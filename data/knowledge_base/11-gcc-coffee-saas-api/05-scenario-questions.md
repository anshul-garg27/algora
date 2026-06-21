# Scenario-Based "What If?" Questions - Coffee + SaaS Gateway

> Hiring managers LOVE these. They test if you truly understand your system under failure.
> Use the framework: DETECT -> IMPACT -> MITIGATE -> RECOVER -> PREVENT

---

## Q1: "What if Redis goes down and all session lookups fail?"

> **DETECT:** "Gateway auth middleware gets errors from `cache.Redis().Exists()`. Prometheus `requests_winkl` counter shows spike in 401 responses."
>
> **IMPACT:** "Every request that relies on Redis session validation fails. BUT the fallback chain saves us -- when Redis fails, the auth middleware falls through to the Identity service API call. Requests are SLOWER (50-100ms instead of 1-2ms) but NOT broken. Users stay authenticated."
>
> **MITIGATE:** "The Identity service fallback was designed exactly for this scenario. Ristretto L1 cache still serves hot sessions that were already cached in-memory -- those users see no impact at all. Only cold sessions (first request or infrequent users) hit the Identity service fallback."
>
> **RECOVER:** "When Redis recovers, new session lookups populate the Redis cache again. Ristretto continues serving hot sessions. Within minutes of Redis recovery, the normal fast path is restored."
>
> **PREVENT:** "Redis cluster with 3 nodes means single-node failure is already handled by Redis itself. For full cluster failure, we could add a local session cache with TTL as an additional layer, or implement circuit breaker pattern on the Redis client to fail fast to Identity service instead of waiting for connection timeouts."

---

## Q2: "What if a Coffee module's database transaction times out?"

> **DETECT:** "The `ServiceSessionMiddlewares` detects `context.DeadlineExceeded` when the timeout fires. The slow query logger has already logged the request (it started timing before the handler). Sentry receives the error with full request body via `GetSentryEvent`."
>
> **IMPACT:** "Single request fails with 504 Gateway Timeout. The user sees an error. BUT the critical part: both PostgreSQL and ClickHouse sessions are explicitly rolled back."
>
> **MITIGATE:** "The middleware does three things on timeout:
> 1. Calls `rollbackSessions(ctx)` -- rolls back both PG and CH transactions
> 2. Sends request details to Sentry for debugging
> 3. Returns 504 to the client
>
> Without explicit rollback, the database connection stays locked until the connection pool timeout, which could cascade -- other requests waiting for a connection from the pool also time out."
>
> **RECOVER:** "The rolled-back connection returns to the pool immediately. Next request gets a fresh connection. No persistent state is corrupted because the transaction was never committed."
>
> **PREVENT:** "Monitor slow query logs for patterns. The 5-second threshold in `SlowQueryLogger` catches requests approaching timeout. Optimize the slow queries or add database indexes. For legitimately long operations, consider making them async via the Watermill event system."

---

## Q3: "What if the Watermill/RabbitMQ connection drops?"

> **DETECT:** "Watermill's router logs connection errors. Listener goroutine logs `Unable to link listeners`. Publisher's `sync.Once` initialization fails on next publish attempt."
>
> **IMPACT:** "HTTP requests continue working normally -- event publishing uses after-commit callbacks, which are fire-and-forget. If the publish fails, the callback catches the error, but the HTTP response has already been sent. The database transaction is already committed. So: data is saved, event is lost."
>
> **MITIGATE:** "For the 7 listener handlers: they stop processing messages. RabbitMQ holds unacknowledged messages in the queue. When the connection recovers, messages are redelivered.
>
> For the publisher: the `sync.Once` singleton means the publisher was initialized at startup. If the underlying connection drops, the next `PublishMessage` call fails. The after-commit callback catches this error silently."
>
> **RECOVER:** "Watermill's AMQP transport handles reconnection automatically. The subscriber reconnects and resumes consuming from where it left off (unacked messages are redelivered). The publisher singleton needs the application to be restarted to reinitialize."
>
> **PREVENT:** "Add Prometheus counter for failed publish attempts. Implement the outbox pattern for critical events -- write events to a database table in the same transaction, poll and publish separately. This survives both application crashes and RabbitMQ outages."

