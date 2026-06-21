# Stir Data Platform -- Complete Interview Master Guide

> **Resume Bullet:** "Cut data latency by 50% by streamlining ETL pipelines using Apache Airflow and DBT for batch ingestion"
> **Company:** Good Creator Co. (GCC) -- SaaS platform for influencer marketing analytics
> **Repo:** `stir` | **17,500+ lines** | **1,476 commits**

---

## Pitches

### 30-Second Pitch

> "At Good Creator Co., I built Stir -- the data transformation and orchestration platform powering influencer marketing analytics. The core challenge was syncing analytics from ClickHouse (our OLAP engine) to PostgreSQL (serving the SaaS app) with minimal latency. I designed 76 Airflow DAGs orchestrating 112 dbt models through a three-layer pipeline: ClickHouse transforms data, exports to S3 as JSON staging, then atomic table swaps load it into PostgreSQL. Scheduling ranges from every 5 minutes for real-time scrape monitoring to weekly for aggregate leaderboards. This cut data latency by 50% and powers the discovery, leaderboard, and collection analytics for the platform."

### 90-Second Pitch

> "At Good Creator Co., I built Stir -- the data transformation and orchestration platform behind an influencer marketing SaaS product. The core challenge was that brands like Coca-Cola need real-time influencer analytics -- rankings, engagement rates, growth trends -- but our raw data lived in ClickHouse, while the web app read from PostgreSQL.
>
> I designed a three-layer pipeline: dbt models in ClickHouse compute 112 analytics transformations -- from raw scrape data to business-ready metrics like multi-dimensional leaderboard rankings. ClickHouse then exports to S3 as JSON staging. Airflow orchestrates the SSH download and PostgreSQL load with an atomic table swap pattern -- zero-downtime updates.
>
> I built 76 Airflow DAGs across 7 scheduling tiers -- every 5 minutes for real-time monitoring, every 15 minutes for core metrics, daily for leaderboards. This cut data latency by 50% compared to the previous monolithic batch approach. The platform handles 17,500 lines of code with 1,476 commits."

---

## Key Numbers

| Metric | Value |
|--------|-------|
| Total lines of code | **17,500+** |
| Airflow DAGs | **76** |
| dbt models | **112** (29 staging + 83 marts) |
| Git commits | **1,476** |
| Python dependencies | **350+** |
| Scheduling range | ***/5 min to weekly** |
| Data latency reduction | **50%** |
| Operator types used | **5** (Python, Postgres, ClickHouse, SSH, dbt) |
| dbt tags (scheduling tiers) | **10** |
| Data sources integrated | **7** (Instagram, YouTube, Beat, Coffee, Shopify, Vidooly, S3) |

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

## Architecture

```
                         STIR DATA PLATFORM ARCHITECTURE

  DATA SOURCES                    ORCHESTRATION              SERVING LAYER
  ============                    =============              =============

  Instagram API  --+
  YouTube API    --+              +------------------------------------------+
  Beat (Scraper) --+              |         APACHE AIRFLOW (76 DAGs)        |
  Coffee (SaaS)  --+---------->   |                                          |
  Shopify        --+              |  +-------------------------------------+ |
  Vidooly        --+              |  |    dbt ORCHESTRATION (11 DAGs)      | |
                                  |  |                                     | |
                                  |  |  dbt_core      */15 min  tag:core   | |
                                  |  |  dbt_recent_scl */5 min  tag:recent | |
                                  |  |  dbt_hourly     every 2h tag:hourly | |
                                  |  |  dbt_daily      19:00    tag:daily  | |
                                  |  |  dbt_weekly     weekly   tag:weekly | |
                                  |  |  dbt_collections */30    tag:coll   | |
                                  |  |  post_ranker    */5 hr   tag:ranker | |
                                  |  +-------------------------------------+ |
                                  +------------------------------------------+
                                               |
                 +-----------------------------+-----------------------------+
                 |                             |                             |
                 v                             v                             v
  +----------------------+   +----------------------+   +----------------------+
  |   LAYER 1: CLICKHOUSE|   |   LAYER 2: AWS S3    |   | LAYER 3: POSTGRESQL  |
  |   (Analytics/OLAP)   |-->|   (JSON Staging)     |-->|   (Operational/OLTP) |
  |                      |   |                      |   |                      |
  |  29 staging models   |   |  gcc-social-data     |   |  beat database       |
  |  83 mart models      |   |  /data-pipeline/tmp/ |   |  Atomic table swap   |
  |  ReplacingMergeTree  |   |  JSONEachRow format  |   |  JSONB parsing       |
  |  argMax, partitions  |   |  s3_truncate=1       |   |  COPY + RENAME       |
  +----------------------+   +----------------------+   +----------------------+
                                                                 |
                                                                 v
                                                    +----------------------+
                                                    |   GCC SaaS Platform  |
                                                    |   (Coffee API)       |
                                                    |                      |
                                                    |  Discovery           |
                                                    |  Leaderboards        |
                                                    |  Collections         |
                                                    |  Campaign Analytics  |
                                                    +----------------------+
```

### Technology Stack

| Category | Technology | Purpose |
|----------|-----------|---------|
| Orchestration | Apache Airflow 2.6.3 | Workflow scheduling and monitoring |
| Transformation | dbt-core 1.3.1 | SQL-based ELT transformations |
| Analytics DB | ClickHouse (dbt-clickhouse 1.3.2) | OLAP engine, real-time analytics |
| Operational DB | PostgreSQL (psycopg2 2.9.5) | SaaS application serving |
| Cloud Storage | AWS S3 (gcc-social-data) | JSON staging between databases |
| CI/CD | GitLab CI | Manual production deploys |
| Monitoring | Slack (slack-sdk 3.21.3) | Failure/success notifications |
| SSH Transfer | Paramiko | File download to PostgreSQL host |

### DAG Categories (76 Total)

| Category | Count | Examples |
|----------|-------|---------|
| dbt Orchestration | 11 | dbt_core, dbt_daily, dbt_collections |
| Instagram Sync | 17 | sync_insta_collection_posts, sync_insta_profile_insights |
| YouTube Sync | 12 | sync_yt_channels, sync_yt_critical_daily |
| Collection/Leaderboard Sync | 15 | sync_leaderboard_prod, sync_time_series_prod |
| Operational/Verification | 9 | sync_missing_journey, sync_group_metrics_prod |
| Asset Upload | 7 | upload_post_asset, upload_content_verification |
| Utility | 5 | crm_recommendation_invitation, track_hashtags |

### dbt Model Architecture (112 Total)

| Layer | Count | Domains |
|-------|-------|---------|
| **Staging** | 29 | beat (14 models), coffee (15 models) |
| **Marts** | 83 | discovery (16), leaderboard (14), collection (12), profile_stats (8), profile_stats_partial (6), genre (7), audience (4), posts (3), staging_collection (9), orders (1), data_request (3) |

---

## Technical Implementation

### Scheduling Tiers -- From Real DAG Files

**Tier 1: Every 5 minutes -- Real-time monitoring**
```python
# dags/dbt_recent_scl.py
with DAG(
        dag_id="dbt_recent_scl",
        schedule_interval="*/5 * * * *",
        start_date=days_ago(1),
        catchup=False,
        max_active_runs=1,
        concurrency=1,
        on_failure_callback = SlackNotifier.slack_fail_alert,
        on_success_callback = SlackNotifier.slack_fail_alert,
        dagrun_timeout=dt.timedelta(minutes=90),
) as dag:
    dbt_run = DbtRunOperator(
        task_id="dbt_run_hourly",
        project_dir="/gcc/airflow/stir/gcc_social/",
        profiles_dir="/gcc/airflow/.dbt/",
        select=["tag:recent_scl"],
        exclude=["tag:deprecated", "tag:post_ranker", "tag:core"],
        target="production",
        profile="gcc_warehouse",
    )
```

