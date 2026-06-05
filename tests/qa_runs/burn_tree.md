## 1. Problem Understanding

We have an undirected tree with N nodes (N up to 100,000). We pick a "start" node, light it on fire, and every time unit the fire spreads from each burning node to all its direct neighbors. We want to choose the start node so that the **whole tree finishes burning as fast as possible**, and return that minimum time.

The time to burn the whole tree from a chosen start node `s` equals the distance from `s` to the farthest node (its **eccentricity**). Minimizing that over all start nodes is, by definition, the **radius** of the tree.

**Clarifying questions to ask:**
- Are edges given as a list of pairs, and are nodes labeled 0..N-1 or 1..N? (affects indexing)
- Is the input guaranteed to be a tree (connected, N-1 edges, no cycles)? Single node case (N=1) → answer 0?
- Time is measured in "edges traversed" (1 unit per hop), so adjacent node burns at time 1, right?
- Can N=0 happen? I'll assume N≥1.

> 💬 "So I light one node, and each second the fire jumps to every neighbor. The time to fully burn from a given start is just the distance to the farthest node from it. I want the start that minimizes that worst-case distance — that's exactly the radius of the tree. Let me confirm: edges form a valid tree, and burning one hop costs 1 time unit?"

## 2. Understand It On Paper (slow, visual)

Let me make this concrete. The "time to burn everything starting at node s" is the largest distance from s to any other node. Pick the s that makes that largest distance as small as possible.

Take this small tree:

```
        0
        |
        1
       / \
      2   3
          |
          4
```

Edges: 0-1, 1-2, 1-3, 3-4.

Let me compute, for each possible start, the time to burn the whole tree (= farthest distance):

```
Start at 0:  farthest is 4, distance 0->1->3->4 = 3   => time 3
Start at 2:  farthest is 4, 2->1->3->4 = 3            => time 3
Start at 4:  farthest is 0 or 2, 4->3->1->0 = 3       => time 3
Start at 1:  distances: 0=1, 2=1, 3=1, 4=2  -> max 2  => time 2
Start at 3:  distances: 4=1, 1=1, 0=2, 2=2  -> max 2  => time 2
```

Best is starting at node 1 (or 3): time **2**. That's the radius.

Now the key picture. Look at the **longest path in the tree** (the diameter). Here the longest path is 0—1—3—4 (or 2—1—3—4), length 3 edges:

```
   0 --- 1 --- 3 --- 4        (diameter path, 3 edges)
   ^                 ^
  end              end
```

The best place to start the fire is the **middle of this longest path**. Why? Whatever node you start from, the two ends of the diameter are the hardest to reach. If you stand in the middle, you split that longest path roughly in half.

```
   0 --- 1 --- 3 --- 4
            ^
          center  ->  distance to each end ≈ 3/2 = 1.5 -> ceil = 2
```

So the answer is **ceil(diameter_length / 2)**, where diameter_length is the number of edges on the longest path.

Here diameter = 3 edges, ceil(3/2) = 2. ✓ Matches our brute-force table.

**Building the aha visually — why the middle of the diameter?**

The single observation: the eccentricity of any node is dominated by the distance to one of the two diameter endpoints. (In a tree, the farthest node from ANY node is always one of the two diameter endpoints — a well-known fact.) So minimizing your worst-case distance means sitting as centrally as possible between those two endpoints. The center of the diameter path gives exactly ceil(D/2).

```
Even diameter (D=4):  a - x - C - y - b   center C, dist 2 each  -> radius 2
Odd diameter (D=3):   a - x - y - b       two centers x,y, dist 2 -> radius 2 = ceil(3/2)
```

**Constraints check:**
- N up to 1e5 → we need O(N), not O(N²). Computing each node's eccentricity separately would be O(N²) = 1e10, too slow. The diameter trick is O(N).
- Recursion depth could be 1e5 (a path graph) → use **BFS (iterative)**, not recursive DFS, to avoid stack overflow.
- N=1 → no edges, diameter 0, answer 0.

## 3. Approach & Intuition

This screams "tree diameter" the moment you see "minimize the farthest distance from a chosen center." Pattern recognition:

- "Burn time from a node = farthest distance from it" → that's **eccentricity**.
- "Minimize over all start nodes" → that's the **radius** = minimum eccentricity.
- For a **tree**, radius = ceil(diameter / 2). So the whole problem reduces to **finding the diameter**, which is the classic **two-BFS trick**.

