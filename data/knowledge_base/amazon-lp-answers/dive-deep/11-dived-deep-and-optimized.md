# Q: Tell me about a time you dived deep and optimized something.

> **LP**: Dive Deep
> **Primary story**: `G1 — ClickHouse Migration`
> **Backup story**: `W8 — DC Inventory Search API`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

The slowest query on our supplier-facing analytics at GCC was "show me this influencer's follower growth for the last 30 days." It ran against a PostgreSQL `profile_log` table with about 2.5 billion rows. The query took roughly 30 seconds. Suppliers were complaining. The product manager was complaining. The DBA team had run out of ideas.

### Task

Take the 30-second query under 15 seconds. Without breaking the rest of the platform that was already writing 10M+ logs/day into the same table.

### Action

I started with the query plan. Postgres was doing a sequence scan on the partial-index that I'd hoped would help. Two reasons. One, the table was row-oriented, so even to read `followers` it pulled the entire row including `metrics JSONB`, `dimensions JSONB`, and a dozen other columns. Two, the JSONB extraction (`metrics->>'followers'`) had to happen per row before the index could narrow the scan.

I tried three optimisations. Partial index on `(profile_id, timestamp DESC) INCLUDE (metrics)` shaved a few seconds. Materialised view aggregated daily — fast but stale. TimescaleDB hypertable — 18 seconds, still not enough and added a PG extension our DBA team didn't run.

The actual answer was that PG was the wrong shape. The query is a column-oriented aggregation. I built a ClickHouse POC in three days with the same data. MergeTree engine. `PARTITION BY toYYYYMM(event_timestamp)`. `ORDER BY (platform, profile_id, event_timestamp)`. The same query: 12 seconds. Storage shrank from 500GB to 100GB on the same data because columnar compression on metrics-heavy rows is ridiculous.

The reason ClickHouse was 2.5x faster came down to four things stacked together. Partition pruning meant the query touched one monthly partition out of 24 instead of the whole table. Columnar reads pulled only the `metrics` and `event_timestamp` columns, not all nine. The `ORDER BY` prefix matched the WHERE clause exactly, so the filter found contiguous blocks. And vectorised aggregation in SIMD batches was about 3x faster per row than row-by-row.

Then I built the migration path. RabbitMQ as the buffer, a Go service called event-grpc as the consumer, dual-trigger buffered sinker — flush at 1000 records or every 1 minute. The sinker was the part that made ClickHouse actually fast in production, because ClickHouse hates small inserts. Each `INSERT INTO profile_log_events VALUES (...1000 rows...)` runs in 5ms.

### Result

Query time: 30s → 12s. Storage: 500GB → 100GB. Infrastructure cost dropped about 30% because we needed less provisioned IOPS, smaller disks, smaller instances. Write I/O went from 10,000 individual INSERTs per second on PG to ~10 batch INSERTs per second on ClickHouse — 99.9% I/O reduction.

The migration itself ran for two weeks of dual-writes, less than 0.02% drift on row counts, then we commented out the `session.add()` calls in Beat. The commented-out code is still in the repo as a record of what changed.

---

## Technical depth — if they probe

- **Why MergeTree over ReplacingMergeTree**: Log events are append-only. Each crawl produces a new row with a UUID `event_id`. Replacing semantics add merge overhead with no benefit.
- **Why monthly partitions, not daily**: At 10M/day, daily creates 365 parts/year — too many small merges. Monthly hits ~300M rows per partition, which compresses well and supports partition pruning on 30-day queries with one or two partitions touched.
- **Why dual-trigger sinker**: Size-only flushes leave partial batches sitting during quiet hours. Time-only flushes throttle peak. Both together give throughput AND latency bounds.
- **Why early ACK on RabbitMQ**: We ACK when the message hits the Go channel, not after ClickHouse confirms. Higher throughput, slightly lower reliability. For log data the trade-off was right. For payments I'd flip it.

---

## Likely follow-ups

**Q: Why not just throw more hardware at PG?**
> I priced it out. To match ClickHouse's query speed on PG we'd need a 10x bigger instance plus provisioned IOPS. About 5x the cost for the same outcome. ClickHouse was both faster AND cheaper, which doesn't happen often.

**Q: How did you validate data correctness?**
> Three layers. Daily row counts within 0.1%. Spot-checks comparing argMax(followers, ts) for specific high-profile accounts day by day. And downstream rank-stability — leaderboard rankings from both backends matched 99.9%.

**Q: Did you consider Druid or Pinot?**
> Briefly. ClickHouse won on operational simplicity — single binary, no Zookeeper or coordination layer. For our team size that mattered.

**Q: What did the 2.5x calc actually look like?**
> Same query, same data. Partition pruning ≈12x less data scanned. Columnar reads ≈4.5x less I/O. Vectorised aggregation ≈3x faster processing. Combined ends up around 30s/12s = 2.5x at the user-facing layer.

---

## What NOT to say

- Don't say "PG is bad." It's great for OLTP. It's wrong for this workload.
- Don't oversell the 30% cost saving as the headline — the query speed is what suppliers felt.
- Don't claim "zero data loss" through the migration — say "under 0.02% drift" because that's the verified number.

---

## Backup story (if asked for another)

For W8, optimising the DC Inventory Search API came from latency-budget thinking. The naive sequential implementation would have run UberKey → supplier auth → EI fetch in series — about 5 seconds for 100 items. I rewrote the pipeline with `processWithBulkValidation` so each stage batched its calls. UberKey went from 100 sequential calls to one batched call. EI went from 100 to one. P95 landed at 1.8 seconds — 33% faster than our peer inventory-status API. The dive was identifying that the latency budget was eaten by chattiness, not by any single slow call.
