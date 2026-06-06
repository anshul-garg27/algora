import random
from collections import deque
from sol import getMinInversions


def brute(n, g_from, g_to):
    # For each root, BFS over undirected tree, count edges that point the wrong way.
    # Build set of directed edges.
    directed = set(zip(g_from, g_to))
    und = [[] for _ in range(n + 1)]
    for a, b in zip(g_from, g_to):
        und[a].append(b)
        und[b].append(a)
    best = float('inf')
    for root in range(1, n + 1):
        vis = [False] * (n + 1)
        vis[root] = True
        dq = deque([root])
        rev = 0
        while dq:
            u = dq.popleft()
            for v in und[u]:
                if not vis[v]:
                    vis[v] = True
                    # need edge u->v. If original is u->v fine else reverse.
                    if (u, v) not in directed:
                        rev += 1
                    dq.append(v)
        best = min(best, rev)
    return best


def random_tree(n):
    g_from, g_to = [], []
    for v in range(2, n + 1):
        u = random.randint(1, v - 1)
        # random orientation
        if random.random() < 0.5:
            g_from.append(u); g_to.append(v)
        else:
            g_from.append(v); g_to.append(u)
    return g_from, g_to


random.seed(1)
for t in range(3000):
    n = random.randint(2, 9)
    gf, gt = random_tree(n)
    exp = brute(n, gf, gt)
    got = getMinInversions(n, gf, gt)
    if exp != got:
        print("MISMATCH", n, gf, gt, "exp", exp, "got", got)
        break
else:
    print("All random tests passed")

# Edge case: n=2 both orientations
print("n=2 a->b:", getMinInversions(2, [1], [2]))  # root1 ->0
print("n=2 b->a:", getMinInversions(2, [2], [1]))  # root2 ->0

# Chain pointing entirely backward 5<-4<-3<-2<-1 ... worst case for root 1
n = 6
gf = [i + 1 for i in range(1, n)]  # 2,3,4,5,6
gt = [i for i in range(1, n)]      # 1,2,3,4,5  => edges 2->1,3->2,...
print("backward chain:", getMinInversions(n, gf, gt))  # root at deepest gives 0

# Stress / performance: large line graph 1e5
import time
N = 100000
gf = list(range(1, N))   # 1..N-1
gt = list(range(2, N + 1))  # 2..N  forward chain 1->2->...->N
start = time.time()
r = getMinInversions(N, gf, gt)
print("large forward chain result:", r, "time %.3fs" % (time.time() - start))

# large star all pointing into center -> root center costs n-1, root leaf?
center = 1
gf = [i for i in range(2, N + 1)]
gt = [1] * (N - 1)   # all i->1
start = time.time()
r2 = getMinInversions(N, gf, gt)
print("large in-star result:", r2, "time %.3fs" % (time.time() - start))
