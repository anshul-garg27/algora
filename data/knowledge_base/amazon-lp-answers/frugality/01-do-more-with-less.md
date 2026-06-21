# Q: Give an example of a time when you had to do more with less.

> **LP**: Frugality
> **Primary story**: `G1 — ClickHouse Migration`
> **Backup story**: `W9 — Cosmos → Postgres`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Good Creator Co was a small influencer-analytics SaaS. Five engineers total. No DevOps, no separate data engineer. Beat — our scraping engine — was emitting 10M+ log events a day from 150+ async workers. PostgreSQL was choking. Write latency went from 5ms to 500ms. Analytics queries on `profile_log` took 30 seconds and the dashboard was crawling.

The "right" answer was a managed analytics warehouse — Snowflake, BigQuery, Redshift. Any of those would cost us $5-10K/month plus an engineer-month to integrate. Neither was on the table.

### Task

Get analytics off PostgreSQL onto something that compressed well, queried fast, and we could operate alone. With no extra headcount and no external spend.

### Action

I picked ClickHouse, self-hosted on the boxes we already had. Reasons: columnar, single binary, no Hadoop or ZooKeeper, and we'd already been running it for a smaller event stream so the team had basic operational muscle.

The pipeline was Beat → RabbitMQ → Go consumer (event-grpc) → ClickHouse. RabbitMQ was already our messaging backbone for credential events and Identity events, so no new infra. Event-grpc already existed for app analytics; I added log-event consumers to it instead of building a new service. Buffered sinker pattern — Go channel of 10K capacity, flush at batch-size-1000 or 1-minute ticker.

ClickHouse schema: `MergeTree` partitioned `toYYYYMM(event_timestamp)`, `ORDER BY (platform, profile_id, event_timestamp)`. Monthly partitions matched how dbt and the dashboard actually queried — last 30 days, last 90 days. ORDER BY matched "show me this influencer's metrics."

Migration was 2-week dual-write. Beat kept `session.add()` to PostgreSQL and also called `make_scrape_log_event()` to publish to RabbitMQ. I ran row-count diffs hourly and spot-checked top influencers. Parity within 0.02%. Switched dbt reads to ClickHouse. Commented out the PostgreSQL writes. Done.

### Result

Query times went from 30 seconds to 12 seconds. Storage compressed 5x — 500GB down to 100GB. Infra cost dropped about 30%. Zero new tooling, zero new headcount, no external spend. The team-of-5 ran six services after this; ClickHouse just slotted in.

The "less" was real — no dedicated data engineer, no managed warehouse budget. Working with what we had forced choices that turned out to be better than the catalogue answer.

---

## Technical depth — if they probe

- **MergeTree, not ReplacingMergeTree**: Log events are append-only. ReplacingMergeTree has merge overhead for dedup logic we didn't need.
- **`PARTITION BY toYYYYMM`**: Monthly partitions for partition pruning. Daily would have created too many small parts.
- **Dual-trigger buffered sinker**: Size limit + ticker. Size optimises throughput, ticker bounds latency in quiet hours.
- **Metrics as JSON, not columns**: Different platforms have different metrics. JSON keeps Beat free to add fields without an `ALTER TABLE` round trip.
- **Why not Kafka**: RabbitMQ was already in production. Switching messaging systems for one pipeline isn't frugal.

---

## Likely follow-ups

**Q: Why not Snowflake or BigQuery?**
> Cost and team size. Both would have been $5-10K/month and a multi-week integration. ClickHouse self-hosted was zero new spend and shipped in 4 weeks.

**Q: What if you'd needed exactly-once?**
> ACK after flush instead of on channel push. Trades throughput for reliability. For log data, throughput won.

**Q: How did you operate ClickHouse with no DevOps?**
> Single-node deployment, daily backup to S3, Sentry on the Go consumer for ingestion errors. Not pretty, but it ran for the rest of my time there.

**Q: How did you know dbt would be happy?**
> Wrote one model — `stg_beat_profile_log` — against ClickHouse first and compared its output to the PostgreSQL version. Same numbers, faster build.

**Q: What broke later?**
> Hit a "too many parts" warning early on — flush batch size was too low. Tuned to ~1,000. After that the system held.

---

## What NOT to say

- Don't pitch this as a tech choice — pitch it as a constraints choice.
- Don't oversell ClickHouse — managed warehouses are better at most things; we just couldn't afford them.
- Don't skip the "and no DevOps" line — that's the frugality point.

---

## Backup story (if asked for another)

At Walmart, the transaction event history was on Cosmos DB. Cost was significant and read latency was inconsistent. I migrated it to PostgreSQL with proper partitioning on `transaction_date` and a covering index on `consumer_id, transaction_id`. We dropped Cosmos. Cost fell and query latency tightened to a predictable P95. Same data, smaller bill.
