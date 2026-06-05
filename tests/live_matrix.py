"""Live matrix test against a running server: every model x thinking on/off.

Asserts no error events, that tools actually executed, and the turn completed.
Run with the server up on :8000.
"""

import json
import sys
import urllib.request

BASE = "http://localhost:8000"
PROBLEM = (
    "Find the length of the Longest Increasing Subsequence in O(n log n). "
    "Test with [10,9,2,5,3,7,101,18] (expect 4). "
    "Write the code, run it to verify on that case plus a few edge cases, then answer."
)


def stream(session, model, thinking):
    body = json.dumps({
        "session_id": session, "model": model, "message": PROBLEM,
        **({"thinking": 0} if thinking is False else {}),
    }).encode()
    req = urllib.request.Request(BASE + "/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    events = []
    with urllib.request.urlopen(req, timeout=300) as resp:
        buf = ""
        for raw in resp:
            buf += raw.decode("utf-8", "replace")
            while "\n\n" in buf:
                chunk, buf = buf.split("\n\n", 1)
                if chunk.startswith("data: "):
                    try:
                        events.append(json.loads(chunk[6:]))
                    except json.JSONDecodeError:
                        pass
    return events


def summarize(events):
    types = [e["type"] for e in events]
    tool_calls = [e for e in events if e["type"] == "tool_call"]
    tool_errs = [e for e in events if e["type"] == "tool_result" and e.get("is_error")]
    errors = [e for e in events if e["type"] == "error"]
    notices = [e for e in events if e["type"] == "notice"]
    thought = "thinking_delta" in types
    done = "turn_done" in types
    return {
        "tools": len(tool_calls),
        "tool_errors": len(tool_errs),
        "api_errors": [e["message"][:80] for e in errors],
        "notices": [e["message"][:60] for e in notices],
        "thought": thought,
        "completed": done,
    }


def main():
    cases = [
        ("opus", True), ("opus", False),
        ("sonnet", True),
        ("haiku", True),
    ]
    failed = False
    for i, (model, thinking) in enumerate(cases):
        label = f"{model} thinking={'on' if thinking else 'off'}"
        try:
            ev = stream(f"live-{i}", model, thinking)
            s = summarize(ev)
            ok = s["completed"] and not s["api_errors"]
            flag = "✅" if ok else "❌"
            print(f"{flag} {label:22} tools={s['tools']} thought={s['thought']} "
                  f"completed={s['completed']} api_errors={s['api_errors']} notices={s['notices']}")
            if not ok:
                failed = True
        except Exception as e:
            print(f"❌ {label:22} EXCEPTION {type(e).__name__}: {e}")
            failed = True
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
