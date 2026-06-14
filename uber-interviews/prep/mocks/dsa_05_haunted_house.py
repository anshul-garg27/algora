"""
UBER DSA MOCK #5 — 45 minutes — Haunted House (group constraints)
===================================================================
(Asked 3x at Uber last year — elimination round, onsite Coding Round 1 at a
hiring drive, and an SDE-3 DSA round. HackerRank-original, Uber rewords it.)

N people want to visit a haunted house. Person i will only go if the number
of OTHER people going is at least L[i] and at most R[i] — i.e., in a group
of size k that includes person i:  L[i] <= k-1 <= R[i].

  max_group_size(L, R) -> int
      Largest possible group size (0 if nobody can go).

Constraints: N up to 2*10^5  =>  O(n log n) or O(n).

The interviewer will push: brute force first (try every k: O(n^2)), then
optimize. Leave time for the follow-up after your solution works.
"""

# ============== YOUR IMPLEMENTATION BELOW ==============


def max_group_size(L: list[int], R: list[int]) -> int:
    raise NotImplementedError


# ============== DEMO / ACCEPTANCE TESTS ==============

def main() -> None:
    assert max_group_size([1, 2, 2], [3, 3, 3]) == 3
    assert max_group_size([2], [3]) == 0           # alone => k-1=0 < 2
    assert max_group_size([0, 0], [0, 0]) == 1     # any one person alone
    assert max_group_size([0, 1, 1, 1], [1, 2, 2, 2]) == 3
    assert max_group_size([5, 5, 5], [9, 9, 9]) == 0   # need 6+ people, have 3
    assert max_group_size([], []) == 0

    # brute-force cross-check
    import random
    random.seed(1)

    def brute(L, R):
        n = len(L)
        best = 0
        for k in range(1, n + 1):
            eligible = sum(1 for l, r in zip(L, R) if l <= k - 1 <= r)
            if eligible >= k:
                best = k
        return best

    for _ in range(300):
        n = random.randint(0, 14)
        L = [random.randint(0, 6) for _ in range(n)]
        R = [l + random.randint(0, 6) for l in L]
        assert max_group_size(L, R) == brute(L, R), (L, R)

    print("PASS")


if __name__ == "__main__":
    main()