> 💬 "The phrase 'fastest to burn the whole tree from the best start' is just the radius of the tree. And for a tree there's a clean identity: radius equals ceil(diameter / 2). So I'll find the diameter — the longest path between any two nodes — and the answer falls right out."

**The two-BFS trick for diameter:**
1. BFS from any node → reach the farthest node `u`. `u` is guaranteed to be one endpoint of a diameter.
2. BFS from `u` → the farthest distance found is the diameter length, and that node `v` is the other endpoint.

> 💬 "To get the diameter I run BFS from any node to find the farthest node — call it u. Then BFS again from u; the farthest distance from u is the diameter. It's a neat property of trees that the farthest node from any start is always a diameter endpoint."

## 4. Brute Force

The natural first idea: for **every** node, run a BFS/DFS to find its farthest distance (eccentricity), then take the minimum.

```
for each node s in tree:
    d = BFS(s) -> max distance to any node
    answer = min(answer, d)
```

- Time: O(N) per BFS × N nodes = **O(N²)** → 1e10 for N=1e5, way too slow.
- Space: O(N).

> 💬 "The brute force is: compute every node's farthest distance with a BFS, take the minimum. That's correct but O(N²) — fine to mention as a baseline, but for N up to 1e5 I need linear time, so I'll use the diameter property instead."

## 5. Optimal Approach

**1. Core idea in one sentence:** The answer is ceil(diameter / 2) — find the longest path in the tree using two BFS passes, then halve it (rounding up).

**2. Why it works:** In a tree, the node farthest from *any* node is always an endpoint of the diameter. So the best place to start the fire is the midpoint of the diameter path, and from there the farthest you ever have to reach is half the diameter, rounded up.

**3. The steps:**
1. Build an adjacency list.
2. BFS from node 0 → find farthest node `u`.
3. BFS from `u` → the max distance is the diameter `D` (and farthest node is `v`).
4. Return `(D + 1) // 2`  (= ceil(D/2)).

**4. Trace on a tiny example.** Same tree, edges 0-1, 1-2, 1-3, 3-4:

```
        0
        |
        1
       / \
      2   3
          |
          4
```

**Step A — BFS from node 0**, track distances:

```
node:  0  1  2  3  4
dist:  0  1  2  2  3
                    ^ farthest = node 4 (dist 3)  => u = 4
```

> 💬 "BFS from 0. Distances: node 4 is farthest at distance 3. So u = 4 — that's one end of the diameter."

**Step B — BFS from node u=4**, track distances:

```
Queue trace from 4:
  visit 4 (d=0)
  visit 3 (d=1)
  visit 1 (d=2)
  visit 0 (d=3), visit 2 (d=3)

node:  0  1  2  3  4
dist:  3  2  3  1  0
       ^     ^
  max distance = 3  => diameter D = 3  (path 4-3-1-0 or 4-3-1-2)
```

> 💬 "BFS again from 4. The farthest distance now is 3 — that's the diameter. The longest path is 4–3–1–0, three edges."

**Step C — compute answer:**

```
radius = ceil(D / 2) = ceil(3/2) = (3 + 1) // 2 = 2
```

> 💬 "Diameter is 3, so the radius is ceil(3/2) = 2. That matches my hand check — starting at node 1 or 3 burns everything in 2 units."

**5. Formal statement:**
- Diameter D = max over all pairs (a,b) of dist(a,b). Computed via two BFS in O(N).
- Radius R = min over s of max_t dist(s,t) = ceil(D/2) for any tree.
- Answer = (D + 1) // 2.

Now let me implement and verify it.All tests pass — the two-BFS diameter approach matches the O(N²) brute force on 2000 random trees, handles N=1, and runs on a 100,000-node path in ~0.03s. (One note: my inline comment guessed "49999" for the 100k-path, but the true answer is 50000 = ceil(99999/2) — the code is right, my comment was off by one. No change to the approach.)

## 6. Solution (runnable, commented code)

