# Technical Decisions Deep Dive - "Why THIS and Not THAT?"

> **Every major decision in the Stir data platform with alternatives, trade-offs, and follow-up answers.**
> This is what separates "good" from "excellent" in a hiring manager interview.

---

## Decision 1: Why ClickHouse -> S3 -> PostgreSQL Instead of Direct Sync?

### What's In The Code
```python
# Three-step pipeline in every sync DAG:
fetch_from_ch = ClickHouseOperator(sql="INSERT INTO FUNCTION s3(...) SELECT * FROM dbt.mart_table")
import_to_pg_box = SSHOperator(command="aws s3 cp s3://... /tmp/")
import_to_pg_db = PostgresOperator(sql="COPY ... FROM '/tmp/file.json'")
```

### The Options

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **CH -> S3 -> PG** | Decoupled stages, S3 as checkpoint, can retry individual steps | Extra latency, S3 costs | **YES** |
| **Direct ClickHouse -> PostgreSQL** | Fewer hops, lower latency | No checkpoint, CH has no native PG writer, failures require full restart | No |
| **Kafka CDC** | Real-time, event-driven | Overkill for batch analytics, complex setup | No |
| **pg_foreign_data_wrapper** | Direct SQL access | Terrible performance for large datasets, network bottleneck | No |

### Interview Answer
> "We chose S3 as an intermediate staging layer because it decouples ClickHouse from PostgreSQL. If the PostgreSQL load fails, we don't need to re-export from ClickHouse -- the JSON file is already in S3. ClickHouse has native S3 integration via `INSERT INTO FUNCTION s3()` which is very efficient. The alternative of direct sync doesn't exist natively -- ClickHouse has no built-in PostgreSQL writer. We could have used Kafka CDC, but our use case is batch analytics, not real-time streaming. The S3 staging approach gives us retry-ability, auditability (the JSON files are still there), and separation of concerns."

### Follow-up: "Doesn't the S3 hop add latency?"
> "Yes, roughly 2-3 minutes for the S3 export and download. But our fastest pipeline runs every 15 minutes, so 2-3 minutes is acceptable. The benefit is that if PostgreSQL is under load or the COPY fails, we don't need to re-query ClickHouse. We just re-download from S3 and retry."

### Follow-up: "Why not write directly from ClickHouse to PostgreSQL using clickhouse_fdw?"
> "Foreign data wrappers work for small queries, but we're syncing entire mart tables -- sometimes millions of rows. FDW sends data row by row over the network. COPY from a local file is orders of magnitude faster because it bypasses the network and uses PostgreSQL's bulk loader."

---

## Decision 2: Why Apache Airflow vs Prefect/Dagster?

### What's In The Code
```python
from airflow import DAG
from airflow_dbt_python.operators.dbt import DbtRunOperator
from airflow_clickhouse_plugin.operators.clickhouse import ClickHouseOperator
```

### The Options

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **Apache Airflow** | Mature ecosystem, rich operator library, dbt/CH/PG plugins | Complex setup, DAG parsing overhead | **YES** |
| **Prefect** | Pythonic, better local dev, dynamic flows | Smaller plugin ecosystem, no native CH operator | No |
| **Dagster** | Type system, asset-based, better testing | Steep learning curve, less community | No |
| **dbt Cloud** | Native dbt scheduling | Can't orchestrate non-dbt tasks (SSH, PG ops) | No |

### Interview Answer
> "Airflow was the right choice because our pipelines are heterogeneous -- they combine dbt runs, ClickHouse exports, SSH file transfers, and PostgreSQL operations. Airflow has mature operators for all of these: `DbtRunOperator`, `ClickHouseOperator`, `SSHOperator`, `PostgresOperator`. Prefect has better Pythonic ergonomics but lacks native ClickHouse integration. Dagster's asset-based model is interesting but adds complexity we didn't need. dbt Cloud could schedule dbt models, but it can't orchestrate the SSH transfers and PostgreSQL atomic swaps that are core to our pipeline."

### Follow-up: "What are the downsides of Airflow you've experienced?"
> "DAG parsing time is the biggest issue -- with 76 DAGs, the scheduler takes time to parse all files. We also had to be careful with `max_active_runs=1` and `concurrency=1` on every DAG to prevent resource contention. The UI can be slow with many DAGs. If I were starting fresh today, I might consider Dagster for its better testing story."

---

## Decision 3: Why dbt for Transformations vs Custom Python?

### What's In The Code
```sql
-- dbt model with Jinja templating, refs, and tags
{{ config(materialized = 'table', tags=["hourly"], order_by='ig_id') }}
select * from {{ref('stg_beat_instagram_account')}} ia
left join {{ref('mart_audience_info')}} aud on aud.platform_id = ia.profile_id
```

