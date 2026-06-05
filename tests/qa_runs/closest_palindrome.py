
Step D — smallest diff is `13`, from `1221`. None equals `n`, no tie. **Answer: `1221`.** ✓

> 💬 "Prefix is '12'. I mirror 11, 12, 13 to get 1111, 1221, 1331, then add the boundary palindromes 999 and 10001. Distances from 1234 are 123, 13, 97, 235, 8767 — the winner is 1221 at distance 13."

Quick second trace on the tie case `n = "1000"`: candidates include `999` (diff 1) and `1001` (diff 1) → tie → smaller → **`999`**. This is exactly why the all-9s boundary candidate matters.

**5. Formal statement / invariant:** Let `k = ceil(L/2)`, `prefix = int(n[:k])`. Each candidate palindrome is `mirror(p)` for `p ∈ {prefix-1, prefix, prefix+1}`, where `mirror(p)` reflects `p` over the center using `L` parity, together with `10^(L-1)-1` and `10^L+1`. The answer is `argmin |c - n|` over candidates `c ≠ n`, breaking ties by smaller `c`. Completeness holds because any palindrome closer than these would have to agree with `n` on the leading digits (covered by prefix±1) or change length (covered by the two boundaries).

Now let me implement and verify it.Let me cross-check against a brute-force oracle for all small inputs to be sure.Zero mismatches against brute force across all inputs 1–19,999 (including all tie cases). The approach holds — no correction needed.

## 6. Solution (runnable, commented code)

