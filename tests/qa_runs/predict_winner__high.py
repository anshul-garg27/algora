
So **P1 picks [1, 2], P2 picks [5]** → P1=3, P2=5. Consistent.

**5. Formal statement:**
- Recurrence: `dp[i][j] = max(nums[i] - dp[i+1][j], nums[j] - dp[i][j-1])`, base `dp[i][i] = nums[i]`.
- Invariant: `dp[i][j]` = optimal (current-player-score − opponent-score) for `nums[i..j]`.
- Answer: `dp[0][n-1] >= 0`.

Now let me implement and verify it.Everything passed, including 3000 random arrays checked against an independent brute force, and the picks always sum correctly. Notably, on the classic `[1, 5, 233, 7]`, P1 indeed sacrifices the `1` to capture the `233` — exactly the non-greedy insight.

## 6. Solution (runnable, commented code)