---

## Q4: "What if a partner's contract expires mid-session?"

> **DETECT:** "The gateway checks contract dates on every authenticated request:
> ```go
> if currentTime.After(startTime) && currentTime.Before(endTime) {
>     planType = contract.Plan
> } else {
>     planType = 'FREE'
> }
> ```
> So the moment the contract expires, the next request gets `planType = FREE`."
>
> **IMPACT:** "The user's session continues working, but their plan type downgrades to FREE. Premium fields (email, phone, audience demographics) are no longer returned. Usage limits are enforced at FREE tier. No error is shown -- they just see less data."
>
> **MITIGATE:** "This is actually the DESIRED behavior. Expired contract = free tier. The user can still access the platform with limited features. It's a soft downgrade, not a hard lockout."
>
> **RECOVER:** "When the partner renews their contract, the next request picks up the new plan type. No cache invalidation needed because the gateway checks the contract dates on every request via the Partner service API."
>
> **PREVENT:** "The Partner service could send notifications before expiry. The SaaS frontend could show a warning banner. But from the gateway perspective, the contract-based check is intentionally stateless -- it always reflects the current truth."

---

## Q5: "What if someone tries to access another partner's data by spoofing the x-bb-partner-id header?"

> **DETECT:** "This is NOT possible in the current architecture. Here's why:
>
> The client never sets `x-bb-partner-id` directly. The gateway:
> 1. Parses the JWT token to get the user's claims
> 2. Extracts the partner ID from the JWT's `partnerId` claim
> 3. Validates against the Partner service
> 4. Sets `x-bb-partner-id` in the proxy Director function
>
> The proxy Director OVERWRITES all headers:
> ```go
> req.Header.Set(header.PartnerId, partnerId)  // From JWT, not from client
> ```
>
> Even if a client sends `x-bb-partner-id: 99999`, the gateway replaces it with the actual partner ID from the authenticated JWT."
>
> **IMPACT:** "None. The header enrichment in the reverse proxy is the security boundary."
>
> **PREVENT:** "The architecture inherently prevents this. The gateway is the ONLY entry point, and it ALWAYS overwrites tenant headers. Coffee trusts the gateway-set headers because the gateway is in the same private network."

---

## Q6: "What if the gateway's Ristretto cache grows beyond 1GB?"

> **DETECT:** "Ristretto self-manages. The `MaxCost: 1 << 30` (1GB) is a hard limit. When the cache reaches capacity, the TinyLFU admission policy rejects new entries and evicts least-frequently-used entries."
>
> **IMPACT:** "Cache hit rate decreases. More requests fall through to Redis (L2). Response latency increases slightly for cache misses -- from nanoseconds (L1) to milliseconds (L2). The system continues functioning normally, just slower."
>
> **MITIGATE:** "Ristretto's LFU eviction is smart -- it keeps the most frequently accessed sessions and evicts the rarely accessed ones. So the most active users (who generate the most load) still get L1 cache hits."
>
> **RECOVER:** "Self-recovering. As load patterns shift, the LFU policy naturally adapts. No manual intervention needed."
>
> **PREVENT:** "Monitor L1 cache hit rate via custom Prometheus metrics (if instrumented). If hit rate drops below 50%, consider increasing `MaxCost` or adding more gateway instances (which each have their own L1 cache). In production with 2 gateway nodes, each has its own 1GB Ristretto, so total L1 capacity is 2GB."

---

## Q7: "What if a new business module needs to query both PostgreSQL AND ClickHouse in the same request?"

