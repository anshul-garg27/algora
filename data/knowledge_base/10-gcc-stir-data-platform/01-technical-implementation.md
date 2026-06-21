# Technical Implementation - Stir Data Platform

> **Every code snippet below is from the actual production codebase.**
> File paths reference the `stir/` repository structure.

---

## 1. DAG Configurations (76 DAGs)

### Scheduling Tiers - From Real DAG Files

**Tier 1: Every 5 minutes -- Real-time monitoring**
```python
# dags/dbt_recent_scl.py (ACTUAL CODE)
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
# dags/sync_insta_collection_posts.py (ACTUAL CODE)
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
# dags/dbt_core.py (ACTUAL CODE)
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
# dags/dbt_collections.py (ACTUAL CODE)
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
    # ShortCircuit to skip during daily batch window (19:00-22:00)
    check_hour_task = ShortCircuitOperator(
        task_id="check_hour",
        python_callable=check_hour,   # Returns False if 19 <= hour < 22
    )
```

**Tier 5: Every 2 hours -- Hourly models (with conflict avoidance)**
```python
# dags/dbt_hourly.py (ACTUAL CODE)
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
# dags/post_ranker.py (ACTUAL CODE)
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
# dags/dbt_daily.py (ACTUAL CODE)
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
# dags/dbt_weekly.py (ACTUAL CODE)
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

---

## 2. dbt Model Architecture (112 Models)

### Staging Layer (29 Models) -- Raw Data Extraction

```sql
-- models/staging/stg_beat_instagram_account.sql (ACTUAL CODE)
{{ config(materialized = 'table', tags=["post_ranker_partial"], order_by='id') }}
with
data as (
     select * from beat_replica.instagram_account
)
select * from data
```

Key staging sources:
- **beat (14 models)**: `stg_beat_instagram_account`, `stg_beat_instagram_post`, `stg_beat_youtube_account`, `stg_beat_youtube_post`, `stg_beat_scrape_request_log`, `stg_beat_profile_log`, `stg_beat_asset_log`, etc.
- **coffee (15 models)**: `stg_coffee_post_collection`, `stg_coffee_post_collection_item`, `stg_coffee_profile_collection`, `stg_coffee_campaign_profiles`, `stg_coffee_activity_tracker`, etc.

### Mart Layer (83 Models) -- Business Logic

#### mart_instagram_account (Core Discovery Model -- 559 lines)

This is the most complex model, joining 12+ CTEs to produce the master influencer profile:

```sql
-- models/marts/discovery/mart_instagram_account.sql (ACTUAL CODE, key sections)
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
        -- ... 50+ fields including:
        multiIf(
            followers < 5000, '0-5k',
            followers < 10000, '5k-10k',
            followers < 50000, '10k-50k',
            followers < 100000, '50k-100k',
            followers < 500000, '100k-500k',
            followers < 1000000, '500k-1M',
            '1M+'
        ) follower_group,

        -- Ranking within country/category
        rank() over (partition by country order by followers desc) country_rank,
        rank() over (partition by country, category order by followers desc) category_rank,
    from {{ref('mart_instagram_account_summary')}} stats
    left join {{ref('stg_beat_instagram_account')}} ia on ia.profile_id = stats.profile_id
    left join {{ref('mart_audience_info')}} aud on aud.platform_id = ia.profile_id
    -- ... 10+ more joins
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
        -- ... 50+ argMax columns
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

**Key patterns in this model:**
1. **argMax for deduplication** -- ClickHouse's `argMax(value, timestamp)` returns the value at the max timestamp
2. **argMaxIf for time-windowed growth** -- `argMaxIf(followers, date, date < now() - INTERVAL 30 DAY)` gets followers 30 days ago
3. **Jinja templating for grading** -- Loop over 19 metrics to generate percentile grades
4. **multiIf for follower segmentation** -- Nano/Micro/Macro/Mega classification
5. **12+ LEFT JOINs** -- Combining data from Beat, Coffee, Vidooly, predictions

---

#### mart_leaderboard (Multi-Dimensional Rankings)

