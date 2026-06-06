import threading
from collections import deque


class HitCounter:
    """Counts hits in the last `window` seconds. Bucketed O(1)/op, O(window) space."""

    def __init__(self, window: int = 300):
        if window <= 0:
            raise ValueError("window must be positive")
        self.window = window
        # fixed ring buffers: time[i] = timestamp owning bucket i, count[i] = hits
        self.times = [0] * window
        self.counts = [0] * window
        self.lock = threading.RLock()

    def hit(self, timestamp: int) -> None:
        if timestamp < 1:
            raise ValueError("timestamp must be >= 1")
        with self.lock:
            idx = timestamp % self.window
            if self.times[idx] != timestamp:
                self.times[idx] = timestamp
                self.counts[idx] = 1
            else:
                self.counts[idx] += 1

    def getHits(self, timestamp: int) -> int:
        if timestamp < 1:
            raise ValueError("timestamp must be >= 1")
        with self.lock:
            total = 0
            for i in range(self.window):
                if timestamp - self.times[i] < self.window:
                    total += self.counts[i]
            return total


class HitCounterExact:
    """Exact queue version (stores every hit). O(1) amortized hit, O(k) cleanup."""

    def __init__(self, window: int = 300):
        self.window = window
        self.q = deque()  # (timestamp, count) compressed by second
        self.lock = threading.RLock()

    def hit(self, timestamp: int) -> None:
        if timestamp < 1:
            raise ValueError("timestamp must be >= 1")
        with self.lock:
            if self.q and self.q[-1][0] == timestamp:
                self.q[-1][1] += 1
            else:
                self.q.append([timestamp, 1])

    def getHits(self, timestamp: int) -> int:
        with self.lock:
            while self.q and self.q[0][0] <= timestamp - self.window:
                self.q.popleft()
            return sum(c for _, c in self.q)


if __name__ == "__main__":
    c = HitCounter()
    c.hit(1); c.hit(2); c.hit(3)
    assert c.getHits(4) == 3, c.getHits(4)
    c.hit(300)
    assert c.getHits(300) == 4, c.getHits(300)   # ts 1,2,3,300 all within [1,300]
    assert c.getHits(301) == 3, c.getHits(301)   # ts 1 expired (301-1=300 not <300)

    # boundary: invalid input
    for bad in (0, -5):
        try:
            c.hit(bad); assert False
        except ValueError:
            pass

    # multiple hits same timestamp + far future query empties window
    c2 = HitCounter()
    for _ in range(5):
        c2.hit(10)
    assert c2.getHits(10) == 5
    assert c2.getHits(309) == 5
    assert c2.getHits(310) == 0   # 310-10=300 not <300 -> expired

    # ring buffer reuse: same idx, new timestamp overwrites stale bucket
    c3 = HitCounter()
    c3.hit(5)
    c3.hit(305)            # 305 % 300 == 5 collides with ts5's bucket
    assert c3.getHits(305) == 1   # ts5 must NOT be counted (overwritten)

    # exact version cross-check
    e = HitCounterExact()
    e.hit(1); e.hit(2); e.hit(3)
    assert e.getHits(4) == 3
    e.hit(300)
    assert e.getHits(300) == 4
    assert e.getHits(301) == 3

    # concurrency: many threads hitting same second
    cc = HitCounter()
    def worker():
        for _ in range(1000):
            cc.hit(50)
    ts = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert cc.getHits(50) == 8000, cc.getHits(50)

    print("ALL TESTS PASSED")
