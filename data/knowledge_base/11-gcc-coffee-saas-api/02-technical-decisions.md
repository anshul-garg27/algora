# Technical Decisions Deep Dive - Coffee + SaaS Gateway

> For each decision: What we chose, what we rejected, WHY, and the trade-off.
> These are the "Why X not Y?" questions interviewers love.

---

## Decision 1: Why Go Generics for the REST Framework?

### What We Chose
Go 1.18 generics with `Service[RES, EX, EN, I]`, `Manager[EX, EN, I]`, and `DaoProvider[EN, I]` -- four type parameters constraining every layer.

### What We Rejected
1. **Interface-based polymorphism** (pre-generics Go pattern): `interface{}` everywhere with type assertions
2. **Code generation** (e.g., `go generate` with templates)
3. **Reflection-based ORM** (like Java Spring Data)

### Why Generics Won
```go
// WITHOUT generics (what we'd have had):
func (s *Service) Create(ctx context.Context, entry interface{}) (interface{}, error) {
    // Type assertion everywhere -- runtime panic if wrong type
    e := entry.(*ProfileCollectionEntry)  // UNSAFE
}

// WITH generics (what we built):
func (r *Service[RES, EX, EN, I]) Create(ctx context.Context, entry *EX) RES {
    // Compile-time type safety -- wrong type = compile error
    createdEntry, err := r.manager.Create(ctx, entry)  // SAFE
}
```

**The real reason:** We had 12 modules to build. Without generics, each module would need its own Service, Manager, and DAO implementations -- roughly 36 boilerplate files. With generics, the core framework is 6 files (`api.go`, `service.go`, `manager.go`, `dao.go`, `dao_provider.go`, `container.go`), and each module only implements the `DaoProvider` interface and converter functions (`toEntity`, `toEntry`).

### Trade-off
- Go generics are less powerful than Java/C# generics (no variance, no type erasure tricks)
- Error messages involving generics can be cryptic
- Team had to learn Go 1.18 features

### Follow-up: "Would you do it differently today?"
> "No, this was the right call. The ROI was massive -- 12 modules with consistent patterns. If Go had generics from day one, I'd have used them from day one. The only thing I might change is adding method constraints (Go 1.21+ interface methods) for stricter Entry/Entity contracts."

---

## Decision 2: Why 4-Layer Architecture vs 3-Layer (No Manager)?

### What We Chose
API -> Service -> **Manager** -> DAO (four layers)

### What We Rejected
API -> Service -> DAO (three layers, standard for most Go REST APIs)

### Why the Manager Layer Exists
The Manager owns TWO things that don't belong in Service or DAO:

1. **Data transformation** (`toEntity` and `toEntry` converter functions)
2. **Business logic enforcement** (validation rules, field masking, derived calculations)

```go
// Manager owns the mapping:
type Manager[EX domain.Entry, EN domain.Entity, I domain.ID] struct {
    dao      *Dao[EN, I]
    toEntity func(*EX) (*EN, error)    // Entry -> Entity (for writes)
    toEntry  func(*EN) (*EX, error)    // Entity -> Entry (for reads)
}
```

Without the Manager, the Service would need to know about both DTOs and entities, violating single responsibility. The DAO should only deal with entities (database rows), not business DTOs.

In complex modules like Discovery, the Manager layer is even more critical:
- `SearchManager` -- Profile search with audience demographic filters
- `TimeSeriesManager` -- Growth data over time (ClickHouse)
- `HashtagsManager` -- Hashtag frequency analytics
- `AudienceManager` -- Demographic data with JSONB path queries

### Trade-off
- Extra layer adds indirection for simple CRUD modules
- New developers need to understand which logic goes where

### Follow-up: "When would you NOT use 4 layers?"
> "For simple microservices with only CRUD and no data transformation, 3 layers is fine. The Manager layer pays for itself when you have complex mapping logic, multiple sub-managers per domain (like Discovery), or when Entry and Entity diverge significantly."

---

## Decision 3: Why Watermill vs Direct RabbitMQ Client?

### What We Chose
Watermill framework (`github.com/ThreeDotsLabs/watermill`) with AMQP transport

### What We Rejected
1. **Direct `streadway/amqp` client** -- Go's standard RabbitMQ library
2. **NATS** -- Simpler pub/sub
3. **Kafka** -- Heavier event streaming

### Why Watermill Won

Watermill provides a middleware chain for message handlers -- the SAME pattern we use for HTTP:

```go
router.AddMiddleware(
    middlewares.MessageApplicationContext,      // Extract context from message
    middlewares.TransactionSessionHandler,      // Transaction management
    middleware.Retry{MaxRetries: 3, InitialInterval: 100ms}.Middleware,
    middlewares.Recoverer,                      // Panic recovery
)
```

With direct `streadway/amqp`, we would have had to build:
- Message context extraction (re-creating RequestContext from message metadata)
- Transaction management per message handler
- Retry logic with backoff
- Panic recovery
- Router pattern matching

Watermill gave us all of this with the same mental model as HTTP middleware.

### The Naming Convention

Our topic naming `exchange___queue` (triple underscore separator) encodes both exchange and queue in a single string:

```go
routingKeyGen := func(topic string) string { return strings.Split(topic, "___")[1] }
exchangeGen := func(topic string) string { return strings.Split(topic, "___")[0] }
```

This is a Watermill-specific pattern -- it uses topic strings as the primary abstraction, and we encode RabbitMQ's exchange/queue/routing-key concepts into that single string.

### Trade-off
- Watermill adds a dependency (~10KB binary size impact)
- The `___` naming convention is unconventional
- Less control over AMQP channel management

### Follow-up: "Why RabbitMQ over Kafka?"
> "RabbitMQ was already in the GCC infrastructure. The use case is point-to-point work queues (collection updates, profile refresh), not event streaming. RabbitMQ's push-based delivery with acknowledgments fits better than Kafka's pull-based consumer groups for our workload."

---

## Decision 4: Why Chi Router for Coffee vs Gin for Gateway?

### What We Chose
- **Coffee:** `go-chi/chi` v5
- **Gateway:** `gin-gonic/gin` v1.8.1

### Why Two Different Routers?

**Coffee chose Chi because:**
1. Chi is `net/http` compatible -- middleware is `func(http.Handler) http.Handler`
2. Our custom session middleware needs to wrap `http.Handler` and control commit/rollback
3. Chi's middleware composability is better for complex pipelines (10 layers)
4. Chi uses the standard `context.Context` -- our `RequestContext` lives in the standard context

```go
// Chi middleware signature -- standard net/http:
func ApplicationContext(next http.Handler) http.Handler {
    fn := func(w http.ResponseWriter, r *http.Request) {
        appCtx, _ := appcontext.CreateApplicationContext(ctx, r)
        newCtx := context.WithValue(ctx, constants.AppContextKey, &appCtx)
        next.ServeHTTP(w, r.WithContext(newCtx))
    }
    return http.HandlerFunc(fn)
}
```

**Gateway chose Gin because:**
1. The gateway is simpler -- just proxy + auth + logging
2. Gin has built-in recovery, request binding, context management
3. Gin's `c.Next()` / `c.Abort()` flow is simpler for auth middleware
4. Sentrygin integration is first-party with Gin
5. Gin was the existing standard at GCC when the gateway was built

### Trade-off
- Two router libraries means different middleware patterns across projects
- New developers switching between projects need to adapt

### Follow-up: "Would you standardize on one?"
> "If starting fresh, I'd use Chi everywhere -- it's more idiomatic Go and gives better control for complex middleware. But migrating the gateway from Gin to Chi wasn't worth the risk for a working production system."

---

## Decision 5: Why Ristretto + Redis Two-Layer Cache?

### What We Chose
- **Layer 1:** Ristretto in-memory cache (10M keys, 1GB, LFU eviction)
- **Layer 2:** Redis cluster (3 nodes, 100 connection pool)

### What We Rejected
1. **Redis only** -- Single layer distributed cache
2. **Ristretto only** -- Single layer in-memory cache
3. **Memcached** -- Simpler distributed cache

### Why Two Layers

The gateway handles every request to the platform. The critical path is:

```
Request --> Parse JWT --> Check session exists --> Proxy to backend
```

Session lookup is the bottleneck. With Redis only:
- Every request = 1 network round trip to Redis (~1-2ms)
- At high load, Redis becomes the bottleneck

With Ristretto + Redis:
- Hot sessions (active users) are in Ristretto: **nanosecond** lookup, zero network
- Cold sessions fall through to Redis: **millisecond** lookup
- Cache miss from both = Identity service API call (expensive, ~50-100ms)

```
Request --> [Ristretto: nanoseconds] --> HIT? Return
                     |
                     v MISS
            [Redis: milliseconds] --> HIT? Return + populate Ristretto
                     |
                     v MISS
            [Identity Service: 50-100ms] --> Return + populate both
```

### Why Ristretto Specifically
```go
ristretto.NewCache(&ristretto.Config{
    NumCounters: 1e7,     // Track frequency of 10M keys
    MaxCost:     1 << 30, // Cap at 1GB memory
    BufferItems: 64,      // Batch 64 keys per Get buffer
})
```

