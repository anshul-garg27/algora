"""The agentic loop — now powered by the Claude Agent SDK (drives the `claude` CLI).

Instead of calling the Anthropic Messages API directly, this spawns Claude Code
under the hood: Claude writes files and runs them with its OWN built-in tools
(Write / Read / Bash / …) inside a per-session workspace, loops until its code
passes, and then writes the final structured answer.

We translate the SDK's streamed messages into the SAME event dicts the web layer
already forwards as SSE (`step_start`, `thinking_delta`, `text_delta`,
`tool_call`, `tool_result`, `web_search`, `turn_done`, `notice`, `error`), and we
remap Claude Code's tool names/inputs onto the names the existing frontend
expects (`Bash`→`run_command`, `Write`→`write_file`, `Read`→`read_file`,
`Glob`/`Grep`→`list_files`) so the UI renders unchanged.

Auth: the underlying CLI authenticates with ANTHROPIC_API_KEY (API billing) by
default, or with your logged-in subscription when `ALGORA_USE_SUBSCRIPTION=1`
strips the key from the subprocess env (see `config.subprocess_env`). Flipping
that one flag is the ONLY change needed to move from an API key to a Claude
subscription on another machine.
"""

from __future__ import annotations

import base64
import binascii
from pathlib import Path
from typing import Any, AsyncIterator

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    CLINotFoundError,
    ClaudeSDKError,
    ResultMessage,
    StreamEvent,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    query,
)

from . import config
from .prompts import get_system_prompt

# base64 image -> file extension for attachments written into the workspace.
_IMAGE_EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
}


class Agent:
    """Holds one conversation and runs streaming, tool-using turns via Claude Code."""

    def __init__(
        self,
        model: str | None = None,
        mode: str | None = None,
        thinking_enabled: bool = True,
        session_id: str | None = None,
    ) -> None:
        self.model = config.resolve_model(model)
        self.mode = config.resolve_mode(mode)
        self.thinking_enabled = thinking_enabled
        self.session_id = session_id
        # Claude Code's own session id, captured from the stream and reused to
        # `resume` the conversation on follow-up turns (survives server restarts).
        self.cc_session_id: str | None = None
        # Per-turn map of tool_use_id -> display name, so a tool_result can be
        # rendered with the same (remapped) name as its tool_call.
        self._tool_names: dict[str, str] = {}

    @property
    def thinking_on(self) -> bool:
        return bool(self.thinking_enabled)

    def _mode_cfg(self) -> dict:
        return config.MODES[self.mode]

    def _workspace(self) -> Path:
        """Per-conversation workspace subdir so concurrent chats never share files."""
        return config.workspace_for(self.session_id, self.mode)

    # -- persistence -----------------------------------------------------------
    #
    # The render-ready transcript is built separately (store.TranscriptBuilder)
    # from the same events; here we only need to persist Claude Code's session id
    # so a reloaded conversation can be `resume`d with full context.

    def export_messages(self) -> dict:
        return {"cc_session_id": self.cc_session_id}

    def import_messages(self, data: Any) -> None:
        if isinstance(data, dict):
            self.cc_session_id = data.get("cc_session_id")
        # Tolerate the pre-migration list-of-messages format: there's no Claude
        # Code session to resume, so a fresh one starts; the saved transcript
        # still redisplays the old conversation.

    # -- request construction --------------------------------------------------

    def _options(self, cwd: Path) -> ClaudeAgentOptions:
        cfg = self._mode_cfg()
        opts: dict[str, Any] = {
            "system_prompt": get_system_prompt(self.mode),
            "model": self.model,
            "cwd": str(cwd),
            "permission_mode": config.PERMISSION_MODE,
            "allowed_tools": list(config.ALLOWED_TOOLS),
            "setting_sources": list(config.SETTING_SOURCES),
            "max_turns": config.MAX_AGENT_STEPS,
            "include_partial_messages": True,  # delta-level text/thinking streaming
        }
        env = config.subprocess_env()
        if env is not None:  # only in subscription mode; None must NOT be passed
            opts["env"] = env
        if config.CLAUDE_CLI:
            opts["cli_path"] = config.CLAUDE_CLI
        if self.thinking_on:
            # For models with adaptive thinking, DON'T set max_thinking_tokens.
            # Let the Claude CLI use the model's native adaptive thinking (thinks on-demand).
            # For budget-style models, set the budget explicitly.
            is_adaptive = config.uses_adaptive_thinking(self.model)
            if not is_adaptive:
                # Budget thinking: set fixed token budget
                opts["max_thinking_tokens"] = cfg["thinking_budget"]
            # Adaptive models (Opus/Sonnet/Haiku via CLI) handle thinking internally
        if self.cc_session_id:
            opts["resume"] = self.cc_session_id
        return ClaudeAgentOptions(**opts)

    def _build_prompt(self, user_content: list[dict] | str, cwd: Path) -> str:
        """Flatten user content into a prompt string.

        Images are written into the workspace and referenced by path, because the
        Agent SDK takes a text prompt — Claude reads them back with the Read tool.
        """
        if isinstance(user_content, str):
            return user_content or "(no text provided)"

        text_parts: list[str] = []
        image_names: list[str] = []
        idx = 0
        for block in user_content or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif block.get("type") == "image":
                src = block.get("source", {}) or {}
                ext = _IMAGE_EXT.get(src.get("media_type", ""), "png")
                name = f"attachment_{idx}.{ext}"
                try:
                    (cwd / name).write_bytes(base64.b64decode(src.get("data", "")))
                    image_names.append(name)
                    idx += 1
                except (binascii.Error, ValueError, OSError):
                    pass

        prompt = "\n".join(p for p in text_parts if p).strip()
        if image_names:
            refs = ", ".join(f"./{n}" for n in image_names)
            preface = (
                f"[The user attached {len(image_names)} image(s) saved in your "
                f"working directory: {refs}. Read them with the Read tool.]\n\n"
            )
            prompt = preface + prompt
        return prompt or "(no text provided)"

    # -- main loop -------------------------------------------------------------

    async def stream_turn(self, user_content: list[dict] | str) -> AsyncIterator[dict]:
        """Run one user turn to completion, yielding event dicts.

        A single ``query`` call runs Claude Code's full internal agentic loop
        (write → run → read → fix → …) up to ``max_turns``; we surface each piece
        of it as it streams in.
        """
        cwd = self._workspace()
        cwd.mkdir(parents=True, exist_ok=True)
        prompt = self._build_prompt(user_content, cwd)
        self._tool_names = {}

        yield {"type": "step_start", "step": 0}
        try:
            async for message in query(prompt=prompt, options=self._options(cwd)):
                for event in self._translate(message):
                    yield event
        except CLINotFoundError:
            yield {
                "type": "error",
                "message": "The `claude` CLI was not found. Install Claude Code "
                "and ensure it is on PATH (or set ALGORA_CLAUDE_CLI).",
            }
        except ClaudeSDKError as exc:
            yield {"type": "error", "message": f"Agent error: {type(exc).__name__}: {exc}"}
        except Exception as exc:  # never leak a raw 500 mid-stream
            yield {"type": "error", "message": f"{type(exc).__name__}: {exc}"}

    def _translate(self, message: Any) -> list[dict]:
        """Map one SDK message to zero or more frontend event dicts."""
        # Any message that carries a session id lets us resume later.
        sid = getattr(message, "session_id", None)
        if sid:
            self.cc_session_id = sid

        if isinstance(message, StreamEvent):
            return _deltas(message.event)

        if isinstance(message, AssistantMessage):
            out: list[dict] = []
            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    out.append(self._tool_call_event(block))
            return out

        if isinstance(message, UserMessage):
            out = []
            content = message.content
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, ToolResultBlock):
                        out.append(self._tool_result_event(block))
            return out

        if isinstance(message, ResultMessage):
            if message.is_error and message.subtype != "success":
                return [
                    {
                        "type": "error",
                        "message": message.result or f"Run ended: {message.subtype}",
                    }
                ]
            return [
                {
                    "type": "turn_done",
                    "stop_reason": message.stop_reason or message.subtype,
                    "usage": _usage(message),
                }
            ]

        # SystemMessage(init) and anything else: session id already captured.
        return []

    def _tool_call_event(self, block: ToolUseBlock) -> dict:
        name, inp = _map_tool(block.name, block.input)
        if name == "__web_search__":
            return {"type": "web_search", "query": (block.input or {}).get("query")}
        self._tool_names[block.id] = name
        return {"type": "tool_call", "id": block.id, "name": name, "input": inp}

    def _tool_result_event(self, block: ToolResultBlock) -> dict:
        return {
            "type": "tool_result",
            "id": block.tool_use_id,
            "name": self._tool_names.get(block.tool_use_id, ""),
            "output": _stringify(block.content),
            "is_error": bool(block.is_error),
        }


