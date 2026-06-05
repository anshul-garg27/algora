"""FastAPI app: serves the chat API (SSE) and the static frontend.

One process serves everything and binds to 0.0.0.0, so the same URL works from
the host laptop and from a phone on the same hotspot/network.
"""

from __future__ import annotations

import json
import logging
import shutil
import threading
from collections import defaultdict
from typing import Iterator

from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, store
from .agent import Agent
from .store import TranscriptBuilder

app = FastAPI(title="Claude DSA Agent", version="1.0.0")

# Same-origin SPA, so cross-origin is denied by default; widen via env if needed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _warn_if_open() -> None:
    if not config.ALGORA_TOKEN:
        logging.getLogger("uvicorn.error").warning(
            "SECURITY: no ALGORA_TOKEN set — the API (which can run shell/Python "
            "on this machine) is OPEN to your network. Fine on a private hotspot; "
            "set ALGORA_TOKEN=<secret> to require auth on a shared network."
        )


def _check_token(token: str | None) -> bool:
    """True if access is allowed (no token configured, or it matches)."""
    if not config.ALGORA_TOKEN:
        return True
    return bool(token) and token == config.ALGORA_TOKEN


# --- Session store ------------------------------------------------------------

_sessions: dict[str, Agent] = {}
_locks: defaultdict[str, threading.Lock] = defaultdict(threading.Lock)
_store_lock = threading.Lock()


def _get_agent(
    session_id: str, model: str | None, mode: str | None, thinking_enabled: bool
) -> Agent:
    with _store_lock:
        agent = _sessions.get(session_id)
        if agent is None:
            agent = Agent(
                model=model, mode=mode, thinking_enabled=thinking_enabled, session_id=session_id
            )
            # Resume a previously-saved conversation so follow-ups keep context
            # (even after a server restart).
            saved = store.load(session_id)
            if saved:
                agent.import_messages(saved.get("messages", []))
                if not mode:
                    agent.mode = config.resolve_mode(saved.get("mode"))
            _sessions[session_id] = agent
        else:
            # Allow switching model / mode / thinking mid-session.
            if model is not None:
                agent.model = config.resolve_model(model)
            if mode is not None:
                agent.mode = config.resolve_mode(mode)
            agent.thinking_enabled = thinking_enabled
        return agent


# --- Request models -----------------------------------------------------------


class ImagePayload(BaseModel):
    media_type: str = Field(..., description="e.g. image/png, image/jpeg")
    data: str = Field(..., description="base64-encoded image bytes (no data URL prefix)")


class ChatRequest(BaseModel):
    session_id: str
    message: str = ""
    images: list[ImagePayload] = Field(default_factory=list)
    model: str | None = None
    mode: str | None = None  # "assessment" | "interview"
    thinking: int | None = None  # 0 disables thinking; omitted/non-zero enables it


# --- Helpers ------------------------------------------------------------------


def _build_user_content(req: ChatRequest) -> list[dict]:
    content: list[dict] = []
    for img in req.images:
        content.append(
            {
                "type": "image",
                "source": {"type": "base64", "media_type": img.media_type, "data": img.data},
            }
        )
    text = (req.message or "").strip()
    if text:
        content.append({"type": "text", "text": text})
    return content


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


def _persist_turn(agent: Agent, session_id: str, mode: str, turn_items: list) -> None:
    """Append this turn to the saved conversation (history)."""
    try:
        existing = store.load(session_id)
        transcript = (existing.get("transcript", []) if existing else []) + turn_items
        title = (existing or {}).get("title") or _title_from(turn_items)
        store.save(session_id, mode, title, agent.export_messages(), transcript)
    except Exception:  # history is best-effort; never break the chat
        pass


def _title_from(turn_items: list) -> str:
    for it in turn_items:
        if it.get("role") == "user" and it.get("text"):
            return it["text"]
    return "Untitled"