**Tier 2: Every 10 minutes -- Near real-time scrape requests**
```python
# dags/sync_insta_collection_posts.py
with DAG(
        dag_id='sync_insta_collection_posts',
        start_date=days_ago(1),
        catchup=False,
        max_active_runs=1,
        concurrency=1,
        on_failure_callback = SlackNotifier.slack_fail_alert,
        on_success_callback = SlackNotifier.slack_fail_alert,
        schedule_interval="*/10 * * * *",
) as dag:
    task = PythonOperator(
        task_id='create_insta_post_scl',
        python_callable=create_scrape_request_log
    )
```

**Tier 3: Every 15 minutes -- Core business metrics**
```python
# dags/dbt_core.py
with DAG(
        dag_id="dbt_core",
        schedule_interval="*/15 * * * *",
        start_date=days_ago(1),
        catchup=False,
        max_active_runs=1,
        concurrency=1,
        on_failure_callback = SlackNotifier.slack_fail_alert,
        on_success_callback = SlackNotifier.slack_fail_alert,
        dagrun_timeout=dt.timedelta(minutes=60),
) as dag:
    dbt_run = DbtRunOperator(
        task_id="dbt_run_core",
        project_dir="/gcc/airflow/stir/gcc_social/",
        profiles_dir="/gcc/airflow/.dbt/",
        select=["tag:core"],
        exclude=["tag:deprecated", "tag:post_ranker"],
        target="production",
        profile="gcc_warehouse",
    )
```

**Tier 4: Every 30 minutes -- Collections**
```python
# dags/dbt_collections.py
with DAG(
        dag_id="dbt_collections",
        schedule_interval="*/30 * * * *",
        start_date=days_ago(1),
        catchup=False,
        max_active_runs=1,
        concurrency=1,
        on_failure_callback = SlackNotifier.slack_fail_alert,
        on_success_callback = SlackNotifier.slack_fail_alert,
        dagrun_timeout=dt.timedelta(minutes=180),
) as dag:
    check_hour_task = ShortCircuitOperator(
        task_id="check_hour",
        python_callable=check_hour,   # Returns False if 19 <= hour < 22
    )
```

**Tier 5: Every 2 hours -- Hourly models (with conflict avoidance)**
```python
# dags/dbt_hourly.py
def check_hour():
    hour = dt.datetime.now().hour
    if 19 <= hour < 22:
        return False
    return True

with DAG(
        dag_id="dbt_hourly",
        schedule_interval="0 1-23/2 * * *",
        start_date=days_ago(1),
        catchup=False,
        max_active_runs=1,
        concurrency=1,
        dagrun_timeout=dt.timedelta(minutes=180),
) as dag:
    check_hour_task = ShortCircuitOperator(
        task_id="check_hour",
        python_callable=check_hour,
    )
    dbt_run = DbtRunOperator(
        task_id="dbt_run_hourly",
        select=["tag:hourly"],
        exclude=["tag:deprecated", "tag:post_ranker", "tag:core"],
        target="production",
        profile="gcc_warehouse",
    )
    check_hour_task >> dbt_run
```

**Tier 6: Every 5 hours -- Post ranking (heavy computation)**
```python
# dags/post_ranker.py
with DAG(
        dag_id="post_ranker",
        schedule_interval="0 */5 * * *",
        start_date=days_ago(1),
        catchup=False,
        max_active_runs=1,
        concurrency=1,
        dagrun_timeout=dt.timedelta(minutes=300),
) as dag:
    dbt_run = DbtRunOperator(
        task_id="post_ranker_dbt",
        select=["tag:post_ranker"],
        exclude=["tag:deprecated", "tag:core"],
        target="production",
        profile="gcc_warehouse",
    )
```

**Tier 7: Daily -- Batch processing**
```python
# dags/dbt_daily.py
with DAG(
        dag_id="dbt_daily",
        schedule_interval="0 19 * * *",
        start_date=days_ago(1),
        catchup=False,
        max_active_runs=1,
        concurrency=1,
        dagrun_timeout=dt.timedelta(minutes=360),
) as dag:
    dbt_run = DbtRunOperator(
        task_id="dbt_run_daily",
        select=["tag:daily"],
        exclude=["tag:deprecated", "tag:post_ranker", "tag:core"],
        target="production",
        profile="gcc_warehouse",
    )
```

**Tier 8: Weekly -- Aggregate leaderboards**
```python
# dags/dbt_weekly.py
with DAG(
        dag_id="dbt_weekly",
        schedule_interval="0 6 */7 * *",
        start_date=days_ago(7),
        catchup=False,
        max_active_runs=1,
        concurrency=1,
        dagrun_timeout=dt.timedelta(minutes=360),
) as dag:
    dbt_run = DbtRunOperator(
        task_id="dbt_run_weekly",
        select=["tag:weekly"],
        exclude=["tag:deprecated", "tag:post_ranker", "tag:core"],
        target="production",
        profile="gcc_warehouse",
    )
```

### Complete Scheduling Frequency Table

| Frequency | Cron Expression | DAGs | Timeout | Purpose |
|-----------|----------------|------|---------|---------|
| */5 min | `*/5 * * * *` | dbt_recent_scl | 90 min | Real-time scrape log processing |
| */10 min | `*/10 * * * *` | sync_insta_collection_posts + 4 others | varies | Near real-time data refresh |
| */15 min | `*/15 * * * *` | dbt_core, post_ranker_partial | 60-90 min | Core metrics, partial rankings |
| */30 min | `*/30 * * * *` | dbt_collections, dbt_staging_collections | 180 min | Collection analytics |
| Hourly | `0 * * * *` | refresh_account_tracker_stats + 11 others | 40 min | Account stats, sync operations |
| Every 2h | `0 1-23/2 * * *` | dbt_hourly | 180 min | Hourly transforms (skip 19-22h) |
| Every 3h | `0 */3 * * *` | 8 sync DAGs | varies | Heavy sync operations |
| Every 5h | `0 */5 * * *` | post_ranker | 300 min | Full post ranking |
| Daily midnight | `0 0 * * *` | dbt_gcc_orders + 14 others | 90 min | Full refreshes |
| Daily 19:00 | `0 19 * * *` | dbt_daily | 360 min | Daily batch (leaderboards, time series) |
| Daily 20:15 | `15 20 * * *` | sync_leaderboard_prod/staging | varies | Leaderboard sync to PostgreSQL |
| Daily 03:03 | `3 3 * * *` | sync_time_series_prod | varies | Time series sync to PostgreSQL |
| Weekly | `0 6 */7 * *` | dbt_weekly | 360 min | Weekly aggregates |

### dbt Models -- Key Implementations

#### mart_instagram_account (Core Discovery Model -- 559 lines)

The most complex model, joining 12+ CTEs to produce the master influencer profile:

