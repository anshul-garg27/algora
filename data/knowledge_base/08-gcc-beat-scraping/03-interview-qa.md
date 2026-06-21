# Interview Q&A - Beat Scraping Engine

> Organized by interview round type. Practice the answer, not the memorization.

---

## SECTION A: Hiring Manager / Technical Deep Dive

### Q1: "Walk me through the most complex system you've built."

> "Beat is the data collection engine behind GCC's influencer marketing platform. It aggregates social media data from 15+ APIs -- Instagram, YouTube, Shopify -- at enterprise scale.
>
> The core architecture is a distributed worker pool: multiprocessing for CPU isolation with 73 configured flows, asyncio with uvloop for I/O concurrency, and semaphores for per-worker throttling. This gives us 150+ concurrent workers processing 10 million data points daily.
>
> The hardest engineering challenge was reliability. External APIs rate-limit unpredictably, credentials expire, and providers go down without notice. I solved this with three systems:
> 1. **Three-level stacked rate limiting** -- daily, per-minute, and per-handle limits backed by Redis
> 2. **Credential rotation with TTL backoff** -- when a key gets rate-limited, it's disabled for a TTL period and we switch to the next available credential
> 3. **Strategy pattern with ordered fallback** -- each scraping function has a priority-ordered list of API providers. If GraphAPI fails, we try ArrayBobo, then JoTucker, then Lama.
>
> The data pipeline has three stages -- Retrieval, Parsing, Processing -- each producing standardized dimension/metric arrays. Every data change publishes an event to RabbitMQ for downstream consumers."

---

### Q2: "How does your task queue work?"

> "We use PostgreSQL as the task queue with `FOR UPDATE SKIP LOCKED`. Each worker process polls the `scrape_request_log` table once per second. The query atomically selects the next pending task, locks it so no other worker can pick it, and updates the status to PROCESSING -- all in one SQL statement.
>
> `SKIP LOCKED` is the key feature -- it skips rows that are already locked by other workers. So 150 workers polling simultaneously never conflict. There's no blocking, no retries on lock contention.
>
> Tasks have priority ordering, flow-based routing (each worker only picks tasks for its assigned flow), and expiry timestamps. The API server can query the same table to check task status, which would be impossible with Redis or RabbitMQ."

---

### Q3: "How do you handle failures and retries?"

> "Multiple layers:
> 1. **Task level**: If a task throws an exception, it's marked FAILED with the error message in the data column. The status update is in a `finally` block, so it always executes.
> 2. **Long-running tasks**: A probabilistic cleanup process runs ~1% of poll cycles and cancels tasks running longer than 10 minutes.
> 3. **API level**: The credential rotation system disables failed credentials with a TTL and switches to alternatives. The fallback chain tries multiple providers.
> 4. **Process level**: Each worker's `looper()` function has a `while True` with exception handling. If the event loop crashes, it creates a new one and continues.
> 5. **System level**: The heartbeat endpoint supports graceful shutdown. The deploy script sends a heartbeat=false, waits 10 seconds, then restarts."

---

### Q4: "Explain your rate limiting strategy."

> "Three levels, each protecting against a different abuse pattern:
>
> **Level 1 - Daily global** (20K requests/day): Prevents runaway processes from exhausting our entire API budget.
>
> **Level 2 - Per-minute global** (60 requests/minute): Prevents burst spikes that would trip upstream provider rate limits.
>
> **Level 3 - Per-handle** (1 request/second): Prevents a single client from repeatedly scraping the same profile.
>
> On top of that, each API provider has its own rate spec. YouTube138 allows 850 req/60s. ArrayBobo allows 100 req/30s. BestPerformance allows just 2 req/sec. The `make_request()` function detects the provider from the URL and applies the correct limiter.
>
> All limiters are backed by Redis using `asyncio-redis-rate-limit`. Redis INCR with EXPIRE gives us atomic counter operations shared across all 150+ worker processes."

---

