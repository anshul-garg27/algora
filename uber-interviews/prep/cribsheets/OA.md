# CRIB SHEET — Online Assessment (read morning-of, nothing else)

**Format:** CodeSignal/HackerRank · 65-90 min · 2-4 problems · camera ON,
strict proctoring (no second monitor, no phone in view, stay in frame).
Bar: ~3 of 4 solved. Scores like 556/600 passed.

## Strategy (from people who passed)
1. **First 3 min:** open ALL problems, read, rank by ease. The
   penultimate/last one is usually the time sink — schedule it LAST.
2. **Bank the easy ones fast** — implementation speed wins OAs, not insight.
3. Hard one: get the brute force submitted for partial score FIRST, then
   optimize in remaining time.
4. 10 min left + stuck = clean up partials, make sure everything compiles.

## Patterns that actually appeared in Uber OAs (recent)
- DSU: connect hubs MST `min(|dx|,|dy|)` (sort by x and y, adjacent edges
  only), GCD zone clusters (SPF sieve + union by prime)
- K-th next greater indices (monotonic/BIT — partial-score the brute force)
- Spiral matrix with index condition · implementation-heavy string rules
  (valid strings, command frequency, vowel-consonant sorting)
- Rotting oranges / multi-source BFS · min ops to make array continuous
- Obstacle build/check queries on a number line (sorted list + bisect)

## Python speed kit (have these at your fingertips)
`from collections import deque, defaultdict, Counter` ·
`import heapq, bisect, math` · `sys.stdin` fast read if HackerRank ·
DSU template from memory (2 min) · BFS template (90 sec).

## Don'ts
- Don't perfect problem 1 while problem 4 sits unread.
- Don't debug by staring — print/trace immediately.
- Don't leave any problem with 0 — partial brute force > blank.
