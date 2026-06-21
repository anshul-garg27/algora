# Interview Q&A - Coffee + SaaS Gateway

> Organized by topic. For each question: Model answer + code reference + follow-up handling.

---

## MULTI-TENANCY

### Q1: "How did you implement multi-tenancy in Coffee?"

> "Coffee uses a three-level tenant hierarchy: Partner, Account, and User. Every request carries these as HTTP headers -- `x-bb-partner-id`, `x-bb-account-id`, and user info encoded in the Authorization header.
>
> The gateway extracts these from the JWT token and enriches the request headers before proxying to Coffee. Inside Coffee, the `ApplicationContext` middleware reads these headers and builds a `RequestContext` struct that flows through the entire request lifecycle via Go's `context.Context`.
>
> The key insight is that the Partner is the paying entity -- they have a plan type (FREE, SAAS, PAID) that gates which features and data fields are accessible. Individual users within a partner all share the same plan tier."

**Code reference:** `core/appcontext/requestcontext.go` lines 46-62

**Follow-up: "How do you prevent data leakage between tenants?"**
> "Every database query includes the partner ID as a filter -- it's part of the search predicate at the DAO layer. The RequestContext carries the partner ID, and each module's DAO implementation uses it when building GORM queries. Additionally, the gateway validates the partner ID against the JWT claims, so a user can't spoof another partner's ID."

---

### Q2: "How does the plan-based feature gating work end to end?"

> "The flow is: the user authenticates via JWT, the gateway parses the token and extracts the partner ID, then calls the Partner service to get the partner's SAAS contracts. It checks if the current time falls within the contract's start and end dates. If yes, the plan type is the contract's plan (PRO, BUSINESS, etc.). If the contract is expired, it defaults to FREE.
>
> This plan type is set as an `x-bb-plan-type` header on the proxied request. Coffee's ApplicationContext middleware reads this header and stores it in the RequestContext. Business modules then check `ctx.PlanType` to decide what data to expose.
>
> For free users, premium fields like email, phone, and audience demographics are nullified before sending the response."

**Code reference:** `middleware/auth.go` lines 83-91 (gateway), `core/appcontext/requestcontext.go` lines 75-89 (coffee)

---

### Q3: "What's the Authorization header format and why?"

> "It's a Base64-encoded string in the format: `userId~userName~isLoggedIn~accountId:password`. This was a design inherited from the platform -- the gateway generates this from the JWT claims and Identity service response.
>
> The tilde-separated format allows Coffee to parse out user info without making another auth call. The `isLoggedIn` flag (0 or 1) distinguishes between device-level access (anonymous) and user-level access (authenticated). For anonymous users, the userId field contains the device ID instead.
>
> This is essentially a pre-computed auth context that the gateway passes downstream, so Coffee doesn't need to re-validate the JWT or call the Identity service again."

**Code reference:** `core/appcontext/requestcontext.go` lines 188-222 (parsing), `context/context.go` lines 152-166 (generation)

---

## API DESIGN

### Q4: "Walk me through how a request flows from the client to the database and back."

> "Let me trace a profile search request:
>
> 1. **Client** sends POST to `https://gateway/discovery-service/api/profile/instagram/search`
> 2. **Gateway middleware pipeline** (7 layers): Recovery, Sentry, CORS check, context injection, request ID generation, logging, then AppAuth validates JWT + Redis session
> 3. **Gateway reverse proxy** enriches headers (partner ID, plan type, device ID) and proxies to Coffee at `SAAS_URL/discovery-service/api/profile/instagram/search`
> 4. **Coffee middleware pipeline** (10 layers): Request interceptor captures body, slow query logger starts timer, Sentry integration, ApplicationContext extracts headers into RequestContext, ServiceSession starts a PostgreSQL transaction with timeout
> 5. **Discovery API handler** parses the search body (filters, pagination), calls Discovery Service
> 6. **Discovery Service** (generic) calls Discovery Manager's Search method
> 7. **Discovery Manager** (SearchManager specifically) calls DAO.Search with the filters
> 8. **Discovery DAO** translates SearchFilters into GORM where clauses, executes against PostgreSQL (or ClickHouse for analytics queries), returns entities
> 9. **Manager** converts entities to entries using `toEntry` function
> 10. **Service** wraps entries in the response DTO with pagination cursor
> 11. **Middleware** commits the transaction (or rolls back on error/timeout), executes after-commit callbacks
> 12. **Response** flows back through the proxy to the client"

