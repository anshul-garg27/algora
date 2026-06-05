
`t` fully matched → **2 copies**. ✅

> 💬 "Watch the pointer: it walks a-b-c, runs off the end, so I spend a second copy and restart at the front to grab the trailing b-c. Two copies total — and I never built the doubled string, I just counted the wrap."

**5. Formal invariant:** At any moment, `i` is the smallest index in the current copy such that the prefix of `t` processed so far is a subsequence of `(copies-1)` full copies of `s` plus `s[0..i)`. Greedy choice of earliest match preserves minimality of `copies`.

Now let me implement and verify it.All sample cases, edge cases, a 3000-iteration random cross-check against brute force, and the max-size (1000x1000) stress all pass — the greedy approach held up, so no correction needed.

## 6. Solution