Ristretto uses TinyLFU admission policy -- it only admits keys that are accessed frequently enough. Random one-time requests don't pollute the cache. This is critical for a gateway where some sessions are accessed 100x/minute and others once/hour.

### Trade-off
- Ristretto is per-instance: session invalidation must happen in Redis (shared), and Ristretto will serve stale data until TTL expires or eviction occurs
- Two layers add complexity to debugging cache behavior
- 1GB memory per gateway instance dedicated to caching

### Follow-up: "How do you handle cache invalidation?"
> "Redis is the source of truth. Ristretto has no explicit invalidation -- it relies on TTL and LFU eviction. For session revocation (logout, password change), we delete from Redis. Ristretto will serve the stale session until its natural eviction. In practice, this is a few seconds at most, and the trade-off is worth it for the latency reduction."

---

## Decision 6: Why JWT + Redis Session vs Pure Token Validation?

### What We Chose
JWT tokens with session ID claim (`sid`), validated against Redis cluster

### What We Rejected
1. **Pure JWT (stateless)** -- Validate only the JWT signature, no server-side state
2. **Opaque tokens** -- No JWT, just random tokens with server-side lookup
3. **OAuth2 + refresh tokens** -- Standard OAuth2 flow

### Why JWT + Redis

Pure JWT has a fatal flaw for SaaS: **you cannot revoke a session**. If a user changes their password or an admin deactivates an account, the JWT is still valid until expiry.

Our approach:
```go
// JWT contains: uid, sid, userAccountId, partnerId
claims["sid"]  // Session ID

// Redis key: "session:{sid}"
// EXISTS check is O(1) -- just checks key existence
cache.Redis(gc.Config).Exists("session:" + sessionId)
```

This gives us:
- **JWT benefits:** Self-contained claims (userId, partnerId) -- no database lookup to know WHO the user is
- **Server-side control:** Delete `session:{sid}` from Redis = instant session revocation
- **Performance:** Redis EXISTS is O(1), sub-millisecond

### The Fallback Chain

```
JWT valid? --> Redis session exists? --> YES: proceed
                                    --> NO: call Identity service
                                            --> YES: proceed (Redis was stale)
                                            --> NO: 401 Unauthorized
```

The Identity service fallback handles the case where Redis was flushed or the session was created on a different cluster. This is a resilience pattern -- Redis is the fast path, Identity is the authoritative path.

### Trade-off
- Every request touches Redis (mitigated by Ristretto L1 cache)
- JWT payload is larger (contains claims) vs opaque token
- Session state means horizontal scaling needs shared Redis

---

## Decision 7: Why Reverse Proxy vs API Composition?

### What We Chose
`httputil.NewSingleHostReverseProxy` -- direct proxy pass-through with header enrichment

### What We Rejected
1. **API Composition** (BFF pattern) -- Gateway makes multiple service calls, assembles response
2. **GraphQL Gateway** -- Schema stitching across services
3. **gRPC Gateway** -- Protocol translation

### Why Reverse Proxy

```go
proxy := httputil.NewSingleHostReverseProxy(remote)
proxy.Director = func(req *http.Request) {
    req.Header = c.Request.Header              // Pass through ALL headers
    req.Header.Set("Authorization", authHeader) // Enrich auth
    req.Header.Set(header.PartnerId, partnerId) // Enrich tenant
    req.URL.Path = "/" + module + c.Param("any") // Route to service
}
proxy.ServeHTTP(c.Writer, c.Request)
```

The gateway's job is AUTH + ROUTING + ENRICHMENT, not business logic. Each Coffee module already returns complete responses. There is no need to compose data from multiple services for a single response.

Benefits:
- **Zero business logic in gateway** -- Gateway never parses response bodies
- **Any HTTP method works** -- `router.Any()` catches GET, POST, PUT, DELETE, PATCH
- **Streaming support** -- Large responses stream through without buffering
- **Low memory** -- No response body parsing/assembly

### Trade-off
- Cannot aggregate data from multiple services in one call
- Client must make multiple requests for composite views
- No response transformation (filtering fields, reshaping JSON)

### Follow-up: "What if you needed aggregation?"
> "I would add specific composition endpoints at the gateway level for those cases, while keeping the default as reverse proxy. Most client needs are served by individual service endpoints. The 80/20 rule: 80% of requests are single-service, optimize for that."

---

## Decision 8: Why Plan-Based Feature Gating vs Role-Based?

