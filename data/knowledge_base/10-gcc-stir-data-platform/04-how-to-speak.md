# How To Speak About Stir Data Platform In Interview

> **Ye file sikhata hai Stir data platform ke baare mein KAISE bolna hai - word by word.**
> Interview se pehle ye OUT LOUD practice karo.

---

## YOUR 90-SECOND PITCH (Ye Yaad Karo)

Jab interviewer bole "Tell me about a data pipeline you built" ya "Tell me about your ETL experience":

> "At Good Creator Co., I built Stir -- the data transformation and orchestration platform behind an influencer marketing SaaS product. The core challenge was that brands like Coca-Cola need real-time influencer analytics -- rankings, engagement rates, growth trends -- but our raw data lived in ClickHouse, while the web app read from PostgreSQL.
>
> I designed a three-layer pipeline: dbt models in ClickHouse compute 112 analytics transformations -- from raw scrape data to business-ready metrics like multi-dimensional leaderboard rankings. ClickHouse then exports to S3 as JSON staging. Airflow orchestrates the SSH download and PostgreSQL load with an atomic table swap pattern -- zero-downtime updates.
>
> I built 76 Airflow DAGs across 7 scheduling tiers -- every 5 minutes for real-time monitoring, every 15 minutes for core metrics, daily for leaderboards. This cut data latency by 50% compared to the previous monolithic batch approach. The platform handles 17,500 lines of code with 1,476 commits."

**Practice this until it flows naturally. Time yourself -- should be ~90 seconds.**

---

## PYRAMID METHOD - Architecture Question

**Q: "Walk me through the architecture"**

### Level 1 - Headline (Isse shuru karo HAMESHA):
> "It's a three-layer ELT pipeline with 76 Airflow DAGs orchestrating 112 dbt models, flowing data from ClickHouse through S3 staging to PostgreSQL with atomic table swaps."

### Level 2 - Structure (Agar unhone aur jaanna chaha):
> "Layer 1 is ClickHouse -- our OLAP engine. dbt runs 29 staging models that extract from raw databases, and 83 mart models that compute business metrics: engagement rates, multi-dimensional rankings, growth trends, collection analytics. All SQL-based with Jinja templating.
>
> Layer 2 is S3 staging. ClickHouse has native S3 integration -- `INSERT INTO FUNCTION s3()` exports JSON directly. This decouples the ClickHouse compute from the PostgreSQL load, giving us retry-ability.
>
> Layer 3 is PostgreSQL. An SSH operator downloads the JSON to the PostgreSQL host, then a COPY command loads it into a temporary JSONB table. We parse and type-cast each field, enrich with JOINs against operational tables, then do an atomic table swap -- RENAME in a transaction -- so the SaaS app always reads consistent data."

### Level 3 - Go deep on ONE part (Jo sabse interesting lage):
> "The most interesting design is the scheduling architecture. I built 7 scheduling tiers matched to business freshness requirements. Scrape monitoring runs every 5 minutes. Core influencer metrics run every 15 minutes because the SaaS app shows near-real-time data. Collection analytics run every 30 minutes for campaign managers. But leaderboard rankings only need daily computation because they're based on monthly aggregates. The key production-hardening is a `ShortCircuitOperator` that pauses fast-frequency DAGs during the daily batch window to prevent ClickHouse resource contention."

### Level 4 - OFFER (Ye zaroor bolo):
> "I can go deeper into the ClickHouse-specific optimizations like argMax and ReplacingMergeTree, the dbt Jinja templating that generates performance grades across 19 metrics, or the atomic table swap pattern -- which interests you?"

**YE LINE INTERVIEW KA GAME CHANGER HAI -- TU DECIDE KAR RAHA HAI CONVERSATION KAHAN JAAYE.**

---

## KEY DECISION STORIES - "Why did you choose X?"

### Story 1: "Why ClickHouse instead of BigQuery or Snowflake?"

> "Three reasons drove the ClickHouse decision.
>
> First, real-time inserts. Our scraper produces data continuously -- Instagram profiles, posts, comments -- and we need it queryable immediately. BigQuery and Snowflake are designed for batch loading, not continuous inserts. ClickHouse accepts inserts in real-time with zero lag.
>
> Second, query speed. Our leaderboard model scans millions of profiles, ranks them across 28 dimensions, and needs to complete within minutes. ClickHouse's columnar storage and vectorized execution handle this. Our `SETTINGS max_bytes_before_external_group_by = 20GB` lets it spill to disk for the largest queries.
>
> Third, cost. We're a startup. ClickHouse is open-source, self-hosted on a single EC2 instance. BigQuery's per-query pricing with queries running every 5-15 minutes would be expensive. Snowflake's always-on compute would cost more than our entire infrastructure budget."

### Story 2: "Why the three-layer pipeline instead of direct sync?"

> "The key constraint was that ClickHouse has no native PostgreSQL writer. We needed a bridge.
>
> S3 serves as a checkpoint. If PostgreSQL is under load and the COPY fails, we don't re-query ClickHouse -- the JSON is already in S3. We just re-download and retry. ClickHouse's native `INSERT INTO FUNCTION s3()` is extremely efficient -- it streams query results directly to S3 without buffering the entire result in memory.
>
> On the PostgreSQL side, `COPY FROM` a local file is the fastest bulk loading mechanism -- faster than INSERT or even the `aws_s3` extension -- because it reads sequentially from disk without network overhead.
>
> The alternative would have been Kafka CDC for real-time streaming, but our analytics are batch by nature. A 15-minute batch refresh is sufficient for influencer rankings."

### Story 3: "Why atomic table swap instead of UPSERT?"

