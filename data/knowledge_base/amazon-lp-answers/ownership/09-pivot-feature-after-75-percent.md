# Q: Tell me about a time you had to pivot the direction of a feature after it was 75% developed.

> **LP**: Ownership
> **Primary story**: `G3 — Data Platform / Stir`
> **Backup story**: `W5 — Spring Boot 3 Migration`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

At Good Creator Co., I was about three months into building Stir — our analytics data platform on Airflow and dbt. The original plan was straightforward. All metrics ran on a daily batch schedule. I'd built about 50 DAGs and the first batch of dbt models. Then a customer call landed in my lap.

A brand using our platform was about to commit a budget to a fashion influencer based on yesterday's engagement-rate dashboard. That morning, the influencer's most recent post had gone viral — millions of new likes. Our dashboard wasn't going to reflect that until the next day's run. The brand asked: "are these numbers fresh?" Our answer was "they're from yesterday."

### Task

The platform was about 75% done with the daily-batch design. Pivot to something that supported much fresher data for the metrics that mattered, without throwing away three months of dbt models.

### Action

I sat with the customer call notes and our own access logs for a day. Which dashboards did brands actually look at right before signing deals? Engagement rate, post-rank-by-engagement, recent post counts, leaderboard. Maybe ten metrics out of about eighty. The rest could absolutely stay daily — historical aggregations, full-refresh marts, weekly demographics.

That gave me a real plan. Don't redesign the platform. Add scheduling tiers on top of it.

Five tiers. Every 5 minutes for the truly time-sensitive — `dbt_recent_scl` (recent scrape logs) and `post_ranker`. Every 15 minutes for `dbt_core`, the critical engagement metrics. Every 30 minutes for collections. Hourly for most sync operations. Daily and weekly for heavy aggregations.

The pivot was structurally cheap because dbt's dependency DAG let me tag models. `dbt run --models tag:core` ran a slice of the 112 models, not all of them. I refactored the 50 existing DAGs to declare which tier they belonged to. Three new DAGs picked up the 5-minute and 15-minute work.

The ClickHouse → S3 → PostgreSQL sync pipeline was the tricky bit. Coffee, the REST API, read from PostgreSQL. So fresh data in ClickHouse meant nothing if it didn't reach Postgres fast. I built the sync as `INSERT INTO FUNCTION s3('...', 'JSONEachRow')` from ClickHouse, SSH download to the PG server, atomic table swap with `COPY` and rename. Zero-downtime swap so consumers always saw either old data or new, never partial.

I also pushed back on one tier internally. The team lead wanted every metric on 5-minute refresh. I argued that aggregations over millions of rows every 5 minutes would cost more than it gained. We agreed on the tier mapping in a 30-minute design review.

### Result

Average data freshness went from 24 hours to under 1 hour — about 50% latency reduction overall. The metrics brands actually used pre-deal were on 15-minute refresh. 76 DAGs total across the 5 tiers, 112 dbt models. Slack alerts on pipeline failures through `slack_failure_conn`. Brands stopped asking "are these fresh?" within a month.

The thing I'd say I learned: when you pivot late, don't redesign — re-tier. Most of the platform was right. The schedule was wrong.

---

## Technical depth — if they probe

- **dbt tagged model selection**: Each model has `tags: ['core']` or `tags: ['daily']` in its config. `DbtRunOperator(select="tag:core")` runs only that slice. Lets you reuse one dbt project across 5 schedules.
- **Five scheduling tiers**: 5 min (recent_scl, post_ranker), 15 min (dbt_core), 30 min (collections), hourly (most syncs), daily/weekly (heavy aggregations).
- **ClickHouse → S3 → PG sync**: `INSERT INTO FUNCTION s3('gcc-social-data/tmp/leaderboard.json', 'JSONEachRow') SELECT * FROM dbt.mart_leaderboard`. Airflow SSHOperator downloads to PG host. PostgresOperator does `CREATE TABLE tmp_x`, `COPY tmp_x FROM ...`, `ALTER TABLE ... RENAME`. Atomic swap, zero downtime.
- **Airflow operator mix**: 46 PythonOperator (API calls), 20 PostgresOperator (data load), 19 ClickHouseOperator (exports), 18 SSHOperator (file transfers), 11 DbtRunOperator. Five connections — `clickhouse_gcc`, `prod_pg`, `stage_pg`, `ssh_prod_pg`, `beat`.
- **Why frequency-based not event-driven**: We considered event-driven refresh (RabbitMQ → trigger DAG). Rejected because the dbt DAG has long-running models and concurrent triggers would step on each other. Frequency was simpler and met the freshness target.

---

## Likely follow-ups

**Q: How did you decide which metrics get 5-minute refresh?**
> Looked at access logs — which dashboards were viewed within an hour of campaign decisions. Engagement rate and post-rank were the heavy hitters. Demographic breakdowns and weekly summaries weren't time-sensitive. Data, not intuition.

**Q: What did you throw away?**
> Almost nothing. The dbt models were schedule-agnostic — they're just SQL. The DAGs got refactored to declare tiers. Maybe a day of throwaway work out of three months.

**Q: Cost impact of the 5-minute tier?**
> Real but bounded. The 5-minute DAGs were the cheapest dbt models — recent scrape logs and post-ranking, both incremental. Heavy aggregations stayed daily. ClickHouse compute cost went up about 15% overall. The customer-impact win was worth it.

**Q: Did the team push back?**
> Yes — the team lead wanted everything on 5-minute refresh. I pushed back with the cost numbers. We agreed on the tier mapping after a 30-minute design review.

**Q: What's the failure mode if a 5-minute DAG falls behind?**
> Airflow's `max_active_runs=1` means we don't pile up concurrent runs. If one is slow, the next gets skipped and we eat a freshness penalty for one cycle. Slack notification fires through `slack_failure_conn`. Manual catch-up is straightforward.

---

## What NOT to say

- Don't call it a "rewrite" — it was a re-tiering. The pivot was structural, not from scratch.
- Don't claim "real-time" — it's near-real-time, 5 to 15 minutes depending on tier.
- Don't say "112 dbt models" without context — 29 staging, 83 mart, organised by domain (audience, collection, discovery, genre, leaderboard, etc.).
- Don't pitch ClickHouse as a hot transactional store — it's analytics, columnar, append-only. PostgreSQL was still the OLTP store for Coffee.

---

## Backup story (if asked for another)

The Spring Boot 3 migration at Walmart. I'd planned to migrate six services over six weeks using a clean cut-over. About four weeks in, the senior architect challenged my use of `.block()` on a WebFlux call inside a synchronous filter. I'd defended it overnight and realised he was right. Pivoted to keep the migration moving but added a tech-debt write-up to revisit the reactive boundary. Shipped all six services on schedule with zero customer impact through Flagger canary.
