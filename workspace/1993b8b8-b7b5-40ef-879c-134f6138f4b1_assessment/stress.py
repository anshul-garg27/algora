import random, copy, time
from solution import Solution

def brute(grid):
    n = len(grid)
    def area_from(g):
        seen = [[False]*n for _ in range(n)]
        best = 0
        for i in range(n):
            for j in range(n):
                if g[i][j] == 1 and not seen[i][j]:
                    st = [(i,j)]; seen[i][j]=True; c=0
                    while st:
                        x,y=st.pop(); c+=1
                        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                            nx,ny=x+dx,y+dy
                            if 0<=nx<n and 0<=ny<n and g[nx][ny]==1 and not seen[nx][ny]:
                                seen[nx][ny]=True; st.append((nx,ny))
                    best=max(best,c)
        return best
    best = area_from(grid)
    zeros = [(i,j) for i in range(n) for j in range(n) if grid[i][j]==0]
    for (i,j) in zeros:
        g=copy.deepcopy(grid); g[i][j]=1
        best=max(best, area_from(g))
    return best

random.seed(1)
for t in range(3000):
    n=random.randint(1,5)
    grid=[[random.randint(0,1) for _ in range(n)] for _ in range(n)]
    exp=brute(copy.deepcopy(grid))
    got=Solution().largestIsland(copy.deepcopy(grid))
    if exp!=got:
        print("MISMATCH", grid, exp, got); break
else:
    print("All random tests passed")

# Performance: worst case checkerboard 500x500 (max zeros, max components)
n=500
big=[[(i+j)%2 for j in range(n)] for i in range(n)]
s=time.time()
r=Solution().largestIsland(big)
print("n=500 checkerboard ->", r, "in %.3fs"%(time.time()-s))

# all ones
big2=[[1]*n for _ in range(n)]
s=time.time()
r2=Solution().largestIsland(big2)
print("n=500 all-ones ->", r2, "in %.3fs"%(time.time()-s))
