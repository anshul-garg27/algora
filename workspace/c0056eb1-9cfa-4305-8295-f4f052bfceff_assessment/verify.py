import random
from collections import deque
from solution import solve


def brute(n, edges):
    # adjacency with reversal cost
    adj = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append((v, 0))
        adj[v].append((u, 1))
    res = []
    for s in range(n):
        seen = [False] * n
        seen[s] = True
        dq = deque([s])
        cost = 0
        while dq:
            x = dq.popleft()
            for y, w in adj[x]:
                if not seen[y]:
                    seen[y] = True
                    cost += w
                    dq.append(y)
        res.append(cost)
    return " ".join(map(str, res))


def make_input(n, edges):
    s = [str(n)]
    for u, v in edges:
        s.append(f"{u} {v}")
    return "\n".join(s) + "\n"


random.seed(1)
for t in range(3000):
    n = random.randint(1, 9)
    edges = []
    for v in range(1, n):
        u = random.randint(0, v - 1)
        # random orientation
        if random.random() < 0.5:
            edges.append((u, v))
        else:
            edges.append((v, u))
    inp = make_input(n, edges)
    got = solve(inp)
    exp = brute(n, edges)
    if got != exp:
        print("MISMATCH", n, edges, "got", got, "exp", exp)
        break
else:
    print("All random tests passed")
