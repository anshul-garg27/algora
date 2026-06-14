"""
UBER DSA MOCK #3 — 45 minutes — Closest Palindrome
====================================================
(Asked 3x in the last 12 months: screening, SDE-4 bar-raiser, and SDE-2 DSA
rounds. LC 564 — Uber asks it with edge-case follow-ups.)

Given an integer n as a string, find the closest palindrome (by absolute
difference) to n. If two palindromes tie, return the smaller one.
The answer must NOT be n itself.

  closest_palindrome(n: str) -> str

Edge cases the bar-raiser probed: "10", "11", "99", "1000", single digits,
numbers already palindromic.

Drive: candidates who enumerate "candidates = mirror, mirror±1 on the half,
10^k±1 boundaries" cleanly get Strong Hire; digit-by-digit ad-hoc logic
usually drowns in edge cases — that's the trap.
"""

# ============== YOUR IMPLEMENTATION BELOW ==============


def closest_palindrome(n: str) -> str:
    raise NotImplementedError


# ============== DEMO / ACCEPTANCE TESTS ==============

def main() -> None:
    assert closest_palindrome("123") == "121"
    assert closest_palindrome("1") == "0"        # not n itself; 0 and 2 tie -> smaller
    assert closest_palindrome("11") == "9"       # 9 (diff 2) beats 22 (diff 11)... check!
    assert closest_palindrome("10") == "9"
    assert closest_palindrome("99") == "101"     # 101 vs 88: |99-101|=2 < |99-88|=11
    assert closest_palindrome("1000") == "999"
    assert closest_palindrome("12121") == "12021"  # already palindrome -> nearest other
    assert closest_palindrome("100") == "99"
    print("PASS")


if __name__ == "__main__":
    main()
