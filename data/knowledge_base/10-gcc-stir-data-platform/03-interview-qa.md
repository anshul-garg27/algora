# Interview Q&A Bank - Stir Data Platform

> **Data engineering, ETL, and analytics questions with model answers.**
> Covers Airflow, dbt, ClickHouse, PostgreSQL, and data modeling.

---

## Opening Questions

### Q1: "Tell me about the data platform you built."

**Level 1 Answer:**
> "At Good Creator Co., I built Stir -- the data orchestration and transformation platform for an influencer marketing SaaS product. It processes social media data from Instagram and YouTube, transforms it through 112 dbt models in ClickHouse, and syncs analytics to PostgreSQL for the web application. I designed 76 Airflow DAGs with scheduling from every 5 minutes to weekly, cutting data latency by 50%."

**Follow-up:** "What's the business problem it solves?"
> "Brands like Coca-Cola and Nike need to find and evaluate influencers for marketing campaigns. They search by follower count, engagement rate, category, language, and country. Our platform ranks millions of profiles across multiple dimensions and updates these rankings in near-real-time. Without Stir, the analytics would be stale by hours or days."

**Follow-up:** "Walk me through the architecture."
> "It's a three-layer architecture. Layer 1 is ClickHouse -- our OLAP engine where dbt runs 112 models that compute rankings, engagement rates, growth metrics, and time series. Layer 2 is S3 staging -- ClickHouse exports JSON files using its native S3 integration. Layer 3 is PostgreSQL -- we SSH-download the files, parse JSONB, enrich with operational data, and do an atomic table swap so the SaaS app always reads consistent data. Airflow orchestrates everything with 76 DAGs across 7 scheduling tiers."

---

### Q2: "How did you cut data latency by 50%?"

> "Before Stir, data transformations ran as monolithic daily batch jobs. A profile update could take 24 hours to appear in the app. I restructured the pipeline into tiered scheduling. Core metrics -- follower counts, engagement rates -- now run every 15 minutes via the `dbt_core` DAG. Collections update every 30 minutes. Only heavy computations like full leaderboard rebuilds remain daily. The key insight was that not all data needs the same freshness. Scrape monitoring needs 5-minute freshness, but weekly growth rates inherently need a week of data. By matching scheduling frequency to business requirements, we went from 24-hour average latency to under 12 hours overall, with core metrics under 15 minutes."

**Follow-up:** "How do you prevent the fast schedules from overwhelming the system?"
> "Three mechanisms. First, `max_active_runs=1` on every DAG prevents a slow run from stacking with the next scheduled run. Second, `ShortCircuitOperator` pauses hourly and collection DAGs during the daily batch window (19:00-22:00 UTC) to avoid resource contention on ClickHouse. Third, timeout enforcement -- `dagrun_timeout` kills runaway jobs, from 40 minutes for simple hourly tasks to 360 minutes for the daily batch."

---

### Q3: "Explain the atomic table swap pattern."

> "When syncing analytics from ClickHouse to PostgreSQL, we never update the production table in-place. Instead, we create a temporary table, load all the data, enrich it with JOINs against operational tables, build indexes, and then within a single PostgreSQL transaction, RENAME the old table to `_old_bkp` and RENAME the new table to the production name. This gives us zero-downtime updates -- the SaaS app switches from reading the old table to the new table in a single atomic operation. No user ever sees partially updated data."

**Follow-up:** "Why not use UPSERT instead?"
> "With millions of rows, UPSERT causes row-level locking that blocks reads. The SaaS app queries these tables on every page load. With atomic swap, reads are never blocked. The trade-off is we need 2x storage temporarily, but that's cheap compared to user-facing latency."

**Follow-up:** "What if the swap fails?"
> "The transaction rolls back. The old table is untouched. We also keep the `_old_bkp` table so we can manually restore if something goes wrong after the swap."

---

### Q4: "Explain your dbt model architecture."

