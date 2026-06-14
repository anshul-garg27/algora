# CRIB SHEET — Machine Coding / LLD (45 min — the round that rejects most)

## The clock (non-negotiable)
- **0-5: requirements.** Repeat ops back. Ask: errors return False or raise?
  concurrent callers? out of scope? Write method signatures as the contract.
- **5-10: skeleton.** Classes + fields only. Data structure per op + its
  complexity, out loud.
- **10-35: core code, HARDEST op first** (wildcard cd before pwd). Stub easy
  ones if time runs out — never the hard one.
- **35-45: RUN IT.** 3-4 asserts: empty, duplicate, boundary. Name remaining
  gaps yourself ("known limitation" beats "discovered bug").

## The bar (from real debriefs)
**Bare-bones RUNNING code beats elaborate incomplete design.** An SDE-1 with
strong DSA+behavioral was cut here for exactly that. They will not extend
time by one minute.

## Design heuristics
- Nouns → classes; verbs → methods on the data owner.
- `dict[str, Room]`, never parallel lists. `@dataclass` for values, `Enum`
  for states.
- Patterns only where earned: Strategy (pricing/allocation), Observer
  (pub-sub), Factory (types). Singleton → "I'd avoid it; pass the instance."
- State conventions out loud: "cd above root stays at root", "EQUAL split
  leftover paisa goes to payer."

## Concurrency follow-up (memorize the 3 sentences)
1. "The race is **check-then-act** — two threads both pass the check."
2. "One lock around the whole check-and-act; coarse first, split only if
   contention is measured."
3. "**The GIL doesn't save me** — my invariant spans multiple operations."
Blocking semantics → `Condition.wait_for(pred, timeout)` + `notify_all()`.
NEVER sleep-loop.

## Likely problems (all have references in prep/lld/)
File system + wildcard (4x) · pub-sub broker w/ replay (3x) · meeting
scheduler (3x) · TTL store / O(1) getRandom / hit counter (3x) · parking lot
(bus = 2 adjacent large) · vending machine · Splitwise (integer paise!).

## Last check before call
Plain editor ready (no Copilot) · `python3 file.py` runs · threading.Lock,
Condition, defaultdict imports from memory.
