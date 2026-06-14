# LEARN: Topological Sort — the Alien Dictionary family

*Why this matters: Alien Dictionary alone was asked 4x at Uber last year
(phone screens AND onsites), plus Course Schedule I/II twice, plus the
"microservice start cycles" question — all the same pattern.*

## The idea in plain words

Some tasks depend on others: "b must come before a". Draw an arrow b → a.
A **topological order** is any line-up of all nodes where every arrow points
forward. It exists **iff there is no cycle**.

Kahn's algorithm (the one to use in interviews — cycle detection is free):
1. Count incoming arrows (`indegree`) for every node.
2. Start with all nodes having indegree 0 (nothing blocks them).
3. Repeatedly take one out, "remove" its outgoing arrows (decrement
   neighbors' indegree), and add any neighbor that just hit 0.
4. If you produced fewer nodes than exist → **cycle** → no valid order.

## The template

```python
from collections import deque

def topo_order(nodes, edges):           # edges: (before, after)
    graph = {u: [] for u in nodes}
    indeg = {u: 0 for u in nodes}
    for u, v in edges:
        graph[u].append(v)
        indeg[v] += 1
    q = deque(u for u in nodes if indeg[u] == 0)
    out = []
    while q:
        u = q.popleft()
        out.append(u)
        for v in graph[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    return out if len(out) == len(nodes) else None   # None => cycle
```

## Worked example: Alien Dictionary (the 4x Uber question)

> Words sorted in an unknown language's order. Recover the character order.

The unlock (say this): "The SORTING gives me pairwise character constraints.
For adjacent words, the **first differing character** tells me an order:
if `wrt` < `wrf` then `t` < `f`. One edge per adjacent pair, then topo sort."

Steps out loud:
1. Nodes = every character appearing anywhere.
2. For each adjacent word pair: find first mismatch → edge c1 → c2. **Only
   the first mismatch** — later characters tell you nothing.
3. **The trap that distinguishes candidates**: `["abc", "ab"]` — no mismatch
   but the longer word comes first. That's INVALID input → return "". An Uber
   phone-screen candidate reported this exact probe.
4. Topo sort; produced fewer chars than nodes → cycle → "".

Follow-ups Uber asked:
- "Is the order unique?" — No; any valid topo order is acceptable. Unique iff
  at every step the queue has exactly one element.
- "How do you detect the cycle?" — output shorter than node count (Kahn) or
  gray/black states (DFS version). Know both sentences.

## Worked example 2: Microservice start cycles (SDE-1 2026, asked 2x)

> Services with dependencies start in repeated scan-cycles 0..N-1; a service
> starts if its deps already started. Min number of cycles, or impossible.

This is topo sort + one extra observation: within a single scan, a service
can start in the SAME cycle as its dependency **only if the dependency has a
smaller index**. So: `cycles(v) = max over deps u of (cycles(u) if u.index <
v.index else cycles(u) + 1)` processed in topological order. Impossible =
cycle in the graph. This "topo order + DP along the order" combo is extremely
common — recognize it as one unit.

## Mistakes that cost offers

- Adding edges for EVERY differing position instead of just the first.
- Missing the prefix-invalid case (`["abc","ab"]`).
- Building duplicate edges and double-counting indegree (use a set per node).
- Saying "DFS topological sort" and then fumbling cycle detection — Kahn's
  gives it for free; default to Kahn's under pressure.

## Practice ladder

1. LC 207 Course Schedule (asked at Uber)
2. LC 210 Course Schedule II (asked at Uber, same loop)
3. LC 269 Alien Dictionary (THE question)
4. LC 2115 Recipes from Supplies (topo + DP feel)
5. Microservice variant: `../mocks/` retake list & data.json #1834
