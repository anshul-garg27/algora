"""Deterministic correctness checks (no API) on the generated trap solutions, by
extracting their code from the transcript and cross-checking against brute force."""

import pathlib
import random
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUNS = ROOT / "tests" / "qa_runs"


def all_code(md: str):
    return re.findall(r"```(?:python|py)?\n(.*?)```", md, re.DOTALL)


def solution_code(md: str) -> str:
    """The canonical final solution is the code block under '## N. Solution'."""
    m = re.search(r"##\s*\d+\.\s*Solution.*?```(?:python|py)?\n(.*?)```", md, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1)
    blocks = all_code(md)
    return max(blocks, key=len) if blocks else ""


def find_namespace(md: str):
    """Exec the self-contained final solution block."""
    ns = {}
    code = solution_code(md)
    if not code.strip():
        return None, "no solution block found"
    try:
        exec(code, ns)  # noqa: S102 - local algorithmic code from our own agent
    except Exception as e:  # noqa: BLE001
        return None, f"exec failed: {e}"
    return ns, code


# ---------- DSU + remove_edge ----------
class BruteGraph:
    def __init__(self, n):
        self.n = n
        self.adj = [set() for _ in range(n + 1)]

    def add_edge(self, u, v):
        self.adj[u].add(v)
        self.adj[v].add(u)

    def remove_edge(self, u, v):
        self.adj[u].discard(v)
        self.adj[v].discard(u)

    def count(self):
        seen = [False] * (self.n + 1)
        c = 0
        for s in range(1, self.n + 1):
            if not seen[s]:
                c += 1
                st = [s]
                seen[s] = True
                while st:
                    x = st.pop()
                    for y in self.adj[x]:
                        if not seen[y]:
                            seen[y] = True
                            st.append(y)
        return c


def check_dsu():
    md = (RUNS / "dsu_remove_components.md").read_text()
    ns, _ = find_namespace(md)
    if ns is None:
        return "EXEC-FAIL", ns
    # find a class with the three methods
    cls = None
    for v in ns.values():
        if isinstance(v, type) and all(hasattr(v, m) for m in ("add_edge", "remove_edge", "count_components")):
            cls = v
            break
    if cls is None:
        return "NO-CLASS (couldn't find add_edge/remove_edge/count_components)", None
    random.seed(7)
    for trial in range(200):
        n = random.randint(2, 8)
        try:
            g = cls(n)
        except Exception:
            try:
                g = cls(n=n)
            except Exception as e:  # noqa: BLE001
                return f"CONSTRUCT-FAIL: {e}", cls.__name__
        b = BruteGraph(n)
        for _ in range(random.randint(1, 20)):
            op = random.choice(["add", "add", "remove", "count"])
            u, v = random.randint(1, n), random.randint(1, n)
            if u == v:
                continue
            if op == "add":
                g.add_edge(u, v)
                b.add_edge(u, v)
            elif op == "remove":
                g.remove_edge(u, v)
                b.remove_edge(u, v)
            else:
                got = g.count_components()
                exp = b.count()
                if got != exp:
                    return (f"WRONG at trial {trial}: got {got}, expected {exp} "
                            f"(class {cls.__name__}) — likely the DSU-can't-remove trap"), cls.__name__
    return "CORRECT (200 random add/remove/count trials match brute force)", cls.__name__


# ---------- Closest Palindrome ----------
def brute_closest_pal(s: str) -> str:
    n = int(s)
    best = None
    # search outward; bounded window is fine for small n
    for d in range(0, 200000):
        for cand in ({n - d, n + d} if d else {n}):
            if cand < 0:
                continue
            cs = str(cand)
            if cs == cs[::-1] and cand != n:  # closest DIFFERENT palindrome (per "1"->"0")
                if best is None:
                    best = cand
        if best is not None:
            # also consider the tie on the other side at same d
            other = n + (best - n) * -1
            os_ = str(other)
            if other >= 0 and os_ == os_[::-1] and other != n and abs(other - n) == abs(best - n):
                best = min(best, other)
            return str(best)
    return str(best)


def check_palindrome():
    md = (RUNS / "closest_palindrome.md").read_text()
    ns, _ = find_namespace(md)
    if ns is None:
        return "EXEC-FAIL"
    # find a callable str->str
    fn = None
    for name, v in ns.items():
        if callable(v) and not isinstance(v, type) and not name.startswith("_"):
            try:
                r = v("123")
                if isinstance(r, str):
                    fn = v
                    break
            except Exception:
                continue
    if fn is None:
        return "NO-FUNC (couldn't find a str->str solver)"
    fails = []
    # spot examples + classic edge cases (brute-forced expectations for small ones)
    cases = ["123", "1", "10", "11", "99", "100", "1000", "9", "808", "12921", "13", "21", "1213"]
    for c in cases:
        try:
            got = str(fn(c))
        except Exception as e:  # noqa: BLE001
            fails.append(f"{c}: crashed {e}")
            continue
        exp = brute_closest_pal(c)
        if got != exp:
            fails.append(f"n={c}: got {got}, brute={exp}")
    return "CORRECT (all example + edge cases match brute force)" if not fails else "WRONG: " + "; ".join(fails)


if __name__ == "__main__":
    print("=== DSU + remove_edge ===")
    r, cls = check_dsu()
    print(" ", r)
    print("=== Closest Palindrome ===")
    print(" ", check_palindrome())
