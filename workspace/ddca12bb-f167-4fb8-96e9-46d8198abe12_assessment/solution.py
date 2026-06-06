import sys

class Solution:
    def trap(self, height):
        # Two-pointer approach: O(n) time, O(1) space.
        # Water above bar i = min(maxLeft, maxRight) - height[i].
        # We converge two pointers; the side with the smaller wall is
        # safe to resolve because the opposite (taller) wall bounds it.
        if not height:
            return 0
        left, right = 0, len(height) - 1
        left_max, right_max = height[left], height[right]
        water = 0
        while left < right:
            if left_max <= right_max:
                left += 1
                left_max = max(left_max, height[left])
                water += left_max - height[left]
            else:
                right -= 1
                right_max = max(right_max, height[right])
                water += right_max - height[right]
        return water


def _brute(height):
    # O(n^2) reference for validation.
    n = len(height)
    total = 0
    for i in range(n):
        lm = max(height[:i+1])
        rm = max(height[i:])
        total += min(lm, rm) - height[i]
    return total


if __name__ == "__main__":
    data = sys.stdin.read().split()
    if data:
        arr = list(map(int, data))
        print(Solution().trap(arr))