```sql
-- models/marts/leaderboard/mart_leaderboard.sql (ACTUAL CODE, key structure)
{{ config(materialized = 'table', tags=["daily", "leaderboard"],
          order_by='month, platform, platform_id') }}

-- Instagram leaderboard
select
    month,
    'IA' profile_platform,
    language, category,
    ifNull(platform, 'MISSING') platform,
    platform_id,
    followers, engagement_rate, avg_likes, avg_comments, avg_views, avg_plays,
    followers_rank, followers_change_rank, views_rank,
    -- Per-dimension ranks
    followers_rank_by_cat, views_rank_by_cat,
    followers_rank_by_lang, views_rank_by_lang,
    followers_rank_by_cat_lang, views_rank_by_cat_lang,
    -- Previous month ranks stored as ClickHouse Map type
    CAST(map(
        'followers_rank', ifNull(followers_rank_prev, 0),
        'views_rank', ifNull(views_rank_prev, 0),
        'followers_change_rank', ifNull(followers_change_rank_prev, 0),
        'plays_rank', ifNull(plays_rank_prev, 0),
        -- ... 28 rank dimensions stored
    ), 'Map(String, UInt64)') last_month_ranks,
    CAST(map(
        'followers_rank', ifNull(followers_rank, 0),
        'views_rank', ifNull(views_rank, 0),
        -- ... 28 rank dimensions
    ), 'Map(String, UInt64)') current_month_ranks
from {{ref('mart_instagram_leaderboard')}}

UNION ALL

-- YouTube leaderboard
select ... from {{ref('mart_youtube_leaderboard')}}

UNION ALL

-- Cross-platform leaderboard
select ... from {{ref('mart_cross_platform_leaderboard')}}

SETTINGS max_bytes_before_external_group_by = 20000000000,
         max_bytes_before_external_sort = 20000000000,
         join_algorithm='partial_merge'
```

**Key patterns:**
1. **ClickHouse Map type** -- `CAST(map(...), 'Map(String, UInt64)')` stores 28 rank dimensions per profile as a single column
2. **UNION ALL** for multi-platform -- Instagram, YouTube, and cross-platform combined
3. **Memory settings** -- `max_bytes_before_external_group_by = 20GB` allows spilling to disk for large aggregations
4. **partial_merge join** -- ClickHouse join algorithm for memory-efficient large joins

---

#### mart_time_series (Weekly/Monthly Growth Tracking)

```sql
-- models/marts/leaderboard/mart_time_series.sql (ACTUAL CODE)
{{ config(materialized = 'table', tags=["daily", "leaderboard"],
          order_by="date, ifNull(platform_id, 'MISSING')") }}

-- Filter to Indian profiles only
with channels as (
    select channelid from dbt.mart_youtube_account where country = 'IN'
),
profile_ids as (
    select ig_id from dbt.mart_instagram_account where country = 'IN'
),

-- YouTube weekly time series
yt_weekly as (
    select date, p_date, platform, platform_id,
        toInt64(if(base.views < 0, 0, base.views)) views_total,
        toInt64(if(views_change < 0, 0, views_change)) views,
        likes, comments, engagement, plays, followers, following,
        avg_views, avg_likes, avg_comments, engagement_rate, avg_plays,
        toInt64(if(uploads_change < 0, 0, uploads_change)) uploads,
        followers_change, false monthly_stats
    from dbt.mart_yt_account_weekly base
    where platform_id in channels
),
-- ... Instagram weekly, Instagram monthly, YouTube monthly

select * from yt_weekly
    union all select * from insta_weekly
    union all select * from insta_monthly
    union all select * from yt_monthly
SETTINGS max_bytes_before_external_group_by = 20000000000,
         max_bytes_before_external_sort = 20000000000,
         join_algorithm='partial_merge'
```

---

#### mart_insta_account_weekly (Window Functions for Growth)

```sql
-- models/marts/leaderboard/mart_insta_account_weekly.sql (ACTUAL CODE, key CTE)
followers_by_week as (
    select
        week, profile_id,
        max(followers) followers,
        max(following) following,
        -- Window function to get previous week's data
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

---

#### mart_collection_post (Campaign Analytics -- 382 lines)

```sql
-- models/marts/collection/mart_collection_post.sql (ACTUAL CODE, key sections)
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

---

#### mart_instagram_account_summary (Post Ranking)

