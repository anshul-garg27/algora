# Beat - Technical Implementation (Actual Code from Repo)

> Every code snippet here is from the actual `beat/` source tree.
> This is what you reference when they ask "show me the code."

---

## 1. Worker Pool System (main.py)

The core of Beat: multiprocessing for CPU isolation + asyncio for I/O concurrency + semaphore for per-worker throttling.

### 1.1 Flow Configuration - 73 Flows

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

### 1.2 Process Spawning - Multiprocessing + uvloop

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

**Key insight**: Each worker process creates its own uvloop event loop. This means the GIL never blocks across flows -- Instagram scraping never slows down YouTube scraping.

### 1.3 Event Loop with uvloop

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

### 1.4 Async Poller with Semaphore Backpressure

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

### 1.5 Task Execution with Semaphore and Timeout

```python
# main.py - Task execution with concurrency control
@sessionize
async def perform_task(con: AsyncConnection, row: any, limit: Semaphore,
                       session=None, session_engine=None) -> None:
    logger.debug(f"TASK-{row.id}::Acquiring Locks")
    await limit.acquire()
    logger.debug(f"TASK-{row.id}::Starting Execution")
    body = ScrapeRequest(
        flow=row.flow,
        platform=row.platform,
        params=row.params,
        retry_count=row.retry_count,
        priority=1
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

        now = datetime.datetime.now()
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

### 1.6 Long-Running Task Cancellation (10-minute timeout)

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

---

## 2. SQL-Based Task Queue with FOR UPDATE SKIP LOCKED

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

**Why this matters**: `FOR UPDATE SKIP LOCKED` is a PostgreSQL feature that atomically:
1. Selects the next pending task
2. Locks it so no other worker can pick it
3. Skips already-locked rows (no blocking)
4. Updates status to PROCESSING
5. Returns the row -- all in one query

---

## 3. Three-Level Stacked Rate Limiting

### 3.1 Server-Side: Stacked Redis Limiters (server.py)

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
                        backend=redis,
                        cache_prefix="beat_server_",
                        rate_spec=global_limit_day):
                    async with RateLimiter(
                            unique_key="refresh_profile_insta_per_minute",
                            backend=redis,
                            cache_prefix="beat_server_",
                            rate_spec=global_limit_minute):
                        async with RateLimiter(
                                unique_key="refresh_profile_insta_per_handle_" + handle,
                                backend=redis,
                                cache_prefix="beat_server_",
                                rate_spec=handle_limit):
                            await refresh_profile(None, handle, session=session)
            except RateLimitError as e:
                return error("Concurrency Limit Exceeded", 2)
```

### 3.2 Worker-Side: Source-Specific Rate Specs (utils/request.py)

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
    # URL-based provider detection routes to appropriate rate limiter
    if 'instagram-api-cheap-best-performance.p.rapidapi.com' in url:
        return await make_request_limited('insta-best-performance', method, url, **kwargs)
    elif 'youtube138.p.rapidapi.com' in url:
        return await make_request_limited('youtube138', method, url, **kwargs)
    elif 'instagram-scraper-2022' in url:
        return await make_request_limited('instagram-scraper-2022', method, url, **kwargs)
    # ... more providers
    # Default: no rate limiting
    resp = await asks.request(method, url, **kwargs)
    return resp


async def make_request_limited(source, method: str, url: str, **kwargs) -> any:
    redis = AsyncRedis.from_url(os.environ["REDIS_URL"])
    while True:
        try:
            async with RateLimiter(
                    unique_key=source,
                    backend=redis,
                    cache_prefix="beat_",
                    rate_spec=source_specs[source]):
                start_time = time.perf_counter()
                resp = await asks.request(method, url, **kwargs)
                end_time = time.perf_counter()
                await emit_trace_log_event(method, url, resp, end_time - start_time, kwargs)
                return resp
        except RateLimitError as e:
            await asyncio.sleep(1)  # Back off and retry
```

---

## 4. Credential Rotation with TTL Backoff

### 4.1 Credential Entity (core/entities/entities.py)

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

### 4.2 Credential Selection with Fallback (core/crawler/crawler.py)

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

---

## 5. Asset Upload Pipeline (main_assets.py)

### 5.1 Dedicated Asset Worker Pool

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

### 5.2 S3 Upload with CDN Delivery (core/client/upload_assets.py)

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
            Body=response.content,
            Bucket=bucket,
            Key=blob_s3_key,
            ContentType=content_type,
            ContentDisposition='inline'
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
        'entity_type': entity_type,
        'entity_id': entity_id,
        'platform': platform,
        'asset_type': asset_type,
        'asset_url': asset_url,
        'original_url': original_url,
        'updated_at': datetime.now()
    }
    await upsert_save_profile_url(query_string, session=session)
```

---

## 6. AMQP/RabbitMQ Event Publishing

### 6.1 Listener Configuration (core/amqp/models.py + core/amqp/amqp.py)

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

