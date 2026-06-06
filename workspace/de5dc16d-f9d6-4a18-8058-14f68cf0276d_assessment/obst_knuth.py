import sys
sys.setrecursionlimit(1 << 20)


class TreeNode:
    __slots__ = ("word", "freq", "left", "right")

    def __init__(self, word, freq):
        self.word, self.freq, self.left, self.right = word, freq, None, None


def construct_optimal_bst_knuth(words, frequency):
    """
    Optimal BST via bottom-up interval DP with Knuth's monotonicity:
    the optimal root of [i..j] lies in [root[i][j-1] .. root[i+1][j]].
    Time O(n^2), Space O(n^2).
    """
    n = len(words)
    if n == 0:
        return None, 0

    prefix = [0] * (n + 1)
    for i in range(n):
        prefix[i + 1] = prefix[i] + frequency[i]

    def window(i, j):              # sum(freq[i..j]) inclusive
        return prefix[j + 1] - prefix[i]

    INF = float("inf")
    # cost[i][j], root[i][j] over inclusive interval [i..j]
    cost = [[0] * n for _ in range(n)]
    root = [[0] * n for _ in range(n)]
    for i in range(n):
        cost[i][i] = frequency[i]
        root[i][i] = i

    # length = j - i + 1, from 2..n
    for length in range(2, n + 1):
        for i in range(0, n - length + 1):
            j = i + length - 1
            w = window(i, j)
            best, best_r = INF, i
            lo = root[i][j - 1]
            hi = root[i + 1][j]
            for r in range(lo, hi + 1):
                left = cost[i][r - 1] if r > i else 0
                right = cost[r + 1][j] if r < j else 0
                c = left + right
                if c < best:
                    best, best_r = c, r
            cost[i][j] = best + w
            root[i][j] = best_r

    def build(i, j):
        if i > j:
            return None
        r = root[i][j]
        node = TreeNode(words[r], frequency[r])
        node.left = build(i, r - 1)
        node.right = build(r + 1, j)
        return node

    return build(0, n - 1), cost[0][n - 1]


def tree_cost(node, depth=1):
    if node is None:
        return 0
    return node.freq * depth + tree_cost(node.left, depth + 1) + tree_cost(node.right, depth + 1)
