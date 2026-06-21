# Q: Describe a complex problem you encountered that required in-depth research, development of proof of concepts, and exploration of multiple solutions.

> **LP**: Dive Deep
> **Primary story**: `G1 — ClickHouse Migration`
> **Backup story**: `W11 — Unified Onboarding / IAM`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

At GCC our Beat scraper was crawling 500K+ influencer profiles a day. Every crawl wrote a row into PostgreSQL `profile_log` and `post_log` — the time-series tables that fed our analytics. By the time I joined, write latency had climbed from 5ms to 500ms per INSERT and a 30-day follower-growth query took 30 seconds. The DB was the bottleneck.

### Task

Find a path that handled 10M+ log inserts a day, kept analytics queries under 15 seconds, and didn't break the running system. I had two weeks to bring a recommendation.

### Action

I built three POCs, not one.

First POC was a partitioned PostgreSQL setup with monthly child tables and BRIN indexes. It helped writes a bit but query time barely moved — row-oriented storage scans all the columns even when you only need `followers`. I ruled it out.

Second POC was TimescaleDB. Hypertables looked promising on paper. But I'd be locking the team into a PG extension our DBA team didn't run, and the compression numbers were 3x at best.

Third POC was ClickHouse fronted by RabbitMQ with a Go buffered sinker. I built it end-to-end in three days on a dev box. MergeTree with `PARTITION BY toYYYYMM(event_timestamp)` and `ORDER BY (platform, profile_id, event_timestamp)`. The dual-trigger sinker — flush at 1000 records or every 1 minute, whichever hit first — kept ClickHouse happy because ClickHouse hates small inserts.

The benchmarks were the conversation-ender. Same 30-day query: PG 30s, partitioned PG 22s, TimescaleDB 18s, ClickHouse 12s. Storage: 500GB shrank to 100GB on ClickHouse. I wrote up the comparison with execution plans for each and walked the team through the partition-pruning math.

We then did a dual-write phase. Beat published to RabbitMQ AND kept writing to PG for two weeks. I diffed row counts daily — under 0.02% drift. Once dbt models read from ClickHouse cleanly, I commented out the `session.add()` calls. You can still see them commented in `processing.py` as a record of the migration.

### Result

Query time went from 30 seconds to about 12 — 2.5x faster. Storage came down 5x via columnar compression. I/O on the write path dropped from 10,000 individual INSERTs/sec to roughly 10 batch INSERTs/sec. Infrastructure cost dropped ~30%. The piece I'm still proud of is the dual-write phase — we never had a moment of "is the data wrong?" because we could diff both sides.

---

## Technical depth — if they probe

- **Why MergeTree, not ReplacingMergeTree**: Log events are append-only. Each crawl is a new row with a UUID `event_id`. Replacing semantics would add merge overhead we didn't need. Trace logs and order events use Replacing because they DO get updates.
- **Why monthly partitions**: At 10M/day, daily partitions create 365 parts/year — too many small merges. Monthly hits ~300M rows per part: enough for good compression, few enough that partition pruning on a 30-day query touches one or two parts max.
- **Why dual-trigger sinker**: Size-only flushes leave partial batches sitting forever during quiet hours. Time-only flushes throttle peak traffic. Both together give throughput AND bounded latency.
- **Why early ACK on RabbitMQ**: We ACK when the message hits the Go channel, not after ClickHouse confirms. Lower reliability, higher throughput. For log data — acceptable. For transactional data I'd flip it.

---

## Likely follow-ups

**Q: What if ClickHouse was down during the migration?**
> Beat would keep publishing to RabbitMQ — messages are durable. The Go sinker would back off and retry. We'd lose the in-flight buffer batch (a few thousand events at most). For log data, that loss budget was acceptable; we documented it.

**Q: Why RabbitMQ, not Kafka?**
> RabbitMQ was already the backbone — credentials, identity, WebEngage all used it. The team had operational muscle. At 115 events/sec average, it handled the volume comfortably. At 100x that I'd push for Kafka.

**Q: How did you validate data parity?**
> Three checks. Daily row counts within 0.1%. Spot-checks on high-profile accounts comparing argMax(followers, ts) day-by-day. And ranking-stability checks on the leaderboard dbt models — ClickHouse-backed rankings matched PG-backed rankings 99.9%.

**Q: What would you change today?**
> Late ACK after successful flush — exactly-once over throughput. And I'd extract the top 10 metrics into native columns instead of a JSON blob, to skip `JSONExtractInt()` on hot queries.

---

## What NOT to say

- Don't pitch ClickHouse as a silver bullet — name the trade-offs (eventual merge consistency, JSON parsing cost).
- Don't skip the POC comparison. The fact that I built three and benchmarked them is the dive.
- Don't claim "zero data loss" — say "under 0.02% drift," because that's the real number.

---

## Backup story (if asked for another)

For W11, when we hit the Apollo Federation supergraph for supplier onboarding, I had to research three patterns — REST-aggregator BFF, GraphQL stitching, and Federation v2 — before recommending Federation. I built a 200-line POC of each, benchmarked resolver fan-out, and ran a junior engineer through it as the test of whether the docs were good enough. The deep dive paid off — Federation won and the junior shipped the credentials subgraph six weeks later.
