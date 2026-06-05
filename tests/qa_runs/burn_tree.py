from collections import deque

def min_burn_time(n, edges):
    """Minimum time to burn the whole tree from an optimally chosen start node.
    Equals the tree radius = ceil(diameter / 2). O(N) via two BFS passes."""
    if n <= 1:
        return 0  # single/empty node: nothing to spread to

    # Build adjacency list
    adj = [[] for _ in range(n)]
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)

    def bfs(src):
        """Return (farthest_node, distance_to_it) using ITERATIVE BFS
        so a long path (depth up to 1e5) can't overflow the stack."""
        dist = [-1] * n
        dist[src] = 0
        q = deque([src])
        far_node, far_dist = src, 0
        while q:
            node = q.popleft()
            for nxt in adj[node]:
                if dist[nxt] == -1:               # unvisited
                    dist[nxt] = dist[node] + 1
                    if dist[nxt] > far_dist:
                        far_dist, far_node = dist[nxt], nxt
                    q.append(nxt)
        return far_node, far_dist

    # Step 1: from any node, the farthest node u is a diameter endpoint.
    u, _ = bfs(0)
    # Step 2: from u, the farthest distance IS the diameter.
    _, diameter = bfs(u)

    # Radius = ceil(diameter / 2)  -> the burn time from the optimal center.
    return (diameter + 1) // 2
