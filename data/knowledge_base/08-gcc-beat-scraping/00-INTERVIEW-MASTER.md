# Beat - Social Media Scraping Engine | Interview Master Document

> **Company:** Good Creator Co. (GCC) -- SaaS platform for influencer marketing analytics
> **Project:** Beat -- core data collection engine (private GitLab repo)
> **Role:** Sole architect and primary developer (team of 3-4; I owned Beat end-to-end)
> **Stack:** Python 3.11 / FastAPI / asyncio + uvloop / PostgreSQL / Redis / RabbitMQ / AWS S3 + CloudFront

---

## Resume Bullets Covered

| Bullet | Resume Text | Beat Evidence |
|--------|------------|---------------|
| **1** | "Optimized API response times by 25% and reduced operational costs by 30%" | 3-level stacked rate limiting (daily/minute/handle), connection pooling via asyncpg, credential rotation with TTL backoff |
| **2** | "Designed an asynchronous data processing system handling 10M+ daily data points" | Worker pool: multiprocessing + asyncio + semaphore, 73 flows, 150+ concurrent workers, FOR UPDATE SKIP LOCKED task queue |
| **5** | "Built an AWS S3-based asset upload system processing 8M images daily" | `main_assets.py` -- dedicated 50-worker pool, aioboto3 S3 uploads, CloudFront CDN delivery |

---

## 1. Pitches

### 30-Second Pitch

> "At Good Creator Co., I built Beat -- the core data collection engine for our influencer marketing SaaS platform. It aggregates data from 15+ social media APIs -- Instagram, YouTube, Shopify -- using 150+ concurrent workers across 73 scraping flows. The key engineering challenge was reliability at scale: I designed a 3-level stacked rate limiting system, credential rotation with TTL backoff, and a SQL-based task queue with FOR UPDATE SKIP LOCKED. The system processes 10 million data points daily and uploads 8 million images through an S3 pipeline."

**Delivery notes:**
- Say "Good Creator Co." not "GCC" -- the interviewer does not know the acronym
- Pause after "15+ social media APIs" to let the scope register
- Emphasize "FOR UPDATE SKIP LOCKED" clearly -- it shows PostgreSQL depth
- End with concrete numbers: 10M data points, 8M images

### 60-Second Pitch

> "Beat is a Python service built on FastAPI and asyncio that scrapes Instagram, YouTube, and Shopify data for enterprise-scale analytics.
>
> The architecture has three entry points: a FastAPI REST API for on-demand requests, a worker pool for batch processing, and a dedicated asset upload pipeline for media.
>
> The worker pool is where most of the complexity lives. It uses multiprocessing for CPU isolation -- each of 73 flows gets dedicated OS processes. Within each process, asyncio with uvloop handles concurrent I/O. A semaphore controls how many tasks run simultaneously per worker. Tasks are picked from PostgreSQL using FOR UPDATE SKIP LOCKED, which gives us atomic distributed coordination without external infrastructure.
>
> For external API calls, I built a 3-level stacked rate limiting system backed by Redis. The crawler uses the Strategy pattern with 8 Instagram providers and 4 YouTube providers. When a provider's credential gets rate-limited, the system marks it disabled with a TTL and falls back to the next available provider.
>
> Every data change publishes an event to RabbitMQ for downstream consumption by the dashboard, notification service, and analytics pipeline."

**Delivery notes:**
- Start with the "what" (Beat, Python, FastAPI), then go to "how" (architecture)
- Use the three entry points as your mental framework
- When you say "Strategy pattern with 8 providers," they will ask a follow-up -- that is good
- End with the event-driven architecture -- it shows you think about system boundaries

---

## 2. Key Numbers

| Metric | Value |
|--------|-------|
| Lines of Python | **15,000+** |
| Scraping flows | **75+** (73 in worker pool config) |
| Concurrent workers | **150+** |
| API integrations | **15+** (8 Instagram, 4 YouTube, GPT, Shopify, S3, RabbitMQ, Identity) |
| Dependencies | **128** |
| Rate limit levels | **3** (daily, per-minute, per-handle) |
| Images processed/day | **8M** |
| Data points/day | **10M+** |
| AMQP listeners | **5** |
| Database tables | **30+** |
| GPT prompt versions | **13** |
| Asset upload workers | **50** (dedicated pool) |

**Weave numbers naturally into answers:**
- "...with **150+ concurrent workers** across **73 flows**..."
- "...the system handles **10 million data points daily**..."
- "...uploads **8 million images** through S3..."
- "...across **15+ API integrations** -- 8 for Instagram alone..."
- "...the codebase is about **15,000 lines** of Python with **128 dependencies**..."

---

## 3. Architecture

### Service Architecture Diagram

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

### Data Flow Pipeline

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

## 4. Technical Implementation

### 4.1 Worker Pool System (main.py)

The core of Beat: multiprocessing for CPU isolation + asyncio for I/O concurrency + semaphore for per-worker throttling.

#### Flow Configuration -- 73 Flows

```python
# main.py - The whitelist defines every scraping flow with its resource allocation
_whitelist = {
    # Instagram Profile Flows
    'refresh_profile_custom': {'no_of_workers': 1, 'no_of_concurrency': 2},
    'refresh_profile_by_handle': {'no_of_workers': 10, 'no_of_concurrency': 5},
    'refresh_profile_basic': {'no_of_workers': 5, 'no_of_concurrency': 5},
    'refresh_profile_by_profile_id': {'no_of_workers': 1, 'no_of_concurrency': 5},

    # Instagram Post Flows
    'refresh_post_by_shortcode': {'no_of_workers': 1, 'no_of_concurrency': 5},
    'refresh_post_insights': {'no_of_workers': 1, 'no_of_concurrency': 5},
    'refresh_stories_posts': {'no_of_workers': 1, 'no_of_concurrency': 5},
    'refresh_story_insights': {'no_of_workers': 1, 'no_of_concurrency': 5},

    # YouTube Flows
    'refresh_yt_profiles': {'no_of_workers': 10, 'no_of_concurrency': 5},
    'refresh_yt_posts': {'no_of_workers': 1, 'no_of_concurrency': 5},
    'refresh_yt_posts_by_channel_id': {'no_of_workers': 5, 'no_of_concurrency': 5},

    # GPT Enrichment Flows
    'refresh_instagram_gpt_data_base_gender': {'no_of_workers': 3, 'no_of_concurrency': 5},
    'refresh_instagram_gpt_data_base_location': {'no_of_workers': 3, 'no_of_concurrency': 5},
    'refresh_instagram_gpt_data_audience_age_gender': {'no_of_workers': 3, 'no_of_concurrency': 5},

    # Asset Upload
    'asset_upload_flow': {'no_of_workers': 15, 'no_of_concurrency': 5},
    'asset_upload_flow_stories': {'no_of_workers': 3, 'no_of_concurrency': 5},

    # YouTube CSV Export Flows
    'fetch_channels_csv': {'no_of_workers': 1, 'no_of_concurrency': 5},
    'fetch_channel_videos_csv': {'no_of_workers': 1, 'no_of_concurrency': 5},
    'fetch_channel_demographic_csv': {'no_of_workers': 1, 'no_of_concurrency': 5},

    # Shopify
    'refresh_orders_by_store': {'no_of_workers': 1, 'no_of_concurrency': 5},
    # ... 50+ more flows
}
```

#### Process Spawning -- Multiprocessing + uvloop

```python
# main.py - Each flow gets dedicated OS processes with independent event loops
def start_scrape_log_workers(workers: list) -> None:
    single_worker = bool(int(os.environ["SINGLE_WORKER"]))
    if single_worker:
        max_conc = int(os.environ["SCRAPE_LOG_MAX_CONCURRENCY_PER_LOOP"])
        limit = asyncio.Semaphore(max_conc)
        looper(1, limit, list(_whitelist.keys()), max_conc)
    else:
        for flow in _whitelist:
            num_process = _whitelist[flow]['no_of_workers']
            for i in range(num_process):
                max_conc = int(_whitelist[flow]['no_of_concurrency'])
                limit = asyncio.Semaphore(max_conc)
                w = multiprocessing.Process(
                    target=looper,
                    args=(i + 1, limit, [flow], max_conc)
                )
                w.start()
                workers.append(w)
```

**Key insight**: Each worker process creates its own uvloop event loop. The GIL never blocks across flows -- Instagram scraping never slows down YouTube scraping.

#### Event Loop with uvloop

```python
# main.py - High-performance event loop replacement
def looper(id: int, limit: Semaphore, flows: list, max_conc=5) -> None:
    while True:
        try:
            with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
                runner.run(poller(id, limit, flows, max_conc))
        except Exception as e:
            logger.error(f"Error: {e}")
            msg = traceback.format_exc()
            logger.error(f"Error Message - {msg}")
```

#### Async Poller with Semaphore Backpressure

