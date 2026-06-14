"""Uber DSA solutions — Arrays / Sliding Window / Monotonic family.
Run: python3 arrays_windows.py
Problems: Haunted House (3x), longest subarray |diff|<=limit (2x),
sorted-squares + k-th by magnitude (2x), k-th next greater (OA hard, 2x),
max sum from ends (onsite).
"""
from __future__ import annotations

import bisect
from collections import deque


# ---- 1. Haunted House: max group size with per-person [L,R] (asked 3x) ------
# Person i joins a group of size k only if L_i <= k-1 <= R_i.
# Insight: for a fixed k, anyone with L_i+1 <= k <= R_i+1 is eligible; the
# group works iff eligible(k) >= k. Difference array => O(n).

def max_group_size(L: list[int], R: list[int]) -> int:
    n = len(L)
    diff = [0] * (n + 2)
    for l, r in zip(L, R):
        lo, hi = l + 1, min(r + 1, n)
        if lo <= hi:
            diff[lo] += 1
            diff[hi + 1] -= 1
    best, cur = 0, 0
    for k in range(1, n + 1):
        cur += diff[k]
        if cur >= k:
            best = k
    return best
# Follow-up asked: output WHO goes — any k people eligible at the best k.


# ---- 2. Longest subarray with |max-min| <= limit (asked 2x) ------------------
# Sliding window + two monotonic deques tracking window max and min. O(n).

def longest_subarray_limit(nums: list[int], limit: int) -> int:
    maxd: deque[int] = deque()   # decreasing values (indices)
    mind: deque[int] = deque()   # increasing values (indices)
    left = best = 0
    for right, x in enumerate(nums):
        while maxd and nums[maxd[-1]] <= x:
            maxd.pop()
        maxd.append(right)
        while mind and nums[mind[-1]] >= x:
            mind.pop()
        mind.append(right)
        while nums[maxd[0]] - nums[mind[0]] > limit:
            left += 1
            if maxd[0] < left:
                maxd.popleft()
            if mind[0] < left:
                mind.popleft()
        best = max(best, right - left + 1)
    return best


# ---- 3. Sorted squares reorder + k-th by magnitude (asked 2x, 2026) ----------
# Part 1: reorder original elements by |x| using two-pointer merge. O(n).
# Tie rule (matches the Uber sample): when |left| == |right|, take left
# (i.e., the negative side first).

def reorder_by_magnitude(nums: list[int]) -> list[int]:
    # Trap: the smaller of the two ENDS is not the globally smallest element
    # (the middle is). So build from the LARGEST end inward instead:
    res = [0] * len(nums)
    i, j = 0, len(nums) - 1
    for pos in range(len(nums) - 1, -1, -1):
        if abs(nums[i]) > abs(nums[j]):
            res[pos] = nums[i]; i += 1
        else:
            res[pos] = nums[j]; j -= 1
    return res

# Part 2 (the follow-up that sank a real candidate): k-th element by magnitude
# in better-than-linear time. Binary search on magnitude m: how many elements
# have |x| <= m?  count(m) = bisect_right(a, m) - bisect_left(a, -m).
# O(log(maxA) * log n). Tie convention: negative before positive (matches
# part 1 because the larger-end-first build places -m left of +m).

def kth_by_magnitude(nums: list[int], k: int) -> int:
    def count_le(m: int) -> int:
        return bisect.bisect_right(nums, m) - bisect.bisect_left(nums, -m)
    lo, hi = 0, max(abs(nums[0]), abs(nums[-1]))
    while lo < hi:                                # smallest m with count >= k
        mid = (lo + hi) // 2
        if count_le(mid) >= k:
            hi = mid
        else:
            lo = mid + 1
    m = lo
    rank_in_tie = k - count_le(m - 1) if m > 0 else k
    neg_count = bisect.bisect_right(nums, -m) - bisect.bisect_left(nums, -m)
    return -m if rank_in_tie <= neg_count else m


# ---- 4. K-th Next Greater Element indices (OA hard, asked 2x) ----------------
# For each i: 0-based index of the k-th element to the right with value
# strictly greater, else -1. Offline: process values in DESC order; for equal
# values query before inserting the group. BIT gives "k-th set index > i".
# O(n log n).

