"""Live full HLD render of the URL-shortener (the user's reference problem) under the
rewritten prompt. Streams to completion, saves the Markdown, and reports whether the new
always-on features actually appeared: structure pitch, say-it scripts, jargon glosses,
checkpoints, traps/gaps, colored diagrams, and DETAILED (not one-liner) §11 answers."""

import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

# load .env so the API key is present
env = ROOT / ".env"
if env.exists():
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from backend.agent import Agent

a = Agent(mode="hld")
chunks, tools = [], []
first_text_t = None
first_tool_t = None
t0 = time.monotonic()
saw_text = False
for ev in a.stream_turn("Design a URL shortener like bit.ly."):
    et = ev.get("type")
    if et == "text_delta":
        if not saw_text:
            first_text_t = time.monotonic() - t0
            saw_text = True
        chunks.append(ev["text"])
    elif et == "tool_call":
        if first_tool_t is None:
            first_tool_t = time.monotonic() - t0
        tools.append(ev.get("name"))
    elif et == "turn_done":
        break
    if time.monotonic() - t0 > 540:  # safety cap
        print("!! hit time cap")
        break

txt = "".join(chunks)
out = ROOT / "screenshots" / "url_shortener_full.md"
out.write_text(txt, encoding="utf-8")

# ---- analysis ----
def count(s):
    return txt.count(s)

# §11 answer detail: split on "Q" lines isn't reliable; measure paragraphs after "## 11"
s11 = txt.split("## 11", 1)[-1] if "## 11" in txt else ""
# crude: lines under §11 that look like answers (sentences), average words
ans_lines = [l for l in s11.splitlines() if len(l.split()) > 12]
avg_words = round(sum(len(l.split()) for l in ans_lines) / len(ans_lines), 1) if ans_lines else 0

mermaid_blocks = txt.count("```mermaid")
colored = "classDef hot" in txt or "classDef cold" in txt or ":::hot" in txt

stats = {
    "elapsed_s": round(time.monotonic() - t0, 1),
    "first_text_s": round(first_text_t, 2) if first_text_t else None,
    "first_tool_s": round(first_tool_t, 2) if first_tool_t else None,
    "opener_before_tools": (first_text_t is not None) and (first_tool_t is None or first_text_t < first_tool_t),
    "tools_used": tools,
    "total_chars": len(txt),
    "structure_pitch (🎬/plan)": ("structure" in txt.lower() and "🎙️" in txt) or "Here's how I'll structure" in txt,
    "say_it_scripts (🎙️)": count("🎙️"),
    "jargon_defense (🧠)": count("🧠"),
    "checkpoints (🤝)": count("🤝"),
    "traps_or_gaps (⚠️)": count("⚠️"),
    "talk_lines (💬)": count("💬"),
    "mermaid_blocks": mermaid_blocks,
    "colored_diagram": colored,
    "has_§11": "## 11" in txt,
    "§11_answer_lines": len(ans_lines),
    "§11_avg_words_per_answer_line": avg_words,
    "sections_present": [h for h in ["## 1","## 2","## 3","## 4","## 5","## 6","## 7","## 8","## 9","## 10","## 11"] if h in txt],
    "no_latex": ("\\frac" not in txt) and ("$$" not in txt),
}
print("Saved:", out)
for k, v in stats.items():
    print(f"  {k}: {v}")