### Q5: "How does the asset upload pipeline handle 8M images daily?"

> "The asset pipeline runs as a separate process -- `main_assets.py` -- with 50 workers and 100 concurrency per worker. That's up to 5,000 concurrent uploads.
>
> Each upload: (1) downloads the image from the social media CDN, (2) detects the format from the URL, (3) uploads to S3 with proper Content-Type headers, (4) records the S3 key in PostgreSQL's `asset_log` table.
>
> We use PgBouncer for connection pooling at this scale -- 50 workers each with pool_size=100 would exceed PostgreSQL's max_connections without a pooler. The S3 keys follow a convention: `assets/{type}s/{platform}/{entity_id}.{ext}`, and CloudFront serves them with `ContentDisposition: inline` for browser display.
>
> URL signature expiration is a real problem -- Instagram CDN URLs expire after a few hours. We detect `URL signature expired` responses and skip those assets rather than retrying, since the URL can't be refreshed without re-scraping the profile."

---

### Q6: "How did you design the Instagram crawler interface?"

> "Strategy pattern. `InstagramCrawlerInterface` defines 15+ abstract methods -- fetch profile, fetch posts, fetch followers, parse responses, etc. Eight concrete implementations: GraphApi, ArrayBobo, JoTucker, NeoTank, BestSolutions, IGApi, RocketApi, and Lama.
>
> The `InstagramCrawler` class maintains two maps: `providers` maps source names to implementation classes, and `available_sources` maps function types to priority-ordered source lists. When you call `fetch_profile_by_handle`, it queries the credential manager for the first available source, looks up the provider class, and delegates the call.
>
> Each provider has its own parser because Instagram has no standardized API -- GraphAPI returns nested business_discovery objects, ArrayBobo returns flat JSON, JoTucker returns yet another format. The parsers normalize everything to our internal model with dimensions and metrics arrays."

---

### Q7: "Tell me about the GPT enrichment flows."

> "We use Azure OpenAI GPT-3.5-turbo to infer attributes that aren't available from Instagram's API: creator gender, location, language, content category, and audience demographics.
>
> Six flows, each processing a different attribute. The input is the creator's handle, bio, and recent post captions. The output is structured JSON validated by `is_data_consumable()`.
>
> Key design choices: temperature=0 for deterministic output, up to 2 retries if the response contains 'UNKNOWN' values, and selective field merging -- if the first call gets gender right but location wrong, the retry only overwrites location.
>
> We version our prompts as YAML files -- 13 versions so far -- so we can test improvements without code changes. The flows run as part of the main worker pool with 3 workers and 5 concurrency each."

---

## SECTION B: Googleyness / Leadership / Collaboration

### Q8: "Tell me about a time you had to make a trade-off between perfection and shipping."

> "The `publish()` function in our AMQP module uses synchronous kombu inside async code. The 'right' solution would be fully async aio-pika for publishing. But we already had kombu working reliably for event consumption, and the synchronous publish adds only 1-2ms of blocking.
>
> I considered rewriting it but estimated 2 weeks of work for testing all event types across all consumers. The business needed new scraping flows -- YouTube CSV exports, story insights -- urgently. I documented the technical debt, added it to the backlog, and shipped the working system.
>
> Six months later, it still works fine at our scale. Sometimes the pragmatic choice IS the right choice."

---

### Q9: "How do you handle disagreements with teammates about technical approach?"

> "When building the credential rotation system, my teammate wanted a simple round-robin approach. I advocated for the priority-ordered fallback with TTL backoff. Instead of arguing abstractly, I ran a one-week experiment.
>
> I instrumented the code to log which credentials were being used and which were failing. The data showed that 40% of our GraphAPI calls were failing because tokens expired at different times. Round-robin would waste 40% of attempts on dead tokens.
>
> The data convinced the team. We shipped the priority-ordered approach with TTL backoff, and failure rates dropped to under 2%. The lesson: let the data resolve disagreements, not opinions."

---

