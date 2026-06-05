"""Live end-to-end: run the FULL problem statements (the trigger) several times and
confirm the answer ALWAYS has Sections 1-5 before any tool, all 9 sections present,
and report whether the opener-gate had to fire to enforce it."""

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

from backend.agent import Agent

SECT = re.compile(r"^## (\d+)\.", re.MULTILINE)

PALINDROME = """4863. Find the Closest Palindrome of an Integer
Given an integer n represented as a string, find the closest palindrome (in terms of absolute
difference) to n. If there are two palindromes with the same absolute difference, return the smaller.
Input Format: a string n. Output Format: a string.
Example 1: n = "123" -> "121". Example 2: n = "1" -> "0".
Constraints: 1 <= n.length <= 18, digits only, no leading zeros."""

DSU = """Graph Operations for Connected Components.
Design a system on an undirected graph with n vertices supporting: add_edge(u,v), remove_edge(u,v),
count_components() returns the current number of connected components.
1 <= n <= 1e5, 1 <= operations <= 1e5.
Example: add_edge(3,4); count_components()->3; remove_edge(1,2); count_components()->2;
add_edge(2,3); count_components()->1."""


def run(label, prompt):
    a = Agent(mode="interview")
    text, pre = [], []
    saw_tool = False
    t0 = time.monotonic()
    ttf = None
    for ev in a.stream_turn(prompt):
        et = ev.get("type")
        if et == "text_delta":
            if ttf is None:
                ttf = round(time.monotonic() - t0, 1)
            text.append(ev["text"])
            if not saw_tool:
                pre.append(ev["text"])
        elif et == "tool_call":
            saw_tool = True
        elif et == "turn_done":
            break
        if time.monotonic() - t0 > 280:
            break
    full = "".join(text)
    pre_t = "".join(pre)
    # did the gate fire? look for our BLOCKED tool_result in the message history
    gate_fired = sum(
        1 for m in a.messages if m.get("role") == "user" and isinstance(m.get("content"), list)
        for blk in m["content"]
        if isinstance(blk, dict) and blk.get("is_error") and "BLOCKED: do not run code yet" in str(blk.get("content", ""))
    )
    full_secs = sorted(set(int(x) for x in SECT.findall(full)))
    pre_secs = sorted(set(int(x) for x in SECT.findall(pre_t)))
    ok = all(s in pre_secs for s in (1, 2, 3, 4, 5))
    return {
        "label": label, "ttf_s": ttf,
        "opener_1to5_before_tools": ok,
        "pre_tool_sections": pre_secs,
        "full_sections": full_secs,
        "gate_fired_times": gate_fired,
        "answer_chars": len(full),
    }


def main():
    plan = [("palindrome#1", PALINDROME), ("palindrome#2", PALINDROME), ("palindrome#3", PALINDROME),
            ("dsu#1", DSU), ("dsu#2", DSU)]
    rows = []
    for label, prompt in plan:
        print(f"[gate-verify] {label} ...", flush=True)
        try:
            r = run(label, prompt)
        except Exception as e:  # noqa: BLE001
            r = {"label": label, "error": str(e)[:200]}
        rows.append(r)
        print("  ->", json.dumps(r), flush=True)
    bad = [r for r in rows if not r.get("opener_1to5_before_tools")]
    print(f"\nRESULT: {len(rows) - len(bad)}/{len(rows)} runs had Sections 1-5 before tools. "
          f"gate fired in {sum(r.get('gate_fired_times', 0) for r in rows)} place(s).")
    print("FAILURES:" if bad else "ALL CLEAN — opener never skipped.")
    for b in bad:
        print(" ", b)


if __name__ == "__main__":
    main()
