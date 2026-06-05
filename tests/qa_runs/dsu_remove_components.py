**Enter [3]:** leaf, not a query (t3 is the remove op). 
**Enter [4]:** leaf, **is the t4 query → record components = 3.** ✅
**Leave [3..4]:** roll back union(3,4).

Recorded answers: `[2, 3]` — matches our paper computation in §2. 🎉

> 💬 "I descend the tree applying each node's edges as unions and bumping the component count down on each successful merge. When I hit a query leaf I just read the current count. On the way back up I pop the union stack to undo exactly what that node added — that's the rollback that makes deletions work."

**5. Formal statement.** Maintain rollback DSU with `comp` = current component count, `comp = n − successful_unions`. Build segment tree on the time axis of length `T` (number of ops). For edge with life interval `[l, r]`, call `add(node, [l,r], edge)` distributing to O(log T) canonical nodes. `dfs(node)`: for each edge at node do `comp -= union(edge)`; if leaf and query, `answer = comp`; else recurse children; finally pop the rollback stack back to the size it had on entry. Total work O(n + Q log Q · α(n))-ish.

Now let me implement and verify it.Random testing surfaced a real semantics bug with **duplicate adds / parallel edges** — my multiset model diverged from a simple-graph model. Let me fix the edge-presence tracking to the standard simple-graph convention (a duplicate `add` of an already-present edge is a no-op; `remove` deletes the edge) and re-verify.All 3000 randomized trials now match the brute force, all edge cases pass, and 100,000 operations on n=100,000 run in ~0.43s.

## ⚠️ Approach update (after testing)

The algorithm (segment-tree-on-time + rollback DSU) held up — but testing exposed an important **definitional** issue: how to treat a *duplicate* `add_edge` of an already-present edge (and a `remove` of an absent edge). My first cut used a multiset/LIFO interval model, which disagreed with a simple-graph model on when an edge truly disappears. I switched to the **simple-graph convention**: a duplicate `add` is a no-op, and an edge becomes present on its first add and absent on remove.

> 💬 "One thing I should pin down out loud: if `add_edge` is called on an edge that's already there, do we treat it as a parallel edge or ignore it? I'll go with simple-graph semantics — an add of an existing edge is a no-op and a remove deletes it — and I'll guard against removing an edge that isn't present. If you want multigraph semantics I'd track edge multiplicity instead."

## 6. Solution (runnable, commented code)

