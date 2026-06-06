from functools import lru_cache

def predict_winner(nums):
    n = len(nums)
    # dp[i][j] = best (current player - opponent) on nums[i..j]
    dp = [[0] * n for _ in range(n)]
    for i in range(n):
        dp[i][i] = nums[i]
    for length in range(2, n + 1):
        for i in range(0, n - length + 1):
            j = i + length - 1
            take_left = nums[i] - dp[i + 1][j]
            take_right = nums[j] - dp[i][j - 1]
            dp[i][j] = max(take_left, take_right)

    result = dp[0][n - 1] >= 0

    # Reconstruct path, tie-break prefers left
    p1, p2 = [], []
    i, j, turn = 0, n - 1, 0  # turn 0 -> Player1
    while i <= j:
        if i == j:
            pick = nums[i]
            i += 1
        else:
            take_left = nums[i] - dp[i + 1][j]
            take_right = nums[j] - dp[i][j - 1]
            if take_left >= take_right:
                pick = nums[i]; i += 1
            else:
                pick = nums[j]; j -= 1
        (p1 if turn == 0 else p2).append(pick)
        turn ^= 1

    return result, p1, p2


def brute(nums):
    # exponential reference for difference, ignoring path
    from functools import lru_cache
    @lru_cache(None)
    def solve(i, j):
        if i > j: return 0
        return max(nums[i] - solve(i + 1, j), nums[j] - solve(i, j - 1))
    return solve(0, len(nums) - 1) >= 0


if __name__ == "__main__":
    tests = [
        [1, 5, 2],
        [1, 5, 233, 7],
        [1, 2, 3, 4, 5, 6],
        [0],
        [5, 3],
        [3, 5],
        [2, 2, 2, 2],
        [100000] * 10,
        [0, 0, 0],
    ]
    for t in tests:
        res, p1, p2 = predict_winner(t)
        s1, s2 = sum(p1), sum(p2)
        assert res == (s1 >= s2), (t, p1, p2)
        print(f"{t} -> P1wins={res}  P1picks={p1}(={s1})  P2picks={p2}(={s2})")

    # stress vs brute
    import random
    for _ in range(2000):
        m = random.randint(1, 9)
        arr = [random.randint(0, 9) for _ in range(m)]
        res, p1, p2 = predict_winner(arr)
        assert res == brute(arr), (arr, res, brute(arr))
        assert res == (sum(p1) >= sum(p2)), (arr, p1, p2)
    print("All stress tests passed.")
