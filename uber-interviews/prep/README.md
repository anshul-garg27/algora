# Uber SDE-2 Prep Kit (Python) — Self-Contained

Everything here is generated from analysis of 44 real Uber loops (Jun 2025–Jun 2026,
12 offers / 32 rejections) + ~700 LeetCode Discuss posts. It works **standalone or
with any AI model** — nothing depends on a specific chat session.

## Folder map

| Folder | What | How to use |
|---|---|---|
| `learn/` | **10 teaching docs** — each pattern from zero: intuition → template → worked Uber example → mistakes that cost offers → practice ladder | START HERE when something "samajh nahi aata". Read the doc, then do its mock/drill. |
| `deepdives/` | **14 question-level deep dives with Mermaid diagrams** — one per mock: full reasoning path, worked traces, and EVERY follow-up answered in detail | Mock first, then read — pass or fail. The "agar nahi aaya toh yahan se seekh lo" layer. |
| `mocks/` | **15 mock-interview kits** (5 LLD, 5 DSA, 4 HLD, 1 HM) + retake problems in every kit | Paste the `*_INTERVIEWER.md` into ANY model → it becomes a calibrated Uber interviewer with the real follow-ups and grading rubric. Code in the matching `.py`. See `mocks/README.md`. |
| `solutions/` | Editorial Python solutions for every Tier-1/Tier-2 repeated question, **with the exact follow-up variants Uber asked** (all runnable + tested) | Attempt first, then read. `python3 <file>` runs its tests. |
| `lld/` | Reference implementations of the 5 recurring machine-coding problems, thread-safe, with follow-up answers at the bottom of each file | Do the timed mock first, then diff your code against these. |
| `hld/` | End-to-end playbooks for the 5 HLD archetypes, in the exact format Uber grades (incl. "sentences that score") | Read one per day in week 3; rehearse out loud; then run the matching mock. |
| `behavioral/` | STAR Work Document template built from the real HM question data | Fill it completely in writing — an offer-getter credited exactly this for selection. |
| `cribsheets/` | **One page per round** (OA, DSA, LLD, HLD, HM) — protocol, minute marks, the rules from real debriefs | The ONLY thing to read on interview day. |
| `PHRASE_BANK.md` | Exact English sentences for every interview moment — clarifying, narrating, complexity, stuck, follow-ups, STAR | Rehearse out loud until automatic; fluency under pressure is its own skill. |
| `PLAN.md` | 4-week schedule + 15-mock log | Tick boxes; log verdicts after each mock. |

**Question bank (`../index.html`) now has progress tracking:** every card has
✓ Done / ★ Revisit buttons (saved in your browser), a Done counter in the
header, and a Progress filter (Done / Revisit / Untouched) inside Filters —
use it to systematically clear all 859 questions.

## Which doc when (quick router)

| "Mujhe ___ samajh nahi aata" | Read |
|---|---|
| Union-Find / connectivity | `learn/01` |
| BFS, grids, multi-source, binary search on answer | `learn/02` |
| Alien dictionary / ordering from constraints | `learn/03` |
| Heaps, top-K, streams | `learn/04` |
| Sliding window, next-greater | `learn/05` |
| DP (interval / game / grid) | `learn/06` |
| Palindrome questions | `learn/07` |
| How to even DO the LLD round | `learn/08` |
| Locks, threads, GIL, Condition | `learn/09` |
| How to even DO the HLD round | `learn/10` |

## The 5 facts to never forget (from the rejection data)

1. **LLD is the #1 rejection round.** Runnable code in 45 min beats perfect design.
2. **Ask clarifying questions out loud** — a senior was rejected specifically for not doing this.
3. **Shortest path ⇒ BFS/Dijkstra, never DFS** — a candidate passed all tests with DFS and still got negative feedback.
4. **You need ≥1 Strong Hire** in the loop. All "soft yes" = reject (real case).
5. The most-asked question at Uber is not a coding question: **"Walk me through the architecture of your past project"** (6× last year).