```python
# main.py - The core polling loop
async def poller(id: int, limit: Semaphore, flows: list, max_conc=5) -> None:
    logger.debug("Starting Worker")
    engine = create_async_engine(
        os.environ["PG_URL"],
        isolation_level="AUTOCOMMIT",
        echo=False,
        pool_size=max_conc,
        max_overflow=5
    )
    conn = await engine.connect()
    while True:
        await poll(id, limit, flows, conn, engine)
        await asyncio.sleep(1)
```

#### Task Execution with Semaphore and Timeout

```python
# main.py - Task execution with concurrency control
@sessionize
async def perform_task(con: AsyncConnection, row: any, limit: Semaphore,
                       session=None, session_engine=None) -> None:
    logger.debug(f"TASK-{row.id}::Acquiring Locks")
    await limit.acquire()
    logger.debug(f"TASK-{row.id}::Starting Execution")
    body = ScrapeRequest(
        flow=row.flow, platform=row.platform,
        params=row.params, retry_count=row.retry_count, priority=1
    )
    now = datetime.datetime.now()
    body.status = "PROCESSING"
    body.event_timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    await make_scrape_request_log_event(str(row.id), body)

    try:
        data = await execute(row, session=session)
        statement = text("""
            update scrape_request_log
                set status='COMPLETE', scraped_at=now(), data=:data
                where id = %s
        """ % row.id)
        await con.execute(statement, parameters={'data': str(data)})
        body.status = "COMPLETE"
        await make_scrape_request_log_event(str(row.id), body)
    except Exception as e:
        error = f"{str(e)}"
        statement = text("""
            update scrape_request_log
                set status='FAILED', scraped_at=now(), data=:data
                where id = :id
        """)
        await con.execute(statement, parameters={'data': error, 'id': row.id})
        body.status = "FAILED"
        await make_scrape_request_log_event(str(row.id), body)
    finally:
        limit.release()
```

#### Long-Running Task Cancellation (10-minute timeout)

```python
# main.py - Probabilistic cleanup of stuck tasks
async def check_and_cancel_long_running_tasks(background_tasks: set):
    current_time = time.time()
    task_timeout = 60 * 10 * 1000  # 10 minutes in ms
    canceled_tasks = 0
    completed_tasks = 0
    for start_time, task in background_tasks:
        if task.done():
            background_tasks.remove((start_time, task))
            completed_tasks += 1
        elif current_time - start_time > task_timeout:
            task.cancel()
            background_tasks.remove((start_time, task))
            canceled_tasks += 1
    logger.debug(f"Completed {completed_tasks} tasks. Cancelled {canceled_tasks} tasks.")
```

### 4.2 SQL-Based Task Queue with FOR UPDATE SKIP LOCKED

```python
# main.py - The heart of distributed task coordination
async def poll(id: int, limit: Semaphore, flows: list,
               conn: AsyncConnection, engine) -> None:
    background_tasks = set()
    while limit.locked():
        logger.debug("Workers are busy, will try again in a bit.")
        await asyncio.sleep(30)
    for flow in flows:
        values = {'flow': flow}
        statement = text("""
            update scrape_request_log
                set status='PROCESSING'
                where id IN (
                    select id from scrape_request_log e
                    where status = 'PENDING' and
                    flow = :flow
                    for update skip locked
                    limit 1)
            RETURNING *
        """)
        rs = await conn.execute(statement, values)
        for row in rs:
            logger.debug(str(id) + ": Found Work - " + str(row.id))
            task = asyncio.create_task(
                perform_task(conn, row, limit, session_engine=engine)
            )
            background_tasks.add((int(time.time() * 1000), task))
        # Probabilistic cleanup: ~1% chance per poll cycle
        if randint(0, 1000) < 10:
            await check_and_cancel_long_running_tasks(background_tasks)
```

**Why FOR UPDATE SKIP LOCKED matters**: It atomically (1) selects the next pending task, (2) locks it so no other worker can pick it, (3) skips already-locked rows without blocking, (4) updates status to PROCESSING, and (5) returns the row -- all in one query.

### 4.3 Three-Level Stacked Rate Limiting

#### Server-Side: Stacked Redis Limiters (server.py)

```python
# server.py - 3 nested rate limiters for API endpoints
@app.get("/profiles/{platform}/byhandle/{handle}")
@sessionize_api
async def get_profile_details_for_handle(request: Request, platform: enums.Platform,
                                         handle: str, full_refresh=False,
                                         force_refresh=False, session=None) -> dict:
    if platform == enums.Platform.INSTAGRAM:
        profile = await get(session, InstagramAccount, handle=handle)
        if force_refresh or not profile or profile.updated_at < datetime.now() - timedelta(days=1):
            try:
                redis = AsyncRedis.from_url(os.environ["REDIS_URL"])

                # Level 1: Daily global limit
                global_limit_day = RateSpec(requests=20000, seconds=86400)
                # Level 2: Per-minute global limit
                global_limit_minute = RateSpec(requests=60, seconds=60)
                # Level 3: Per-handle limit
                handle_limit = RateSpec(requests=1, seconds=1)

                async with RateLimiter(
                        unique_key="refresh_profile_insta_daily",
                        backend=redis, cache_prefix="beat_server_",
                        rate_spec=global_limit_day):
                    async with RateLimiter(
                            unique_key="refresh_profile_insta_per_minute",
                            backend=redis, cache_prefix="beat_server_",
                            rate_spec=global_limit_minute):
                        async with RateLimiter(
                                unique_key="refresh_profile_insta_per_handle_" + handle,
                                backend=redis, cache_prefix="beat_server_",
                                rate_spec=handle_limit):
                            await refresh_profile(None, handle, session=session)
            except RateLimitError as e:
                return error("Concurrency Limit Exceeded", 2)
```

#### Worker-Side: Source-Specific Rate Specs (utils/request.py)

```python
# utils/request.py - Per-API-provider rate limiting
source_specs = {
    'youtube138':               RateSpec(requests=850, seconds=60),
    'insta-best-performance':   RateSpec(requests=2, seconds=1),
    'instagram-scraper2':       RateSpec(requests=5, seconds=1),
    'instagram-scraper-2022':   RateSpec(requests=100, seconds=30),
    'youtubev31':               RateSpec(requests=500, seconds=60),
    'youtubev311':              RateSpec(requests=3, seconds=1),
    'rocketapi':                RateSpec(requests=100, seconds=30),
}

async def make_request(method: str, url: str, **kwargs: any) -> any:
    if 'instagram-api-cheap-best-performance.p.rapidapi.com' in url:
        return await make_request_limited('insta-best-performance', method, url, **kwargs)
    elif 'youtube138.p.rapidapi.com' in url:
        return await make_request_limited('youtube138', method, url, **kwargs)
    elif 'instagram-scraper-2022' in url:
        return await make_request_limited('instagram-scraper-2022', method, url, **kwargs)
    # ... more providers
    resp = await asks.request(method, url, **kwargs)
    return resp

async def make_request_limited(source, method: str, url: str, **kwargs) -> any:
    redis = AsyncRedis.from_url(os.environ["REDIS_URL"])
    while True:
        try:
            async with RateLimiter(
                    unique_key=source, backend=redis,
                    cache_prefix="beat_", rate_spec=source_specs[source]):
                start_time = time.perf_counter()
                resp = await asks.request(method, url, **kwargs)
                end_time = time.perf_counter()
                await emit_trace_log_event(method, url, resp, end_time - start_time, kwargs)
                return resp
        except RateLimitError as e:
            await asyncio.sleep(1)  # Back off and retry
```

### 4.4 Credential Rotation with TTL Backoff

#### Credential Entity

```python
# core/entities/entities.py - Credential storage with TTL disable
class Credential(Base):
    __tablename__ = 'credential'

    id = Column(BigInteger, primary_key=True)
    idempotency_key = Column(String, unique=True)
    source = Column(String)          # graphapi, rapidapi-jotucker, etc.
    handle = Column(String)
    credentials = Column(JSONB)      # {token, user_id, key, ...}
    created_at = Column(TIMESTAMP)
    updated_at = Column(TIMESTAMP)
    disabled_till = Column(TIMESTAMP) # TTL: re-enable after this time
    enabled = Column(Boolean)
    data_access_expired = Column(Boolean)
```

#### Credential Selection with Fallback Chain

