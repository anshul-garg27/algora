import random

def trap(height):
    # Two-pointer, O(n) time, O(1) space.
    left, right = 0, len(height) - 1
    left_max = right_max = 0
    water = 0
    while left < right:
        if height[left] < height[right]:
            # left side is the shorter wall -> it bounds the water
            left_max = max(left_max, height[left])
            water += left_max - height[left]
            left += 1
        else:
            right_max = max(right_max, height[right])
            water += right_max - height[right]
            right -= 1
    return water

def trap_brute(height):
    n = len(height)
    total = 0
    for i in range(n):
        lm = max(height[:i+1])
        rm = max(height[i:])
        total += min(lm, rm) - height[i]
    return total

# sample cases
samples = [
    ([0,1,0,2,1,0,1,3,2,1,2,1], 6),
    ([4,2,0,3,2,5], 9),
    ([3,0,2,0,4], 7),
    ([], 0),
    ([5], 0),
    ([2,2], 0),
    ([1,2,3,4,5], 0),     # strictly increasing -> no trap
    ([5,4,3,2,1], 0),     # strictly decreasing -> no trap
    ([0,0,0], 0),
    ([5,0,5], 5),
]
for arr, expected in samples:
    got = trap(arr)
    print(f"trap({arr}) = {got}  expected {expected}  [{'OK' if got==expected else 'FAIL'}]")

# randomized cross-check against brute force
bad = 0
for _ in range(5000):
    n = random.randint(0, 20)
    arr = [random.randint(0, 9) for _ in range(n)]
    if trap(arr) != trap_brute(arr):
        bad += 1
        print("MISMATCH", arr, trap(arr), trap_brute(arr))
print("random cross-check mismatches:", bad)