```sql
-- models/marts/profile_stats/mart_instagram_account_summary.sql (ACTUAL CODE)
{{ config(materialized = 'table', tags=["post_ranker"], order_by='profile_id') }}

-- Multi-dimensional post ranking using window functions
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

---

## 3. Three-Layer Data Flow: ClickHouse -> S3 -> PostgreSQL

### Complete Pipeline: sync_leaderboard_prod (ACTUAL CODE)

```python
# dags/sync_leaderboard_prod.py (ACTUAL CODE)
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
            -- Clean up previous runs
            DROP TABLE IF EXISTS leaderboard_tmp;
            DROP TABLE IF EXISTS mart_leaderboard;
            DROP TABLE IF EXISTS leaderboard_old_bkp;

            -- Create temp table for raw JSON
            CREATE TEMP TABLE mart_leaderboard(data jsonb);
            COPY mart_leaderboard from '/tmp/leaderboard.json';

            -- Create UNLOGGED table (faster inserts, no WAL)
            create UNLOGGED table leaderboard_tmp (
                like leaderboard
                including defaults
            );

            -- Parse JSONB into typed columns
            INSERT INTO leaderboard_tmp (
                month, language, category, platform, profile_type,
                handle, followers, engagement_rate, avg_likes, avg_comments,
                avg_views, avg_plays, followers_rank, followers_change_rank,
                views_rank, platform_id, country, ...
            )
            SELECT
                (data->>'month')::timestamp AS month,
                (data->>'language') AS language,
                (data->>'category') AS category,
                (data->>'followers')::int8 AS followers,
                (data->>'engagement_rate')::float AS engagement_rate,
                (data->>'last_month_ranks')::jsonb AS last_month_ranks,
                (data->>'current_month_ranks')::jsonb AS current_month_ranks
                ...
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

            -- Build indexes (random suffix to avoid name conflicts)
            CREATE UNIQUE INDEX leaderboard_{uniq}_pkey1
                ON public.leaderboard_tmp USING btree (id);
            CREATE INDEX leaderboard_{uniq}_month_platform_idx1
                ON public.leaderboard_tmp USING btree (month, platform);
            -- ... 4 more indexes

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

### Complete Pipeline: dbt_collections (with ClickHouse + PostgreSQL transforms)

```python
# dags/dbt_collections.py (ACTUAL CODE -- task chain)

# 1. ShortCircuit: Skip during daily batch window
check_hour_task = ShortCircuitOperator(...)

# 2. Truncate fake events table in ClickHouse before rebuild
truncate_fake_ts = ClickHouseOperator(
    task_id='truncate_fake_ts',
    database='dbt',
    sql='truncate table dbt.mart_fake_events',
    clickhouse_conn_id='clickhouse_gcc',
)

# 3. Run dbt models tagged "collections"
create_ts = DbtRunOperator(
    task_id="create_ts",
    select=["tag:collections"],
    exclude=["tag:deprecated", "tag:post_ranker", "tag:core"],
    target="production",
    profile="gcc_warehouse",
)

# 4. Export from ClickHouse to S3 with hashtag normalization
fetch_from_ch = ClickHouseOperator(
    task_id='fetch_from_ch',
    sql='''
        INSERT INTO FUNCTION s3(
            '.../data-pipeline/tmp/cps.json', 'KEY', 'SECRET', 'JSONEachRow'
        )
        select platform, post_short_code, post_type,
            replaceRegexpAll(post_link, '[^a-zA-Z0-9_%\/\:\.\-\?]', '') post_link,
            arrayMap(x -> lower(x), hashtags) hashtags,
            ...
        from dbt.mart_collection_post
        SETTINGS s3_truncate_on_insert=1;
    ''',
)

# 5. SSH download with escape character handling
download_cmd = ("aws s3 cp s3://gcc-social-data/.../cps.json /tmp/cps_raw.json "
                "&& sed -e 's/\\\\/\\\\\\\\/g' /tmp/cps_raw.json > /tmp/cps.json")
import_to_pg_box = SSHOperator(ssh_conn_id='ssh_prod_pg', command=download_cmd)

# 6. PostgreSQL: JSONB parse + enrich + atomic swap
import_to_pg_db = PostgresOperator(
    postgres_conn_id="prod_pg",
    sql="""
        -- Create temp table and COPY JSON
        CREATE TEMP TABLE mart_cps(data jsonb);
        COPY mart_cps from '/tmp/cps.json';

        -- Create new table matching production schema
        create table collection_post_metrics_summary_tmp (
            like collection_post_metrics_summary
            including defaults including constraints including indexes
        );

        -- Parse 35+ JSONB fields with type casting
        INSERT INTO collection_post_metrics_summary_tmp (...)
        select
            (data->>'platform') platform,
            coalesce((data->>'published_at')::timestamp, date('1970-01-01')) published_at,
            coalesce((data->>'followers')::int8, 0) followers,
            round(coalesce((data->>'views')::float8, 0.0)) views,
            (data->>'hashtags')::jsonb hashtags,
            ...
        from mart_cps;

        -- Enrich with profile pics and names from Instagram/YouTube
        update collection_post_metrics_summary_tmp
        set profile_pic = ia.thumbnail, followers = coalesce(ia.followers, 0)
        from instagram_account ia
        where ia.ig_id = profile_social_id;

        -- Enrich with collection share IDs
        update collection_post_metrics_summary_tmp
        set collection_share_id = pc.share_id
        from post_collection pc
        where pc.id = collection_id and collection_type = 'POST';

        -- Clean up invalid rows
        delete from collection_post_metrics_summary_tmp
        where collection_type = 'POST' and show_in_report = false;

        -- ATOMIC TABLE SWAP
        BEGIN;
            ALTER TABLE "collection_post_metrics_summary"
                RENAME TO "collection_post_metrics_summary_old_bkp";
            ALTER TABLE "collection_post_metrics_summary_tmp"
                RENAME TO "collection_post_metrics_summary";
        COMMIT;
    """,
)

# Pipeline chain
check_hour_task >> truncate_fake_ts >> create_ts >> fetch_from_ch
    >> import_to_pg_box >> import_to_pg_db
```