> "We have a two-layer architecture: 29 staging models and 83 mart models. Staging models extract raw data from source databases -- Beat for scrape data and Coffee for campaign data -- with minimal transformation. Mart models contain business logic: computing engagement rates, multi-dimensional rankings, growth metrics, and collection analytics. Models are organized by domain: discovery (16), leaderboard (14), collection (12), profile stats (14), genre (7), audience (4), posts (3), orders (1), and staging collections (9)."

**Follow-up:** "How do you manage dependencies between 112 models?"
> "dbt's `ref()` function handles this automatically. When I write `ref('stg_beat_instagram_account')`, dbt knows the staging model must run before the mart model. We also use dbt tags to group models by schedule: `tag:core` for every-15-minute models, `tag:daily` for once-a-day, `tag:collections` for every 30 minutes. Each Airflow DAG runs `DbtRunOperator(select=['tag:X'])` which only executes models in that tag group, respecting dependency order."

---

## Technical Deep Dive Questions

### Q5: "How do you use ClickHouse's argMax? Why not standard SQL?"

> "`argMax(value, timestamp)` is a ClickHouse aggregate function that returns the `value` at the row where `timestamp` is maximum. It's equivalent to a correlated subquery or window function in standard SQL but runs in a single pass. For example, `argMax(followers, updated_at)` gives me the most recent follower count per profile without a window function. We use it extensively for deduplication -- when the same profile has multiple rows (from overlapping incremental windows), `argMax` always picks the latest value."

```sql
-- Instead of this standard SQL:
SELECT followers FROM profiles WHERE updated_at = (SELECT MAX(updated_at) ...)

-- We write this ClickHouse-native:
SELECT argMax(followers, updated_at) followers FROM profiles GROUP BY profile_id
```

**Follow-up:** "What about argMaxIf?"
> "That's even more powerful. `argMaxIf(followers, date, date < now() - INTERVAL 30 DAY)` returns the latest follower count from before 30 days ago. We use it to compute growth metrics: `current_followers - followers_30d_ago`. In standard SQL, this would require a self-join or a complex window function with RANGE."

---

### Q6: "How does the ClickHouse-to-S3 export work?"

> "ClickHouse has a native `s3()` table function. We use `INSERT INTO FUNCTION s3(url, key, secret, format) SELECT ... FROM table`. This pushes query results directly from ClickHouse to S3 in a single operation -- no intermediate step. We use `JSONEachRow` format because PostgreSQL can `COPY` it directly into a JSONB column. The `s3_truncate_on_insert=1` setting overwrites the file on each run so we always have fresh data."

```sql
INSERT INTO FUNCTION s3(
    'https://gcc-social-data.s3.ap-south-1.amazonaws.com/data-pipeline/tmp/leaderboard.json',
    'KEY', 'SECRET', 'JSONEachRow'
)
SELECT * FROM dbt.mart_leaderboard
SETTINGS s3_truncate_on_insert=1, output_format_json_quote_64bit_integers=0;
```

**Follow-up:** "Why `output_format_json_quote_64bit_integers=0`?"
> "By default, ClickHouse quotes 64-bit integers as strings in JSON to prevent JavaScript precision loss. But PostgreSQL's JSONB parser expects unquoted numbers. This setting ensures integers are written as numbers, so `(data->>'followers')::int8` works correctly on the PostgreSQL side."

---

### Q7: "How do you handle data quality in the pipeline?"

> "Multiple layers. In ClickHouse, dbt's `ref()` ensures dependency order -- a mart model never runs before its staging dependencies. Our staging models use `COALESCE` for NULL handling and type casting. In the sync pipeline, PostgreSQL's `COPY` + `JSONB` parsing validates types -- if a field can't cast to `int8`, the COPY fails and the atomic swap never happens, so the old table stays live. We also use `replaceRegexpAll` in ClickHouse to sanitize URLs and text before export. Post-load enrichment joins against operational tables (Instagram accounts, YouTube accounts) ensure profile pictures and names are current."

