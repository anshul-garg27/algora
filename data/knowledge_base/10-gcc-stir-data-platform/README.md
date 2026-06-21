# Stir Data Platform (Airflow + dbt) - Complete Interview Guide

> **Resume Bullet Covered:** Bullet 4 - "Crafted and streamlined ETL data pipelines (Apache Airflow) for batch data ingestion, cutting data latency by 50%"
> **Company:** Good Creator Co. (GCC) - SaaS platform for influencer marketing analytics
> **Repo:** `stir`

---

## Quick Navigation

| File | Purpose |
|------|---------|
| [01-technical-implementation.md](./01-technical-implementation.md) | Actual code: DAGs, dbt models, data flow patterns |
| [02-technical-decisions.md](./02-technical-decisions.md) | 10 "Why X not Y?" decisions with follow-ups |
| [03-interview-qa.md](./03-interview-qa.md) | Interview Q&A for data engineering & ETL |
| [04-how-to-speak.md](./04-how-to-speak.md) | Speaking guide with pitches and pyramid method |
| [05-scenario-questions.md](./05-scenario-questions.md) | 10 "What if?" failure scenarios |

---

## 30-Second Pitch

> "At Good Creator Co., I built Stir -- the data transformation and orchestration platform powering influencer marketing analytics. The core challenge was syncing analytics from ClickHouse (our OLAP engine) to PostgreSQL (serving the SaaS app) with minimal latency. I designed 76 Airflow DAGs orchestrating 112 dbt models through a three-layer pipeline: ClickHouse transforms data, exports to S3 as JSON staging, then atomic table swaps load it into PostgreSQL. Scheduling ranges from every 5 minutes for real-time scrape monitoring to weekly for aggregate leaderboards. This cut data latency by 50% and powers the discovery, leaderboard, and collection analytics for the platform."

---

## Key Numbers to Memorize

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

---

## Architecture Diagram

```
                         STIR DATA PLATFORM ARCHITECTURE

  DATA SOURCES                    ORCHESTRATION              SERVING LAYER
  ============                    =============              =============

  Instagram API  ──┐
  YouTube API    ──┤              ┌──────────────────────────────────────────┐
  Beat (Scraper) ──┤              │         APACHE AIRFLOW (76 DAGs)        │
  Coffee (SaaS)  ──┤──────────>   │                                          │
  Shopify        ──┤              │  ┌─────────────────────────────────────┐ │
  Vidooly        ──┘              │  │    dbt ORCHESTRATION (11 DAGs)      │ │
                                  │  │                                     │ │
                                  │  │  dbt_core      */15 min  tag:core   │ │
                                  │  │  dbt_recent_scl */5 min  tag:recent │ │
                                  │  │  dbt_hourly     every 2h tag:hourly │ │
                                  │  │  dbt_daily      19:00    tag:daily  │ │
                                  │  │  dbt_weekly     weekly   tag:weekly │ │
                                  │  │  dbt_collections */30    tag:coll   │ │
                                  │  │  post_ranker    */5 hr   tag:ranker │ │
                                  │  └─────────────────────────────────────┘ │
                                  └──────────────────────────────────────────┘
                                               │
                 ┌─────────────────────────────┼─────────────────────────────┐
                 │                             │                             │
                 ▼                             ▼                             ▼
  ┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
  │   LAYER 1: CLICKHOUSE│   │   LAYER 2: AWS S3    │   │ LAYER 3: POSTGRESQL  │
  │   (Analytics/OLAP)   │──>│   (JSON Staging)     │──>│   (Operational/OLTP) │
  │                      │   │                      │   │                      │
  │  29 staging models   │   │  gcc-social-data     │   │  beat database       │
  │  83 mart models      │   │  /data-pipeline/tmp/ │   │  Atomic table swap   │
  │  ReplacingMergeTree  │   │  JSONEachRow format  │   │  JSONB parsing       │
  │  argMax, partitions  │   │  s3_truncate=1       │   │  COPY + RENAME       │
  └──────────────────────┘   └──────────────────────┘   └──────────────────────┘
         │                                                        │
         │              ClickHouseOperator                        │
         │────────> INSERT INTO FUNCTION s3(...)                  │
         │              SSHOperator                               │
         │────────> aws s3 cp s3://... /tmp/                     │
         │              PostgresOperator                          │
         │────────> COPY + INSERT + BEGIN; RENAME; COMMIT; ──────│
                                                                  │
                                                                  ▼
                                                    ┌──────────────────────┐
                                                    │   GCC SaaS Platform  │
                                                    │   (Coffee API)       │
                                                    │                      │
                                                    │  Discovery           │
                                                    │  Leaderboards        │
                                                    │  Collections         │
                                                    │  Campaign Analytics  │
                                                    └──────────────────────┘
```

---

## Technology Stack

| Category | Technology | Purpose |
|----------|-----------|---------|
| Orchestration | Apache Airflow 2.6.3 | Workflow scheduling & monitoring |
| Transformation | dbt-core 1.3.1 | SQL-based ELT transformations |
| Analytics DB | ClickHouse (dbt-clickhouse 1.3.2) | OLAP engine, real-time analytics |
| Operational DB | PostgreSQL (psycopg2 2.9.5) | SaaS application serving |
| Cloud Storage | AWS S3 (gcc-social-data) | JSON staging between databases |
| CI/CD | GitLab CI | Manual production deploys |
| Monitoring | Slack (slack-sdk 3.21.3) | Failure/success notifications |
| SSH Transfer | Paramiko | File download to PostgreSQL host |

---

## DAG Categories (76 Total)

| Category | Count | Examples |
|----------|-------|---------|
| dbt Orchestration | 11 | dbt_core, dbt_daily, dbt_collections |
| Instagram Sync | 17 | sync_insta_collection_posts, sync_insta_profile_insights |
| YouTube Sync | 12 | sync_yt_channels, sync_yt_critical_daily |
| Collection/Leaderboard Sync | 15 | sync_leaderboard_prod, sync_time_series_prod |
| Operational/Verification | 9 | sync_missing_journey, sync_group_metrics_prod |
| Asset Upload | 7 | upload_post_asset, upload_content_verification |
| Utility | 5 | crm_recommendation_invitation, track_hashtags |

---

## dbt Model Architecture (112 Total)

| Layer | Count | Domains |
|-------|-------|---------|
| **Staging** | 29 | beat (14 models), coffee (15 models) |
| **Marts** | 83 | discovery (16), leaderboard (14), collection (12), profile_stats (8), profile_stats_partial (6), genre (7), audience (4), posts (3), staging_collection (9), orders (1), data_request (3) |