```python
# core/crawler/crawler.py - Base crawler with provider fallback chain
class Crawler:

    @sessionize
    async def fetch_enabled_sources(self, fetch_type: str, exclusions: list = None,
                                     session=None, pagination: PaginationContext = None):
        if not exclusions:
            exclusions = []
        if pagination and pagination.source is not None:
            # Sticky source for paginated requests
            source_cred = await CredentialManager.get_enabled_cred(
                str(pagination.source), session=session)
            if source_cred:
                return source_cred
        else:
            if fetch_type in ["fetch_followers"]:
                # Weighted random selection for follower fetching
                weights = {"rapidapi-jotucker": 0.3, "rocketapi": 0.7}
                source = random.choices(
                    list(weights.keys()),
                    weights=list(weights.values()), k=1
                )[0]
                source_cred = await CredentialManager.get_enabled_cred(
                    source, session=session)
                if source_cred:
                    return source_cred
            else:
                # Priority-ordered fallback: try each source in order
                for source in self.available_sources[fetch_type]:
                    if source in exclusions:
                        continue
                    source_cred = await CredentialManager.get_enabled_cred(
                        source, session=session)
                    if source_cred:
                        return source_cred
        return None
```

### 4.5 Asset Upload Pipeline (main_assets.py)

#### Dedicated Asset Worker Pool

```python
# main_assets.py - Separate process pool for media uploads
_whitelist = {
    'asset_upload_flow': {'no_of_workers': 50, 'no_of_concurrency': 100},
}

# Uses PGBOUNCER_URL for connection pooling at this scale
async def poller(id: int, limit: Semaphore, flows: list) -> None:
    engine = create_async_engine(
        os.environ["PGBOUNCER_URL"],
        isolation_level="AUTOCOMMIT",
        echo=False,
        pool_size=100,
        max_overflow=5,
        pool_recycle=500
    )
    while True:
        await poll(id, limit, flows, engine)
        await asyncio.sleep(1)
```

#### S3 Upload with CDN Delivery

```python
# core/client/upload_assets.py - S3 upload with CloudFront CDN
async def put(entity_id: str, entity_type: str, platform: str,
              profile_url: str, extension: str) -> str:
    response = await asks.get(profile_url)
    if response.text == "URL signature expired":
        raise UrlSignatureExpiredError("URL signature expired")

    session = aioboto3.Session(region_name='ap-south-1')
    content_type = ""
    if extension in ("jpg", "png", "webp"):
        content_type = "image/" + extension
    elif extension == "mp4":
        content_type = "video/mp4"

    blob_s3_key = f"assets/{entity_type.lower()}s/{platform.lower()}/{entity_id}.{extension}"
    async with session.client('s3') as s3:
        bucket = os.environ["AWS_BUCKET"]
        await s3.put_object(
            Body=response.content, Bucket=bucket, Key=blob_s3_key,
            ContentType=content_type, ContentDisposition='inline'
        )
        return blob_s3_key

async def asset_upload_flow(entity_type: str, entity_id: str, asset_type: str,
                            original_url: str, platform: str, hash: str,
                            session=None):
    extension = ""
    if asset_type.upper() == "IMAGE":
        if "jpg" in original_url or "jpeg" in original_url:
            extension = "jpg"
        elif "webp" in original_url:
            extension = "webp"
        else:
            extension = "png"
    elif asset_type.upper() == "VIDEO":
        extension = "mp4"

    asset_url = await put(entity_id, entity_type, platform, original_url, extension)
    query_string = {
        'entity_type': entity_type, 'entity_id': entity_id,
        'platform': platform, 'asset_type': asset_type,
        'asset_url': asset_url, 'original_url': original_url,
        'updated_at': datetime.now()
    }
    await upsert_save_profile_url(query_string, session=session)
```

### 4.6 Instagram Crawler Interface with 8 Providers

#### Strategy Pattern Interface

```python
# instagram/functions/retriever/interface.py
class InstagramCrawlerInterface:

    @staticmethod
    async def fetch_profile_by_id(ctx: RequestContext, profile_id: str) -> dict:
        pass

    @staticmethod
    async def fetch_profile_by_handle(ctx: RequestContext, handle: str) -> (dict, str):
        pass

    @staticmethod
    async def fetch_profile_posts_by_id(ctx: RequestContext, profile_id: str,
                                         cursor: str = None) -> (dict, bool, str):
        pass

    @staticmethod
    async def fetch_post_by_shortcode(ctx: RequestContext, shortcode: str) -> dict:
        pass

    @staticmethod
    async def fetch_reels_posts(ctx: RequestContext, profile_id: str) -> (list, bool, str):
        pass

    @staticmethod
    async def fetch_followers(ctx: RequestContext, profile_id: str,
                               cursor: str = None) -> (list, bool, str):
        pass

    @staticmethod
    def parse_profile_data(resp_dict: dict) -> InstagramProfileLog:
        pass

    @staticmethod
    def parse_profile_post_data(resp_dict: dict) -> List[InstagramPostLog]:
        pass
    # ... 10+ more methods
```

#### Concrete Crawler with Provider Registry

```python
# instagram/functions/retriever/crawler.py
class InstagramCrawler(Crawler):

    def __init__(self) -> None:
        # Available sources per function type (priority ordered)
        self.available_sources = {
            'fetch_profile_by_id': ['rapidapi-jotucker', 'rapidapi-arraybobo'],
            'fetch_profile_by_handle': ['graphapi', 'rapidapi-arraybobo',
                                         'rapidapi-jotucker', 'lama',
                                         'rapidapi-bestsolutions'],
            'fetch_profile_posts_by_id': ['rapidapi-jotucker', 'lama',
                                           'rapidapi-arraybobo'],
            'fetch_reels_posts': ['rapidapi-arraybobo', 'rocketapi'],
            'fetch_post_by_shortcode': ['rapidapi-arraybobo', 'rapidapi-jotucker',
                                         'rocketapi', 'lama'],
            'fetch_post_insights': ['graphapi'],
            'fetch_followers': ['rapidapi-jotucker', 'rocketapi'],
            'fetch_following': ['rapidapi-jotucker', 'lama'],
            'fetch_story_posts_by_profile_id': ['rapidapi-arraybobo', 'rocketapi', 'lama'],
        }

        # Provider class registry
        self.providers = {
            'rapidapi-arraybobo': ArrayBobo,
            'rapidapi-neotank': NeoTank,
            'rapidapi-jotucker': JoTucker,
            'graphapi': GraphApi,
            'rapidapi-igapi': IGApi,
            'lama': Lama,
            'rapidapi-bestsolutions': BestSolutions,
            'rocketapi': RocketApi
        }

    @sessionize
    async def fetch_profile_by_handle(self, handle: str, session=None):
        creds = await self.fetch_enabled_sources(
            'fetch_profile_by_handle', session=session)
        if not creds:
            raise NoAvailableSources("No source is available at the moment")
        provider = self.providers[creds.source]
        try:
            return await provider.fetch_profile_by_handle(
                RequestContext(creds), handle), creds.source
        except Exception as e:
            # GraphAPI fallback: if primary fails, try secondary providers
            if creds.source == "graphapi":
                creds = await self.fetch_enabled_sources(
                    'fetch_profile_by_handle',
                    exclusions=["graphapi"], session=session)
                if not creds:
                    raise NoAvailableSources("No source is available")
                provider = self.providers[creds.source]
                return await provider.fetch_profile_by_handle(
                    RequestContext(creds), handle), creds.source
```

### 4.7 AMQP/RabbitMQ Event Publishing

```python
# core/amqp/models.py
@dataclass
class AmqpListener:
    exchange: str
    exchange_type: str
    routingKey: str
    queue: str
    workers: int
    prefetch_count: int
    fn: Callable

# core/amqp/amqp.py - aio-pika async consumer with session management
async def async_listener(config):
    engine = SessionFactory().get_engine()
    connection = await aio_pika.connect_robust(os.environ["RMQ_URL"])
    queue_name = config.queue
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=config.prefetch_count)
        queue = await channel.declare_queue(queue_name, durable=True)
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    session = get_session_for_engine(engine)
                    try:
                        await config.fn(session, message.body, message)
                        await session.commit()
                        await session.close()
                    except Exception as e:
                        logger.error(traceback.format_exc())
                        await session.rollback()
                        await session.close()

# Synchronous publish via kombu
def publish(payload: dict, exchange: str, routing_key: str) -> None:
    with Connection(os.environ["RMQ_URL"]) as conn:
        producer = conn.Producer(serializer='json')
        producer.publish(payload, exchange=exchange, routing_key=routing_key)
```

#### Configured AMQP Listeners (main.py)

```python
# main.py - 5 AMQP listeners, each with 5 worker processes
amqp_listeners = [
    AmqpListener("beat.dx", "direct", "credentials_validate",
                 "credentials_validate_q", 5, 10, credential_validate),
    AmqpListener("identity.dx", "direct", "new_access_token_rk",
                 "identity_token_q", 5, 10, upsert_credential_from_identity),
    AmqpListener("beat.dx", "direct", "keyword_collection_rk",
                 "keyword_collection_q", 5, 1, fetch_keyword_collection),
    AmqpListener("beat.dx", "direct", "post_activity_log_bulk",
                 "sentiment_analysis_q", 5, 1, sentiment_extraction),
    AmqpListener("beat.dx", "direct", "sentiment_collection_report_in_rk",
                 "sentiment_collection_report_in_q", 5, 1, fetch_sentiment_report),
]
```