> **DETECT:** "Not a failure scenario -- this is a normal feature request."
>
> **SOLUTION:** "The architecture already supports this. The RequestContext has BOTH sessions:
> ```go
> Session   persistence.Session    // PostgreSQL
> CHSession persistence.Session    // ClickHouse
> ```
>
> The Discovery module already does this -- `SearchManager` queries PostgreSQL for profile search, while `TimeSeriesManager` queries ClickHouse for growth data. Both within the same request.
>
> The ServiceSession middleware commits or rolls back both:
> ```go
> func closeSessions(ctx context.Context) {
>     session := ctx.Value(constants.AppContextKey).(*appcontext.RequestContext).GetSession()
>     if session != nil { session.Close(ctx) }
>     chSession := ctx.Value(constants.AppContextKey).(*appcontext.RequestContext).GetCHSession()
>     if chSession != nil { chSession.Close(ctx) }
> }
> ```
>
> The new module would initialize both sessions and use them within its Manager layer. The middleware handles the lifecycle."

---

## Q8: "What if you need to add a 14th microservice to the gateway?"

> **DETECT:** "Feature request, not failure."
>
> **SOLUTION:** "Adding a new service requires exactly ONE line of code:
> ```go
> router.Any('/new-service/*any', middleware.AppAuth(config), saas.ReverseProxy('new-service', config))
> ```
>
> The `ReverseProxy` function is parameterized by module name. It:
> 1. Routes to `SAAS_URL` by default (or `SAAS_DATA_URL` for data-heavy services)
> 2. Enriches headers with auth and tenant info
> 3. Proxies to `/{module}/{path}`
>
> No changes needed to auth middleware, caching, logging, or metrics -- they all apply globally. Deploy the gateway with the new route, and the new service is accessible."
>
> **CONSIDERATION:** "If the new service needs a different backend URL (like `social-profile-service`), add another condition in the proxy handler. If it needs different auth (e.g., public endpoints), create a route without `middleware.AppAuth`."

---

## Q9: "What if the Discovery module search returns millions of results?"

> **DETECT:** "The search would be slow. But it's prevented at multiple levels."
>
> **PROTECTION LAYERS:**
>
> "1. **Pagination caps:** `ParseSearchParameters` in `core/rest/utils.go` caps page at 1000 and size at 100:
> ```go
> if page >= 1000 { page = 1 }
> if size >= 100 { size = 50 }
> ```
> So the maximum results per request is 100 rows.
>
> 2. **Request timeout:** ServiceSession middleware enforces `SERVER_TIMEOUT`. If the query takes too long, the transaction is rolled back and 504 is returned.
>
> 3. **Slow query logger:** Queries exceeding 5 seconds are logged with full context for investigation.
>
> 4. **Database-level:** GORM's `Limit` and `Offset` translate to SQL `LIMIT/OFFSET`, so the database never loads millions of rows into memory."
>
> **IF IT STILL HAPPENS:** "If a search filter is too broad (e.g., no filters at all), the database does a full table scan limited to 100 rows. This is slow but bounded. We'd add required filters (like platform) to prevent filterless searches."

---

## Q10: "What if you need to deploy a breaking change to Coffee while the gateway is running?"

> **DETECT:** "This is a deployment coordination scenario."
>
> **APPROACH:**
>
> "1. **Backward-compatible changes first:** Add new endpoints alongside old ones. The gateway routes by path prefix, so `/discovery-service/api/v2/search` and `/discovery-service/api/search` can coexist.
>
> 2. **Rolling deployment with heartbeat:**
>    - Node 1: `PUT /heartbeat/?beat=false`, wait 15s, deploy new Coffee, `PUT /heartbeat/?beat=true`
>    - Node 2: Same process
>    - During deployment, the other node handles all traffic
>
> 3. **Gateway doesn't need changes for additive changes:** New endpoints, new fields in responses, new modules -- the gateway proxies everything through. Only breaking path changes require gateway updates.
>
> 4. **If truly breaking:** Deploy the gateway change first (it handles unknown paths gracefully -- they just 404 at Coffee). Then deploy Coffee with the new paths."
>
> **PREVENTION:** "API versioning in path prefixes. The current structure (`/discovery-service/api/...`) makes it easy to add `/api/v2/` alongside `/api/`. The gateway's wildcard routing (`/*any`) handles any sub-path."