class BIT:
    def __init__(self, n: int) -> None:
        self.n = n
        self.t = [0] * (n + 1)

    def add(self, i: int) -> None:               # 0-based index
        i += 1
        while i <= self.n:
            self.t[i] += 1
            i += i & (-i)

    def prefix(self, i: int) -> int:             # count of set indices <= i
        i += 1
        s = 0
        while i > 0:
            s += self.t[i]
            i -= i & (-i)
        return s

    def kth(self, k: int) -> int:
        """Smallest 0-based index with prefix == k (k >= 1)."""
        pos, log = 0, self.n.bit_length()
        for step in range(log, -1, -1):
            nxt = pos + (1 << step)
            if nxt <= self.n and self.t[nxt] < k:
                pos = nxt
                k -= self.t[nxt]
        return pos                                # 0-based


def kth_next_greater(nums: list[int], k: int) -> list[int]:
    n = len(nums)
    ans = [-1] * n
    bit = BIT(n)
    order = sorted(range(n), key=lambda i: -nums[i])
    i = 0
    while i < n:
        j = i
        group = []
        while j < n and nums[order[j]] == nums[order[i]]:
            group.append(order[j])
            j += 1
        for idx in group:                         # query before inserting equals
            greater_before = bit.prefix(idx)      # set indices <= idx
            target = greater_before + k           # k-th set index AFTER idx
            total = bit.prefix(n - 1)
            if total >= target:
                ans[idx] = bit.kth(target)
        for idx in group:
            bit.add(idx)
        i = j
    return ans


def kth_next_greater_brute(nums: list[int], k: int) -> list[int]:
    n = len(nums)
    out = []
    for i in range(n):
        cnt = 0
        res = -1
        for j in range(i + 1, n):
            if nums[j] > nums[i]:
                cnt += 1
                if cnt == k:
                    res = j
                    break
        out.append(res)
    return out


# ---- 5. Max sum taking exactly k elements from the ends (onsite 2025-11) -----
# Complement trick: keep a window of n-k contiguous elements with MIN sum.

def max_sum_from_ends(nums: list[int], k: int) -> int:
    n = len(nums)
    total = sum(nums)
    w = n - k
    if w == 0:
        return total
    cur = sum(nums[:w])
    best = cur
    for i in range(w, n):
        cur += nums[i] - nums[i - w]
        best = min(best, cur)
    return total - best


# ------------------------------- tests ---------------------------------------

def main() -> None:
    import random

    assert max_group_size([1, 2, 2], [3, 3, 3]) == 3
    assert max_group_size([2], [3]) == 0          # alone: k-1=0 < L=2
    assert max_group_size([0, 0], [0, 0]) == 1    # only a single person works

    assert longest_subarray_limit([8, 2, 4, 7], 4) == 2
    assert longest_subarray_limit([10, 1, 2, 4, 7, 2], 5) == 4
    assert longest_subarray_limit([4, 2, 2, 2, 4, 4, 2, 2], 0) == 3

    a = [-7, -2, -1, -1, 1, 2, 2, 2, 3, 5]
    assert reorder_by_magnitude(a) == [-1, -1, 1, -2, 2, 2, 2, 3, 5, -7]
    for k in range(1, len(a) + 1):
        assert kth_by_magnitude(a, k) == reorder_by_magnitude(a)[k - 1], k

    # randomized cross-check for kth_next_greater
    random.seed(7)
    for _ in range(200):
        arr = [random.randint(0, 9) for _ in range(random.randint(1, 12))]
        kk = random.randint(1, 3)
        assert kth_next_greater(arr, kk) == kth_next_greater_brute(arr, kk), (arr, kk)

    assert max_sum_from_ends([1, 2, 3, 4, 5, 6, 1], 3) == 12
    assert max_sum_from_ends([2, 2, 2], 2) == 4
    assert max_sum_from_ends([1, 1000, 1], 1) == 1

    print("PASS")


if __name__ == "__main__":
    main()