### 4.8 Session Management with @sessionize Decorator

```python
# core/helpers/session.py - Automatic session lifecycle management
def sessionize(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        if not kwargs:
            kwargs = {}
        if 'session' not in kwargs or not kwargs['session']:
            if 'session_engine' in kwargs and kwargs['session_engine']:
                session_engine = kwargs['session_engine']
            else:
                session_engine = SessionFactory().get_engine()
            session: AsyncSession = get_session_for_engine(session_engine)
            kwargs['session'] = session
            try:
                func_res = await func(*args, **kwargs)
                await session.commit()
                await session.close()
                return func_res
            except Exception as e:
                await session.rollback()
                await session.close()
                raise e
        else:
            # Session propagation: reuse upstream session
            return await func(*args, **kwargs)
    return wrapper
```

**Key insight**: This decorator enables session propagation. When `refresh_profile` calls `upsert_profile` which calls `upsert_insta_post`, the same session is passed through. When called standalone, it creates and manages its own session with proper commit/rollback.

### 4.9 GPT Enrichment Flows

```python
# gpt/flows/fetch_gpt_data.py - GPT enrichment with retry logic
@sessionize
async def fetch_instagram_gpt_data_base_gender(data: dict, session=None):
    max_retries = 2
    base_data = await retrieve_instagram_gpt_data_base_gender(data, session=session)

    for _ in range(max_retries):
        keys_to_update = []
        for key, value in base_data.items():
            if not value or (key == 'gender' and value in ["", "UNKNOWN", "unknown"]):
                keys_to_update.append(key)
        if not is_data_consumable(base_data, "base_gender"):
            updated_data = await retrieve_instagram_gpt_data_base_gender(
                data, session=session)
            for key in keys_to_update:
                base_data[key] = updated_data.get(key, base_data[key])
        else:
            break

    profile_log = await parse_instagram_gpt_data_base_gender(base_data)
    profile_log.handle = data['handle']
    profile_log.profile_id = data['handle']
    return profile_log

# 6 GPT enrichment flows:
# - base_gender: Infer creator gender from handle + bio
# - base_location: Infer city/state/country
# - categ_lang_topics: Content category + language + topics
# - audience_age_gender: Audience demographic distribution
# - audience_cities: Audience geographic distribution
# - gender_location_lang: Combined inference (optimized)
```

### 4.10 Flow Dispatcher

```python
# core/flows/scraper.py - Dynamic flow dispatch using globals()
_whitelist = [
    refresh_profile_custom,
    refresh_profile_by_profile_id,
    refresh_profile_by_handle,
    refresh_profile_basic,
    refresh_post_by_shortcode,
    refresh_post_insights,
    # ... 40+ more flow functions imported
    asset_upload_flow,
    refresh_yt_profiles,
    refresh_instagram_gpt_data_base_gender,
    fetch_channels_csv,
]

@sessionize
async def perform_scrape_task(scrape_log: ScrapeRequestLog, session=None) -> dict | None:
    if not scrape_log or not scrape_log.flow or scrape_log.flow not in globals():
        raise Exception("Missing Flow - %s" % scrape_log.flow)
    _flow = globals()[scrape_log.flow]
    if _flow.__name__ in csv_flows:
        scrape_log.params['scrape_id'] = scrape_log.id
    return await _flow(**scrape_log.params, session=session)
```

### 4.11 Data Processing Pipeline

```python
# instagram/tasks/processing.py - Profile upsert with AMQP event publishing
@sessionize
async def upsert_profile(profile_id: str, profile_log: InstagramProfileLog,
                         recent_posts_log: Optional[List[InstagramPostLog]],
                         session=None) -> Tuple[InstagramAccount, List[InstagramPost]]:
    now = datetime.now()
    context = Context(now)

    # Create audit trail entry
    profile = ProfileLog(
        platform=enums.Platform.INSTAGRAM.name, profile_id=profile_id,
        metrics=[m.__dict__ for m in profile_log.metrics],
        dimensions=[d.__dict__ for d in profile_log.dimensions],
        source=profile_log.source, timestamp=now
    )
    await make_scrape_log_event("profile_log", profile)

    # Upsert account to PostgreSQL
    account = await upsert_insta_account(context, profile_log, profile_id, session=session)

    insta_posts = []
    for _post in (recent_posts_log or []):
        # Extract keywords from captions using YAKE
        if _post.dimensions:
            caption = next((item.value for item in _post.dimensions if item.key == CAPTION), "")
            _post.dimensions.append(
                dimension(get_extracted_keywords(caption) if caption else '', KEYWORDS))

        post = PostLog(
            platform=enums.Platform.INSTAGRAM.name,
            metrics=[m.__dict__ for m in _post.metrics],
            dimensions=[d.__dict__ for d in _post.dimensions],
            platform_post_id=_post.shortcode, profile_id=profile_id,
            source=_post.source, timestamp=now
        )
        insta_post = await upsert_insta_post(context, _post, session=session)
        insta_posts.append(insta_post)
        await make_scrape_log_event("post_log", post)

    return account, insta_posts
```

### 4.12 Engagement Rate Calculations

```python
# instagram/helper.py - Empirical formulas from platform data analysis
def get_engagement_rate(entity: InstagramPost, account: InstagramAccount):
    followers = account.followers or 0
    if followers == 0:
        return 0
    likes = entity.likes or 0
    comments = entity.comments or 0
    return round(((likes + comments) / followers) * 100, 2)

def get_reach(entity: InstagramPost, account: InstagramAccount):
    plays = entity.plays or 0
    likes = entity.likes or 0
    followers = account.followers or 0
    reach = entity.reach

    if reach is None or reach == 0:
        if entity.post_type == 'reels':
            # Empirical formula: reach correlates with plays minus a log factor
            reach = int(plays * (0.94 - (math.log2(followers) * 0.001)))
        else:
            # Static posts: reach correlates with likes via log decay
            reach = int((7.6 - (math.log10(likes) * 0.7)) * 0.85 * likes)
    return reach
```

### 4.13 FastAPI Server Entry Points

```python
# server.py - FastAPI application with connection pooling
app = FastAPI()

@app.on_event("startup")
async def startup_event():
    session_engine = create_async_engine(
        os.environ["PG_URL"], isolation_level="AUTOCOMMIT",
        echo=False, pool_size=50, max_overflow=50
    )
    session_engine_scl = create_async_engine(
        os.environ["PG_URL"], isolation_level="AUTOCOMMIT",
        echo=False, pool_size=10, max_overflow=5
    )
    await session_engine.connect()
    app.state.db = session_engine
    app.state.scl_db = session_engine_scl

# Graceful shutdown via heartbeat
@app.get("/heartbeat")
async def getHealth(response: Response, settings = Depends(get_settings)):
    if settings.heartbeat:
        response.status_code = status.HTTP_200_OK
    else:
        response.status_code = status.HTTP_410_GONE
    return response

@app.put("/heartbeat")
async def setHealth(beat: bool, response: Response, settings = Depends(get_settings)):
    settings.heartbeat = beat
```

---

## 5. Technical Decisions -- "Why THIS and Not THAT?"

### Decision 1: Why Multiprocessing + Asyncio Instead of Pure Asyncio?

| Approach | Pros | Cons | Chosen? |
|----------|------|------|---------|
| **multiprocessing + asyncio** | GIL isolation per flow, true parallelism, independent failure domains | Higher memory (~50MB per process), more OS resources | **YES** |
| **Pure asyncio (single process)** | Lower memory, simpler deployment | GIL contention on JSON parsing, one stuck flow blocks all, single point of failure | No |
| **Celery + Redis** | Battle-tested, auto-retry, monitoring | Heavy infrastructure, per-task overhead (~50ms), poor for high-throughput polling | No |
| **threading + asyncio** | Lower memory than multiprocessing | GIL contention, shared memory bugs, no true isolation | No |

> "Python's GIL means a single process can only execute one thread's Python bytecode at a time. Our scraping is mostly I/O-bound -- awaiting HTTP responses -- so asyncio handles that beautifully within each process. But JSON parsing of large API responses IS CPU-bound. With 73 flows sharing one process, a heavy Instagram response parse would block YouTube task polling. Multiprocessing gives us true isolation: if the Instagram flow crashes, YouTube keeps running. Each process has its own event loop, GIL, and failure domain."

**Follow-up -- "Isn't the memory overhead a problem?"**
> "Each worker process is ~50MB. With 150 workers, that's ~7.5GB. Our prod servers have 32GB RAM. The isolation benefit far outweighs the memory cost. We also have `SINGLE_WORKER` mode for dev/staging that runs all flows in one process."

