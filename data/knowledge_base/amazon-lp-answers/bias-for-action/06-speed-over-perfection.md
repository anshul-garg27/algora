# Q: Describe a time speed mattered more than perfection.

> **LP**: Bias for Action
> **Primary story**: `G1 — Dual-write 2-week ClickHouse cutover`
> **Backup story**: `P2 — Disbursal parallelisation in a sprint`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

At Good Creator Co, PostgreSQL was choking on Beat's log writes — 10M events a day, 150+ async workers all doing `session.add()` on time-series tables. Write latency went from 5ms to 500ms over a few weeks. Analytics queries on `profile_log` were taking 30 seconds and the dashboard was crawling. Brands were noticing.

The "perfect" migration to ClickHouse looked like: write a CDC pipeline, replay history, verify byte-for-byte, swap reads atomically. That's 2-3 months of work for a 5-person team that didn't have a spare 2-3 months.

### Task

Get analytics off PostgreSQL onto ClickHouse fast — without losing data or breaking the customer dashboard. I was the one architect on the platform side.

### Action

I picked a dual-write strategy with a 2-week overlap instead of the CDC route. Beat kept doing `session.add()` to PostgreSQL, and I added `make_scrape_log_event()` calls right next to each one to emit a RabbitMQ event. The Go consumer (event-grpc) buffered events into batches of 1,000 and bulk-INSERTed them into ClickHouse via a MergeTree table partitioned by month.

The compromise — and I knew it going in — was that during the overlap window, both paths were live. If a record failed to land in ClickHouse, we'd notice it as a count mismatch, not as a data corruption. For log data, that's an acceptable failure mode. For transactional data it wouldn't have been.

Two weeks in, I ran daily row-count diffs and spot-checks on top influencers. PG count and CH count were within 0.02%. Aggregated daily follower numbers matched within rounding. That was enough.

Then I switched the dbt models — `stg_beat_profile_log` — to read from `_e.profile_log_events` (ClickHouse) instead of `beat_replica.profile_log` (PostgreSQL). Watched the dashboard for a day. Same numbers. Commented out the `session.add()` calls in Beat. Migration done.

There's one shortcut I made that I'd own openly: I never wrote a backfill for events that pre-dated the dual-write window. PostgreSQL had years of history; ClickHouse started two weeks back. The dbt mart models read from a union view for a few months, then we dropped the PG history once retention rules allowed it.

### Result

Analytics queries went from 30 seconds to about 12. Storage compressed 5x (500GB → 100GB). Infra cost dropped roughly 30%. Total elapsed time from kickoff to cutover: 4 weeks, not 3 months. The shortcut on backfill cost us a small union-view complication that we paid down later. Worth it.

---

## Technical depth — if they probe

- **Dual-trigger buffered sinker**: Go consumer flushes a batch when it hits the size limit (~1,000) or when a 1-minute ticker fires. Size optimises throughput; ticker bounds latency during quiet hours.
- **ClickHouse MergeTree schema**: `PARTITION BY toYYYYMM(event_timestamp)`, `ORDER BY (platform, profile_id, event_timestamp)`. Monthly partitions for partition pruning; ORDER BY matches the actual query pattern.
- **Why dual-write, not CDC**: CDC needs replication slots, a stable schema mapping, and conflict resolution. Dual-write is a one-line code change on the publisher side.
- **The trade-off I accepted**: At-most-once delivery for log data during ClickHouse hiccups. RabbitMQ ACK happens when events enter the Go channel, before the ClickHouse flush. If the flush fails, the batch is gone.

---

## Likely follow-ups

**Q: How did you know 0.02% drift was acceptable?**
> Because the consumer of this data was a dashboard, not a financial ledger. Aggregates over millions of profile points don't move on 0.02%.

**Q: What if a brand asked for an exact historical count?**
> We had PG history for years. The union view handled it for 6 months while we waited for PG retention rules to expire.

**Q: Why not exactly-once?**
> Late-ACK after ClickHouse flush would give exactly-once but halves throughput because the consumer blocks on every batch. For log data the throughput mattered more. Documented this in the design doc.

**Q: What broke?**
> One ClickHouse "too many parts" warning early on — I'd set the batch size too low. Tuned to ~1,000 and the warning stopped.

**Q: What would you do differently?**
> Add a dead-letter consumer that writes failed batches to S3 for manual replay. Right now a failed flush is just gone. For log data acceptable; would be nice to have.

---

## What NOT to say

- Don't pretend this was perfect — I shortcut backfill and accepted at-most-once.
- Don't oversell ClickHouse — the 2.5x query speedup came from columnar + partition pruning, not from magic.
- Don't claim "30% cost cut" without the context that team-of-5 with no DevOps had to ship this.

---

## Backup story (if asked for another)

At PayU, four days before a partner demo, I wrapped three independent disbursal-flow downstream calls in `CompletableFuture.allOf` with per-call timeouts. TAT went from 3.2 minutes to 1.1. I didn't refactor the whole flow — I refactored the slowest 30-line section. Speed > completeness.
