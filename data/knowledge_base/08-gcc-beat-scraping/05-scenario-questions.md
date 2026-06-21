# Scenario-Based "What If?" Questions - Beat Scraping Engine

> **Hiring managers LOVE these.** They test if you truly understand your system under failure.
> Use the framework: DETECT -> IMPACT -> MITIGATE -> RECOVER -> PREVENT

---

## Q1: "What if your primary Instagram API provider (GraphAPI) goes down?"

> **DETECT:** "API calls to graph.facebook.com start returning 5xx errors. The `emit_trace_log_event()` function logs every HTTP request with status codes, so we'd see the error rate spike immediately in our trace logs."
>
> **IMPACT:** "GraphAPI is only the primary provider for some operations. Profile insights and post insights are GraphAPI-exclusive, so those fail. But profile fetches and post fetches have fallback providers."
>
> **MITIGATE:** "The `InstagramCrawler.fetch_profile_by_handle()` has built-in fallback logic. If GraphAPI throws an exception, it re-calls `fetch_enabled_sources()` with `exclusions=['graphapi']` and tries the next provider -- ArrayBobo, JoTucker, Lama, or BestSolutions. This happens transparently within the same task execution."
>
> **RECOVER:** "When GraphAPI comes back online, the credential's `disabled_till` TTL expires, and it's automatically re-included in the provider rotation. No manual intervention needed."
>
> **PREVENT:** "The priority-ordered fallback chain means single-provider outages are handled automatically. For GraphAPI-exclusive operations like insights, we'd need to implement caching of the last known good data and return stale data during outages."

---

## Q2: "What if PostgreSQL becomes slow and task polling takes 10+ seconds?"

> **DETECT:** "Workers log 'Found Work' with timestamps. If the gap between poll cycles increases from 1s to 10s, we'd see it in logs. More visibly, task processing throughput would drop dramatically -- the PENDING queue would grow while workers idle."
>
> **IMPACT:** "All 150+ workers poll PostgreSQL every second. If each query takes 10s, workers are effectively idle 90% of the time. The scrape_request_log table would fill with PENDING tasks. Upstream API consumers would see timeouts waiting for scrape results."
>
> **MITIGATE:** "The `asyncio.sleep(1)` between polls means workers don't hammer the database in a tight loop. The semaphore backpressure (`while limit.locked(): await asyncio.sleep(30)`) reduces polling frequency when workers are busy. If PostgreSQL is slow because of connection exhaustion, the `pool_size` and `max_overflow` parameters limit our connection count."
>
> **RECOVER:** "Identify the root cause: (1) Missing index on (flow, status) -- add it. (2) Connection exhaustion -- enable PgBouncer (already used for assets pipeline). (3) Lock contention from too many workers -- reduce worker count for low-priority flows. (4) Table bloat -- VACUUM the scrape_request_log table."
>
> **PREVENT:** "Add PostgreSQL connection pool monitoring. Set alerts on query latency p99. The `pool_size=max_conc` setting already right-sizes connections per worker. Would add PgBouncer as a standard component between all workers and PostgreSQL."

---

## Q3: "What if all API credentials for Instagram get rate-limited simultaneously?"

> **DETECT:** "`CredentialManager.get_enabled_cred()` returns `None` for all sources. The crawler raises `NoAvailableSources('No source is available at the moment')`. Tasks fail with this error message in the scrape_request_log data column."
>
> **IMPACT:** "All Instagram scraping stops. YouTube and Shopify continue unaffected (different credentials). Tasks accumulate in PENDING state. Upstream consumers get FAILED responses."
>
> **MITIGATE:** "The `disabled_till` field is a TTL -- credentials automatically re-enable after the backoff period. If all credentials are disabled for 1 hour, scraping resumes after 1 hour without intervention. Tasks that failed can be retried by the upstream system."
>
> **RECOVER:** "Wait for TTL expiry. Or manually set `enabled=true, disabled_till=null` on credentials that are known to be healthy. Or add new credentials from additional provider accounts."
>
> **PREVENT:** "(1) Stagger credential usage so they don't all hit limits at the same time -- use the weighted random selection. (2) Add more credentials for each provider. (3) Monitor credential health: alert when >50% of credentials for a provider are disabled. (4) Implement progressive backoff -- first disable = 10 min, second = 30 min, third = 1 hour."

---

## Q4: "What if a worker process crashes and leaves tasks stuck in PROCESSING?"

