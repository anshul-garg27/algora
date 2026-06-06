import random, time
from solution import solve

random.seed(7)
n = 200000
lines = [str(n)]
for v in range(1, n):
    u = random.randint(0, v - 1)
    if random.random() < 0.5:
        lines.append(f"{u} {v}")
    else:
        lines.append(f"{v} {u}")
# also force a deep chain edge case separately
inp = "\n".join(lines) + "\n"

t = time.time()
out = solve(inp)
print("n =", n, "time = %.3fs" % (time.time() - t), "outlen =", len(out.split()))

# deep chain (worst case for recursion - we use iterative so fine)
chain = [str(n)] + [f"{i} {i+1}" for i in range(n - 1)]
t = time.time()
out2 = solve("\n".join(chain) + "\n")
vals = out2.split()
print("chain time = %.3fs" % (time.time() - t), "first/last:", vals[0], vals[-1])
