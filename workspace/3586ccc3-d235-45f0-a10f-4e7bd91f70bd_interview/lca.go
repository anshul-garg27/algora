package main

import "fmt"

// TreeNode is the definition of a binary tree node.
type TreeNode struct {
	Val   int
	Left  *TreeNode
	Right *TreeNode
}

// lowestCommonAncestor returns the lowest common ancestor of p and q.
func lowestCommonAncestor(root, p, q *TreeNode) *TreeNode {
	// Base case: empty subtree, OR we landed exactly on a target.
	if root == nil || root == p || root == q {
		return root
	}

	// Ask both children whether they found a target.
	left := lowestCommonAncestor(root.Left, p, q)
	right := lowestCommonAncestor(root.Right, p, q)

	// One target on each side -> this node is the LCA.
	if left != nil && right != nil {
		return root
	}

	// Otherwise bubble up whichever side found something (or nil).
	if left != nil {
		return left
	}
	return right
}

func main() {
	// Build the example tree:
	//            3
	//          /   \
	//         5     1
	//        / \   / \
	//       6   2 0   8
	//          / \
	//         7   4
	n7 := &TreeNode{Val: 7}
	n4 := &TreeNode{Val: 4}
	n2 := &TreeNode{Val: 2, Left: n7, Right: n4}
	n6 := &TreeNode{Val: 6}
	n5 := &TreeNode{Val: 5, Left: n6, Right: n2}
	n0 := &TreeNode{Val: 0}
	n8 := &TreeNode{Val: 8}
	n1 := &TreeNode{Val: 1, Left: n0, Right: n8}
	root := &TreeNode{Val: 3, Left: n5, Right: n1}

	tests := []struct {
		p, q, expected *TreeNode
	}{
		{n5, n1, root}, // meet at root
		{n5, n4, n5},   // self-ancestor
		{n6, n4, n5},   // split at 5
		{n7, n4, n2},   // split at 2
		{n0, n8, n1},   // both under 1
		{n7, n8, root}, // opposite sides of root
		{n4, n4, n4},   // p == q
	}

	for _, t := range tests {
		got := lowestCommonAncestor(root, t.p, t.q)
		status := "OK"
		if got != t.expected {
			status = "FAIL"
		}
		fmt.Printf("LCA(%d,%d) = %d  expected %d  [%s]\n",
			t.p.Val, t.q.Val, got.Val, t.expected.Val, status)
	}
}