### The Options

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **dbt** | SQL-native, dependency tracking, incremental, Jinja templating | Learning curve, ClickHouse adapter maturity | **YES** |
| **Custom Python (pandas)** | Full flexibility, ML integration | Slow at scale, no dependency management, hard to maintain | No |
| **Spark SQL** | Distributed, handles huge data | Overkill for our scale, complex infra | No |
| **Stored procedures** | Database-native | No version control, no dependency DAG, hard to test | No |

### Interview Answer
> "dbt gives us three critical things. First, `ref()` creates an automatic dependency graph -- when I write `ref('stg_beat_instagram_account')`, dbt knows to run the staging model first. With 112 models, manual dependency management would be impossible. Second, Jinja templating lets us generate SQL dynamically -- our mart_instagram_account model loops over 19 metrics to generate performance grades, which would be hundreds of lines of hand-written SQL. Third, the tag system lets us group models by schedule frequency -- `tag:core` runs every 15 minutes, `tag:daily` runs once. Custom Python scripts in pandas would work for small datasets but can't handle the volume or complexity of our 83 mart models."

### Follow-up: "Any issues with dbt on ClickHouse?"
> "The dbt-clickhouse adapter was version 1.3.2 when we adopted it -- relatively early. We had to work around some missing features like partial refresh support. The `order_by` config is ClickHouse-specific and not standard dbt. But the benefits of SQL-first transformations with dependency management far outweighed the adapter limitations."

---

## Decision 4: Why Atomic Table Swap vs UPSERT?

### What's In The Code
```sql
-- Atomic swap pattern (used in every sync DAG)
BEGIN;
    ALTER TABLE "leaderboard" RENAME TO "leaderboard_old_bkp";
    ALTER TABLE "leaderboard_tmp" RENAME TO "leaderboard";
COMMIT;
```

### The Options

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **Atomic table swap (RENAME)** | Zero-downtime, consistent snapshot, simple | Full table rebuild, temporary 2x storage | **YES** |
| **UPSERT (INSERT ON CONFLICT)** | Incremental, less storage | Row-level locking, inconsistent reads during update, slow for millions of rows | No |
| **DELETE + INSERT** | Simple | Table locked during operation, inconsistent reads | No |
| **Materialized views** | Automatic refresh | PostgreSQL matview refresh locks table, no concurrent reads | No |

### Interview Answer
> "UPSERT sounds ideal on paper, but with millions of rows being updated, the row-level locking in PostgreSQL causes significant contention. Our SaaS app reads these tables for every API request -- leaderboard queries, profile lookups, collection analytics. With UPSERT, users would see inconsistent data during the update window (some rows old, some new). The atomic RENAME happens in a single transaction -- one instant the old table is serving, the next instant the new table is serving. Zero inconsistency, zero downtime. The trade-off is we need 2x storage temporarily, which is cheap compared to the consistency guarantee."

### Follow-up: "What happens if the swap fails mid-transaction?"
> "PostgreSQL's transaction guarantees protect us. If the RENAME fails -- say the new table has constraint violations -- the entire transaction rolls back. The old table is still in place. We also keep the old table as `_old_bkp` so we can manually restore if needed."

### Follow-up: "Why UNLOGGED tables for the temporary table?"
> "We use `CREATE UNLOGGED TABLE` for the temp table in the leaderboard sync. UNLOGGED tables skip WAL writes, making inserts 2-3x faster. We then `ALTER TABLE SET LOGGED` before the swap. Since the temp table is disposable -- we rebuild it every run -- the risk of data loss on crash is acceptable."

---

## Decision 5: Why ReplacingMergeTree vs Standard MergeTree?

### What's In The Code
```sql
{{ config(
    materialized='incremental',
    engine='ReplacingMergeTree()',
    order_by='(profile_id, date)',
    incremental_strategy='append'
) }}
```

### The Options

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **ReplacingMergeTree** | Automatic dedup on merge, idempotent inserts | Dedup not guaranteed until merge, needs FINAL for exact reads | **YES** |
| **Standard MergeTree** | Simplest, fastest inserts | Duplicates accumulate, must handle dedup in queries | No |
| **CollapsingMergeTree** | Can handle updates/deletes | Complex sign column logic, error-prone | No |
| **AggregatingMergeTree** | Pre-aggregated state | Only for aggregate queries, not raw data | No |

