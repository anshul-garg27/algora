"""Reference: Hit Counter family — Uber phone-screen favorite.
Asked as: "HitCounter, hits in last 5 min" (SDE-2 onsite), and the richer
"Counter class: put(num,t) / count(num,t) / countAll(t) over 5-min window"
(SDE-2 phone screen, with 'unit tests?' and 'production issues?' follow-ups).

Design notes (say out loud):
- Calls arrive in chronological order => a deque + lazy eviction gives O(1)
  amortized everything. Without that guarantee you'd need sorted structures.
- Memory is O(events in window); the production follow-up wants you to say
  what happens when that's millions/sec => bucket per second (fixed 300
  buckets) trading exactness granularity for O(1) memory.
"""
from __future__ import annotations

from collections import deque

WINDOW = 300  # seconds


class HitCounter:
    """Exact counts; O(window events) memory."""

    def __init__(self) -> None:
        self._q: deque[tuple[int, int]] = deque()   # (timestamp, hits)
        self._total = 0

    def hit(self, ts: int) -> None:
        if self._q and self._q[-1][0] == ts:
            t, c = self._q.pop()
            self._q.append((t, c + 1))
        else:
            self._q.append((ts, 1))
        self._total += 1

    def get_hits(self, ts: int) -> int:
        self._evict(ts)
        return self._total

    def _evict(self, now: int) -> None:
        while self._q and self._q[0][0] <= now - WINDOW:
            self._total -= self._q.popleft()[1]


class Counter:
    """The richer Uber variant: per-number counts + global count."""

    def __init__(self) -> None:
        self._events: deque[tuple[int, int]] = deque()  # (ts, num)
        self._per_num: dict[int, int] = {}
        self._total = 0

    def put(self, num: int, ts: int) -> None:
        self._events.append((ts, num))
        self._per_num[num] = self._per_num.get(num, 0) + 1
        self._total += 1

    def count(self, num: int, ts: int) -> int:
        self._evict(ts)
        return self._per_num.get(num, 0)

    def count_all(self, ts: int) -> int:
        self._evict(ts)
        return self._total

    def _evict(self, now: int) -> None:
        while self._events and self._events[0][0] <= now - WINDOW:
            _, num = self._events.popleft()
            self._per_num[num] -= 1
            if self._per_num[num] == 0:
                del self._per_num[num]
            self._total -= 1


class BucketHitCounter:
    """Production-scale variant: fixed 300 one-second buckets, O(1) memory.
    Loses sub-second exactness at the window edge — SAY this trade-off."""

    def __init__(self) -> None:
        self._ts = [0] * WINDOW
        self._count = [0] * WINDOW

    def hit(self, ts: int) -> None:
        i = ts % WINDOW
        if self._ts[i] != ts:
            self._ts[i] = ts
            self._count[i] = 0
        self._count[i] += 1

    def get_hits(self, ts: int) -> int:
        return sum(c for t, c in zip(self._ts, self._count) if ts - t < WINDOW)


# ---------------- tests (the actual example from the Uber round) ----------------

def main() -> None:
    c = HitCounter()
    c.hit(1); c.hit(2); c.hit(3)
    assert c.get_hits(4) == 3
    c.hit(300)
    assert c.get_hits(300) == 4
    assert c.get_hits(301) == 3        # ts=1 fell out of [2..301]

    k = Counter()                       # the phone-screen example, in seconds
    k.put(2, 0); k.put(2, 120); k.put(3, 180)
    assert k.count(2, 240) == 2
    assert k.count_all(240) == 3
    assert k.count(2, 360) == 1         # the t=0 put expired
    assert k.count_all(360) == 2

    b = BucketHitCounter()
    b.hit(1); b.hit(2); b.hit(2); b.hit(300)
    assert b.get_hits(300) == 4
    assert b.get_hits(301) == 3

    print("PASS")


if __name__ == "__main__":
    main()


# ---------------- FOLLOW-UP ANSWERS (asked verbatim at Uber) ----------------
# "What unit tests would you write?"
#   same-timestamp hits; boundary at exactly now-300; queries with no hits;
#   monotonic-time violation behavior (document the contract!); counter going
#   to zero and key cleanup; very sparse hits (eviction across big gaps).
# "If this ran in production, what issues?"
#   memory growth under burst (exact variant) -> bucketed/sharded counters;
#   thread safety (wrap _evict+read in a lock — eviction MUTATES on read,
#   that's the sneaky race); clock skew across hosts -> ingest-time stamping;
#   single hot counter -> shard by key, aggregate on read.
