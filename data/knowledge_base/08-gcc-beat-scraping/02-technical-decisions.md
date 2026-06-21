# Technical Decisions Deep Dive - "Why THIS and Not THAT?"

> **Every major decision in the Beat scraping engine with alternatives, trade-offs, and follow-up answers.**
> This is what separates "good" from "excellent" in a hiring manager interview.

---

## Decision 1: Why Multiprocessing + Asyncio Instead of Pure Asyncio?

### What's In The Code
```python
# main.py
for flow in _whitelist:
    num_process = _whitelist[flow]['no_of_workers']
    for i in range(num_process):
        max_conc = int(_whitelist[flow]['no_of_concurrency'])
        limit = asyncio.Semaphore(max_conc)
        w = multiprocessing.Process(target=looper, args=(i + 1, limit, [flow], max_conc))
        w.start()
```

### The Options

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **multiprocessing + asyncio** | GIL isolation per flow, true parallelism, independent failure domains | Higher memory (each process ~50MB), more OS resources | **YES** |
| **Pure asyncio (single process)** | Lower memory, simpler deployment | GIL contention on JSON parsing, one stuck flow blocks all, single point of failure | No |
| **Celery + Redis** | Battle-tested, auto-retry, monitoring | Heavy infrastructure (Redis broker + flower), per-task overhead, poor for high-throughput polling | No |
| **threading + asyncio** | Lower memory than multiprocessing | GIL contention, shared memory bugs, no true isolation | No |

### Interview Answer
> "Python's GIL means a single process can only execute one thread's Python bytecode at a time. Our scraping is mostly I/O-bound -- awaiting HTTP responses -- so asyncio handles that beautifully within each process. But JSON parsing of large API responses IS CPU-bound. With 73 flows sharing one process, a heavy Instagram response parse would block YouTube task polling. Multiprocessing gives us true isolation: if the Instagram flow crashes, YouTube keeps running. Each process has its own event loop, GIL, and failure domain."

### Follow-up: "Isn't the memory overhead a problem?"
> "Each worker process is ~50MB. With 150 workers, that's ~7.5GB. Our prod servers have 32GB RAM. The isolation benefit far outweighs the memory cost. We also have `SINGLE_WORKER` mode for dev/staging that runs all flows in one process."

### Follow-up: "Why not Celery?"
> "Celery's per-task overhead -- serialization, broker round-trip, deserialization -- adds ~50ms per task. We're polling tasks at 1-second intervals and executing them inline. Our approach has near-zero dispatch overhead. Also, Celery would add Redis as a required dependency for the broker; our SQL queue uses infrastructure we already had."

---

## Decision 2: Why SQL Task Queue (FOR UPDATE SKIP LOCKED) vs Redis/RabbitMQ?

### What's In The Code
```python
# main.py - Atomic task pickup
statement = text("""
    update scrape_request_log
        set status='PROCESSING'
        where id IN (
            select id from scrape_request_log e
            where status = 'PENDING' and flow = :flow
            for update skip locked
            limit 1)
    RETURNING *
""")
```

### The Options

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **SQL + FOR UPDATE SKIP LOCKED** | Persistent, queryable, priority ordering, no extra infra, atomic pickup | Polling overhead (1 query/sec/worker), not as fast as in-memory | **YES** |
| **Redis (BRPOPLPUSH)** | Sub-ms latency, built-in blocking pop | Volatile (data loss on restart), no complex queries, no priority | No |
| **RabbitMQ** | Reliable delivery, acknowledgments | Can't query pending tasks, no priority without plugin, extra infra | No |
| **Celery** | Full task framework | Overhead, opinionated, doesn't fit our polling model | No |

### Interview Answer
> "FOR UPDATE SKIP LOCKED is a PostgreSQL feature that gives us distributed locking, persistence, and priority ordering in a single SQL query. The key advantage over Redis or RabbitMQ is queryability -- our API server can query `scrape_request_log` to check task status, list pending tasks per account, and show results. With Redis, we'd need a separate persistence layer. With RabbitMQ, once a message is consumed, it's gone -- you can't query 'what's pending?' The trade-off is polling overhead, but at 1 query per second per worker, PostgreSQL handles this easily."

### Follow-up: "What about at 1000 workers?"
> "At 1000 workers polling once per second, that's 1000 SELECT queries/sec on the scrape_request_log table. PostgreSQL can handle 10K+ simple queries/sec on a modest instance. The index on (flow, status) makes each query O(log n). If we outgrew this, we'd add connection pooling through PgBouncer -- which we already use for the asset pipeline."

