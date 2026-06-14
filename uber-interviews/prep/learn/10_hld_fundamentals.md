# LEARN: System Design (HLD) — the framework + the building blocks Uber probes

*Why this matters: a technically deep senior candidate was rejected with the
feedback "didn't ask enough clarifying questions at the start." The framework
below is graded as much as the architecture. Uber's deep dives concentrate on
caching, partitioning, and real-time aggregation.*

## The 6-step framework (45-50 min round)

**1. Requirements — 5-8 minutes, OUT LOUD (graded!).**
Functional: who are the consumers? what exactly do they see/do? what's out of
scope? Non-functional: scale (DAU, QPS), latency targets, consistency needs
(what may be stale, what must NOT be), availability. Write them down visibly.
Uber interviewers deliberately give a one-line prompt ("design a heatmap") and
watch whether you excavate the real requirements.

**2. Estimates — 3 minutes, order-of-magnitude only.**
Writes/sec, reads/sec, storage/day. One worked rule: 1M drivers × update/4s ≈
250K writes/sec; 40 bytes/update ≈ 10 GB/day raw. Round aggressively; the
skill being graded is "did the numbers CHANGE your design?" (e.g., 250K
writes/sec ⇒ you need a queue + stream aggregation, not row inserts).

**3. APIs — write them concretely.** Uber explicitly asks for "path, request
body, response" (a real SDE-2 round demanded exactly this). 2-4 endpoints,
with response JSON shapes. This forces your data model to be real.

**4. Data model + storage choice.** Tables/documents with keys. JUSTIFY the
store: "menus = document store (nested, read-heavy); availability = Redis
(hot, TTL); events = Kafka→S3 (append-only, replayable)." One sentence each.

**5. High-level diagram.** Client → gateway → services → stores. Walk ONE
request end-to-end out loud, then ONE write end-to-end.

**6. Deep dives — where the round is won.** The interviewer picks 2-3 probes;
at Uber they cluster in: cache invalidation, hot partitions, exactly-how-stale
walkthroughs, and failure modes ("ranking service is down — what does the
user see?"). Answer with specifics, never "add more servers."

## Building block 1: Caching (Uber's favorite deep dive)

- **Layers**: client/CDN → edge → service-local → distributed (Redis) → DB.
- **Invalidation, the 3 honest options**: TTL (simple, stale up to TTL);
  event-driven purge (fresh, needs a pub-sub path and is racy); versioned keys
  (fresh + simple, costs key churn). For "restaurant closed NOW" → short-TTL
  availability check at render OR event purge; SAY the staleness number.
- **Stampede**: single-flight (one recompute, others wait) + jittered TTLs.
- **Hot keys**: replicate the hot key across shards (key+random suffix, read
  any) — this answers "a celebrity restaurant / stadium event" probes.

## Building block 2: Partitioning / sharding

- Partition BY the access pattern: heatmap reads are by-region → partition by
  geohash prefix, NOT driver_id (a real probe: "why not driver_id?" — because
  aggregation would cross every partition).
- Hot partition story ready: stadium event → split the hot geohash into finer
  cells / salt the key, aggregate on read.
- Resharding sentence: consistent hashing limits data movement to 1/n.

## Building block 3: Queues + stream aggregation (the heatmap/trending core)

Pattern: producers → Kafka (partitioned) → stream workers keeping WINDOWED
state (per-minute counts) → results to Redis/store → API reads aggregates.
Say: at-least-once delivery + idempotent updates (or dedupe keys) — that
sentence covers the reliability probe. Windows: tumbling (per-minute buckets)
vs sliding; late events → watermark or accept undercount; SAY the choice.

## Building block 4: Geo-indexing (Uber WILL touch geo)

Geohash in one breath: "encode lat/lng into a string where longer prefix =
smaller cell; nearby points share prefixes; so 'drivers near me' = a prefix
range query, and zoom levels = different precisions." Precision 5 ≈ 5km,
6 ≈ 1.2km, 7 ≈ 150m. Edge caveat: neighbors can differ in prefix at cell
boundaries → query the 8 neighbor cells too. Alternatives to name: S2, H3
(Uber's own!), PostGIS. Naming H3 at Uber is a free point.

## Building block 5: Notifications/webhooks (archetype #3)

Fan-out worker pool reading from a queue; per-channel providers (push/email/
SMS) behind an interface; retries with exponential backoff + DLQ; idempotency
keys so retries don't double-send; user preferences checked at send time;
rate-limit per user AND per provider. That one paragraph IS the design.

## Failure-mode vocabulary (deploy at least twice per round)

Graceful degradation (ranker down → popular-only feed), timeout + fallback,
circuit breaker, retry budget, DLQ, idempotency key, backpressure.

## The Uber archetype map (study the playbooks)

| Archetype | Playbook |
|---|---|
| Real-time aggregation / top-K / heatmap | `../hld/01_realtime_heatmap_topk.md` |
| Food delivery (Eats homepage, cart) | `../hld/02_uber_eats_homepage.md` |
| Notifications / alerts / webhooks | `../hld/03_notification_system.md` |
| Distributed job scheduler | `../hld/04_distributed_job_scheduler.md` |
| Kafka-lite message broker | `../hld/05_kafka_lite_broker.md` |

## Mistakes that cost offers (all observed in real Uber debriefs)

- Drawing boxes in the first 3 minutes (the rejected senior's exact mistake).
- "We'll cache it" with no invalidation story or staleness number.
- No concrete APIs when asked (a real round demanded request/response bodies).
- Numbers that never influence the design.
- Same generic microservices answer regardless of the question.
