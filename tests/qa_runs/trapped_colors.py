
> 💬 "All 8 neighbors are B, the opposite color, and I never hit a W — so this cell is trapped, return True."

Now contrast: if I'd flipped `(2,2)` to `'W'`, then when I reach `(2,2)='W'` (same as center) I instantly return `False` without finishing — that's the early exit in action.

**5. Formal statement:** `is_trapped(i,j,k)` is `True` iff for all `(r,c)` with `max(0,i-k) <= r <= min(n-1,i+k)` and `max(0,j-k) <= c <= min(m-1,j+k)` and `(r,c) != (i,j)`, we have `matrix[r][c] != matrix[i][j]`.

**For classifying the whole grid efficiently**, replace the per-cell scan with a **2D prefix sum** of black cells. Let `B(rect)` = count of black cells in a rectangle (O(1) via the summed-area table). A cell is trapped iff the box (minus the center) is *all one opposite color*, i.e. the number of neighbors equal to the center color is 0. Compute `total neighbors` and `black neighbors` in the clamped box; the cell is trapped iff all neighbors are opposite. That makes whole-grid classification `O(n*m)` instead of `O(n*m*k^2)`.

Let me now write and verify both the single-query function and the prefix-sum whole-grid version.My hand-picked test grid was wrong (the `W` columns leak into the box). Let me fix the test data, not the logic.Cross-checked: brute force and prefix-sum agree on 3000 random grids, and the whole 1000x1000 grid classifies in **0.39s**.

## ⚠️ Approach update (after testing)

The **algorithm didn't change**, but my illustrative 5x5 grid in Section 2 was sloppy — in that checkerboard, the cell `(2,2)`'s 3x3 box actually *does* contain some `W` neighbors, so it would **not** be trapped. The clean example to use is the simple "one `W` boxed by all `B`" 3x3 (the one in Section 5), which I verified really is trapped.

> 💬 "Quick correction on my drawing — in that checkerboard the center actually has a couple of same-color cells in its box, so it's not trapped. The cleaner illustration is a single white cell surrounded by a solid ring of black — that one is genuinely trapped."

## 6. Solution (runnable, commented code)

