# Q: Typical `tell me about a time XXXX` LP questions.

> **LP**: Generic / multi-LP placeholder
> **Primary story**: `G1 — ClickHouse Migration`
> **Backup story**: `W8 — DC Inventory Search API`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

This entry is a placeholder for any generic "tell me about a time you…" prompt where the interviewer hasn't named a specific LP. The two stories below are my default go-tos — one technical depth + ownership (G1 ClickHouse), one bias-for-action + simple solution (W8 DC Inventory). Pick the angle that matches the LP being probed.

### Situation (G1 default)

GCC's Beat scraper crawled 500K+ Instagram and YouTube profiles a day. Every crawl wrote one or more log rows directly into Postgres — profile log, post log, sentiment log. At 10M+ rows a day, Postgres write latency had degraded from 5ms per insert to 500ms. Analytics queries — "how did this profile grow over 30 days?" — were taking 30 seconds because Postgres row-storage scans badly on time-series.

### Task

Stop the write saturation, speed up analytics, and not lose any data during cutover. I was the sole architect for this pipeline.

### Action

I designed a three-tier pipeline. Beat publishes log events as fire-and-forget messages to RabbitMQ. A Go service called `event-grpc` consumes them, batches them in-memory (10K capacity per channel), and flushes to ClickHouse on either a 1000-record threshold or a 1-minute ticker, whichever fires first.

ClickHouse was the right tool for this — MergeTree engine, partitioned by `toYYYYMM(event_timestamp)`, sorted by `(platform, profile_id, event_timestamp)`. Columnar storage compresses time-series 5x and reads single-column queries 10x faster than row storage.

The risky part was cutover. I ran dual-write for two weeks — every log went to both Postgres and the new RabbitMQ pipeline. Parity check: nightly row counts plus sampled deep-compare. Three consecutive clean nights, then we flipped reads to ClickHouse via a feature flag at the dbt layer. Postgres writes stayed for one more week as a safety net before decommission.

The buffered sinker is what made it work. Without batching, we'd have just moved the bottleneck from Postgres to ClickHouse — ClickHouse is bad at single-row inserts. The 1000-record batch flushed at either threshold or 1-minute ticker gave us 99 percent reduction in DB calls per second.

### Result

Write latency dropped from 500ms per event to 5ms per 1000-event batch. 30-day analytics queries went from 30s to about 12s. Storage shrank 5x for 1B rows. Infrastructure cost down 30 percent. Zero data loss across the cutover. The pattern is now used for all eight event types — profile log, post log, sentiment log, scrape-request log, the rest.

---

## Technical depth — if they probe

- **MergeTree config**: `PARTITION BY toYYYYMM(event_timestamp) ORDER BY (platform, profile_id, event_timestamp) SETTINGS index_granularity = 8192`. The order matters — it's the primary sort key for queries.
- **Buffered sinker mechanics**: Go channel with 10K capacity per event type. Goroutine reads from channel, accumulates into a slice, flushes on `len >= 1000` OR `time.NewTicker(1 * time.Minute)` whichever fires first.
- **Why RabbitMQ, not Kafka, here**: Beat was already running RabbitMQ for other workflows. Reusing infra beat adding Kafka. Throughput requirement was ~10M/day, well within a single-node RabbitMQ.
- **Cutover parity**: Nightly count match, sampled deep-equal on 1000 random rows. Three clean nights before flipping reads.

---

## Likely follow-ups

**Q: What's the most enriched answer you can give about this work?**
> The buffered sinker pattern. Without it, you've just moved the bottleneck — ClickHouse hates single-row inserts because each insert triggers a `MergeTree` part write and a background merge. Batching of 1000+ records per flush makes those merges efficient.

**Q: What would you change if you redid it?**
> I'd use Kafka instead of RabbitMQ for the durability story. RabbitMQ's at-most-once-by-default makes the loss model worse. With Kafka I'd have replay and the same dual-write would be cleaner.

**Q: How did you decide on 1000 records / 1 minute?**
> 1000 records gave us ~5MB batch — sweet spot for ClickHouse insert efficiency. 1-minute ticker matched our analytics freshness requirement. Tuned both with a 24-hour staging benchmark.

**Q: What about backup story for a bias-for-action LP?**
> Switch to W8 — DC Inventory Search API. The EI team had no capacity to build it, so I reverse-engineered three of their internal APIs with Charles Proxy, built the three-stage pipeline myself (GTIN → CID, supplier validation, EI fetch), and shipped in four weeks instead of their twelve-week estimate. 30,000+ queries/day in two months.

---

## What NOT to say

- "We just built it" — own the architecture call. I was the sole architect.
- Don't dive deep on ClickHouse internals unless asked. Lead with the impact.
- Avoid generic "I always think about scalability." Give the specific 5ms-to-500ms number.

---

## Backup story (if asked for another)

The DC Inventory Search API was a fast-execute project. EI team had no capacity to build it, so I reverse-engineered their internal APIs using Charles Proxy and Postman, designed a three-stage pipeline (GTIN-to-CID conversion via UberKey, supplier validation via Postgres, DC inventory fetch via EI), and shipped in four weeks. 30,000+ queries/day within two months, 1.8s P95 latency, zero production incidents. Three other teams copied the pattern.
