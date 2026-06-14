# LEARN: Machine Coding / LLD — how to survive Uber's killer round

*Why this matters: this is the #1 rejection round. Real cases: an SDE-1 with
strong DSA+behavioral cut purely on LLD; an SSE failing after 3 good DSA
rounds ("I don't come from an OOPS background"); the "100+ interviews" poster
out at Uber round 3 = LLD. None of them lacked intelligence — they lacked a
PROTOCOL.*

## What this round actually is (and isn't)

It is NOT a UML/design-patterns quiz. Uber's bar, from the actual feedback:
**runnable code implementing 3-5 operations of a small system in 45 minutes**,
with clean class boundaries, edge cases, and (for SDE-2) a credible
concurrency answer. An intern offer-getter's exact advice: *"try to write
something bare-bones working — they won't go a minute beyond 45."*

## The 45-minute protocol (memorize the clock)

**Minutes 0-5 — Requirements.** Repeat the ops back. Ask: scale? concurrent
callers? what's out of scope? error behavior — return False or raise?
Write the method signatures as a contract FIRST.

**Minutes 5-10 — Skeleton.** Entities as classes with fields only. Pick the
core data structure per operation and SAY its complexity. Don't write logic
yet — a correct skeleton makes the interviewer relax.

**Minutes 10-35 — Core code, ugliest-first.** Implement the operation with
the most logic FIRST (wildcard cd, not pwd). If short on time, stub the easy
ones — never the hard one ("I ran out of time on the easy parts" is fine;
the reverse is a No Hire).

**Minutes 35-45 — Run, test, edge cases.** Actually execute. Add 3-4 asserts:
the empty case, the duplicate case, the boundary case. Name remaining gaps
out loud — naming them yourself converts "bug" into "known limitation."

## Class design heuristics (enough for this round; forget grand UML)

1. **Nouns → classes, verbs → methods** on whichever class OWNS the data.
2. One class = one reason to change. The broker shouldn't know how a topic
   stores messages; `Topic` does (look at `../lld/pubsub_broker.py`).
3. Dicts of objects beat parallel lists. `dict[str, Room]`, not three lists.
4. Patterns only where they EARN their name: Strategy (pricing rules, parking
   spot allocation), Factory (vehicle/notification types), Observer (pub-sub),
   Singleton (say "I'd avoid it; pass the instance" — that's the senior take).
5. Python specifics: `@dataclass` for value objects, `Enum` for states,
   raise `ValueError` for contract violations, return None/False for
   expected misses — and state WHICH convention you chose.

## Concurrency: the follow-up that is ALWAYS coming (SDE-2+)

You need three sentences and one snippet, not a thesis:

1. **Find the race**: it's almost always **check-then-act** ("if room free →
   book it" — two threads both pass the check) or **read-modify-write**
   (`count += 1`).
2. **Fix**: one `threading.Lock` around the critical section. Coarse lock
   first, ALWAYS — then say "if contention shows up, split to per-topic /
   per-room locks; lock ordering becomes a concern then."
3. **The GIL trap**: "Python's GIL doesn't save me — my invariant spans
   multiple statements/structures, and the GIL can switch threads between
   them." (Claiming GIL safety capped a real candidate at Lean Hire.)

```python
self._lock = threading.Lock()
def book(self, start, end):
    with self._lock:              # check AND act inside
        room = self._find_free(start, end)
        if room: room.add(start, end)
        return room.id if room else INVALID
```

Blocking semantics ("wait until a message arrives") → `threading.Condition`:
`wait_for(predicate, timeout)` + `notify_all()` on state change. One
memorized example: `../lld/pubsub_broker.py` poll().

## The recurring problems (attempt EVERY one before your loop)

| Problem | Asked | Reference |
|---|---|---|
| File system mkdir/cd/pwd + wildcard | 4x | `../lld/file_system.py` |
| Pub-sub broker, threaded, replay | 3x | `../lld/pubsub_broker.py` |
| Meeting/room scheduler family | 3-4x | `../lld/meeting_scheduler.py` |
| TTL store / O(1) getRandom / hit counter | 3x | `../lld/ttl_random_store.py`, `../lld/hit_counter.py` |
| Parking lot | 2x | classic; do it cold |
| Vending machine | 2x | state machine + change-making |
| Splitwise / pricing calculator | 2x | strategy pattern home turf |

## Mistakes that cost offers (every one is from a real debrief)

- Spending 20 minutes on class diagrams, then "ran out of time to code" —
  the SDE-1's exact downfall.
- Building the generic framework before any feature works.
- Never running the code ("it should work" ≠ PASS).
- The GIL claim (above).
- Practicing in an IDE with Copilot, then facing bare HackerRank — practice
  in a plain editor; for Staff loops Uber literally uses HackerRank
  multi-file.

## Drill plan

1. Read ONE reference implementation per day; close it; re-type from memory
   in 35 minutes; diff.
2. Run mocks `lld_01` → `lld_02` → `lld_03` (kits in `../mocks/`), with the
   45-min alarm, in a plain editor.
3. After each: write ONE sentence — "the race in this design was ___, fixed
   by ___." If you can't, reread the follow-up answers at the file bottom.