def _stream_events(
    agent: Agent, lock: threading.Lock, user_content: list[dict], session_id: str, mode: str
) -> Iterator[str]:
    """Wrap the agent generator as SSE, guarding the session with a lock, and
    record a render-ready transcript so the conversation can be reopened later."""
    acquired = lock.acquire(blocking=False)
    if not acquired:
        yield _sse({"type": "error", "message": "This session is already processing a request."})
        return
    tb = TranscriptBuilder()
    tb.add_user(user_content)
    try:
        for event in agent.stream_turn(user_content):
            tb.consume(event)
            yield _sse(event)
    except Exception as exc:  # never leak a raw 500 mid-stream
        yield _sse({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
    finally:
        _persist_turn(agent, session_id, agent.mode, tb.items())
        yield _sse({"type": "done"})
        lock.release()


# --- Routes -------------------------------------------------------------------


def _lan_ips() -> list[str]:
    """This machine's LAN IPv4 address(es), so the UI can tell you the URL to open
    on a phone/iPad on the same network. The UDP-connect trick reliably yields the
    address of the interface that reaches the network without sending any packets."""
    import socket

    ips: list[str] = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ips.append(s.getsockname()[0])
        finally:
            s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    return ips


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "build": config.BUILD,  # source hash — compare to confirm the server isn't stale
        "models": config.MODELS,
        "default_model": config.DEFAULT_MODEL_KEY,
        "modes": list(config.MODES.keys()),
        "default_mode": config.DEFAULT_MODE,
        "auth_required": bool(config.ALGORA_TOKEN),
        "workspace": str(config.WORKSPACE_DIR),
        # LAN IP(s) of this server — the client builds an "open on another device" URL
        # by pairing these with its own scheme+port. Same network only; no new exposure.
        "lan_hosts": _lan_ips(),
    }


def _unauthorized() -> JSONResponse:
    return JSONResponse(status_code=401, content={"error": "Invalid or missing access token."})


@app.post("/api/reset")
def reset(payload: dict, x_algora_token: str | None = Header(default=None)):
    if not _check_token(x_algora_token):
        return _unauthorized()
    session_id = payload.get("session_id", "")
    with _store_lock:
        _sessions.pop(session_id, None)
    # Remove this conversation's workspace dir so a fresh problem starts clean.
    ws = config.workspace_for(session_id)
    if session_id and ws != config.WORKSPACE_DIR and ws.is_relative_to(config.WORKSPACE_DIR):
        shutil.rmtree(ws, ignore_errors=True)
    return {"status": "reset", "session_id": session_id}


@app.post("/api/chat")
def chat(req: ChatRequest, x_algora_token: str | None = Header(default=None)):
    if not _check_token(x_algora_token):
        return _unauthorized()
    user_content = _build_user_content(req)
    if not user_content:
        return JSONResponse(
            status_code=400,
            content={"error": "Provide a message and/or at least one image."},
        )
    thinking_enabled = req.thinking is None or req.thinking != 0
    agent = _get_agent(req.session_id, req.model, req.mode, thinking_enabled)
    lock = _locks[req.session_id]
    return StreamingResponse(
        _stream_events(agent, lock, user_content, req.session_id, agent.mode),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable proxy buffering
        },
    )


# --- Conversation history -----------------------------------------------------


@app.get("/api/conversations")
def list_conversations(mode: str | None = None, x_algora_token: str | None = Header(default=None)):
    if not _check_token(x_algora_token):
        return _unauthorized()
    items = store.list_all()
    if mode:
        items = [c for c in items if c.get("mode") == mode]
    return {"conversations": items}


@app.get("/api/conversations/{session_id}")
def get_conversation(session_id: str, x_algora_token: str | None = Header(default=None)):
    if not _check_token(x_algora_token):
        return _unauthorized()
    data = store.load(session_id)
    if not data:
        return JSONResponse(status_code=404, content={"error": "Not found."})
    return {
        "session_id": session_id,
        "mode": data.get("mode"),
        "title": data.get("title"),
        "transcript": data.get("transcript", []),
    }


@app.delete("/api/conversations/{session_id}")
def delete_conversation(session_id: str, x_algora_token: str | None = Header(default=None)):
    if not _check_token(x_algora_token):
        return _unauthorized()
    with _store_lock:
        _sessions.pop(session_id, None)
    store.delete(session_id)
    return {"status": "deleted", "session_id": session_id}


# Static frontend mounted last so /api/* routes take precedence.
app.mount("/", StaticFiles(directory=str(config.FRONTEND_DIR), html=True), name="frontend")
