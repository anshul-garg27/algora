from collections import deque

def findOrder(numCourses, prerequisites):
    adj = [[] for _ in range(numCourses)]
    indeg = [0] * numCourses
    for a, b in prerequisites:          # b before a  =>  edge b -> a
        adj[b].append(a)
        indeg[a] += 1

    q = deque(i for i in range(numCourses) if indeg[i] == 0)
    order = []
    while q:
        node = q.popleft()
        order.append(node)
        for nxt in adj[node]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                q.append(nxt)

    return order if len(order) == numCourses else []


def is_valid(numCourses, prereqs, order):
    if not order:
        return None  # claims impossible
    if sorted(order) != list(range(numCourses)):
        return False
    pos = {c: i for i, c in enumerate(order)}
    for a, b in prereqs:
        if pos[b] > pos[a]:
            return False
    return True

# Sample tests
print(findOrder(4, [[1,0],[2,0],[3,1],[3,2]]))
print(findOrder(2, [[1,0],[0,1]]))
print(findOrder(1, []))
print(findOrder(3, []))
print(findOrder(2, [[0,0]]))  # self-loop cycle

# Stress / random validation against brute checker
import random
def brute(numCourses, prereqs):
    done = [False]*numCourses
    pre = [[] for _ in range(numCourses)]
    for a,b in prereqs: pre[a].append(b)
    order=[]
    changed=True
    while changed:
        changed=False
        for c in range(numCourses):
            if not done[c] and all(done[p] for p in pre[c]):
                done[c]=True; order.append(c); changed=True
    return order if len(order)==numCourses else []

random.seed(1)
for _ in range(3000):
    n = random.randint(1,7)
    edges=set()
    m=random.randint(0,10)
    for _ in range(m):
        a=random.randint(0,n-1); b=random.randint(0,n-1)
        if a!=b: edges.add((a,b))
    edges=[list(e) for e in edges]
    res=findOrder(n,edges)
    bru=brute(n,edges)
    # both must agree on feasibility
    if (len(res)==n) != (len(bru)==n):
        print("FEASIBILITY MISMATCH", n, edges, res, bru); break
    if res:
        v=is_valid(n,edges,res)
        if v is False:
            print("INVALID ORDER", n, edges, res); break
else:
    print("ALL RANDOM TESTS PASSED")

# Max stress timing
import time
N=2000
big=[]
for i in range(1,N):
    big.append([i, i-1])  # chain
t=time.time()
r=findOrder(N,big)
print("chain ok:", len(r)==N, "time:", round(time.time()-t,4))
