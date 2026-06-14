"""
UBER MACHINE CODING / LLD MOCK #2 — 45 minutes
================================================
(Asked 3x in the last 12 months: "Design a system like Kafka with concurrency
support" — one candidate's only weak round in an otherwise all-YES loop.)

Design a thread-safe, topic-based message broker supporting publish-subscribe:

  * create_topic(name)
  * publish(topic, message) -> offset
      Appends message to the topic's log. Multiple publishers may call
      this concurrently.
  * subscribe(topic, subscriber_id)
      Subscriber starts receiving messages published AFTER subscription.
  * poll(topic, subscriber_id, max_messages=10) -> list[message]
      Returns the next unconsumed messages for this subscriber and advances
      its offset. Each subscriber consumes independently (fan-out, not queue).
  * reset_offset(topic, subscriber_id, offset)
      Replay support: subscriber can rewind to any retained offset.

Expectations:
  1. RUNNABLE — demo below must print PASS.
  2. Thread-safety is part of the core requirement, not a follow-up.
  3. Clean separation: Broker / Topic / subscriber state.
  4. Know your own complexity: publish O(?), poll O(?).

When done (or at 45 min), say "done" to the interviewer chat.
"""

# ============== YOUR IMPLEMENTATION BELOW ==============


class Broker:
    pass  # replace with your design


# ============== DEMO / ACCEPTANCE TESTS ==============

def main() -> None:
    import threading

    b = Broker()
    b.create_topic("rides")

    b.publish("rides", "m0")              # before subscription -> not delivered
    b.subscribe("rides", "s1")
    o1 = b.publish("rides", "m1")
    b.publish("rides", "m2")

    assert b.poll("rides", "s1") == ["m1", "m2"]
    assert b.poll("rides", "s1") == []          # nothing new

    b.subscribe("rides", "s2")
    b.publish("rides", "m3")
    assert b.poll("rides", "s1") == ["m3"]      # independent consumption
    assert b.poll("rides", "s2") == ["m3"]

    b.reset_offset("rides", "s1", o1)           # replay from m1
    assert b.poll("rides", "s1", max_messages=2) == ["m1", "m2"]

    # concurrency smoke test: 4 publishers x 250 msgs, no loss, no duplicates
    b.create_topic("load")
    b.subscribe("load", "c")
    def worker(k):
        for i in range(250):
            b.publish("load", f"{k}-{i}")
    ts = [threading.Thread(target=worker, args=(k,)) for k in range(4)]
    [t.start() for t in ts]; [t.join() for t in ts]
    got = []
    while True:
        batch = b.poll("load", "c", max_messages=100)
        if not batch:
            break
        got.extend(batch)
    assert len(got) == 1000 and len(set(got)) == 1000

    print("PASS")


if __name__ == "__main__":
    main()