> **DETECT:** "Tasks in PROCESSING state with `picked_at` older than 10 minutes. A monitoring query: `SELECT * FROM scrape_request_log WHERE status='PROCESSING' AND picked_at < now() - interval '10 minutes'`."
>
> **IMPACT:** "Those tasks are stuck forever. No other worker will pick them because `status = 'PROCESSING'`. The upstream consumer waits indefinitely for a result."
>
> **MITIGATE:** "The `check_and_cancel_long_running_tasks()` function cancels asyncio tasks after 10 minutes. But if the entire process crashes, the asyncio cleanup never runs."
>
> **RECOVER:** "Run a cleanup query: `UPDATE scrape_request_log SET status='PENDING' WHERE status='PROCESSING' AND picked_at < now() - interval '15 minutes'`. This requeues stuck tasks. Could also set them to FAILED if they shouldn't be retried."
>
> **PREVENT:** "Add a scheduled job (cron or separate process) that periodically requeues stuck PROCESSING tasks. The `expires_at` column already exists on scrape_request_log -- enforce it by adding `AND (expires_at IS NULL OR expires_at > NOW())` to the poll query, and a cleanup job that marks expired tasks as FAILED."

---

## Q5: "What if RabbitMQ goes down during peak scraping?"

> **DETECT:** "The `publish()` function uses kombu which raises `ConnectionError` on RabbitMQ unavailability. The error is caught by the exception handler in `make_scrape_log_event()` and logged."
>
> **IMPACT:** "Event publishing fails, but scraping continues. The data still reaches PostgreSQL. Downstream consumers (dashboard, notifications, analytics) stop receiving real-time updates. The scrape_request_log event publishing also fails, so the task lifecycle tracking becomes incomplete."
>
> **MITIGATE:** "Data is still written to PostgreSQL first, then events are published. If RabbitMQ is down, we lose the event but not the data. The `try/except` in every `emit_*_event()` function catches the exception and logs it without crashing the task."
>
> **RECOVER:** "When RabbitMQ comes back, new events flow normally. Events during the outage are lost. If downstream consumers need the missing data, they can query PostgreSQL directly -- the profile_log, post_log, and other audit tables have all the data."
>
> **PREVENT:** "(1) Add a dead-letter buffer: if publish fails, write to a local file or Redis queue, then replay when RabbitMQ recovers. (2) Use aio-pika's `connect_robust()` with auto-reconnection (already used for listeners). (3) Deploy RabbitMQ in a cluster with mirrored queues."

---

## Q6: "What if a new Instagram API provider returns malformed data?"

> **DETECT:** "The parser throws a `KeyError` or `TypeError`. The task fails and the exception is logged with the full traceback. The scrape_request_log status is set to FAILED with the error message."
>
> **IMPACT:** "Tasks using that provider fail. If it's the primary provider for a function type, the fallback chain tries the next provider. If parsing fails after the API call, the credential is still consumed (rate limit hit) but no data is saved."
>
> **MITIGATE:** "The fallback chain means other providers handle the load. The `@sessionize` decorator rolls back the database transaction, so no partial data is saved. The credential is not disabled -- a parse error is our bug, not a rate limit."
>
> **RECOVER:** "Fix the parser. Each provider has its own parser file (`arraybobo_parser.py`, etc.), so the fix is isolated. Deploy. Failed tasks can be retried by setting status back to PENDING."
>
> **PREVENT:** "(1) Add response schema validation before parsing -- check that expected keys exist. (2) Add integration tests that run against saved API response fixtures. (3) Version the parser alongside the API -- when a provider announces a change, update the parser in advance."

---

## Q7: "What if the S3 asset upload pipeline falls behind and 100K images are queued?"

> **DETECT:** "Growing PENDING count in scrape_request_log for `flow='asset_upload_flow'`. The `list_scrape_data` API endpoint shows the backlog."
>
> **IMPACT:** "Profile and post data is up-to-date (different pipeline), but thumbnail URLs point to expired Instagram CDN links instead of our CloudFront URLs. The dashboard shows broken images."
>
> **MITIGATE:** "The asset pipeline has 50 workers with 100 concurrency each -- up to 5,000 concurrent uploads. This is already heavily parallelized. The PgBouncer connection pooling (`pool_recycle=500`) prevents connection exhaustion."
>
> **RECOVER:** "Scale the workers: increase `no_of_workers` from 50 to 100. Or temporarily increase `no_of_concurrency` from 100 to 200. Monitor S3 rate limits -- S3 allows 3,500 PUT requests/sec per partition, which is far above our throughput."
>
> **PREVENT:** "(1) Monitor queue depth for asset_upload_flow specifically. Alert at 50K pending. (2) Implement priority: profile pictures (high visibility) before post thumbnails. (3) Consider CDN URL proxying as an alternative -- redirect through our domain to Instagram's CDN with on-demand caching."

