# Q: Describe a project you are most proud of.

> **LP**: Deliver Results
> **Primary story**: `G1 — ClickHouse Migration`
> **Backup story**: `W8 — DC Inventory Search API`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Mid-2023 at Good Creator Co. Beat was our Python scraping engine — 150+ workers crawling Instagram and YouTube, generating profile-log, post-log, sentiment-log entries that the SaaS app reads for influencer analytics. Volume was crossing 10 million log events a day. Postgres was choking. Write latency had drifted from 5ms per INSERT to 500ms. Profile-log and post-log tables had billions of rows and the autovacuum was running constantly. Time-series queries — "show me this influencer's follower growth over 30 days" — were taking 30 seconds because Postgres was scanning row-oriented storage for a metric workload.

### Task

Redesign the write pipeline so Postgres stopped saturating, time-series analytics ran in seconds, and we did not lose data during the migration.

### Action

I designed a three-tier pipeline spanning three services.

Beat (Python) stopped doing `session.add()` on log objects. Instead it called `make_scrape_log_event("profile_log", profile)` to publish to RabbitMQ. The old code is literally still commented in `processing.py` so you can see the before/after on the same lines. Fire-and-forget from the scraper's perspective.

Event-gRPC (Go) was the new consumer. I wrote it from scratch. Each topic — `profile_log_events`, `post_log_events`, `sentiment_log_events`, `scrape_request_events` — has its own sinker. The sinker buffers up to 1000 records in a Go channel, then either flushes when the channel fills or when a ticker fires every 1-5 minutes (configurable per topic). The flush is a batch INSERT into ClickHouse via GORM. That single change is the heart of the throughput jump — Postgres saw 10,000 INSERTs per second before, ClickHouse sees 10 batched INSERTs per second now.

ClickHouse table design mattered. `MergeTree` engine, `PARTITION BY toYYYYMM(event_timestamp)`, `ORDER BY (platform, profile_id, event_timestamp)`. That ordering means a "30-day follower growth for profile X on Instagram" query hits an indexed range scan on the same disk block.

Stir (Airflow + dbt) was the third tier. dbt models in ClickHouse compute the analytics — 29 staging models, 83 marts. Then a nightly job exports the materialized analytics back to Postgres as a JSON staging file on S3, and an atomic table swap loads them into the operational DB so the SaaS app keeps reading from Postgres.

Migration plan was two weeks of dual-write — Beat writing to both Postgres and RabbitMQ in parallel — so I could diff the row counts and prove no events were lost. After two clean weeks, I dropped the Postgres write path in `processing.py` and cleaned up the unused tables.

### Result

Write latency 500ms per event → 5ms per 1000 events. 99% reduction. Query time for a 30-day range on a profile 30 seconds → 12 seconds — 2.5x faster. Storage 5x compression because ClickHouse is columnar (1B logs went from 500GB to 100GB). Infrastructure cost 30% lower because the analytics shifted off the same Postgres cluster the SaaS app needed for OLTP. DB calls per second dropped from 10,000 to 10. Zero data loss in the cutover. I am proud of this one because it was real architecture, not a refactor — three services, three databases, a migration plan with proof, and numbers that actually moved.

---

## Technical depth — if they probe

- **Buffered sinker pattern**: Go channel with capacity 1000, ticker at 1-5 minutes per topic. Flush on either fill or tick. Batch INSERT via GORM. Single-digit ms per batch on ClickHouse.
- **ClickHouse table design**: `MergeTree`, `PARTITION BY toYYYYMM(event_timestamp)`, `ORDER BY (platform, profile_id, event_timestamp)`. Range scans on the ordering key for time-series queries.
- **Migration safety**: 2-week dual-write window. Daily diff of Postgres event counts vs RabbitMQ publish counts vs ClickHouse row counts. Three-way reconciliation.
- **Stir back to Postgres**: dbt models → ClickHouse INSERT INTO FUNCTION s3() → SSH download → atomic table swap (COPY + RENAME) in Postgres. Zero-downtime updates for the SaaS reader.

---

## Likely follow-ups

**Q: Why ClickHouse over a managed time-series DB like Timescale?**
> ClickHouse columnar compression was 5x vs Timescale's 2-3x at our scale. And the SQL surface was familiar — dbt-clickhouse adapter let me reuse the model patterns we already had on Postgres.

**Q: What was the biggest risk?**
> Data loss during cutover. The 2-week dual-write window with daily count reconciliation was the insurance. I would not have dropped the Postgres path without three days of clean diffs in a row.

**Q: What broke first time around?**
> First buffer tuning was too aggressive — 10K records per batch. ClickHouse `OPTIMIZE` started lagging. Dropped to 1K, problem went away.

**Q: How did the team adopt it?**
> They saw the dashboard. 30-second leaderboard queries became 12-second. That sold it more than any architecture doc.

---

## What NOT to say

- Do not say "I migrated everything." The Postgres OLTP path stayed — only the time-series log writes moved.
- Do not call it a cost-cut project. The cost savings were a side effect of the right architecture.
- Do not skip the dual-write window. That is the part that made the migration safe.

---

## Backup story (if asked for another)

W8 — DC Inventory Search API. End-to-end ownership of a supplier-facing API at Walmart — 898 lines of OpenAPI spec first, then 3,059 lines of implementation, then a 1,903-line error-handling refactor, then 1,724 lines of container tests. 8,000+ lines total. 1.8s P95 on 100-item bulk queries. 30,000+ queries/day inside two months. Three other teams copied the 3-stage pipeline pattern.
