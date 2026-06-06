import threading
import random
from typing import Any, Optional, Tuple


class Entry:
    """A key-value pair stored in the backing array."""
    __slots__ = ("key", "value")

    def __init__(self, key: Any, value: Any):
        self.key = key
        self.value = value


class ConcurrentRandomizedMap:
    """
    Thread-safe map supporting average O(1):
      set(key, value), get(key), delete(key), getRandom()

    Internal representation:
      - _entries: list (dynamic array) of Entry objects  -> enables O(1) getRandom by index
      - _index:   dict key -> position in _entries        -> enables O(1) get/locate
      Deletion uses 'swap with last' to keep the array dense in O(1).

    Concurrency:
      - A single ReadWriteLock guards both structures together so they never diverge.
      - Reads (get, getRandom) take the shared read lock (concurrent readers allowed).
      - Writes (set, delete) take the exclusive write lock.
    """

    def __init__(self):
        self._entries = []          # list[Entry]
        self._index = {}            # key -> int position
        self._lock = ReadWriteLock()
        self._rng = random.Random()

    # ---------- WRITES (exclusive) ----------
    def set(self, key: Any, value: Any) -> None:
        if key is None:
            raise ValueError("key must not be None")
        with self._lock.write():
            pos = self._index.get(key)
            if pos is not None:
                self._entries[pos].value = value      # update in place
            else:
                self._index[key] = len(self._entries)
                self._entries.append(Entry(key, value))

    def delete(self, key: Any) -> bool:
        if key is None:
            raise ValueError("key must not be None")
        with self._lock.write():
            pos = self._index.get(key)
            if pos is None:
                return False                          # defined outcome: not found
            last = len(self._entries) - 1
            if pos != last:
                moved = self._entries[last]           # swap last into the hole
                self._entries[pos] = moved
                self._index[moved.key] = pos
            self._entries.pop()
            del self._index[key]
            return True

    # ---------- READS (shared) ----------
    def get(self, key: Any) -> Optional[Any]:
        if key is None:
            raise ValueError("key must not be None")
        with self._lock.read():
            pos = self._index.get(key)
            if pos is None:
                return None
            return self._entries[pos].value

    def get_random(self) -> Tuple[Any, Any]:
        with self._lock.read():
            n = len(self._entries)
            if n == 0:
                raise KeyError("structure is empty")  # defined outcome on empty
            e = self._entries[self._rng.randrange(n)]
            return (e.key, e.value)

    def __len__(self) -> int:
        with self._lock.read():
            return len(self._entries)


class ReadWriteLock:
    """
    Writer-preferring readers-writer lock built on a Condition.
    Allows many concurrent readers OR one exclusive writer.
    """

    def __init__(self):
        self._cond = threading.Condition(threading.Lock())
        self._readers = 0
        self._writer = False
        self._waiting_writers = 0

    def acquire_read(self):
        with self._cond:
            # yield to waiting/active writers to avoid writer starvation
            while self._writer or self._waiting_writers > 0:
                self._cond.wait()
            self._readers += 1

    def release_read(self):
        with self._cond:
            self._readers -= 1
            if self._readers == 0:
                self._cond.notify_all()

    def acquire_write(self):
        with self._cond:
            self._waiting_writers += 1
            while self._writer or self._readers > 0:
                self._cond.wait()
            self._waiting_writers -= 1
            self._writer = True

    def release_write(self):
        with self._cond:
            self._writer = False
            self._cond.notify_all()

    # context-manager helpers
    def read(self):
        return _LockCtx(self.acquire_read, self.release_read)

    def write(self):
        return _LockCtx(self.acquire_write, self.release_write)


class _LockCtx:
    def __init__(self, acq, rel):
        self._acq, self._rel = acq, rel

    def __enter__(self):
        self._acq()
        return self

    def __exit__(self, *exc):
        self._rel()
        return False


# ----------------------------- DRIVER / TESTS -----------------------------
if __name__ == "__main__":
    m = ConcurrentRandomizedMap()

    # 1. basic set/get/update
    m.set("a", 1)
    m.set("b", 2)
    assert m.get("a") == 1
    m.set("a", 10)                      # update path
    assert m.get("a") == 10
    assert len(m) == 2

    # 2. unknown key -> defined outcome (None / False)
    assert m.get("zzz") is None
    assert m.delete("zzz") is False

    # 3. invalid input rejected at boundary
    for bad in (lambda: m.set(None, 1), lambda: m.get(None), lambda: m.delete(None)):
        try:
            bad(); assert False, "should have raised"
        except ValueError:
            pass

    # 4. empty getRandom -> defined outcome
    empty = ConcurrentRandomizedMap()
    try:
        empty.get_random(); assert False
    except KeyError:
        pass

    # 5. delete with swap-with-last keeps structure consistent
    m.set("c", 3); m.set("d", 4)
    assert m.delete("a") is True        # 'a' not last -> triggers swap
    assert m.get("a") is None
    assert len(m) == 3
    for k in ("b", "c", "d"):
        assert m.get(k) is not None
    # invariant: every index maps back correctly
    with m._lock.read():
        for k, pos in m._index.items():
            assert m._entries[pos].key == k

    # 6. getRandom returns only live keys
    seen = set()
    for _ in range(200):
        k, v = m.get_random()
        seen.add(k)
    assert seen <= {"b", "c", "d"}

    # 7. concurrency stress: many threads hammering all ops
    big = ConcurrentRandomizedMap()
    N = 2000

    def writer(tid):
        for i in range(N):
            big.set((tid, i), i)
            if i % 3 == 0:
                big.delete((tid, i))

    def reader(tid):
        for i in range(N):
            big.get((tid, i))
            try:
                big.get_random()
            except KeyError:
                pass

    threads = []
    for t in range(4):
        threads.append(threading.Thread(target=writer, args=(t,)))
        threads.append(threading.Thread(target=reader, args=(t,)))
    for th in threads: th.start()
    for th in threads: th.join()

    # final invariant check after concurrent chaos
    with big._lock.read():
        assert len(big._entries) == len(big._index)
        for k, pos in big._index.items():
            assert 0 <= pos < len(big._entries)
            assert big._entries[pos].key == k
    print("len after stress:", len(big))
    print("ALL TESTS PASSED")
