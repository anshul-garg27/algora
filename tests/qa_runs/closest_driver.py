> 💬 "The first driver I dequeue is (2,3), so that's my answer — driver B, even though driver A looked closer in a straight line."

**5. Formal statement:** BFS maintains the invariant that cells are dequeued in non-decreasing `dist` order; the first dequeued cell `c` with `c ∈ drivers` minimizes `dist(rider, c)` over all reachable drivers.

Now let me implement and verify it.All tests pass, including the full 1,000,000-cell grid in ~0.3s. The optimal approach from §3/§5 held up, so no correction section is needed.

## 6. Solution (runnable, commented code)