```sql
-- models/marts/discovery/mart_instagram_account.sql
{{ config(materialized = 'table', tags=["hourly"], order_by='ig_id') }}
{%
    set metrics = [
        "avg_likes", "avg_comments", "comments_rate", "followers",
        "engagement_rate", "reels_reach", "image_reach", "story_reach",
        "reels_impressions", "image_impressions", "likes_to_comment_ratio",
        "followers_growth7d", "followers_growth30d", "followers_growth90d",
        "audience_reachability", "audience_authencity", "post_count",
        "likes_spread", "avg_posts_per_week"
    ]
%}

-- CTE 1: Linked socials (Instagram <-> YouTube)
with links as (
    select handle, max(channel_id) channel_id, max(category) category
    from dbt.mart_linked_socials
    group by handle
),

-- CTE 2: Overtime growth using argMaxIf for time-windowed metrics
overtime_growth as (
    select
        platform_id profile_id,
        argMax(followers, date) cur_followers,
        argMaxIf(followers, date, date < toStartOfWeek(now()) - INTERVAL 7 DAY) followers_7d,
        argMaxIf(followers, date, date < toStartOfWeek(now()) - INTERVAL 30 DAY) followers_30d,
        argMaxIf(followers, date, date < toStartOfWeek(now()) - INTERVAL 90 DAY) followers_90d,
        argMaxIf(followers, date, date < toStartOfWeek(now()) - INTERVAL 1 YEAR) followers_1y,
        cur_followers - followers_7d followers_growth_7d,
        cur_followers - followers_30d followers_growth_30d,
        cur_followers - followers_90d followers_growth_90d,
        cur_followers - followers_1y followers_growth_1y
    from dbt.mart_insta_account_weekly
    group by profile_id
),

-- CTE 3: Follower grouping for performance grading
semi_final as (
    select
        multiIf(
            followers < 5000, '0-5k',
            followers < 10000, '5k-10k',
            followers < 50000, '10k-50k',
            followers < 100000, '50k-100k',
            followers < 500000, '100k-500k',
            followers < 1000000, '500k-1M',
            '1M+'
        ) follower_group,
        rank() over (partition by country order by followers desc) country_rank,
        rank() over (partition by country, category order by followers desc) category_rank,
    from {{ref('mart_instagram_account_summary')}} stats
    left join {{ref('stg_beat_instagram_account')}} ia on ia.profile_id = stats.profile_id
    left join {{ref('mart_audience_info')}} aud on aud.platform_id = ia.profile_id
),

-- CTE 4: Dedup using argMax (ClickHouse pattern for latest value per group)
final_without_group_metrics as (
    select
        handle,
        max(updated_at) _updated_at,
        argMax(name, updated_at) name,
        argMax(ig_id, updated_at) ig_id,
        argMax(followers, updated_at) followers,
        argMax(engagement_rate, updated_at) engagement_rate,
        argMax(country, updated_at) country,
        argMax(category_rank, updated_at) category_rank,
    from final_without_group_metrics_with_dups
    group by handle
),

-- CTE 5: Performance grading using Jinja loop + percentile buckets
final as (
    select
        *,
        {% for metric in metrics %}
            multiIf(
                {{metric}} is null or {{metric}} == 0
                    or isInfinite({{metric}}) or isNaN({{metric}}), NULL,
                {{metric}} > gm.p90_{{metric}}, 'Excellent',
                {{metric}} > gm.p75_{{metric}}, 'Very Good',
                {{metric}} > gm.p60_{{metric}}, 'Good',
                {{metric}} > gm.p40_{{metric}}, 'Average',
                'Poor'
            ) {{metric}}_grade,
            gm.group_avg_{{metric}} group_avg_{{metric}},
        {% endfor %}
        group_key
    from final_without_group_metrics
    left join dbt.mart_primary_group_metrics gm
        on gm.group_key = final_without_group_metrics.group_key
)
select * from final
order by followers desc
```

**Key patterns:** argMax for deduplication, argMaxIf for time-windowed growth, Jinja templating for grading, multiIf for follower segmentation, 12+ LEFT JOINs combining data from Beat, Coffee, Vidooly, predictions.

#### mart_leaderboard (Multi-Dimensional Rankings)

```sql
-- models/marts/leaderboard/mart_leaderboard.sql
{{ config(materialized = 'table', tags=["daily", "leaderboard"],
          order_by='month, platform, platform_id') }}

select
    month,
    'IA' profile_platform,
    language, category,
    ifNull(platform, 'MISSING') platform,
    platform_id,
    followers, engagement_rate, avg_likes, avg_comments, avg_views, avg_plays,
    followers_rank, followers_change_rank, views_rank,
    followers_rank_by_cat, views_rank_by_cat,
    followers_rank_by_lang, views_rank_by_lang,
    followers_rank_by_cat_lang, views_rank_by_cat_lang,
    -- Previous month ranks stored as ClickHouse Map type
    CAST(map(
        'followers_rank', ifNull(followers_rank_prev, 0),
        'views_rank', ifNull(views_rank_prev, 0),
        'followers_change_rank', ifNull(followers_change_rank_prev, 0),
        'plays_rank', ifNull(plays_rank_prev, 0),
    ), 'Map(String, UInt64)') last_month_ranks,
    CAST(map(
        'followers_rank', ifNull(followers_rank, 0),
        'views_rank', ifNull(views_rank, 0),
    ), 'Map(String, UInt64)') current_month_ranks
from {{ref('mart_instagram_leaderboard')}}

UNION ALL
select ... from {{ref('mart_youtube_leaderboard')}}
UNION ALL
select ... from {{ref('mart_cross_platform_leaderboard')}}

SETTINGS max_bytes_before_external_group_by = 20000000000,
         max_bytes_before_external_sort = 20000000000,
         join_algorithm='partial_merge'
```

**Key patterns:** ClickHouse Map type stores 28 rank dimensions per profile as a single column. UNION ALL for multi-platform. Memory settings allow spilling to disk for large aggregations. partial_merge join for memory-efficient large joins.

#### mart_insta_account_weekly (Window Functions for Growth)

```sql
-- models/marts/leaderboard/mart_insta_account_weekly.sql
followers_by_week as (
    select
        week, profile_id,
        max(followers) followers,
        max(following) following,
        groupArray(week) OVER (
            PARTITION BY profile_id ORDER BY week ASC
            ROWS BETWEEN 1 PRECEDING AND 0 FOLLOWING
        ) AS week_values,
        week_values[1] p_week,
        abs(p_week - week) <= 7 last_week_available,
        groupArray(followers) OVER (
            PARTITION BY profile_id ORDER BY week ASC
            ROWS BETWEEN 1 PRECEDING AND 0 FOLLOWING
        ) AS followers_values,
        followers_values[1] followers_prev,
        if(last_week_available = 1, followers - followers_prev, NULL) followers_change
    from followers_by_week_all
    group by week, profile_id
)
```

**Key pattern:** Uses `groupArray() OVER (ROWS BETWEEN 1 PRECEDING)` to access previous week's value within a window, then calculates `followers_change` only if the previous week was consecutive (within 7 days).

#### mart_collection_post (Campaign Analytics -- 382 lines)

```sql
-- models/marts/collection/mart_collection_post.sql
{{ config(materialized = 'table', tags=["collections"],
          order_by='collection_id, post_short_code') }}

-- Story reach estimation formula
CASE
    WHEN item.created_at < '2023-11-22' THEN
        round((-0.000025017) * sd.profile_follower
              + (1.11 * (sd.profile_follower * abs(log2(sd.profile_er)) * 2 / 100)))
    ELSE
        round((-0.000025017) * sd.profile_follower
              + (1.11 * (sd.profile_follower * abs(log2((sd.profile_er + 2))) * 2 / 100)))
END AS _story_reach,

-- Latest values using argMax
story_data as (
    select shortcode,
           argMax(profile_follower, updated_at) profile_follower,
           argMax(profile_er, updated_at) profile_er
    from dbt.stg_beat_instagram_post
    where shortcode in items_shortcode
    group by shortcode
),

-- Hashtag normalization using arrayMap
arrayMap(x -> lower(x), hashtags) hashtags
```

#### mart_instagram_account_summary (Post Ranking)

```sql
-- models/marts/profile_stats/mart_instagram_account_summary.sql
{{ config(materialized = 'table', tags=["post_ranker"], order_by='profile_id') }}

recent_posts_by_class as (
    select
        profile_id, followers, following, post_shortcode, post_type,
        likes, comments, views, plays, engagement, impressions, reach,
        er, post_class, publish_time, post_rank, post_rank_by_class,
        rank() over (partition by profile_id, post_class
                     order by likes desc, comments desc, publish_time desc)
            likes_rank_by_class,
        rank() over (partition by profile_id, post_class
                     order by comments desc, likes desc, publish_time desc)
            comments_rank_by_class,
        rank() over (partition by profile_id, post_class
                     order by plays desc, likes desc, comments desc, publish_time desc)
            plays_rank_by_class,
        rank() over (partition by profile_id, post_class
                     order by views desc, likes desc, comments desc, publish_time desc)
            views_rank_by_class
    from {{ref('mart_instagram_recent_post_stats')}}
    where post_rank_by_class <= 12
)
```

