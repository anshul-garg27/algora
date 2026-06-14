# CRIB SHEET — System Design (45-60 min, SDE-2)

## The 6 steps with minute marks
- **0-8 REQUIREMENTS — OUT LOUD.** A real senior was REJECTED for skipping
  this. Ask: consumers? scale? freshness split (what may be stale, what must
  not)? out of scope? Write them visibly.
- **8-11 estimates.** Writes/sec, reads/sec, storage/day — rounded hard.
  Then SAY what the numbers force ("250K writes/sec ⇒ queue + stream agg").
- **11-16 APIs.** Concrete: paths, params, response JSON. Uber asks for
  request/response bodies explicitly.
- **16-20 data model.** Tables + keys + one-sentence store justification each.
- **20-30 diagram.** Walk ONE read and ONE write end-to-end, out loud.
- **30-45 deep dives.** This is where the round is won — specifics only.

## Uber's probe zones (prepare answers in advance)
- **Cache invalidation:** TTL vs event purge vs versioned keys — give the
  staleness NUMBER. Stampede → single-flight + jitter. Hot key → salt+shard.
- **Partitioning:** by ACCESS pattern (geo cells, not driver_id). Hot
  partition story ready (stadium event → finer cells / salted counters).
- **"Exactly how stale?"** Walk the chain hop by hop with numbers.
- **Failure:** "ranker down → popularity-only feed" — degrade, never 500.
- **Exactly-once trap:** "at-least-once + idempotency key = effectively-once."

## The 5 archetypes (one of these IS your question, ~80% odds)
1. **Real-time agg / top-K / heatmap** — Kafka by region → windowed counts →
   Redis (geohash×precision×minute) → viewport MGET. Approximate OK; CMS for
   unbounded keys. Name-drop **H3 (Uber's own)**.
2. **Uber Eats / delivery** — freshness split: availability seconds-fresh
   (Redis), ranking minutes-fresh; versioned menu cache keys; degrade ranker.
3. **Notifications/alerts** — inverted rule index per symbol; CROSSING not
   level semantics; fan-out workers; retries+DLQ; idempotent sends; rate caps.
4. **Job scheduler** — next_fire_time indexed column; atomic claim w/ lease;
   workers pull; (job_id, fire_time) idempotency key; misfire policy; jitter.
5. **Kafka-lite** — partitioned append-only log; consumer-owned offsets;
   per-partition ordering; acks trade-offs; pull + long-poll.

## Sentences that score (deploy 3+)
- "I'm splitting freshness: ___ must be seconds-fresh, ___ can lag minutes."
- "Approximate is fine for rendering — count-min sketch, exact in batch."
- "Consumers own their offsets; retention is time-based — replay is free."
- "Per-partition ordering, per-key via partition keys; global order would
  serialize the world."
- Failure vocab: graceful degradation, circuit breaker, DLQ, backpressure,
  idempotency key. Use at least two.

## Never
Boxes before requirements · "we'll cache it" without invalidation ·
numbers that don't change the design · "add more servers."
