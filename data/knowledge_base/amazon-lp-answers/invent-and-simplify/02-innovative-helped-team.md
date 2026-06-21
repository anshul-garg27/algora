# Q: Tell me about a time, you did something innovative which helped the team.

> **LP**: Invent and Simplify
> **Primary story**: `G1 — ClickHouse Migration`
> **Backup story**: `W2 — Shared Library Adoption`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

At Good Creator Co. our Beat scraper was generating 10 million log events a day — follower counts, post likes, sentiment snapshots. Every event went straight into Postgres via `session.add()`. Write latency had crept from 5ms to 500ms. Analytics queries on `profile_log` took 30+ seconds. Storage was bleeding money. The team was talking about throwing more Postgres replicas at it.

### Task

I was the SE-I owning the data plumbing. I thought we were solving the wrong problem — Postgres wasn't the right tool for append-only time-series at this scale. I proposed a different shape and had to build it.

### Action

I designed a three-tier pipeline. Beat publishes events to RabbitMQ instead of writing to Postgres directly. A Go consumer service called Event-gRPC buffers them. ClickHouse stores them.

The key invention was the buffered sinker. ClickHouse hates small inserts — each one creates a new data part and the merge overhead kills you. So I built a dual-trigger flush. Each sinker is a goroutine. Events come in on a buffered channel (10,000 capacity). The sinker has a `select` statement watching the channel and a 1-minute ticker. Two flush triggers — whichever fires first: batch hits the size limit (1000 records) or the ticker ticks. Size-based flush wins during peak load. Time-based flush prevents events from sitting around at 3 AM when traffic is low.

For the schema I picked MergeTree with `PARTITION BY toYYYYMM(event_timestamp)` and `ORDER BY (platform, profile_id, event_timestamp)`. A 30-day query opens at most two partitions. Columnar storage means we only read the two columns we need, not the whole row.

I rolled it out dual-write first for two weeks — Beat wrote to both Postgres and RabbitMQ. We validated row counts (under 0.1 percent drift) and spot-checked specific influencers day by day. Then dbt models switched their reads. Then I commented out the Postgres writes. You can still see the commented-out `session.add(profile)` in `processing.py`.

### Result

10,000 individual inserts per second became 10 batch inserts per second. 99.9 percent I/O reduction. Time-series queries went from 30 seconds to 12 seconds — about 2.5x faster. 5x compression on disk. Infrastructure cost dropped about 30 percent. Two other teams adopted the same buffered-sinker pattern for their analytics pipelines.

---

## Technical depth — if they probe

- **Dual-trigger flush**: One `select` on the events channel and a `time.NewTicker(1*time.Minute)`. Size optimises throughput, ticker bounds latency. Without the ticker, low-traffic events sit forever waiting for batch size.
- **Why ClickHouse, not Kafka + Postgres**: We needed analytics queries fast, not just durability. ClickHouse's columnar MergeTree gives both: durable append + fast scans. Kafka would have left us still querying Postgres.
- **`PARTITION BY toYYYYMM` not daily**: Daily would mean 365 partitions a year. Too many small parts = merge thrash. Monthly is the sweet spot for our query shape ("last 30 days").
- **RabbitMQ over Kafka**: RabbitMQ was already the messaging backbone for credential validation, identity events. Team knew it. At 115 events/sec average, Kafka would have been overkill.
- **Early ACK trade-off**: We ACK the RabbitMQ message when it lands in the channel, not after the ClickHouse flush. If the sinker crashes mid-batch, we lose that batch. Acceptable for log data — would not be acceptable for orders.

---

## Likely follow-ups

**Q: What if RabbitMQ goes down?**
> Beat's `make_scrape_log_event` is wrapped in try/except. A publish failure logs and moves on — the scraper keeps running. We lose log events, not scrape data. Availability over consistency was the deliberate call for log data.

**Q: How did you choose batch size 1000?**
> ClickHouse docs recommend 1000-100000 per batch. At 1000 rows × 500 bytes each that's ~500KB per insert — well under the network limit. We started at 100, saw "Too many parts" warnings, raised to 1000, warnings went away.

**Q: What about exactly-once?**
> Each event has a UUID `event_id`. ClickHouse doesn't enforce uniqueness but our dbt models use `argMax(metric, event_timestamp)` so duplicates collapse at the query layer. For real exactly-once we'd need ReplacingMergeTree or transaction-bound ACK — neither was worth the cost.

**Q: How did you validate the migration didn't lose data?**
> Three checks. Daily row counts between Postgres `profile_log` and ClickHouse `profile_log_events` (under 0.1 percent drift). Spot-checks on specific high-profile influencers day by day. Downstream check — leaderboard rankings matched 99.9 percent between old and new sources.

**Q: Would you build this the same way today?**
> Mostly yes. I'd switch to late-ACK so the RabbitMQ message only ACKs after a successful ClickHouse flush — zero data loss in exchange for slightly lower throughput. And I'd extract the top 10 metrics as native columns instead of a JSON blob, to cut `JSONExtractInt` overhead.

---

## What NOT to say

- Don't claim 50x or 100x faster — the measured number is 2.5x retrieval. Be precise.
- Don't say "we used Kafka" — we used RabbitMQ. Mixing these up tanks credibility.
- Don't pitch this as "I invented ClickHouse buffered writes" — it's a known pattern; the invention was applying dual triggers and a clean migration path.

---

## Backup story (if asked for another)

At Walmart I noticed three teams independently building audit logging — same servlet filter, same async sender, slightly different code. I proposed a shared Spring Boot starter JAR with the common 80 percent inside and the 20 percent (endpoint list, response-body capture) as CCM config. Three teams adopted it. Integration time dropped from two weeks to one day. The library is on version 0.0.54 and is the default for any new supplier-facing service.