### Three-Layer Data Flow: ClickHouse -> S3 -> PostgreSQL

#### Complete Pipeline: sync_leaderboard_prod

```python
# dags/sync_leaderboard_prod.py
with DAG(
        dag_id='sync_leaderboard_prod',
        start_date=days_ago(1),
        catchup=False,
        max_active_runs=1,
        concurrency=1,
        on_failure_callback = SlackNotifier.slack_fail_alert,
        on_success_callback = SlackNotifier.slack_fail_alert,
        schedule_interval="15 20 * * *",
) as dag:

    # STEP 1: Export from ClickHouse to S3 via INSERT INTO FUNCTION s3(...)
    fetch_leaderboard_from_ch = ClickHouseOperator(
        task_id='fetch_leaderboard_from_ch',
        database='vidooly',
        sql='''
            INSERT INTO FUNCTION s3(
                'https://gcc-social-data.s3.ap-south-1.amazonaws.com/
                    data-pipeline/tmp/leaderboard.json',
                'AWS_KEY', 'AWS_SECRET', 'JSONEachRow'
            )
            SELECT * from dbt.mart_leaderboard
            SETTINGS s3_truncate_on_insert=1,
                     output_format_json_quote_64bit_integers=0;
        ''',
        clickhouse_conn_id='clickhouse_gcc',
    )

    # STEP 2: Download from S3 to PostgreSQL host via SSH
    download_cmd = "aws s3 cp s3://gcc-social-data/data-pipeline/tmp/leaderboard.json /tmp/leaderboard.json"
    import_to_pg_box = SSHOperator(
        ssh_conn_id='ssh_prod_pg',
        cmd_timeout=1000,
        task_id='download_to_pg_local',
        command=download_cmd,
    )

    # STEP 3: Load into PostgreSQL with JSONB parsing + atomic swap
    uniq = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    import_to_pg_db = PostgresOperator(
        task_id="import_to_pg_db",
        runtime_parameters={'statement_timeout': '14400s'},  # 4-hour timeout
        postgres_conn_id="prod_pg",
        sql=f"""
            DROP TABLE IF EXISTS leaderboard_tmp;
            DROP TABLE IF EXISTS mart_leaderboard;
            DROP TABLE IF EXISTS leaderboard_old_bkp;

            CREATE TEMP TABLE mart_leaderboard(data jsonb);
            COPY mart_leaderboard from '/tmp/leaderboard.json';

            -- Create UNLOGGED table (faster inserts, no WAL)
            create UNLOGGED table leaderboard_tmp (
                like leaderboard including defaults
            );

            -- Parse JSONB into typed columns
            INSERT INTO leaderboard_tmp (
                month, language, category, platform, profile_type, ...
            )
            SELECT
                (data->>'month')::timestamp AS month,
                (data->>'language') AS language,
                (data->>'followers')::int8 AS followers,
                (data->>'engagement_rate')::float AS engagement_rate,
                (data->>'last_month_ranks')::jsonb AS last_month_ranks,
                (data->>'current_month_ranks')::jsonb AS current_month_ranks
            from mart_leaderboard;

            -- Enrich with platform profile IDs
            update leaderboard_tmp lv
            set platform_profile_id = ia.id,
                audience_gender = ia.audience_gender,
                search_phrase = ia.search_phrase
            from instagram_account ia
            where ia.ig_id = lv.platform_id and lv.platform_id is not null;

            -- Switch from UNLOGGED to LOGGED for durability
            ALTER TABLE leaderboard_tmp SET LOGGED;

            -- Build indexes
            CREATE UNIQUE INDEX leaderboard_{uniq}_pkey1
                ON public.leaderboard_tmp USING btree (id);
            CREATE INDEX leaderboard_{uniq}_month_platform_idx1
                ON public.leaderboard_tmp USING btree (month, platform);

            -- ATOMIC TABLE SWAP inside transaction
            BEGIN;
            ALTER TABLE "leaderboard" RENAME TO "leaderboard_old_bkp";
            ALTER TABLE "leaderboard_tmp" RENAME TO "leaderboard";
            COMMIT;
        """,
    )

    # STEP 4: Vacuum for query planner stats
    vacuum_to_pg_db = PostgresOperator(
        task_id="vacuum_to_pg_db",
        runtime_parameters={'statement_timeout': '3000s'},
        postgres_conn_id="prod_pg",
        sql="vacuum analyze leaderboard;",
        autocommit=True,
    )

    # Pipeline: CH -> S3 -> SSH Download -> PG Load -> Vacuum
    fetch_leaderboard_from_ch >> import_to_pg_box >> import_to_pg_db >> vacuum_to_pg_db
```

### ClickHouse-Specific Features Used

**ReplacingMergeTree for Upserts:**
```sql
{{ config(
    materialized='incremental',
    engine='ReplacingMergeTree()',
    order_by='(profile_id, date)',
    incremental_strategy='append'
) }}
```

**argMax for Latest Value Extraction:**
```sql
argMax(followers, updated_at) followers,
argMax(engagement_rate, updated_at) engagement_rate,
argMaxIf(followers, date, date < toStartOfWeek(now()) - INTERVAL 30 DAY) followers_30d
```

**Partition Pruning and Memory Settings:**
```sql
SETTINGS max_bytes_before_external_group_by = 20000000000,
         max_bytes_before_external_sort = 20000000000,
         join_algorithm='partial_merge'
```

**Array Operations:**
```sql
arrayMap(x -> lower(x), hashtags) hashtags
splitByWhitespace(ifNull(concat(lower(name), ' ', lower(handle)), '')) keywords
splitByChar(',', city)[1] city
```

**S3 Integration:**
```sql
INSERT INTO FUNCTION s3(
    'https://gcc-social-data.s3.ap-south-1.amazonaws.com/data-pipeline/tmp/file.json',
    'AWS_KEY', 'AWS_SECRET', 'JSONEachRow'
)
SELECT * FROM dbt.mart_table
SETTINGS s3_truncate_on_insert=1;
```

### Production Hardening Patterns

**ShortCircuit Operator (Conflict Avoidance):**
```python
def check_hour():
    hour = datetime.now().hour
    if 19 <= hour < 22:
        return False   # ShortCircuit skips all downstream tasks
    return True
```

**Slack Failure Notifications:**
```python
class SlackNotifier(BaseNotifier):
    def slack_fail_alert(context):
        ti = context['ti']
        task_state = ti.state
        if task_state == 'success':
            return
        elif task_state == 'failed':
            SLACK_CONN_ID = Variable.get('slack_failure_conn')
            slack_msg = f"""
            :x: Task Failed.
            *Task*: {context.get('task_instance').task_id}
            *Dag*: {context.get('task_instance').dag_id}
            *Execution Time*: {context.get('execution_date')}
            <{context.get('task_instance').log_url}|*Logs*>
            """
            slack_alert = SlackWebhookOperator(
                task_id='slack_fail',
                webhook_token=slack_webhook_token,
                message=slack_msg,
                channel=channel,
                username='airflow',
            )
            return slack_alert.execute(context=context)
```

**Concurrency Controls:**
```python
max_active_runs=1,    # No parallel DAG runs
concurrency=1,        # One task at a time within DAG
catchup=False,        # Don't backfill on schedule change
dagrun_timeout=dt.timedelta(minutes=X),  # Kill runaway jobs
```

### Scrape Request Management (PythonOperator Pattern)

