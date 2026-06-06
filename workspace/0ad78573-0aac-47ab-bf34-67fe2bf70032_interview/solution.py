def trap(height):
    """Two-pointer, O(n) time, O(1) space."""
    if not height:
        return 0
    left, right = 0, len(height) - 1
    left_max, right_max = 0, 0
    water = 0
    while left < right:
        if height[left] < height[right]:
            left_max = max(left_max, height[left])
            water += left_max - height[left]
            left += 1
        else:
            right_max = max(right_max, height[right])
            water += right_max - height[right]
            right -= 1
    return water


def trap_brute(height):
    """O(n^2) reference for cross-checking."""
    n = len(height)
    total = 0
    for i in range(n):
        l = max(height[:i + 1])
        r = max(height[i:])
        total += min(l, r) - height[i]
    return total


# --- sample + edge cases ---
tests = [
    ([0,1,0,2,1,0,1,3,2,1,2,1], 6),   # LeetCode classic
    ([4,2,0,3,2,5], 9),               # LeetCode classic 2
    ([3,0,2,0,4], 7),                 # my traced example
    ([], 0),
    ([5], 0),
    ([2,2], 0),
    ([1,2,3,4,5], 0),                 # monotonic increasing
    ([5,4,3,2,1], 0),                 # monotonic decreasing
    ([0,0,0], 0),
    ([5,0,5], 5),
    ([2,0,2,0,2], 4),
]
for h, expected in tests:
    got = trap(h)
    assert got == expected, f"FAIL {h}: got {got}, want {expected}"
    if h:
        assert got == trap_brute(h), f"BRUTE MISMATCH {h}"
print("all tests passed")

# random cross-check against brute force
import random
random.seed(1)
for _ in range(3000):
    h = [random.randint(0, 9) for _ in range(random.randint(0, 12))]
    assert trap(h) == trap_brute(h), f"mismatch {h}"
print("random cross-check passed")