### Follow-up: "Why not use RabbitMQ since you already have it?"
> "We DO use RabbitMQ -- for event publishing and credential validation. But the task queue has different requirements: we need queryability (check task status via API), persistence (survive crashes), and priority ordering (urgent tasks first). RabbitMQ is perfect for fire-and-forget events; PostgreSQL is perfect for stateful task management."

---

## Decision 3: Why 3-Level Stacked Rate Limiting?

### What's In The Code
```python
# server.py - Three nested RateLimiter context managers
async with RateLimiter(unique_key="refresh_profile_insta_daily",
                       backend=redis, rate_spec=RateSpec(requests=20000, seconds=86400)):
    async with RateLimiter(unique_key="refresh_profile_insta_per_minute",
                           backend=redis, rate_spec=RateSpec(requests=60, seconds=60)):
        async with RateLimiter(unique_key="refresh_profile_insta_per_handle_" + handle,
                               backend=redis, rate_spec=RateSpec(requests=1, seconds=1)):
            await refresh_profile(None, handle, session=session)
```

### The Options

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **3-level stacked** | Granular control, prevents both burst and sustained abuse | More Redis calls per request | **YES** |
| **Single global limit** | Simple | Can't prevent per-handle abuse, no burst protection | No |
| **Token bucket** | Smooth rate, allows bursts | Complex implementation, one dimension only | No |
| **API gateway rate limiting** | Offloaded, standard | Can't do per-handle limits without custom logic | Partial |

### Interview Answer
> "Each level protects against a different abuse pattern. The daily limit (20K/day) prevents runaway scripts from exhausting our API quota for the entire day. The per-minute limit (60/min) prevents burst spikes that would trip upstream API rate limits. The per-handle limit (1/sec) prevents a single client from repeatedly scraping the same profile. Without all three, a bug in one client could consume our entire daily budget in minutes."

### Follow-up: "Why Redis and not in-memory?"
> "Rate limits must be shared across all workers. We have 150+ processes across multiple servers. Redis gives us a single source of truth for rate limit state. In-memory counters would only protect within one process."

### Follow-up: "What's the Redis overhead?"
> "Each RateLimiter call is one Redis INCR + EXPIRE. Three levels = 6 Redis operations per request. At 60 req/min, that's 360 Redis ops/min -- trivial. Redis handles millions of operations per second."

---

## Decision 4: Why Credential Rotation vs Single API Key?

### What's In The Code
```python
# core/crawler/crawler.py
for source in self.available_sources[fetch_type]:
    source_cred = await CredentialManager.get_enabled_cred(source, session=session)
    if source_cred:
        return source_cred
```

### The Options

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **Credential rotation with TTL backoff** | Distribute load, survive rate limits, scale horizontally | Complex state management | **YES** |
| **Single API key** | Simple | One rate limit, single point of failure | No |
| **Round-robin** | Even distribution | Ignores credential health, uses disabled keys | No |
| **Proxy rotation** | Hides identity | Expensive, doesn't help with API-key-based limits | No |

### Interview Answer
> "External APIs rate-limit per credential. With a single API key, hitting the limit means ALL scraping stops. With credential rotation, when one key gets rate-limited, we mark it `disabled_till = now + TTL` and switch to the next available key. The TTL backoff prevents hammering a recently-limited key. We also have weighted random selection for specific operations -- follower fetching uses 70% RocketAPI and 30% JoTucker based on cost/reliability ratios."

### Follow-up: "How do you handle a credential becoming permanently invalid?"
> "We have an AMQP listener for credential validation. When a token expires or scopes change, the Identity service publishes an event, Beat receives it, and we set `data_access_expired = true`. The credential is never selected again until a user re-authenticates."

---

## Decision 5: Why Strategy Pattern for Crawlers?

### What's In The Code
```python
# instagram/functions/retriever/crawler.py
self.providers = {
    'rapidapi-arraybobo': ArrayBobo,
    'rapidapi-jotucker': JoTucker,
    'graphapi': GraphApi,
    'lama': Lama,
    'rocketapi': RocketApi,
    # ... 3 more
}
# Dynamic dispatch
provider = self.providers[creds.source]
return await provider.fetch_profile_by_handle(RequestContext(creds), handle), creds.source
```

### The Options

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **Strategy pattern (interface + registry)** | Add providers without changing callers, clean separation of parsing | More classes/files | **YES** |
| **if/elif chain** | Simple for 2-3 providers | Grows to 500+ lines with 8 providers, violates Open/Closed | No |
| **Factory method** | Encapsulated creation | Doesn't solve the interface consistency problem | Partial |
| **Plugin system** | Hot-loadable | Over-engineered for fixed provider set | No |

