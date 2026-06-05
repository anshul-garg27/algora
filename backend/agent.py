"""The agentic loop: drives Claude through analyse -> code -> run -> verify.

An ``Agent`` owns one conversation. ``stream_turn`` is a generator that yields
plain event dicts describing everything happening (thinking, text, tool calls,
tool results) so the web layer can forward them to the browser as SSE.
"""

from __future__ import annotations

import copy
from typing import Any, Iterator

import anthropic

from . import config
from .prompts import get_system_prompt
from .tools import TOOLS, execute_tool

# A single shared client; it reads ANTHROPIC_API_KEY from the environment.
_client = anthropic.Anthropic()


def _system_blocks(mode: str) -> list[dict]:
    """System prompt for a mode as a cacheable block (caches tools + system)."""
    return [
        {
            "type": "text",
            "text": get_system_prompt(mode),
            "cache_control": {"type": "ephemeral"},
        }
    ]


def _mark_last_for_cache(messages: list[dict]) -> list[dict]:
    """Return a copy of messages with a cache breakpoint on the final user block.

    This makes the agentic tool loop re-use the conversation prefix instead of
    re-billing it at full price on every step.
    """
    if not messages:
        return messages
    # Only the last message is mutated, so copy just that one (the rest, incl.
    # large SDK pydantic blocks, are shared by reference — O(1) not O(history)).
    msgs = messages[:-1] + [copy.deepcopy(messages[-1])]
    last = msgs[-1]
    if last.get("role") != "user":
        return msgs

    content = last.get("content")
    if isinstance(content, str):
        last["content"] = [
            {"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}
        ]
    elif isinstance(content, list) and content:
        block = content[-1]
        if isinstance(block, dict):
            block["cache_control"] = {"type": "ephemeral"}
    return msgs


class Agent:
    """Holds one conversation and runs streaming, tool-using turns."""

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
        self.messages: list[dict] = []

    @property
    def thinking_on(self) -> bool:
        return bool(self.thinking_enabled)

    def _mode_cfg(self) -> dict:
        return config.MODES[self.mode]

    # -- persistence -----------------------------------------------------------

    def export_messages(self) -> list:
        """JSON-safe copy of the conversation for saving/continuation.

        Assistant pydantic blocks are dumped to dicts; thinking/redacted_thinking
        blocks are dropped (they're only required intra-turn, which is complete),
        which keeps reload robust without juggling thinking signatures.
        """
        return [_serialize_message(m) for m in self.messages]

    def import_messages(self, messages: list) -> None:
        """Restore a previously exported conversation (dicts the SDK accepts)."""
        self.messages = list(messages or [])

    def _workspace(self):
        """Per-conversation workspace subdir so concurrent chats never share files."""
        return config.workspace_for(self.session_id, self.mode)

    # -- request construction --------------------------------------------------

    def _tools(self) -> list:
        tools = list(TOOLS)
        if config.ENABLE_WEB_SEARCH:
            # Server-side tool: Anthropic runs the search and returns results
            # inline; our loop never executes it.
            tools.append(
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": config.WEB_SEARCH_MAX_USES,
                }
            )
        return tools

    def _create_kwargs(self) -> dict:
        cfg = self._mode_cfg()
        extra_body: dict[str, Any] = {}
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": cfg["max_tokens"],
            "system": _system_blocks(self.mode),
            "tools": self._tools(),
            "messages": _mark_last_for_cache(self.messages),
        }
        if self.thinking_on:
            if config.uses_adaptive_thinking(self.model):
                # Newer models (Opus 4.8): adaptive thinking + effort. Opus defaults
                # to display="omitted" (hidden thinking, no thinking_delta stream);
                # "summarized" surfaces the reasoning so the UI can show it. Sent via
                # extra_body so it works regardless of SDK typing for these fields.
                extra_body["thinking"] = {"type": "adaptive", "display": "summarized"}
                extra_body["output_config"] = {"effort": cfg["effort"]}
            else:
                # Budget-style thinking (Sonnet 4.6, Haiku 4.5).
                kwargs["thinking"] = {"type": "enabled", "budget_tokens": cfg["thinking_budget"]}
        if extra_body:
            kwargs["extra_body"] = extra_body
        # 1M context for Opus, so long multi-turn design sessions fit.
        if config.ENABLE_1M_CONTEXT and config.uses_adaptive_thinking(self.model):
            kwargs["extra_headers"] = {"anthropic-beta": config.CONTEXT_1M_BETA}
        return kwargs

    # -- main loop -------------------------------------------------------------

    def stream_turn(self, user_content: list[dict] | str) -> Iterator[dict]:
        """Run one user turn to completion, yielding event dicts.

        Loops over assistant responses: whenever the model calls tools, the
        tools run, results are appended, and the model is invoked again — until
        it stops calling tools or the step ceiling is hit.
        """
        self.messages.append({"role": "user", "content": user_content})

        for step in range(config.MAX_AGENT_STEPS):
            final = None
            for attempt in range(2):
                try:
                    final = yield from self._stream_one_response(step)
                    break
                except anthropic.APIStatusError as exc:
                    # If the model rejects the thinking config, drop thinking and
                    # retry once rather than failing the whole turn.
                    if attempt == 0 and self.thinking_on and _is_thinking_error(exc):
                        self.thinking_enabled = False
                        yield {
                            "type": "notice",
                            "message": "This model rejected the extended-thinking "
                            "configuration; retrying without it.",
                        }
                        continue
                    yield {"type": "error", "message": f"API error {exc.status_code}: {_err(exc)}"}
                    return
                except anthropic.APIError as exc:
                    yield {"type": "error", "message": f"API error: {_err(exc)}"}
                    return
            if final is None:
                return

            # Persist the assistant turn verbatim (preserves thinking signatures
            # and tool_use blocks needed for the next request).
            self.messages.append({"role": "assistant", "content": final.content})

            # A long server-side tool turn (e.g. web_search) can pause: resend the
            # paused assistant turn as-is so the model continues — do NOT end here,
            # or the answer is truncated at the pause point.
            if final.stop_reason == "pause_turn":
                continue

            tool_uses = [b for b in final.content if getattr(b, "type", None) == "tool_use"]
            if final.stop_reason != "tool_use" or not tool_uses:
                yield {
                    "type": "turn_done",
                    "stop_reason": final.stop_reason,
                    "usage": _usage(final),
                }
                return

            tool_results = []
            for block in tool_uses:
                yield {
                    "type": "tool_call",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                }
                output, is_error = execute_tool(block.name, block.input, self._workspace())
                yield {
                    "type": "tool_result",
                    "id": block.id,
                    "name": block.name,
                    "output": output,
                    "is_error": is_error,
                }
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": output,
                        "is_error": is_error,
                    }
                )
            self.messages.append({"role": "user", "content": tool_results})

        yield {
            "type": "error",
            "message": f"Reached the maximum of {config.MAX_AGENT_STEPS} agent steps.",
        }

    def _stream_one_response(self, step: int):
        """Stream a single assistant message, yielding deltas; return final msg."""
        yield {"type": "step_start", "step": step}
        with _client.messages.stream(**self._create_kwargs()) as stream:
            for event in stream:
                etype = getattr(event, "type", None)
                if etype == "content_block_start":
                    cb = getattr(event, "content_block", None)
                    if getattr(cb, "type", None) == "server_tool_use" and (
                        getattr(cb, "name", None) == "web_search"
                    ):
                        # Anthropic runs this search server-side; surface it to the UI.
                        yield {"type": "web_search", "query": _ws_query(cb)}
                elif etype == "content_block_delta":
                    delta = event.delta
                    dtype = getattr(delta, "type", None)
                    if dtype == "thinking_delta":
                        yield {"type": "thinking_delta", "text": delta.thinking}
                    elif dtype == "text_delta":
                        yield {"type": "text_delta", "text": delta.text}
            return stream.get_final_message()