```python
# dags/sync_insta_collection_posts.py
def create_scrape_request_log():
    import clickhouse_connect
    connection = BaseHook.get_connection("clickhouse_gcc")
    client = clickhouse_connect.get_client(
        host=connection.host,
        password=connection.password,
        username=connection.login,
        send_receive_timeout=extra_params['send_receive_timeout']
    )

    # Smart query: find posts needing refresh, exclude recent attempts and failures
    posts = client.query('''
        with
        posts_to_scrape as (
            select short_code shortcode
            from dbt.stg_coffee_post_collection_item
            where platform = 'INSTAGRAM'
              and post_type IN ('reels', 'image', 'carousel')
              and match(short_code, '^[0-9]*$') = 0
              and created_at >= now() - INTERVAL 2 MONTH
        ),
        attempted_recently as (
            SELECT JSONExtractString(params, 'shortcode') as shortcode
            from _e.scrape_request_log_events
            where flow = 'refresh_post_by_shortcode'
              and event_timestamp >= now() - INTERVAL 12 HOUR
        ),
        failures as (
            SELECT JSONExtractString(params, 'shortcode') as shortcode
            from dbt.stg_beat_scrape_request_log
            where flow = 'refresh_post_by_shortcode'
              and status = 'FAILED'
              and created_at >= now() - INTERVAL 1 MONTH
            group by shortcode
            having uniqExactIf(id, status = 'FAILED') > 1
               and uniqExactIf(id, status = 'COMPLETE') = 0
        )
        select * from candidate_set
        order by publish_time asc nulls first
        LIMIT 250
    ''')

    for shortcode in posts.result_rows:
        data = {"flow": flow, "platform": "INSTAGRAM",
                "params": {"shortcode": shortcode[0]}}
        response = requests.post(url=url, data=json.dumps(data))
```

**Key patterns:** Exclude recent attempts (12h window), exclude persistent failures (2+ fails, 0 successes), prioritize older posts (`ORDER BY publish_time ASC NULLS FIRST`), rate limiting (`LIMIT 250`).

---

## Technical Decisions

### Decision 1: Why ClickHouse -> S3 -> PostgreSQL Instead of Direct Sync?

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **CH -> S3 -> PG** | Decoupled stages, S3 as checkpoint, can retry individual steps | Extra latency, S3 costs | **YES** |
| **Direct ClickHouse -> PostgreSQL** | Fewer hops, lower latency | No checkpoint, CH has no native PG writer, failures require full restart | No |
| **Kafka CDC** | Real-time, event-driven | Overkill for batch analytics, complex setup | No |
| **pg_foreign_data_wrapper** | Direct SQL access | Terrible performance for large datasets, network bottleneck | No |

> "We chose S3 as an intermediate staging layer because it decouples ClickHouse from PostgreSQL. If the PostgreSQL load fails, we don't need to re-export from ClickHouse -- the JSON file is already in S3. ClickHouse has native S3 integration via `INSERT INTO FUNCTION s3()` which is very efficient. The alternative of direct sync doesn't exist natively -- ClickHouse has no built-in PostgreSQL writer. We could have used Kafka CDC, but our use case is batch analytics, not real-time streaming. The S3 staging approach gives us retry-ability, auditability (the JSON files are still there), and separation of concerns."

**Follow-up: "Doesn't the S3 hop add latency?"**
> "Yes, roughly 2-3 minutes for the S3 export and download. But our fastest pipeline runs every 15 minutes, so 2-3 minutes is acceptable. The benefit is that if PostgreSQL is under load or the COPY fails, we don't need to re-query ClickHouse. We just re-download from S3 and retry."

**Follow-up: "Why not clickhouse_fdw?"**
> "Foreign data wrappers work for small queries, but we're syncing entire mart tables -- sometimes millions of rows. FDW sends data row by row over the network. COPY from a local file is orders of magnitude faster because it bypasses the network and uses PostgreSQL's bulk loader."

### Decision 2: Why Apache Airflow vs Prefect/Dagster?

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **Apache Airflow** | Mature ecosystem, rich operator library, dbt/CH/PG plugins | Complex setup, DAG parsing overhead | **YES** |
| **Prefect** | Pythonic, better local dev, dynamic flows | Smaller plugin ecosystem, no native CH operator | No |
| **Dagster** | Type system, asset-based, better testing | Steep learning curve, less community | No |
| **dbt Cloud** | Native dbt scheduling | Can't orchestrate non-dbt tasks (SSH, PG ops) | No |

> "Airflow was the right choice because our pipelines are heterogeneous -- they combine dbt runs, ClickHouse exports, SSH file transfers, and PostgreSQL operations. Airflow has mature operators for all of these: `DbtRunOperator`, `ClickHouseOperator`, `SSHOperator`, `PostgresOperator`. Prefect has better Pythonic ergonomics but lacks native ClickHouse integration. Dagster's asset-based model is interesting but adds complexity we didn't need. dbt Cloud could schedule dbt models, but it can't orchestrate the SSH transfers and PostgreSQL atomic swaps that are core to our pipeline."

**Follow-up: "What are the downsides of Airflow?"**
> "DAG parsing time is the biggest issue -- with 76 DAGs, the scheduler takes time to parse all files. We also had to be careful with `max_active_runs=1` and `concurrency=1` on every DAG to prevent resource contention. The UI can be slow with many DAGs. If I were starting fresh today, I might consider Dagster for its better testing story."

### Decision 3: Why dbt for Transformations vs Custom Python?

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **dbt** | SQL-native, dependency tracking, incremental, Jinja templating | Learning curve, ClickHouse adapter maturity | **YES** |
| **Custom Python (pandas)** | Full flexibility, ML integration | Slow at scale, no dependency management, hard to maintain | No |
| **Spark SQL** | Distributed, handles huge data | Overkill for our scale, complex infra | No |
| **Stored procedures** | Database-native | No version control, no dependency DAG, hard to test | No |

> "dbt gives us three critical things. First, `ref()` creates an automatic dependency graph -- when I write `ref('stg_beat_instagram_account')`, dbt knows to run the staging model first. With 112 models, manual dependency management would be impossible. Second, Jinja templating lets us generate SQL dynamically -- our mart_instagram_account model loops over 19 metrics to generate performance grades, which would be hundreds of lines of hand-written SQL. Third, the tag system lets us group models by schedule frequency -- `tag:core` runs every 15 minutes, `tag:daily` runs once. Custom Python scripts in pandas would work for small datasets but can't handle the volume or complexity of our 83 mart models."

### Decision 4: Why Atomic Table Swap vs UPSERT?

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **Atomic table swap (RENAME)** | Zero-downtime, consistent snapshot, simple | Full table rebuild, temporary 2x storage | **YES** |
| **UPSERT (INSERT ON CONFLICT)** | Incremental, less storage | Row-level locking, inconsistent reads during update, slow for millions of rows | No |
| **DELETE + INSERT** | Simple | Table locked during operation, inconsistent reads | No |
| **Materialized views** | Automatic refresh | PostgreSQL matview refresh locks table, no concurrent reads | No |

> "UPSERT sounds ideal on paper, but with millions of rows being updated, the row-level locking in PostgreSQL causes significant contention. Our SaaS app reads these tables for every API request -- leaderboard queries, profile lookups, collection analytics. With UPSERT, users would see inconsistent data during the update window (some rows old, some new). The atomic RENAME happens in a single transaction -- one instant the old table is serving, the next instant the new table is serving. Zero inconsistency, zero downtime. The trade-off is we need 2x storage temporarily, which is cheap compared to the consistency guarantee."

**Follow-up: "What if the swap fails mid-transaction?"**
> "PostgreSQL's transaction guarantees protect us. If the RENAME fails -- say the new table has constraint violations -- the entire transaction rolls back. The old table is still in place. We also keep the old table as `_old_bkp` so we can manually restore if needed."

**Follow-up: "Why UNLOGGED tables for the temporary table?"**
> "We use `CREATE UNLOGGED TABLE` for the temp table in the leaderboard sync. UNLOGGED tables skip WAL writes, making inserts 2-3x faster. We then `ALTER TABLE SET LOGGED` before the swap. Since the temp table is disposable -- we rebuild it every run -- the risk of data loss on crash is acceptable."

