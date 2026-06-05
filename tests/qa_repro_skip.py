"""Root-cause repro: run the same problems multiple times and measure how often the
model SKIPS sections 2-5 (jumps §1 -> §6) and whether it fires a tool before §5 is
written as text. Distinguishes 'sections in thinking' vs 'sections skipped entirely'."""

import json
import os
import pathlib
import re
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
env = ROOT / ".env"
if env.exists():
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

import backend.config as cfg
from backend.agent import Agent

PROBS = {
    "palindrome": 'Find the closest palindrome (by absolute difference, not equal to n) to an integer '
                  'given as a string n; tie -> smaller. "123"->"121", "1"->"0". len up to 18. '
                  'Walk me through it for an interview.',
}
SECT = re.compile(r"^## (\d+)\.", re.MULTILINE)


def one_run(prompt, effort):
    cfg.MODES["interview"]["effort"] = effort
    a = Agent(mode="interview")
    text, think = [], []
    pre_tool_text = []
    events = []
    saw_tool = False
    t0 = time.monotonic()
    for ev in a.stream_turn(prompt):
        et = ev.get("type")
        if et == "thinking_delta":
            think.append(ev["text"]); events.append("K")
        elif et == "text_delta":
            text.append(ev["text"]); events.append("T")
            if not saw_tool:
                pre_tool_text.append(ev["text"])
        elif et == "tool_call":
            saw_tool = True; events.append("X:" + (ev.get("name") or ""))
        elif et == "turn_done":
            break
        if time.monotonic() - t0 > 260:
            break
    full = "".join(text)
    pre = "".join(pre_tool_text)
    thinking = "".join(think)
    full_secs = sorted(set(int(x) for x in SECT.findall(full)))
    pre_secs = sorted(set(int(x) for x in SECT.findall(pre)))
    # did any tool fire before section 5 was written as TEXT?
    first_tool_idx = next((i for i, e in enumerate(events) if e.startswith("X")), None)
    # find index in events where §5 text appears: approximate by checking pre_secs
    skipped = [s for s in (2, 3, 4, 5) if s not in full_secs]
    return {
        "effort": effort,
        "full_sections": full_secs,
        "pre_tool_sections": pre_secs,
        "skipped_2to5_in_answer": skipped,
        "tool_before_all_opener": pre_secs != [1, 2, 3, 4, 5] and first_tool_idx is not None,
        "first_tool_event_idx": first_tool_idx,
        "answer_chars": len(full), "thinking_chars": len(thinking),
        # do the skipped sections' keywords appear in THINKING instead?
        "approach_in_thinking": ("brute force" in thinking.lower() or "optimal" in thinking.lower()),
    }


def main():
    runs = []
    plan = [("palindrome", "medium"), ("palindrome", "medium"), ("palindrome", "medium"),
            ("palindrome", "low"), ("palindrome", "low")]
    for key, eff in plan:
        print(f"[repro] {key} @ {eff} ...", flush=True)
        try:
            r = one_run(PROBS[key], eff)
            r["key"] = key
        except Exception as e:  # noqa: BLE001
            r = {"key": key, "effort": eff, "error": str(e)[:200]}
        runs.append(r)
        print("  ->", json.dumps(r), flush=True)
    (ROOT / "tests" / "qa_runs" / "_repro_skip.json").write_text(json.dumps(runs, indent=2))
    skips = sum(1 for r in runs if r.get("skipped_2to5_in_answer"))
    print(f"\nSUMMARY: {skips}/{len(runs)} runs SKIPPED some of sections 2-5 in the answer")


if __name__ == "__main__":
    main()
