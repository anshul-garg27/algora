
Enter leaf `t4`: **count query** → record `count = 3`  ✓. Roll back on exit.

Final recorded answers: `[t2 → 2, t4 → 3]`. Matches the paper trace. 🎉

**5. Formal statement:**
- *Invariant:* on entering the DFS at any tree node `v`, the DSU reflects exactly the union of all edges stored on the path root→v; on exit it's restored to the pre-entry state.
- *Component count:* `components = n − (number of successful unions currently on the stack)`, maintained incrementally.
- *DSU rule:* union by rank/size, **no path compression**, so each union touches `O(log n)` nodes and is exactly reversible by popping the stack.

Now let me implement and verify it.Everything passed: the sample gives `[2, 3]`, all edge cases are correct, 2000 randomized trials match the brute-force reference, and 100K ops on n=100K ran in ~0.33s. The approach I narrated held up, so there's no approach-update section.

## 6. Solution (runnable, commented code)