### Decision 5: Why ReplacingMergeTree vs Standard MergeTree?

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **ReplacingMergeTree** | Automatic dedup on merge, idempotent inserts | Dedup not guaranteed until merge, needs FINAL for exact reads | **YES** |
| **Standard MergeTree** | Simplest, fastest inserts | Duplicates accumulate, must handle dedup in queries | No |
| **CollapsingMergeTree** | Can handle updates/deletes | Complex sign column logic, error-prone | No |
| **AggregatingMergeTree** | Pre-aggregated state | Only for aggregate queries, not raw data | No |

> "We chose ReplacingMergeTree because our pipelines are append-only with overlapping windows. The 4-hour lookback means we re-process some records that were already inserted. ReplacingMergeTree automatically deduplicates during background merges based on the ORDER BY key. With standard MergeTree, these duplicates would accumulate and inflate our query results. The trade-off is that before a merge happens, `SELECT` queries might see duplicates, but for our analytics use case, minor temporary duplicates are acceptable."

**Follow-up: "How do you handle the pre-merge duplicate issue?"**
> "For models where exact dedup matters, we use `argMax(value, timestamp)` in the SQL query itself. This gives us the latest value per key regardless of whether ClickHouse has merged the parts yet."

### Decision 6: Why Incremental 4-Hour Lookback vs Full Refresh?

```sql
{% if is_incremental() %}
WHERE created_at > (
    SELECT max(last_updated) - INTERVAL 4 HOUR
    FROM {{ this }}
)
{% endif %}
```

> "We use a hybrid approach. Time-series models use incremental with a 4-hour lookback window. The lookback handles late-arriving data -- scrape results that arrive after the initial processing window. Full refresh is used for daily models like `mart_leaderboard` where we need the complete dataset recalculated. The 4-hour window was tuned empirically -- our scrape pipeline typically delivers results within 2 hours, so 4 hours gives us 2x safety margin."

**Follow-up: "What if data arrives more than 4 hours late?"**
> "It gets picked up by the daily full refresh, which runs at 19:00 UTC. So worst case, a late-arriving data point is delayed by one day in our time-series models."

### Decision 7: Why SSH Transfer vs Direct S3-to-PostgreSQL?

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **SSH + aws s3 cp + local COPY** | COPY from local file is fastest, simple | Requires SSH access, disk space on PG host | **YES** |
| **aws_s3 extension (COPY FROM S3)** | No SSH needed | Requires PostgreSQL extension, not always available | No |
| **Stream S3 through Airflow worker** | No SSH needed | Airflow worker becomes bottleneck, memory issues | No |
| **Lambda trigger** | Serverless | Additional infrastructure, harder to debug | No |

> "PostgreSQL's `COPY FROM` is fastest when reading from a local file -- it bypasses network overhead entirely. The SSH operator downloads the S3 file to `/tmp/` on the PostgreSQL host, then `COPY` reads it locally. The alternative `aws_s3` extension exists but wasn't installed on our PostgreSQL instance, and adding extensions to a production database requires DBA approval and downtime."

### Decision 8: Why ClickHouse for OLAP vs BigQuery/Snowflake?

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **ClickHouse (self-hosted)** | Extremely fast OLAP, free, native S3 integration, real-time inserts | Self-managed, single-node risk | **YES** |
| **BigQuery** | Serverless, no ops | Pay-per-query expensive at our scale, no real-time insert | No |
| **Snowflake** | Scalable, multi-cloud | Expensive for always-on analytics, cold start | No |
| **PostgreSQL only** | Single database, simpler | OLAP queries too slow on PostgreSQL at our data volume | No |

> "ClickHouse was ideal for three reasons. First, we need real-time inserts -- scrape data arrives continuously and needs to be queryable immediately. Second, our ranking queries scan millions of rows with GROUP BY and ORDER BY -- ClickHouse's columnar storage handles this in seconds where PostgreSQL would take minutes. Third, ClickHouse's native S3 integration eliminates the need for an external export tool. BigQuery's pay-per-query model would be expensive given we run queries every 5-15 minutes. We kept PostgreSQL for serving the SaaS app because it handles transactional reads (single profile lookup) better than ClickHouse."

### Decision 9: Why JSONEachRow Format for S3 Staging?

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **JSONEachRow** | PostgreSQL COPY compatible, human-readable, schema-flexible | Larger file size vs binary | **YES** |
| **CSV** | Smallest text format | Escaping issues with commas in text fields, no nested types | No |
| **Parquet** | Compressed, columnar | PostgreSQL can't COPY from Parquet, needs extra tool | No |
| **Avro** | Compressed, schema-enforced | PostgreSQL can't COPY from Avro, needs extra tool | No |

> "JSONEachRow is ClickHouse's native one-JSON-per-line format, and it's directly compatible with PostgreSQL's `COPY` command. PostgreSQL can `COPY` a file where each line is a JSON object into a `JSONB` column. We then parse fields with `data->>'field_name'` and cast types. CSV was rejected because our data contains commas, quotes, and special characters in fields like biography and post titles. Parquet would be smaller but PostgreSQL has no native Parquet reader. The file size trade-off is acceptable because the files are temporary staging -- they're overwritten on every run."

---

## Interview Q&A

### Q1: "Tell me about the data platform you built."

> "At Good Creator Co., I built Stir -- the data orchestration and transformation platform for an influencer marketing SaaS product. It processes social media data from Instagram and YouTube, transforms it through 112 dbt models in ClickHouse, and syncs analytics to PostgreSQL for the web application. I designed 76 Airflow DAGs with scheduling from every 5 minutes to weekly, cutting data latency by 50%."

**Follow-up: "What's the business problem?"**
> "Brands like Coca-Cola and Nike need to find and evaluate influencers for marketing campaigns. They search by follower count, engagement rate, category, language, and country. Our platform ranks millions of profiles across multiple dimensions and updates these rankings in near-real-time."

**Follow-up: "Walk me through the architecture."**
> "It's a three-layer architecture. Layer 1 is ClickHouse -- our OLAP engine where dbt runs 112 models that compute rankings, engagement rates, growth metrics, and time series. Layer 2 is S3 staging -- ClickHouse exports JSON files using its native S3 integration. Layer 3 is PostgreSQL -- we SSH-download the files, parse JSONB, enrich with operational data, and do an atomic table swap so the SaaS app always reads consistent data. Airflow orchestrates everything with 76 DAGs across 7 scheduling tiers."

### Q2: "How did you cut data latency by 50%?"

> "Before Stir, data transformations ran as monolithic daily batch jobs. A profile update could take 24 hours to appear in the app. I restructured the pipeline into tiered scheduling. Core metrics -- follower counts, engagement rates -- now run every 15 minutes via the `dbt_core` DAG. Collections update every 30 minutes. Only heavy computations like full leaderboard rebuilds remain daily. The key insight was that not all data needs the same freshness. By matching scheduling frequency to business requirements, we went from 24-hour average latency to under 12 hours overall, with core metrics under 15 minutes."

**Follow-up: "How do you prevent the fast schedules from overwhelming the system?"**
> "Three mechanisms. First, `max_active_runs=1` on every DAG prevents a slow run from stacking with the next scheduled run. Second, `ShortCircuitOperator` pauses hourly and collection DAGs during the daily batch window (19:00-22:00 UTC). Third, timeout enforcement -- `dagrun_timeout` kills runaway jobs, from 40 minutes for simple tasks to 360 minutes for the daily batch."

### Q3: "Explain the atomic table swap pattern."

> "When syncing analytics from ClickHouse to PostgreSQL, we never update the production table in-place. Instead, we create a temporary table, load all the data, enrich it with JOINs against operational tables, build indexes, and then within a single PostgreSQL transaction, RENAME the old table to `_old_bkp` and RENAME the new table to the production name. Zero-downtime updates -- the SaaS app switches from reading the old table to the new table in a single atomic operation."

