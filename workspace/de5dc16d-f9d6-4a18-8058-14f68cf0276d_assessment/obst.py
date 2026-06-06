import sys
sys.setrecursionlimit(1 << 20)


class TreeNode:
    """A node of the Binary Search Tree."""
    __slots__ = ("word", "freq", "left", "right")

    def __init__(self, word, freq):
        self.word = word
        self.freq = freq
        self.left = None
        self.right = None


def construct_optimal_bst(words, frequency):
    """
    Build the Optimal BST minimizing  sum(freq[i] * depth[i]),  depth(root)=1.
    Returns (root_node, min_total_cost).  Top-down memoization: O(n^3)/O(n^2).
    """
    n = len(words)
    if n == 0:
        return None, 0

    prefix = [0] * (n + 1)
    for i in range(n):
        prefix[i + 1] = prefix[i] + frequency[i]

    def window(i, j):
        return prefix[j + 1] - prefix[i]

    memo = {}
    root_choice = {}

    def cost(i, j):
        if i > j:
            return 0
        key = (i, j)
        if key in memo:
            return memo[key]
        w = window(i, j)
        best, best_r = float("inf"), i
        for r in range(i, j + 1):
            c = cost(i, r - 1) + cost(r + 1, j)
            if c < best:
                best, best_r = c, r
        memo[key] = best + w
        root_choice[key] = best_r
        return memo[key]

    min_cost = cost(0, n - 1)

    def build(i, j):
        if i > j:
            return None
        r = root_choice[(i, j)]
        node = TreeNode(words[r], frequency[r])
        node.left = build(i, r - 1)
        node.right = build(r + 1, j)
        return node

    return build(0, n - 1), min_cost


def tree_cost(node, depth=1):
    if node is None:
        return 0
    return (node.freq * depth
            + tree_cost(node.left, depth + 1)
            + tree_cost(node.right, depth + 1))


def pretty(node, indent="", is_right=True):
    if node is None:
        return
    pretty(node.right, indent + ("        " if is_right else "   |    "), True)
    branch = "/----- " if is_right else "\\----- "
    print(indent + branch + f"{node.word}({node.freq})")
    pretty(node.left, indent + ("   |    " if is_right else "        "), False)