### Interview Answer
> "We have 8 Instagram API providers, each with different response formats, auth mechanisms, and capabilities. The Strategy pattern means each provider implements `InstagramCrawlerInterface` -- same method signatures, different implementations. The crawler maintains a registry (`self.providers`) and a capability map (`self.available_sources`) that lists which providers support which operations. Adding a new provider means creating one class and adding one entry to both dicts. No existing code changes."

### Follow-up: "How do you handle different response formats?"
> "Each provider has its own parser. GraphAPI returns nested business_discovery objects. ArrayBobo returns flat user objects. JoTucker returns a different structure. The `parse_profile_data()` method in each implementation normalizes to our internal `InstagramProfileLog` model with standardized dimensions and metrics arrays."

---

## Decision 6: Why FastAPI + uvloop?

### What's In The Code
```python
# server.py
app = FastAPI()
uvicorn.run(app, host="0.0.0.0", port=8000)

# main.py
with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
    runner.run(poller(id, limit, flows, max_conc))
```

### The Options

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **FastAPI + uvloop** | Native async, auto-docs, Pydantic validation, 2-4x faster event loop | Python ecosystem limits | **YES** |
| **Flask** | Simpler, more battle-tested | Synchronous by default, no native async | No |
| **Django** | Full-featured ORM, admin | Too heavy for an API-only service, sync | No |
| **Go/Rust** | Better performance | Team expertise in Python, ML/GPT ecosystem in Python | No |

### Interview Answer
> "FastAPI was chosen because our entire pipeline is async -- from HTTP requests to database queries to message publishing. It supports native async/await, auto-generates OpenAPI docs for internal consumers, and Pydantic gives us request validation for free. uvloop replaces the default asyncio event loop with a libuv-based implementation that's 2-4x faster for I/O operations. Since we're making thousands of concurrent HTTP requests, that speedup compounds significantly."

### Follow-up: "Why not Go for better concurrency?"
> "The team's expertise is Python. More importantly, our GPT integration uses OpenAI's Python SDK, our ML keyword extraction uses YAKE (Python), and our sentiment analysis uses Python NLP libraries. Rewriting in Go would mean reimplementing or calling out to all of those. The Python async ecosystem with uvloop gives us sufficient performance for our scale."

---

## Decision 7: Why RabbitMQ for Events vs Direct DB Writes?

### What's In The Code
```python
# utils/request.py - Publish events to RabbitMQ after every data change
def publish(payload: dict, exchange: str, routing_key: str) -> None:
    with Connection(os.environ["RMQ_URL"]) as conn:
        producer = conn.Producer(serializer='json')
        producer.publish(payload, exchange=exchange, routing_key=routing_key)
```

### Interview Answer
> "Beat publishes events for every profile update, post update, credential change, and sentiment analysis result. These events are consumed by the GCC dashboard service, the notification service, and the analytics pipeline. Direct DB writes would couple Beat to every downstream consumer. With RabbitMQ, Beat publishes once and any number of consumers can subscribe. Adding a new consumer requires zero changes to Beat."

### Follow-up: "Why not Kafka?"
> "RabbitMQ was already deployed in our infrastructure for the Identity service. Our event volume -- ~100K events/day -- doesn't need Kafka's throughput. RabbitMQ's routing keys give us flexible topic-based routing. Kafka would be the right choice if we needed replay capability or multi-million events/sec."

### Follow-up: "Why synchronous publish inside async code?"
> "The `publish()` function uses kombu, which is synchronous. This is a known trade-off. Each publish blocks for ~1-2ms. We considered using aio-pika for async publishing, but kombu's simplicity and reliability won. If publish latency became a bottleneck, we'd switch to aio-pika or buffer events."

---

## Decision 8: Why Semaphore-Based Concurrency Control?

### What's In The Code
```python
# main.py
limit = asyncio.Semaphore(max_conc)  # e.g., 5 concurrent tasks

async def perform_task(con, row, limit, session=None, session_engine=None):
    await limit.acquire()
    try:
        data = await execute(row, session=session)
        # ... update status
    finally:
        limit.release()
```

### The Options

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **asyncio.Semaphore** | Simple, built-in, per-worker control | Manual acquire/release | **YES** |
| **asyncio.TaskGroup** | Structured concurrency (Python 3.11+) | All-or-nothing cancellation | No |
| **Connection pool limit** | Controls DB connections | Doesn't control API concurrency | Complementary |
| **External rate limiter** | Shared across processes | Adds latency for every task | For API calls only |

