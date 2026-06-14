"""Uber DSA solutions — Graph/DSU family (Uber's #1 pattern).
Run: python3 graphs_dsu.py
Problems: ride-log connectivity (+deletion follow-up), alien dictionary,
minimum edge reversals (re-rooting), making a large island.
"""
from __future__ import annotations

from collections import defaultdict, deque


class DSU:
    def __init__(self, items=()) -> None:
        self.parent: dict = {}
        self.size: dict = {}
        self.components = 0
        for x in items:
            self.add(x)

    def add(self, x) -> None:
        if x not in self.parent:
            self.parent[x] = x
            self.size[x] = 1
            self.components += 1

    def find(self, x):
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:           # path compression
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a, b) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        if self.size[ra] < self.size[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        self.size[ra] += self.size[rb]
        self.components -= 1
        return True


# ---- 1. Earliest full connectivity from ride logs (asked 3+ times) ----------
# O(m α). Count components down to 1.

def earliest_full_connectivity(logs: list[str]) -> int:
    parsed = []
    users = set()
    for line in logs:
        ts, a, _, b = line.split()
        parsed.append((int(ts), a, b))
        users.update((a, b))
    dsu = DSU(users)
    for ts, a, b in parsed:
        dsu.union(a, b)
        if dsu.components == 1:
            return ts
    return -1


# FOLLOW-UP (the real one): logs may also contain "cancelled_ride" removing a
# connection. KEY LINE TO SAY: "DSU doesn't support deletion, and connectivity
# is no longer monotonic in time, so binary-searching the answer breaks too."
# Accepted approach: maintain edge multiset, after each event run BFS/DSU over
# current edges until first success — O(m^2) worst case, fine for interview.

def earliest_full_connectivity_with_cancel(logs: list[str]) -> int:
    edges: dict[tuple, int] = defaultdict(int)
    users = set()
    parsed = []
    for line in logs:
        ts, a, verb, b = line.split()
        parsed.append((int(ts), a, verb, b))
        users.update((a, b))
    for ts, a, verb, b in parsed:
        key = (min(a, b), max(a, b))
        if verb == "cancelled_ride":
            if edges[key] > 0:
                edges[key] -= 1
        else:
            edges[key] += 1
        dsu = DSU(users)                        # rebuild
        for (u, v), cnt in edges.items():
            if cnt > 0:
                dsu.union(u, v)
        if dsu.components == 1:
            return ts
    return -1


# ---- 2. Alien Dictionary (asked 4x) -----------------------------------------
# Topological sort (Kahn's). Trap: ["abc","ab"] is invalid (prefix case).

def alien_order(words: list[str]) -> str:
    graph: dict[str, set[str]] = {c: set() for w in words for c in w}
    indeg: dict[str, int] = {c: 0 for c in graph}
    for w1, w2 in zip(words, words[1:]):
        for c1, c2 in zip(w1, w2):
            if c1 != c2:
                if c2 not in graph[c1]:
                    graph[c1].add(c2)
                    indeg[c2] += 1
                break
        else:
            if len(w1) > len(w2):
                return ""                       # invalid: longer word first
    q = deque(sorted(c for c in indeg if indeg[c] == 0))  # sorted = stable output
    out = []
    while q:
        c = q.popleft()
        out.append(c)
        for nxt in sorted(graph[c]):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                q.append(nxt)
    return "".join(out) if len(out) == len(graph) else ""  # "" => cycle
# Follow-ups asked: how do you detect the cycle (out shorter than node count);
# multiple valid orders (any topo order acceptable — say it).


# ---- 3. Minimum edge reversals so every node reachable (asked 2x, OA+BPS) ---
# Tree with n-1 directed edges. Re-rooting: ans[child] = ans[parent] ± 1.
# O(n).

def min_edge_reversals(n: int, edges: list[tuple[int, int]]) -> list[int]:
    adj: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for u, v in edges:
        adj[u].append((v, 0))                   # original direction: cost 0
        adj[v].append((u, 1))                   # traversing against: cost 1
    ans = [0] * n
    seen = [False] * n
    seen[0] = True
    stack = [0]
    root_cost = 0
    while stack:                                # pass 1: cost for root 0
        u = stack.pop()
        for v, w in adj[u]:
            if not seen[v]:
                seen[v] = True
                root_cost += w
                stack.append(v)
    ans[0] = root_cost
    q = deque([0])                              # pass 2: re-root via BFS
    visited = [False] * n
    visited[0] = True
    while q:
        u = q.popleft()
        for v, w in adj[u]:
            if not visited[v]:
                visited[v] = True
                # edge u->v original (w=0): moving root to v costs one reversal
                ans[v] = ans[u] + (1 if w == 0 else -1)
                q.append(v)
    return ans


# ---- 4. Making a Large Island (asked 2x: "flip one 0") -----------------------
# Label components, sizes; for each 0 sum distinct neighbor components. O(n^2).

def largest_island(grid: list[list[int]]) -> int:
    n, m = len(grid), len(grid[0])
    label = [[0] * m for _ in range(n)]
    sizes = {0: 0}
    cur = 0
    for i in range(n):
        for j in range(m):
            if grid[i][j] == 1 and label[i][j] == 0:
                cur += 1
                sz = 0
                stack = [(i, j)]
                label[i][j] = cur
                while stack:
                    r, c = stack.pop()
                    sz += 1
                    for nr, nc in ((r+1, c), (r-1, c), (r, c+1), (r, c-1)):
                        if 0 <= nr < n and 0 <= nc < m and grid[nr][nc] == 1 \
                                and label[nr][nc] == 0:
                            label[nr][nc] = cur
                            stack.append((nr, nc))
                sizes[cur] = sz
    best = max(sizes.values())                   # no flip needed case
    for i in range(n):
        for j in range(m):
            if grid[i][j] == 0:
                neigh = {label[ni][nj]
                         for ni, nj in ((i+1, j), (i-1, j), (i, j+1), (i, j-1))
                         if 0 <= ni < n and 0 <= nj < m}
                best = max(best, 1 + sum(sizes.get(l, 0) for l in neigh if l))
    return best


# ------------------------------- tests ---------------------------------------

def main() -> None:
    assert earliest_full_connectivity(
        ["1 A shared_ride B", "3 C shared_ride D", "5 B shared_ride C"]) == 5
    assert earliest_full_connectivity(
        ["1 A shared_ride B", "2 C shared_ride D"]) == -1

    logs = ["1 A shared_ride B", "2 B shared_ride C",
            "3 A cancelled_ride B", "4 A shared_ride C"]
    assert earliest_full_connectivity_with_cancel(logs) == 2  # all connected at 2
    logs2 = ["1 A shared_ride B", "2 A cancelled_ride B",
             "3 B shared_ride C", "4 A shared_ride B"]
    assert earliest_full_connectivity_with_cancel(logs2) == 4

    assert alien_order(["wrt", "wrf", "er", "ett", "rftt"]) == "wertf"
    assert alien_order(["z", "x"]) == "zx"
    assert alien_order(["abc", "ab"]) == ""      # invalid prefix case

    ans = min_edge_reversals(4, [(2, 0), (2, 1), (1, 3)])
    # edges: 2->0, 2->1, 1->3. From 0: need reverse 2->0 (1), then 2->1 ok...
    # known LC 2858 example answer: [1, 1, 0, 2]
    assert ans == [1, 1, 0, 2], ans

    assert largest_island([[1, 0], [0, 1]]) == 3
    assert largest_island([[1, 1], [1, 0]]) == 4
    assert largest_island([[1, 1], [1, 1]]) == 4

    print("PASS")


if __name__ == "__main__":
    main()
