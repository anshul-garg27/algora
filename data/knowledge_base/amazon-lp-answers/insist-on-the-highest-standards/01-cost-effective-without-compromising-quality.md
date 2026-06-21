# Q: Describe a situation where you found a cost-effective solution without compromising on quality.

> **LP**: Insist on the Highest Standards
> **Primary story**: `G1 — ClickHouse Migration`
> **Backup story**: `W9 — Cosmos → Postgres for Transaction Event History`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

At GCC, we were on a single Postgres for everything. Transactional writes, analytics queries, dashboards. Around 10 million events a day were landing on it. Write latency had degraded by roughly 100x. The dashboards engineers loved were slowing the API tier down.

Adding more Postgres replicas was the easy answer. Finance had already pushed back on the bill.

### Task

I had to bring analytics costs and latency down without breaking the live platform. No big-bang cutover allowed.

### Action

I split the workload. Postgres kept the CRUD path. ClickHouse became the analytics store with MergeTree tables partitioned by `toYYYYMM(timestamp)`.

The cost lever was real columnar compression. Our event data compressed about 5x better than Postgres. So the analytics footprint shrank before I even tuned anything.

For the cutover, I refused to flip in one go. I designed a dual-write: Beat still wrote to Postgres, and also published the same event to RabbitMQ. Event-gRPC consumed from RabbitMQ and wrote to ClickHouse through a buffered sinker — batch size 1000, flush every 5 seconds. That batching alone cut the write I/O by about 99% compared to row-by-row inserts.

For about two weeks, both stores had the same data. I wrote validation queries — row counts per hour, checksums on key columns — and only flipped reads to ClickHouse once the diff was zero for three consecutive days.

I also moved dbt models from full-refresh to incremental. That dropped the daily compute by another big chunk because we stopped re-processing 30 days of data every night.

### Result

Analytics queries that took 30 seconds in Postgres came back in around 2 seconds. Infra cost on the analytics side dropped by roughly 30%. Data freshness on dashboards went from 24 hours to under an hour. No downtime, no lost rows.

Looking back, the discipline of the two-week dual-write window is what kept this clean. Cheaper but broken would've cost more than the original Postgres bill.

---

## Technical depth — if they probe

- **Why ClickHouse over more Postgres**: Columnar storage compresses event data 5x better. Aggregations over millions of rows run 10–100x faster. Postgres replicas would've scaled reads but not changed the cost curve.
- **Buffered sinker batching**: Go channel as a bounded queue (capacity 10,000), with two flush triggers — batch reaches 1000 events OR 5 seconds elapsed. That hits the ClickHouse sweet spot for write throughput without blowing latency.
- **Dual-write over CDC**: Considered Debezium CDC from Postgres to ClickHouse. Rejected because we already had RabbitMQ in the pipeline and a 4-person team couldn't operate Debezium. The simpler tool we already ran was the right call.
- **Validation gate**: Three consecutive clean days, not just one. Some bugs only show up across an end-of-day batch boundary.

---

## Likely follow-ups

**Q: How did you size the batch and flush interval?**
> I load-tested. 100, 500, 1000, 5000 batch sizes. 1000 gave the best throughput before ClickHouse started rejecting on memory. 5-second flush kept tail latency under 10 seconds for any single event.

**Q: What if RabbitMQ dropped a message during dual-write?**
> Durable queues with manual acks. The consumer only acked after the ClickHouse write returned success. If the consumer crashed mid-batch, RabbitMQ redelivered. My validation queries would've caught any silent gap.

**Q: Why not just buy more Postgres?**
> The analytics queries weren't slow because of Postgres tuning. They were slow because row storage is wrong for `SUM(...) GROUP BY day`. More hardware would've delayed the same problem.

**Q: Did you regret the dbt incremental move later?**
> Incremental models need careful watermarks. Once we got the unique key right, they were fine. Saved hours of warehouse time every night.

---

## What NOT to say

- Don't claim ClickHouse is "always better." It's wrong for transactional updates.
- Don't skip the dual-write step. The interviewer will hear "big-bang migration."
- Don't say "we saved 30%" without saying what (analytics infra, not total bill).

---

## Backup story (if asked for another)

At Walmart I led the Transaction Event History service off Cosmos DB onto Postgres on WCNP. Cosmos pricing was per RU and unpredictable — finance kept getting surprised by spikes. I migrated the persistence layer in PR #80 (+529/-333), kept the API contract identical, and held the cutover behind 4 codegate fix PRs across stage. Zero consumer impact, predictable monthly cost, and we built the Canada launch on top of it.
