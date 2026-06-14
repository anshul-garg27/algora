"""
UBER DSA MOCK #2 — 45 minutes — Robots in a Grid (Uber original)
==================================================================
(Repeated at Uber since Sep 2024 through 2026 across SDE-2/SDE-3/Senior
loops — an Uber-house question, not on LeetCode.)

You are given a 2D grid `location_map` of characters:
    'O' = robot, 'E' = empty, 'X' = blocker
Cells outside the grid count as blockers.

You are given query = [dist_left, dist_top, dist_bottom, dist_right]:
the MINIMUM required distance from a robot to the closest blocker in each
cardinal direction. (Distance = number of cells between robot and blocker,
counting the steps to reach the blocker cell/boundary.)

  find_robots(location_map, query) -> list[tuple[int, int]]
      Return coordinates (row, col) of all robots whose actual distances
      to the nearest blocker in each direction are >= the required ones.

Drive brute force first (per-robot scan), state its complexity, then the
optimized version (4 directional DP sweeps, O(M*N) total). The interviewer
expects BOTH, in that order.
"""

# ============== YOUR IMPLEMENTATION BELOW ==============


def find_robots(location_map: list[list[str]], query: list[int]) -> list[tuple[int, int]]:
    raise NotImplementedError


# ============== DEMO / ACCEPTANCE TESTS ==============

def main() -> None:
    grid = [
        list("OEEX"),
        list("XXOE"),
        list("EXOX"),
    ]
    # robot (0,0): left=1(boundary), top=1(boundary), bottom=1(X below), right=3(X at col3)
    # robot (1,2): left=1? (X at (1,1)) -> dist 1; top=3?(no blocker above till boundary)...
    # Work the example by hand before coding — interviewers made candidates do this.
    res = find_robots(grid, [1, 1, 1, 1])
    assert (0, 0) in res                       # every direction >= 1

    res2 = find_robots(grid, [2, 1, 1, 1])
    assert (0, 0) not in res2                  # left distance is only 1

    # single robot fully open
    grid2 = [list("EEE"), list("EOE"), list("EEE")]
    assert find_robots(grid2, [2, 2, 2, 2]) == [(1, 1)]
    assert find_robots(grid2, [3, 2, 2, 2]) == []

    print("PASS")


if __name__ == "__main__":
    main()
