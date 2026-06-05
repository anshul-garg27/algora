"""Tests for the agentic loop, with the Anthropic client mocked.

We don't hit the network here; we script the streaming responses so the loop's
tool-execution, history-building, event-emission, and prompt-cache wiring are
all exercised deterministically.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import agent as agent_mod  # noqa: E402


# --- fakes mirroring the SDK streaming surface --------------------------------


class FakeStream:
    def __init__(self, events, final):
        self._events = events
        self._final = final

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        return iter(self._events)

    def get_final_message(self):
        return self._final


class FakeMessages:
    def __init__(self, scripted):
        self.scripted = scripted
        self.calls = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        item = self.scripted.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def delta_event(kind, text):
    delta = SimpleNamespace(type=kind, thinking=text, text=text)
    return SimpleNamespace(type="content_block_delta", delta=delta)


def usage(**kw):
    base = dict(input_tokens=10, output_tokens=5, cache_read_input_tokens=0,
                cache_creation_input_tokens=0)
    base.update(kw)
    return SimpleNamespace(**base)


def test_agent_runs_tool_then_finishes(monkeypatch, tmp_path):
    # Step 1: assistant emits text + a write_file tool_use.
    tool_block = SimpleNamespace(
        type="tool_use", id="t1", name="write_file",
        input={"path": "agent_test.py", "content": "print(7*6)"},
    )
    text_block = SimpleNamespace(type="text", text="writing the file")
    step1 = FakeStream(
        events=[delta_event("text_delta", "writing the file")],
        final=SimpleNamespace(content=[text_block, tool_block],
                              stop_reason="tool_use", usage=usage()),
    )
    # Step 2: assistant finishes.
    done_block = SimpleNamespace(type="text", text="done: 42")
    step2 = FakeStream(
        events=[delta_event("text_delta", "done: 42")],
        final=SimpleNamespace(content=[done_block], stop_reason="end_turn",
                              usage=usage(cache_read_input_tokens=123)),
    )

    fake_msgs = FakeMessages([step1, step2])
    monkeypatch.setattr(agent_mod, "_client", SimpleNamespace(messages=fake_msgs))

    a = agent_mod.Agent(model="sonnet", thinking_enabled=False)
    events = list(a.stream_turn("solve 7*6"))
    types = [e["type"] for e in events]

    assert "tool_call" in types
    assert "tool_result" in types
    assert types[-1] == "turn_done"

    # the tool actually executed and wrote a real file in the workspace
    tool_results = [e for e in events if e["type"] == "tool_result"]
    assert tool_results and not tool_results[0]["is_error"]

    # final usage surfaced the cache read
    done = events[-1]
    assert done["usage"]["cache_read_input_tokens"] == 123

    # history shape: user, assistant(tool), user(tool_result), assistant(final)
    assert len(a.messages) == 4
    assert a.messages[0]["role"] == "user"
    assert a.messages[1]["role"] == "assistant"
    assert a.messages[2]["role"] == "user"
    assert a.messages[2]["content"][0]["type"] == "tool_result"
    assert a.messages[3]["role"] == "assistant"


def _one_step():
    block = SimpleNamespace(type="text", text="hi")
    return FakeStream(events=[], final=SimpleNamespace(
        content=[block], stop_reason="end_turn", usage=usage()))


def test_opus_uses_adaptive_thinking(monkeypatch):
    from backend import config
    fake_msgs = FakeMessages([_one_step()])
    monkeypatch.setattr(agent_mod, "_client", SimpleNamespace(messages=fake_msgs))

    a = agent_mod.Agent(model="opus", thinking_enabled=True)
    list(a.stream_turn("hi"))
    call = fake_msgs.calls[0]
    # adaptive config is sent entirely via extra_body (no typed thinking kwarg)
    assert "thinking" not in call
    assert call["extra_body"]["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert call["extra_body"]["output_config"] == {"effort": config.MODES["assessment"]["effort"]}
    # system prompt is still sent as a cacheable block
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}


def test_sonnet_uses_budget_thinking(monkeypatch):
    from backend import config
    fake_msgs = FakeMessages([_one_step()])
    monkeypatch.setattr(agent_mod, "_client", SimpleNamespace(messages=fake_msgs))

    a = agent_mod.Agent(model="sonnet", thinking_enabled=True)
    list(a.stream_turn("hi"))
    call = fake_msgs.calls[0]
    assert call["thinking"] == {
        "type": "enabled",
        "budget_tokens": config.MODES["assessment"]["thinking_budget"],
    }
    assert "extra_body" not in call


def test_haiku_uses_budget_thinking(monkeypatch):
    from backend import config
    fake_msgs = FakeMessages([_one_step()])
    monkeypatch.setattr(agent_mod, "_client", SimpleNamespace(messages=fake_msgs))

    a = agent_mod.Agent(model="haiku", thinking_enabled=True)
    list(a.stream_turn("hi"))
    assert fake_msgs.calls[0]["thinking"]["type"] == "enabled"


def test_interview_mode_uses_interview_settings(monkeypatch):
    from backend import config
    fake_msgs = FakeMessages([_one_step()])
    monkeypatch.setattr(agent_mod, "_client", SimpleNamespace(messages=fake_msgs))

    a = agent_mod.Agent(model="sonnet", mode="interview")
    list(a.stream_turn("hi"))
    call = fake_msgs.calls[0]
    assert call["max_tokens"] == config.MODES["interview"]["max_tokens"]
    # the interview system prompt is what's sent, not the assessment one
    sys_text = call["system"][0]["text"]
    assert "Problem Understanding" in sys_text
    assert "interview" in sys_text.lower()


def test_lld_hld_modes_use_their_prompts_and_128k(monkeypatch):
    from backend import config
    fake_msgs = FakeMessages([_one_step(), _one_step()])
    monkeypatch.setattr(agent_mod, "_client", SimpleNamespace(messages=fake_msgs))

    a_lld = agent_mod.Agent(model="opus", mode="lld")
    list(a_lld.stream_turn("design a parking lot"))
    c_lld = fake_msgs.calls[0]
    assert c_lld["max_tokens"] == config.MODES["lld"]["max_tokens"] == 128000
    assert "Low Level Design" in c_lld["system"][0]["text"]

    a_hld = agent_mod.Agent(model="opus", mode="hld")
    list(a_hld.stream_turn("design a url shortener"))
    c_hld = fake_msgs.calls[1]
    assert c_hld["max_tokens"] == 128000
    assert "System Design" in c_hld["system"][0]["text"] or "High Level" in c_hld["system"][0]["text"]


def test_tools_include_web_search_when_enabled(monkeypatch):
    from backend import config
    fake_msgs = FakeMessages([_one_step()])
    monkeypatch.setattr(agent_mod, "_client", SimpleNamespace(messages=fake_msgs))
    monkeypatch.setattr(config, "ENABLE_WEB_SEARCH", True)

    a = agent_mod.Agent(model="opus", mode="hld")
    list(a.stream_turn("hi"))
    tools = fake_msgs.calls[0]["tools"]
    names = [t.get("name") for t in tools]
    assert "web_search" in names
    ws = next(t for t in tools if t.get("name") == "web_search")
    assert ws["type"] == "web_search_20250305"
    # client tools are still present
    assert "write_file" in names and "run_python" in names


def test_opus_gets_1m_context_header(monkeypatch):
    fake_msgs = FakeMessages([_one_step()])
    monkeypatch.setattr(agent_mod, "_client", SimpleNamespace(messages=fake_msgs))
    a = agent_mod.Agent(model="opus", mode="hld")
    list(a.stream_turn("hi"))
    hdrs = fake_msgs.calls[0].get("extra_headers", {})
    assert "anthropic-beta" in hdrs and "context-1m" in hdrs["anthropic-beta"]


def test_pause_turn_continues_instead_of_truncating(monkeypatch):
    # A server-side web_search can pause the turn; the loop must resend and continue.
    paused = FakeStream(
        events=[delta_event("text_delta", "searching…")],
        final=SimpleNamespace(content=[SimpleNamespace(type="text", text="searching…")],
                              stop_reason="pause_turn", usage=usage()))
    finished = FakeStream(
        events=[delta_event("text_delta", "the answer")],
        final=SimpleNamespace(content=[SimpleNamespace(type="text", text="the answer")],
                              stop_reason="end_turn", usage=usage()))
    fm = FakeMessages([paused, finished])
    monkeypatch.setattr(agent_mod, "_client", SimpleNamespace(messages=fm))

    a = agent_mod.Agent(model="opus", mode="hld")
    events = list(a.stream_turn("design a url shortener"))
    types = [e["type"] for e in events]
    assert len(fm.calls) == 2  # re-invoked after the pause instead of stopping
    assert types.count("turn_done") == 1 and types[-1] == "turn_done"
    # no tool_result injected between the paused turn and the continuation
    assert [m["role"] for m in a.messages] == ["user", "assistant", "assistant"]


def test_default_model_is_opus():
    from backend import config
    assert config.DEFAULT_MODEL_KEY == "opus"
    assert config.resolve_model(None) == config.MODELS["opus"]


def test_assessment_and_interview_prompts_differ(monkeypatch):
    fake_msgs = FakeMessages([_one_step(), _one_step()])
    monkeypatch.setattr(agent_mod, "_client", SimpleNamespace(messages=fake_msgs))
    a1 = agent_mod.Agent(model="sonnet", mode="assessment")
    list(a1.stream_turn("hi"))
    a2 = agent_mod.Agent(model="sonnet", mode="interview")
    list(a2.stream_turn("hi"))
    assert fake_msgs.calls[0]["system"][0]["text"] != fake_msgs.calls[1]["system"][0]["text"]


def test_thinking_config_classification():
    from backend import config
    assert config.uses_adaptive_thinking("claude-opus-4-8") is True
    assert config.uses_adaptive_thinking("claude-sonnet-4-6") is False
    assert config.uses_adaptive_thinking("claude-haiku-4-5-20251001") is False


class _FakeThinkingError(agent_mod.anthropic.APIStatusError):
    """Mimics the 400 a model raises when it rejects the thinking config."""

    def __init__(self):
        self.status_code = 400
        self.message = '"thinking.type.enabled" is not supported for this model.'


def test_falls_back_when_model_rejects_thinking(monkeypatch):
    # First stream call raises the thinking 400; the retry (no thinking) succeeds.
    fake_msgs = FakeMessages([_FakeThinkingError(), _one_step()])
    monkeypatch.setattr(agent_mod, "_client", SimpleNamespace(messages=fake_msgs))

    a = agent_mod.Agent(model="sonnet", thinking_enabled=True)
    events = list(a.stream_turn("hi"))
    types = [e["type"] for e in events]

    assert "notice" in types  # user is told thinking was dropped
    assert types[-1] == "turn_done"  # turn still completes
    assert a.thinking_enabled is False  # thinking disabled after the rejection
    # the retry request carried no thinking param
    assert "thinking" not in fake_msgs.calls[1]
    assert len(fake_msgs.calls) == 2


def test_no_thinking_when_budget_zero(monkeypatch):
    block = SimpleNamespace(type="text", text="hi")
    step = FakeStream(events=[], final=SimpleNamespace(content=[block],
                                                       stop_reason="end_turn", usage=usage()))
    fake_msgs = FakeMessages([step])
    monkeypatch.setattr(agent_mod, "_client", SimpleNamespace(messages=fake_msgs))

    a = agent_mod.Agent(model="haiku", thinking_enabled=False)
    list(a.stream_turn("hi"))
    assert "thinking" not in fake_msgs.calls[0]
    assert "extra_body" not in fake_msgs.calls[0]


def test_is_thinking_error_is_specific():
    class E(agent_mod.anthropic.APIStatusError):
        def __init__(self, m, code=400):
            self.status_code = code
            self.message = m

    real = [
        '"thinking.type.enabled" is not supported for this model. Use "thinking.type.adaptive"',
        "adaptive thinking is not supported on this model",
        "This model does not support the effort parameter.",
        "output_config.effort: Input should be 'low', 'medium', 'high'",
    ]
    for m in real:
        assert agent_mod._is_thinking_error(E(m)) is True, m
    # unrelated 400s must NOT be treated as a thinking error (else thinking is
    # silently stripped on a genuine bad request)
    for m in ["messages: field required", "max_tokens must be greater than 0",
              "image exceeds 5 MB"]:
        assert agent_mod._is_thinking_error(E(m)) is False, m
    # non-400 never matches
    assert agent_mod._is_thinking_error(E("thinking", code=500)) is False


def test_agent_workspace_is_per_session():
    from backend import config
    # Same mode, DIFFERENT sessions -> different dirs (no concurrent file clobbering).
    a1 = agent_mod.Agent(mode="hld", session_id="aaaa-1111:hld")
    a2 = agent_mod.Agent(mode="hld", session_id="bbbb-2222:hld")
    assert a1._workspace() != a2._workspace()
    assert "aaaa-1111" in a1._workspace().name and "bbbb-2222" in a2._workspace().name
    # Both stay inside the workspace root.
    assert config.WORKSPACE_DIR in a1._workspace().parents
    # No session id -> falls back to a per-mode dir.
    assert agent_mod.Agent(mode="lld")._workspace().name == "lld"


def test_workspace_slug_cannot_escape():
    from backend import config
    for evil in ["..", "../../etc", "../../../tmp:hld", "/etc/passwd"]:
        p = config.workspace_for(evil)
        assert config.WORKSPACE_DIR == p.parent or config.WORKSPACE_DIR in p.parents
        assert p != config.WORKSPACE_DIR.parent
        assert ".." not in p.parts


def test_mark_last_for_cache_string_content():
    msgs = [{"role": "user", "content": "hello"}]
    out = agent_mod._mark_last_for_cache(msgs)
    assert out[0]["content"][0]["cache_control"] == {"type": "ephemeral"}
    # original is untouched (immutability)
    assert msgs[0]["content"] == "hello"


def test_mark_last_for_cache_list_content():
    msgs = [{"role": "user", "content": [{"type": "tool_result", "tool_use_id": "x", "content": "y"}]}]
    out = agent_mod._mark_last_for_cache(msgs)
    assert out[0]["content"][-1]["cache_control"] == {"type": "ephemeral"}
