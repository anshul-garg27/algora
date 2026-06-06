import random
import threading
from typing import Optional


class RandomizedSet:
    """
    Supports insert / delete / get_random in O(1) average time.

    Core idea: keep a dynamic array (values) for O(1) random access,
    and a hash map (index_of) mapping value -> its index in the array.
    Deletion in O(1) is achieved by the "swap with last, pop" trick.
    """

    def __init__(self, seed: Optional[int] = None) -> None:
        self._values = []            # contiguous storage; enables O(1) random index
        self._index_of = {}          # val -> position in self._values
        self._rng = random.Random(seed)
        self._lock = threading.RLock()  # one consistent concurrency model

    def insert(self, val: int) -> bool:
        """Insert val. Returns True if newly added, False if it was already present."""
        with self._lock:
            if val in self._index_of:          # validate / dedupe at boundary
                return False
            self._index_of[val] = len(self._values)
            self._values.append(val)
            return True

    def delete(self, val: int) -> bool:
        """Remove val if present. Returns True if removed, False if absent (no-op)."""
        with self._lock:
            if val not in self._index_of:      # absent -> defined outcome, no crash
                return False
            idx = self._index_of[val]
            last_idx = len(self._values) - 1
            last_val = self._values[last_idx]

            # Move the last element into the hole, then pop the tail.
            self._values[idx] = last_val
            self._index_of[last_val] = idx

            self._values.pop()
            del self._index_of[val]
            return True

    def get_random(self) -> int:
        """Return a uniformly random element. Raises if empty."""
        with self._lock:
            if not self._values:
                raise IndexError("get_random() called on empty structure")
            i = self._rng.randrange(len(self._values))
            return self._values[i]

    def __len__(self) -> int:
        with self._lock:
            return len(self._values)

    def __contains__(self, val: int) -> bool:
        with self._lock:
            return val in self._index_of


if __name__ == "__main__":
    s = RandomizedSet(seed=42)

    # --- basic inserts ---
    assert s.insert(10) is True
    assert s.insert(20) is True
    assert s.insert(30) is True

    # --- duplicate insert -> rejected, no corruption ---
    assert s.insert(10) is False
    assert len(s) == 3

    # --- delete existing (middle element triggers swap-with-last) ---
    assert s.delete(20) is True
    assert 20 not in s
    assert len(s) == 2

    # --- delete non-existing -> defined no-op, never crashes ---
    assert s.delete(999) is False

    # --- invariant check after swap: index map still consistent ---
    for v in list(s._index_of.keys()):
        assert s._values[s._index_of[v]] == v

    # --- get_random only returns valid live elements ---
    seen = set()
    for _ in range(1000):
        seen.add(s.get_random())
    assert seen == {10, 30}, seen

    # --- uniformity sanity check (~50/50) ---
    s2 = RandomizedSet(seed=7)
    for v in (1, 2):
        s2.insert(v)
    counts = {1: 0, 2: 0}
    for _ in range(100000):
        counts[s2.get_random()] += 1
    ratio = counts[1] / 100000
    assert 0.47 < ratio < 0.53, counts

    # --- empty structure get_random -> explicit error ---
    empty = RandomizedSet()
    try:
        empty.get_random()
        raise AssertionError("expected IndexError")
    except IndexError:
        pass

    # --- delete down to empty, then reinsert (lifecycle edge) ---
    assert s.delete(10) is True
    assert s.delete(30) is True
    assert len(s) == 0
    assert s.insert(99) is True
    assert s.get_random() == 99

    print("All assertions passed.")
    print("Uniformity counts (~50/50):", counts)