**Follow-up: "Why not UPSERT?"**
> "With millions of rows, UPSERT causes row-level locking that blocks reads. With atomic swap, reads are never blocked. The trade-off is 2x storage temporarily, but that's cheap compared to user-facing latency."

### Q4: "Explain your dbt model architecture."

> "Two-layer architecture: 29 staging models and 83 mart models. Staging models extract raw data from source databases with minimal transformation. Mart models contain business logic: computing engagement rates, multi-dimensional rankings, growth metrics, and collection analytics. Models are organized by domain: discovery (16), leaderboard (14), collection (12), profile stats (14), genre (7), audience (4), posts (3), orders (1), and staging collections (9)."

**Follow-up: "How do you manage dependencies between 112 models?"**
> "dbt's `ref()` function handles this automatically. We also use dbt tags to group models by schedule: `tag:core` for every-15-minute models, `tag:daily` for once-a-day, `tag:collections` for every 30 minutes. Each Airflow DAG runs `DbtRunOperator(select=['tag:X'])` which only executes models in that tag group, respecting dependency order."

### Q5: "How do you use ClickHouse's argMax?"

> "`argMax(value, timestamp)` is a ClickHouse aggregate function that returns the `value` at the row where `timestamp` is maximum. It's equivalent to a correlated subquery or window function in standard SQL but runs in a single pass. We use it extensively for deduplication -- when the same profile has multiple rows from overlapping incremental windows, `argMax` always picks the latest value."

```sql
-- Instead of this standard SQL:
SELECT followers FROM profiles WHERE updated_at = (SELECT MAX(updated_at) ...)
-- We write this ClickHouse-native:
SELECT argMax(followers, updated_at) followers FROM profiles GROUP BY profile_id
```

**Follow-up: "What about argMaxIf?"**
> "`argMaxIf(followers, date, date < now() - INTERVAL 30 DAY)` returns the latest follower count from before 30 days ago. We use it to compute growth metrics: `current_followers - followers_30d_ago`. In standard SQL, this would require a self-join or complex window function with RANGE."

### Q6: "How does the ClickHouse-to-S3 export work?"

> "ClickHouse has a native `s3()` table function. We use `INSERT INTO FUNCTION s3(url, key, secret, format) SELECT ... FROM table`. This pushes query results directly to S3 in a single operation. We use `JSONEachRow` format because PostgreSQL can `COPY` it directly into a JSONB column. `s3_truncate_on_insert=1` overwrites the file on each run."

**Follow-up: "Why `output_format_json_quote_64bit_integers=0`?"**
> "By default, ClickHouse quotes 64-bit integers as strings in JSON to prevent JavaScript precision loss. But PostgreSQL's JSONB parser expects unquoted numbers. This setting ensures integers are written as numbers, so `(data->>'followers')::int8` works correctly on the PostgreSQL side."

### Q7: "How do you handle data quality?"

> "Multiple layers. dbt's `ref()` ensures dependency order. Staging models use `COALESCE` for NULL handling and type casting. PostgreSQL's JSONB parsing validates types -- if a field can't cast to `int8`, the COPY fails and the atomic swap never happens, so the old table stays live. We also use `replaceRegexpAll` in ClickHouse to sanitize URLs and text before export."

### Q8: "Explain the Jinja templating in your dbt models."

> "The most sophisticated use is in `mart_instagram_account`. We define 19 metrics and use a Jinja `for` loop to generate percentile-based grades for each metric. This generates 38 columns (grade + group average per metric) from 10 lines of Jinja. If we add a new metric, we just append to the list -- no SQL changes needed."

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

### Q9: "How do you handle the leaderboard ranking system?"

> "Multi-dimensional. We rank influencers along 4 axes: followers, follower growth, views, and reels plays. Each axis is ranked globally and within 4 segmentation dimensions: by category, by language, by category+language, and by profile type. That's 28 rank dimensions per platform, stored as a ClickHouse Map type. We also store previous month's ranks in a separate Map column so the frontend can show rank changes."

**Follow-up: "Why a Map type instead of separate columns?"**
> "28 rank dimensions times 2 (current + previous) would be 56 columns. The Map type stores them as key-value pairs in a single column. PostgreSQL receives it as JSONB. It also makes adding new rank dimensions backward-compatible."

### Q10: "How do you monitor 76 DAGs?"

> "Every DAG has `on_failure_callback = SlackNotifier.slack_fail_alert`. Slack message includes DAG ID, task ID, execution time, and direct link to logs. `max_active_runs=1` prevents cascading failures. `dagrun_timeout` kills runaway jobs. `catchup=False` prevents schedule-change backfills. For PostgreSQL sync, `runtime_parameters={'statement_timeout': '14400s'}` kills long-running queries."

### Q11: "If you were redesigning from scratch?"

> "Three things. First, secrets manager instead of hardcoded credentials -- the current setup has AWS keys directly in DAG SQL strings. Second, data quality tests using dbt's built-in framework -- `unique`, `not_null`, `accepted_values`. Third, ClickHouse Cloud or a multi-node cluster for high availability."

### Q12: "How would you scale to 10x data volume?"

> "Three changes. First, ClickHouse multi-shard cluster with ReplicatedMergeTree for fault tolerance. Second, parallelize dbt models -- our `concurrency=1` is conservative; with a cluster, we could run multiple models simultaneously. Third, replace S3 staging with Kafka for real-time streaming. But honestly, ClickHouse handles 10x volume on a single node for analytical queries -- the bottleneck would be the PostgreSQL sync, which we'd solve by moving the SaaS app to read from ClickHouse directly."

---

## Behavioral Stories

### The Data Latency Story (Primary -- Use for "Tell me about improving a pipeline")

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

**Key Learning (always add this):**
> "The key learning was that scheduling is a product decision, not just an engineering decision. Matching data freshness to business requirements is more impactful than making everything real-time."

### Story: "Why ClickHouse instead of BigQuery or Snowflake?"

> "Three reasons. First, real-time inserts -- our scraper produces data continuously and we need it queryable immediately. BigQuery and Snowflake are designed for batch loading. Second, query speed -- our leaderboard model scans millions of profiles, ranks them across 28 dimensions, and needs to complete within minutes. ClickHouse's columnar storage and vectorized execution handle this. Third, cost -- we're a startup. ClickHouse is open-source, self-hosted on a single EC2 instance. BigQuery's per-query pricing with queries running every 5-15 minutes would be expensive."

### Story: "Why the three-layer pipeline instead of direct sync?"

> "The key constraint was that ClickHouse has no native PostgreSQL writer. S3 serves as a checkpoint. If PostgreSQL is under load and the COPY fails, we don't re-query ClickHouse -- the JSON is already in S3. ClickHouse's native `INSERT INTO FUNCTION s3()` streams query results directly to S3 without buffering. On the PostgreSQL side, `COPY FROM` a local file is the fastest bulk loading mechanism."

### Story: "Why atomic table swap instead of UPSERT?"

> "When you UPSERT millions of rows in PostgreSQL, each row acquires a row-level lock. Our SaaS app reads these tables for every API request. With UPSERT, a user might see inconsistent data: some profiles updated, others still old. The atomic RENAME inside a transaction is instant. We also create the temp table as UNLOGGED for 2-3x faster inserts, then switch to LOGGED before the swap. And we keep the old table as `_old_bkp` for emergency rollback."

---

## What-If Scenarios

### Scenario 1: "What if ClickHouse goes down?"

