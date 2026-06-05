"""Tests for the sandboxed tool layer."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import config, tools  # noqa: E402


def test_write_and_read_roundtrip():
    out, err = tools.execute_tool("write_file", {"path": "rt.py", "content": "print('hi')"})
    assert not err
    assert "Wrote" in out
    out, err = tools.execute_tool("read_file", {"path": "rt.py"})
    assert not err
    assert "print('hi')" in out


def test_path_traversal_is_blocked():
    out, err = tools.execute_tool("write_file", {"path": "../escape.txt", "content": "x"})
    assert err
    assert "escapes the workspace" in out
    assert not (config.WORKSPACE_DIR.parent / "escape.txt").exists()


def test_absolute_path_blocked():
    out, err = tools.execute_tool("write_file", {"path": "/tmp/evil.txt", "content": "x"})
    assert err
    assert "escapes the workspace" in out


def test_run_python_captures_stdout():
    tools.execute_tool("write_file", {"path": "hello.py", "content": "print('hello world')"})
    out, err = tools.execute_tool("run_python", {"path": "hello.py"})
    assert not err
    assert "hello world" in out
    assert "exit code: 0" in out


def test_run_python_with_stdin():
    code = "import sys\ndata=sys.stdin.read().split()\nprint(int(data[0])+int(data[1]))"
    tools.execute_tool("write_file", {"path": "add.py", "content": code})
    out, err = tools.execute_tool("run_python", {"path": "add.py", "stdin": "2 40\n"})
    assert not err
    assert "42" in out


def test_run_python_nonzero_exit_reports_stderr():
    tools.execute_tool("write_file", {"path": "boom.py", "content": "raise ValueError('nope')"})
    out, err = tools.execute_tool("run_python", {"path": "boom.py"})
    # process error is not a tool error; the run itself succeeded in capturing it
    assert not err
    assert "ValueError" in out
    assert "exit code: 1" in out


def test_run_python_timeout():
    tools.execute_tool("write_file", {"path": "loop.py", "content": "while True: pass"})
    out, err = tools.execute_tool("run_python", {"path": "loop.py", "timeout": 1})
    assert not err
    assert "TIMEOUT" in out


def test_run_python_missing_file_is_tool_error():
    out, err = tools.execute_tool("run_python", {"path": "does_not_exist.py"})
    assert err
    assert "not found" in out


def test_run_command_echo():
    out, err = tools.execute_tool("run_command", {"command": "echo agentic"})
    assert not err
    assert "agentic" in out


def test_timeout_is_clamped_to_max():
    assert tools._clamp_timeout(99999) == config.MAX_EXEC_TIMEOUT
    assert tools._clamp_timeout(-5) == 1
    assert tools._clamp_timeout(None) == config.DEFAULT_EXEC_TIMEOUT
    assert tools._clamp_timeout("abc") == config.DEFAULT_EXEC_TIMEOUT


def test_oversized_file_rejected():
    big = "x" * (config.MAX_FILE_BYTES + 1)
    out, err = tools.execute_tool("write_file", {"path": "big.txt", "content": big})
    assert err
    assert "exceeding" in out


def test_unknown_tool():
    out, err = tools.execute_tool("frobnicate", {})
    assert err
    assert "Unknown tool" in out


def test_execute_tool_respects_base_dir(tmp_path):
    base = tmp_path / "sess"
    out, err = tools.execute_tool("write_file", {"path": "x.py", "content": "print(1)"}, base)
    assert not err
    assert (base / "x.py").exists()
    # run within the isolated base
    out, err = tools.execute_tool("run_python", {"path": "x.py"}, base)
    assert not err and "exit code: 0" in out
    # path traversal is still blocked relative to the base dir
    out, err = tools.execute_tool("write_file", {"path": "../../escape", "content": "y"}, base)
    assert err and "escapes the workspace" in out


def test_two_bases_are_isolated(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    tools.execute_tool("write_file", {"path": "only_in_a.py", "content": "x=1"}, a)
    out_a, _ = tools.execute_tool("list_files", {}, a)
    out_b, _ = tools.execute_tool("list_files", {}, b)
    assert "only_in_a.py" in out_a
    assert "only_in_a.py" not in out_b


def test_list_files_shows_written_file():
    tools.execute_tool("write_file", {"path": "listed.py", "content": "x=1"})
    out, err = tools.execute_tool("list_files", {})
    assert not err
    assert "listed.py" in out


def test_output_truncation():
    long = "A" * (config.MAX_OUTPUT_CHARS + 5000)
    truncated = tools._truncate(long)
    assert "truncated" in truncated
    assert len(truncated) < len(long)