---

## Q8: "What if you accidentally deploy a bug that corrupts Instagram profile data?"

> **DETECT:** "The `profile_log` table records every profile update with full dimension and metric snapshots. Compare current `instagram_account` data against recent `profile_log` entries. Anomaly detection: followers count suddenly zero, engagement rate negative, etc."
>
> **IMPACT:** "The dashboard shows incorrect data for affected profiles. Customers using the analytics platform see wrong follower counts, engagement rates, or audience demographics."
>
> **MITIGATE:** "The `profile_log` and `post_log` tables serve as an audit trail. Every data change is logged with the source and timestamp. We can identify which profiles were affected and when the corruption started."
>
> **RECOVER:** "
> 1. Deploy the fix immediately.
> 2. Use `profile_log` to find the last good snapshot for each affected profile.
> 3. Run a SQL UPDATE to restore correct values from the log.
> 4. Re-queue those profiles for a fresh scrape to get current data.
> The `upsert` pattern (get_or_create + set_attr) means we can overwrite corrupted data without creating duplicates."
>
> **PREVENT:** "(1) Add data validation before upsert -- reject obviously wrong values like negative follower counts. (2) Add a 'data quality score' that flags suspicious changes (followers dropped 90% in one update). (3) Staging environment testing with production data snapshots."

---

## Q9: "What if the daily rate limit (20K requests) is exhausted by noon?"

> **DETECT:** "The RateLimiter raises `RateLimitError` which is caught in the API endpoint handler. The endpoint returns 'Concurrency Limit Exceeded' with code 2. Monitoring: track the Redis counter for `refresh_profile_insta_daily`."
>
> **IMPACT:** "All on-demand Instagram profile requests through the API server are rejected for the rest of the day. Worker pool tasks are unaffected -- they use their own rate limiting at the HTTP client level, not the server-level stacked limiters."
>
> **MITIGATE:** "The per-minute limit (60/min) should prevent this scenario. At 60 req/min, the maximum daily consumption is 86,400 -- well within 20K if usage is spread across the day. If it happens, it means there was a burst that the per-minute limit didn't prevent."
>
> **RECOVER:** "Wait until midnight (UTC) when the daily counter resets. Or manually reset the Redis counter: `DEL beat_server_refresh_profile_insta_daily`."
>
> **PREVENT:** "(1) Add alerting at 50% and 80% of daily limit. (2) Implement a queue for non-urgent requests that processes during off-peak hours. (3) Differentiate between customer-facing (high priority) and batch (low priority) requests. (4) Consider a sliding window instead of fixed daily reset."

---

## Q10: "What if you need to add a completely new platform (TikTok) to Beat?"

> **DETECT:** "Product requirement, not a failure scenario. But the question tests whether the architecture is extensible."
>
> **IMPACT:** "No existing code should need to change. That's the test of good architecture."
>
> **MITIGATE (i.e., Implementation Plan):**
>
> "The architecture was designed for this. Here's what I'd need to create:
>
> 1. **New module**: `tiktok/` with the same structure as `instagram/`:
>    - `entities/entities.py` -- TikTokAccount, TikTokPost ORM models
>    - `models/models.py` -- TikTokProfileLog, TikTokPostLog data models
>    - `functions/retriever/interface.py` -- TikTokCrawlerInterface
>    - `functions/retriever/crawler.py` -- TikTokCrawler with provider registry
>    - `tasks/retrieval.py`, `ingestion.py`, `processing.py` -- 3-stage pipeline
>    - `flows/refresh_profile.py` -- Flow orchestration
>
> 2. **New entries in _whitelist**: `'refresh_tiktok_profiles': {'no_of_workers': 5, 'no_of_concurrency': 5}`
>
> 3. **New flow import in scraper.py**: Add `refresh_tiktok_profiles` to the _whitelist list and import.
>
> 4. **New rate specs in request.py**: TikTok API rate limits.
>
> 5. **New enum value**: Add `TIKTOK` to `enums.Platform`.
>
> Zero changes to main.py, server.py core logic, AMQP publishing, session management, or rate limiting infrastructure. The dimension/metric model means downstream analytics works automatically."
>
> **PREVENT (i.e., Design Validation):** "The fact that Instagram, YouTube, and Shopify all follow the same module structure -- with the same 3-stage pipeline, same interface pattern, same @sessionize decorator -- proves the architecture is platform-agnostic. Adding TikTok is ~2 weeks of work, not a redesign."
