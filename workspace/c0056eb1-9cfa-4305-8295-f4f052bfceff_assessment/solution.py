import sys
from collections import deque


def solve(input_str):
    data = input_str.split()
    idx = 0
    n = int(data[idx]); idx += 1

    if n <= 0:
        return ""
    # adjacency: for neighbor entry store (neighbor, cost_to_go_toward_neighbor)
    # cost 0 if real edge points from current node -> neighbor (away from root direction)
    # cost 1 if real edge is neighbor -> current (needs reversal to traverse outward)
    adj = [[] for _ in range(n)]
    for _ in range(n - 1):
        u = int(data[idx]); v = int(data[idx + 1]); idx += 2
        adj[u].append((v, 0))  # going u->v matches real edge: free
        adj[v].append((u, 1))  # going v->u opposes real edge: 1 reversal

    answer = [0] * n

    # ---- Pass 1: BFS from node 0 to compute answer[0] and a rooted order ----
    visited = [False] * n
    order = []          # nodes in BFS order
    parent = [-1] * n
    visited[0] = True
    dq = deque([0])
    base = 0
    while dq:
        node = dq.popleft()
        order.append(node)
        for nxt, w in adj[node]:
            if not visited[nxt]:
                visited[nxt] = True
                parent[nxt] = node
                base += w           # cost to extend reach root->...->nxt
                dq.append(nxt)
    answer[0] = base

    # ---- Pass 2: reroot using BFS order (parents before children) ----
    # For child v of u across an edge with outward-cost w (u->v traversal):
    #   moving root from u to v: gain w (was needed), lose (1-w) (reverse edge now needed)
    #   answer[v] = answer[u] - w + (1 - w)
    for u in order:
        for v, w in adj[u]:
            if parent[v] == u:      # v is child of u in the rooted tree
                answer[v] = answer[u] - w + (1 - w)

    return " ".join(map(str, answer))


if __name__ == "__main__":
    print(solve(sys.stdin.read()))