---

## 4. ClickHouse-Specific Features Used

### ReplacingMergeTree for Upserts
```sql
-- dbt materialization config
{{ config(
    materialized='incremental',
    engine='ReplacingMergeTree()',
    order_by='(profile_id, date)',
    incremental_strategy='append'
) }}
```

### argMax for Latest Value Extraction
```sql
-- Get the most recent value per profile (ClickHouse-native)
argMax(followers, updated_at) followers,
argMax(engagement_rate, updated_at) engagement_rate,
argMax(country, updated_at) country

-- Time-windowed latest value
argMaxIf(followers, date, date < toStartOfWeek(now()) - INTERVAL 30 DAY) followers_30d
```

### Partition Pruning and Memory Settings
```sql
SETTINGS max_bytes_before_external_group_by = 20000000000,
         max_bytes_before_external_sort = 20000000000,
         join_algorithm='partial_merge'
```

### Array Operations
```sql
-- Hashtag normalization
arrayMap(x -> lower(x), hashtags) hashtags
-- Keyword tokenization
splitByWhitespace(ifNull(concat(lower(name), ' ', lower(handle)), '')) keywords
-- City extraction from comma-separated string
splitByChar(',', city)[1] city
```

### S3 Integration
```sql
-- ClickHouse native S3 export
INSERT INTO FUNCTION s3(
    'https://gcc-social-data.s3.ap-south-1.amazonaws.com/data-pipeline/tmp/file.json',
    'AWS_KEY', 'AWS_SECRET', 'JSONEachRow'
)
SELECT * FROM dbt.mart_table
SETTINGS s3_truncate_on_insert=1;
```

---

## 5. Production Hardening Patterns

### ShortCircuit Operator (Conflict Avoidance)
```python
# Skip hourly/collection DAGs during the daily batch window (19:00-22:00 UTC)
def check_hour():
    hour = datetime.now().hour
    if 19 <= hour < 22:
        return False   # ShortCircuit skips all downstream tasks
    return True
```

### Slack Failure Notifications
```python
# dags/slack_connection.py (ACTUAL CODE)
class SlackNotifier(BaseNotifier):
    def slack_fail_alert(context):
        ti = context['ti']
        task_state = ti.state
        if task_state == 'success':
            return  # Skip success notifications
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

### Concurrency Controls
```python
# Every DAG enforces these patterns:
max_active_runs=1,    # No parallel DAG runs
concurrency=1,        # One task at a time within DAG
catchup=False,        # Don't backfill on schedule change
dagrun_timeout=dt.timedelta(minutes=X),  # Kill runaway jobs
```

---

## 6. Scrape Request Management (PythonOperator Pattern)

```python
# dags/sync_insta_collection_posts.py (ACTUAL CODE)
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

    # Fire scrape requests to Beat API
    for shortcode in posts.result_rows:
        data = {"flow": flow, "platform": "INSTAGRAM",
                "params": {"shortcode": shortcode[0]}}
        response = requests.post(url=url, data=json.dumps(data))
```

**Key patterns:**
1. **Exclude recent attempts** -- `now() - INTERVAL 12 HOUR` prevents re-scraping
2. **Exclude persistent failures** -- Posts that failed 2+ times with 0 successes
3. **Prioritize older posts** -- `ORDER BY publish_time ASC NULLS FIRST` (never-scraped first)
4. **Rate limiting** -- `LIMIT 250` per execution cycle