# --- Helpers ------------------------------------------------------------------


def _map_tool(name: str, inp: dict | None) -> tuple[str, dict]:
    """Translate a Claude Code tool name + input into the {name, input} shape the
    existing frontend already knows how to render."""
    inp = inp or {}
    if name == "Bash":
        return "run_command", {"command": inp.get("command", "")}
    if name == "Write":
        return "write_file", {"path": inp.get("file_path", ""), "content": inp.get("content", "")}
    if name == "Read":
        return "read_file", {"path": inp.get("file_path", "")}
    if name in ("Glob", "Grep", "LS"):
        return "list_files", {}
    if name == "WebSearch":
        return "__web_search__", inp
    # Edit / MultiEdit / WebFetch / TodoWrite / … render as a neutral card.
    return name, inp


def _deltas(event: dict | None) -> list[dict]:
    """Extract text/thinking deltas from a raw partial-stream event."""
    if not isinstance(event, dict) or event.get("type") != "content_block_delta":
        return []
    delta = event.get("delta") or {}
    dtype = delta.get("type")
    if dtype == "text_delta" and delta.get("text"):
        return [{"type": "text_delta", "text": delta["text"]}]
    if dtype == "thinking_delta" and delta.get("thinking"):
        return [{"type": "thinking_delta", "text": delta["thinking"]}]
    return []


def _stringify(content: Any) -> str:
    """Flatten a ToolResultBlock's content (str | list of blocks) to text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text") or block.get("content") or "")
            else:
                parts.append(str(block))
        return "\n".join(p for p in parts if p)
    return str(content)


def _usage(message: ResultMessage) -> dict:
    u = message.usage if isinstance(message.usage, dict) else {}
    return {
        "input_tokens": u.get("input_tokens"),
        "output_tokens": u.get("output_tokens"),
        "cache_read_input_tokens": u.get("cache_read_input_tokens"),
        "cache_creation_input_tokens": u.get("cache_creation_input_tokens"),
    }
