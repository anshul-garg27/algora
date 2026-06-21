# Q: Tell me about a time you changed the direction of a team.

> **LP**: Think Big
> **Primary story**: `G1 — ClickHouse Migration`
> **Backup story**: `W8 — Factory Pattern for Multi-DC`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Mid-2023 at Good Creator Co. Our SaaS platform was growing fast. PostgreSQL was the single database for everything — profile data, post data, and event logs. The event log table alone was taking 10 million inserts a day from our Beat scraping engine. Write latency had degraded from 5 milliseconds to 500 milliseconds — a 100x spike. Analytics queries over the same table were taking 30 seconds or more.

The team's plan was to scale Postgres vertically — bigger box, more partitions, more indexes. Standard "make Postgres faster" playbook.

### Task

I'd just shipped my first Go service (Event-gRPC) and had been reading about ClickHouse for columnar analytics. The team didn't have anyone advocating for a different database. I had to decide whether to push.

### Action

I started with benchmarks, not opinions. I exported a week of event log data, loaded it into a ClickHouse instance with a `MergeTree` engine partitioned by `toYYYYMM(timestamp)`, and ran our heaviest analytics queries against both. Postgres: 30 seconds for "engagement rate by category, last 30 days." ClickHouse: 2 seconds. Same data, same query, same hardware tier. Plus ClickHouse compressed the same data 5x because columnar storage compresses similar values well.

That was the conversation-starter. I took the numbers to the team in a design sync. The senior engineer's first reaction was "we don't have time for a database migration." Fair concern. So I came back with a phased plan that didn't require any big-bang cutover.

The plan was dual-write. Beat would keep writing to Postgres exactly as before. In parallel, it would publish events to RabbitMQ. A new Go service — Event-gRPC — would consume from RabbitMQ and batch-write to ClickHouse using a buffered sinker pattern (1000-event batches or 5-second flushes). For two weeks, both databases would have the same data. I built validation queries comparing counts and checksums daily.

Once data parity was verified, we'd flip reads to ClickHouse for analytics-style queries and keep Postgres for OLTP. The Postgres event log table could be archived once consumers moved over.

I also had to address ops concerns. Our infra team already had a ClickHouse cluster running for other workloads, so we weren't introducing new infrastructure. The buffered sinker meant 99% fewer write operations than per-event inserts, which kept ClickHouse load light.

### Result

The team agreed to the plan after two design reviews. Two weeks of dual-write, zero data drift between the systems. Reads flipped to ClickHouse over a week. Log retrieval went from 30 seconds to about 12 seconds. Write throughput on the buffered sinker — 33x improvement over per-event inserts. Storage cost dropped because of the 5x compression. The team direction shifted from "scale Postgres vertically" to "right database for the workload" — and that pattern stuck. When I built Coffee later, the dual-database design (Postgres OLTP + ClickHouse OLAP) was already the team's default. The lesson stayed with me — direction change works when you bring benchmarks, not opinions, and propose a phased path that lets the team cut at any point.

---

## Technical depth — if they probe

- **Buffered sinker pattern**: producer pushes to a 10K-capacity Go channel. Consumer goroutine reads, accumulates into a slice, flushes on size (1000) or time (5s) — whichever first. Single batch INSERT to ClickHouse.
- **Why 33x throughput improvement**: per-event INSERT vs batch of 1000 = roughly 1000x fewer round trips. The 33x figure is empirical end-to-end including RabbitMQ overhead.
- **MergeTree partitioning**: `PARTITION BY toYYYYMM(timestamp), ORDER BY (profile_id, timestamp)`. Old partitions can be dropped cheaply. Query pruning by partition.
- **Why ClickHouse compresses 5x**: columnar storage groups same-type values together. LZ4 (default) compresses repeated integer/string patterns much better than row-based Postgres TOAST.
- **Dual-write validation**: daily `SELECT count(*), max(event_timestamp), sumIfNotNull(value)` on both sides. Zero drift over two weeks.

---

## Likely follow-ups

**Q: What if the benchmarks had been close?**
> I wouldn't have pushed. Migration cost is real — two weeks of dual-write plus a new service to operate. The 30s → 2s gap was what made the case obvious.

**Q: How did you handle the cross-database consistency question?**
> ClickHouse is for analytics — eventual consistency is fine. The lag between Postgres update and ClickHouse mart was up to 15 minutes during heavy load. We mitigated with cache invalidation events via Watermill so Coffee's Redis cache cleared on Postgres update.

**Q: Was anyone against the change?**
> The senior engineer wanted to delay until next quarter. Fair pushback. I addressed it by showing the dual-write plan had no flag day — we could cut at any point in the rollout if it wasn't working.

**Q: What did this teach you about pushing direction?**
> Benchmarks beat opinions. Phased plans beat big-bang plans. And if you're proposing a change, the senior in the room is doing their job by pushing back — your job is to address the actual concern, not win the argument.

---

## What NOT to say

- Don't claim I "led the migration." I proposed and drove it. The team agreed.
- Don't downplay the operational cost. Two databases means more ops surface. The win has to be big enough to justify it.
- Don't oversell — 30s → 12s on log retrieval is the verified number. 2s was the synthetic benchmark; production is closer to 12s including network and serialisation.

---

## Backup story (if asked for another)

DC Inventory Search API at Walmart. The team's plan was hardcode for one data centre and expand later. I argued for a Factory Pattern across multiple DCs from day one — each DC implementing the same interface, selected by config. Took two extra days in the design phase. Six months later, we added a second DC in 4 hours instead of a rewrite. Same shape — change direction early, when the cost is small and the future cost would be a rebuild.