> **DETECT:** Airflow DbtRunOperator and ClickHouseOperator tasks fail. Slack notifications fire for every affected DAG.
>
> **IMPACT:** All 11 dbt orchestration DAGs stop. BUT -- PostgreSQL still serves the SaaS app with the last successfully synced data. Users see slightly stale data, but the app doesn't break.
>
> **RECOVER:** Restart ClickHouse. Since dbt materializes as tables (not views), models are persisted on disk. Airflow with `catchup=False` picks up the next scheduled run without trying to backfill.
>
> **PREVENT:** Move to ClickHouse Cloud or multi-node cluster with ReplicatedMergeTree.

### Scenario 2: "What if the S3 export fails midway -- partial JSON file?"

> **DETECT:** SSH download succeeds (partial file exists). But PostgreSQL COPY fails -- invalid JSON at the truncation point. Slack notification fires.
>
> **IMPACT:** The COPY fails, so the temp table is never populated, so the atomic swap never executes. Old production table remains live and untouched. Users see no impact.
>
> **RECOVER:** Simply wait for the next scheduled run. The DAG retries automatically. `s3_truncate_on_insert=1` means each run fully overwrites the file.
>
> **PREVENT:** Could add a row count validation step after COPY, comparing against a ClickHouse count query. But the PostgreSQL COPY failure is already a sufficient guard.

### Scenario 3: "What if the atomic table swap fails mid-transaction?"

> **DETECT:** PostgresOperator task fails. Slack notification fires.
>
> **IMPACT:** PostgreSQL's transaction guarantee protects us. `BEGIN; ALTER TABLE RENAME; COMMIT;` either fully completes or fully rolls back. Old production table is untouched.
>
> **RECOVER:** Investigate why (usually constraint violation or stale temp table from previous failed run). `DROP TABLE IF EXISTS` at the start handles stale artifacts. Re-trigger the DAG.

### Scenario 4: "What if the daily batch takes longer than 6 hours?"

> **DETECT:** `dagrun_timeout=360 minutes` kills the DAG run. Slack failure notification fires.
>
> **IMPACT:** Daily models (leaderboards, time series) are stale for that day. But ShortCircuitOperator automatically resumes hourly and collection DAGs once the 19:00-22:00 window passes, so near-real-time data keeps flowing.
>
> **RECOVER:** Investigate slow queries. Increase memory limits or optimize. Run `dbt_daily` manually with `--full-refresh` during off-peak hours.
>
> **PREVENT:** Monitor query execution time trends. Alert when the daily batch exceeds 80% of its timeout budget. Consider breaking into smaller parallel tag groups.

### Scenario 5: "What if two DAGs try to swap the same PostgreSQL table?"

> **DETECT:** Shouldn't happen due to `max_active_runs=1` and `concurrency=1`. If two DIFFERENT DAGs target the same table, one fails with 'table does not exist' error.
>
> **IMPACT:** PostgreSQL's DDL locking serializes the transactions. The first succeeds; the second fails.
>
> **RECOVER:** Failed DAG's next scheduled run will succeed. `DROP TABLE IF EXISTS` cleans up leftovers.
>
> **PREVENT:** `max_active_runs=1` is the primary guard. Random index name suffixes prevent name collisions.

### Scenario 6: "What if the scrape pipeline stops -- dbt models process empty tables?"

> **DETECT:** dbt models still succeed -- they produce empty results. Downstream sync exports empty JSON, swaps with an empty table. SaaS app shows no data. **This is the most dangerous scenario -- silent data loss.**
>
> **RECOVER:** The `_old_bkp` table is still on disk. Manual `ALTER TABLE leaderboard_old_bkp RENAME TO leaderboard` restores the previous version.
>
> **PREVENT:** Add a row count validation: after COPY, check `SELECT COUNT(*)`. If less than 50% of the current production table's row count, ShortCircuit the swap.

### Scenario 7: "What if a dbt model produces wrong results?"

> **DETECT:** dbt succeeds (SQL is valid) but produces incorrect metrics. Only caught by users noticing anomalous data.
>
> **MITIGATE:** Tag-based scheduling limits blast radius. `exclude=['tag:deprecated']` lets us quickly deprecate a broken model.
>
> **RECOVER:** Fix SQL, commit, deploy via GitLab CI. dbt models are idempotent. For PostgreSQL, `_old_bkp` has the last correct data.
>
> **PREVENT:** Implement dbt tests: `unique`, `not_null`, `accepted_values`, and custom business logic tests. Add a staging environment.

### Scenario 8: "What if someone needs to add a new metric to the leaderboard?"

> **Steps:**
> 1. **dbt model**: Add the computation to `mart_leaderboard.sql`. Add the rank to the Map type columns.
> 2. **Sync DAG**: Add the field to the PostgreSQL INSERT. Add JSONB parsing: `(data->>'new_metric')::float`.
> 3. **PostgreSQL schema**: `ALTER TABLE leaderboard ADD COLUMN`. Temp table uses `LIKE production_table` so it picks up new columns automatically.
> 4. **Test**: Run dbt manually, verify in ClickHouse, trigger sync DAG manually.
>
> **Time estimate:** 2-4 hours. The Map type makes adding new rank dimensions backward-compatible. The Jinja templating means adding a new grade is just appending to a list.

---

## How to Speak

### Pyramid Method -- Architecture Question

**Level 1 -- Headline (always start here):**
> "It's a three-layer ELT pipeline with 76 Airflow DAGs orchestrating 112 dbt models, flowing data from ClickHouse through S3 staging to PostgreSQL with atomic table swaps."

**Level 2 -- Structure (if they want more):**
> "Layer 1 is ClickHouse -- our OLAP engine. dbt runs 29 staging models and 83 mart models that compute engagement rates, rankings, growth trends, collection analytics. All SQL-based with Jinja templating.
>
> Layer 2 is S3 staging. ClickHouse has native S3 integration -- `INSERT INTO FUNCTION s3()` exports JSON directly. This decouples ClickHouse compute from PostgreSQL load, giving us retry-ability.
>
> Layer 3 is PostgreSQL. SSH operator downloads the JSON, COPY command loads it into JSONB, we parse and type-cast each field, enrich with JOINs, then do an atomic table swap -- RENAME in a transaction."

**Level 3 -- Go deep on ONE part:**
> "The most interesting design is the scheduling architecture. 7 tiers matched to business freshness requirements. Scrape monitoring every 5 minutes. Core metrics every 15 minutes. Collections every 30 minutes. Leaderboards daily. The `ShortCircuitOperator` pauses fast-frequency DAGs during the daily batch window to prevent ClickHouse resource contention."

**Level 4 -- OFFER (always say this):**
> "I can go deeper into the ClickHouse-specific optimizations like argMax and ReplacingMergeTree, the dbt Jinja templating that generates performance grades across 19 metrics, or the atomic table swap pattern -- which interests you?"

### Pivot Phrases

**If they ask about real-time streaming (Kafka, Flink):**
> "Our architecture is batch-oriented because influencer analytics don't need sub-second freshness. Our fastest pipeline runs every 5 minutes. If I needed true real-time, I'd replace the S3 staging layer with Kafka -- ClickHouse has a native Kafka engine -- but for our use case, 5-minute batches give us simpler operations with acceptable freshness."

**If they ask about data quality/testing:**
> "We enforce data quality at multiple layers. dbt's `ref()` ensures execution order. ClickHouse's `COALESCE` and type casting handle NULLs. PostgreSQL's JSONB parsing fails the entire COPY if any row has invalid types, and the atomic swap ensures the old table stays live. If I were to improve this, I'd add dbt's built-in tests and a data lineage tool."

**If they ask about CI/CD:**
> "We use GitLab CI with a manual deployment step. Production deploys are gated behind manual approval. If I were redesigning, I'd add staging environment testing with dbt's `--defer` flag to test changes against production data."

**If they ask about cost:**
> "Self-hosted ClickHouse on EC2 keeps OLAP costs near zero. S3 staging costs are negligible -- files are temporary and overwritten each run. The entire data platform infrastructure costs less than what a single BigQuery or Snowflake seat would cost per month."
