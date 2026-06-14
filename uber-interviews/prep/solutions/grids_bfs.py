"""Uber DSA solutions — Grid/BFS family (Uber loves grid skins).
Run: python3 grids_bfs.py
Problems: robots & blockers (Uber original), fire-escape (multi-source BFS),
thief→bank with police patrol radii, min path sum with diagonal.

REMEMBER: shortest path in unweighted grid = BFS. A real Uber candidate
passed all tests with DFS and still got negative feedback.
"""
from __future__ import annotations

from collections import deque
import heapq


# ---- 1. Robots in a Grid: blocker distance query (Uber original, 4x) --------
# Brute force: per robot scan 4 directions O(R*(M+N)). Optimal: 4 DP sweeps,
# O(M*N) total. Distance counts steps to the blocking cell/boundary.

def find_robots(location_map: list[list[str]], query: list[int]) -> list[tuple[int, int]]:
    n, m = len(location_map), len(location_map[0])
    req_left, req_top, req_bottom, req_right = query
    left = [[0] * m for _ in range(n)]
    right = [[0] * m for _ in range(n)]
    top = [[0] * m for _ in range(n)]
    bottom = [[0] * m for _ in range(n)]
    for r in range(n):
        last = -1                                # boundary as blocker at -1
        for c in range(m):
            if location_map[r][c] == "X":
                last = c
            else:
                left[r][c] = c - last
        last = m
        for c in range(m - 1, -1, -1):
            if location_map[r][c] == "X":
                last = c
            else:
                right[r][c] = last - c
    for c in range(m):
        last = -1
        for r in range(n):
            if location_map[r][c] == "X":
                last = r
            else:
                top[r][c] = r - last
        last = n
        for r in range(n - 1, -1, -1):
            if location_map[r][c] == "X":
                last = r
            else:
                bottom[r][c] = last - r
    return [(r, c) for r in range(n) for c in range(m)
            if location_map[r][c] == "O"
            and left[r][c] >= req_left and top[r][c] >= req_top
            and bottom[r][c] >= req_bottom and right[r][c] >= req_right]
# Follow-up "many queries, same grid": sweeps precomputed once, each query
# checks only the robot list. Mutating grid: recompute affected row+col.


# ---- 2. Fire escape: min time S->E before fire spreads (asked 2x) -----------
# Multi-source BFS for fire arrival times, then BFS for the person where a
# cell is enterable at time t only if t < fire_time. Convention documented:
# strict <, including at E.

def min_time_to_exit(grid: list[str]) -> int:
    n, m = len(grid), len(grid[0])
    INF = float("inf")
    fire = [[INF] * m for _ in range(n)]
    q: deque = deque()
    start = exit_ = None
    for r in range(n):
        for c in range(m):
            ch = grid[r][c]
            if ch == "F":
                fire[r][c] = 0
                q.append((r, c))
            elif ch == "S":
                start = (r, c)
            elif ch == "E":
                exit_ = (r, c)
    while q:                                     # multi-source BFS (fire)
        r, c = q.popleft()
        for nr, nc in ((r+1, c), (r-1, c), (r, c+1), (r, c-1)):
            if 0 <= nr < n and 0 <= nc < m and grid[nr][nc] != "#" \
                    and fire[nr][nc] == INF:
                fire[nr][nc] = fire[r][c] + 1
                q.append((nr, nc))
    seen = [[False] * m for _ in range(n)]
    sr, sc = start
    if fire[sr][sc] == 0:
        return -1
    q = deque([(sr, sc, 0)])
    seen[sr][sc] = True
    while q:                                     # person BFS
        r, c, t = q.popleft()
        if (r, c) == exit_:
            return t
        for nr, nc in ((r+1, c), (r-1, c), (r, c+1), (r, c-1)):
            if 0 <= nr < n and 0 <= nc < m and not seen[nr][nc] \
                    and grid[nr][nc] != "#" and t + 1 < fire[nr][nc]:
                seen[nr][nc] = True
                q.append((nr, nc, t + 1))
    return -1
# Follow-up "wait W minutes first, maximize W": feasible(W) = same BFS with
# t+1+W < fire; W is monotonic => binary search W over [0, n*m].


# ---- 3. Thief -> Bank avoiding police patrol radius (SDE-4 offer loop) ------
# Uniform k: mark patrolled via multi-source BFS to depth k, then BFS.
# Variable radii (the follow-up): seed with remaining budget, expand by max
# remaining budget first (Dijkstra-style on remaining radius).

