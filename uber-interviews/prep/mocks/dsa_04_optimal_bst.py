"""
UBER DSA MOCK #4 — 45 minutes — Optimal BST (the screening killer)
====================================================================
(Asked 2x as Uber's Round-1 "Screening (DSA + System Design)" — both
candidates called it their TOUGHEST round; one passed with a memoized
solution and got the offer.)

Given n unique words sorted lexicographically and their search frequencies,
build a BST containing all words (inorder = sorted order) minimizing:

    total cost = sum over words of  frequency[word] * depth(word)

where the root has depth 1 (depth = number of comparisons to find it).

  optimal_bst_cost(freq: list[int]) -> int

Constraints: n <= 250 (so O(n^3) passes; O(2^n) does not).

Interview reality: you get ~35 minutes for this INCLUDING discussion,
because the round also wants a system-design chat. A working memoized
solution is a pass; an elegant tabulation is a flourish.
"""

# ============== YOUR IMPLEMENTATION BELOW ==============


def optimal_bst_cost(freq: list[int]) -> int:
    raise NotImplementedError


# ============== DEMO / ACCEPTANCE TESTS ==============

def main() -> None:
    assert optimal_bst_cost([34, 8, 50]) == 142       # classic
    assert optimal_bst_cost([3, 2, 4]) == 16          # the 2026 example:
    # banana root (1*2) + apple (2*3) + cherry (2*4) = 2+6+8 = 16
    assert optimal_bst_cost([10]) == 10
    assert optimal_bst_cost([1, 1]) == 3              # root + child
    assert optimal_bst_cost([25, 10, 20]) == 95       # root=0: 25+2*10+... check all shapes
    print("PASS")


if __name__ == "__main__":
    main()
