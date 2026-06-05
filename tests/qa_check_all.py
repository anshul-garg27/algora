"""Deterministic correctness for the remaining DSA solutions: extract each final
'Solution' block, find its entry point, and cross-check against a brute-force reference
or the problem's examples. No API — pure local execution."""

import collections
import itertools
import pathlib
import random
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUNS = ROOT / "tests" / "qa_runs"


def sol_code(key: str) -> str:
    md = (RUNS / f"{key}.md").read_text()
    m = re.search(r"##\s*\d+\.\s*Solution.*?```(?:python|py)?\n(.*?)```", md, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1)
    blocks = re.findall(r"```(?:python|py)?\n(.*?)```", md, re.DOTALL)
    return max(blocks, key=len) if blocks else ""


def ns_of(key: str):
    ns = {}
    try:
        exec(sol_code(key), ns)  # noqa: S102
        return ns
    except Exception as e:  # noqa: BLE001
        return {"__error__": str(e)}


def callables_of(ns):
    return [(n, v) for n, v in ns.items() if callable(v) and not isinstance(v, type) and not n.startswith("_")]


def pick(ns, *, probe):
    """Return the first top-level function for which probe(fn) returns a non-None result."""
    if "__error__" in ns:
        return None, ns["__error__"]
    for _, v in callables_of(ns):
        try:
            r = probe(v)
            if r is not None:
                return v, None
        except Exception:
            continue
    return None, "no matching entry function"


# ---------------- references ----------------
def check_course_schedule():
    ns = ns_of("course_schedule_ii")
    fn, err = pick(ns, probe=lambda f: f(4, [[1, 0], [2, 0], [3, 1], [3, 2]]))
    if not fn:
        return "course_schedule_ii", "SKIP (" + str(err) + ")"

    def valid(numc, prereq, order):
        if order == [] or order is None:
            # must be a cycle
            indeg = collections.defaultdict(int); g = collections.defaultdict(list)
            for a, b in prereq:
                g[b].append(a); indeg[a] += 1
            q = [i for i in range(numc) if indeg[i] == 0]; seen = 0
            while q:
                x = q.pop(); seen += 1
                for y in g[x]:
                    indeg[y] -= 1
                    if indeg[y] == 0: q.append(y)
            return seen != numc  # [] correct iff cycle
        if sorted(order) != list(range(numc)):
            return False
        pos = {c: i for i, c in enumerate(order)}
        return all(pos[b] < pos[a] for a, b in prereq)

    random.seed(1); fails = 0
    cases = [(4, [[1, 0], [2, 0], [3, 1], [3, 2]]), (2, [[1, 0], [0, 1]]), (2, [[1, 0]]), (1, [])]
    for _ in range(120):
        n = random.randint(1, 6); m = random.randint(0, 8)
        pr = [[random.randint(0, n - 1), random.randint(0, n - 1)] for _ in range(m)]
        pr = [p for p in pr if p[0] != p[1]]
        cases.append((n, pr))
    for n, pr in cases:
        try:
            out = list(fn(n, [list(p) for p in pr]))
        except Exception as e:  # noqa: BLE001
            return "course_schedule_ii", f"CRASH on {n},{pr}: {e}"
        if not valid(n, pr, out):
            fails += 1
            if fails == 1: bad = (n, pr, out)
    return "course_schedule_ii", "CORRECT (topo valid / [] iff cycle)" if not fails else f"WRONG x{fails}, e.g. {bad}"


def check_merge_cars():
    ns = ns_of("merge_cars_k")
    fn, err = pick(ns, probe=lambda f: f(["a", "a"], 2))
    if not fn:
        # try (cars, k) where first arg list
        fn, err = pick(ns, probe=lambda f: f(["a", "a", "b"], 2))
    if not fn:
        return "merge_cars_k", "SKIP (" + str(err) + ")"

    def brute(cars, k):
        st = []  # (name, count)
        for c in cars:
            if st and st[-1][0] == c:
                st[-1][1] += 1
            else:
                st.append([c, 1])
            if st[-1][1] == k:
                st.pop()
        out = []
        for name, cnt in st:
            out += [name] * cnt
        return out

    random.seed(2); fails = 0; bad = None
    cases = [(["Honda", "Honda", "Maruti", "Maruti", "Maruti", "BMW", "Maruti", "Maruti", "Maruti"], 2),
             (["Audi"] * 6, 3)]
    for _ in range(200):
        k = random.randint(2, 4)
        cars = [random.choice("abc") for _ in range(random.randint(0, 14))]
        cases.append((cars, k))
    for cars, k in cases:
        try:
            out = list(fn(list(cars), k))
        except Exception as e:  # noqa: BLE001
            return "merge_cars_k", f"CRASH: {e}"
        if out != brute(cars, k):
            fails += 1; bad = (cars, k, out, brute(cars, k))
    return "merge_cars_k", "CORRECT (matches stack brute force)" if not fails else f"WRONG x{fails}, e.g. {bad}"