---

### Q5: "Why did you choose cursor-based pagination?"

> "The Search method in the generic Service uses cursor-based pagination:
>
> ```go
> if len(entries) >= size {
>     nextCursor = strconv.Itoa(page + 1)
> } else {
>     nextCursor = ""
> }
> ```
>
> If the result count equals the page size, there's a next page. The cursor is the next page number. This is simpler than offset-based pagination for our use case because:
>
> 1. Social media data changes constantly -- offsets can cause duplicates or skips when new profiles are added between requests
> 2. The client just passes `cursor=N` for the next page -- no need to track total counts
> 3. We also cap page at 1000 and size at 100 to prevent abuse -- if someone passes `page=999999`, we reset to 1"

**Code reference:** `core/rest/service.go` lines 71-83, `core/rest/utils.go` lines 43-85

---

### Q6: "How does the generic search/filter system work?"

> "Every search endpoint uses the same SearchQuery model:
>
> ```go
> type SearchQuery struct {
>     Filters []SearchFilter `json:"filters"`
> }
> type SearchFilter struct {
>     FilterType string `json:"filterType"`   // EQ, GTE, LTE, LIKE, IN
>     Field      string `json:"field"`
>     Value      string `json:"value"`
> }
> ```
>
> The client sends a POST with a JSON body like `{filters: [{filterType: "GTE", field: "followers", value: "10000"}]}`. The DAO layer translates each filter into a GORM where clause. Each module's DAO implements `AddPredicateForSearchJoins` for custom filter logic -- for example, the Discovery DAO maps audience demographic filters like `audience_gender=MALE` to JSONB path queries like `audience_gender.male_per >= 40`.
>
> This generic filter system means we can add new filter fields without changing any framework code -- just update the DAO's predicate builder."

**Code reference:** `core/domain/types.go` lines 30-37, `core/rest/utils.go` lines 208-231

---

## CACHING

### Q7: "Explain the two-layer caching strategy in the gateway."

> "Layer 1 is Ristretto, an in-memory LFU cache from Dgraph. It's configured for 10 million key slots and 1GB max memory. It uses TinyLFU as its admission policy, which means it only caches keys that are accessed frequently -- a random one-time session lookup won't pollute the cache.
>
> Layer 2 is Redis cluster with 3 nodes and a 100-connection pool. Session data lives here as `session:{sessionId}` keys.
>
> The lookup order is: Ristretto (nanoseconds) -> Redis (milliseconds) -> Identity service (50-100ms). When Redis returns a hit, we also populate Ristretto so the next request is served from memory.
>
> The key trade-off is consistency. Ristretto is per-instance -- if a user logs out, we delete from Redis, but the Ristretto cache on each gateway node might still have the old session for a few seconds until TTL or LFU eviction kicks in."

**Code reference:** `cache/ristretto.go` lines 14-23, `cache/redis.go` lines 14-23, `middleware/auth.go` lines 61-62

**Follow-up: "What's the cache hit rate?"**
> "For active users, the Ristretto hit rate should be very high -- active users make multiple requests per session, and Ristretto's LFU policy keeps hot sessions in memory. The Redis layer catches the long-tail of less frequent users. In production, I'd estimate 60-70% L1 hit rate, 95%+ L1+L2 combined hit rate."

---

