"""Conversation persistence — one JSON file per session under CONV_DIR.

Each file stores:
  - messages:   the raw agent messages (JSON-safe) so a conversation can be
                CONTINUED with full context, even after a server restart.
  - transcript: a coalesced, render-ready view (user/assistant blocks) so the UI
                can REDISPLAY the conversation exactly.
plus metadata (mode, title, timestamps).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from . import config


def _path(session_id: str) -> Path:
    return config.CONV_DIR / f"{config.session_slug(session_id)}.json"


def load(session_id: str) -> dict | None:
    p = _path(session_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def save(session_id: str, mode: str, title: str, messages: list, transcript: list) -> None:
    """Write/overwrite the full conversation. `transcript` is the COMPLETE list."""
    config.CONV_DIR.mkdir(parents=True, exist_ok=True)
    existing = load(session_id)
    created = existing.get("created_at") if existing else time.time()
    data = {
        "session_id": session_id,
        "mode": mode,
        "title": (title or "Untitled").strip()[:120],
        "created_at": created,
        "updated_at": time.time(),
        "messages": messages,
        "transcript": transcript,
    }
    tmp = _path(session_id).with_suffix(".json.tmp")
    # default=str so one unexpected (non-serializable) block never loses the
    # whole turn's history.
    tmp.write_text(json.dumps(data, default=str), encoding="utf-8")
    tmp.replace(_path(session_id))  # atomic


def list_all() -> list[dict]:
    """Metadata for every saved conversation, newest first."""
    if not config.CONV_DIR.exists():
        return []
    out = []
    for p in config.CONV_DIR.glob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        out.append(
            {
                "session_id": d.get("session_id"),
                "mode": d.get("mode"),
                "title": d.get("title", "Untitled"),
                "updated_at": d.get("updated_at", 0),
                "turns": sum(1 for t in d.get("transcript", []) if t.get("role") == "user"),
            }
        )
    out.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
    return out


def delete(session_id: str) -> bool:
    p = _path(session_id)
    if p.exists():
        p.unlink()
        return True
    return False


# --- Transcript builder: coalesces the streamed event dicts into render-ready items ---


class TranscriptBuilder:
    """Consumes the same event dicts the server streams and produces a compact,
    render-ready transcript for one user turn: [user_item, assistant_item]."""

    def __init__(self) -> None:
        self._user: dict | None = None
        self._blocks: list[dict] = []
        self._text = ""
        self._thinking = ""
        self._tool_by_id: dict[str, dict] = {}
        self._usage: dict | None = None

    def add_user(self, user_content) -> None:
        text, images = "", 0
        if isinstance(user_content, list):
            for b in user_content:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text":
                    text = b.get("text", "")
                elif b.get("type") == "image":
                    images += 1
        elif isinstance(user_content, str):
            text = user_content
        self._user = {"role": "user", "text": text, "images": images}

    def _flush_text(self) -> None:
        if self._text.strip():
            self._blocks.append({"k": "text", "md": self._text})
        self._text = ""

    def consume(self, ev: dict) -> None:
        t = ev.get("type")
        if t == "step_start":
            self._flush_text()
        elif t == "thinking_delta":
            self._thinking += ev.get("text", "")
        elif t == "text_delta":
            self._text += ev.get("text", "")
        elif t == "web_search":
            self._flush_text()
            self._blocks.append({"k": "web", "query": ev.get("query")})
        elif t == "tool_call":
            self._flush_text()
            block = {
                "k": "tool",
                "id": ev.get("id"),
                "name": ev.get("name"),
                "input": ev.get("input"),
                "output": None,
                "is_error": False,
            }
            self._blocks.append(block)
            self._tool_by_id[ev.get("id")] = block
        elif t == "tool_result":
            block = self._tool_by_id.get(ev.get("id"))
            if block is not None:
                block["output"] = ev.get("output")
                block["is_error"] = bool(ev.get("is_error"))
        elif t == "turn_done":
            self._flush_text()
            self._usage = ev.get("usage")

    def items(self) -> list[dict]:
        self._flush_text()
        assistant = {
            "role": "assistant",
            "thinking": self._thinking,
            "blocks": self._blocks,
            "usage": self._usage,
        }
        out = []
        if self._user:
            out.append(self._user)
        out.append(assistant)
        return out
