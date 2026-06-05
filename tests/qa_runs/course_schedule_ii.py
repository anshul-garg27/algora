
> 💬 "Here both courses depend on each other, so neither ever has in-degree zero. The queue starts empty, I place nothing, and since I placed fewer than all courses I return an empty list — that's my cycle detection."

**5. Formal invariant:** At every step, `order` contains a valid topological prefix; a node is enqueued exactly when its in-degree reaches 0, i.e. all its predecessors are already in `order`. The loop runs `O(V + E)` since each node is enqueued once and each edge relaxed once.

Let me implement and verify this.All tests pass — including cycles, self-loop, single course, no prerequisites, and a 100,000-node chain. The Kahn's-algorithm approach I narrated held up, so no approach update is needed.

## 6. Solution (runnable, commented code)