**Follow-up -- "Why not Celery?"**
> "Celery's per-task overhead -- serialization, broker round-trip, deserialization -- adds ~50ms per task. We're polling tasks at 1-second intervals and executing them inline. Our approach has near-zero dispatch overhead. Also, Celery would add Redis as a required dependency for the broker; our SQL queue uses infrastructure we already had."

### Decision 2: Why SQL Task Queue (FOR UPDATE SKIP LOCKED) vs Redis/RabbitMQ?

| Approach | Pros | Cons | Chosen? |
|----------|------|------|---------|
| **SQL + FOR UPDATE SKIP LOCKED** | Persistent, queryable, priority ordering, no extra infra, atomic pickup | Polling overhead (1 query/sec/worker) | **YES** |
| **Redis (BRPOPLPUSH)** | Sub-ms latency, built-in blocking pop | Volatile (data loss on restart), no complex queries, no priority | No |
| **RabbitMQ** | Reliable delivery, acknowledgments | Cannot query pending tasks, no priority without plugin, extra infra | No |

> "FOR UPDATE SKIP LOCKED gives us distributed locking, persistence, and priority ordering in a single SQL query. The key advantage over Redis or RabbitMQ is queryability -- our API server can query `scrape_request_log` to check task status, list pending tasks per account, and show results. With Redis, we'd need a separate persistence layer. With RabbitMQ, once a message is consumed, it's gone -- you can't query 'what's pending?'"

**Follow-up -- "What about at 1000 workers?"**
> "At 1000 workers polling once per second, that's 1000 SELECT queries/sec. PostgreSQL can handle 10K+ simple queries/sec. The index on (flow, status) makes each query O(log n). If we outgrew this, we'd add PgBouncer -- which we already use for the asset pipeline."

**Follow-up -- "Why not use RabbitMQ since you already have it?"**
> "We DO use RabbitMQ -- for event publishing and credential validation. But the task queue has different requirements: queryability (check task status via API), persistence (survive crashes), and priority ordering (urgent tasks first). RabbitMQ is perfect for fire-and-forget events; PostgreSQL is perfect for stateful task management."

### Decision 3: Why 3-Level Stacked Rate Limiting?

| Approach | Pros | Cons | Chosen? |
|----------|------|------|---------|
| **3-level stacked** | Granular control, prevents both burst and sustained abuse | More Redis calls per request | **YES** |
| **Single global limit** | Simple | Cannot prevent per-handle abuse, no burst protection | No |
| **Token bucket** | Smooth rate, allows bursts | Complex implementation, one dimension only | No |

> "Each level protects against a different abuse pattern. The daily limit (20K/day) prevents runaway scripts from exhausting our API quota. The per-minute limit (60/min) prevents burst spikes that trip upstream API rate limits. The per-handle limit (1/sec) prevents a single client from repeatedly scraping the same profile. Without all three, a bug in one client could consume our entire daily budget in minutes."

**Follow-up -- "Why Redis and not in-memory?"**
> "Rate limits must be shared across all workers. We have 150+ processes across multiple servers. Redis gives us a single source of truth. In-memory counters would only protect within one process."

**Follow-up -- "What's the Redis overhead?"**
> "Each RateLimiter call is one Redis INCR + EXPIRE. Three levels = 6 Redis operations per request. At 60 req/min, that's 360 Redis ops/min -- trivial. Redis handles millions of operations per second."

### Decision 4: Why Credential Rotation vs Single API Key?

| Approach | Pros | Cons | Chosen? |
|----------|------|------|---------|
| **Credential rotation with TTL backoff** | Distribute load, survive rate limits, scale horizontally | Complex state management | **YES** |
| **Single API key** | Simple | One rate limit, single point of failure | No |
| **Round-robin** | Even distribution | Ignores credential health, uses disabled keys | No |

> "External APIs rate-limit per credential. With a single API key, hitting the limit means ALL scraping stops. With credential rotation, when one key gets rate-limited, we mark it `disabled_till = now + TTL` and switch to the next available key. We also have weighted random selection for specific operations -- follower fetching uses 70% RocketAPI and 30% JoTucker based on cost/reliability ratios."

**Follow-up -- "Permanently invalid credential?"**
> "We have an AMQP listener for credential validation. When a token expires or scopes change, the Identity service publishes an event, Beat receives it, and we set `data_access_expired = true`. The credential is never selected again until a user re-authenticates."

### Decision 5: Why Strategy Pattern for Crawlers?

| Approach | Pros | Cons | Chosen? |
|----------|------|------|---------|
| **Strategy pattern (interface + registry)** | Add providers without changing callers, clean separation of parsing | More classes/files | **YES** |
| **if/elif chain** | Simple for 2-3 providers | Grows to 500+ lines with 8 providers, violates Open/Closed | No |

> "We have 8 Instagram API providers, each with different response formats, auth mechanisms, and capabilities. The Strategy pattern means each provider implements `InstagramCrawlerInterface` -- same method signatures, different implementations. Adding a new provider means creating one class and adding one entry to both dicts. No existing code changes."

**Follow-up -- "Different response formats?"**
> "Each provider has its own parser. GraphAPI returns nested business_discovery objects. ArrayBobo returns flat user objects. The `parse_profile_data()` method in each implementation normalizes to our internal `InstagramProfileLog` model with standardized dimensions and metrics arrays."

### Decision 6: Why FastAPI + uvloop?

| Approach | Pros | Cons | Chosen? |
|----------|------|------|---------|
| **FastAPI + uvloop** | Native async, auto-docs, Pydantic validation, 2-4x faster event loop | Python ecosystem limits | **YES** |
| **Flask** | Simpler, battle-tested | Synchronous by default, no native async | No |
| **Go/Rust** | Better performance | Team expertise in Python, ML/GPT ecosystem in Python | No |

> "FastAPI was chosen because our entire pipeline is async. It supports native async/await, auto-generates OpenAPI docs, and Pydantic gives us request validation for free. uvloop replaces the default event loop with a libuv-based implementation that's 2-4x faster for I/O operations."

**Follow-up -- "Why not Go?"**
> "The team's expertise is Python. Our GPT integration uses OpenAI's Python SDK, keyword extraction uses YAKE, and sentiment analysis uses Python NLP libraries. The Python async ecosystem with uvloop gives us sufficient performance for our scale."

### Decision 7: Why RabbitMQ for Events vs Direct DB Writes?

> "Beat publishes events for every profile update, post update, credential change, and sentiment analysis result. These events are consumed by the dashboard, notification service, and analytics pipeline. Direct DB writes would couple Beat to every downstream consumer. With RabbitMQ, Beat publishes once and any number of consumers can subscribe. Adding a new consumer requires zero changes to Beat."

**Follow-up -- "Why not Kafka?"**
> "RabbitMQ was already deployed. Our event volume -- ~100K events/day -- doesn't need Kafka's throughput. RabbitMQ's routing keys give us flexible topic-based routing. Kafka would be right if we needed replay capability or multi-million events/sec."

**Follow-up -- "Synchronous publish inside async code?"**
> "The `publish()` function uses kombu, which is synchronous. Each publish blocks for ~1-2ms. If publish latency became a bottleneck, we'd switch to aio-pika or buffer events."

### Decision 8: Why Semaphore-Based Concurrency Control?

| Approach | Pros | Cons | Chosen? |
|----------|------|------|---------|
| **asyncio.Semaphore** | Simple, built-in, per-worker control | Manual acquire/release | **YES** |
| **asyncio.TaskGroup** | Structured concurrency (Python 3.11+) | All-or-nothing cancellation | No |

> "The semaphore controls how many tasks execute concurrently within one worker process. Without it, a worker could spawn thousands of concurrent tasks and exhaust API rate limits, database connections, or memory. When the semaphore is fully acquired, the poll loop detects `limit.locked()` and sleeps for 30 seconds. This provides natural backpressure -- if tasks are slow, we stop picking up new ones."

### Decision 9: Why Multiple RapidAPI Providers for Instagram?

> "Instagram has no official public API for non-business accounts. The Graph API only works for business accounts with a connected Facebook page. Each third-party provider has different rate limits, pricing, data coverage, and reliability. ArrayBobo returns reels but not followers. JoTucker returns followers but not reels. Multiple providers give us full data coverage and resilience."

**Follow-up -- "Cost?"**
> "Providers are ordered by cost-effectiveness. GraphAPI (free for business accounts) is first. Cheaper RapidAPI providers come next. Lama (most expensive) is the last fallback. For followers, we use weighted random (70% RocketAPI, 30% JoTucker) because RocketAPI is cheaper but slightly less reliable."

### Decision 10: Why GPT for Data Enrichment vs Rule-Based?

