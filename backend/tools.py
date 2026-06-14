"""Tool definitions and execution for the agent.

Tools give Claude the ability to create files and run them inside a confined
workspace directory. File-system access is sandboxed to ``WORKSPACE_DIR``;
command/code execution is bounded by a timeout and the captured output is
truncated to protect the context window.
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path

from . import config

# --- Tool schemas advertised to the model -------------------------------------

TOOLS = [
    {
        "name": "write_file",
        "description": (
            "Create or overwrite a file in the workspace. Use this to save your "
            "solution before running it. Returns the resolved path and byte count."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path inside the workspace, e.g. 'solution.py'.",
                },
                "content": {
                    "type": "string",
                    "description": "Full text content to write to the file.",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "read_file",
        "description": "Read back the contents of a file in the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path inside the workspace."}
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_files",
        "description": "List files currently in the workspace.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "run_python",
        "description": (
            "Execute a Python file in the workspace and capture stdout/stderr. "
            "Optionally pass text to the program's standard input (stdin) — use "
            "this to feed competitive-programming test cases. Has a timeout."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path of the .py file to run.",
                },
                "stdin": {
                    "type": "string",
                    "description": "Optional text piped to the program's stdin.",
                },
                "timeout": {
                    "type": "integer",
                    "description": f"Optional seconds (max {config.MAX_EXEC_TIMEOUT}).",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "run_command",
        "description": (
            "Run a shell command in the workspace directory and capture output. "
            "Use for anything beyond a plain python run (e.g. piping input, "
            "running with arguments, quick benchmarks). Has a timeout."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to run."},
                "stdin": {
                    "type": "string",
                    "description": "Optional text piped to the command's stdin.",
                },
                "timeout": {
                    "type": "integer",
                    "description": f"Optional seconds (max {config.MAX_EXEC_TIMEOUT}).",
                },
            },
            "required": ["command"],
        },
    {
        "name": "search_knowledge_base",
        "description": (
            "Search the massive offline database of past mock interviews, transcripts, "
            "Walmart architecture details, and Amazon LP answers. Use this to lookup "
            "exact stories, tech specs, or past Q&A. Returns matching lines from files."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The exact term or regex to search for (e.g. 'conflict', 'kafka', 'bullet-1')."},
            },
            "required": ["query"],
        },
    },
]


# --- Helpers ------------------------------------------------------------------


class ToolError(Exception):
    """Raised for predictable tool failures returned to the model as is_error."""


def _safe_path(base: Path, rel_path: str) -> Path:
    """Resolve ``rel_path`` inside ``base``, refusing escapes.

    Prevents path traversal (``../``) and absolute paths from reaching outside
    the (per-session) workspace directory.
    """
    if not rel_path or not str(rel_path).strip():
        raise ToolError("path must be a non-empty string")

    root = base.resolve()
    candidate = (root / rel_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise ToolError(
            f"path '{rel_path}' escapes the workspace; only paths inside the "
            "workspace are allowed."
        )
    return candidate


def _truncate(text: str) -> str:
    limit = config.MAX_OUTPUT_CHARS
    if len(text) <= limit:
        return text
    head = text[: limit // 2]
    tail = text[-limit // 2 :]
    omitted = len(text) - limit
    return f"{head}\n\n... [{omitted} chars truncated] ...\n\n{tail}"


def _clamp_timeout(value: object) -> int:
    try:
        secs = int(value) if value is not None else config.DEFAULT_EXEC_TIMEOUT
    except (TypeError, ValueError):
        secs = config.DEFAULT_EXEC_TIMEOUT
    return max(1, min(secs, config.MAX_EXEC_TIMEOUT))


# --- Individual tool implementations ------------------------------------------


def _write_file(base: Path, path: str, content: str) -> str:
    if content is None:
        content = ""
    encoded = content.encode("utf-8")
    if len(encoded) > config.MAX_FILE_BYTES:
        raise ToolError(
            f"file is {len(encoded)} bytes, exceeding the {config.MAX_FILE_BYTES} byte limit"
        )
    target = _safe_path(base, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Wrote {len(encoded)} bytes to {target.relative_to(base.resolve())}"


def _read_file(base: Path, path: str) -> str:
    target = _safe_path(base, path)
    if not target.exists():
        raise ToolError(f"file not found: {path}")
    if not target.is_file():
        raise ToolError(f"not a file: {path}")
    return _truncate(target.read_text(encoding="utf-8", errors="replace"))


def _list_files(base: Path) -> str:
    root = base.resolve()
    if not root.exists():
        return "(workspace is empty)"
    entries = sorted(p for p in root.rglob("*") if p.is_file())
    if not entries:
        return "(workspace is empty)"
    return "\n".join(f"{p.relative_to(root)}  ({p.stat().st_size} bytes)" for p in entries)


def _format_run_result(proc: subprocess.CompletedProcess, timed_out: bool, timeout: int) -> str:
    parts = []
    if timed_out:
        parts.append(f"[TIMEOUT after {timeout}s — process killed]")
    parts.append(f"[exit code: {proc.returncode}]")
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    parts.append(f"--- stdout ---\n{stdout if stdout else '(empty)'}")
    parts.append(f"--- stderr ---\n{stderr if stderr else '(empty)'}")
    return _truncate("\n".join(parts))


def _run(args, stdin: str | None, timeout: int, *, shell: bool, cwd: Path) -> str:
    cwd.mkdir(parents=True, exist_ok=True)
    timed_out = False
    try:
        proc = subprocess.run(
            args,
            input=stdin if stdin is not None else "",
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd),
            shell=shell,
        )
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        proc = subprocess.CompletedProcess(
            args=args,
            returncode=-1,
            stdout=exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
            stderr=exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or ""),
        )
    except FileNotFoundError as exc:
        raise ToolError(str(exc)) from exc
    return _format_run_result(proc, timed_out, timeout)


def _run_python(base: Path, path: str, stdin: str | None = None, timeout: object = None) -> str:
    target = _safe_path(base, path)
    if not target.exists():
        raise ToolError(f"file not found: {path}. Write it first with write_file.")
    secs = _clamp_timeout(timeout)
    # Use the same interpreter that runs the server for consistency.
    return _run([sys.executable, str(target)], stdin, secs, shell=False, cwd=base)


def _run_command(base: Path, command: str, stdin: str | None = None, timeout: object = None) -> str:
    if not command or not command.strip():
        raise ToolError("command must be a non-empty string")
    secs = _clamp_timeout(timeout)
    return _run(command, stdin, secs, shell=True, cwd=base)


def _search_knowledge_base(query: str) -> str:
    if not query:
        raise ToolError("query must not be empty")
    kb_path = Path(__file__).resolve().parent.parent / "data" / "knowledge_base"
    if not kb_path.exists():
        return "Knowledge base directory not found. Data has not been imported yet."
    cmd = ["grep", "-rni", query, str(kb_path)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        out = proc.stdout.strip()
        if not out:
            return "No matches found in the knowledge base."
        # Strip absolute path for cleaner output
        clean_out = out.replace(str(kb_path) + "/", "")
        return _truncate(clean_out)
    except subprocess.TimeoutExpired:
        raise ToolError("Search timed out.")
    except Exception as exc:
        raise ToolError(f"Search error: {exc}")


# --- Dispatch -----------------------------------------------------------------

_DISPATCH = {
    "write_file": lambda i, b: _write_file(b, i.get("path", ""), i.get("content", "")),
    "read_file": lambda i, b: _read_file(b, i.get("path", "")),
    "list_files": lambda i, b: _list_files(b),
    "run_python": lambda i, b: _run_python(b, i.get("path", ""), i.get("stdin"), i.get("timeout")),
    "run_command": lambda i, b: _run_command(b, i.get("command", ""), i.get("stdin"), i.get("timeout")),
    "search_knowledge_base": lambda i, b: _search_knowledge_base(i.get("query", "")),
}


def execute_tool(name: str, tool_input: dict, base: Path | None = None) -> tuple[str, bool]:
    """Run a tool by name within ``base`` workspace. Returns (output, is_error).

    Never raises: predictable failures are returned as error strings so the
    agent loop can feed them back to the model and let it recover.
    """
    base = (base or config.WORKSPACE_DIR)
    handler = _DISPATCH.get(name)
    if handler is None:
        return f"Unknown tool: {name}", True
    try:
        return handler(tool_input or {}, base), False
    except ToolError as exc:
        return f"Tool error: {exc}", True
    except Exception as exc:  # defensive: surface unexpected failures to the model
        return f"Unexpected error in tool '{name}': {type(exc).__name__}: {exc}", True
