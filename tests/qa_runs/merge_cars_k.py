
**5. Formal statement / invariant:** After processing index i, the stack holds the fully-reduced sequence of `(name, count)` groups for the prefix `0..i`, where every `count` is in `[1, K-1]` after a reset (or `[1, K]` momentarily before the snap). A group's count is reset to 1 exactly when it reaches K, modeling "replace K consecutive with one."

Now let me implement and verify it.The example matches, all edge cases behave, and 3000 randomized cases agree with the brute force — the single-pass stack approach from Sections 3/5 held up, so no correction is needed.

## 6. Solution (runnable, commented code)

