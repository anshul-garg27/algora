from collections import namedtuple

class TreeNode:
    def __init__(self, val, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

class Solution:
    def lowestCommonAncestor(self, root, p, q):
        # Post-order DFS. Each call returns:
        #   - p or q if found in this subtree
        #   - the LCA if already determined below
        #   - None if neither target is here
        if root is None or root is p or root is q:
            return root
        left = self.lowestCommonAncestor(root.left, p, q)
        right = self.lowestCommonAncestor(root.right, p, q)
        if left and right:
            # p and q found on opposite sides -> this node is the LCA
            return root
        # otherwise bubble up whichever side found something (or None)
        return left if left else right


# ---------- build the example tree ----------
#            3
#          /   \
#         5     1
#        / \   / \
#       6   2 0   8
#          / \
#         7   4
def build():
    n7, n4 = TreeNode(7), TreeNode(4)
    n2 = TreeNode(2, n7, n4)
    n6 = TreeNode(6)
    n5 = TreeNode(5, n6, n2)
    n0, n8 = TreeNode(0), TreeNode(8)
    n1 = TreeNode(1, n0, n8)
    n3 = TreeNode(3, n5, n1)
    return {n.val: n for n in [n7, n4, n2, n6, n5, n0, n8, n1, n3]}, n3

nodes, root = build()
sol = Solution()

def lca(a, b):
    return sol.lowestCommonAncestor(root, nodes[a], nodes[b]).val

tests = [
    (5, 1, 3),   # meet at root
    (5, 4, 5),   # self-ancestor: 5 is ancestor of 4
    (6, 4, 5),   # split at 5
    (7, 4, 2),   # split at 2
    (6, 2, 5),   # 2 is in 5's subtree, 6 too
    (0, 8, 1),   # both under 1
    (7, 8, 3),   # opposite sides of root
    (4, 4, 4),   # p == q
]
for a, b, expected in tests:
    got = lca(a, b)
    status = "OK" if got == expected else "FAIL"
    print(f"LCA({a},{b}) = {got}  expected {expected}  [{status}]")

# single node tree edge case
solo = TreeNode(99)
print("single-node:", sol.lowestCommonAncestor(solo, solo, solo).val)
