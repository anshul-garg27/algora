import random, time
from obst import construct_optimal_bst, tree_cost
from obst_knuth import construct_optimal_bst_knuth


def brute_min(freq):
    from functools import lru_cache
    @lru_cache(maxsize=None)
    def rec(i, j, depth):
        if i > j:
            return 0
        return min(freq[r] * depth + rec(i, r - 1, depth + 1) + rec(r + 1, j, depth + 1)
                   for r in range(i, j + 1))
    return rec(0, len(freq) - 1, 1)


print("=== Prompt sample ===")
w = ["apple", "banana", "cherry"]; f = [30, 10, 40]
r1, c1 = construct_optimal_bst(w, f)
r2, c2 = construct_optimal_bst_knuth(w, f)
print("O(n^3) cost =", c1, " Knuth O(n^2) cost =", c2, " expected 130 =>",
      c1 == c2 == 130 == tree_cost(r1) == tree_cost(r2))

print("=== Randomized: brute vs O(n^3) vs Knuth (n<=9) ===")
random.seed(7)
for _ in range(500):
    n = random.randint(1, 9)
    f = [random.randint(1, 60) for _ in range(n)]
    w = [f"w{i:02d}" for i in range(n)]
    a = construct_optimal_bst(w, f)[1]
    b = construct_optimal_bst_knuth(w, f)[1]
    g = brute_min(tuple(f))
    assert a == b == g, (f, a, b, g)
print("500/500 agree across all three methods.")

print("=== n=200 timing: O(n^3) vs Knuth O(n^2) ===")
random.seed(11)
f = [random.randint(1, 10**6) for _ in range(200)]
w = [f"w{i:04d}" for i in range(200)]
t0 = time.time(); _, c_cubic = construct_optimal_bst(w, f); t_cubic = time.time() - t0
t0 = time.time(); _, c_knuth = construct_optimal_bst_knuth(w, f); t_knuth = time.time() - t0
print(f"O(n^3): {t_cubic*1000:7.1f} ms  cost={c_cubic}")
print(f"Knuth : {t_knuth*1000:7.1f} ms  cost={c_knuth}")
print("Costs identical:", c_cubic == c_knuth)
