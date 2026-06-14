"""Reference: TTLStore (count_active in O(log n)) + thread-safe RandomizedDict.
Both asked as standalone Uber rounds (SDE-4 Jan-2026 loop; SDE-2 LLD round).

TTLStore design (say out loud):
- put() timestamps strictly increase, but expire_at values arrive in ANY order
  => keep a SORTED list of (expire_at) for live keys via bisect-insert.
- Updating a key must remove its old expiry: bisect + list.pop is O(n) worst
  case; interviews accept it if you SAY the trade-off and offer the
  alternative (lazy deletion with a stale-counter per expiry, or an indexed
  BST/`sortedcontainers`). We implement bisect-remove: simple + correct.
- count_active(now) = len(live) - bisect_right(expiries, now)  ... careful:
  convention here = key is ACTIVE while now < expire_at (expires AT expire_at).

RandomizedDict design: LC-380 classic — dict key->idx + arrays; delete =
swap-with-last + pop; get_random = uniform index. All O(1) average.
"""
from __future__ import annotations

import bisect
import random
import threading


class TTLStore:
    def __init__(self) -> None:
        self._data: dict[str, tuple[object, int]] = {}  # key -> (value, expire_at)
        self._expiries: list[int] = []                  # sorted expire_at of live keys

    def put(self, key: str, value: object, expire_at: int) -> None:
        if key in self._data:
            old_exp = self._data[key][1]
            i = bisect.bisect_left(self._expiries, old_exp)
            self._expiries.pop(i)                       # remove stale expiry
        self._data[key] = (value, expire_at)
        bisect.insort(self._expiries, expire_at)

    def get(self, key: str, now: int) -> object | None:
        item = self._data.get(key)
        if item is None or now >= item[1]:              # expired AT expire_at
            return None
        return item[0]

    def count_active(self, now: int) -> int:
        # expiries <= now are dead under our convention (active while now < exp)
        return len(self._expiries) - bisect.bisect_right(self._expiries, now)


class RandomizedDict:
    def __init__(self) -> None:
        self._pos: dict[object, int] = {}
        self._keys: list[object] = []
        self._vals: list[object] = []
        self._lock = threading.Lock()   # follow-up: where are the races? see below

    def set(self, key: object, value: object) -> None:
        with self._lock:
            if key in self._pos:
                self._vals[self._pos[key]] = value
                return
            self._pos[key] = len(self._keys)
            self._keys.append(key)
            self._vals.append(value)

    def get(self, key: object) -> object | None:
        with self._lock:
            i = self._pos.get(key)
            return None if i is None else self._vals[i]

    def delete(self, key: object) -> bool:
        with self._lock:
            i = self._pos.pop(key, None)
            if i is None:
                return False
            last = len(self._keys) - 1
            if i != last:                # swap victim with last, then pop
                self._keys[i] = self._keys[last]
                self._vals[i] = self._vals[last]
                self._pos[self._keys[i]] = i
            self._keys.pop()
            self._vals.pop()
            return True

    def get_random(self) -> tuple[object, object]:
        with self._lock:
            if not self._keys:
                raise KeyError("empty")
            i = random.randrange(len(self._keys))
            return self._keys[i], self._vals[i]


# ---------------- tests ----------------

def main() -> None:
    s = TTLStore()
    s.put("a", 1, expire_at=10)
    s.put("b", 2, expire_at=5)
    s.put("c", 3, expire_at=20)
    assert s.get("a", now=4) == 1
    assert s.get("b", now=6) is None
    assert s.count_active(now=6) == 2          # a(10), c(20)
    assert s.count_active(now=15) == 1         # c
    s.put("a", 9, expire_at=30)                # update replaces old expiry
    assert s.get("a", now=25) == 9
    assert s.count_active(now=25) == 1         # only a (c died at 20)
    assert s.count_active(now=20) == 1         # boundary: c inactive AT 20
    assert s.count_active(now=19) == 2

    r = RandomizedDict()
    r.set("x", 1); r.set("y", 2); r.set("z", 3)
    assert r.get("y") == 2
    assert r.delete("y") is True
    assert r.get("y") is None
    assert r.delete("y") is False
    seen = {r.get_random()[0] for _ in range(300)}
    assert seen == {"x", "z"}
    r.set("x", 42)                              # update in place
    assert r.get("x") == 42

    print("PASS")


if __name__ == "__main__":
    main()


# ---------------- FOLLOW-UP ANSWERS ----------------
# RandomizedDict races without the lock:
#   delete's swap-with-last vs get_random's index read => get_random can read
#   an index that just shrank (IndexError) or return a key mid-swap. set vs
#   set on the same new key double-appends. One Lock fixes all; for read-heavy
#   loads discuss an RW lock; "GIL makes it safe" is FALSE for multi-step
#   invariants (dict+two lists must move together).
# Merge A+B (random over non-expired): uniform O(1) get_random + lazy expiry
#   conflict — expired entries pollute the array. Options: (a) amortized
#   cleanup on access (pop expired when drawn, redraw) => O(1) amortized but
#   worst-case spikes; (b) active-count array + O(log n). SAY the trade-off.
# 10M keys: stale expiry entries from updates are why we remove eagerly;
#   if using lazy deletion instead, track stale count and rebuild when >50%.
