# LEARN: Union-Find (DSU) — Uber's #1 pattern

*Why this matters: DSU appeared more than any other technique in the last year
of Uber loops — OA, screening, AND onsite. If you master one thing, master this.*

## The idea in plain words

You have items that get **merged into groups** over time, and you keep asking
"are these two in the same group?" or "how many groups are there?"

Think of it as: every item has a **parent pointer**. Follow parents up and you
reach the group's **root** — the group's identity. Two items are in the same
group iff they have the same root.

Two tricks make it near-O(1):
1. **Path compression** — while finding the root, re-point everything you
   passed directly at the root. Next time it's one hop.
2. **Union by size** — always attach the smaller tree under the bigger one,
   so trees stay shallow.

## How to recognize it in an Uber question

The words change, the shape doesn't:
- "users **become connected** / share rides / become friends over time"
- "**merge** islands / clusters / zones"
- "when is everything **fully connected**?"
- "count **connected components** after each operation"
- Kruskal's MST (the OA "connect city hubs" question is exactly this)

Signal: connections are only **added**, and you need component info **between
additions**. (If connections are *removed*, see the trap below.)

## The template (memorize cold — you should type this in under 2 minutes)

```python
class DSU:
    def __init__(self, items=()):
        self.parent = {}; self.size = {}; self.components = 0
        for x in items: self.add(x)

    def add(self, x):
        if x not in self.parent:
            self.parent[x] = x; self.size[x] = 1; self.components += 1

    def find(self, x):
        root = x
        while self.parent[root] != root: root = self.parent[root]
        while self.parent[x] != root:                 # path compression
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb: return False
        if self.size[ra] < self.size[rb]: ra, rb = rb, ra
        self.parent[rb] = ra
        self.size[ra] += self.size[rb]
        self.components -= 1
        return True
```

Complexity to state: **O(α(n)) amortized per op** — "effectively constant,
α is inverse Ackermann." Saying this sentence calmly is itself a signal.

## Worked example (the actual Uber question, asked 3+ times)

> Logs: `<ts> <UserA> shared_ride <UserB>`, sorted by time. Find the earliest
> timestamp when ALL users are connected.

Thought process out loud:
1. "Connections only get added → connectivity only improves → DSU."
2. "I'll seed DSU with every user that appears (scan once), then replay logs."
3. "Track `components`; the first union that brings it to 1 gives the answer."
4. Complexity: O(m α) after O(m) parse. Done in ~10 lines.

Full code: `../solutions/graphs_dsu.py` → `earliest_full_connectivity`.

## THE trap (this is where the follow-up kills people)

Follow-up Uber always asks: **"now rides can be cancelled (edge removed)."**

Two things you MUST say:
1. **"DSU cannot delete edges."** Union is a one-way merge; there is no
   un-merge. Candidates who silently try to "remove from DSU" cap at Lean Hire.
2. **"Connectivity is no longer monotonic over time"** — it can flicker
   connected → disconnected → connected. So binary-searching the answer
   timestamp ALSO breaks. (Catching this unprompted = Strong Hire signal.)

Acceptable interview answer: keep an edge multiset; after each event, rebuild
DSU from live edges and check (O(m²) worst case — say it honestly). Mention
"offline dynamic connectivity exists but is out of interview scope."

## Mistakes that cost offers

- Forgetting path compression → TLE on 10^5-10^6 OA inputs.
- Using recursion for `find` → recursion limit on deep chains in Python.
- Not seeding all users first → components count starts wrong.
- Self-union (`union(a,a)`) decrementing components — guard with the
  `ra == rb` early return.

## Practice ladder

1. LC 547 Number of Provinces (warm-up)
2. LC 1319 Make Network Connected
3. LC 305 Number of Islands II (this IS the Uber screening question, 2026-04)
4. LC 721 Accounts Merge
5. LC 1584 Min Cost to Connect Points (≈ the Uber OA hubs question)
6. Mock: `../mocks/dsa_01_dsu_logs.py`
