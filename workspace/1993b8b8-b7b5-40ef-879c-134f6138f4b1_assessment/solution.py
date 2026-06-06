import sys
from collections import deque

class Solution:
    def largestIsland(self, grid):
        n = len(grid)
        if n == 0:
            return 0

        # area[id] = size of component labeled `id` (ids start at 2)
        area = {}
        next_id = 2
        DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))

        # 1) Label each island via iterative BFS (safe vs recursion limits at n=500)
        for i in range(n):
            for j in range(n):
                if grid[i][j] == 1:
                    q = deque([(i, j)])
                    grid[i][j] = next_id
                    size = 0
                    while q:
                        x, y = q.popleft()
                        size += 1
                        for dx, dy in DIRS:
                            nx, ny = x + dx, y + dy
                            if 0 <= nx < n and 0 <= ny < n and grid[nx][ny] == 1:
                                grid[nx][ny] = next_id
                                q.append((nx, ny))
                    area[next_id] = size
                    next_id += 1

        # If there were no zeros, the answer is simply the biggest component.
        best = max(area.values()) if area else 0

        # 2) For each water cell, combine distinct neighboring components + itself.
        has_zero = False
        for i in range(n):
            for j in range(n):
                if grid[i][j] == 0:
                    has_zero = True
                    seen = set()
                    total = 1  # the flipped cell itself
                    for dx, dy in DIRS:
                        nx, ny = i + dx, j + dy
                        if 0 <= nx < n and 0 <= ny < n:
                            cid = grid[nx][ny]
                            if cid >= 2 and cid not in seen:
                                seen.add(cid)
                                total += area[cid]
                    if total > best:
                        best = total

        # If the whole grid is land (no zero), best already == n*n.
        # If grid is all water, has_zero True and best == 1.
        return best


# ---- stdin/stdout harness ----
def main():
    data = sys.stdin.read().strip()
    if not data:
        return
    # Accept Python-literal grid like [[1,0],[0,1]]
    import ast
    grid = ast.literal_eval(data)
    print(Solution().largestIsland(grid))


if __name__ == "__main__":
    main()
