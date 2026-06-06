import sys
from collections import deque


def getMinInversions(g_nodes, g_from, g_to):
    # build undirected graph, weight 0 = same as arrow, 1 = needs reversing
    graph = [[] for _ in range(g_nodes + 1)]
    for u, v in zip(g_from, g_to):
        graph[u].append((v, 0))
        graph[v].append((u, 1))

    parent = [0] * (g_nodes + 1)
    seen = [False] * (g_nodes + 1)
    ans = [0] * (g_nodes + 1)

    # bfs from node 1 to get cost when 1 is root
    seen[1] = True
    total = 0
    order = []
    q = deque([1])
    while q:
        u = q.popleft()
        order.append(u)
        for v, w in graph[u]:
            if not seen[v]:
                seen[v] = True
                parent[v] = u
                total += w
                q.append(v)
    ans[1] = total

    # re-root: only the edge between parent and child changes
    for u in order:
        for v, w in graph[u]:
            if v != 1 and parent[v] == u:
                ans[v] = ans[u] + 1 - 2 * w

    return min(ans[1:])


if __name__ == '__main__':
    data = sys.stdin.buffer.read().split()
    pos = 0
    g_nodes = int(data[pos]); pos += 1
    g_edges = int(data[pos]); pos += 1
    g_from = [0] * g_edges
    g_to = [0] * g_edges
    for i in range(g_edges):
        g_from[i] = int(data[pos]); pos += 1
        g_to[i] = int(data[pos]); pos += 1
    print(getMinInversions(g_nodes, g_from, g_to))