### What We Chose
Three plan tiers: `FREE`, `SAAS`, `PAID` -- determined by partner's SAAS contract

### What We Rejected
1. **RBAC (Role-Based Access Control)** -- User roles with permissions
2. **Feature flags** (LaunchDarkly style) -- Per-feature toggles
3. **Attribute-based access control (ABAC)** -- Complex policy rules

### Why Plan-Based

The platform's monetization is SaaS subscriptions per company (partner), not per user:

```go
// Gateway determines plan from partner contract:
for _, contract := range partnerDetail.Contracts {
    if contract.ContractType == "SAAS" {
        currentTime := time.Now()
        startTime := time.Unix(0, contract.StartTime*int64(time.Millisecond))
        endTime := time.Unix(0, contract.EndTime*int64(time.Millisecond))
        if currentTime.After(startTime) && currentTime.Before(endTime) {
            planType = contract.Plan
        } else {
            planType = "FREE"    // Expired contract = free tier
        }
    }
}
```

The plan type flows through as `x-bb-plan-type` header. Coffee uses it to:
- Gate premium data fields (email, phone, audience demographics) for free users
- Enforce usage limits per module (`PartnerLimitModules`)
- Track profile page access counts (`partner_profile_page_track` table)

### Why Not RBAC
Individual users within a partner don't have different access levels -- the PARTNER is the paying entity. All users under a paid partner get paid features. RBAC would add complexity without matching the business model.

### Trade-off
- No per-user permission granularity
- Cannot A/B test features for individual users
- Plan changes require contract updates, not just flag flips

---

## Decision 9: Why Separate SAAS_DATA_URL for social-profile-service?

### What We Chose
Two backend URLs: `SAAS_URL` (12 services) and `SAAS_DATA_URL` (1 service)

### Why the Split
```go
func ReverseProxy(module string, config config.Config) func(c *gin.Context) {
    return func(c *gin.Context) {
        saasUrl := config.SAAS_URL
        if module == "social-profile-service" {
            saasUrl = config.SAAS_DATA_URL    // Different backend!
        }
    }
}
```

`social-profile-service` is the heaviest service -- it serves raw social media profile data (Instagram accounts with 100+ columns, YouTube channels, engagement metrics). It needs:
- **Separate scaling:** This service handles the most data-intensive queries
- **Different database backend:** Likely connects to a different PostgreSQL replica optimized for reads
- **Independent deployment:** Can be updated without affecting the other 12 services
- **Network isolation:** Heavy analytics queries don't compete with lightweight CRUD traffic

### Trade-off
- Two URLs to configure and monitor
- Slightly more complex deployment
- Gateway routing logic for one exception case

---

## Decision 10: Why After-Commit Callbacks vs Sync Event Publishing?

### What We Chose
Events are queued during request processing and published ONLY after the database transaction commits successfully.

### What We Rejected
1. **Synchronous publish** -- Publish event, then commit transaction
2. **Outbox pattern** -- Write event to database table, separate process publishes
3. **Saga pattern** -- Distributed transaction across event and database

### Why After-Commit

```go
// core/appcontext/requestcontext.go
func (c *RequestContext) SetSession(ctx context.Context, session persistence.Session) {
    c.Session = session
    c.Session.PerformAfterCommit(ctx, c.applyEvents)
}

func (c *RequestContext) applyEvents(ctx context.Context) {
    eventStore := appContext.GetValue("event_store").([]event.Event)
    for i := range _store {
        _store[i].Apply()
    }
}
```

The problem with sync publish:
```
1. Save to DB
2. Publish event  <-- What if this fails?
3. Commit DB      <-- Data saved, but event lost

OR:
1. Publish event  <-- What if DB fails after this?
2. Save to DB
3. Commit DB      <-- Event published, but data not saved
```

After-commit callbacks guarantee:
- If the transaction rolls back (timeout, error), no events are published
- Events are only published for data that actually persisted
- The callback runs synchronously after commit, so any publish failure can be logged

### Trade-off
- If the process crashes between commit and callback execution, events are lost
- Events are NOT in the same transaction as the database write (no exactly-once)
- The outbox pattern would be more reliable but adds a polling mechanism

### Follow-up: "What about the outbox pattern?"
> "The outbox pattern writes events to a database table in the same transaction, then a separate process polls and publishes. It gives exactly-once semantics but adds latency (polling interval) and infrastructure (outbox table, poller process). For our use case -- collection updates, profile refreshes -- occasional lost events are acceptable because the next user action triggers a fresh event. If we needed financial-grade reliability, I'd switch to outbox."
