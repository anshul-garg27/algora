"""
UBER MACHINE CODING / LLD MOCK #3 — 45 minutes
================================================
(Combines two real Uber rounds: "TTL key-value store with active counts"
(SDE-4 loop, Jan 2026) and "Thread-safe O(1) insert/delete/get/getRandom"
(SDE-2 loop). Both were standalone 45-min rounds; together they're the
data-structure-design family Uber loves.)

PART A — TTLStore (do this first)
  * put(key, value, expire_at)   — timestamps strictly increase across calls
  * get(key, now) -> value|None  — None if absent or expired at `now`
  * count_active(now) -> int     — number of unexpired keys, **O(log n) or better**

PART B — RandomizedDict (if time remains; interviewer will ask regardless)
  * set(key, value), get(key), delete(key), get_random() -> (key, value)
  * ALL average O(1); get_random uniform over current keys

Expectations:
  1. RUNNABLE — demo below must print PASS.
  2. State the complexity of every operation unprompted.
  3. Thread-safety questions WILL come in follow-ups — design with that in mind.

When done (or at 45 min), say "done" to the interviewer chat.
"""

# ============== YOUR IMPLEMENTATION BELOW ==============


class TTLStore:
    pass


class RandomizedDict:
    pass


# ============== DEMO / ACCEPTANCE TESTS ==============

def main() -> None:
    s = TTLStore()
    s.put("a", 1, expire_at=10)
    s.put("b", 2, expire_at=5)
    s.put("c", 3, expire_at=20)
    assert s.get("a", now=4) == 1
    assert s.get("b", now=6) is None          # expired
    assert s.count_active(now=6) == 2         # a, c
    assert s.count_active(now=15) == 1        # c
    s.put("a", 9, expire_at=30)               # update extends ttl
    assert s.get("a", now=25) == 9
    assert s.count_active(now=25) == 2        # a, c... c expired at 20 -> just a
    # careful: at now=25, c (expire 20) is gone -> exactly 1? decide & document!
    # The interviewer accepts either boundary convention IF stated and consistent.

    r = RandomizedDict()
    r.set("x", 1); r.set("y", 2); r.set("z", 3)
    assert r.get("y") == 2
    r.delete("y")
    assert r.get("y") is None
    seen = {r.get_random()[0] for _ in range(200)}
    assert seen == {"x", "z"}                  # uniform over remaining keys

    print("PASS")


if __name__ == "__main__":
    main()