def thief_path_exists(grid: list[list[int]], police: list[tuple[int, int]],
                      radii: list[int], thief: tuple[int, int],
                      bank: tuple[int, int]) -> bool:
    n, m = len(grid), len(grid[0])
    best = [[-1] * m for _ in range(n)]          # max remaining patrol budget seen
    pq = [(-radii[i], r, c) for i, (r, c) in enumerate(police)]
    heapq.heapify(pq)
    for neg, r, c in pq:
        best[r][c] = max(best[r][c], -neg)
    while pq:                                    # patrol marking
        neg, r, c = heapq.heappop(pq)
        rem = -neg
        if rem < best[r][c]:
            continue
        if rem == 0:
            continue
        for nr, nc in ((r+1, c), (r-1, c), (r, c+1), (r, c-1)):
            if 0 <= nr < n and 0 <= nc < m and rem - 1 > best[nr][nc]:
                best[nr][nc] = rem - 1
                heapq.heappush(pq, (-(rem - 1), nr, nc))
    patrolled = [[best[r][c] >= 0 for c in range(m)] for r in range(n)]
    tr, tc = thief
    br, bc = bank
    if patrolled[tr][tc] or patrolled[br][bc] or grid[tr][tc] or grid[br][bc]:
        return False
    q = deque([thief])
    seen = [[False] * m for _ in range(n)]
    seen[tr][tc] = True
    while q:
        r, c = q.popleft()
        if (r, c) == bank:
            return True
        for nr, nc in ((r+1, c), (r-1, c), (r, c+1), (r, c-1)):
            if 0 <= nr < n and 0 <= nc < m and not seen[nr][nc] \
                    and not grid[nr][nc] and not patrolled[nr][nc]:
                seen[nr][nc] = True
                q.append((nr, nc))
    return False
# NOTE: patrol spreads over open cells here (BFS distance). If the interviewer
# means pure Manhattan distance ignoring walls, mark |dr|+|dc| <= k instead —
# ASK which one. (That's a scored clarifying question.)


# ---- 4. Min cost path with diagonal moves (asked 2x, screening) -------------

def min_cost_path(cost: list[list[int]], x: int, y: int) -> int:
    dp = [[0] * (y + 1) for _ in range(x + 1)]
    dp[0][0] = cost[0][0]
    for i in range(x + 1):
        for j in range(y + 1):
            if i == 0 and j == 0:
                continue
            cands = []
            if i > 0:
                cands.append(dp[i-1][j])
            if j > 0:
                cands.append(dp[i][j-1])
            if i > 0 and j > 0:
                cands.append(dp[i-1][j-1])       # the diagonal Uber adds
            dp[i][j] = cost[i][j] + min(cands)
    return dp[x][y]


# ------------------------------- tests ---------------------------------------

def main() -> None:
    grid = [list("OEEX"), list("XXOE"), list("EXOX")]
    res = find_robots(grid, [1, 1, 1, 1])
    assert (0, 0) in res
    assert find_robots(grid, [2, 1, 1, 1]) == []
    grid2 = [list("EEE"), list("EOE"), list("EEE")]
    assert find_robots(grid2, [2, 2, 2, 2]) == [(1, 1)]
    assert find_robots(grid2, [3, 2, 2, 2]) == []

    # Fire at (2,0); S(0,0) -> (0,1) [t1 < fire 3] -> E(0,2) [t2 < fire 4] => 2
    assert min_time_to_exit(["S.E",
                             "...",
                             "F.."]) == 2
    # Fire between S and E on a single row: person can never enter (0,1)
    assert min_time_to_exit(["SFE"]) == -1

    grid3 = [[0] * 5 for _ in range(5)]
    assert thief_path_exists(grid3, [(2, 2)], [1], (0, 0), (4, 4)) is True
    assert thief_path_exists(grid3, [(2, 2)], [3], (0, 0), (4, 4)) is False

    assert min_cost_path([[1, 2], [3, 1]], 1, 1) == 2     # 1 -> diagonal -> 1
    assert min_cost_path([[1, 2, 3], [4, 8, 2], [1, 5, 3]], 2, 2) == 8

    print("PASS")


if __name__ == "__main__":
    main()