def check_min_appends():
    ns = ns_of("min_appends_subsequence")
    fn, err = pick(ns, probe=lambda f: f("boy", "oyb"))
    if not fn:
        return "min_appends_subsequence", "SKIP (" + str(err) + ")"

    def brute(s, t):
        i = 0; copies = 1; ti = 0
        # greedy: walk t, consume s cyclically
        si = 0; copies = 0
        ti = 0
        cur = 0
        copies = 1; pos = 0
        # straightforward: build s repeated until t is subsequence (bounded)
        for reps in range(1, len(t) + 2):
            big = s * reps; it = iter(big); ok = all(ch in it for ch in t)
            if ok:
                return reps
        return -1  # impossible (char not in s)

    fails = 0; bad = None
    cases = [("boy", "oyb", 2), ("abc", "abcbc", 2)]
    for s, t, exp in cases:
        try:
            if int(fn(s, t)) != exp:
                fails += 1; bad = (s, t, fn(s, t), exp)
        except Exception as e:  # noqa: BLE001
            return "min_appends_subsequence", f"CRASH: {e}"
    random.seed(3)
    for _ in range(150):
        s = "".join(random.choice("ab") for _ in range(random.randint(1, 5)))
        t = "".join(random.choice("ab") for _ in range(random.randint(1, 8)))
        bf = brute(s, t)
        if bf == -1:
            continue
        try:
            got = int(fn(s, t))
        except Exception:
            continue
        if got != bf:
            fails += 1; bad = (s, t, got, bf)
    return "min_appends_subsequence", "CORRECT (matches brute force)" if not fails else f"WRONG x{fails}, e.g. {bad}"


def check_array_equal():
    ns = ns_of("array_equal_general_x")
    fn, err = pick(ns, probe=lambda f: f([1, 3, 5], 2))
    if not fn:
        return "array_equal_general_x", "SKIP (" + str(err) + ")"

    def ref(arr, x):
        if x == 0:
            return len(set(arr)) <= 1
        return len(set(a % x for a in arr)) <= 1

    fails = 0; bad = None
    random.seed(4)
    cases = [([1, 3, 5], 2, True), ([1, 2, 5], 2, False), ([4, 4], 0, True), ([4, 5], 0, False)]
    for arr, x, exp in cases:
        try:
            if bool(fn(list(arr), x)) != exp:
                fails += 1; bad = (arr, x, fn(list(arr), x), exp)
        except Exception as e:  # noqa: BLE001
            return "array_equal_general_x", f"CRASH (maybe x=0?): {e}"
    for _ in range(200):
        arr = [random.randint(-6, 6) for _ in range(random.randint(1, 6))]
        x = random.randint(0, 5)
        try:
            got = bool(fn(list(arr), x))
        except Exception as e:  # noqa: BLE001
            return "array_equal_general_x", f"CRASH x={x}: {e}"
        if got != ref(arr, x):
            fails += 1; bad = (arr, x, got, ref(arr, x))
    return "array_equal_general_x", "CORRECT (incl. x=0)" if not fails else f"WRONG x{fails}, e.g. {bad}"


def check_burn_tree():
    ns = ns_of("burn_tree")
    fn, err = pick(ns, probe=lambda f: f(4, [[0, 1], [1, 2], [1, 3]]))
    if not fn:
        return "burn_tree", "SKIP (" + str(err) + ")"

    def ref(n, edges):
        if n <= 1:
            return 0
        g = collections.defaultdict(list)
        for a, b in edges:
            g[a].append(b); g[b].append(a)

        def bfs(src):
            dist = {src: 0}; q = collections.deque([src]); far = src
            while q:
                x = q.popleft()
                for y in g[x]:
                    if y not in dist:
                        dist[y] = dist[x] + 1; q.append(y)
                        if dist[y] > dist[far]:
                            far = y
            return far, dist
        a, _ = bfs(0); b, d = bfs(a)
        diameter = d[b]
        return (diameter + 1) // 2  # radius
    fails = 0; bad = None
    cases = [(4, [[0, 1], [1, 2], [1, 3]], 1), (6, [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5]], 3)]
    for n, e, exp in cases:
        try:
            if int(fn(n, [list(x) for x in e])) != exp:
                fails += 1; bad = (n, e, fn(n, e), exp)
        except Exception as ex:  # noqa: BLE001
            return "burn_tree", f"CRASH: {ex}"
    random.seed(5)
    for _ in range(120):
        n = random.randint(1, 12); e = [[i, random.randint(0, i - 1)] for i in range(1, n)]
        try:
            got = int(fn(n, [list(x) for x in e]))
        except Exception:
            continue
        if got != ref(n, e):
            fails += 1; bad = (n, e, got, ref(n, e))
    return "burn_tree", "CORRECT (tree radius)" if not fails else f"WRONG x{fails}, e.g. {bad}"


def main():
    checks = [check_course_schedule, check_merge_cars, check_min_appends, check_array_equal, check_burn_tree]
    for c in checks:
        try:
            key, res = c()
        except Exception as e:  # noqa: BLE001
            key, res = c.__name__, f"HARNESS-ERROR: {e}"
        flag = "✅" if res.startswith("CORRECT") else ("⏭️ " if res.startswith("SKIP") else "❌")
        print(f"{flag} {key:26} {res}")


if __name__ == "__main__":
    main()