### Q8: "How does ClickHouse complement PostgreSQL?"

> "PostgreSQL handles OLTP -- all the transactional operations like creating collections, updating profiles, managing relationships. It has 27+ tables with foreign keys, indexes, and GORM-managed transactions.
>
> ClickHouse handles OLAP -- time-series data like follower growth over time, leaderboard aggregations, engagement rate calculations across millions of profiles. These are read-heavy, scan-heavy queries that would slow down PostgreSQL.
>
> In Coffee, both databases are managed through the same session middleware. The RequestContext has both `Session` (PostgreSQL) and `CHSession` (ClickHouse). The middleware commits or rolls back BOTH on request completion.
>
> The Discovery module is the main consumer of ClickHouse -- the `TimeSeriesManager` queries ClickHouse for growth data, while the `SearchManager` queries PostgreSQL for profile search."

**Code reference:** `core/appcontext/requestcontext.go` lines 59-60, `server/middlewares/session.go` lines 55-75

---

## GATEWAY ARCHITECTURE

### Q9: "Why does social-profile-service route to a different backend?"

> "The `social-profile-service` handles raw social media profile data -- Instagram accounts with 100+ columns, YouTube channels with millions of rows. This is the heaviest data service in the platform.
>
> By routing it to `SAAS_DATA_URL` instead of `SAAS_URL`, we get:
> 1. Independent scaling -- the data service can have more replicas without affecting other services
> 2. A separate database replica optimized for read-heavy analytics queries
> 3. Network isolation -- heavy scan queries don't compete with lightweight CRUD on other services
> 4. Independent deployment -- we can upgrade the data service without touching the other 12 services
>
> The routing is a one-line check in the proxy handler -- simple but effective."

**Code reference:** `handler/saas/saas.go` lines 45-48

---

### Q10: "How does the gateway handle CORS for 41 origins?"

> "The gateway has an explicit whitelist of 41 origins -- production domains, staging domains, beta environments, local development, and external sites like instagram.com and youtube.com. We use the `rs/cors` library wrapped for Gin.
>
> All 7 HTTP methods are allowed, all headers are allowed (`*`), and credentials are enabled. For OPTIONS preflight requests, the proxy's `responseHandler` explicitly sets the `Access-Control-Allow-Origin` header from the request's origin, and for non-OPTIONS requests, it removes the header to prevent conflicts with the CORS middleware.
>
> The whitelist approach over wildcard (`*`) is necessary because we need `AllowCredentials: true` for JWT cookie support, and the CORS spec forbids `*` with credentials."

**Code reference:** `router/router.go` lines 22-73, `handler/saas/saas.go` lines 19-40

---

## EVENT-DRIVEN ARCHITECTURE

### Q11: "How does the event system work in Coffee?"

> "Coffee uses Watermill with AMQP (RabbitMQ) for event-driven processing. There are two sides:
>
> **Publishing:** Events are queued in the RequestContext's event store during request processing. After the database transaction commits, the `PerformAfterCommit` callback fires, iterating through the event store and calling `Apply()` on each event. This ensures we never publish events for rolled-back transactions.
>
> **Consuming:** Seven listener handlers are registered on Watermill's router, each subscribed to a specific queue. The listener router has its own middleware chain -- message context extraction, transaction session management, retry (3 attempts, 100ms backoff), and panic recovery. This means each message handler gets its own database transaction, just like HTTP handlers.
>
> The topic naming convention `exchange___queue` (triple underscore) encodes both RabbitMQ exchange and queue in a single string, which Watermill's config generators split at runtime."

**Code reference:** `listeners/listeners.go` lines 26-71, `publishers/publisher.go` lines 17-31, `amqp/config.go` lines 9-62

**Follow-up: "What happens if a message handler fails?"**
> "The retry middleware retries up to 3 times with 100ms initial interval. If all retries fail, the message is nacked and RabbitMQ handles dead-lettering based on queue configuration. The recoverer middleware catches panics and converts them to errors, which the retry middleware then handles."