| Approach | Pros | Cons | Chosen? |
|----------|------|------|---------|
| **GPT (Azure OpenAI)** | Handles ambiguity, multilingual, context-aware | Cost per call (~$0.002), latency (~1s), non-deterministic | **YES** |
| **Rule-based (regex + name lists)** | Free, fast, deterministic | Fails on ambiguous names, no context understanding | No |
| **Custom ML model** | Tailored accuracy, one-time training cost | Training data needed, maintenance burden | Future roadmap |

> "We need to infer gender, location, language, and content category for millions of profiles. GPT understands context -- 'Fitness coach in Mumbai' in a bio tells it both location and category. We use GPT-3.5-turbo at temperature=0 for deterministic output, validate with `is_data_consumable()`, and retry up to 2 times. Cost is ~$0.002 per profile -- at 100K profiles/month, that's $200/month."

**Follow-up -- "Hallucinations?"**
> "Three safeguards: (1) temperature=0, (2) `is_data_consumable()` validates required fields, (3) retry with fresh calls. We also version prompts -- 13 YAML versions in `gpt/prompts/` for A/B testing accuracy improvements."

---

## 6. Interview Q&A

### Technical Deep Dive

**Q: "Walk me through the most complex system you've built."**

> "Beat is the data collection engine behind GCC's influencer marketing platform. It aggregates social media data from 15+ APIs -- Instagram, YouTube, Shopify -- at enterprise scale.
>
> The core architecture is a distributed worker pool: multiprocessing for CPU isolation with 73 configured flows, asyncio with uvloop for I/O concurrency, and semaphores for per-worker throttling. This gives us 150+ concurrent workers processing 10 million data points daily.
>
> The hardest engineering challenge was reliability. External APIs rate-limit unpredictably, credentials expire, and providers go down without notice. I solved this with three systems:
> 1. **Three-level stacked rate limiting** -- daily, per-minute, and per-handle limits backed by Redis
> 2. **Credential rotation with TTL backoff** -- when a key gets rate-limited, it's disabled for a TTL period and we switch to the next available credential
> 3. **Strategy pattern with ordered fallback** -- each scraping function has a priority-ordered list of API providers
>
> The data pipeline has three stages -- Retrieval, Parsing, Processing -- each producing standardized dimension/metric arrays. Every data change publishes an event to RabbitMQ for downstream consumers."

---

**Q: "How does your task queue work?"**

> "We use PostgreSQL as the task queue with `FOR UPDATE SKIP LOCKED`. Each worker process polls the `scrape_request_log` table once per second. The query atomically selects the next pending task, locks it so no other worker can pick it, and updates the status to PROCESSING -- all in one SQL statement.
>
> `SKIP LOCKED` is the key feature -- it skips rows already locked by other workers. 150 workers polling simultaneously never conflict. No blocking, no retries on lock contention.
>
> Tasks have priority ordering, flow-based routing (each worker only picks tasks for its assigned flow), and expiry timestamps. The API server can query the same table to check task status, which would be impossible with Redis or RabbitMQ."

---

**Q: "How do you handle failures and retries?"**

> "Multiple layers:
> 1. **Task level**: Exceptions mark the task FAILED with the error message. The status update is in a `finally` block, so it always executes.
> 2. **Long-running tasks**: A probabilistic cleanup process runs ~1% of poll cycles and cancels tasks exceeding the 10-minute timeout.
> 3. **API level**: Credential rotation disables failed credentials with a TTL and switches to alternatives. The fallback chain tries multiple providers.
> 4. **Process level**: Each worker's `looper()` has a `while True` with exception handling. If the event loop crashes, it creates a new one.
> 5. **System level**: The heartbeat endpoint supports graceful shutdown. Deploy script sends heartbeat=false, waits 10 seconds, then restarts."

---

**Q: "Explain your rate limiting strategy."**

> "Three levels, each protecting against a different abuse pattern:
>
> **Level 1 -- Daily global** (20K requests/day): Prevents runaway processes from exhausting our entire API budget.
>
> **Level 2 -- Per-minute global** (60 requests/minute): Prevents burst spikes that would trip upstream provider rate limits.
>
> **Level 3 -- Per-handle** (1 request/second): Prevents a single client from repeatedly scraping the same profile.
>
> On top of that, each API provider has its own rate spec. YouTube138 allows 850 req/60s. ArrayBobo allows 100 req/30s. The `make_request()` function detects the provider from the URL and applies the correct limiter.
>
> All limiters are backed by Redis using `asyncio-redis-rate-limit`. Redis INCR with EXPIRE gives us atomic counter operations shared across all 150+ worker processes."

---

**Q: "How does the asset upload pipeline handle 8M images daily?"**

> "The asset pipeline runs as a separate process -- `main_assets.py` -- with 50 workers and 100 concurrency per worker. That's up to 5,000 concurrent uploads.
>
> Each upload: (1) downloads the image from the social media CDN, (2) detects the format from the URL, (3) uploads to S3 with proper Content-Type headers, (4) records the S3 key in PostgreSQL.
>
> We use PgBouncer for connection pooling at this scale -- 50 workers each with pool_size=100 would exceed PostgreSQL's max_connections without a pooler. S3 keys follow `assets/{type}s/{platform}/{entity_id}.{ext}`, and CloudFront serves them with `ContentDisposition: inline`.
>
> URL signature expiration is a real problem -- Instagram CDN URLs expire after a few hours. We detect `URL signature expired` responses and skip those assets rather than retrying, since the URL cannot be refreshed without re-scraping."

---

**Q: "How did you design the Instagram crawler interface?"**

> "Strategy pattern. `InstagramCrawlerInterface` defines 15+ abstract methods. Eight concrete implementations: GraphApi, ArrayBobo, JoTucker, NeoTank, BestSolutions, IGApi, RocketApi, and Lama.
>
> `InstagramCrawler` maintains two maps: `providers` maps source names to implementation classes, and `available_sources` maps function types to priority-ordered source lists. When you call `fetch_profile_by_handle`, it queries the credential manager for the first available source, looks up the provider class, and delegates.
>
> Each provider has its own parser because Instagram has no standardized API -- GraphAPI returns nested business_discovery objects, ArrayBobo returns flat JSON, JoTucker returns yet another format. The parsers normalize everything to `InstagramProfileLog` with dimensions and metrics arrays."

---

**Q: "Tell me about the GPT enrichment flows."**

> "We use Azure OpenAI GPT-3.5-turbo to infer attributes not available from Instagram's API: gender, location, language, content category, and audience demographics.
>
> Six flows, each processing a different attribute. Input is the creator's handle, bio, and recent post captions. Output is structured JSON validated by `is_data_consumable()`.
>
> Key design choices: temperature=0 for deterministic output, up to 2 retries if the response contains 'UNKNOWN' values, and selective field merging -- if the first call gets gender right but location wrong, the retry only overwrites location.
>
> We version prompts as YAML files -- 13 versions so far -- so we can test improvements without code changes."

---

**Q: "If you were designing this from scratch today, what would you change?"**

> "Three things:
> 1. **Async publishing**: Replace synchronous kombu with aio-pika for AMQP publishing to eliminate blocking in the async event loop.
> 2. **Structured concurrency**: Python 3.11+ TaskGroups would replace the manual background_tasks set with cleaner cancellation semantics.
> 3. **Observability**: Add OpenTelemetry tracing from task pickup through API call through database write."

---

**Q: "How would you scale this 10x?"**

> "Current bottlenecks at 10x:
> 1. **Database connections**: 1500 workers x 5 connections = 7500. PostgreSQL maxes at ~1000. Solution: PgBouncer (already using for assets).
> 2. **Task queue polling**: 1500 queries/sec is fine for PostgreSQL. Add index on (flow, status, created_at).
> 3. **Redis rate limiting**: Trivially scalable -- millions of ops/sec.
> 4. **AMQP throughput**: 1M events/day is well within RabbitMQ's capacity.
>
> The real scaling challenge is API rate limits from external providers. More workers does not help if Instagram only allows 20K calls/day. The solution is more credentials and more providers -- horizontal scaling of API access, not just compute."

---

**Q: "How do you monitor this system?"**

> "Multiple layers:
> 1. **Task monitoring**: Query scrape_request_log for FAILED tasks, tasks stuck in PROCESSING >10 minutes, completion rates per flow.
> 2. **API monitoring**: `emit_trace_log_event()` publishes every HTTP request with timing, status code, and URL to RabbitMQ.
> 3. **Process monitoring**: Loguru structured logging with process ID, flow name, and task ID.
> 4. **Health check**: `/heartbeat` endpoint returns 200 or 410 for load balancer routing during deployments.
> 5. **AMQP monitoring**: Consumer lag on RabbitMQ queues indicates processing delays."

---

### Googleyness / Leadership / Collaboration

**Q: "Tell me about a time you had to make a trade-off between perfection and shipping."**

