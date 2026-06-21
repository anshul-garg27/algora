# Q: Describe a time you reduced cost without sacrificing quality.

> **LP**: Frugality
> **Primary story**: `W9 — Cosmos → PostgreSQL migration`
> **Backup story**: `G3 — Stir CH→S3→PG sync (no new tooling)`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

At Walmart, our transaction event history service was running on Cosmos DB. It stored every supplier-facing API transaction for audit and rebill purposes — millions of rows growing daily. Cosmos was expensive — provisioned RU/s for predictable throughput, plus storage. The latency was also inconsistent — P95 lookups would occasionally spike past 500ms when a partition got hot. We were already on PostgreSQL elsewhere in the stack.

### Task

Cut the Cosmos bill without losing data, breaking the rebill workflow, or degrading lookup latency for the support team. My slice was the design and the cutover.

### Action

I started by understanding what Cosmos was actually doing for us. The reads were almost all keyed lookups — "show me transactions for `consumer_id X` between `date A` and `date B`." Almost never cross-partition scans. Writes were append-only.

That access pattern doesn't justify Cosmos's premium. A partitioned PostgreSQL table with a covering index on `(consumer_id, transaction_date)` does the same job for a fraction of the price.

I picked PostgreSQL with declarative partitioning by month on `transaction_date`. Each month is its own partition; old partitions can be detached and archived. Covering index on `(consumer_id, transaction_date)` plus a partial index on the high-traffic suppliers. Connection pool sized to the actual concurrency profile — we'd been over-provisioning RU/s for safety.

The migration was two weeks of dual-write. Both Cosmos and PostgreSQL got every new transaction. I backfilled history into PostgreSQL using a paginated read from Cosmos — chunked by `consumer_id` to avoid hot partitions during the export. Verified parity with daily row-count diffs and spot-checks on top suppliers' rebill data.

Then I switched the read path service-by-service. Support tooling first (low blast radius), then the rebill workflow (high-stakes), then the internal dashboards. After 30 days of clean reads from PostgreSQL, I stopped the Cosmos writes and deleted the resource.

### Result

Cosmos bill went away. PostgreSQL added a small incremental cost — the table sat on shared instances we already paid for. P95 lookup latency tightened from variable spikes to a predictable sub-100ms because the access pattern matched PostgreSQL's strengths. Zero data loss across the cutover. Support team didn't notice the swap.

The thing that mattered was matching the storage to the access pattern, not picking the "best" database. Cosmos is great at global, multi-region, low-latency document workloads — none of which we actually needed.

---

## Technical depth — if they probe

- **PostgreSQL declarative partitioning**: `PARTITION BY RANGE (transaction_date)` with monthly child tables. Auto-managed by pg_partman. Old partitions detached to S3.
- **Covering index**: `(consumer_id, transaction_date) INCLUDE (status, amount, ...)` so the index alone serves the hot query without heap fetches.
- **Why not DynamoDB or another KV**: Same as why not Cosmos — paying global-scale prices for a regional, keyed-lookup workload.
- **Dual-write window**: Both DBs received every new transaction for 2 weeks. Daily parity checks. Cutover happened after 30 days of clean reads.
- **Backfill strategy**: Paginated by `consumer_id` to avoid hot Cosmos partition reads during the export. Throttled to stay inside RU budget.

---

## Likely follow-ups

**Q: Why not just tune Cosmos better?**
> Cosmos was correctly tuned for what it does. The mismatch was using a multi-region document DB for a keyed-lookup workload. Tuning wouldn't fix the price.

**Q: Did latency really get better?**
> P95 was the win — Cosmos had occasional spikes from hot-partition rebalancing. PostgreSQL with proper indexes was boringly predictable. P50 was similar.

**Q: What if write volume grew 10x?**
> Partition write spread by month means writes hit one partition at a time. Past 10x I'd shard by `consumer_id` hash too. Pattern scales.

**Q: How did you verify no data loss?**
> Daily row-count diffs during dual-write. Cross-validated rebill totals between Cosmos and PostgreSQL for top 20 suppliers. Matched to the cent.

**Q: What broke during the migration?**
> One support query was hitting a Cosmos secondary index that didn't exist in PostgreSQL. I added the partial index after spotting it in slow-query logs. Caught in week 2, before cutover.

---

## What NOT to say

- Don't trash Cosmos — it's good at its actual job.
- Don't oversell — PostgreSQL also costs money, just less.
- Don't skip "match storage to access pattern" — that's the actual lesson.

---

## Backup story (if asked for another)

For Stir at GCC, I needed to move aggregated analytics from ClickHouse to the PostgreSQL that Coffee read for API serving. Instead of buying a CDC tool, I used the Airflow we already had — a DAG that ran `INSERT INTO FUNCTION s3(...) FROM clickhouse_query`, then a second task that did atomic table swap on PostgreSQL via temp-table + rename. Zero new tooling, zero downtime, ran every 15 minutes.
