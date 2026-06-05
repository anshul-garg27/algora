Invariant: `dp[i][j]` is the guaranteed net advantage of the player to move on `nums[i..j]`, both sides optimal.

Now let me implement and verify it.All tests pass: matches LeetCode examples, the brute-force minimax agreed on 3000 random arrays (including negatives), the reconstructed picks always sum to the DP difference, and n=1000 ran in ~0.055s. No approach change needed.

## 6. Solution (runnable, commented code)