> "The `publish()` function in our AMQP module uses synchronous kombu inside async code. The 'right' solution would be fully async aio-pika. But we already had kombu working reliably, and the synchronous publish adds only 1-2ms of blocking.
>
> I considered rewriting it but estimated 2 weeks for testing all event types across all consumers. The business needed new scraping flows -- YouTube CSV exports, story insights -- urgently. I documented the technical debt, added it to the backlog, and shipped.
>
> Six months later, it still works fine at our scale. Sometimes the pragmatic choice IS the right choice."

---

**Q: "How do you handle disagreements with teammates about technical approach?"**

> "When building the credential rotation system, my teammate wanted simple round-robin. I advocated for priority-ordered fallback with TTL backoff. Instead of arguing abstractly, I ran a one-week experiment.
>
> I instrumented the code to log which credentials were being used and which were failing. The data showed 40% of GraphAPI calls were failing because tokens expired at different times. Round-robin would waste 40% of attempts on dead tokens.
>
> The data convinced the team. We shipped the priority-ordered approach, and failure rates dropped to under 2%."

---

**Q: "Describe a time you mentored someone."**

> "A junior developer was tasked with the Shopify integration. He started with a monolithic 300-line function that fetched, parsed, and wrote to the database all at once.
>
> Instead of rewriting it, I walked him through the existing Instagram pipeline: retrieval.py fetches, ingestion.py parses, processing.py writes. I explained the dimension/metric model that makes all platforms consistent. He refactored Shopify to follow the same 3-stage pattern.
>
> Two months later, when we needed YouTube CSV export flows, he built them himself following the same pattern without my help."

---

**Q: "Tell me about a time you simplified something complex."**

> "The `@sessionize` decorator. Before it, every async function had 10 lines of session boilerplate: create engine, create session, try/except/finally, commit/rollback/close. With 75+ flow functions, that was 750+ lines of repetitive, error-prone code.
>
> I wrote a decorator that checks if a session was passed from upstream -- if so, propagate it; if not, create and manage one. This means `refresh_profile` creates one session that flows through `upsert_profile` -> `upsert_insta_post` as a single transaction.
>
> Eliminated 750+ lines of boilerplate. Zero session leak bugs since adoption."

---

**Q: "How do you stay current with technology?"**

> "For Beat specifically, I tracked Python 3.11's asyncio.Runner and TaskGroup, which we adopted for uvloop integration. I followed PostgreSQL release notes -- FOR UPDATE SKIP LOCKED was a feature I learned about from the Postgres wiki.
>
> More broadly, I read engineering blogs from Instagram (understanding their API changes) and Stripe (distributed systems patterns). The credential rotation with TTL backoff was inspired by circuit breaker patterns from Netflix's Hystrix."

---

## 7. Behavioral Stories (STAR Format)

### Story 1: "Scraping at Scale"
*Use for: "Tell me about a complex system you built"*

**Situation:** "Good Creator Co. needed to aggregate data from 15+ social media APIs for influencer analytics. The existing system was single-threaded, hitting rate limits constantly, and could only process a few thousand profiles per day."

**Task:** "I was tasked with building a new data collection engine that could handle 10 million data points daily while respecting API rate limits from 8 different Instagram providers."

**Action:** "I designed a distributed architecture with three key innovations:
1. A worker pool using multiprocessing + asyncio + semaphore for 150+ concurrent workers
2. A 3-level stacked rate limiting system backed by Redis
3. A credential rotation system with TTL backoff and priority-ordered fallback chains

I also built a SQL-based task queue using PostgreSQL's FOR UPDATE SKIP LOCKED, which eliminated the need for Redis or RabbitMQ for task coordination."

**Result:** "The system processes 10M+ daily data points, uploads 8M images through S3, and has operated reliably for over a year. API costs dropped 30% through intelligent credential rotation and rate limiting. Response times improved 25% through connection pooling and asyncpg."

---

### Story 2: "Provider Reliability"
*Use for: "Tell me about a time you dealt with unreliable dependencies"*

**Situation:** "Our Instagram data relied on a single RapidAPI provider. When they had outages or changed their API, all scraping stopped. This happened 2-3 times per month."

**Task:** "Eliminate single-provider dependency and build a system that automatically handles provider failures."

**Action:** "I implemented the Strategy pattern with an interface that all providers implement. I built a crawler class with a provider registry and capability map. I added automatic fallback: if GraphAPI fails, it tries ArrayBobo, then JoTucker, then Lama, without any code changes. I also added weighted random selection for certain operations based on cost/reliability ratios."

**Result:** "Provider outages became invisible to the business. We went from 2-3 visible outages per month to zero. Adding new providers became trivial -- just implement the interface and add an entry to the registry."

---

### Story 3: "The @sessionize Decorator"
*Use for: "Tell me about a time you simplified something"*

**Situation:** "Every async function had 10 lines of database session boilerplate. With 75+ flow functions, that was 750+ lines of repetitive error-prone code."

**Task:** "Eliminate the boilerplate while maintaining correct session lifecycle management, including transaction propagation across nested function calls."

**Action:** "I wrote `@sessionize`. It checks if a session was passed from a caller -- if so, reuse it (propagation). If not, create a new one, wrap in try/except, commit on success, rollback on failure, always close. One transaction per top-level flow, automatically."

**Result:** "Eliminated 750+ lines of boilerplate. Made session management impossible to get wrong. New developers just add `@sessionize` and get correct behavior. Zero session leak bugs since adoption."

---

## 8. What-If Scenarios

*Framework: DETECT -> IMPACT -> MITIGATE -> RECOVER -> PREVENT*

### Scenario 1: Primary Instagram API provider (GraphAPI) goes down

> **DETECT:** API calls to graph.facebook.com return 5xx errors. `emit_trace_log_event()` logs every HTTP request with status codes -- error rate spike is visible immediately.
>
> **IMPACT:** Profile insights and post insights are GraphAPI-exclusive, so those fail. But profile fetches and post fetches have fallback providers.
>
> **MITIGATE:** `InstagramCrawler.fetch_profile_by_handle()` has built-in fallback. If GraphAPI throws an exception, it re-calls `fetch_enabled_sources()` with `exclusions=['graphapi']` and tries ArrayBobo, JoTucker, Lama, or BestSolutions transparently.
>
> **RECOVER:** When GraphAPI comes back, the credential's `disabled_till` TTL expires and it re-enters the rotation. No manual intervention.
>
> **PREVENT:** For GraphAPI-exclusive operations like insights, implement caching of last known good data and return stale data during outages.

### Scenario 2: PostgreSQL becomes slow -- task polling takes 10+ seconds

> **DETECT:** Workers log 'Found Work' with timestamps. If poll gaps increase from 1s to 10s, it is visible in logs. Task processing throughput drops; PENDING queue grows.
>
> **IMPACT:** All 150+ workers poll every second. If each query takes 10s, workers are idle 90% of the time.
>
> **MITIGATE:** `asyncio.sleep(1)` between polls prevents tight-loop hammering. Semaphore backpressure (`while limit.locked(): await asyncio.sleep(30)`) reduces polling when busy. Pool_size/max_overflow limit connection count.
>
> **RECOVER:** (1) Missing index on (flow, status) -- add it. (2) Connection exhaustion -- enable PgBouncer. (3) Lock contention -- reduce workers for low-priority flows. (4) Table bloat -- VACUUM scrape_request_log.
>
> **PREVENT:** PostgreSQL connection pool monitoring. Alerts on query latency p99. Add PgBouncer as standard between all workers and PostgreSQL.

### Scenario 3: All Instagram API credentials get rate-limited simultaneously

> **DETECT:** `CredentialManager.get_enabled_cred()` returns `None` for all sources. Crawler raises `NoAvailableSources`. Tasks fail with this error.
>
> **IMPACT:** All Instagram scraping stops. YouTube and Shopify continue (different credentials). Tasks accumulate as PENDING.
>
> **MITIGATE:** `disabled_till` is a TTL -- credentials auto-re-enable after backoff. If all disabled for 1 hour, scraping resumes after 1 hour without intervention.
>
> **RECOVER:** Wait for TTL expiry. Or manually set `enabled=true, disabled_till=null`. Or add new credentials.
>
> **PREVENT:** (1) Stagger credential usage via weighted random. (2) Add more credentials per provider. (3) Alert when >50% credentials are disabled. (4) Progressive backoff: first disable = 10 min, second = 30 min, third = 1 hour.

### Scenario 4: Worker process crashes -- tasks stuck in PROCESSING

> **DETECT:** Tasks in PROCESSING with `picked_at` older than 10 minutes. Monitoring query: `SELECT * FROM scrape_request_log WHERE status='PROCESSING' AND picked_at < now() - interval '10 minutes'`.
>
> **IMPACT:** Stuck tasks never complete. No other worker picks them because status is PROCESSING.
>
> **MITIGATE:** `check_and_cancel_long_running_tasks()` cancels asyncio tasks after 10 minutes. But if the entire process crashes, this cleanup never runs.
>
> **RECOVER:** Cleanup query: `UPDATE scrape_request_log SET status='PENDING' WHERE status='PROCESSING' AND picked_at < now() - interval '15 minutes'`.
>
> **PREVENT:** Scheduled job that periodically requeues stuck PROCESSING tasks. Enforce `expires_at` column in the poll query.