_DROP_BLOCK_TYPES = {"thinking", "redacted_thinking"}


def _serialize_block(block):
    """Turn an SDK content block (pydantic) or dict into a plain JSON-safe dict."""
    if hasattr(block, "model_dump"):
        return block.model_dump(exclude_none=True)
    return block


def _serialize_message(msg: dict) -> dict:
    content = msg.get("content")
    if isinstance(content, list):
        blocks = []
        for b in content:
            d = _serialize_block(b)
            if isinstance(d, dict) and d.get("type") in _DROP_BLOCK_TYPES:
                continue
            blocks.append(d)
        return {"role": msg["role"], "content": blocks}
    return {"role": msg["role"], "content": content}


def _ws_query(cb) -> str | None:
    inp = getattr(cb, "input", None)
    if isinstance(inp, dict):
        return inp.get("query")
    return None


def _usage(message) -> dict:
    u = getattr(message, "usage", None)
    if u is None:
        return {}
    return {
        "input_tokens": getattr(u, "input_tokens", None),
        "output_tokens": getattr(u, "output_tokens", None),
        "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", None),
        "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", None),
    }


def _err(exc: Exception) -> str:
    msg = getattr(exc, "message", None)
    return msg if msg else str(exc)


def _is_thinking_error(exc: Exception) -> bool:
    """True only for a 400 specifically about the thinking/effort config.

    Tight matching so we never swallow an unrelated 400 (e.g. a bad message)
    and silently strip thinking from the request.
    """
    if getattr(exc, "status_code", None) != 400:
        return False
    msg = (getattr(exc, "message", "") or str(exc)).lower()
    return (
        "thinking.type" in msg
        or "adaptive thinking" in msg
        or "output_config" in msg
        or "effort parameter" in msg
        or ("thinking" in msg and "support" in msg)
    )
