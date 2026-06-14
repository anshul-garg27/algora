"""Reference: File System APIs (mkdir, cd, pwd) with wildcard cd.
Uber machine-coding round, asked 4x in the last year. ~35 min of writing.

Design notes (say these out loud in the interview):
- Directory tree of Node objects; FileSystem holds root + cwd reference.
- cd resolves to a CANDIDATE node first and only commits cwd on full success
  (requirement: no partial moves).
- Wildcard: BFS/DFS over matching paths; success iff exactly one full match.
- Complexity: mkdir/cd O(depth); wildcard cd O(matching paths) worst case
  O(branching^wildcards * depth).

Follow-up (concurrency) answers at the bottom.
"""
from __future__ import annotations

import threading


class Node:
    __slots__ = ("name", "parent", "children")

    def __init__(self, name: str, parent: "Node | None") -> None:
        self.name = name
        self.parent = parent
        self.children: dict[str, Node] = {}


class FileSystem:
    def __init__(self) -> None:
        self._root = Node("", None)
        self._cwd = self._root
        # One coarse lock: tree mutations + cwd moves are tiny critical
        # sections; per-node locking is deadlock bait at this scale.
        self._lock = threading.RLock()

    # ---------------- public API ----------------

    def pwd(self) -> str:
        with self._lock:
            parts: list[str] = []
            node = self._cwd
            while node.parent is not None:
                parts.append(node.name)
                node = node.parent
            return "/" + "/".join(reversed(parts))

    def mkdir(self, path: str) -> bool:
        segs = self._segments(path)
        if segs is None or any(s in ("*", ".", "..") for s in segs):
            return False
        with self._lock:
            node = self._root if path.startswith("/") else self._cwd
            for s in segs:
                node = node.children.setdefault(s, Node(s, node))
            return True

    def cd(self, path: str) -> bool:
        segs = self._segments(path)
        if segs is None:
            return False
        with self._lock:
            start = self._root if path.startswith("/") else self._cwd
            matches = self._resolve(start, segs)
            if len(matches) != 1:
                return False  # zero or ambiguous -> stay put
            self._cwd = matches[0]
            return True

    # ---------------- internals ----------------

    @staticmethod
    def _segments(path: str) -> list[str] | None:
        if not path:
            return None
        segs = [s for s in path.split("/") if s != ""]
        return segs

    def _resolve(self, start: Node, segs: list[str]) -> list[Node]:
        """All nodes reachable from `start` along segs ('.', '..', '*' aware)."""
        frontier = [start]
        for s in segs:
            nxt: list[Node] = []
            for node in frontier:
                if s == ".":
                    nxt.append(node)
                elif s == "..":
                    nxt.append(node.parent or node)  # '..' at root stays at root
                elif s == "*":
                    nxt.extend(node.children.values())
                elif s in node.children:
                    nxt.append(node.children[s])
            # dedupe (diamond via '..' patterns)
            seen: set[int] = set()
            frontier = [n for n in nxt if id(n) not in seen and not seen.add(id(n))]
            if not frontier:
                return []
        return frontier


# ---------------- tests (same as the mock's acceptance tests) ----------------

def main() -> None:
    fs = FileSystem()
    assert fs.pwd() == "/"
    assert fs.mkdir("/a/b/c") is True
    assert fs.mkdir("/a/b2/c") is True
    assert fs.cd("/a/b") is True
    assert fs.pwd() == "/a/b"
    assert fs.cd("c") is True
    assert fs.pwd() == "/a/b/c"
    assert fs.cd("../../b2") is True
    assert fs.pwd() == "/a/b2"
    assert fs.cd("/a/*/c") is False            # ambiguous
    assert fs.pwd() == "/a/b2"                 # no partial move
    assert fs.mkdir("/a/b/unique") is True
    assert fs.cd("/a/*/unique") is True
    assert fs.pwd() == "/a/b/unique"
    assert fs.cd("/nope/x") is False
    assert fs.cd("..") is True
    assert fs.pwd() == "/a/b"
    assert fs.cd("/") is True and fs.pwd() == "/"
    assert fs.cd("..") is True and fs.pwd() == "/"   # stated convention
    print("PASS")


if __name__ == "__main__":
    main()


# ---------------- FOLLOW-UP ANSWERS (memorize the reasoning) ----------------
# Q: Multiple threads call mkdir/cd concurrently — what breaks?
# A: (1) dict mutation races on children during mkdir;
#    (2) cd reading the tree while mkdir mutates it;
#    (3) THE SUBTLE ONE: cwd is shared state — two threads cd-ing fight over
#        one cwd. Real fix: cwd belongs to a *session*, not the FileSystem.
#        Split: FileSystem (tree + lock) and Session (cwd per client).
# Q: Lock granularity?
# A: One RLock is right at this scale: critical sections are micro-ops.
#    RW-lock if reads dominate. Per-node locks: lock-ordering complexity
#    for '..' traversal — say "not worth it" with confidence.
# Q: ls with wildcard?
# A: _resolve() already returns all matches — ls is sorted([n.name for n in
#    matches' children]). Separation of resolve/act pays off here.
