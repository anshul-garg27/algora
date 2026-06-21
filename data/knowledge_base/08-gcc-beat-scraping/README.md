# Beat - Social Media Scraping Engine (GCC) - Interview Guide

> **Resume Bullets Covered:** 1, 2, 5
> **Company:** Good Creator Co. (GCC) - SaaS platform for influencer marketing analytics
> **Repo:** `beat` (private GitLab)

---

## Quick Navigation

| File | Purpose |
|------|---------|
| [01-technical-implementation.md](./01-technical-implementation.md) | Actual code snippets from the repo with architecture walkthrough |
| [02-technical-decisions.md](./02-technical-decisions.md) | 10 "Why X not Y?" decisions with follow-ups |
| [03-interview-qa.md](./03-interview-qa.md) | Q&A pairs for hiring manager + googleyness rounds |
| [04-how-to-speak.md](./04-how-to-speak.md) | 30-sec/60-sec pitches, STAR stories, pivot phrases |
| [05-scenario-questions.md](./05-scenario-questions.md) | 10 "What if X fails?" with DETECT/IMPACT/MITIGATE/RECOVER/PREVENT |

---

## Resume Bullet Mapping

| Bullet # | Resume Text | Beat Evidence |
|----------|------------|---------------|
| **1** | "Optimized API response times by 25% and reduced operational costs by 30%" | 3-level stacked rate limiting (daily/minute/handle), connection pooling via asyncpg, credential rotation with TTL backoff |
| **2** | "Designed an asynchronous data processing system handling 10M+ daily data points" | Worker pool: multiprocessing + asyncio + semaphore, 73 flows, 150+ concurrent workers, FOR UPDATE SKIP LOCKED task queue |
| **5** | "Built an AWS S3-based asset upload system processing 8M images daily" | `main_assets.py` - dedicated 50-worker pool, aioboto3 S3 uploads, CloudFront CDN delivery |

---

## 30-Second Pitch

> "At Good Creator Co., I built Beat -- the core data collection engine for our influencer marketing SaaS platform. It aggregates data from 15+ social media APIs -- Instagram, YouTube, Shopify -- using 150+ concurrent workers across 73 scraping flows. The key engineering challenge was reliability at scale: I designed a 3-level stacked rate limiting system, credential rotation with TTL backoff, and a SQL-based task queue with FOR UPDATE SKIP LOCKED for distributed coordination. The system processes 10 million data points daily and uploads 8 million images through an S3 pipeline."

---

## Key Numbers to Memorize

| Metric | Value |
|--------|-------|
| Lines of Python | **15,000+** |
| Scraping flows | **75+** (73 in worker pool config) |
| Concurrent workers | **150+** |
| API integrations | **15+** (6 Instagram, 4 YouTube, GPT, Shopify, S3, RabbitMQ, Identity) |
| Dependencies | **128** |
| Rate limit levels | **3** (daily, per-minute, per-handle) |
| Images processed/day | **8M** |
| Data points/day | **10M+** |
| AMQP listeners | **5** |
| Database tables | **30+** |
| GPT prompt versions | **13** |
| Asset upload workers | **50** (dedicated pool) |

---

## Architecture Diagram

