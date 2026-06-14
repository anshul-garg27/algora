# LEARN: BFS on Grids — plain, multi-source, and binary-search-on-answer

*Why this matters: grid questions with Uber skins (drivers, riders, police,
fire) ran in a third of all DSA rounds. And one candidate passed every test
with DFS and STILL got negative feedback — algorithm choice is graded.*

## The one rule that got a candidate rejected

**Shortest path in an unweighted grid/graph = BFS. Always.**
DFS finds *a* path, not the *shortest*; with DP it can be made to work on DAGs
but not on general grids with cycles. If the question says "minimum steps /
time / moves", say "BFS" in your first breath.

(Weighted edges → Dijkstra. Weights only 0 and 1 → 0-1 BFS with a deque.)

## Plain BFS — the template

```python
from collections import deque

def bfs(grid, start):
    n, m = len(grid), len(grid[0])
    dist = {start: 0}
    q = deque([start])
    while q:
        r, c = q.popleft()
        for nr, nc in ((r+1,c), (r-1,c), (r,c+1), (r,c-1)):
            if 0 <= nr < n and 0 <= nc < m and (nr,nc) not in dist \
                    and grid[nr][nc] != '#':
                dist[(nr, nc)] = dist[(r, c)] + 1
                q.append((nr, nc))
    return dist
```

Key invariant to say: "BFS visits cells in order of distance, so the first
time I reach a cell is via a shortest path."

## Multi-source BFS — Uber's favorite twist

Question shape: something **spreads** from MANY starting points at once
(fire, rotten oranges, virus, police patrols, "distance to nearest X").

Insight in plain words: don't run BFS from each source (O(S·N·M)) — put **all
sources in the queue at distance 0** and run ONE BFS. Every cell gets the
distance to its NEAREST source. O(N·M) total.

```python
q = deque((r, c) for each source)      # all at dist 0
dist[source] = 0 for all sources
# ... identical BFS loop
```

### Worked example (asked 2x): fire-escape

> Grid has Start, Exit, walls, Fire cells. Fire spreads 1 step/min; you move
> 1 step/min. Min time to reach exit, never standing in fire?

1. Multi-source BFS from all fire cells → `fire_time[cell]`.
2. BFS for the person; you may enter a cell at time `t` only if
   `t < fire_time[cell]`.
3. **Define the boundary out loud**: "I'll use strict less-than, including at
   the exit" — interviewers accept either convention but ONLY if you state one.

Follow-up they asked: "you may wait W minutes before starting — maximize W."
Answer shape: feasibility of W is **monotonic** (if W works, W-1 works) →
**binary search on W**, re-running the person-BFS with `t + W`. This combo
(multi-source BFS + binary search on answer) is an Uber signature — an intern
round and an SDE-2 round both used it.

## Binary search on the answer — when and why

Use when: "maximize/minimize X such that <some feasibility>" AND feasibility
is monotonic in X. Template sentence to say: "Instead of computing the answer
directly, I can CHECK a candidate answer in O(...), and feasibility is
monotonic, so I binary search."

Where Uber used it: max waiting time (above), k-th by magnitude
(`../solutions/arrays_windows.py`), and "check if N obstacles fit before
point Y" in an OA.

## The other grid family: directional sweeps (no BFS at all)

The "Robots & blockers" Uber original (asked 4x) looks like BFS but isn't:
you need, for EVERY cell, the distance to the nearest blocker **in each of
the 4 directions separately**. That's 4 linear sweeps with a "last blocker
seen" variable. O(N·M). See `../solutions/grids_bfs.py` → `find_robots`.

How to tell sweeps from BFS: BFS = nearest anything by *path*; sweeps =
nearest something along a *straight line*.

## Mistakes that cost offers

- DFS for shortest path (see top).
- Marking visited when POPPING instead of when PUSHING → duplicates blow up
  the queue. Mark on push.
- Forgetting boundary cells count as blockers/walls when the problem says so
  (the robots question's #1 bug).
- Not defining tie/boundary conventions (fire arriving exactly when you do).

## Practice ladder

1. LC 994 Rotting Oranges (multi-source warm-up — asked in an Uber OA!)
2. LC 542 01 Matrix
3. LC 1730 Shortest Path to Get Food
4. LC 2258 Escape the Spreading Fire (the full Uber fire question)
5. LC 1102 / 778 (binary search on answer over grids)
6. Mock: `../mocks/dsa_02_robots_grid.py` (sweeps, not BFS — spot it yourself)