> "When you UPSERT millions of rows in PostgreSQL, each row acquires a row-level lock. Our SaaS app reads these tables for every API request -- profile lookups, leaderboard queries. With UPSERT, a user might see inconsistent data: some profiles updated, others still old.
>
> The atomic RENAME inside a transaction is instant. One moment the app reads the old table, the next moment it reads the new table. No inconsistency, no locking, no performance impact on reads.
>
> We also create the temp table as UNLOGGED for 2-3x faster inserts, then switch to LOGGED before the swap. And we keep the old table as `_old_bkp` for emergency rollback."

### Story 4: "Why dbt instead of custom Python scripts?"

> "With 112 transformations and complex dependencies between them, we needed automatic dependency management. dbt's `ref()` function builds a DAG of model dependencies. When I write `ref('stg_beat_instagram_account')`, dbt ensures the staging model runs before the mart model.
>
> The second benefit is Jinja templating. Our mart_instagram_account model grades 19 metrics into 5 percentile buckets. That's 38 generated columns from a 10-line Jinja loop. In Python, I'd be maintaining 200 lines of repetitive SQL strings.
>
> The tag system maps models to scheduling tiers: `tag:core` runs every 15 minutes, `tag:daily` runs once. Each Airflow DAG selects models by tag, so adding a new metric is as simple as creating a SQL file with the right tag."

---

## THE DATA LATENCY STORY

**This is your MOST RELEVANT story for the resume bullet. Use it when they ask:**
- "Tell me about improving a data pipeline"
- "Tell me about reducing latency"
- "Tell me about a technical optimization"

### How To Tell It:

> "When I joined GCC, the data platform was a set of monolithic Python scripts that ran as daily batch jobs. An influencer's follower count would take up to 24 hours to appear in the SaaS app. Campaign managers were making decisions on stale data.
>
> I rebuilt the entire pipeline using Airflow and dbt. The key insight was that not all data needs the same freshness. I categorized our 112 transformations into 7 scheduling tiers:
>
> - Scrape monitoring: every 5 minutes -- we need to know immediately if scraping is failing
> - Core metrics (followers, engagement): every 15 minutes -- this is what users see on profile pages
> - Collection analytics: every 30 minutes -- campaign managers check these multiple times per hour
> - Profile rankings: every 2 hours -- rankings don't change faster than this
> - Post ranking: every 5 hours -- heavy computation, acceptable delay
> - Leaderboards: daily -- based on monthly data, inherently slow-changing
> - Growth aggregates: weekly -- needs a full week of data
>
> The production-hardening was critical. I added `ShortCircuitOperator` to pause fast DAGs during the daily batch window. `max_active_runs=1` prevents cascading failures. Slack notifications fire on every failure.
>
> Result: core metrics went from 24-hour latency to 15-minute latency. Overall average latency dropped by 50%. Campaign managers started making real-time decisions based on fresh data."

### After Telling This Story, ALWAYS Add:

> "The key learning was that scheduling is a product decision, not just an engineering decision. Matching data freshness to business requirements is more impactful than making everything real-time."

---

## NUMBERS YOU MUST KNOW (Interviewer Puchega)

| When They Ask | You Say |
|---------------|---------|
| "How many DAGs?" | "76 Airflow DAGs across 7 scheduling tiers" |
| "How many models?" | "112 dbt models -- 29 staging, 83 marts -- organized by domain" |
| "How big is the codebase?" | "17,500+ lines of code, 1,476 git commits, 350+ Python dependencies" |
| "What scheduling range?" | "Every 5 minutes for real-time monitoring to weekly for growth aggregates" |
| "What's the latency improvement?" | "50% reduction overall, core metrics from 24 hours to 15 minutes" |
| "How many data sources?" | "7 sources: Instagram API, YouTube API, Beat, Coffee, Shopify, Vidooly, S3" |
| "What databases?" | "ClickHouse for OLAP analytics, PostgreSQL for serving the SaaS app" |
| "How many operator types?" | "5: PythonOperator (46), PostgresOperator (20), ClickHouseOperator (19), SSHOperator (18), DbtRunOperator (11)" |

---

## PIVOT PHRASES - Redirect to Your Strengths

### If they ask about real-time streaming (Kafka, Flink):
> "Our architecture is batch-oriented because influencer analytics don't need sub-second freshness. Our fastest pipeline runs every 5 minutes, which satisfies our SLA. If I needed true real-time, I'd replace the S3 staging layer with Kafka -- ClickHouse has a native Kafka engine -- but for our use case, 5-minute batches give us simpler operations with acceptable freshness."

### If they ask about data quality/testing:
> "We enforce data quality at multiple layers. dbt's `ref()` ensures execution order. ClickHouse's `COALESCE` and type casting handle NULLs. PostgreSQL's JSONB parsing fails the entire COPY if any row has invalid types, and the atomic swap ensures the old table stays live. If I were to improve this, I'd add dbt's built-in tests -- `unique`, `not_null`, `accepted_values` -- and a data lineage tool."

### If they ask about CI/CD:
> "We use GitLab CI with a manual deployment step. The pipeline runs `scripts/start.sh` which initializes Airflow and starts the scheduler. Production deploys are gated behind manual approval. If I were redesigning, I'd add staging environment testing with dbt's `--defer` flag to test changes against production data."

### If they ask about cost:
> "Self-hosted ClickHouse on EC2 keeps OLAP costs near zero. S3 staging costs are negligible -- files are temporary and overwritten each run. PostgreSQL is also self-hosted. The entire data platform infrastructure costs less than what a single BigQuery or Snowflake seat would cost per month."
