import heapq
import threading


class TTLStore:
    """TTL key-value store with lazy expiration and O(1) active-count tracking.

    Time model: every public op carries `now` (strictly increasing). The store
    tracks the latest observed time and lazily evicts expired keys.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._store = {}            # key -> (value, expiry)
        self._heap = []             # (expiry, key) min-heap for lazy purge
        self._active = 0            # count of currently-active unique keys
        self._now = 0               # latest observed timestamp

    # ---- internal ----
    def _advance(self, now):
        if now < self._now:
            raise ValueError(f"timestamp went backwards: {now} < {self._now}")
        self._now = now
        self._purge()

    def _purge(self):
        # Evict everything that has expired at/at-or-before _now.
        while self._heap and self._heap[0][0] <= self._now:
            expiry, key = heapq.heappop(self._heap)
            entry = self._store.get(key)
            # Stale heap node: key updated/deleted -> expiry no longer matches.
            if entry is not None and entry[1] == expiry:
                del self._store[key]
                self._active -= 1

    def _is_active(self, key):
        entry = self._store.get(key)
        return entry is not None and entry[1] > self._now

    # ---- public API ----
    def put(self, key, value, expiration_ts, now):
        if key is None:
            raise ValueError("key must not be None")
        if expiration_ts <= now:
            raise ValueError("expiration must be in the future")
        with self._lock:
            self._advance(now)
            existed_active = self._is_active(key)
            self._store[key] = (value, expiration_ts)
            heapq.heappush(self._heap, (expiration_ts, key))
            if not existed_active:
                self._active += 1

    def get(self, key, now):
        with self._lock:
            self._advance(now)
            entry = self._store.get(key)
            if entry is not None and entry[1] > self._now:
                return entry[0]
            return None

    def delete(self, key, now):
        with self._lock:
            self._advance(now)
            if self._is_active(key):
                del self._store[key]      # heap node becomes stale, purged later
                self._active -= 1
                return True
            return False

    def count_active_keys(self, now):
        with self._lock:
            self._advance(now)
            return self._active

    def count_active_key(self, key, now):
        with self._lock:
            self._advance(now)
            return 1 if self._is_active(key) else 0


if __name__ == "__main__":
    s = TTLStore()
    # basic put/get
    s.put("a", 1, expiration_ts=10, now=0)
    s.put("b", 2, expiration_ts=5, now=1)
    assert s.get("a", now=2) == 1
    assert s.count_active_keys(now=2) == 2

    # update key resets expiry; active count unchanged
    s.put("a", 99, expiration_ts=20, now=3)
    assert s.get("a", now=3) == 99
    assert s.count_active_keys(now=3) == 2

    # lazy expiration: b expires at 5
    assert s.get("b", now=6) is None
    assert s.count_active_keys(now=6) == 1
    assert s.count_active_key("b", now=6) == 0
    assert s.count_active_key("a", now=6) == 1

    # delete
    assert s.delete("a", now=7) is True
    assert s.delete("a", now=7) is False      # already gone
    assert s.count_active_keys(now=7) == 0

    # boundary / invalid inputs
    try:
        s.put("x", 0, expiration_ts=7, now=8)   # expiry <= now
        assert False
    except ValueError:
        pass
    try:
        s.get("a", now=5)                        # time went backwards
        assert False
    except ValueError:
        pass

    # re-add after expiry, stale heap node must not double-decrement
    s.put("b", 7, expiration_ts=100, now=9)
    assert s.count_active_keys(now=10) == 1
    # the old stale (5,'b') node is still in heap; purging must ignore it
    assert s.count_active_keys(now=50) == 1
    assert s.get("b", now=50) == 7

    print("ALL TESTS PASSED")