### 6.2 Configured AMQP Listeners (main.py)

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

def start_listeners(workers: list) -> None:
    for amqp_listener_config in amqp_listeners:
        for _ in range(amqp_listener_config.workers):
            w = multiprocessing.Process(target=listener, args=(amqp_listener_config,))
            w.start()
            workers.append(w)
```

### 6.3 Event Publishing from Workers (utils/request.py)

```python
# utils/request.py - Every profile/post update publishes to RabbitMQ
async def emit_profile_log_event(log: ProfileLog):
    now = datetime.datetime.now()
    handle = None
    if log.platform == 'YOUTUBE':
        handle = log.profile_id
    else:
        for dim in log.dimensions:
            if dim["key"] == "handle":
                handle = dim["value"]
    payload = {
        "event_id": str(uuid.uuid4()),
        "source": log.source,
        "platform": log.platform,
        "profile_id": log.profile_id,
        "handle": handle,
        "event_timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "metrics": {m["key"]: m["value"] for m in log.metrics},
        "dimensions": {d["key"]: d["value"] for d in log.dimensions}
    }
    publish(payload, "beat.dx", "profile_log_events")
```

---

## 7. Instagram Crawler Interface with 8 Provider Implementations

### 7.1 Interface Definition (instagram/functions/retriever/interface.py)

```python
# instagram/functions/retriever/interface.py - Strategy pattern interface
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
    async def fetch_post_insights(ctx: RequestContext, post_id: str, post_type: str) -> dict:
        pass

    @staticmethod
    async def fetch_profile_insights(cx: RequestContext, handle: str) -> dict:
        pass

    @staticmethod
    async def fetch_stories_posts(cx: RequestContext, handle: str,
                                   cursor: str = None) -> (dict, str):
        pass

    @staticmethod
    def parse_profile_data(resp_dict: dict) -> InstagramProfileLog:
        pass

    @staticmethod
    def parse_profile_post_data(resp_dict: dict) -> List[InstagramPostLog]:
        pass

    @staticmethod
    def parse_post_by_shortcode(resp_dict: dict) -> InstagramPostLog:
        pass
    # ... 10+ more methods
```

### 7.2 Concrete Crawler with Provider Registry (instagram/functions/retriever/crawler.py)

```python
# instagram/functions/retriever/crawler.py - The strategy selector
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
                    exclusions=["graphapi"],
                    session=session)
                if not creds:
                    raise NoAvailableSources("No source is available")
                provider = self.providers[creds.source]
                return await provider.fetch_profile_by_handle(
                    RequestContext(creds), handle), creds.source
```

---

## 8. Session Management with @sessionize Decorator

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

**Key insight**: This decorator enables session propagation. When `refresh_profile` calls `upsert_profile` which calls `upsert_insta_post`, the same session is passed through. But when a function is called standalone, it creates and manages its own session with proper commit/rollback.

---

## 9. GPT Enrichment Flows

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

---

## 10. Flow Dispatcher (core/flows/scraper.py)

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
    # ...
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

---

## 11. Engagement Rate Calculations (instagram/helper.py)

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

---

## 12. Data Processing Pipeline (instagram/tasks/processing.py)

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
        platform=enums.Platform.INSTAGRAM.name,
        profile_id=profile_id,
        metrics=[m.__dict__ for m in profile_log.metrics],
        dimensions=[d.__dict__ for d in profile_log.dimensions],
        source=profile_log.source,
        timestamp=now
    )
    # Publish profile event to RabbitMQ
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
            platform_post_id=_post.shortcode,
            profile_id=profile_id,
            source=_post.source,
            timestamp=now
        )
        insta_post = await upsert_insta_post(context, _post, session=session)
        insta_posts.append(insta_post)
        await make_scrape_log_event("post_log", post)

    return account, insta_posts
```

---

## 13. FastAPI Server Entry Points (server.py)

```python
# server.py - FastAPI application with connection pooling
app = FastAPI()

@app.on_event("startup")
async def startup_event():
    session_engine = create_async_engine(
        os.environ["PG_URL"],
        isolation_level="AUTOCOMMIT",
        echo=False,
        pool_size=50,
        max_overflow=50
    )
    session_engine_scl = create_async_engine(
        os.environ["PG_URL"],
        isolation_level="AUTOCOMMIT",
        echo=False,
        pool_size=10,
        max_overflow=5
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

# Lama fallback for post fetching when GraphAPI fails
async def lama_fallback(handle: str, platform: str, shortcode: str, session=None):
    lama = Lama()
    ctx = RequestContext(CredentialModel(0, "", "",
        {"x-access-key": "AUIiOivV7oO9vqrv3nnDdL5KYlPzcgu8"}))
    resp_dict = await lama.fetch_post_by_shortcode(ctx, shortcode)
    log = lama.parse_post_by_shortcode(resp_dict)
    context = Context(datetime.now())
    post = await upsert_insta_post(context, log, session=session)
    return success("Post Retrieved", post={...})
```