### Interview Answer
> "The semaphore controls how many tasks execute concurrently within one worker process. Without it, a worker could spawn thousands of concurrent tasks and exhaust API rate limits, database connections, or memory. With `Semaphore(5)`, each worker runs at most 5 tasks simultaneously. When the semaphore is fully acquired, the poll loop detects `limit.locked()` and sleeps for 30 seconds instead of polling for new tasks. This provides natural backpressure -- if tasks are slow, we stop picking up new ones."

### Follow-up: "Why acquire/release instead of `async with semaphore`?"
> "In our code, the task continues after the semaphore is released -- we need to update the task status even if the semaphore was released during exception handling. `async with` would release on any exit, which is what we want, but we also need the status update in the `finally` block after release. The explicit acquire/release gives us control over the exact sequence."

---

## Decision 9: Why Multiple RapidAPI Providers for Instagram?

### What's In The Code
```python
# instagram/functions/retriever/crawler.py
self.available_sources = {
    'fetch_profile_by_handle': ['graphapi', 'rapidapi-arraybobo',
                                 'rapidapi-jotucker', 'lama',
                                 'rapidapi-bestsolutions'],
}
```

### Interview Answer
> "Instagram has no official public API for non-business accounts. The Graph API only works for business accounts that have connected their Facebook page. For personal accounts, we need third-party providers. Each provider has different rate limits, pricing, data coverage, and reliability. ArrayBobo returns reels data but not followers. JoTucker returns followers but not reels. By maintaining multiple providers, we get full data coverage and resilience. If one provider goes down or changes their API, we fall back to the next one in the priority list."

### Follow-up: "How do you keep parsers in sync when APIs change?"
> "Each provider has its own parser class -- `arraybobo_parser.py`, `jotucker_parser.py`, etc. They all produce the same output format: `InstagramProfileLog` with dimensions and metrics arrays. When a provider changes their response format, we only update that one parser. The rest of the pipeline doesn't change."

### Follow-up: "What about cost?"
> "Providers have different pricing per request. We order `available_sources` by cost-effectiveness. GraphAPI (free for business accounts) is first. Cheaper RapidAPI providers come next. Lama (most expensive) is the last fallback. For followers, we use weighted random (70% RocketAPI, 30% JoTucker) because RocketAPI is cheaper but slightly less reliable."

---

## Decision 10: Why GPT for Data Enrichment vs Rule-Based?

### What's In The Code
```python
# gpt/flows/fetch_gpt_data.py - GPT with retry and validation
@sessionize
async def fetch_instagram_gpt_data_base_gender(data: dict, session=None):
    max_retries = 2
    base_data = await retrieve_instagram_gpt_data_base_gender(data, session=session)
    for _ in range(max_retries):
        if not is_data_consumable(base_data, "base_gender"):
            updated_data = await retrieve_instagram_gpt_data_base_gender(data, session=session)
            # Merge only missing/invalid fields
            for key in keys_to_update:
                base_data[key] = updated_data.get(key, base_data[key])
        else:
            break
```

### The Options

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **GPT (Azure OpenAI)** | Handles ambiguity, multilingual, context-aware | Cost per call (~$0.002), latency (~1s), non-deterministic | **YES** |
| **Rule-based (regex + name lists)** | Free, fast, deterministic | Fails on ambiguous names, no context understanding | Too inaccurate |
| **Custom ML model** | Tailored accuracy, one-time training cost | Training data needed, maintenance burden | Future roadmap |
| **Manual labeling** | 100% accurate | Does not scale to millions of profiles | No |

### Interview Answer
> "We need to infer gender, location, language, and content category for millions of Instagram profiles. Rule-based approaches fail on ambiguous names ('Alex', 'Sam'), non-English content, and creative handles. GPT understands context -- 'Fitness coach in Mumbai' in a bio tells it both location and content category. We use Azure OpenAI with GPT-3.5-turbo at temperature=0 for deterministic output, and validate responses with `is_data_consumable()`. If GPT returns 'UNKNOWN', we retry up to 2 times. The cost is ~$0.002 per profile -- at 100K profiles/month, that's $200/month for data that would take a human team weeks."

### Follow-up: "How do you handle GPT hallucinations?"
> "Three safeguards: (1) Temperature=0 for deterministic output, (2) `is_data_consumable()` validates that required fields are present and not 'UNKNOWN', (3) Retry with fresh API calls if validation fails. We also version our prompts -- 13 YAML versions in `gpt/prompts/` -- so we can A/B test accuracy improvements."

### Follow-up: "What about YAKE keyword extraction?"
> "YAKE is used alongside GPT for a different purpose. YAKE extracts keywords from post captions -- it's a statistical method that doesn't need API calls. This runs on every post ingestion. GPT enrichment runs as separate batch flows (6 flows) for profile-level attributes. Different tools for different granularities."
