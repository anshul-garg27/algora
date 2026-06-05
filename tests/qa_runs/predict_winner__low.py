
Now let me implement and verify it.Let me clean up that messy test harness:Everything matches brute force across all 3000 random cases, and every reconstructed pick sequence consumes exactly the original elements. Note `[-1,-5,-2]` returns False — even with negatives the math holds (P1 is forced into a worse net). Now the full write-up.

## 6. Solution (runnable, commented code)

