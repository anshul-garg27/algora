"""Live functional test of the LLD + HLD modes through /api/chat.

Uses a fast model + thinking off to exercise the full pipeline (prompt ->
tools -> diagrams -> structured sections) quickly. Server up on :8000.
"""

import json
import sys
import urllib.request

BASE = "http://localhost:8000"


def run(mode, model, message, thinking_off=True):
    body = {"session_id": f"ld-{mode}", "mode": mode, "model": model, "message": message}
    if thinking_off:
        body["thinking"] = 0
    req = urllib.request.Request(
        BASE + "/api/chat", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    text, tools, ws, errors, done = [], [], 0, [], False
    with urllib.request.urlopen(req, timeout=600) as r:
        buf = ""
        for raw in r:
            buf += raw.decode("utf-8", "replace")
            while "\n\n" in buf:
                chunk, buf = buf.split("\n\n", 1)
                if not chunk.startswith("data: "):
                    continue
                try:
                    ev = json.loads(chunk[6:])
                except json.JSONDecodeError:
                    continue
                t = ev["type"]
                if t == "text_delta":
                    text.append(ev["text"])
                elif t == "tool_call":
                    tools.append(ev["name"])
                elif t == "web_search":
                    ws += 1
                elif t == "turn_done":
                    done = True
                elif t == "error":
                    errors.append(ev["message"][:120])
    return "".join(text), tools, ws, errors, done


def check(label, cond):
    print(f"  {'✓' if cond else '✗'} {label}")
    return cond


def main():
    ok = True

    print("LLD — design a parking lot (sonnet, thinking off):")
    ans, tools, ws, errs, done = run(
        "lld", "sonnet",
        "Low level design for a Parking Lot. Show a class diagram and a sequence diagram, "
        "narrate the classes, and write + run a small Python demo.")
    ok &= check("completed, no errors", done and not errs)
    ok &= check("ran code (write_file + run_python)", "write_file" in tools and "run_python" in tools)
    ok &= check("classDiagram present", "classDiagram" in ans)
    ok &= check("a sequence or flow diagram present", "sequenceDiagram" in ans or "```mermaid" in ans)
    ok &= check("has requirements + class sections", "Requirements" in ans and "Class" in ans)
    ok &= check("has talking points (💬)", "💬" in ans)
    if errs:
        print("    errors:", errs)

    print("HLD — design a URL shortener (sonnet, thinking off):")
    ans, tools, ws, errs, done = run(
        "hld", "sonnet",
        "System design (HLD) for a URL shortener. Include a high-level architecture mermaid "
        "diagram, capacity estimation, API, data model, scaling and trade-offs.")
    ok &= check("completed, no errors", done and not errs)
    ok &= check("architecture mermaid diagram present", "```mermaid" in ans)
    ok &= check("requirements + scaling sections", "Requirements" in ans and ("Scal" in ans or "Trade" in ans))
    ok &= check("capacity estimation present", "Capacity" in ans or "Estimation" in ans or "QPS" in ans)
    ok &= check("has talking points (💬)", "💬" in ans)
    if errs:
        print("    errors:", errs)

    print("\n" + ("✅ DESIGN MODES OK" if ok else "❌ DESIGN MODE CHECK FAILED"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