### Interview Answer
> "We chose ReplacingMergeTree because our pipelines are append-only with overlapping windows. The 4-hour lookback means we re-process some records that were already inserted. ReplacingMergeTree automatically deduplicates during background merges based on the ORDER BY key. With standard MergeTree, these duplicates would accumulate and inflate our query results. CollapsingMergeTree was considered but requires tracking a 'sign' column for inserts and deletes -- too error-prone for our use case. The trade-off is that before a merge happens, `SELECT` queries might see duplicates, but for our analytics use case, minor temporary duplicates are acceptable."

### Follow-up: "How do you handle the pre-merge duplicate issue?"
> "For models where exact dedup matters, we use `argMax(value, timestamp)` in the SQL query itself. This gives us the latest value per key regardless of whether ClickHouse has merged the parts yet. For example: `argMax(followers, updated_at) followers` always returns the most recent follower count."

---

## Decision 6: Why Incremental 4-Hour Lookback vs Full Refresh?

### What's In The Code
```sql
{% if is_incremental() %}
WHERE created_at > (
    SELECT max(last_updated) - INTERVAL 4 HOUR
    FROM {{ this }}
)
{% endif %}
```

### The Options

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **4-hour lookback** | Processes only recent data + safety margin, fast | Misses data older than 4 hours | **YES (for time series)** |
| **Full refresh** | Always correct, no missed data | Slow for large tables, unnecessary reprocessing | Used for daily models |
| **Exact incremental (no lookback)** | Minimal processing | Misses late-arriving data, data gaps | No |
| **Event-driven (CDC)** | Real-time, no polling | Complex setup, overkill for batch analytics | No |

### Interview Answer
> "We use a hybrid approach. Time-series models like `mart_time_series` use incremental with a 4-hour lookback window. The lookback handles late-arriving data -- scrape results that arrive after the initial processing window. Without it, we'd miss data points. Full refresh is used for daily models like `mart_leaderboard` where we need the complete dataset recalculated. The 4-hour window was tuned empirically -- our scrape pipeline typically delivers results within 2 hours, so 4 hours gives us 2x safety margin while keeping processing fast."

### Follow-up: "What if data arrives more than 4 hours late?"
> "It gets picked up by the daily full refresh, which runs at 19:00 UTC. So worst case, a late-arriving data point is delayed by one day in our time-series models. For our analytics use case, that's acceptable."

---

## Decision 7: Why Frequency-Based Scheduling (*/5, */15, daily)?

### What's In The Code
```python
# 7 different scheduling tiers
"*/5 * * * *"       # Recent scrape logs
"*/15 * * * *"      # Core metrics
"*/30 * * * *"      # Collections
"0 1-23/2 * * *"    # Hourly transforms
"0 */5 * * *"       # Post ranking
"0 19 * * *"        # Daily batch
"0 6 */7 * *"       # Weekly aggregates
```

### Interview Answer
> "We designed scheduling tiers based on business data freshness requirements. Scrape monitoring runs every 5 minutes because we need near-real-time visibility into scraping health. Core metrics like follower counts run every 15 minutes because the SaaS app refreshes profile pages in real-time. Collections run every 30 minutes because campaign managers check them multiple times per hour. Leaderboards are daily because rankings only change meaningfully over 24-hour periods. Weekly aggregates like growth rates need a full week of data. Each tier was tuned to balance freshness against ClickHouse compute cost."

### Follow-up: "How do you prevent scheduling conflicts?"
> "Two mechanisms. First, `max_active_runs=1` on every DAG prevents parallel executions of the same DAG. Second, the `ShortCircuitOperator` skips hourly and collection DAGs during the 19:00-22:00 daily batch window. The daily batch is the heaviest -- it takes up to 6 hours with a `dagrun_timeout` of 360 minutes. If collections ran concurrently, they'd compete for ClickHouse resources."

---

## Decision 8: Why SSH Transfer vs Direct S3-to-PostgreSQL?

### What's In The Code
```python
# SSH to download S3 file to PostgreSQL host's local filesystem
download_cmd = "aws s3 cp s3://gcc-social-data/.../file.json /tmp/file.json"
import_to_pg_box = SSHOperator(
    ssh_conn_id='ssh_prod_pg',
    cmd_timeout=1000,
    task_id='download_to_pg_local',
    command=download_cmd,
)
# Then COPY from local file
PostgresOperator(sql="COPY table from '/tmp/file.json'")
```

### The Options

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **SSH + aws s3 cp + local COPY** | COPY from local file is fastest, simple | Requires SSH access, disk space on PG host | **YES** |
| **aws_s3 extension (COPY FROM S3)** | No SSH needed | Requires PostgreSQL extension, not always available | No |
| **Stream S3 through Airflow worker** | No SSH needed | Airflow worker becomes bottleneck, memory issues | No |
| **Lambda trigger** | Serverless | Additional infrastructure, harder to debug | No |

