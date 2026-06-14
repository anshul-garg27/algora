# LEARN: Concurrency in Python — exactly what Uber probes

*Why this matters: concurrency follow-ups appeared in LLD rounds, DSA rounds
("make it thread-safe"), dedicated questions (print-in-order, two-tier cache,
task executor), and HM tech-ambushes. You don't need to be a concurrency
wizard — you need ~6 tools used correctly.*

## The mental model

A thread can be paused **between any two operations** (and inside many
"single" ones). If an invariant spans multiple steps — check then act, read
then write, update two structures together — another thread can sneak in
between. Every concurrency bug in interviews is one of these two:

1. **Check-then-act**: `if key not in d: d[key] = ...` — two threads both
   pass the check.
2. **Read-modify-write**: `count += 1` is read, add, store — interleave two
   and lose an increment.

## The GIL — say this correctly or lose half a grade

The GIL means one thread runs Python bytecode at a time. It does **NOT** make
your code thread-safe: it can switch threads BETWEEN bytecodes, so any
multi-step invariant still breaks. The sentence to say: *"The GIL protects
the interpreter, not my invariants — I still need a lock around compound
operations."* (A real candidate claiming GIL safety got capped at Lean Hire.)

## Tool 1: Lock — the default answer

```python
import threading

class Counter:
    def __init__(self):
        self._n = 0
        self._lock = threading.Lock()
    def incr(self):
        with self._lock:          # ALWAYS the with-statement form
            self._n += 1
```

Rules: ONE coarse lock first; widen the critical section to cover the whole
invariant (find room AND book it); say "I'd split locks only if contention
is measured." `RLock` when a locked method calls another locked method of the
same object.

## Tool 2: Condition — "wait until something happens"

For blocking poll / bounded queues / "consumer waits for producer".
NEVER answer this with `while True: sleep(0.1)` — that's an instant downgrade.

```python
class Inbox:
    def __init__(self):
        self._items = []
        self._lock = threading.Lock()
        self._nonempty = threading.Condition(self._lock)
    def put(self, x):
        with self._lock:
            self._items.append(x)
            self._nonempty.notify_all()
    def take(self, timeout=None):
        with self._lock:
            self._nonempty.wait_for(lambda: self._items, timeout=timeout)
            return self._items.pop(0) if self._items else None
```

Why `wait_for(predicate)` and not plain `wait()`: spurious wakeups + the
predicate re-check is built in. Why `notify_all`: multiple waiters with
different predicates. Both are one-line answers interviewers fish for.

## Tool 3: queue.Queue — the shortcut you're allowed to use

Thread-safe FIFO with blocking get/put built in. In LLD, USING it is fine
("producer-consumer is solved; I'll spend my time on the domain logic") —
but be ready to implement Tool 2 if they say "without queue.Queue".

## The three actual Uber concurrency questions, solved in words

**1. Print 0-even-odd with 3 threads ("0102030405…", senior round 2025-12):**
Three threads, each in a loop: wait on a Condition for ITS turn (a shared
`state` variable says who prints next), print, update state, `notify_all`.
The lesson: turn-taking = shared state + condition, one lock total.

**2. Two-tier cache refresh, single-flight (HM round!):** only ONE thread per
key may recompute; others wait and reuse. Keep `dict[key -> Future/Event]`:
first thread installs an Event and computes; others find the Event and
`wait()` on it. On completion: set value, `event.set()`. Mention "this is
single-flight; thundering-herd protection" — the vocabulary scores.

**3. Task executor with blockUntilComplete (frontend loop, 2025-11):**
`submit()` increments a pending counter and dispatches to worker threads;
`block_until_complete()` does `cond.wait_for(lambda: pending == 0)`; workers
decrement and `notify_all` when pending hits 0. (This is exactly what
`queue.Queue.join()` / `task_done()` do — say that too.)

## Deadlocks — the one question you get if you propose multiple locks

Two locks acquired in opposite orders by two threads = deadlock. The answer
they want: **a global lock ORDER** (always lock lower room-id first), or
better, "I'll keep one lock until profiling says otherwise." Don't volunteer
fine-grained locking; it invites this question on hard mode.

## Cheat sheet

| Need | Tool |
|---|---|
| protect an invariant | `Lock` + `with` |
| nested locked calls on self | `RLock` |
| wait for a state change | `Condition.wait_for` / `notify_all` |
| producer-consumer pipe | `queue.Queue` |
| one-shot "it's ready" signal | `Event` |
| single-flight per key | `dict[key, Event]` + lock |
| cap concurrent users of a resource | `Semaphore` |

## Drill

1. Re-type the Inbox (Condition) from memory — under 5 minutes.
2. Implement print-0-even-odd; verify output order for n=5.
3. Implement single-flight cache; test with 10 threads hitting one key
   (compute function counts its calls — must be 1).
4. Re-read the race notes at the bottom of every file in `../lld/`.