### Q10: "Describe a time you mentored someone or helped a teammate grow."

> "A junior developer was tasked with adding the Shopify integration. He started by writing a monolithic function that fetched data, parsed it, and wrote to the database -- all in one 300-line function.
>
> Instead of rewriting it, I walked him through the existing Instagram pipeline: retrieval.py fetches, ingestion.py parses, processing.py writes. I explained the dimension/metric model that makes all platforms consistent. He refactored Shopify to follow the same 3-stage pattern.
>
> Two months later, when we needed YouTube CSV export flows, he built them himself following the same pattern. The architecture was self-documenting enough that he didn't need my help."

---

### Q11: "Tell me about a time you simplified something complex."

> "The `@sessionize` decorator. Before it existed, every async function had 10 lines of boilerplate: create engine, create session, try/except/finally, commit/rollback/close.
>
> I wrote a decorator that wraps any async function. If no session is passed, it creates one and manages the lifecycle. If a session IS passed from upstream, it just propagates it. This eliminated the boilerplate from 75+ flow functions and made session management impossible to get wrong.
>
> The key insight was the session propagation behavior: `refresh_profile` creates a session, and it flows through `upsert_profile`, `upsert_insta_post`, all the way down. One transaction per top-level flow, automatically."

---

### Q12: "How do you stay current with technology?"

> "For Beat specifically, I tracked Python 3.11's asyncio.Runner and TaskGroup, which we adopted for uvloop integration. I also followed PostgreSQL release notes -- FOR UPDATE SKIP LOCKED was a feature I learned about from the Postgres wiki on advisory locks.
>
> More broadly, I read engineering blogs from companies doing similar work -- Instagram's engineering blog for understanding their API changes, and Stripe's blog for distributed systems patterns. The credential rotation with TTL backoff was inspired by circuit breaker patterns from Netflix's Hystrix library."

---

## SECTION C: System Design Follow-ups

### Q13: "If you were designing this from scratch today, what would you change?"

> "Three things:
> 1. **Async publishing**: Replace synchronous kombu with aio-pika for AMQP publishing to eliminate blocking in the async event loop.
> 2. **Structured concurrency**: Python 3.11+ TaskGroups would replace the manual background_tasks set with cleaner cancellation semantics.
> 3. **Observability**: Add OpenTelemetry tracing from task pickup through API call through database write. Currently we have logging but no distributed traces."

---

### Q14: "How would you scale this 10x?"

> "Current bottlenecks at 10x:
> 1. **Database connections**: 1500 workers x 5 connections = 7500 connections. PostgreSQL maxes at ~1000. Solution: PgBouncer (already using for assets).
> 2. **Task queue polling**: 1500 queries/sec is fine for PostgreSQL. Would add index on (flow, status, created_at).
> 3. **Redis rate limiting**: Trivially scalable -- Redis handles millions of ops/sec.
> 4. **AMQP throughput**: 1M events/day is well within RabbitMQ's capacity.
>
> The real scaling challenge is API rate limits from external providers. More workers doesn't help if Instagram only allows 20K calls/day. The solution is more credentials and more providers -- horizontal scaling of API access, not just compute."

---

### Q15: "How do you monitor this system?"

> "Multiple layers:
> 1. **Task monitoring**: Query scrape_request_log for FAILED tasks, tasks stuck in PROCESSING for >10 minutes, and task completion rates per flow.
> 2. **API monitoring**: `emit_trace_log_event()` publishes every HTTP request with timing, status code, and URL to RabbitMQ. Downstream analytics pipeline aggregates error rates per provider.
> 3. **Process monitoring**: Loguru structured logging with process ID, flow name, and task ID. Each log line includes `{process} | {name}:{function}:{line}`.
> 4. **Health check**: `/heartbeat` endpoint returns 200 or 410. Load balancer uses this for traffic routing during deployments.
> 5. **AMQP monitoring**: Consumer lag on RabbitMQ queues indicates processing delays."