```
                           BEAT SERVICE ARCHITECTURE
                           ========================

  +-----------+    +----------------+    +------------------+
  | server.py |    |   main.py      |    |  main_assets.py  |
  | FastAPI   |    |  Worker Pool   |    |  Asset Workers   |
  | Port 8000 |    |  73 Flows      |    |  50 Workers      |
  | REST API  |    |  Multiprocess  |    |  S3/CDN Upload   |
  +-----+-----+    +-------+--------+    +--------+---------+
        |                   |                      |
        v                   v                      v
  +-----------------------------------------------------------+
  |                   WORKER POOL SYSTEM                       |
  |  Per-flow workers x per-worker concurrency (semaphore)     |
  |  refresh_profile_by_handle: 10 workers x 5 concurrency    |
  |  refresh_yt_profiles:       10 workers x 5 concurrency    |
  |  asset_upload_flow:         15 workers x 5 concurrency    |
  |  ... 70+ more flows                                        |
  +----------------------------+------------------------------+
                               |
                               v
  +-----------------------------------------------------------+
  |                   RATE LIMITING LAYER                       |
  |  Level 1: Daily global    - 20,000 req / 86400s           |
  |  Level 2: Per-minute      - 60 req / 60s                  |
  |  Level 3: Per-handle      - 1 req / 1s                    |
  |  Source-specific: youtube138=850/60s, arraybobo=100/30s    |
  +----------------------------+------------------------------+
                               |
                               v
  +-----------------------------------------------------------+
  |               API INTEGRATIONS (15+ APIs)                  |
  |  INSTAGRAM (8)           YOUTUBE (4)        OTHER          |
  |  - GraphAPI v15          - YT Data API v3   - OpenAI GPT   |
  |  - RapidAPI ArrayBobo    - YT v31           - Shopify API  |
  |  - RapidAPI JoTucker     - YT v311          - Identity Svc |
  |  - RapidAPI NeoTank      - YT Search        - S3/CloudFront|
  |  - RapidAPI BestSolns                                      |
  |  - RapidAPI IGApi                                          |
  |  - RocketAPI                                               |
  |  - Lama (fallback)                                         |
  +----------------------------+------------------------------+
                               |
                               v
  +-----------------------------------------------------------+
  |              MESSAGE QUEUE (RabbitMQ/AMQP)                 |
  |  credentials_validate  | beat.dx  | 5 workers             |
  |  identity_token        | identity.dx | 5 workers          |
  |  keyword_collection    | beat.dx  | 5 workers             |
  |  sentiment_analysis    | beat.dx  | 5 workers             |
  |  sentiment_report      | beat.dx  | 5 workers             |
  +----------------------------+------------------------------+
                               |
                               v
  +-----------------------------------------------------------+
  |                   DATA LAYER                               |
  |  PostgreSQL (async)    Redis Cluster      S3/CloudFront   |
  |  - instagram_account   - Rate limit state - Media assets   |
  |  - instagram_post      - Cache layer      - CDN delivery   |
  |  - youtube_account     - Session data                      |
  |  - scrape_request_log                                      |
  |  - credential                                              |
  |  - profile_log (audit)                                     |
  |  - asset_log                                               |
  +-----------------------------------------------------------+
```

---

## Data Flow Pipeline

```
  API Request / Task Queue Pickup
         |
         v
  STAGE 1: RETRIEVAL  (instagram/tasks/retrieval.py)
    InstagramCrawler -> select provider -> API call -> raw dict
         |
         v
  STAGE 2: PARSING    (instagram/tasks/ingestion.py)
    Raw dict -> InstagramProfileLog / InstagramPostLog
    Extract dimensions: [{key, value}], metrics: [{key, value}]
         |
         v
  STAGE 3: PROCESSING (instagram/tasks/processing.py)
    Log -> ORM entity (InstagramAccount/InstagramPost)
    Upsert to PostgreSQL + Publish event to AMQP
```

---

## Top 5 Interview Questions (Quick Answers)

### 1. "Walk me through the architecture"
> Use the 60-second pitch in [04-how-to-speak.md](./04-how-to-speak.md)

### 2. "Why SQL task queue instead of Redis or RabbitMQ?"
> FOR UPDATE SKIP LOCKED gives us distributed locking + persistence + priority ordering in one SQL query. No extra infrastructure needed. See [02-technical-decisions.md](./02-technical-decisions.md)

### 3. "How do you handle rate limits from 15+ APIs?"
> 3-level stacked limiting plus source-specific rate specs. Credential rotation with TTL backoff when tokens get rate-limited. See [01-technical-implementation.md](./01-technical-implementation.md)

### 4. "What happens when an API provider goes down?"
> Fallback chain. Each function type has ordered providers. If GraphAPI fails, we try ArrayBobo, then JoTucker, then Lama. See [05-scenario-questions.md](./05-scenario-questions.md)

### 5. "Tell me about a complex system you built"
> Use the STAR story in [04-how-to-speak.md](./04-how-to-speak.md) - "Scraping at Scale"