**Follow-up:** "What happens if a dbt model fails?"
> "Airflow's `on_failure_callback` fires a Slack notification immediately with the DAG name, task ID, execution time, and a link to logs. The `max_active_runs=1` setting prevents the next scheduled run from starting while the failure is investigated. Since dbt models are idempotent (materialized as tables that get fully replaced), we can simply retry."

---

### Q8: "Explain the Jinja templating in your dbt models."

> "The most sophisticated use is in `mart_instagram_account`. We define a list of 19 metrics -- avg_likes, engagement_rate, followers_growth30d, audience_reachability, etc. -- and use a Jinja `for` loop to generate percentile-based grades for each metric. Instead of writing 19 nearly identical `CASE` statements by hand, the loop generates them dynamically:"

```sql
{% for metric in metrics %}
    multiIf(
        {{metric}} is null or {{metric}} == 0, NULL,
        {{metric}} > gm.p90_{{metric}}, 'Excellent',
        {{metric}} > gm.p75_{{metric}}, 'Very Good',
        {{metric}} > gm.p60_{{metric}}, 'Good',
        {{metric}} > gm.p40_{{metric}}, 'Average',
        'Poor'
    ) {{metric}}_grade,
    gm.group_avg_{{metric}} group_avg_{{metric}},
{% endfor %}
```

> "This generates 38 columns (grade + group average per metric) from 10 lines of Jinja. If we add a new metric, we just append to the list -- no SQL changes needed."

---

### Q9: "How do you handle the leaderboard ranking system?"

> "It's multi-dimensional. We rank influencers along 4 axes: followers, follower growth, views, and reels plays. Each axis is ranked globally and within 4 segmentation dimensions: by category, by language, by category+language, and by profile type. That's 28 rank dimensions per platform, stored as a ClickHouse Map type. We also store previous month's ranks in a separate Map column so the frontend can show rank changes (green arrow up, red arrow down). The `mart_leaderboard` model unions Instagram, YouTube, and cross-platform rankings into a single table."

**Follow-up:** "Why a Map type instead of separate columns?"
> "28 rank dimensions times 2 (current + previous) would be 56 columns. The Map type stores them as key-value pairs in a single column. PostgreSQL receives it as JSONB, so the frontend can access `current_month_ranks->>'followers_rank'` without us needing to maintain 56 separate columns. It also makes adding new rank dimensions backward-compatible."

---

### Q10: "How do you monitor 76 DAGs?"

> "Every DAG has `on_failure_callback = SlackNotifier.slack_fail_alert`. When a task fails, it sends a Slack message with the DAG ID, task ID, execution time, and a direct link to Airflow logs. We have `max_active_runs=1` to prevent cascading failures from parallel runs. `dagrun_timeout` kills runaway jobs -- from 40 minutes for simple tasks to 360 minutes for the daily batch. `catchup=False` prevents schedule-change backfills from overwhelming the system. For PostgreSQL sync, `runtime_parameters={'statement_timeout': '14400s'}` kills long-running queries."

---

## System Design Questions

### Q11: "If you were redesigning this from scratch, what would you change?"

> "Three things. First, I'd use a secrets manager instead of hardcoded credentials -- the current setup has AWS keys directly in DAG SQL strings. Second, I'd add data quality tests using dbt's built-in test framework -- `unique`, `not_null`, `accepted_values` -- which we didn't implement initially. Third, I'd consider ClickHouse Cloud or a multi-node cluster for high availability. Our single-node ClickHouse is a single point of failure."

### Q12: "How would you scale this to 10x the data volume?"

> "Three changes. First, ClickHouse scaling -- move to a multi-shard cluster with ReplicatedMergeTree for fault tolerance. Second, parallelize the dbt models -- our `concurrency=1` setting is conservative; with a cluster, we could run multiple models simultaneously. Third, replace the S3 staging with Kafka for real-time streaming -- instead of batch JSON exports, use ClickHouse's Kafka engine to stream changes to PostgreSQL. But honestly, ClickHouse handles 10x volume on a single node for analytical queries -- the bottleneck would be the PostgreSQL sync, which we'd solve by moving the SaaS app to read from ClickHouse directly."
