# DSA Coding Patterns -- Complete Study Guide

**For:** Anshul Garg | Backend Engineer | Google Interview Preparation
**Context:** GATE AIR 1343 (98.6 percentile) in CS. Primary language: Java, Secondary: Python. Targeting Google SDE interviews.

---

# TABLE OF CONTENTS

1. [Pattern 1: Two Pointers](#pattern-1-two-pointers)
2. [Pattern 2: Sliding Window](#pattern-2-sliding-window)
3. [Pattern 3: Binary Search](#pattern-3-binary-search)
4. [Pattern 4: BFS/DFS (Trees + Graphs)](#pattern-4-bfsdfs-trees--graphs)
5. [Pattern 5: Dynamic Programming](#pattern-5-dynamic-programming)
6. [Pattern 6: Backtracking](#pattern-6-backtracking)
7. [Pattern 7: Topological Sort](#pattern-7-topological-sort)
8. [Pattern 8: Union Find](#pattern-8-union-find)
9. [Pattern 9: Trie](#pattern-9-trie)
10. [Pattern 10: Monotonic Stack/Queue](#pattern-10-monotonic-stackqueue)
11. [Pattern 11: Heap/Priority Queue](#pattern-11-heappriority-queue)
12. [Pattern 12: Intervals](#pattern-12-intervals)
13. [Pattern 13: Linked List Manipulation](#pattern-13-linked-list-manipulation)
14. [Pattern 14: Prefix Sum](#pattern-14-prefix-sum)
15. [Pattern 15: Bit Manipulation](#pattern-15-bit-manipulation)
16. [Google-Specific Tips](#google-specific-tips)
17. [Complexity Analysis Cheat Sheet](#complexity-analysis-cheat-sheet)
18. [Common Data Structures Overview](#common-data-structures-overview)
19. [50 Must-Practice LeetCode Problems](#50-must-practice-leetcode-problems)
20. [How to Approach an Unknown Problem in 45 Minutes](#how-to-approach-an-unknown-problem-in-45-minutes)

---

# PATTERN 1: TWO POINTERS

## Concept

Two Pointers is a technique where two index variables traverse a data structure (usually a sorted array or linked list) from different positions or at different speeds. It reduces brute-force O(n^2) solutions to O(n) by eliminating redundant comparisons.

**Three main variants:**
- **Opposite-direction pointers:** One pointer starts at the beginning, the other at the end. They move toward each other. Used for pair-finding in sorted arrays, palindrome checks, container problems.
- **Same-direction pointers (fast/slow):** Both start at the beginning. One moves faster. Used for cycle detection, removing duplicates, partitioning.
- **Two-array pointers:** One pointer per array. Used for merging sorted arrays, intersection problems.

**When to use:**
- The input is sorted (or can be sorted without breaking the problem)
- You need to find a pair/triplet that satisfies a condition
- You need to compare elements from both ends
- You need in-place array manipulation

## Template Code

### Python

```python
# Variant 1: Opposite direction (e.g., Two Sum on sorted array)
def two_sum_sorted(nums: list[int], target: int) -> list[int]:
    left, right = 0, len(nums) - 1
    while left < right:
        current_sum = nums[left] + nums[right]
        if current_sum == target:
            return [left, right]
        elif current_sum < target:
            left += 1
        else:
            right -= 1
    return [-1, -1]

# Variant 2: Same direction -- remove duplicates in-place
def remove_duplicates(nums: list[int]) -> int:
    if not nums:
        return 0
    slow = 0
    for fast in range(1, len(nums)):
        if nums[fast] != nums[slow]:
            slow += 1
            nums[slow] = nums[fast]
    return slow + 1

# Variant 3: Fast/Slow for cycle detection (Floyd's)
def has_cycle(head):
    slow = fast = head
    while fast and fast.next:
        slow = slow.next
        fast = fast.next.next
        if slow == fast:
            return True
    return False
```

### Java

```java
// Variant 1: Opposite direction (Two Sum on sorted array)
public int[] twoSumSorted(int[] nums, int target) {
    int left = 0, right = nums.length - 1;
    while (left < right) {
        int currentSum = nums[left] + nums[right];
        if (currentSum == target) {
            return new int[]{left, right};
        } else if (currentSum < target) {
            left++;
        } else {
            right--;
        }
    }
    return new int[]{-1, -1};
}

// Variant 2: Same direction -- remove duplicates in-place
public int removeDuplicates(int[] nums) {
    if (nums.length == 0) return 0;
    int slow = 0;
    for (int fast = 1; fast < nums.length; fast++) {
        if (nums[fast] != nums[slow]) {
            slow++;
            nums[slow] = nums[fast];
        }
    }
    return slow + 1;
}

// Variant 3: Fast/Slow for cycle detection (Floyd's)
public boolean hasCycle(ListNode head) {
    ListNode slow = head, fast = head;
    while (fast != null && fast.next != null) {
        slow = slow.next;
        fast = fast.next.next;
        if (slow == fast) return true;
    }
    return false;
}
```

## Example Problems

| # | Problem | Difficulty | Key Idea |
|---|---------|------------|----------|
| 1 | **LC 167 -- Two Sum II (Sorted)** | Easy | Opposite pointers, shrink window based on sum comparison |
| 2 | **LC 15 -- 3Sum** | Medium | Sort + fix one element + two-pointer on remainder. Skip duplicates carefully |
| 3 | **LC 11 -- Container With Most Water** | Medium | Opposite pointers; move the shorter line inward since that is the only way to potentially increase area |
| 4 | **LC 42 -- Trapping Rain Water** | Hard | Two pointers from both ends tracking left_max and right_max; process the smaller side |
| 5 | **LC 26 -- Remove Duplicates from Sorted Array** | Easy | Slow/fast same-direction pointers |

### Detailed Walkthrough: LC 15 -- 3Sum

**Problem:** Find all unique triplets in the array that sum to zero.

```python
def three_sum(nums: list[int]) -> list[list[int]]:
    nums.sort()
    result = []
    for i in range(len(nums) - 2):
        # Skip duplicate for the first element
        if i > 0 and nums[i] == nums[i - 1]:
            continue
        left, right = i + 1, len(nums) - 1
        while left < right:
            total = nums[i] + nums[left] + nums[right]
            if total == 0:
                result.append([nums[i], nums[left], nums[right]])
                # Skip duplicates for second and third elements
                while left < right and nums[left] == nums[left + 1]:
                    left += 1
                while left < right and nums[right] == nums[right - 1]:
                    right -= 1
                left += 1
                right -= 1
            elif total < 0:
                left += 1
            else:
                right -= 1
    return result
```

```java
public List<List<Integer>> threeSum(int[] nums) {
    Arrays.sort(nums);
    List<List<Integer>> result = new ArrayList<>();
    for (int i = 0; i < nums.length - 2; i++) {
        if (i > 0 && nums[i] == nums[i - 1]) continue;
        int left = i + 1, right = nums.length - 1;
        while (left < right) {
            int total = nums[i] + nums[left] + nums[right];
            if (total == 0) {
                result.add(Arrays.asList(nums[i], nums[left], nums[right]));
                while (left < right && nums[left] == nums[left + 1]) left++;
                while (left < right && nums[right] == nums[right - 1]) right--;
                left++;
                right--;
            } else if (total < 0) {
                left++;
            } else {
                right--;
            }
        }
    }
    return result;
}
```

## Complexity

| Variant | Time | Space |
|---------|------|-------|
| Opposite direction | O(n) | O(1) |
| Same direction | O(n) | O(1) |
| 3Sum (sort + two pointer) | O(n^2) | O(1) extra (O(n) for sort) |
| Trapping Rain Water | O(n) | O(1) |

---

# PATTERN 2: SLIDING WINDOW

## Concept

Sliding Window maintains a contiguous subarray/substring window that expands or contracts to satisfy a condition. It converts nested-loop O(n*k) or O(n^2) solutions into O(n).

**Variants:**
- **Fixed-size window:** Window size k is given. Slide the window by adding one element on the right and removing one from the left.
- **Variable-size window:** Expand the window until a condition is violated, then shrink from the left until the condition is restored.
- **Window with HashMap:** Track character/element frequencies within the window using a hash map.

**When to use:**
- Problem asks for "maximum/minimum subarray/substring of size k"
- Problem asks for "longest/shortest substring with at most/at least K distinct characters"
- Problem involves contiguous sequences

## Template Code

### Python

```python
# Fixed-size sliding window
def max_sum_subarray(nums: list[int], k: int) -> int:
    window_sum = sum(nums[:k])
    max_sum = window_sum
    for i in range(k, len(nums)):
        window_sum += nums[i] - nums[i - k]
        max_sum = max(max_sum, window_sum)
    return max_sum

# Variable-size sliding window -- longest substring with at most k distinct chars
def longest_k_distinct(s: str, k: int) -> int:
    from collections import defaultdict
    char_count = defaultdict(int)
    left = 0
    max_len = 0
    for right in range(len(s)):
        char_count[s[right]] += 1
        while len(char_count) > k:
            char_count[s[left]] -= 1
            if char_count[s[left]] == 0:
                del char_count[s[left]]
            left += 1
        max_len = max(max_len, right - left + 1)
    return max_len

# Sliding window with hashmap -- minimum window substring
def min_window(s: str, t: str) -> str:
    from collections import Counter
    need = Counter(t)
    missing = len(t)
    left = 0
    start, end = 0, float('inf')

    for right, char in enumerate(s):
        if need[char] > 0:
            missing -= 1
        need[char] -= 1

        while missing == 0:  # window contains all chars of t
            if right - left < end - start:
                start, end = left, right
            need[s[left]] += 1
            if need[s[left]] > 0:
                missing += 1
            left += 1

    return s[start:end + 1] if end != float('inf') else ""
```

### Java

```java
// Fixed-size sliding window
public int maxSumSubarray(int[] nums, int k) {
    int windowSum = 0;
    for (int i = 0; i < k; i++) windowSum += nums[i];
    int maxSum = windowSum;
    for (int i = k; i < nums.length; i++) {
        windowSum += nums[i] - nums[i - k];
        maxSum = Math.max(maxSum, windowSum);
    }
    return maxSum;
}

// Variable-size sliding window -- longest substring with at most k distinct
public int longestKDistinct(String s, int k) {
    Map<Character, Integer> charCount = new HashMap<>();
    int left = 0, maxLen = 0;
    for (int right = 0; right < s.length(); right++) {
        charCount.merge(s.charAt(right), 1, Integer::sum);
        while (charCount.size() > k) {
            char leftChar = s.charAt(left);
            charCount.merge(leftChar, -1, Integer::sum);
            if (charCount.get(leftChar) == 0) charCount.remove(leftChar);
            left++;
        }
        maxLen = Math.max(maxLen, right - left + 1);
    }
    return maxLen;
}

// Minimum window substring
public String minWindow(String s, String t) {
    int[] need = new int[128];
    for (char c : t.toCharArray()) need[c]++;
    int missing = t.length();
    int left = 0, start = 0, minLen = Integer.MAX_VALUE;

    for (int right = 0; right < s.length(); right++) {
        if (need[s.charAt(right)] > 0) missing--;
        need[s.charAt(right)]--;

        while (missing == 0) {
            if (right - left + 1 < minLen) {
                minLen = right - left + 1;
                start = left;
            }
            need[s.charAt(left)]++;
            if (need[s.charAt(left)] > 0) missing++;
            left++;
        }
    }
    return minLen == Integer.MAX_VALUE ? "" : s.substring(start, start + minLen);
}
```

## Example Problems

| # | Problem | Difficulty | Key Idea |
|---|---------|------------|----------|
| 1 | **LC 209 -- Minimum Size Subarray Sum** | Medium | Variable window; shrink when sum >= target |
| 2 | **LC 3 -- Longest Substring Without Repeating Characters** | Medium | Variable window with HashSet; shrink on duplicate |
| 3 | **LC 76 -- Minimum Window Substring** | Hard | Variable window with frequency map; expand until valid, shrink to minimize |
| 4 | **LC 438 -- Find All Anagrams in a String** | Medium | Fixed-size window (size = len(p)); compare frequency maps |
| 5 | **LC 239 -- Sliding Window Maximum** | Hard | Fixed window + monotonic deque (see Pattern 10) |

## Complexity

| Variant | Time | Space |
|---------|------|-------|
| Fixed window | O(n) | O(1) |
| Variable window | O(n) | O(k) where k = distinct elements in window |
| Min window substring | O(n + m) | O(m) where m = length of target |

---

# PATTERN 3: BINARY SEARCH

## Concept

Binary Search repeatedly halves the search space by comparing the middle element against the target. It works on any monotonic predicate -- not just sorted arrays.

**Variants:**
- **Standard:** Search for an exact value in a sorted array.
- **Binary search on answer:** The answer lies in a range [lo, hi]; use a predicate to decide which half to keep. Common in "minimize the maximum" or "maximize the minimum" problems.
- **Rotated sorted array:** The array was sorted then rotated. One half is always sorted; determine which half and search accordingly.
- **Finding boundaries:** Find the first/last occurrence of a value (leftmost/rightmost binary search).

**When to use:**
- Sorted array or matrix
- "Find minimum/maximum that satisfies a condition"
- Search space can be divided in half
- O(log n) is expected

## Template Code

### Python

```python
# Standard binary search
def binary_search(nums: list[int], target: int) -> int:
    lo, hi = 0, len(nums) - 1
    while lo <= hi:
        mid = lo + (hi - lo) // 2
        if nums[mid] == target:
            return mid
        elif nums[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1

# Leftmost (first occurrence) binary search
def left_bound(nums: list[int], target: int) -> int:
    lo, hi = 0, len(nums) - 1
    result = -1
    while lo <= hi:
        mid = lo + (hi - lo) // 2
        if nums[mid] == target:
            result = mid
            hi = mid - 1  # keep searching left
        elif nums[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return result

# Binary search on answer -- minimum capacity to ship within D days (LC 1011)
def ship_within_days(weights: list[int], days: int) -> int:
    def can_ship(capacity: int) -> bool:
        current_load = 0
        trips = 1
        for w in weights:
            if current_load + w > capacity:
                trips += 1
                current_load = 0
            current_load += w
        return trips <= days

    lo, hi = max(weights), sum(weights)
    while lo < hi:
        mid = lo + (hi - lo) // 2
        if can_ship(mid):
            hi = mid
        else:
            lo = mid + 1
    return lo

# Search in rotated sorted array (LC 33)
def search_rotated(nums: list[int], target: int) -> int:
    lo, hi = 0, len(nums) - 1
    while lo <= hi:
        mid = lo + (hi - lo) // 2
        if nums[mid] == target:
            return mid
        # Left half is sorted
        if nums[lo] <= nums[mid]:
            if nums[lo] <= target < nums[mid]:
                hi = mid - 1
            else:
                lo = mid + 1
        # Right half is sorted
        else:
            if nums[mid] < target <= nums[hi]:
                lo = mid + 1
            else:
                hi = mid - 1
    return -1
```

### Java

```java
// Standard binary search
public int binarySearch(int[] nums, int target) {
    int lo = 0, hi = nums.length - 1;
    while (lo <= hi) {
        int mid = lo + (hi - lo) / 2;
        if (nums[mid] == target) return mid;
        else if (nums[mid] < target) lo = mid + 1;
        else hi = mid - 1;
    }
    return -1;
}

// Leftmost (first occurrence)
public int leftBound(int[] nums, int target) {
    int lo = 0, hi = nums.length - 1, result = -1;
    while (lo <= hi) {
        int mid = lo + (hi - lo) / 2;
        if (nums[mid] == target) {
            result = mid;
            hi = mid - 1;
        } else if (nums[mid] < target) {
            lo = mid + 1;
        } else {
            hi = mid - 1;
        }
    }
    return result;
}

// Binary search on answer -- ship within days
public int shipWithinDays(int[] weights, int days) {
    int lo = 0, hi = 0;
    for (int w : weights) {
        lo = Math.max(lo, w);
        hi += w;
    }
    while (lo < hi) {
        int mid = lo + (hi - lo) / 2;
        if (canShip(weights, mid, days)) hi = mid;
        else lo = mid + 1;
    }
    return lo;
}

private boolean canShip(int[] weights, int capacity, int days) {
    int currentLoad = 0, trips = 1;
    for (int w : weights) {
        if (currentLoad + w > capacity) {
            trips++;
            currentLoad = 0;
        }
        currentLoad += w;
    }
    return trips <= days;
}

// Search in rotated sorted array
public int searchRotated(int[] nums, int target) {
    int lo = 0, hi = nums.length - 1;
    while (lo <= hi) {
        int mid = lo + (hi - lo) / 2;
        if (nums[mid] == target) return mid;
        if (nums[lo] <= nums[mid]) {
            if (nums[lo] <= target && target < nums[mid]) hi = mid - 1;
            else lo = mid + 1;
        } else {
            if (nums[mid] < target && target <= nums[hi]) lo = mid + 1;
            else hi = mid - 1;
        }
    }
    return -1;
}
```

## Example Problems

| # | Problem | Difficulty | Key Idea |
|---|---------|------------|----------|
| 1 | **LC 704 -- Binary Search** | Easy | Standard template |
| 2 | **LC 34 -- Find First and Last Position** | Medium | Two binary searches: leftmost + rightmost |
| 3 | **LC 33 -- Search in Rotated Sorted Array** | Medium | Determine which half is sorted, then decide |
| 4 | **LC 1011 -- Capacity to Ship Packages Within D Days** | Medium | Binary search on answer with feasibility predicate |
| 5 | **LC 4 -- Median of Two Sorted Arrays** | Hard | Binary search on partition position; O(log(min(m,n))) |

## Complexity

| Variant | Time | Space |
|---------|------|-------|
| Standard | O(log n) | O(1) |
| On answer | O(n * log(search_range)) | O(1) |
| Rotated array | O(log n) | O(1) |

---

# PATTERN 4: BFS/DFS (TREES + GRAPHS)

## Concept

BFS (Breadth-First Search) explores level by level using a queue. DFS (Depth-First Search) explores as deep as possible before backtracking, using recursion or an explicit stack.

**Tree traversals (DFS variants):**
- **Preorder:** root -> left -> right (used for serialization, copying trees)
- **Inorder:** left -> root -> right (gives sorted order for BST)
- **Postorder:** left -> right -> root (used for deletion, bottom-up computation)
- **Level order (BFS):** level by level (used for level-specific operations)

**Graph traversals:**
- **BFS:** Shortest path in unweighted graphs, level-order processing
- **DFS:** Connectivity, cycle detection, topological sort, path finding
- **Cycle detection:** DFS with coloring (white/gray/black) for directed graphs; Union-Find or DFS parent tracking for undirected

## Template Code

### Python

```python
from collections import deque
from typing import Optional

class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

# BFS level-order traversal (tree)
def level_order(root: Optional[TreeNode]) -> list[list[int]]:
    if not root:
        return []
    result = []
    queue = deque([root])
    while queue:
        level_size = len(queue)
        level = []
        for _ in range(level_size):
            node = queue.popleft()
            level.append(node.val)
            if node.left:
                queue.append(node.left)
            if node.right:
                queue.append(node.right)
        result.append(level)
    return result

# DFS preorder, inorder, postorder (iterative + recursive)
def inorder_recursive(root: Optional[TreeNode]) -> list[int]:
    result = []
    def dfs(node):
        if not node:
            return
        dfs(node.left)
        result.append(node.val)
        dfs(node.right)
    dfs(root)
    return result

def inorder_iterative(root: Optional[TreeNode]) -> list[int]:
    result = []
    stack = []
    current = root
    while current or stack:
        while current:
            stack.append(current)
            current = current.left
        current = stack.pop()
        result.append(current.val)
        current = current.right
    return result

# Graph BFS -- shortest path in unweighted graph
def bfs_shortest_path(graph: dict[int, list[int]], start: int, end: int) -> int:
    if start == end:
        return 0
    visited = {start}
    queue = deque([(start, 0)])
    while queue:
        node, dist = queue.popleft()
        for neighbor in graph[node]:
            if neighbor == end:
                return dist + 1
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, dist + 1))
    return -1

# Graph DFS -- cycle detection in directed graph (3-color)
def has_cycle_directed(graph: dict[int, list[int]], n: int) -> bool:
    WHITE, GRAY, BLACK = 0, 1, 2
    color = [WHITE] * n

    def dfs(node: int) -> bool:
        color[node] = GRAY
        for neighbor in graph.get(node, []):
            if color[neighbor] == GRAY:  # back edge => cycle
                return True
            if color[neighbor] == WHITE and dfs(neighbor):
                return True
        color[node] = BLACK
        return False

    for i in range(n):
        if color[i] == WHITE:
            if dfs(i):
                return True
    return False

# Number of Islands (LC 200) -- BFS on grid
def num_islands(grid: list[list[str]]) -> int:
    if not grid:
        return 0
    rows, cols = len(grid), len(grid[0])
    count = 0

    def bfs(r, c):
        queue = deque([(r, c)])
        grid[r][c] = '0'
        while queue:
            row, col = queue.popleft()
            for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nr, nc = row + dr, col + dc
                if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == '1':
                    grid[nr][nc] = '0'
                    queue.append((nr, nc))

    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == '1':
                bfs(r, c)
                count += 1
    return count
```

### Java

```java
// BFS level-order traversal (tree)
public List<List<Integer>> levelOrder(TreeNode root) {
    List<List<Integer>> result = new ArrayList<>();
    if (root == null) return result;
    Queue<TreeNode> queue = new LinkedList<>();
    queue.offer(root);
    while (!queue.isEmpty()) {
        int levelSize = queue.size();
        List<Integer> level = new ArrayList<>();
        for (int i = 0; i < levelSize; i++) {
            TreeNode node = queue.poll();
            level.add(node.val);
            if (node.left != null) queue.offer(node.left);
            if (node.right != null) queue.offer(node.right);
        }
        result.add(level);
    }
    return result;
}

// Iterative inorder traversal
public List<Integer> inorderTraversal(TreeNode root) {
    List<Integer> result = new ArrayList<>();
    Deque<TreeNode> stack = new ArrayDeque<>();
    TreeNode current = root;
    while (current != null || !stack.isEmpty()) {
        while (current != null) {
            stack.push(current);
            current = current.left;
        }
        current = stack.pop();
        result.add(current.val);
        current = current.right;
    }
    return result;
}

// Graph BFS -- shortest path in unweighted graph
public int bfsShortestPath(Map<Integer, List<Integer>> graph, int start, int end) {
    if (start == end) return 0;
    Set<Integer> visited = new HashSet<>();
    Queue<int[]> queue = new LinkedList<>(); // {node, distance}
    queue.offer(new int[]{start, 0});
    visited.add(start);
    while (!queue.isEmpty()) {
        int[] curr = queue.poll();
        for (int neighbor : graph.getOrDefault(curr[0], List.of())) {
            if (neighbor == end) return curr[1] + 1;
            if (visited.add(neighbor)) {
                queue.offer(new int[]{neighbor, curr[1] + 1});
            }
        }
    }
    return -1;
}

// Cycle detection in directed graph (3-color DFS)
public boolean hasCycleDirected(Map<Integer, List<Integer>> graph, int n) {
    int[] color = new int[n]; // 0=WHITE, 1=GRAY, 2=BLACK
    for (int i = 0; i < n; i++) {
        if (color[i] == 0 && dfs(graph, i, color)) return true;
    }
    return false;
}

private boolean dfs(Map<Integer, List<Integer>> graph, int node, int[] color) {
    color[node] = 1;
    for (int neighbor : graph.getOrDefault(node, List.of())) {
        if (color[neighbor] == 1) return true;
        if (color[neighbor] == 0 && dfs(graph, neighbor, color)) return true;
    }
    color[node] = 2;
    return false;
}

// Number of Islands (BFS on grid)
public int numIslands(char[][] grid) {
    int rows = grid.length, cols = grid[0].length, count = 0;
    int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
    for (int r = 0; r < rows; r++) {
        for (int c = 0; c < cols; c++) {
            if (grid[r][c] == '1') {
                count++;
                Queue<int[]> queue = new LinkedList<>();
                queue.offer(new int[]{r, c});
                grid[r][c] = '0';
                while (!queue.isEmpty()) {
                    int[] cell = queue.poll();
                    for (int[] d : dirs) {
                        int nr = cell[0] + d[0], nc = cell[1] + d[1];
                        if (nr >= 0 && nr < rows && nc >= 0 && nc < cols
                            && grid[nr][nc] == '1') {
                            grid[nr][nc] = '0';
                            queue.offer(new int[]{nr, nc});
                        }
                    }
                }
            }
        }
    }
    return count;
}
```

## Example Problems

| # | Problem | Difficulty | Key Idea |
|---|---------|------------|----------|
| 1 | **LC 200 -- Number of Islands** | Medium | BFS/DFS on grid; mark visited |
| 2 | **LC 102 -- Binary Tree Level Order Traversal** | Medium | BFS with level-size loop |
| 3 | **LC 104 -- Maximum Depth of Binary Tree** | Easy | DFS recursive: 1 + max(left, right) |
| 4 | **LC 207 -- Course Schedule** | Medium | Cycle detection in directed graph (DFS or BFS/Kahn's) |
| 5 | **LC 133 -- Clone Graph** | Medium | BFS/DFS with hash map to track cloned nodes |

## Complexity

| Algorithm | Time | Space |
|-----------|------|-------|
| BFS (tree/graph) | O(V + E) | O(V) for queue |
| DFS (tree/graph) | O(V + E) | O(V) for recursion stack |
| Grid BFS/DFS | O(R * C) | O(R * C) worst case |

---

# PATTERN 5: DYNAMIC PROGRAMMING

## Concept

Dynamic Programming solves problems by breaking them into overlapping subproblems, storing results to avoid recomputation. It applies when a problem has **optimal substructure** (optimal solution contains optimal solutions to subproblems) and **overlapping subproblems** (same subproblems are solved multiple times).

**Approaches:**
- **Top-down (memoization):** Recursive with caching. Easier to think about.
- **Bottom-up (tabulation):** Iterative, fill a table from base cases. Usually more space-efficient.

**Common DP categories:**
1. **1D DP:** Fibonacci, climbing stairs, house robber, coin change
2. **2D DP:** Grid paths, edit distance, longest common subsequence
3. **Knapsack:** 0/1 knapsack, unbounded knapsack, subset sum
4. **String DP:** LCS, LIS, palindrome problems, edit distance
5. **State Machine DP:** Stock problems with cooldown, transaction limits

**Framework to solve any DP problem:**
1. Define the state: What does dp[i] (or dp[i][j]) represent?
2. Write the recurrence relation: How does dp[i] relate to smaller subproblems?
3. Identify base cases: dp[0], dp[1], etc.
4. Determine traversal order: Which cells need to be computed first?
5. Optimize space if possible: Can you reduce from 2D to 1D? From 1D to O(1)?

## Template Code

### Python

```python
# 1D DP -- Coin Change (LC 322)
def coin_change(coins: list[int], amount: int) -> int:
    dp = [float('inf')] * (amount + 1)
    dp[0] = 0
    for coin in coins:
        for x in range(coin, amount + 1):
            dp[x] = min(dp[x], dp[x - coin] + 1)
    return dp[amount] if dp[amount] != float('inf') else -1

# 2D DP -- Longest Common Subsequence (LC 1143)
def longest_common_subsequence(text1: str, text2: str) -> int:
    m, n = len(text1), len(text2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if text1[i - 1] == text2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[m][n]

# 0/1 Knapsack
def knapsack_01(weights: list[int], values: list[int], capacity: int) -> int:
    n = len(weights)
    dp = [[0] * (capacity + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for w in range(capacity + 1):
            dp[i][w] = dp[i - 1][w]  # don't take item i
            if weights[i - 1] <= w:
                dp[i][w] = max(dp[i][w], dp[i - 1][w - weights[i - 1]] + values[i - 1])
    return dp[n][capacity]

# Space-optimized 0/1 Knapsack (1D array)
def knapsack_01_optimized(weights: list[int], values: list[int], capacity: int) -> int:
    dp = [0] * (capacity + 1)
    for i in range(len(weights)):
        for w in range(capacity, weights[i] - 1, -1):  # reverse to avoid using same item twice
            dp[w] = max(dp[w], dp[w - weights[i]] + values[i])
    return dp[capacity]

# Longest Increasing Subsequence -- O(n log n) with patience sorting
def length_of_lis(nums: list[int]) -> int:
    from bisect import bisect_left
    tails = []
    for num in nums:
        pos = bisect_left(tails, num)
        if pos == len(tails):
            tails.append(num)
        else:
            tails[pos] = num
    return len(tails)

# State Machine DP -- Best Time to Buy and Sell Stock with Cooldown (LC 309)
def max_profit_cooldown(prices: list[int]) -> int:
    n = len(prices)
    if n < 2:
        return 0
    # States: hold, sold, cooldown
    hold = -prices[0]
    sold = 0
    cooldown = 0
    for i in range(1, n):
        prev_hold = hold
        prev_sold = sold
        prev_cooldown = cooldown
        hold = max(prev_hold, prev_cooldown - prices[i])
        sold = prev_hold + prices[i]
        cooldown = max(prev_cooldown, prev_sold)
    return max(sold, cooldown)
```

### Java

```java
// 1D DP -- Coin Change
public int coinChange(int[] coins, int amount) {
    int[] dp = new int[amount + 1];
    Arrays.fill(dp, amount + 1);
    dp[0] = 0;
    for (int coin : coins) {
        for (int x = coin; x <= amount; x++) {
            dp[x] = Math.min(dp[x], dp[x - coin] + 1);
        }
    }
    return dp[amount] > amount ? -1 : dp[amount];
}

// 2D DP -- Longest Common Subsequence
public int longestCommonSubsequence(String text1, String text2) {
    int m = text1.length(), n = text2.length();
    int[][] dp = new int[m + 1][n + 1];
    for (int i = 1; i <= m; i++) {
        for (int j = 1; j <= n; j++) {
            if (text1.charAt(i - 1) == text2.charAt(j - 1)) {
                dp[i][j] = dp[i - 1][j - 1] + 1;
            } else {
                dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
            }
        }
    }
    return dp[m][n];
}

// 0/1 Knapsack (space-optimized)
public int knapsack01(int[] weights, int[] values, int capacity) {
    int[] dp = new int[capacity + 1];
    for (int i = 0; i < weights.length; i++) {
        for (int w = capacity; w >= weights[i]; w--) {
            dp[w] = Math.max(dp[w], dp[w - weights[i]] + values[i]);
        }
    }
    return dp[capacity];
}

// LIS -- O(n log n)
public int lengthOfLIS(int[] nums) {
    List<Integer> tails = new ArrayList<>();
    for (int num : nums) {
        int pos = Collections.binarySearch(tails, num);
        if (pos < 0) pos = -(pos + 1);
        if (pos == tails.size()) tails.add(num);
        else tails.set(pos, num);
    }
    return tails.size();
}

// State Machine DP -- Stock with Cooldown
public int maxProfitCooldown(int[] prices) {
    if (prices.length < 2) return 0;
    int hold = -prices[0], sold = 0, cooldown = 0;
    for (int i = 1; i < prices.length; i++) {
        int prevHold = hold, prevSold = sold, prevCooldown = cooldown;
        hold = Math.max(prevHold, prevCooldown - prices[i]);
        sold = prevHold + prices[i];
        cooldown = Math.max(prevCooldown, prevSold);
    }
    return Math.max(sold, cooldown);
}
```

## Example Problems

| # | Problem | Difficulty | Key Idea |
|---|---------|------------|----------|
| 1 | **LC 322 -- Coin Change** | Medium | Unbounded knapsack; dp[x] = min coins to make x |
| 2 | **LC 1143 -- Longest Common Subsequence** | Medium | 2D DP; match characters diagonally |
| 3 | **LC 300 -- Longest Increasing Subsequence** | Medium | O(n^2) DP or O(n log n) with patience sorting |
| 4 | **LC 72 -- Edit Distance** | Medium | 2D DP; insert/delete/replace operations |
| 5 | **LC 309 -- Best Time to Buy/Sell Stock with Cooldown** | Medium | State machine: hold/sold/cooldown transitions |

## Complexity

| Type | Time | Space | Space (optimized) |
|------|------|-------|-------------------|
| 1D DP | O(n) to O(n * k) | O(n) | O(1) for some |
| 2D DP | O(m * n) | O(m * n) | O(n) with rolling array |
| 0/1 Knapsack | O(n * W) | O(n * W) | O(W) |
| LIS (optimal) | O(n log n) | O(n) | -- |

---

# PATTERN 6: BACKTRACKING

## Concept

Backtracking explores all possible solutions by building candidates incrementally and abandoning ("pruning") a candidate as soon as it is determined it cannot lead to a valid solution. It is essentially DFS on the decision tree.

**Template:**
1. Choose: Pick an option from the current choices.
2. Explore: Recurse with the choice made.
3. Unchoose: Remove the choice (backtrack) and try the next option.

**Common problem types:**
- **Permutations:** All arrangements of elements
- **Combinations:** Select k elements from n
- **Subsets:** All possible subsets (power set)
- **Constraint satisfaction:** N-Queens, Sudoku, word search

## Template Code

### Python

```python
# General backtracking template
def backtrack(result, current, choices, start):
    if is_valid_solution(current):
        result.append(current[:])  # important: append a copy
        return
    for i in range(start, len(choices)):
        if not is_valid_choice(choices[i]):
            continue
        current.append(choices[i])      # choose
        backtrack(result, current, choices, i + 1)  # explore
        current.pop()                    # unchoose

# Subsets (LC 78)
def subsets(nums: list[int]) -> list[list[int]]:
    result = []
    def backtrack(start, current):
        result.append(current[:])
        for i in range(start, len(nums)):
            current.append(nums[i])
            backtrack(i + 1, current)
            current.pop()
    backtrack(0, [])
    return result

# Permutations (LC 46)
def permutations(nums: list[int]) -> list[list[int]]:
    result = []
    def backtrack(current, remaining):
        if not remaining:
            result.append(current[:])
            return
        for i in range(len(remaining)):
            current.append(remaining[i])
            backtrack(current, remaining[:i] + remaining[i+1:])
            current.pop()
    backtrack([], nums)
    return result

# Combinations (LC 77)
def combine(n: int, k: int) -> list[list[int]]:
    result = []
    def backtrack(start, current):
        if len(current) == k:
            result.append(current[:])
            return
        # Pruning: need (k - len(current)) more elements, so stop early
        for i in range(start, n - (k - len(current)) + 2):
            current.append(i)
            backtrack(i + 1, current)
            current.pop()
    backtrack(1, [])
    return result

# N-Queens (LC 51)
def solve_n_queens(n: int) -> list[list[str]]:
    result = []
    cols = set()
    diag1 = set()  # row - col
    diag2 = set()  # row + col
    board = [['.' ] * n for _ in range(n)]

    def backtrack(row):
        if row == n:
            result.append([''.join(r) for r in board])
            return
        for col in range(n):
            if col in cols or (row - col) in diag1 or (row + col) in diag2:
                continue
            cols.add(col)
            diag1.add(row - col)
            diag2.add(row + col)
            board[row][col] = 'Q'
            backtrack(row + 1)
            board[row][col] = '.'
            cols.remove(col)
            diag1.remove(row - col)
            diag2.remove(row + col)

    backtrack(0)
    return result
```

### Java

```java
// Subsets
public List<List<Integer>> subsets(int[] nums) {
    List<List<Integer>> result = new ArrayList<>();
    backtrackSubsets(result, new ArrayList<>(), nums, 0);
    return result;
}

private void backtrackSubsets(List<List<Integer>> result, List<Integer> current,
                               int[] nums, int start) {
    result.add(new ArrayList<>(current));
    for (int i = start; i < nums.length; i++) {
        current.add(nums[i]);
        backtrackSubsets(result, current, nums, i + 1);
        current.remove(current.size() - 1);
    }
}

// Permutations
public List<List<Integer>> permute(int[] nums) {
    List<List<Integer>> result = new ArrayList<>();
    boolean[] used = new boolean[nums.length];
    backtrackPermute(result, new ArrayList<>(), nums, used);
    return result;
}

private void backtrackPermute(List<List<Integer>> result, List<Integer> current,
                               int[] nums, boolean[] used) {
    if (current.size() == nums.length) {
        result.add(new ArrayList<>(current));
        return;
    }
    for (int i = 0; i < nums.length; i++) {
        if (used[i]) continue;
        used[i] = true;
        current.add(nums[i]);
        backtrackPermute(result, current, nums, used);
        current.remove(current.size() - 1);
        used[i] = false;
    }
}

// N-Queens
public List<List<String>> solveNQueens(int n) {
    List<List<String>> result = new ArrayList<>();
    char[][] board = new char[n][n];
    for (char[] row : board) Arrays.fill(row, '.');
    Set<Integer> cols = new HashSet<>(), diag1 = new HashSet<>(), diag2 = new HashSet<>();
    backtrackQueens(result, board, 0, n, cols, diag1, diag2);
    return result;
}

private void backtrackQueens(List<List<String>> result, char[][] board, int row, int n,
                              Set<Integer> cols, Set<Integer> diag1, Set<Integer> diag2) {
    if (row == n) {
        List<String> snapshot = new ArrayList<>();
        for (char[] r : board) snapshot.add(new String(r));
        result.add(snapshot);
        return;
    }
    for (int col = 0; col < n; col++) {
        if (cols.contains(col) || diag1.contains(row - col) || diag2.contains(row + col))
            continue;
        cols.add(col); diag1.add(row - col); diag2.add(row + col);
        board[row][col] = 'Q';
        backtrackQueens(result, board, row + 1, n, cols, diag1, diag2);
        board[row][col] = '.';
        cols.remove(col); diag1.remove(row - col); diag2.remove(row + col);
    }
}
```

## Example Problems

| # | Problem | Difficulty | Key Idea |
|---|---------|------------|----------|
| 1 | **LC 78 -- Subsets** | Medium | Include/exclude each element |
| 2 | **LC 46 -- Permutations** | Medium | Use visited array, build all orderings |
| 3 | **LC 77 -- Combinations** | Medium | Choose k from n, prune early |
| 4 | **LC 51 -- N-Queens** | Hard | Place queens row-by-row, track column/diagonal conflicts |
| 5 | **LC 37 -- Sudoku Solver** | Hard | Try digits 1-9 in each empty cell, validate and backtrack |

## Complexity

| Problem | Time | Space |
|---------|------|-------|
| Subsets | O(2^n) | O(n) recursion depth |
| Permutations | O(n!) | O(n) |
| Combinations (n choose k) | O(C(n,k)) | O(k) |
| N-Queens | O(n!) | O(n) |

---

# PATTERN 7: TOPOLOGICAL SORT

## Concept

Topological sort produces a linear ordering of vertices in a DAG (Directed Acyclic Graph) such that for every directed edge u->v, u comes before v. It is used for dependency resolution, build systems, course scheduling, and task ordering.

**Two approaches:**
1. **Kahn's Algorithm (BFS):** Maintain in-degree count; start with nodes having in-degree 0; remove them and reduce neighbors' in-degree. If all nodes are processed, no cycle.
2. **DFS-based:** Perform DFS and push nodes to a stack upon completion (post-order). The reverse of the stack is the topological order.

**Cycle detection:** If Kahn's algorithm processes fewer than n nodes, the graph has a cycle. For DFS, a back edge (visiting a GRAY node) indicates a cycle.

## Template Code

### Python

```python
from collections import deque, defaultdict

# Kahn's Algorithm (BFS-based topological sort)
def topological_sort_kahn(num_nodes: int, edges: list[list[int]]) -> list[int]:
    graph = defaultdict(list)
    in_degree = [0] * num_nodes
    for u, v in edges:
        graph[u].append(v)
        in_degree[v] += 1

    queue = deque([i for i in range(num_nodes) if in_degree[i] == 0])
    order = []

    while queue:
        node = queue.popleft()
        order.append(node)
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(order) != num_nodes:
        return []  # cycle detected
    return order

# DFS-based topological sort
def topological_sort_dfs(num_nodes: int, edges: list[list[int]]) -> list[int]:
    graph = defaultdict(list)
    for u, v in edges:
        graph[u].append(v)

    WHITE, GRAY, BLACK = 0, 1, 2
    color = [WHITE] * num_nodes
    order = []
    has_cycle = False

    def dfs(node):
        nonlocal has_cycle
        if has_cycle:
            return
        color[node] = GRAY
        for neighbor in graph[node]:
            if color[neighbor] == GRAY:
                has_cycle = True
                return
            if color[neighbor] == WHITE:
                dfs(neighbor)
        color[node] = BLACK
        order.append(node)

    for i in range(num_nodes):
        if color[i] == WHITE:
            dfs(i)

    if has_cycle:
        return []
    return order[::-1]
```

### Java

```java
// Kahn's Algorithm (BFS-based)
public int[] topologicalSortKahn(int numNodes, int[][] edges) {
    List<List<Integer>> graph = new ArrayList<>();
    int[] inDegree = new int[numNodes];
    for (int i = 0; i < numNodes; i++) graph.add(new ArrayList<>());
    for (int[] edge : edges) {
        graph.get(edge[0]).add(edge[1]);
        inDegree[edge[1]]++;
    }

    Queue<Integer> queue = new LinkedList<>();
    for (int i = 0; i < numNodes; i++) {
        if (inDegree[i] == 0) queue.offer(i);
    }

    int[] order = new int[numNodes];
    int idx = 0;
    while (!queue.isEmpty()) {
        int node = queue.poll();
        order[idx++] = node;
        for (int neighbor : graph.get(node)) {
            if (--inDegree[neighbor] == 0) queue.offer(neighbor);
        }
    }

    return idx == numNodes ? order : new int[0]; // empty = cycle
}

// DFS-based topological sort
public int[] topologicalSortDFS(int numNodes, int[][] edges) {
    List<List<Integer>> graph = new ArrayList<>();
    for (int i = 0; i < numNodes; i++) graph.add(new ArrayList<>());
    for (int[] edge : edges) graph.get(edge[0]).add(edge[1]);

    int[] color = new int[numNodes]; // 0=WHITE, 1=GRAY, 2=BLACK
    Deque<Integer> stack = new ArrayDeque<>();
    boolean[] hasCycle = {false};

    for (int i = 0; i < numNodes; i++) {
        if (color[i] == 0) dfsTopoSort(graph, i, color, stack, hasCycle);
    }

    if (hasCycle[0]) return new int[0];
    int[] order = new int[numNodes];
    for (int i = 0; i < numNodes; i++) order[i] = stack.pop();
    return order;
}

private void dfsTopoSort(List<List<Integer>> graph, int node, int[] color,
                          Deque<Integer> stack, boolean[] hasCycle) {
    if (hasCycle[0]) return;
    color[node] = 1;
    for (int neighbor : graph.get(node)) {
        if (color[neighbor] == 1) { hasCycle[0] = true; return; }
        if (color[neighbor] == 0) dfsTopoSort(graph, neighbor, color, stack, hasCycle);
    }
    color[node] = 2;
    stack.push(node);
}
```

## Example Problems

| # | Problem | Difficulty | Key Idea |
|---|---------|------------|----------|
| 1 | **LC 207 -- Course Schedule** | Medium | Detect cycle in directed graph using topological sort |
| 2 | **LC 210 -- Course Schedule II** | Medium | Return the topological ordering (or empty if cycle) |
| 3 | **LC 269 -- Alien Dictionary** | Hard | Build graph from lexicographic ordering, then topological sort |

## Complexity

| Algorithm | Time | Space |
|-----------|------|-------|
| Kahn's (BFS) | O(V + E) | O(V + E) |
| DFS-based | O(V + E) | O(V + E) |

---

# PATTERN 8: UNION FIND

## Concept

Union-Find (Disjoint Set Union, DSU) maintains a collection of disjoint sets with near-constant time union and find operations. It answers the question "are these two elements in the same group?" and supports merging groups.

**Key optimizations:**
- **Path compression:** During find(), make every node on the path point directly to the root. Flattens the tree.
- **Union by rank (or size):** Always attach the smaller tree under the root of the larger tree. Keeps trees shallow.

With both optimizations, amortized time per operation is O(alpha(n)), where alpha is the inverse Ackermann function -- effectively O(1) for all practical purposes.

## Template Code

### Python

```python
class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n
        self.count = n  # number of connected components

    def find(self, x: int) -> int:
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])  # path compression
        return self.parent[x]

    def union(self, x: int, y: int) -> bool:
        px, py = self.find(x), self.find(y)
        if px == py:
            return False  # already in same set
        # Union by rank
        if self.rank[px] < self.rank[py]:
            px, py = py, px
        self.parent[py] = px
        if self.rank[px] == self.rank[py]:
            self.rank[px] += 1
        self.count -= 1
        return True

    def connected(self, x: int, y: int) -> bool:
        return self.find(x) == self.find(y)
```

### Java

```java
class UnionFind {
    private int[] parent;
    private int[] rank;
    private int count;

    public UnionFind(int n) {
        parent = new int[n];
        rank = new int[n];
        count = n;
        for (int i = 0; i < n; i++) parent[i] = i;
    }

    public int find(int x) {
        if (parent[x] != x) {
            parent[x] = find(parent[x]); // path compression
        }
        return parent[x];
    }

    public boolean union(int x, int y) {
        int px = find(x), py = find(y);
        if (px == py) return false;
        // Union by rank
        if (rank[px] < rank[py]) { int temp = px; px = py; py = temp; }
        parent[py] = px;
        if (rank[px] == rank[py]) rank[px]++;
        count--;
        return true;
    }

    public boolean connected(int x, int y) {
        return find(x) == find(y);
    }

    public int getCount() { return count; }
}
```

## Example Problems

| # | Problem | Difficulty | Key Idea |
|---|---------|------------|----------|
| 1 | **LC 200 -- Number of Islands** | Medium | Union adjacent land cells; count = components of land |
| 2 | **LC 547 -- Number of Provinces** | Medium | Union connected cities; answer = number of components |
| 3 | **LC 684 -- Redundant Connection** | Medium | Add edges one by one; the edge that connects two already-connected nodes is redundant |
| 4 | **LC 721 -- Accounts Merge** | Medium | Union accounts that share an email |
| 5 | **LC 1135 -- Connecting Cities With Minimum Cost** | Medium | Kruskal's MST: sort edges by cost, union greedily |

## Complexity

| Operation | Time (amortized) | Space |
|-----------|-----------------|-------|
| find | O(alpha(n)) ~ O(1) | O(n) |
| union | O(alpha(n)) ~ O(1) | O(n) |
| Initialization | O(n) | O(n) |

---

# PATTERN 9: TRIE

## Concept

A Trie (prefix tree) is a tree-like data structure for efficient storage and retrieval of strings. Each node represents a character, and paths from root to nodes represent prefixes. It is used for autocomplete, spell checking, IP routing, and word games.

**Key operations:**
- **Insert:** O(m) where m is the word length
- **Search:** O(m) exact match
- **Prefix search (startsWith):** O(m) check if any word has the given prefix

## Template Code

### Python

```python
class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end = False

class Trie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word: str) -> None:
        node = self.root
        for char in word:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.is_end = True

    def search(self, word: str) -> bool:
        node = self._find_node(word)
        return node is not None and node.is_end

    def starts_with(self, prefix: str) -> bool:
        return self._find_node(prefix) is not None

    def _find_node(self, prefix: str):
        node = self.root
        for char in prefix:
            if char not in node.children:
                return None
            node = node.children[char]
        return node
```

### Java

```java
class Trie {
    private TrieNode root;

    class TrieNode {
        TrieNode[] children = new TrieNode[26];
        boolean isEnd = false;
    }

    public Trie() {
        root = new TrieNode();
    }

    public void insert(String word) {
        TrieNode node = root;
        for (char c : word.toCharArray()) {
            int idx = c - 'a';
            if (node.children[idx] == null) {
                node.children[idx] = new TrieNode();
            }
            node = node.children[idx];
        }
        node.isEnd = true;
    }

    public boolean search(String word) {
        TrieNode node = findNode(word);
        return node != null && node.isEnd;
    }

    public boolean startsWith(String prefix) {
        return findNode(prefix) != null;
    }

    private TrieNode findNode(String prefix) {
        TrieNode node = root;
        for (char c : prefix.toCharArray()) {
            int idx = c - 'a';
            if (node.children[idx] == null) return null;
            node = node.children[idx];
        }
        return node;
    }
}
```

## Example Problems

| # | Problem | Difficulty | Key Idea |
|---|---------|------------|----------|
| 1 | **LC 208 -- Implement Trie** | Medium | Standard insert/search/startsWith |
| 2 | **LC 212 -- Word Search II** | Hard | Trie + backtracking on grid; prune branches after finding words |
| 3 | **LC 211 -- Design Add and Search Words** | Medium | Trie with DFS for wildcard '.' matching |

## Complexity

| Operation | Time | Space |
|-----------|------|-------|
| Insert | O(m) | O(m) per word |
| Search | O(m) | O(1) |
| StartsWith | O(m) | O(1) |
| Total space | -- | O(ALPHABET * m * n) worst case |

---

# PATTERN 10: MONOTONIC STACK/QUEUE

## Concept

A **monotonic stack** maintains elements in increasing or decreasing order. When a new element arrives, pop all elements that violate the monotonic property. This efficiently solves "next greater/smaller element" problems in O(n).

A **monotonic deque** extends this idea to sliding windows, maintaining the window maximum or minimum in O(1) amortized per operation.

**When to use:**
- "Next greater element" / "next smaller element"
- "Previous greater/smaller element"
- "Sliding window maximum/minimum"
- Histogram / trapping rain water problems

## Template Code

### Python

```python
from collections import deque

# Next Greater Element -- returns array where result[i] = next element > nums[i]
def next_greater_element(nums: list[int]) -> list[int]:
    n = len(nums)
    result = [-1] * n
    stack = []  # stores indices, monotonically decreasing values
    for i in range(n):
        while stack and nums[stack[-1]] < nums[i]:
            idx = stack.pop()
            result[idx] = nums[i]
        stack.append(i)
    return result

# Sliding Window Maximum (LC 239)
def max_sliding_window(nums: list[int], k: int) -> list[int]:
    dq = deque()  # stores indices, monotonically decreasing values
    result = []
    for i in range(len(nums)):
        # Remove indices outside the window
        while dq and dq[0] < i - k + 1:
            dq.popleft()
        # Remove smaller elements from the back
        while dq and nums[dq[-1]] < nums[i]:
            dq.pop()
        dq.append(i)
        if i >= k - 1:
            result.append(nums[dq[0]])
    return result

# Largest Rectangle in Histogram (LC 84)
def largest_rectangle_histogram(heights: list[int]) -> int:
    stack = []  # monotonically increasing heights (store indices)
    max_area = 0
    for i, h in enumerate(heights):
        start = i
        while stack and stack[-1][1] > h:
            idx, height = stack.pop()
            max_area = max(max_area, height * (i - idx))
            start = idx
        stack.append((start, h))
    for idx, height in stack:
        max_area = max(max_area, height * (len(heights) - idx))
    return max_area
```

### Java

```java
// Next Greater Element
public int[] nextGreaterElement(int[] nums) {
    int n = nums.length;
    int[] result = new int[n];
    Arrays.fill(result, -1);
    Deque<Integer> stack = new ArrayDeque<>();
    for (int i = 0; i < n; i++) {
        while (!stack.isEmpty() && nums[stack.peek()] < nums[i]) {
            result[stack.pop()] = nums[i];
        }
        stack.push(i);
    }
    return result;
}

// Sliding Window Maximum
public int[] maxSlidingWindow(int[] nums, int k) {
    Deque<Integer> dq = new ArrayDeque<>();
    int[] result = new int[nums.length - k + 1];
    int ri = 0;
    for (int i = 0; i < nums.length; i++) {
        while (!dq.isEmpty() && dq.peekFirst() < i - k + 1) dq.pollFirst();
        while (!dq.isEmpty() && nums[dq.peekLast()] < nums[i]) dq.pollLast();
        dq.offerLast(i);
        if (i >= k - 1) result[ri++] = nums[dq.peekFirst()];
    }
    return result;
}

// Largest Rectangle in Histogram
public int largestRectangleArea(int[] heights) {
    Deque<Integer> stack = new ArrayDeque<>();
    int maxArea = 0;
    for (int i = 0; i <= heights.length; i++) {
        int h = (i == heights.length) ? 0 : heights[i];
        while (!stack.isEmpty() && heights[stack.peek()] > h) {
            int height = heights[stack.pop()];
            int width = stack.isEmpty() ? i : i - stack.peek() - 1;
            maxArea = Math.max(maxArea, height * width);
        }
        stack.push(i);
    }
    return maxArea;
}
```

## Example Problems

| # | Problem | Difficulty | Key Idea |
|---|---------|------------|----------|
| 1 | **LC 496 -- Next Greater Element I** | Easy | Monotonic stack; map from value to next greater |
| 2 | **LC 239 -- Sliding Window Maximum** | Hard | Monotonic deque; front = current max |
| 3 | **LC 84 -- Largest Rectangle in Histogram** | Hard | Monotonic increasing stack; pop and compute area when smaller bar arrives |

## Complexity

| Problem | Time | Space |
|---------|------|-------|
| Next Greater Element | O(n) | O(n) |
| Sliding Window Maximum | O(n) | O(k) |
| Largest Rectangle | O(n) | O(n) |

---

# PATTERN 11: HEAP/PRIORITY QUEUE

## Concept

A heap (priority queue) gives O(1) access to the min or max element and O(log n) insertion and removal. It is the go-to data structure for "top K", "K-th largest", "merge K sorted lists", and "running median" problems.

**Key insight:** For "K largest" elements, use a **min-heap of size K**. For "K smallest" elements, use a **max-heap of size K**.

## Template Code

### Python

```python
import heapq

# Top K Frequent Elements (LC 347)
def top_k_frequent(nums: list[int], k: int) -> list[int]:
    from collections import Counter
    count = Counter(nums)
    # heapq is a min-heap; use nlargest for top-K
    return [item for item, freq in count.most_common(k)]

    # Alternative with explicit heap:
    # min_heap = []
    # for num, freq in count.items():
    #     heapq.heappush(min_heap, (freq, num))
    #     if len(min_heap) > k:
    #         heapq.heappop(min_heap)
    # return [num for freq, num in min_heap]

# Merge K Sorted Lists (LC 23)
def merge_k_lists(lists):
    heap = []
    for i, lst in enumerate(lists):
        if lst:
            heapq.heappush(heap, (lst.val, i, lst))
    dummy = current = ListNode(0)
    while heap:
        val, i, node = heapq.heappop(heap)
        current.next = node
        current = current.next
        if node.next:
            heapq.heappush(heap, (node.next.val, i, node.next))
    return dummy.next

# Find Median from Data Stream (LC 295)
class MedianFinder:
    def __init__(self):
        self.small = []  # max-heap (negate values)
        self.large = []  # min-heap

    def add_num(self, num: int) -> None:
        heapq.heappush(self.small, -num)
        # Ensure max of small <= min of large
        heapq.heappush(self.large, -heapq.heappop(self.small))
        # Balance sizes: small can have at most 1 more element
        if len(self.large) > len(self.small):
            heapq.heappush(self.small, -heapq.heappop(self.large))

    def find_median(self) -> float:
        if len(self.small) > len(self.large):
            return -self.small[0]
        return (-self.small[0] + self.large[0]) / 2.0
```

### Java

```java
// Top K Frequent Elements
public int[] topKFrequent(int[] nums, int k) {
    Map<Integer, Integer> count = new HashMap<>();
    for (int num : nums) count.merge(num, 1, Integer::sum);

    PriorityQueue<int[]> minHeap = new PriorityQueue<>((a, b) -> a[1] - b[1]);
    for (var entry : count.entrySet()) {
        minHeap.offer(new int[]{entry.getKey(), entry.getValue()});
        if (minHeap.size() > k) minHeap.poll();
    }

    int[] result = new int[k];
    for (int i = 0; i < k; i++) result[i] = minHeap.poll()[0];
    return result;
}

// Merge K Sorted Lists
public ListNode mergeKLists(ListNode[] lists) {
    PriorityQueue<ListNode> heap = new PriorityQueue<>((a, b) -> a.val - b.val);
    for (ListNode node : lists) {
        if (node != null) heap.offer(node);
    }
    ListNode dummy = new ListNode(0), current = dummy;
    while (!heap.isEmpty()) {
        ListNode node = heap.poll();
        current.next = node;
        current = current.next;
        if (node.next != null) heap.offer(node.next);
    }
    return dummy.next;
}

// Find Median from Data Stream
class MedianFinder {
    private PriorityQueue<Integer> small; // max-heap
    private PriorityQueue<Integer> large; // min-heap

    public MedianFinder() {
        small = new PriorityQueue<>(Collections.reverseOrder());
        large = new PriorityQueue<>();
    }

    public void addNum(int num) {
        small.offer(num);
        large.offer(small.poll());
        if (large.size() > small.size()) {
            small.offer(large.poll());
        }
    }

    public double findMedian() {
        if (small.size() > large.size()) return small.peek();
        return (small.peek() + large.peek()) / 2.0;
    }
}
```

## Example Problems

| # | Problem | Difficulty | Key Idea |
|---|---------|------------|----------|
| 1 | **LC 347 -- Top K Frequent Elements** | Medium | Min-heap of size K by frequency |
| 2 | **LC 23 -- Merge K Sorted Lists** | Hard | Min-heap of K list heads; pop min, push its next |
| 3 | **LC 295 -- Find Median from Data Stream** | Hard | Two heaps: max-heap for lower half, min-heap for upper half |
| 4 | **LC 215 -- Kth Largest Element** | Medium | Min-heap of size K or Quickselect O(n) average |
| 5 | **LC 973 -- K Closest Points to Origin** | Medium | Max-heap of size K by distance |

## Complexity

| Operation | Time | Space |
|-----------|------|-------|
| Insert | O(log n) | O(n) |
| Extract min/max | O(log n) | -- |
| Peek min/max | O(1) | -- |
| Top K (using heap) | O(n log k) | O(k) |
| Merge K sorted | O(N log k) | O(k) |
| Median finder | O(log n) per add, O(1) find | O(n) |

---

# PATTERN 12: INTERVALS

## Concept

Interval problems deal with ranges [start, end]. The key insight is usually to **sort intervals by start time** (or sometimes end time), then process them with a sweep or merge approach.

**Common operations:**
- **Merge overlapping intervals:** Sort by start, merge if current.start <= prev.end
- **Insert interval:** Find the position, merge any overlapping
- **Meeting rooms:** Sort by start for overlap check, or use min-heap by end time for room count

## Template Code

### Python

```python
# Merge Intervals (LC 56)
def merge_intervals(intervals: list[list[int]]) -> list[list[int]]:
    intervals.sort(key=lambda x: x[0])
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged

# Insert Interval (LC 57)
def insert_interval(intervals: list[list[int]], new: list[int]) -> list[list[int]]:
    result = []
    i = 0
    n = len(intervals)
    # Add all intervals that end before new starts
    while i < n and intervals[i][1] < new[0]:
        result.append(intervals[i])
        i += 1
    # Merge all overlapping intervals with new
    while i < n and intervals[i][0] <= new[1]:
        new[0] = min(new[0], intervals[i][0])
        new[1] = max(new[1], intervals[i][1])
        i += 1
    result.append(new)
    # Add remaining
    while i < n:
        result.append(intervals[i])
        i += 1
    return result

# Meeting Rooms II -- minimum rooms needed (LC 253)
def min_meeting_rooms(intervals: list[list[int]]) -> int:
    import heapq
    intervals.sort(key=lambda x: x[0])
    heap = []  # end times of ongoing meetings
    for start, end in intervals:
        if heap and heap[0] <= start:
            heapq.heappop(heap)  # reuse room
        heapq.heappush(heap, end)
    return len(heap)
```

### Java

```java
// Merge Intervals
public int[][] merge(int[][] intervals) {
    Arrays.sort(intervals, (a, b) -> a[0] - b[0]);
    List<int[]> merged = new ArrayList<>();
    merged.add(intervals[0]);
    for (int i = 1; i < intervals.length; i++) {
        int[] last = merged.get(merged.size() - 1);
        if (intervals[i][0] <= last[1]) {
            last[1] = Math.max(last[1], intervals[i][1]);
        } else {
            merged.add(intervals[i]);
        }
    }
    return merged.toArray(new int[0][]);
}

// Insert Interval
public int[][] insert(int[][] intervals, int[] newInterval) {
    List<int[]> result = new ArrayList<>();
    int i = 0, n = intervals.length;
    while (i < n && intervals[i][1] < newInterval[0]) result.add(intervals[i++]);
    while (i < n && intervals[i][0] <= newInterval[1]) {
        newInterval[0] = Math.min(newInterval[0], intervals[i][0]);
        newInterval[1] = Math.max(newInterval[1], intervals[i][1]);
        i++;
    }
    result.add(newInterval);
    while (i < n) result.add(intervals[i++]);
    return result.toArray(new int[0][]);
}

// Meeting Rooms II
public int minMeetingRooms(int[][] intervals) {
    Arrays.sort(intervals, (a, b) -> a[0] - b[0]);
    PriorityQueue<Integer> heap = new PriorityQueue<>();
    for (int[] interval : intervals) {
        if (!heap.isEmpty() && heap.peek() <= interval[0]) heap.poll();
        heap.offer(interval[1]);
    }
    return heap.size();
}
```

## Example Problems

| # | Problem | Difficulty | Key Idea |
|---|---------|------------|----------|
| 1 | **LC 56 -- Merge Intervals** | Medium | Sort by start, merge overlapping |
| 2 | **LC 57 -- Insert Interval** | Medium | Three-phase: before, overlap, after |
| 3 | **LC 253 -- Meeting Rooms II** | Medium | Min-heap of end times; heap size = rooms needed |

## Complexity

| Problem | Time | Space |
|---------|------|-------|
| Merge Intervals | O(n log n) | O(n) |
| Insert Interval | O(n) | O(n) |
| Meeting Rooms II | O(n log n) | O(n) |

---

# PATTERN 13: LINKED LIST MANIPULATION

## Concept

Linked list problems test pointer manipulation skills. Key techniques include using a **dummy head node** (simplifies edge cases), **two-pointer (fast/slow)** for cycle detection and finding the middle, and **iterative reversal** of links.

## Template Code

### Python

```python
class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next

# Reverse a linked list (iterative)
def reverse_list(head: ListNode) -> ListNode:
    prev = None
    current = head
    while current:
        next_node = current.next
        current.next = prev
        prev = current
        current = next_node
    return prev

# Detect cycle and find cycle start (Floyd's with entry point)
def detect_cycle(head: ListNode) -> ListNode:
    slow = fast = head
    while fast and fast.next:
        slow = slow.next
        fast = fast.next.next
        if slow == fast:
            # Find entry point
            slow = head
            while slow != fast:
                slow = slow.next
                fast = fast.next
            return slow
    return None

# Merge two sorted linked lists
def merge_two_lists(l1: ListNode, l2: ListNode) -> ListNode:
    dummy = ListNode(0)
    current = dummy
    while l1 and l2:
        if l1.val <= l2.val:
            current.next = l1
            l1 = l1.next
        else:
            current.next = l2
            l2 = l2.next
        current = current.next
    current.next = l1 or l2
    return dummy.next

# Find middle of linked list (slow/fast)
def find_middle(head: ListNode) -> ListNode:
    slow = fast = head
    while fast and fast.next:
        slow = slow.next
        fast = fast.next.next
    return slow
```

### Java

```java
// Reverse linked list (iterative)
public ListNode reverseList(ListNode head) {
    ListNode prev = null, current = head;
    while (current != null) {
        ListNode next = current.next;
        current.next = prev;
        prev = current;
        current = next;
    }
    return prev;
}

// Detect cycle entry point
public ListNode detectCycle(ListNode head) {
    ListNode slow = head, fast = head;
    while (fast != null && fast.next != null) {
        slow = slow.next;
        fast = fast.next.next;
        if (slow == fast) {
            slow = head;
            while (slow != fast) {
                slow = slow.next;
                fast = fast.next;
            }
            return slow;
        }
    }
    return null;
}

// Merge two sorted lists
public ListNode mergeTwoLists(ListNode l1, ListNode l2) {
    ListNode dummy = new ListNode(0), current = dummy;
    while (l1 != null && l2 != null) {
        if (l1.val <= l2.val) {
            current.next = l1;
            l1 = l1.next;
        } else {
            current.next = l2;
            l2 = l2.next;
        }
        current = current.next;
    }
    current.next = (l1 != null) ? l1 : l2;
    return dummy.next;
}

// Find middle
public ListNode findMiddle(ListNode head) {
    ListNode slow = head, fast = head;
    while (fast != null && fast.next != null) {
        slow = slow.next;
        fast = fast.next.next;
    }
    return slow;
}
```

## Example Problems

| # | Problem | Difficulty | Key Idea |
|---|---------|------------|----------|
| 1 | **LC 206 -- Reverse Linked List** | Easy | Iterative: prev/current/next pointer swap |
| 2 | **LC 142 -- Linked List Cycle II** | Medium | Floyd's: find meeting point, then entry point |
| 3 | **LC 21 -- Merge Two Sorted Lists** | Easy | Dummy head + compare and link |

## Complexity

| Operation | Time | Space |
|-----------|------|-------|
| Reverse | O(n) | O(1) |
| Cycle detection | O(n) | O(1) |
| Merge two sorted | O(n + m) | O(1) |
| Find middle | O(n) | O(1) |

---

# PATTERN 14: PREFIX SUM

## Concept

Prefix sum precomputes cumulative sums so that any range sum query can be answered in O(1). The prefix sum array is defined as: `prefix[i] = nums[0] + nums[1] + ... + nums[i-1]`. Then `sum(nums[i..j]) = prefix[j+1] - prefix[i]`.

**Key extension:** For "subarray sum equals K," use a hash map to store prefix sum frequencies. If `prefix[j] - prefix[i] == k`, then `prefix[i] == prefix[j] - k`. Count occurrences with the hash map.

## Template Code

### Python

```python
# Range Sum Query (LC 303)
class NumArray:
    def __init__(self, nums: list[int]):
        self.prefix = [0] * (len(nums) + 1)
        for i in range(len(nums)):
            self.prefix[i + 1] = self.prefix[i] + nums[i]

    def sum_range(self, left: int, right: int) -> int:
        return self.prefix[right + 1] - self.prefix[left]

# Subarray Sum Equals K (LC 560)
def subarray_sum(nums: list[int], k: int) -> int:
    count = 0
    prefix_sum = 0
    prefix_map = {0: 1}  # base case: empty prefix
    for num in nums:
        prefix_sum += num
        if prefix_sum - k in prefix_map:
            count += prefix_map[prefix_sum - k]
        prefix_map[prefix_sum] = prefix_map.get(prefix_sum, 0) + 1
    return count

# Product of Array Except Self (LC 238)
def product_except_self(nums: list[int]) -> list[int]:
    n = len(nums)
    result = [1] * n
    # Left prefix product
    left_product = 1
    for i in range(n):
        result[i] = left_product
        left_product *= nums[i]
    # Right prefix product
    right_product = 1
    for i in range(n - 1, -1, -1):
        result[i] *= right_product
        right_product *= nums[i]
    return result
```

### Java

```java
// Range Sum Query
class NumArray {
    private int[] prefix;

    public NumArray(int[] nums) {
        prefix = new int[nums.length + 1];
        for (int i = 0; i < nums.length; i++) {
            prefix[i + 1] = prefix[i] + nums[i];
        }
    }

    public int sumRange(int left, int right) {
        return prefix[right + 1] - prefix[left];
    }
}

// Subarray Sum Equals K
public int subarraySum(int[] nums, int k) {
    int count = 0, prefixSum = 0;
    Map<Integer, Integer> prefixMap = new HashMap<>();
    prefixMap.put(0, 1);
    for (int num : nums) {
        prefixSum += num;
        count += prefixMap.getOrDefault(prefixSum - k, 0);
        prefixMap.merge(prefixSum, 1, Integer::sum);
    }
    return count;
}

// Product of Array Except Self
public int[] productExceptSelf(int[] nums) {
    int n = nums.length;
    int[] result = new int[n];
    result[0] = 1;
    for (int i = 1; i < n; i++) result[i] = result[i - 1] * nums[i - 1];
    int rightProduct = 1;
    for (int i = n - 1; i >= 0; i--) {
        result[i] *= rightProduct;
        rightProduct *= nums[i];
    }
    return result;
}
```

## Example Problems

| # | Problem | Difficulty | Key Idea |
|---|---------|------------|----------|
| 1 | **LC 303 -- Range Sum Query** | Easy | Build prefix sum array; answer in O(1) |
| 2 | **LC 560 -- Subarray Sum Equals K** | Medium | Prefix sum + hash map for frequency |
| 3 | **LC 238 -- Product of Array Except Self** | Medium | Left prefix product + right prefix product |

## Complexity

| Operation | Time | Space |
|-----------|------|-------|
| Build prefix sum | O(n) | O(n) |
| Range sum query | O(1) | -- |
| Subarray sum = K | O(n) | O(n) |
| Product except self | O(n) | O(1) extra (output not counted) |

---

# PATTERN 15: BIT MANIPULATION

## Concept

Bit manipulation operates directly on binary representations of integers. It is extremely fast (single CPU cycle per operation) and often provides O(1) space solutions.

**Essential operations:**
- `x & 1` -- check if x is odd
- `x >> 1` -- divide by 2
- `x << 1` -- multiply by 2
- `x & (x - 1)` -- turn off the lowest set bit (used to count bits)
- `x ^ x = 0` -- XOR of a number with itself is 0
- `x ^ 0 = x` -- XOR with 0 is identity
- `~x` -- bitwise NOT (flips all bits)

**Key insight for "single number" problems:** XOR all elements. Pairs cancel out (a ^ a = 0), leaving only the unique element.

## Template Code

### Python

```python
# Single Number (LC 136) -- find element appearing once; all others appear twice
def single_number(nums: list[int]) -> int:
    result = 0
    for num in nums:
        result ^= num
    return result

# Counting Bits (LC 338) -- number of 1-bits for each number 0..n
def count_bits(n: int) -> list[int]:
    dp = [0] * (n + 1)
    for i in range(1, n + 1):
        dp[i] = dp[i >> 1] + (i & 1)
    return dp

# Power of Two (LC 231)
def is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0

# Number of 1 Bits (LC 191)
def hamming_weight(n: int) -> int:
    count = 0
    while n:
        n &= (n - 1)  # turn off lowest set bit
        count += 1
    return count

# Reverse Bits (LC 190)
def reverse_bits(n: int) -> int:
    result = 0
    for _ in range(32):
        result = (result << 1) | (n & 1)
        n >>= 1
    return result
```

### Java

```java
// Single Number
public int singleNumber(int[] nums) {
    int result = 0;
    for (int num : nums) result ^= num;
    return result;
}

// Counting Bits
public int[] countBits(int n) {
    int[] dp = new int[n + 1];
    for (int i = 1; i <= n; i++) {
        dp[i] = dp[i >> 1] + (i & 1);
    }
    return dp;
}

// Power of Two
public boolean isPowerOfTwo(int n) {
    return n > 0 && (n & (n - 1)) == 0;
}

// Number of 1 Bits
public int hammingWeight(int n) {
    int count = 0;
    while (n != 0) {
        n &= (n - 1);
        count++;
    }
    return count;
}

// Reverse Bits
public int reverseBits(int n) {
    int result = 0;
    for (int i = 0; i < 32; i++) {
        result = (result << 1) | (n & 1);
        n >>= 1;
    }
    return result;
}
```

## Example Problems

| # | Problem | Difficulty | Key Idea |
|---|---------|------------|----------|
| 1 | **LC 136 -- Single Number** | Easy | XOR all elements; pairs cancel |
| 2 | **LC 338 -- Counting Bits** | Easy | DP: dp[i] = dp[i >> 1] + (i & 1) |
| 3 | **LC 191 -- Number of 1 Bits** | Easy | n & (n-1) removes lowest set bit; count iterations |

## Complexity

| Operation | Time | Space |
|-----------|------|-------|
| Single Number | O(n) | O(1) |
| Counting Bits | O(n) | O(n) |
| Hamming Weight | O(number of set bits) | O(1) |

---

# GOOGLE-SPECIFIC TIPS

## Communication During the Interview

**1. Think out loud at every step.**
Google interviewers explicitly evaluate your thought process. Silence is a red flag. Narrate what you are considering, what you are ruling out, and why.

**2. Clarify before coding.**
- Restate the problem in your own words.
- Ask about input constraints: size of n, value ranges, signed/unsigned, empty inputs.
- Ask about edge cases: empty arrays, single elements, negative numbers, duplicates.
- Confirm expected output format.
- Ask: "Can I assume the input is valid, or should I handle invalid input?"

**3. Start with brute force, then optimize.**
Say: "The brute force approach would be [X] with O(n^2) time. Can we do better?"
This shows you can identify the baseline and reason about optimization.

**4. State your approach before coding.**
Say: "I will use [pattern/technique] because [reason]. The time complexity will be O(...) and space will be O(...)."
Wait for the interviewer to agree before writing code.

**5. Write clean code.**
- Use descriptive variable names (not i, j unless they are loop indices).
- Extract helper functions if a block is complex.
- Add brief inline comments for tricky logic.
- Handle edge cases at the top of the function.

**6. Test your code on paper/whiteboard.**
After writing, trace through with:
- The given example
- An edge case (empty input, single element)
- A tricky case (all same elements, sorted input, reverse-sorted)

**7. Optimize step by step.**
If your first solution is O(n^2), say: "Can I use a hash map to bring this to O(n)?" or "Can I sort and use two pointers for O(n log n)?"

## Time Management in 45 Minutes

| Phase | Time | Action |
|-------|------|--------|
| Understand | 5 min | Read problem, clarify, ask questions |
| Examples | 3 min | Work through 1-2 examples by hand |
| Brute force | 2 min | State brute force approach and complexity |
| Optimize | 5 min | Identify pattern, propose optimal approach |
| Code | 15 min | Write clean, correct code |
| Test | 5 min | Trace through examples, fix bugs |
| Edge cases | 3 min | Test edge cases, discuss |
| Follow-up | 2 min | Discuss alternative approaches, further optimizations |
| **Buffer** | **5 min** | **For unexpected difficulties** |

## What Google Looks For (Hiring Signals)

1. **Coding:** Clean, correct, production-quality code. Not just correctness but readability.
2. **Algorithms:** Choose the right data structure and algorithm. Know trade-offs.
3. **Communication:** Explain your thought process. Engage with the interviewer.
4. **Testing:** Proactively test your code. Identify edge cases.
5. **Problem-solving:** Can you break down a hard problem? Can you handle hints?

---

# COMPLEXITY ANALYSIS CHEAT SHEET

## Big O for Common Algorithms

| Algorithm | Best | Average | Worst | Space |
|-----------|------|---------|-------|-------|
| Binary Search | O(1) | O(log n) | O(log n) | O(1) |
| Linear Search | O(1) | O(n) | O(n) | O(1) |
| Bubble Sort | O(n) | O(n^2) | O(n^2) | O(1) |
| Selection Sort | O(n^2) | O(n^2) | O(n^2) | O(1) |
| Insertion Sort | O(n) | O(n^2) | O(n^2) | O(1) |
| Merge Sort | O(n log n) | O(n log n) | O(n log n) | O(n) |
| Quick Sort | O(n log n) | O(n log n) | O(n^2) | O(log n) |
| Heap Sort | O(n log n) | O(n log n) | O(n log n) | O(1) |
| Counting Sort | O(n + k) | O(n + k) | O(n + k) | O(k) |
| Radix Sort | O(d * (n + k)) | O(d * (n + k)) | O(d * (n + k)) | O(n + k) |
| Tim Sort (Java/Python default) | O(n) | O(n log n) | O(n log n) | O(n) |
| BFS/DFS (graph) | O(V + E) | O(V + E) | O(V + E) | O(V) |
| Dijkstra (min-heap) | O((V+E) log V) | O((V+E) log V) | O((V+E) log V) | O(V) |
| Bellman-Ford | O(V * E) | O(V * E) | O(V * E) | O(V) |
| Floyd-Warshall | O(V^3) | O(V^3) | O(V^3) | O(V^2) |
| Topological Sort | O(V + E) | O(V + E) | O(V + E) | O(V) |
| Kruskal's MST | O(E log E) | O(E log E) | O(E log E) | O(V) |
| Prim's MST (min-heap) | O((V+E) log V) | O((V+E) log V) | O((V+E) log V) | O(V) |

## Big O for Data Structure Operations

| Data Structure | Access | Search | Insert | Delete | Notes |
|---------------|--------|--------|--------|--------|-------|
| Array | O(1) | O(n) | O(n) | O(n) | Insert/delete at end: O(1) amortized |
| Linked List | O(n) | O(n) | O(1)* | O(1)* | *If you have the node reference |
| Stack | O(n) | O(n) | O(1) | O(1) | push/pop are O(1) |
| Queue | O(n) | O(n) | O(1) | O(1) | enqueue/dequeue are O(1) |
| HashMap | N/A | O(1) avg | O(1) avg | O(1) avg | O(n) worst case (hash collision) |
| TreeMap (BST) | O(log n) | O(log n) | O(log n) | O(log n) | Balanced BST (Red-Black Tree in Java) |
| Heap (PQ) | O(1) peek | O(n) | O(log n) | O(log n) | Peek min/max is O(1) |
| Trie | O(m) | O(m) | O(m) | O(m) | m = key length |
| Union-Find | N/A | O(alpha(n)) | O(alpha(n)) | N/A | alpha ~ O(1) amortized |

## Common Complexity Classes (Slowest to Fastest)

```
O(1) < O(log n) < O(sqrt(n)) < O(n) < O(n log n) < O(n^2) < O(n^3) < O(2^n) < O(n!) < O(n^n)
```

**Rough n limits for 1-second time limit:**

| Complexity | Max n (approx) |
|-----------|-----------------|
| O(n!) | n <= 12 |
| O(2^n) | n <= 20-25 |
| O(n^3) | n <= 500 |
| O(n^2) | n <= 5,000-10,000 |
| O(n log n) | n <= 1,000,000 |
| O(n) | n <= 10,000,000 |
| O(log n) | n <= 10^18 |

---

# COMMON DATA STRUCTURES OVERVIEW

## Array

**Description:** Contiguous memory block with fixed size (static) or dynamic resizing (ArrayList/list).

**When to use:** Random access needed, cache-friendly iteration, known or bounded size.

**Java:** `int[]`, `ArrayList<Integer>`
**Python:** `list`

| Operation | Time |
|-----------|------|
| Access by index | O(1) |
| Search (unsorted) | O(n) |
| Search (sorted) | O(log n) |
| Insert at end | O(1) amortized |
| Insert at position | O(n) |
| Delete at end | O(1) |
| Delete at position | O(n) |

## Linked List

**Description:** Nodes connected by pointers. Singly linked (next only) or doubly linked (prev + next).

**When to use:** Frequent insertions/deletions at known positions, no random access needed, implementing stacks/queues.

**Java:** `LinkedList<E>`
**Python:** No built-in; implement with classes or use `collections.deque`

| Operation | Time |
|-----------|------|
| Access by index | O(n) |
| Search | O(n) |
| Insert at head | O(1) |
| Insert at tail (with tail pointer) | O(1) |
| Delete at head | O(1) |
| Delete at position (given node) | O(1) |

## Stack

**Description:** LIFO (Last In, First Out). Push and pop from the same end.

**When to use:** Parenthesis matching, undo operations, DFS, monotonic stack problems, expression evaluation.

**Java:** `Deque<E> stack = new ArrayDeque<>()` (preferred over `Stack<E>`)
**Python:** `list` (use `append()` and `pop()`)

| Operation | Time |
|-----------|------|
| Push | O(1) |
| Pop | O(1) |
| Peek | O(1) |

## Queue

**Description:** FIFO (First In, First Out). Enqueue at back, dequeue from front.

**When to use:** BFS, task scheduling, buffering, level-order traversal.

**Java:** `Queue<E> queue = new LinkedList<>()` or `new ArrayDeque<>()`
**Python:** `collections.deque` (use `append()` and `popleft()`)

| Operation | Time |
|-----------|------|
| Enqueue | O(1) |
| Dequeue | O(1) |
| Peek | O(1) |

## HashMap / HashSet

**Description:** Key-value store with hash-based O(1) average operations. HashSet is a HashMap with no values.

**When to use:** Frequency counting, deduplication, O(1) lookup needed, two-sum type problems.

**Java:** `HashMap<K,V>`, `HashSet<E>`, `LinkedHashMap<K,V>` (insertion order)
**Python:** `dict`, `set`, `collections.Counter`, `collections.defaultdict`

| Operation | Average | Worst |
|-----------|---------|-------|
| Get/Put | O(1) | O(n) |
| Contains | O(1) | O(n) |
| Delete | O(1) | O(n) |

## TreeMap / TreeSet (Balanced BST)

**Description:** Sorted key-value store backed by a Red-Black Tree. All operations O(log n). Supports range queries, floor/ceiling, first/last.

**When to use:** Need sorted order, range queries, floor/ceiling operations, ordered iteration.

**Java:** `TreeMap<K,V>`, `TreeSet<E>`
**Python:** `sortedcontainers.SortedList`, `sortedcontainers.SortedDict` (third-party), or use `bisect` module

| Operation | Time |
|-----------|------|
| Get/Put | O(log n) |
| Contains | O(log n) |
| First/Last | O(log n) |
| Floor/Ceiling | O(log n) |
| Range query | O(log n + k) |

## Heap / Priority Queue

**Description:** Complete binary tree where parent <= children (min-heap) or parent >= children (max-heap). Backed by an array.

**When to use:** Top-K problems, merging sorted sequences, scheduling, median maintenance.

**Java:** `PriorityQueue<E>` (min-heap by default; use `Collections.reverseOrder()` for max-heap)
**Python:** `heapq` module (min-heap; negate values for max-heap)

| Operation | Time |
|-----------|------|
| Insert (offer) | O(log n) |
| Extract min/max (poll) | O(log n) |
| Peek | O(1) |
| Heapify | O(n) |

## Trie (Prefix Tree)

**Description:** Tree where each node represents a character. Paths represent prefixes/words. Efficient for prefix operations.

**When to use:** Autocomplete, spell checking, prefix matching, word search on grids.

| Operation | Time |
|-----------|------|
| Insert word | O(m) |
| Search word | O(m) |
| Search prefix | O(m) |

(m = length of word/prefix)

## Graph

**Description:** Vertices connected by edges. Can be directed/undirected, weighted/unweighted, cyclic/acyclic.

**Representations:**
- **Adjacency list:** `Map<Integer, List<Integer>>` -- space O(V+E), good for sparse graphs
- **Adjacency matrix:** `int[V][V]` -- space O(V^2), good for dense graphs, O(1) edge lookup
- **Edge list:** `List<int[]>` -- space O(E), good for Kruskal's MST

**Java:** `Map<Integer, List<Integer>>` or `List<List<Integer>>`
**Python:** `defaultdict(list)` or `{node: [neighbors]}`

| Operation | Adj List | Adj Matrix |
|-----------|----------|------------|
| Add edge | O(1) | O(1) |
| Check edge | O(degree) | O(1) |
| Get neighbors | O(degree) | O(V) |
| Space | O(V + E) | O(V^2) |

---

# 50 MUST-PRACTICE LEETCODE PROBLEMS

Organized by pattern. Solve these in order within each category. Master the Easy/Medium ones first; Hard ones are stretch goals.

## Two Pointers (5 problems)

| # | LC# | Problem | Difficulty | Notes |
|---|-----|---------|------------|-------|
| 1 | 167 | Two Sum II - Input Array Is Sorted | Easy | Classic opposite-direction |
| 2 | 15 | 3Sum | Medium | Sort + two pointers, skip duplicates |
| 3 | 11 | Container With Most Water | Medium | Move shorter pointer inward |
| 4 | 26 | Remove Duplicates from Sorted Array | Easy | Same-direction slow/fast |
| 5 | 42 | Trapping Rain Water | Hard | Two pointers with left_max/right_max |

## Sliding Window (4 problems)

| # | LC# | Problem | Difficulty | Notes |
|---|-----|---------|------------|-------|
| 6 | 3 | Longest Substring Without Repeating Characters | Medium | Variable window + HashSet |
| 7 | 76 | Minimum Window Substring | Hard | Variable window + frequency map |
| 8 | 438 | Find All Anagrams in a String | Medium | Fixed window + frequency comparison |
| 9 | 209 | Minimum Size Subarray Sum | Medium | Variable window, shrink when sum >= target |

## Binary Search (4 problems)

| # | LC# | Problem | Difficulty | Notes |
|---|-----|---------|------------|-------|
| 10 | 704 | Binary Search | Easy | Standard template |
| 11 | 33 | Search in Rotated Sorted Array | Medium | Determine sorted half |
| 12 | 34 | Find First and Last Position of Element | Medium | Two binary searches |
| 13 | 1011 | Capacity to Ship Packages Within D Days | Medium | Binary search on answer |

## BFS/DFS (5 problems)

| # | LC# | Problem | Difficulty | Notes |
|---|-----|---------|------------|-------|
| 14 | 200 | Number of Islands | Medium | BFS/DFS on grid |
| 15 | 102 | Binary Tree Level Order Traversal | Medium | BFS with level-size loop |
| 16 | 104 | Maximum Depth of Binary Tree | Easy | DFS recursive |
| 17 | 207 | Course Schedule | Medium | Topological sort / cycle detection |
| 18 | 994 | Rotting Oranges | Medium | Multi-source BFS |

## Dynamic Programming (6 problems)

| # | LC# | Problem | Difficulty | Notes |
|---|-----|---------|------------|-------|
| 19 | 70 | Climbing Stairs | Easy | 1D DP, Fibonacci variant |
| 20 | 322 | Coin Change | Medium | Unbounded knapsack |
| 21 | 300 | Longest Increasing Subsequence | Medium | O(n log n) with patience sorting |
| 22 | 1143 | Longest Common Subsequence | Medium | 2D DP |
| 23 | 72 | Edit Distance | Medium | 2D DP, insert/delete/replace |
| 24 | 416 | Partition Equal Subset Sum | Medium | 0/1 knapsack (subset sum) |

## Backtracking (4 problems)

| # | LC# | Problem | Difficulty | Notes |
|---|-----|---------|------------|-------|
| 25 | 78 | Subsets | Medium | Include/exclude pattern |
| 26 | 46 | Permutations | Medium | Use visited array |
| 27 | 39 | Combination Sum | Medium | Reuse elements, start index |
| 28 | 51 | N-Queens | Hard | Row-by-row placement with diagonal tracking |

## Topological Sort (2 problems)

| # | LC# | Problem | Difficulty | Notes |
|---|-----|---------|------------|-------|
| 29 | 210 | Course Schedule II | Medium | Return topological order |
| 30 | 269 | Alien Dictionary | Hard | Build graph from word order |

## Union Find (3 problems)

| # | LC# | Problem | Difficulty | Notes |
|---|-----|---------|------------|-------|
| 31 | 547 | Number of Provinces | Medium | Union connected cities |
| 32 | 684 | Redundant Connection | Medium | Edge that forms a cycle |
| 33 | 721 | Accounts Merge | Medium | Union by shared emails |

## Trie (2 problems)

| # | LC# | Problem | Difficulty | Notes |
|---|-----|---------|------------|-------|
| 34 | 208 | Implement Trie | Medium | Standard template |
| 35 | 212 | Word Search II | Hard | Trie + backtracking on grid |

## Monotonic Stack (3 problems)

| # | LC# | Problem | Difficulty | Notes |
|---|-----|---------|------------|-------|
| 36 | 496 | Next Greater Element I | Easy | Stack + hash map |
| 37 | 84 | Largest Rectangle in Histogram | Hard | Increasing stack |
| 38 | 239 | Sliding Window Maximum | Hard | Monotonic deque |

## Heap / Priority Queue (3 problems)

| # | LC# | Problem | Difficulty | Notes |
|---|-----|---------|------------|-------|
| 39 | 215 | Kth Largest Element in an Array | Medium | Min-heap of size K or Quickselect |
| 40 | 23 | Merge K Sorted Lists | Hard | Min-heap of K heads |
| 41 | 295 | Find Median from Data Stream | Hard | Two heaps |

## Intervals (3 problems)

| # | LC# | Problem | Difficulty | Notes |
|---|-----|---------|------------|-------|
| 42 | 56 | Merge Intervals | Medium | Sort by start, merge overlapping |
| 43 | 57 | Insert Interval | Medium | Three-phase approach |
| 44 | 253 | Meeting Rooms II | Medium | Min-heap of end times |

## Linked List (3 problems)

| # | LC# | Problem | Difficulty | Notes |
|---|-----|---------|------------|-------|
| 45 | 206 | Reverse Linked List | Easy | Iterative pointer reversal |
| 46 | 142 | Linked List Cycle II | Medium | Floyd's algorithm |
| 47 | 21 | Merge Two Sorted Lists | Easy | Dummy head technique |

## Prefix Sum + Bit Manipulation (3 problems)

| # | LC# | Problem | Difficulty | Notes |
|---|-----|---------|------------|-------|
| 48 | 560 | Subarray Sum Equals K | Medium | Prefix sum + hash map |
| 49 | 238 | Product of Array Except Self | Medium | Left and right prefix products |
| 50 | 136 | Single Number | Easy | XOR all elements |

---

# HOW TO APPROACH AN UNKNOWN PROBLEM IN 45 MINUTES

## The UMPIRE Framework

**U -- Understand the problem (5 minutes)**
- Read the problem statement carefully -- twice.
- Identify the input and output types.
- Ask clarifying questions:
  - What is the range of n? (Helps determine acceptable time complexity)
  - Can there be duplicates? Negative numbers? Empty input?
  - Is the input sorted? Can I modify it?
  - What should I return if there is no valid answer?
- Restate the problem in your own words to the interviewer.

**M -- Match to a pattern (3 minutes)**
Use this decision tree:

```
Is input sorted or can be sorted?
  YES --> Two Pointers, Binary Search
  NO  --> Continue

Does problem ask about subarrays/substrings?
  YES --> Sliding Window, Prefix Sum
  NO  --> Continue

Does problem involve a tree?
  YES --> DFS/BFS, Recursion
  NO  --> Continue

Does problem involve a graph?
  YES --> BFS (shortest path), DFS (all paths), Topological Sort, Union-Find
  NO  --> Continue

Does problem ask for all combinations/permutations/subsets?
  YES --> Backtracking
  NO  --> Continue

Does problem have optimal substructure + overlapping subproblems?
  YES --> Dynamic Programming
  NO  --> Continue

Does problem involve "next greater/smaller" or "sliding window max/min"?
  YES --> Monotonic Stack/Queue
  NO  --> Continue

Does problem involve top-K, merge-K, or running median?
  YES --> Heap / Priority Queue
  NO  --> Continue

Does problem involve intervals/ranges?
  YES --> Sort + Sweep/Merge
  NO  --> Continue

Does problem involve string prefixes?
  YES --> Trie
  NO  --> Continue

Does problem involve grouping/connectivity?
  YES --> Union-Find, HashMap
  NO  --> Continue

Does problem involve single unique element or bit properties?
  YES --> Bit Manipulation
  NO  --> Consider brute force optimization with HashMap
```

**P -- Plan your approach (5 minutes)**
- State the brute force solution and its complexity.
- Identify the bottleneck (usually nested loops).
- Propose the optimized approach using the matched pattern.
- State the expected time and space complexity.
- Get interviewer agreement before coding.

**I -- Implement (15 minutes)**
- Write clean, well-structured code.
- Use meaningful variable names.
- Handle edge cases at the top.
- Write helper functions for complex logic.
- Do NOT optimize prematurely -- get a correct solution first.

**R -- Review and test (5 minutes)**
- Trace through your code with the provided example.
- Check for off-by-one errors, null/None checks, boundary conditions.
- Test with:
  - Normal case (provided example)
  - Edge case: empty input, single element
  - Edge case: all same elements
  - Large input (discuss, do not trace)

**E -- Evaluate and optimize (5 minutes + 2 minute buffer)**
- Discuss the time and space complexity of your solution.
- If there is a better approach, discuss it (even if you do not code it).
- Mention trade-offs: "We could use O(n) space to get O(n) time, or O(1) space with O(n log n) time."
- If the interviewer asks a follow-up, apply the same UMPIRE framework.

## Quick Pattern Recognition Cheat Sheet

| If you see... | Think... |
|--------------|----------|
| "Sorted array" | Binary Search, Two Pointers |
| "Find pair/triplet with sum" | Two Pointers (after sorting) |
| "Maximum/minimum subarray" | Sliding Window, Kadane's, Prefix Sum |
| "Longest substring with constraint" | Sliding Window with HashMap |
| "Tree traversal" | BFS (level order), DFS (pre/in/post) |
| "Shortest path (unweighted)" | BFS |
| "Shortest path (weighted)" | Dijkstra, Bellman-Ford |
| "Connected components" | Union-Find, BFS/DFS |
| "Number of ways" or "minimum cost" | Dynamic Programming |
| "All possible combinations" | Backtracking |
| "Dependencies/ordering" | Topological Sort |
| "Next greater/smaller" | Monotonic Stack |
| "Top K" or "Kth largest" | Heap |
| "Overlapping intervals" | Sort + Merge |
| "Prefix matching" | Trie |
| "XOR / bit properties" | Bit Manipulation |
| "Subarray sum = K" | Prefix Sum + HashMap |
| "In-place array modification" | Two Pointers |
| "Linked list cycle" | Floyd's (fast/slow pointers) |
| "Matrix search (sorted)" | Binary Search (treat as 1D) |

## Final Advice for Google Interviews

1. **Practice under time pressure.** Use a 45-minute timer. If you cannot solve a medium problem in 30 minutes, study the solution and re-solve it the next day.

2. **Master the templates.** Do not memorize solutions to specific problems. Memorize the *patterns* and templates. Any new problem is a variation of a known pattern.

3. **Communicate relentlessly.** The interviewer cannot read your mind. A candidate who communicates a mediocre solution well often scores higher than one who silently writes an optimal solution.

4. **Do not panic on Hard problems.** Google interviewers often give hard problems expecting you to solve them partially. Getting the brute force correct and discussing the optimization path is a strong signal.

5. **Edge cases win interviews.** The difference between a "hire" and "strong hire" is often proactive edge case handling. Always check: empty input, single element, all duplicates, negative numbers, integer overflow.

6. **Know your language deeply.** For Java: know Collections API, Streams, Comparators, generics. For Python: know list comprehensions, collections module (Counter, defaultdict, deque), itertools, bisect.

---

**End of DSA Coding Patterns Study Guide**
