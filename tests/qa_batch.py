"""Deep-QA batch: solve the Round-2 problem battery through the real Algora engine,
saving each transcript + extracted final code for adversarial judging. Records whether the
opener streamed before tools and which sections appeared. Correctness is judged separately."""

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

OUT = ROOT / "tests" / "qa_runs"
OUT.mkdir(exist_ok=True)

# (key, mode, prompt). DSA -> interview; the scheduler -> lld; stock alert -> hld.
PROBLEMS = [
    ("closest_palindrome", "interview",
     'Find the closest palindrome (by absolute difference) to an integer given as a string n. '
     'If two palindromes tie, return the smaller. Examples: "123"->"121", "1"->"0". '
     '1<=len(n)<=18, digits only, no leading zeros. Walk me through it for an interview.'),
    ("dsu_remove_components", "interview",
     'Design a system on an undirected graph with n vertices supporting: add_edge(u,v), '
     'remove_edge(u,v), and count_components() returning current number of connected components. '
     '1<=n<=1e5, up to 1e5 operations. Walk me through it for an interview.'),
    ("predict_winner", "interview",
     'Optimal Game Strategy / Predict the Winner: array nums, two players alternate taking from '
     'either end, Player 1 first, both optimal. Return True if Player 1 wins or draws (draw counts '
     'as a win for P1). ALSO print the sequence of picks by each player. nums up to 1000, values up '
     'to 1e5. Walk me through it for an interview.'),
    ("burn_tree", "interview",
     'Minimum time to burn an undirected tree of N nodes from an optimally chosen start node; fire '
     'spreads to neighbors in 1 unit/time. Equivalent to the tree radius. Return the min time. '
     'N up to 1e5. edges given. Walk me through it for an interview.'),
    ("closest_driver", "interview",
     'Find the closest driver in an N x M city grid (0 open, 1 blocked) by min steps (4-dir) from a '
     'rider position to any of several driver positions. Return the closest driver coords, or null if '
     'none reachable. N,M up to 1000. Walk me through it for an interview.'),
    ("course_schedule_ii", "interview",
     'Course Schedule II: numCourses and prerequisites pairs [a,b] meaning b before a. Return a valid '
     'ordering of all courses, or empty list if impossible (cycle). Walk me through it for an interview.'),
    ("merge_cars_k", "interview",
     'Merge Consecutive Cars of Size K: given a list of car names, repeatedly replace any K consecutive '
     'identical names with one, until none remain. Return the final list. Example: '
     '[Honda,Honda,Maruti,Maruti,Maruti,BMW,Maruti,Maruti,Maruti], K=2 -> [Honda,Maruti,BMW,Maruti]. '
     'N up to 1e5. Walk me through it for an interview.'),
    ("min_appends_subsequence", "interview",
     'Minimum Appends for Subsequence: strings s and t (lowercase). Min number of times s must be '
     'concatenated to itself so that t is a subsequence of the result. "boy","oyb"->2; "abc","abcbc"->2. '
     'lengths up to 1000. Walk me through it for an interview.'),
    ("trapped_colors", "interview",
     'Determine Trapped Colors in a Matrix: n x m grid of B/W. is_trapped(matrix,i,j,k): a cell is '
     'trapped if all cells within a k-distance square around it are the opposite color (k=1 = immediate '
     '8 neighbors). Return bool. n,m up to 1000. Walk me through it for an interview.'),
    ("array_equal_general_x", "interview",
     'Array Transformation to Equal Elements: array arr and integer x (x>=1). You may add or subtract x '
     'from any element any number of times. Can all elements be made equal? Return bool. Handle x=0. '
     'len up to 1e5. Walk me through it for an interview.'),
    ("task_scheduler_lld", "lld",
     'Design an in-memory task scheduler library: schedule(task, time) runs a task at a specific time; '
     'scheduleAtFixedInterval(task, interval) runs immediately then every interval seconds after the '
     'previous completes; configurable worker-thread count; thread-safe; no external scheduling libs. '
     'Give the full machine-coding LLD.'),
    ("stock_alert_hld", "hld",
     'Design a stock price alerting system (HLD): users define alerts (price above/below, percent change '
     'in a window) per ticker with notify via push/email/SMS or webhook; ingest real-time ticks for '
     'thousands of symbols sub-second; evaluate alerts per tick without scanning all; HA, no SPOF; '
     'optional historical query. Component diagram, data flow, scaling.'),
]


def extract_last_code(text: str) -> str:
    blocks = re.findall(r"```(?:python|py)?\n(.*?)```", text, re.DOTALL)
    return blocks[-1] if blocks else ""


def run_one(key: str, mode: str, prompt: str) -> dict:
    a = Agent(mode=mode)
    chunks, pre_tool, tools = [], [], []
    saw_tool = False
    t0 = time.monotonic()
    ttf = first_tool = None
    for ev in a.stream_turn(prompt):
        et = ev.get("type")
        if et == "text_delta":
            if ttf is None:
                ttf = round(time.monotonic() - t0, 1)
            chunks.append(ev["text"])
            if not saw_tool:
                pre_tool.append(ev["text"])
        elif et == "tool_call":
            if first_tool is None:
                first_tool = round(time.monotonic() - t0, 1)
            saw_tool = True
            tools.append(ev.get("name"))
        elif et == "turn_done":
            break
        if time.monotonic() - t0 > 280:
            break
    full = "".join(chunks)
    pre = "".join(pre_tool)
    (OUT / f"{key}.md").write_text(full, encoding="utf-8")
    code = extract_last_code(full)
    (OUT / f"{key}.py").write_text(code, encoding="utf-8")
    secs = re.findall(r"^## (\d+)\.", full, re.MULTILINE)
    return {
        "key": key, "mode": mode,
        "ttf_s": ttf, "first_tool_s": first_tool,
        "chars": len(full), "pre_tool_chars": len(pre),
        "tools": tools,
        "opener_before_tools": (ttf is not None) and (first_tool is None or ttf < first_tool),
        "sections": secs,
        "code_chars": len(code),
        "elapsed_s": round(time.monotonic() - t0, 1),
    }


def main():
    results = []
    for key, mode, prompt in PROBLEMS:
        print(f"[run] {key} ({mode}) ...", flush=True)
        try:
            r = run_one(key, mode, prompt)
        except Exception as e:  # noqa: BLE001
            r = {"key": key, "mode": mode, "error": str(e)[:300]}
        results.append(r)
        print("  ->", json.dumps({k: v for k, v in r.items() if k != "sections"}), flush=True)
    (OUT / "_summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("DONE. summary at tests/qa_runs/_summary.json")


if __name__ == "__main__":
    main()