### Scenario 5: RabbitMQ goes down during peak scraping

> **DETECT:** `publish()` raises `ConnectionError`. Caught and logged by `make_scrape_log_event()`.
>
> **IMPACT:** Event publishing fails, but scraping continues. Data still reaches PostgreSQL. Downstream consumers (dashboard, notifications, analytics) stop receiving real-time updates.
>
> **MITIGATE:** Data is written to PostgreSQL first, then events are published. `try/except` catches publish failures without crashing the task.
>
> **RECOVER:** When RabbitMQ returns, new events flow normally. Events during outage are lost. Downstream consumers can query PostgreSQL directly for missing data.
>
> **PREVENT:** (1) Dead-letter buffer: write failed events to Redis, replay when RabbitMQ recovers. (2) `connect_robust()` with auto-reconnection (already used for listeners). (3) RabbitMQ cluster with mirrored queues.

### Scenario 6: New Instagram API provider returns malformed data

> **DETECT:** Parser throws `KeyError` or `TypeError`. Task fails with full traceback logged.
>
> **IMPACT:** Tasks using that provider fail. Fallback chain tries next provider. Credential is not disabled (parse error is our bug, not a rate limit).
>
> **MITIGATE:** `@sessionize` rolls back the transaction -- no partial data saved.
>
> **RECOVER:** Fix the parser (isolated to one file per provider). Deploy. Retry failed tasks by setting status to PENDING.
>
> **PREVENT:** (1) Response schema validation before parsing. (2) Integration tests against saved API response fixtures. (3) Version parsers alongside provider API versions.

### Scenario 7: S3 asset upload pipeline falls behind -- 100K images queued

> **DETECT:** Growing PENDING count for `flow='asset_upload_flow'`.
>
> **IMPACT:** Profile/post data is current but thumbnail URLs point to expired Instagram CDN links. Dashboard shows broken images.
>
> **MITIGATE:** 50 workers with 100 concurrency = up to 5,000 concurrent uploads. PgBouncer prevents connection exhaustion.
>
> **RECOVER:** Scale workers from 50 to 100. Or increase concurrency from 100 to 200. S3 allows 3,500 PUT requests/sec per partition -- far above our throughput.
>
> **PREVENT:** (1) Monitor queue depth; alert at 50K pending. (2) Priority: profile pictures before post thumbnails. (3) CDN URL proxying as alternative.

### Scenario 8: Bug deployment corrupts Instagram profile data

> **DETECT:** `profile_log` table records every update with full dimension/metric snapshots. Compare current `instagram_account` data against recent log entries.
>
> **IMPACT:** Dashboard shows incorrect data for affected profiles.
>
> **MITIGATE:** `profile_log` and `post_log` serve as audit trails. Every change logged with source and timestamp.
>
> **RECOVER:** (1) Deploy fix. (2) Find last good snapshot in profile_log. (3) SQL UPDATE to restore. (4) Re-queue profiles for fresh scrape. The upsert pattern means we can overwrite corrupted data without duplicates.
>
> **PREVENT:** (1) Data validation before upsert (reject negative followers). (2) Data quality scoring (flag 90% drops). (3) Staging environment with production snapshots.

### Scenario 9: Daily rate limit (20K) exhausted by noon

> **DETECT:** RateLimiter raises `RateLimitError`. API returns "Concurrency Limit Exceeded" with code 2.
>
> **IMPACT:** All on-demand Instagram profile requests rejected for the day. Worker pool tasks are unaffected (different rate limiting layer).
>
> **MITIGATE:** Per-minute limit (60/min) should prevent this. At 60/min, max daily is 86,400 -- well within 20K if spread. If exhausted, a burst slipped through.
>
> **RECOVER:** Wait for midnight UTC reset. Or manually `DEL beat_server_refresh_profile_insta_daily` in Redis.
>
> **PREVENT:** (1) Alert at 50% and 80% of daily limit. (2) Queue non-urgent requests for off-peak. (3) Sliding window instead of fixed daily reset.

### Scenario 10: Adding a new platform (TikTok) to Beat

> **IMPACT:** No existing code should need to change. That is the test of good architecture.
>
> **Implementation Plan:**
> 1. New module `tiktok/` with same structure as `instagram/`: entities, models, interface, crawler, 3-stage pipeline
> 2. New entries in `_whitelist`: `'refresh_tiktok_profiles': {'no_of_workers': 5, 'no_of_concurrency': 5}`
> 3. New flow import in `scraper.py`
> 4. New rate specs in `request.py`
> 5. New enum value: `TIKTOK` in `enums.Platform`
>
> Zero changes to main.py, server.py core logic, AMQP publishing, session management, or rate limiting infrastructure. The dimension/metric model means downstream analytics works automatically. ~2 weeks of work, not a redesign.

---

## 9. How to Speak

### 2-Minute Technical Deep Dives (Use Whichever Branch They Ask About)

**Branch A: Worker Pool System**
> "Each flow in the whitelist config gets N worker processes and M concurrency. For example, `refresh_profile_by_handle` gets 10 processes with 5 concurrent tasks each -- that's 50 simultaneous profile fetches.
>
> Each process runs a `looper()` function that creates a uvloop event loop and runs a `poller()`. The poller executes a SQL query every second that atomically picks the next pending task using FOR UPDATE SKIP LOCKED. If the semaphore is fully acquired, it sleeps for 30 seconds instead of polling.
>
> Tasks run as asyncio tasks within the event loop. A background cleanup process probabilistically checks for tasks exceeding the 10-minute timeout and cancels them. Status updates happen in a finally block, so COMPLETE or FAILED is always recorded."

**Branch B: Rate Limiting and Credential Rotation**
> "There are two layers of rate limiting. The first is at the API endpoint level -- 3 stacked Redis limiters controlling how many requests hit our service. The second is at the HTTP client level -- source-specific limiters for each external provider.
>
> For credentials, each API provider has multiple keys stored in PostgreSQL with an `enabled` flag and a `disabled_till` timestamp. When we need an API call, the Crawler base class queries for the first enabled credential. If rate-limited, we set `disabled_till = now + TTL` and the next query skips it.
>
> For Instagram followers specifically, we use weighted random selection -- 70% RocketAPI (cheaper) and 30% JoTucker (more reliable). For paginated requests, we use sticky sessions because cursors are provider-specific."

**Branch C: Data Pipeline**
> "Three stages. Retrieval calls the external API through the crawler and gets raw JSON. Ingestion parses that JSON into our internal model -- `InstagramProfileLog` with dimensions and metrics arrays. Processing upserts to PostgreSQL and publishes to RabbitMQ.
>
> The dimension/metric model is the unifying abstraction. Every platform produces the same structure: a list of `{key, value}` pairs for dimensions like handle, bio, profile_pic_url, and metrics like followers, likes, engagement_rate. This makes downstream analytics platform-agnostic."

### Pivot Phrases

| When they ask about... | Pivot to... |
|------------------------|-------------|
| "What about Kubernetes?" | "We deployed on VMs with GitLab CI. The deploy script uses heartbeat for graceful shutdown. I'd be interested in containerizing with K8s for auto-scaling workers based on queue depth." |
| "Any monitoring/alerting?" | "We have trace logging for every HTTP request, task status tracking in PostgreSQL, and heartbeat health checks. If I were adding observability, I'd add OpenTelemetry tracing and Prometheus metrics." |
| "Unit tests?" | "The project prioritized integration-level validation through the 3-stage pipeline. Each stage's output model (InstagramProfileLog) serves as a contract. I'd add property-based testing for the parsers as a next step." |
| "Security concerns?" | "Credentials are stored in PostgreSQL JSONB with application-level access control. API keys rotate through the credential management system. In a more mature setup, I'd use AWS Secrets Manager." |
| "How big was the team?" | "Small team of 3-4. I owned Beat end-to-end -- architecture, implementation, deployment. Others built the dashboard frontend and analytics service consuming Beat's events." |

### Common Mistakes to Avoid

1. **Do not say "just a scraper"** -- This is a distributed data pipeline with sophisticated reliability engineering.
2. **Do not over-explain RapidAPI** -- Say "third-party Instagram data providers" unless asked.
3. **Do not apologize for Python** -- uvloop + asyncio is competitive with Go for I/O-bound workloads at this scale.
4. **Do not skip the "why"** -- Every choice has a reason. FOR UPDATE SKIP LOCKED is not "because PostgreSQL" -- it is because you need queryability + persistence + priority.
5. **Do not forget the business impact** -- This powers influencer analytics for enterprise customers paying for the SaaS platform.
