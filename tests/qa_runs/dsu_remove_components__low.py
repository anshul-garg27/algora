
Between branches, the DFS **rolls back** unions (pop the stack, restore parent/size, components += 1) so each path is independent. Answers collected: **2, 1, 2**.

> 💬 "Watch the component counter: it starts at n, drops by one on every *successful* union as I descend, and pops back up by one on every rollback as I ascend. Each query leaf just reads the counter — no recomputation."

**5. Formal statement / invariants:**
- **Invariant:** when DFS is at segment-tree node covering time-range S, the DSU equals the graph formed by all edges whose intervals fully cover S (the ancestors' canonical placements).
- DSU: union by size, no path compression → `find` is O(log n); each union pushes one record; rollback pops it restoring `parent[root]` and `size`, and adjusts `components`.

Now let me implement and verify it.Sample passes. The error is only in my test harness (a self-loop add isn't appended, so `ops[-1]` references the wrong op). Let me fix the harness.All 2000 random trials match the brute-force oracle, the 1e5-op stress runs in ~0.8s, and edge cases behave correctly. My §5 approach held up — no correction section needed.

## 6. Solution (runnable, commented code)

