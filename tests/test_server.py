"""API-surface tests via FastAPI TestClient (Anthropic client mocked)."""

import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import agent as agent_mod  # noqa: E402
from backend.server import app  # noqa: E402

client = TestClient(app)


class _Stream:
    def __init__(self, events, final):
        self._e, self._f = events, final

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        return iter(self._e)

    def get_final_message(self):
        return self._f


class _Messages:
    def __init__(self, scripted):
        self.scripted = scripted

    def stream(self, **kw):
        return self.scripted.pop(0)


def _usage():
    return SimpleNamespace(input_tokens=1, output_tokens=1,
                           cache_read_input_tokens=0, cache_creation_input_tokens=0)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "sonnet" in body["models"]


def test_chat_requires_content():
    r = client.post("/api/chat", json={"session_id": "empty", "message": "  "})
    assert r.status_code == 400


def test_index_served():
    r = client.get("/")
    assert r.status_code == 200
    assert "Algora" in r.text


def test_chat_streams_events(monkeypatch):
    text_block = SimpleNamespace(type="text", text="answer: 4")
    step = _Stream(events=[], final=SimpleNamespace(
        content=[text_block], stop_reason="end_turn", usage=_usage()))
    monkeypatch.setattr(agent_mod, "_client", SimpleNamespace(messages=_Messages([step])))

    r = client.post("/api/chat", json={
        "session_id": "sess-stream", "message": "2+2?", "thinking": 0, "model": "sonnet"})
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    body = r.text
    assert "turn_done" in body
    assert body.strip().endswith("}")  # ends with a 'done' event
    assert '"type": "done"' in body


def test_reset():
    r = client.post("/api/reset", json={"session_id": "whatever"})
    assert r.status_code == 200
    assert r.json()["status"] == "reset"


def test_auth_token_enforced(monkeypatch):
    from backend import config
    monkeypatch.setattr(config, "ALGORA_TOKEN", "secret123")
    # health advertises that auth is required
    assert client.get("/api/health").json()["auth_required"] is True
    # missing / wrong token -> 401 on both endpoints
    assert client.post("/api/chat", json={"session_id": "a", "message": "hi"}).status_code == 401
    assert client.post("/api/chat", json={"session_id": "a", "message": "hi"},
                       headers={"X-Algora-Token": "nope"}).status_code == 401
    assert client.post("/api/reset", json={"session_id": "a"}).status_code == 401
    # correct token -> reset works
    r = client.post("/api/reset", json={"session_id": "a"}, headers={"X-Algora-Token": "secret123"})
    assert r.status_code == 200


def test_no_auth_by_default():
    # default (no token) leaves the API open and health says so
    assert client.get("/api/health").json()["auth_required"] is False


def test_conversation_history_roundtrip(monkeypatch, tmp_path):
    from backend import config
    monkeypatch.setattr(config, "CONV_DIR", tmp_path / "conv")

    class _Block:  # a content block that serializes like a real SDK pydantic block
        def __init__(self, **kw):
            self.__dict__.update(kw)
        def model_dump(self, exclude_none=True):
            return dict(self.__dict__)

    text_block = _Block(type="text", text="hello answer")
    step = _Stream(events=[], final=SimpleNamespace(
        content=[text_block], stop_reason="end_turn", usage=_usage()))
    monkeypatch.setattr(agent_mod, "_client", SimpleNamespace(messages=_Messages([step])))

    sid = "conv-sess:hld"
    r = client.post("/api/chat", json={"session_id": sid, "mode": "hld",
                                       "message": "design a thing", "thinking": 0})
    assert r.status_code == 200
    list(r.iter_lines())  # drain the stream so the turn (and persistence) completes

    # the conversation now appears in history, filtered by mode
    convs = client.get("/api/conversations?mode=hld").json()["conversations"]
    assert any(c["session_id"] == sid and c["title"].startswith("design a thing") for c in convs)
    assert client.get("/api/conversations?mode=assessment").json()["conversations"] == [] or all(
        c["session_id"] != sid for c in client.get("/api/conversations?mode=assessment").json()["conversations"])

    # the transcript is render-ready (user item + assistant blocks)
    conv = client.get(f"/api/conversations/{sid}").json()
    roles = [it["role"] for it in conv["transcript"]]
    assert "user" in roles and "assistant" in roles

    # delete removes it
    assert client.request("DELETE", f"/api/conversations/{sid}").status_code == 200
    assert client.get(f"/api/conversations/{sid}").status_code == 404
