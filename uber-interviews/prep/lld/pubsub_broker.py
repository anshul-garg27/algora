"""Reference: Thread-safe topic-based pub-sub message broker (Kafka-lite).
Uber machine-coding round, asked 3x in the last year.

Design notes (say out loud):
- Fan-out semantics: every subscriber gets every message after it subscribes
  => per-topic append-only log + per-subscriber offset. (A shared queue would
  be competing-consumer semantics — different thing; say the difference.)
- Lock per Topic (not one global lock): publishers to different topics don't
  contend. Condition enables blocking poll (follow-up #2).
- Retention (follow-up #3): drop log prefix, keep base_offset; offsets are
  logical, never reused.
- Complexity: publish O(1); poll O(k) for k messages returned.
"""
from __future__ import annotations

import threading


class Topic:
    def __init__(self, name: str) -> None:
        self.name = name
        self.lock = threading.Lock()
        self.not_empty = threading.Condition(self.lock)
        self.log: list[object] = []
        self.base_offset = 0                      # for retention trimming
        self.offsets: dict[str, int] = {}         # subscriber_id -> next offset

    @property
    def end_offset(self) -> int:
        return self.base_offset + len(self.log)


class Broker:
    def __init__(self) -> None:
        self._topics: dict[str, Topic] = {}
        self._registry_lock = threading.Lock()

    # ---------------- public API ----------------

    def create_topic(self, name: str) -> None:
        with self._registry_lock:
            self._topics.setdefault(name, Topic(name))

    def publish(self, topic: str, message: object) -> int:
        t = self._topic(topic)
        with t.lock:
            t.log.append(message)
            offset = t.end_offset - 1
            t.not_empty.notify_all()
            return offset

    def subscribe(self, topic: str, subscriber_id: str) -> None:
        t = self._topic(topic)
        with t.lock:
            # start at current end => only future messages
            t.offsets.setdefault(subscriber_id, t.end_offset)

    def poll(self, topic: str, subscriber_id: str, max_messages: int = 10,
             timeout: float | None = 0.0) -> list[object]:
        """timeout=0 -> non-blocking; timeout=None -> wait forever."""
        t = self._topic(topic)
        with t.lock:
            if subscriber_id not in t.offsets:
                raise KeyError(f"{subscriber_id} not subscribed to {topic}")
            if timeout != 0.0:
                t.not_empty.wait_for(
                    lambda: t.offsets[subscriber_id] < t.end_offset,
                    timeout=timeout)
            start = max(t.offsets[subscriber_id], t.base_offset)
            end = min(start + max_messages, t.end_offset)
            msgs = t.log[start - t.base_offset: end - t.base_offset]
            t.offsets[subscriber_id] = end
            return list(msgs)

    def reset_offset(self, topic: str, subscriber_id: str, offset: int) -> None:
        t = self._topic(topic)
        with t.lock:
            if subscriber_id not in t.offsets:
                raise KeyError(f"{subscriber_id} not subscribed to {topic}")
            if offset < t.base_offset:
                raise ValueError(f"offset {offset} below retained base {t.base_offset}")
            t.offsets[subscriber_id] = min(offset, t.end_offset)

    def trim(self, topic: str, retain_from_offset: int) -> None:
        """Retention: drop everything before retain_from_offset."""
        t = self._topic(topic)
        with t.lock:
            cut = max(0, min(retain_from_offset - t.base_offset, len(t.log)))
            if cut:
                t.log = t.log[cut:]
                t.base_offset += cut

    # ---------------- internals ----------------

    def _topic(self, name: str) -> Topic:
        with self._registry_lock:
            if name not in self._topics:
                raise KeyError(f"no such topic: {name}")
            return self._topics[name]


# ---------------- tests (superset of the mock's acceptance tests) ----------------

def main() -> None:
    b = Broker()
    b.create_topic("rides")
    b.publish("rides", "m0")
    b.subscribe("rides", "s1")
    o1 = b.publish("rides", "m1")
    b.publish("rides", "m2")
    assert b.poll("rides", "s1") == ["m1", "m2"]
    assert b.poll("rides", "s1") == []
    b.subscribe("rides", "s2")
    b.publish("rides", "m3")
    assert b.poll("rides", "s1") == ["m3"]
    assert b.poll("rides", "s2") == ["m3"]
    b.reset_offset("rides", "s1", o1)
    assert b.poll("rides", "s1", max_messages=2) == ["m1", "m2"]

    # retention
    b.trim("rides", 2)
    try:
        b.reset_offset("rides", "s1", 0)
        raise AssertionError("expected ValueError below retained base")
    except ValueError:
        pass

    # concurrency: 4 publishers x 250, no loss/dup
    b.create_topic("load")
    b.subscribe("load", "c")
    def worker(k: int) -> None:
        for i in range(250):
            b.publish("load", f"{k}-{i}")
    ts = [threading.Thread(target=worker, args=(k,)) for k in range(4)]
    [t.start() for t in ts]; [t.join() for t in ts]
    got: list[object] = []
    while True:
        batch = b.poll("load", "c", max_messages=100)
        if not batch:
            break
        got.extend(batch)
    assert len(got) == 1000 and len(set(got)) == 1000

    # blocking poll
    b.create_topic("slow")
    b.subscribe("slow", "w")
    res: list[object] = []
    def waiter() -> None:
        res.extend(b.poll("slow", "w", timeout=None))
    th = threading.Thread(target=waiter)
    th.start()
    b.publish("slow", "late")
    th.join(timeout=2)
    assert res == ["late"]

    print("PASS")


if __name__ == "__main__":
    main()


# ---------------- FOLLOW-UP ANSWERS ----------------
# Consumer groups (exactly-one-worker-per-message): keep ONE offset per GROUP,
#   workers poll under the same group lock => each message claimed once.
#   Mention rebalancing/partitions as the real-Kafka extension, don't build it.
# Monitoring in prod: per-subscriber lag (end_offset - offset), publish rate,
#   poll latency, retained-log bytes.
# Why notify_all not notify: multiple subscribers may be waiting on the same
#   topic; a single notify could wake the wrong waiter whose predicate is
#   already satisfied-false.