```python
from collections import deque

def min_burn_time(n, edges):
    """Minimum time to burn the whole tree from an optimally chosen start node.
    Equals the tree radius = ceil(diameter / 2). O(N) via two BFS passes."""
    if n <= 1:
        return 0  # single/empty node: nothing to spread to

    # Build adjacency list
    adj = [[] for _ in range(n)]
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)

    def bfs(src):
        """Return (farthest_node, distance_to_it) using ITERATIVE BFS
        so a long path (depth up to 1e5) can't overflow the stack."""
        dist = [-1] * n
        dist[src] = 0
        q = deque([src])
        far_node, far_dist = src, 0
        while q:
            node = q.popleft()
            for nxt in adj[node]:
                if dist[nxt] == -1:               # unvisited
                    dist[nxt] = dist[node] + 1
                    if dist[nxt] > far_dist:
                        far_dist, far_node = dist[nxt], nxt
                    q.append(nxt)
        return far_node, far_dist

    # Step 1: from any node, the farthest node u is a diameter endpoint.
    u, _ = bfs(0)
    # Step 2: from u, the farthest distance IS the diameter.
    _, diameter = bfs(u)

    # Radius = ceil(diameter / 2)  -> the burn time from the optimal center.
    return (diameter + 1) // 2
```

## 7. Code Walkthrough

Trace on the example tree, edges `[(0,1),(1,2),(1,3),(3,4)]`:

1. **Build `adj`:** `0:[1], 1:[0,2,3], 2:[1], 3:[1,4], 4:[3]`.
2. **`bfs(0)`:** distances become `[0,1,2,2,3]`. The running `far_dist` climbs to 3 at node 4, so it returns `u = 4`.
   - State of the queue: `0 → 1 → 2,3 → 4`. Each pop sets unvisited neighbors’ distance to parent+1.
3. **`bfs(4)`:** distances become `[3,2,3,1,0]`. Max distance seen is 3 → `diameter = 3`.
4. **Answer:** `(3 + 1) // 2 = 2`. ✓

The key variable to narrate is `far_dist` inside BFS — it’s a running maximum that captures "how deep have I gone from the source," and on the second BFS that maximum is precisely the diameter.

> 💬 "First BFS gives me an endpoint u of the longest path. Second BFS from u, the deepest distance is the diameter. Then I just halve it, rounding up."

## 8. Complexity Analysis

| Approach | Time | Space | Why |
|---|---|---|---|
| Brute force | O(N²) | O(N) | One BFS (O(N)) from every one of N nodes |
| Optimal (2× BFS) | **O(N)** | **O(N)** | Exactly two BFS traversals; each visits N nodes and N-1 edges once |

- **Time O(N):** Two BFS passes; each is linear in nodes + edges, and a tree has N-1 edges, so it's O(N) total.
- **Space O(N):** adjacency list (O(N) for a tree), plus the `dist` array and BFS queue, each O(N).
- Iterative BFS (not recursive DFS) keeps us safe from a stack overflow on a degenerate path-shaped tree of depth 1e5.

## 9. Edge Cases & Pitfalls

- **N = 1 (single node):** No edges, nothing spreads → answer 0. Handled by the early return. (Tested ✓)
- **N = 2:** One edge, diameter 1 → radius 1. (Tested ✓)
- **Path / "caterpillar" tree:** Worst-case depth = N-1; recursive DFS would blow the stack — that's why BFS is iterative. (Tested on 1e5-node path ✓)
- **Star graph:** Diameter 2 regardless of size → radius 1; the center is the optimal start. (Tested ✓)
- **Off-by-one on rounding:** Use `(D + 1) // 2`, i.e. **ceil**, not floor. Floor would be wrong for odd diameters (e.g. D=3 → 1 is wrong, should be 2).
- **Node labeling:** Confirm 0-indexed vs 1-indexed; shift inputs if labels are 1..N.
- **Assuming farthest-from-arbitrary-node is the diameter:** It's not — that's only one *endpoint*. You need the **second** BFS from u to actually measure the diameter. Skipping it is the classic bug interviewers probe.
- **Disconnected input:** Problem guarantees a tree (connected). If it weren't, BFS would only cover one component — worth stating the assumption.

> 💬 **30-second verbal summary:** "Burning the whole tree from the best start node is the tree's radius, and for a tree radius = ceil(diameter / 2). I find the diameter with the standard two-BFS trick: BFS from any node to find a farthest node u, then BFS from u — that farthest distance is the diameter. Answer is (diameter + 1) // 2. It's O(N) time and space, I use iterative BFS to avoid stack overflow on long paths, and edge cases like a single node return 0."