"""Uber DSA solutions — DP & Digit-Math family.
Run: python3 dp_math.py
Problems: Closest Palindrome (3x), Optimal BST (2x, "toughest screening"),
Predict the Winner / Optimal Game Strategy (2x).
"""
from __future__ import annotations

from functools import lru_cache


# ---- 1. Closest Palindrome (asked 3x, incl. a bar-raiser) --------------------
# Candidate-set method — the ONLY approach that survives the edge probes:
#   * mirror of the left half, and mirrors of (half-1), (half+1)
#   * 10^(L-1) - 1  (all 9s, one digit shorter:  999)
#   * 10^L + 1      (one digit longer:           10001)
# Pick by (abs diff, value); exclude n itself. O(digits).

def closest_palindrome(n: str) -> str:
    length = len(n)
    num = int(n)
    half = int(n[: (length + 1) // 2])
    candidates = {10 ** (length - 1) - 1, 10 ** length + 1}
    for h in (half - 1, half, half + 1):
        s = str(h)
        if h <= 0:
            candidates.add(0 if h == 0 else -1)   # degenerate tiny cases
            continue
        if length % 2 == 0:
            candidates.add(int(s + s[::-1]))
        else:
            candidates.add(int(s + s[-2::-1]))
    candidates.discard(num)
    best = min((c for c in candidates if c >= 0),
               key=lambda c: (abs(c - num), c))
    return str(best)
# Variant Uber also asked ("smallest palindrome strictly greater than N"):
# same machinery — keep only candidates > num, take min.

def next_palindrome(n: int) -> int:
    s = str(n)
    length = len(s)
    half = int(s[: (length + 1) // 2])
    candidates = {10 ** length + 1}
    for h in (half, half + 1):
        t = str(h)
        pal = t + (t[::-1] if length % 2 == 0 else t[-2::-1])
        candidates.add(int(pal))
    return min(c for c in candidates if c > n)


# ---- 2. Optimal BST from sorted words + frequencies (asked 2x) ---------------
# cost(word at depth d, 1-based) = freq * d ; minimize total.
# Interval DP: dp[i][j] = min over root r of dp[i][r-1] + dp[r+1][j] + sum(i..j)
# (every node in the subtree gets one level deeper => + subtree freq sum).
# O(n^3); say "Knuth optimization brings it to O(n^2)" — don't code it.

def optimal_bst_cost(freq: list[int]) -> int:
    n = len(freq)
    prefix = [0] * (n + 1)
    for i, f in enumerate(freq):
        prefix[i + 1] = prefix[i] + f

    def rng(i: int, j: int) -> int:
        return prefix[j + 1] - prefix[i]

    dp = [[0] * n for _ in range(n)]
    for i in range(n):
        dp[i][i] = freq[i]
    for span in range(2, n + 1):
        for i in range(n - span + 1):
            j = i + span - 1
            best = min(
                (dp[i][r - 1] if r > i else 0) + (dp[r + 1][j] if r < j else 0)
                for r in range(i, j + 1)
            )
            dp[i][j] = best + rng(i, j)
    return dp[0][n - 1]
# The May-2026 screening pairing: words sorted lexicographically => BST order
# is fixed by the words; only the SHAPE is free. The words themselves are a
# red herring — only frequencies matter. SAY THIS: it's the unlock.


# ---- 3. Predict the Winner / Optimal Game Strategy (asked 2x) -----------------
# Two players pick from either END; both optimal. Minimax on the score DIFF:
# f(i,j) = best (my total - opponent total) for subarray i..j.

def game_result(nums: list[int]) -> tuple[int, bool]:
    """Returns (player1's best total, does player1 win-or-tie)."""
    total = sum(nums)

    @lru_cache(maxsize=None)
    def diff(i: int, j: int) -> int:
        if i == j:
            return nums[i]
        return max(nums[i] - diff(i + 1, j), nums[j] - diff(i, j - 1))

    d = diff(0, len(nums) - 1)
    p1 = (total + d) // 2
    diff.cache_clear()
    return p1, d >= 0
# Follow-ups the interviewer used: reconstruct the move sequence (walk the dp
# choosing the argmax), and "what if both can also pass?" (state grows).


# ------------------------------- tests ---------------------------------------

def main() -> None:
    assert closest_palindrome("123") == "121"
    assert closest_palindrome("1") == "0"
    assert closest_palindrome("11") == "9"
    assert closest_palindrome("10") == "9"
    assert closest_palindrome("99") == "101"
    assert closest_palindrome("1000") == "999"
    assert closest_palindrome("12121") == "12021"
    assert closest_palindrome("100") == "99"
    assert closest_palindrome("4") == "3"

    assert next_palindrome(123) == 131            # the exact Uber example
    assert next_palindrome(99) == 101
    assert next_palindrome(121) == 131
    assert next_palindrome(9) == 11

    assert optimal_bst_cost([34, 8, 50]) == 142   # classic GfG example
    assert optimal_bst_cost([3, 2, 4]) == 16      # the 2026 interview example
    assert optimal_bst_cost([10]) == 10

    p1, wins = game_result([1, 5, 2])
    assert (p1, wins) == (3, False)               # p1 loses 3 vs 5
    p1, wins = game_result([1, 5, 233, 7])
    assert (p1, wins) == (234, True)
    p1, wins = game_result([5, 5])
    assert (p1, wins) == (5, True)                # tie counts as not-losing

    print("PASS")


if __name__ == "__main__":
    main()