### Interview Answer
> "PostgreSQL's `COPY FROM` is fastest when reading from a local file -- it bypasses network overhead entirely. The SSH operator downloads the S3 file to `/tmp/` on the PostgreSQL host, then `COPY` reads it locally. The alternative `aws_s3` extension exists but wasn't installed on our PostgreSQL instance, and adding extensions to a production database requires DBA approval and downtime. Streaming through the Airflow worker would make the worker a bottleneck -- some of our JSON exports are gigabytes. The SSH approach is simple, fast, and reliable."

### Follow-up: "What about disk space on the PostgreSQL host?"
> "The files are written to `/tmp/` and PostgreSQL's COPY reads them immediately. We could add a cleanup step, but in practice the daily cron on the host clears `/tmp/`. The largest file (leaderboard) is about 2GB JSON, well within the host's storage."

---

## Decision 9: Why ClickHouse for OLAP vs BigQuery/Snowflake?

### What's In The Code
```yaml
# .dbt/profiles.yml
gcc_warehouse:
  target: prod
  outputs:
    prod:
      type: clickhouse
      host: 172.31.28.68
      port: 9000
      database: dbt
      threads: 3
```

### The Options

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **ClickHouse (self-hosted)** | Extremely fast OLAP, free, native S3 integration, real-time inserts | Self-managed, single-node risk | **YES** |
| **BigQuery** | Serverless, no ops | Pay-per-query expensive at our scale, no real-time insert | No |
| **Snowflake** | Scalable, multi-cloud | Expensive for always-on analytics, cold start | No |
| **PostgreSQL only** | Single database, simpler | OLAP queries too slow on PostgreSQL at our data volume | No |

### Interview Answer
> "ClickHouse was ideal for three reasons. First, we need real-time inserts -- scrape data arrives continuously and needs to be queryable immediately, not after a batch load. Second, our ranking queries scan millions of rows with GROUP BY and ORDER BY -- ClickHouse's columnar storage handles this in seconds where PostgreSQL would take minutes. Third, ClickHouse's native S3 integration (`INSERT INTO FUNCTION s3(...)`) eliminates the need for an external export tool. BigQuery's pay-per-query model would be expensive given we run queries every 5-15 minutes. Snowflake's cold start time doesn't work for sub-minute analytics. We kept PostgreSQL for serving the SaaS app because it handles transactional reads (single profile lookup) better than ClickHouse."

### Follow-up: "What about ClickHouse availability since it's self-hosted?"
> "That's a valid concern. We run on a single node which is a single point of failure. For our startup context, the cost savings of self-hosted ClickHouse over Snowflake justified the risk. If I were designing this at a larger company, I'd use ClickHouse Cloud or a multi-node cluster."

---

## Decision 10: Why JSONEachRow Format for S3 Staging?

### What's In The Code
```sql
INSERT INTO FUNCTION s3(
    's3://gcc-social-data/.../file.json',
    'KEY', 'SECRET',
    'JSONEachRow'    -- One JSON object per line
)
SELECT * FROM dbt.mart_leaderboard
SETTINGS s3_truncate_on_insert=1;
```

### The Options

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **JSONEachRow** | PostgreSQL COPY compatible, human-readable, schema-flexible | Larger file size vs binary | **YES** |
| **CSV** | Smallest text format | Escaping issues with commas in text fields, no nested types | No |
| **Parquet** | Compressed, columnar | PostgreSQL can't COPY from Parquet, needs extra tool | No |
| **Avro** | Compressed, schema-enforced | PostgreSQL can't COPY from Avro, needs extra tool | No |

### Interview Answer
> "JSONEachRow is ClickHouse's native one-JSON-per-line format, and it's directly compatible with PostgreSQL's `COPY` command. PostgreSQL can `COPY` a file where each line is a JSON object into a `JSONB` column. We then parse fields with `data->>'field_name'` and cast types. CSV was rejected because our data contains commas, quotes, and special characters in fields like biography and post titles -- escaping would be fragile. Parquet would be smaller but PostgreSQL has no native Parquet reader. The file size trade-off is acceptable because the files are temporary staging -- they're overwritten on every run with `s3_truncate_on_insert=1`."

### Follow-up: "Why not compress the JSON?"
> "ClickHouse's S3 function supports compression (gzip), but PostgreSQL's COPY command can't read gzipped files directly from disk. We'd need to add a decompression step via SSH. For our file sizes (1-2GB), the transfer time over S3 within the same AWS region is fast enough without compression."
