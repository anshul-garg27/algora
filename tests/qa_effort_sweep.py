"""Effort sweep: run the trickiest trap problems at multiple effort levels and measure
the wait (time-to-first-text + when the opener finishes) plus save transcripts/code so the
judges can compare correctness across efforts. Answers: 'does cranking effort up help?'"""

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

OUT = ROOT / "tests" / "qa_runs"
OUT.mkdir(exist_ok=True)

TRAP = {
    "dsu_remove_components":
        'Design a system on an undirected graph with n vertices supporting add_edge(u,v), '
        'remove_edge(u,v), and count_components() (current number of connected components). '
        '1<=n<=1e5, up to 1e5 ops. Walk me through it for an interview.',
    "closest_palindrome":
        'Find the closest palindrome (by absolute difference) to an integer given as a string n; '
        'on a tie return the smaller. "123"->"121", "1"->"0". 1<=len(n)<=18, digits only. '
        'Walk me through it for an interview.',
    "predict_winner":
        'Predict the Winner: array nums, two players alternate taking from either end, P1 first, '
        'both optimal; return True if P1 wins or draws, AND print each player\'s pick sequence. '
        'Walk me through it for an interview.',
}
EFFORTS = ["low", "high", "xhigh"]


def extract_last_code(text):
    b = re.findall(r"```(?:python|py)?\n(.*?)```", text, re.DOTALL)
    return b[-1] if b else ""


def run(key, prompt, effort):
    cfg.MODES["interview"]["effort"] = effort
    a = Agent(mode="interview")
    chunks = []
    t0 = time.monotonic()
    ttf = first_tool = None
    saw_tool = False
    for ev in a.stream_turn(prompt):
        et = ev.get("type")
        if et == "text_delta":
            if ttf is None:
                ttf = round(time.monotonic() - t0, 1)
            chunks.append(ev["text"])
        elif et == "tool_call":
            if first_tool is None:
                first_tool = round(time.monotonic() - t0, 1)
            saw_tool = True
        elif et == "turn_done":
            break
        if time.monotonic() - t0 > 280:
            break
    full = "".join(chunks)
    (OUT / f"{key}__{effort}.md").write_text(full, encoding="utf-8")
    (OUT / f"{key}__{effort}.py").write_text(extract_last_code(full), encoding="utf-8")
    return {
        "key": key, "effort": effort,
        "ttf_s": ttf, "opener_done_s": first_tool,
        "elapsed_s": round(time.monotonic() - t0, 1),
        "chars": len(full),
        "opener_before_tools": (ttf is not None) and (first_tool is None or ttf < first_tool),
    }


def main():
    rows = []
    for key, prompt in TRAP.items():
        for eff in EFFORTS:
            print(f"[sweep] {key} @ {eff} ...", flush=True)
            try:
                r = run(key, prompt, eff)
            except Exception as e:  # noqa: BLE001
                r = {"key": key, "effort": eff, "error": str(e)[:200]}
            rows.append(r)
            print("  ->", json.dumps(r), flush=True)
    (OUT / "_effort_sweep.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print("DONE effort sweep")


if __name__ == "__main__":
    main()
