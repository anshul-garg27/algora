# English Phrase Bank — exact sentences for every interview moment
*Interviews run in English; fluency under pressure is a separate skill from
knowing the answer. Rehearse these OUT LOUD until they're automatic. Each
phrase is calibrated to what Uber interviewers grade (clarifying, narrating,
complexity, honesty).*

## Opening (every round, ~45 seconds max)
- "Hi, I'm Anshul — I'm a backend engineer with X years of experience,
  currently working on ___ at ___. My core strengths are ___ and ___.
  Happy to dive in whenever you're ready."
- If asked "tell me about yourself" in a TECH round, keep it under a minute:
  "Short version: X years across ___; most recently I built ___. I'll keep
  it brief so we have full time for the problem."

## Clarifying questions (graded — ask 2-3 BEFORE solving, every round)
**DSA:**
- "Before I start — what's the expected input size? That decides how
  aggressive I need to be about complexity."
- "Can the input contain duplicates / negatives / be empty?"
- "Should I return any valid answer if there are multiple, or a specific one?"
- "Is the input guaranteed sorted/valid, or should I handle malformed cases?"

**LLD:**
- "Let me confirm the operations and their contracts first — should invalid
  calls return false or raise an error?"
- "Will multiple threads call this concurrently, or can I treat concurrency
  as a follow-up?"
- "What's in scope: just these operations, or should I design for extensions?"

**HLD:**
- "Who are the consumers of this system, and do they have different
  freshness needs?"
- "What scale are we designing for — users, writes per second?"
- "What must be strongly consistent, and what can be eventually consistent?"
- "What's explicitly out of scope?"

## Driving the solution (the brute→optimal narrative)
- "Let me state the brute force first so we have a baseline: ___, which is
  O(n²). Now let me see what's wasteful about it."
- "The bottleneck is ___ — I think a ___ removes it. Let me reason it through
  before coding."
- "I see two approaches: ___ which is simpler, and ___ which is faster.
  Given the constraints, I'd go with ___ — sound good?"
- "This smells like a ___ problem because ___." (pattern recognition out loud)
- Before coding: "Let me outline the steps as comments first, then fill them in."

## Complexity (say it UNPROMPTED, every time)
- "Time is O(n log n) from the sort; everything after is linear. Space is
  O(n) for the index map."
- "Each element enters and leaves the deque at most once, so it's amortized
  O(n) despite the nested loop."
- "Union-Find with path compression and union by size — effectively constant
  per operation, formally inverse-Ackermann."

## While coding (narration loop — never go silent >30s)
- "I'm using a dict here so lookups stay O(1)."
- "I'll handle the happy path first and come back to edge cases — noting
  them as TODOs so I don't forget."
- "Naming this `next_fire_time` so the intent is clear."
- "Let me trace this with the example before running: for input ___, the
  loop does ___."

## When stuck (buying time gracefully — one nudge costs less than silence)
- "Let me step back and restate the problem to check my understanding: ___."
- "My current approach struggles with ___ — let me check whether a different
  structure handles that case."
- "Can I think out loud for a moment? I want to test this idea: ___."
- Asking for help WITHOUT losing points: "I'm deciding between ___ and ___ —
  is there a constraint I should weight more heavily?"
- "I know the brute force works — let me bank that on screen first, then
  optimize." (this is GOOD interview behavior; say it confidently)

## Edge cases & testing (do this BEFORE they ask)
- "Before I run it: edge cases I should cover — empty input, single element,
  all duplicates, the boundary at exactly ___."
- "Let me write three quick asserts rather than eyeballing the output."
- "This passes; one case I'd still add with more time is ___ — flagging it."

## Concurrency follow-up (the 3-sentence skeleton, LLD rounds)
- "The race is check-then-act: two threads both see the room free and both
  book it."
- "I'll put one lock around the whole check-and-act so the invariant holds;
  it's a tiny critical section, so a coarse lock is right until contention
  is measured."
- "And to be clear — Python's GIL doesn't save me here, because my invariant
  spans multiple operations."

## HLD deep-dive answers (skeletons)
- Staleness: "Let me walk the exact chain: ingestion ___ + processing ___ +
  cache TTL ___ — worst case the user sees data ___ seconds old."
- Failure: "If the ranking service is down, I degrade to popularity-only —
  the page never fails, it just gets less personal."
- Hot key: "For a celebrity restaurant I'd salt the key across shards and
  aggregate on read."
- Honest trade-off: "Exactly-once delivery isn't achievable here; I'll do
  at-least-once with an idempotency key, which is effectively-once."

## When you genuinely don't know
- "I haven't used ___ hands-on, but my understanding is ___ — and here's how
  I'd verify before relying on it."
- "I don't know the answer; my reasoning would be ___. Where does it break?"
  (Far better than bluffing — a real Uber offer-getter's advice: never make
  it up; probes go sideways and fabrication snaps.)

## HM round (STAR discipline)
- Transitions: "The situation was ___ … my specific responsibility was ___ …
  what I did was — and I'll be specific about MY part — ___ … the result was
  ___ , measurably ___."
- Ownership: "The team built X; the piece I personally designed and defend
  end-to-end is ___."
- Conflict: "We disagreed about a genuine trade-off — ___ vs ___. I brought
  data: ___. We went with ___, and I'd make the same call today / I learned ___."
- Why Uber (have TWO specifics): "Two things specifically: ___ (e.g., H3 and
  the geo-infra Uber open-sourced) and the marketplace dispatch problem —
  I want to work on systems where ___."

## Closing every round (30 seconds, leaves a mark)
- "To summarize: I built ___, it handles ___, complexity is ___, and the two
  things I'd improve with more time are ___ and ___."
- Question to ask THEM (tech rounds): "What does this problem look like in
  production at Uber — what did I simplify that bites in real life?"
  (interviewers love answering this one)