---

### Q12: "How do you handle database timeouts?"

> "The ServiceSession middleware creates a context with a configurable timeout (`SERVER_TIMEOUT` config). The handler runs within this timeout context. When the deadline is exceeded:
>
> 1. The deferred function detects `context.DeadlineExceeded`
> 2. Both PostgreSQL and ClickHouse sessions are rolled back
> 3. The request body is captured and sent to Sentry for debugging
> 4. A 504 Gateway Timeout is returned to the client
>
> This is important because without explicit rollback, the database connection stays locked until the connection pool timeout. By rolling back immediately on timeout, we return the connection to the pool and prevent cascade failures."

**Code reference:** `server/middlewares/session.go` lines 22-53

---

## OBSERVABILITY

### Q13: "What observability did you build into the system?"

> "Four layers of observability:
>
> 1. **Prometheus metrics:** Coffee uses chi-prometheus with custom buckets (300ms to 30s). The gateway has custom counters -- `requests_winkl` tracks every proxied request with method, path, channel, and response status labels.
>
> 2. **Sentry error tracking:** Both systems have Sentry integration. Coffee captures panics with stack traces AND captures non-200 responses with the full request body. The gateway's Sentry includes all `x-bb-*` headers as tags for debugging.
>
> 3. **Structured logging:** Coffee uses Logrus with JSON formatter. The gateway uses Zerolog for high-performance logging with request ID correlation. Both systems propagate `x-bb-requestid` through the entire chain for distributed tracing.
>
> 4. **Slow query logging:** Coffee logs any request exceeding 5 seconds to a dedicated daily log file with the full request body and headers."

**Code reference:** `server/server.go` line 120 (prometheus), `server/middlewares/sentrylogger.go` (sentry), `server/middlewares/slowquerylogger.go` (slow queries)

---

### Q14: "How does the health check-based deployment work?"

> "Both Coffee and the gateway expose `/heartbeat/` GET (check) and PUT (toggle). The deployment script:
>
> 1. `PUT /heartbeat/?beat=false` -- Takes the instance out of the load balancer
> 2. `sleep 15` -- Waits for in-flight requests to complete
> 3. `kill -9 $PID` -- Kills the old process
> 4. Start new binary with correct ENV
> 5. `sleep 20` -- Waits for the new process to initialize
> 6. `PUT /heartbeat/?beat=true` -- Puts the instance back in the load balancer
>
> Production has 2 nodes (cb1-1, cb2-1) deployed manually one at a time, ensuring at least one node is always serving traffic. The `GOGC=250` setting in CI reduces garbage collection frequency for the gateway."

**Code reference:** `scripts/start.sh` (both repos), `.gitlab-ci.yml` (both repos)

---

## GENERIC FRAMEWORK

### Q15: "How much boilerplate did Go generics eliminate?"

> "Without generics, each of the 12 modules would need its own Service, Manager, and Dao implementation -- that's 36 files of mostly identical code. With generics, the core framework is 6 files totaling about 300 lines. Each module only implements:
>
> 1. The `DaoProvider` interface (custom query logic)
> 2. Two converter functions: `toEntity` and `toEntry`
> 3. The API handler (HTTP routes)
>
> The generic constraints are minimal:
> ```go
> type ID interface{ ~int64 | ~string }
> type Entry interface{}
> type Entity interface{}
> type Response interface{}
> ```
>
> The `~int64 | ~string` constraint on ID allows modules to use either integer or string IDs. The empty interfaces for Entry/Entity/Response are necessary because Go generics don't yet support method constraints on struct types. The real type safety comes from the parameterized struct definitions, not the constraint interfaces."

**Code reference:** `core/domain/types.go` lines 8-24, `core/rest/service.go`, `core/rest/manager.go`, `core/rest/dao_provider.go`
