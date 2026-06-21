# Coffee + SaaS Gateway -- Complete Interview Master Guide

> **Resume Bullets:**
> - "Optimized API response times by 25% and reduced operational costs by 30%"
> - "Developed real-time social media insights modules, driving 10% user engagement growth" (Genre Insights, Keyword Analytics)
>
> **Company:** Good Creator Co. (GCC) -- goodcreator.co
> **Repos:** `coffee` (8,500+ LOC), `saas-gateway` (2,200+ LOC)

---

## Pitches

### 30-Second Pitch

> "At Good Creator Co., I built the core backend for a SaaS influencer analytics platform. The main system, Coffee, is a multi-tenant Go REST API serving 50+ endpoints across 12 business modules -- discovery, leaderboards, collections, genre insights, keyword analytics. I designed a generic 4-layer architecture using Go generics so every module follows the same API-Service-Manager-DAO pattern with type-safe CRUD. It uses PostgreSQL for OLTP and ClickHouse for analytics, with Watermill for event-driven processing. In front of it sits the SaaS Gateway, which I also built -- an API gateway proxying all 13 microservices with JWT + Redis session auth, a two-layer cache (Ristretto + Redis), and header enrichment for multi-tenant routing."

### 90-Second Pitch

> "At Good Creator Co., I built the core backend for a multi-tenant SaaS platform used by brands and agencies for influencer marketing analytics. The system has two main components.
>
> The first is Coffee -- a Go REST API serving 50+ endpoints across 12 business modules like influencer discovery, leaderboard rankings, profile collections, and genre insights. I designed a generic 4-layer architecture using Go generics -- API, Service, Manager, DAO -- so every module follows the same pattern with compile-time type safety. It uses PostgreSQL for transactional operations and ClickHouse for analytics, with Watermill for event-driven processing via RabbitMQ.
>
> The second is the SaaS Gateway -- an API gateway I built that sits in front of all 13 microservices. It handles JWT authentication with Redis session caching, has a two-layer cache using Ristretto and Redis for sub-millisecond session lookups, and enriches requests with tenant context before proxying them downstream.
>
> This combination optimized API response times by 25% through the caching layers and reduced operational costs by 30% by offloading analytics to ClickHouse."

---

## Key Numbers

| Metric | Value |
|--------|-------|
| **Coffee LOC** | 8,500+ |
| **API Endpoints** | 50+ |
| **Business Modules** | 12 |
| **Database Tables** | 27+ |
| **Middleware Layers (Coffee)** | 10 |
| **Gateway LOC** | 2,200+ |
| **Services Proxied** | 13 |
| **Middleware Layers (Gateway)** | 7 |
| **CORS Origins** | 41 |
| **Ristretto Cache Keys** | 10M capacity |
| **Ristretto Max Memory** | 1GB |
| **Redis Pool Size** | 100 connections |
| **API Response Time Improvement** | 25% |
| **Operational Cost Reduction** | 30% |
| **User Engagement Growth** | 10% |

### Resume Bullet Evidence

| Claim | Evidence in Code |
|-------|-----------------|
| API response time optimization | Two-layer caching (Ristretto nanosecond + Redis millisecond) in gateway; ClickHouse OLAP for analytics queries instead of PostgreSQL |
| Redis caching | `cache/redis.go` -- Redis cluster with 100 pool size; `cache/ristretto.go` -- 10M key in-memory LFU cache |
| ClickHouse analytics | `core/persistence/clickhouse/db.go` -- Separate OLAP connection; dual session management in `RequestContext.CHSession` |
| Operational cost reduction | ClickHouse columnar storage reduces analytics query costs; Ristretto eliminates redundant Identity service calls |
| Genre Insights | `app/genreinsights/` -- Full module with API/Service/Manager/DAO layers |
| Keyword Analytics | `app/keywordcollection/` -- Keyword-based collection analytics |
| Discovery module | `app/discovery/` -- Profile search, time-series, hashtags, audience demographics |

---

## Architecture

```
                          INTERNET / MOBILE / WEB
                                    |
                                    v
 ===================================================================
 |                     SAAS GATEWAY (Port 8009)                      |
 |                         Go + Gin v1.8.1                           |
 |-------------------------------------------------------------------|
 | MIDDLEWARE PIPELINE:                                               |
 |  1. gin.Recovery()           -- Panic recovery                    |
 |  2. sentrygin.New()          -- Error tracking                    |
 |  3. cors.New()               -- CORS (41 origins)                 |
 |  4. GatewayContext           -- Context injection + bot blocking  |
 |  5. RequestIdMiddleware()    -- UUID generation (x-bb-requestid)  |
 |  6. RequestLogger()          -- Request/response logging          |
 |  7. AppAuth()                -- JWT + Redis session validation    |
 |-------------------------------------------------------------------|
 | AUTH FLOW:                                                        |
 |  JWT (HMAC-SHA256) --> Redis session lookup --> Identity fallback  |
 |-------------------------------------------------------------------|
 | CACHING:                                                          |
 |  Layer 1: Ristretto (10M keys, 1GB, LFU, per-instance)           |
 |  Layer 2: Redis Cluster (3 nodes, 100 pool, shared)              |
 |-------------------------------------------------------------------|
 | HEADER ENRICHMENT:                                                |
 |  Authorization, x-bb-partner-id, x-bb-plan-type, x-bb-deviceid   |
 ===================================================================
          |                    |                         |
          v                    v                         v
  [12 services @ SAAS_URL]  [social-profile-service]  [heartbeat]
          |                  @ SAAS_DATA_URL
          v
 ===================================================================
 |                     COFFEE API (Port 7179)                        |
 |                   Go 1.18 + Chi Router + GORM                     |
 |-------------------------------------------------------------------|
 | MIDDLEWARE PIPELINE (10 layers):                                   |
 |  1. RequestInterceptor    -- Capture req/res for error reporting  |
 |  2. SlowQueryLogger       -- Log requests > 5s threshold         |
 |  3. SentryErrorLogging    -- Error tracking post-response         |
 |  4. ApplicationContext    -- Extract headers -> RequestContext     |
 |  5. ServiceSession        -- Transaction + timeout management     |
 |  6. chi/Logger            -- HTTP request logging                 |
 |  7. chi/RequestID         -- Request ID generation                |
 |  8. chi/RealIP            -- Client IP extraction                 |
 |  9. chi-prometheus        -- Metrics (300ms-30s buckets)          |
 | 10. Recoverer             -- Panic recovery + Sentry              |
 |-------------------------------------------------------------------|
 | 4-LAYER REST ARCHITECTURE (Generic):                              |
 |  API (Handler) --> Service[RES,EX,EN,I] --> Manager[EX,EN,I]     |
 |                                              --> Dao[EN,I]        |
 |-------------------------------------------------------------------|
 | 12 MODULES:                                                       |
 |  Discovery | ProfileCollection | PostCollection | Leaderboard     |
 |  CollectionAnalytics | GenreInsights | KeywordCollection          |
 |  CampaignProfiles | CollectionGroup | PartnerUsage | Content      |
 |-------------------------------------------------------------------|
 | DATABASES:                                                        |
 |  PostgreSQL (OLTP) -- 27+ tables, GORM, request-scoped txns      |
 |  ClickHouse (OLAP) -- Time-series, analytics, aggregations       |
 |-------------------------------------------------------------------|
 | EVENT SYSTEM:                                                     |
 |  Watermill + AMQP (RabbitMQ)                                      |
 |  After-commit callbacks for guaranteed event publishing           |
 |  7 listener handlers with retry (3x, 100ms) + recovery           |
 ===================================================================
```

### Services Proxied by Gateway (13 Total)

| Service | Route Pattern | Backend |
|---------|--------------|---------|
| discovery-service | `/discovery-service/*` | SAAS_URL |
| leaderboard-service | `/leaderboard-service/*` | SAAS_URL |
| profile-collection-service | `/profile-collection-service/*` | SAAS_URL |
| activity-service | `/activity-service/*` | SAAS_URL |
| collection-analytics-service | `/collection-analytics-service/*` | SAAS_URL |
| post-collection-service | `/post-collection-service/*` | SAAS_URL |
| genre-insights-service | `/genre-insights-service/*` | SAAS_URL |
| content-service | `/content-service/*` | SAAS_URL |
| **social-profile-service** | `/social-profile-service/*` | **SAAS_DATA_URL** |
| collection-group-service | `/collection-group-service/*` | SAAS_URL |
| keyword-collection-service | `/keyword-collection-service/*` | SAAS_URL |
| partner-usage-service | `/partner-usage-service/*` | SAAS_URL |
| campaign-profile-service | `/campaign-profile-service/*` | SAAS_URL |

### Twelve Business Modules

| Module | Directory | Key Endpoints |
|--------|-----------|---------------|
| Discovery | `app/discovery/` | Profile search, audience, hashtags, time-series, similar accounts |
| Profile Collection | `app/profilecollection/` | CRUD collections, add/remove profiles, search, share links |
| Post Collection | `app/postcollection/` | Curated post collections with ingestion frequency |
| Leaderboard | `app/leaderboard/` | Platform rankings by followers, engagement, category, language |
| Collection Analytics | `app/collectionanalytics/` | Hashtag and keyword tracking, post metrics summary |
| Genre Insights | `app/genreinsights/` | Genre-based trending content analytics |
| Keyword Collection | `app/keywordcollection/` | Keyword-based search optimization |
| Campaign Profiles | `app/campaignprofiles/` | Campaign-profile associations |
| Collection Group | `app/collectiongroup/` | Hierarchical collection grouping |
| Partner Usage | `app/partnerusage/` | Plan limits, usage tracking per module |
| Content | `app/content/` | Media/content management |
| Activity | (via listeners) | Activity tracking across modules |

Each module follows the same directory structure:
```
{module}/
  api/api.go              # HTTP handlers
  service/service.go      # Business orchestration
  manager/manager.go      # Domain logic + data mapping
  dao/dao.go              # Data access (PostgreSQL or ClickHouse)
  domain/
    entry.go              # Input DTOs
    entity.go             # Database entities
    response.go           # Output DTOs
  listeners/listeners.go  # Event handlers (Watermill)
```

---

## Technical Implementation

### PART 1: COFFEE -- Four-Layer REST Architecture with Go Generics

#### Layer 1: API (Handler)

```go
// core/rest/api.go
type ApiWrapper interface {
    AttachRoutes(r *chi.Mux)
    GetPrefix() string
}
```

Every module implements `ApiWrapper`. `GetPrefix()` returns the URL prefix (e.g., `/discovery-service/api/`), and `AttachRoutes` wires HTTP handlers to the chi router.

#### Layer 2: Service

```go
// core/rest/service.go
type Service[RES domain.Response, EX domain.Entry, EN domain.Entity, I domain.ID] struct {
    ctx                 context.Context
    manager             *Manager[EX, EN, I]
    createResponse      func([]EX, int64, string, string) RES
    createErrorResponse func(error, int) RES
    getPrimaryStore     func() domain.DataStore
}

func (r *Service[RES, EX, EN, I]) Create(ctx context.Context, entry *EX) RES {
    createdEntry, err := r.manager.Create(ctx, entry)
    if err != nil {
        return r.createErrorResponse(err, 0)
    }
    return r.createResponse([]EX{*createdEntry}, 1, "", "Record Created Successfully")
}

func (r *Service[RES, EX, EN, I]) Search(ctx context.Context, searchQuery domain.SearchQuery,
    sortBy string, sortDir string, page int, size int) RES {
    entries, filteredCount, err := r.manager.Search(ctx, searchQuery, sortBy, sortDir, page, size)
    if err != nil {
        return r.createErrorResponse(err, 0)
    }
    var nextCursor string
    if len(entries) >= size {
        nextCursor = strconv.Itoa(page + 1)
    } else {
        nextCursor = ""
    }
    return r.createResponse(entries, filteredCount, nextCursor, "Record(s) Retrieved Successfully")
}
```

Service is parameterized by FOUR generic types: `RES` (Response DTO), `EX` (Entry/business DTO), `EN` (Entity/database row), `I` (ID type: `int64` or `string`). Handles cursor-based pagination.

#### Layer 3: Manager

```go
// core/rest/manager.go
type Manager[EX domain.Entry, EN domain.Entity, I domain.ID] struct {
    dao      *Dao[EN, I]
    toEntity func(*EX) (*EN, error)    // Entry -> Entity (for writes)
    toEntry  func(*EN) (*EX, error)    // Entity -> Entry (for reads)
}

func (r *Manager[EX, EN, I]) Create(ctx context.Context, entry *EX) (*EX, error) {
    if entry == nil {
        return nil, errors.New("domain is null")
    }
    entity, err := r.toEntity(entry)
    if err != nil {
        return nil, err
    }
    createdEntity, err := r.dao.Create(ctx, entity)
    if err != nil {
        return nil, err
    }
    return r.toEntry(createdEntity)
}
```

The Manager owns `toEntity` and `toEntry` converter functions -- injected at construction time. This is where each module's custom mapping logic lives.

#### Layer 4: DAO

```go
// core/rest/dao_provider.go
type DaoProvider[EN domain.Entity, I domain.ID] interface {
    FindById(ctx context.Context, id I) (*EN, error)
    FindByIds(ctx context.Context, ids []I) ([]EN, error)
    Create(ctx context.Context, entity *EN) (*EN, error)
    Update(ctx context.Context, id I, entity *EN) (*EN, error)
    Search(ctx context.Context, query domain.SearchQuery, sortBy string, sortDir string,
        page int, size int) ([]EN, int64, error)
    SearchJoins(ctx context.Context, query domain.SearchQuery, sortBy string, sortDir string,
        page int, size int, joinTables []domain.JoinClauses) ([]EN, int64, error)
    GetSession(ctx context.Context) *gorm.DB
    AddPredicateForSearchJoins(req *gorm.DB, filter domain.SearchFilter) *gorm.DB
}
```

The `DaoProvider` interface is implemented by both PostgreSQL and ClickHouse DAO implementations. Each module provides its own DAO that implements `AddPredicateForSearchJoins` for custom filtering logic.

#### Generic Type Constraints

```go
// core/domain/types.go
type ID interface{ ~int64 | ~string }
type Entry interface{}
type Entity interface{}
type Response interface{}

type BaseEntity struct {
    Version optimisticlock.Version    // Optimistic locking via GORM plugin
}

type SearchQuery struct {
    Filters []SearchFilter `json:"filters"`
}

type SearchFilter struct {
    FilterType string `json:"filterType"`    // EQ, GTE, LTE, LIKE, IN
    Field      string `json:"field"`
    Value      string `json:"value"`
}
```

### Multi-Tenant Request Context

```go
// core/appcontext/requestcontext.go
type RequestContext struct {
    Ctx             context.Context
    Mutex           sync.Mutex
    Properties      map[string]interface{}

    // Tenant Identification (3-level hierarchy)
    PartnerId       *int64              // Primary tenant (company)
    AccountId       *int64              // Sub-account within partner
    UserId          *int64              // Individual user
    UserName        *string

    // Authentication
    Authorization   string              // "Basic base64(userId~userName~isLoggedIn~accountId:password)"
    DeviceId        *string
    IsLoggedIn      bool

    // Plan & Access Control
    IsPremiumMember bool
    IsBasicMember   bool
    PlanType        *constants.PlanType // FREE, SAAS, PAID

    // Dual Database Sessions
    Session         persistence.Session // PostgreSQL transaction
    CHSession       persistence.Session // ClickHouse transaction
}
```

#### Authorization Token Parsing

```go
func PopulateUserInfoFromAuthToken(appCtx RequestContext, token string) (RequestContext, error) {
    tokenParts := strings.Split(token, " ")
    decodedAuthToken, _ := base64.StdEncoding.DecodeString(tokenParts[1])
    namePassword := strings.Split(string(decodedAuthToken), ":")
    userIdNameOperationArr := strings.Split(namePassword[0], "~")

    appCtx.IsLoggedIn = false
    if len(userIdNameOperationArr) >= 3 {
        loggedInFlag, err1 := strconv.Atoi(userIdNameOperationArr[2])
        if err1 == nil && loggedInFlag == 1 {
            appCtx.IsLoggedIn = true
        }
    }
    if !appCtx.IsLoggedIn {
        appCtx.DeviceId = &userIdNameOperationArr[0]
    } else {
        userId, _ := strconv.ParseInt(userIdNameOperationArr[0], 10, 64)
        appCtx.UserId = &userId
        appCtx.UserName = &userIdNameOperationArr[1]
        if len(userIdNameOperationArr) > 3 {
            userAccountId, _ := strconv.ParseInt(userIdNameOperationArr[3], 10, 64)
            appCtx.AccountId = &userAccountId
        }
    }
    return appCtx, nil
}
```

#### After-Commit Event Callbacks

```go
func (c *RequestContext) SetSession(ctx context.Context, session persistence.Session) {
    c.Session = session
    c.Session.PerformAfterCommit(ctx, c.applyEvents)
}

func (c *RequestContext) applyEvents(ctx context.Context) {
    appContext := ctx.Value(constants.AppContextKey).(*RequestContext)
    eventStore := appContext.GetValue("event_store")
    if eventStore == nil {
        eventStore = []event.Event{}
    }
    _store := eventStore.([]event.Event)
    for i := range _store {
        _store[i].Apply()
    }
}
```

Events are queued during request processing and only applied AFTER the database transaction commits successfully. This prevents publishing events for rolled-back transactions.

### Ten-Layer Middleware Pipeline

```go
// server/server.go
func attachMiddlewares(r *chi.Mux, container rest.ApplicationContainer) {
    r.Use(middlewares.RequestInterceptor)       // 1. Capture req/res bodies for error reporting
    r.Use(middlewares.SlowQueryLogger)          // 2. Log requests exceeding 5s threshold
    r.Use(middlewares.SentryErrorLoggingMiddleware) // 3. Error tracking post-response
    r.Use(middlewares.ApplicationContext)        // 4. Extract headers -> RequestContext
    r.Use(middlewares.ServiceSessionMiddlewares(container)) // 5. Transaction + timeout
    r.Use(middleware.Logger)                    // 6. Chi built-in HTTP logging
    r.Use(middleware.RequestID)                 // 7. Request ID generation
    r.Use(middleware.RealIP)                    // 8. Client IP extraction
    r.Use(chiprometheus.NewPatternMiddleware(   // 9. Prometheus metrics
        constants.ApplicationName, 300, 500, 1000, 5000, 10000, 20000, 30000))
    r.Use(middlewares.Recoverer)               // 10. Panic recovery + Sentry
}
```

#### Session Management (Transaction + Timeout)

```go
// server/middlewares/session.go
func ServiceSessionMiddlewares(container rest.ApplicationContainer) func(handler http.Handler) http.Handler {
    return func(handler http.Handler) http.Handler {
        fn := func(w http.ResponseWriter, r *http.Request) {
            ctx, cancel := context.WithTimeout(r.Context(),
                time.Duration(viper.GetInt("SERVER_TIMEOUT"))*time.Second)
            defer cancel()

            for service, api := range container.Services {
                if strings.HasPrefix(r.URL.String(), api.GetPrefix()) {
                    sessionCtx := r.Context()
                    defer func(service rest.ServiceWrapper, sessionCtx context.Context) {
                        cancel()
                        if ctx.Err() == context.DeadlineExceeded {
                            rollbackSessions(sessionCtx)
                            w.WriteHeader(http.StatusGatewayTimeout)
                        } else {
                            closeSessions(sessionCtx)
                        }
                    }(service, sessionCtx)
                    handler.ServeHTTP(w, r.WithContext(sessionCtx))
                }
            }
        }
        return http.HandlerFunc(fn)
    }
}
```

Matches request URL to a registered service, wraps in a timeout context, and manages dual database sessions (PostgreSQL + ClickHouse). On timeout, both sessions are rolled back and a 504 is returned.

#### Recoverer

```go
// server/middlewares/recoverer.go
func Recoverer(next http.Handler) http.Handler {
    fn := func(w http.ResponseWriter, r *http.Request) {
        defer func() {
            if rvr := recover(); rvr != nil {
                if rvr == http.ErrAbortHandler {
                    panic(rvr)
                }
                sentry.PrintToSentryWithInterface(rvr)
                errorResponse := domain.BaseResponse{Status: domain.Status{
                    Status:  "ERROR",
                    Message: "Something Went Wrong",
                }}
                render.JSON(w, r, errorResponse)
            }
        }()
        next.ServeHTTP(w, r)
    }
    return http.HandlerFunc(fn)
}
```

### Watermill Event-Driven Architecture

```go
// amqp/config.go -- Topic format: "exchange___queue"
routingKeyGen := func(topic string) string { return strings.Split(topic, "___")[1] }
queueGen := func(topic string) string { return strings.Split(topic, "___")[1] }
exchangeGen := func(topic string) string { return strings.Split(topic, "___")[0] }

amqpConfig.Exchange = amqp.ExchangeConfig{
    GenerateName: exchangeGen,
    Type:         "direct",
    Durable:      true,
}
```

```go
// listeners/listeners.go
func SetupListeners() {
    router, _ := message.NewRouter(message.RouterConfig{}, logger)
    router.AddMiddleware(
        middlewares.MessageApplicationContext,
        middlewares.TransactionSessionHandler,
        middleware.Retry{MaxRetries: 3, InitialInterval: time.Millisecond * 100}.Middleware,
        middlewares.Recoverer,
    )
    // 7 listener handlers registered:
    socialdiscoveryListners.SetupListeners(router, subscriber)
    profilecollectionlisteners.SetupListeners(router, subscriber)
    postcollectionlisteners.SetupListeners(router, subscriber)
    leaderboard.SetupListeners(router, subscriber)
    collectionanalytics.SetupListeners(router, subscriber)
    keywordcollection.SetupListeners(router, subscriber)
    campaignprofileListners.SetupListeners(router, subscriber)
    go func() { router.Run(context.Background()) }()
}
```

### PART 2: SAAS GATEWAY

### JWT + Redis Session Authentication

```go
// middleware/auth.go
func AppAuth(config config.Config) gin.HandlerFunc {
    return func(c *gin.Context) {
        gc := util.GatewayContextFromGinContext(c, config)
        verified := false

        // STEP 1: Extract client ID, set client authorization
        if clientId := gc.GetHeader(header.ClientID); clientId != "" {
            gc.GenerateClientAuthorizationWithClientId(clientId, clientType)
        }

        // STEP 2: Skip auth for device init endpoints
        apolloOp := gc.Context.GetHeader(header.ApolloOpName)
        if apolloOp == "initDeviceGoMutation" || apolloOp == "initDeviceV2" || ... {
            verified = true
        }

        // STEP 3: Parse JWT with HMAC-SHA256
        token, err := jwt.Parse(splittedAuthHeader[1], func(token *jwt.Token) (interface{}, error) {
            if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
                return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
            }
            hmac, _ := b64.StdEncoding.DecodeString(config.HMAC_SECRET)
            return hmac, nil
        })

        // STEP 4: Redis session lookup
        if sessionId, ok := claims["sid"].(string); ok && sessionId != "" {
            keyExists := cache.Redis(gc.Config).Exists("session:" + sessionId)
            if exist, err := keyExists.Result(); err == nil && exist == 1 {
                verified = true
            }
        }

        // STEP 5: Fallback to Identity service if Redis miss
        if !verified {
            verifyTokenResponse, err := identity.New(gc).VerifyToken(
                &input.Token{Token: splittedAuthHeader[1]}, false)
            if err == nil && verifyTokenResponse.Status.Type == "SUCCESS" {
                verified = true
            }
        }

        // STEP 6: Partner plan validation (contract date range check)
        partnerResponse, _ := partner.New(gc).FindPartnerById(partnerId)
        for _, contract := range partnerDetail.Contracts {
            if contract.ContractType == "SAAS" {
                currentTime := time.Now()
                startTime := time.Unix(0, contract.StartTime*int64(time.Millisecond))
                endTime := time.Unix(0, contract.EndTime*int64(time.Millisecond))
                if currentTime.After(startTime) && currentTime.Before(endTime) {
                    userClientAccount.PartnerProfile.PlanType = contract.Plan
                } else {
                    userClientAccount.PartnerProfile.PlanType = "FREE"
                }
            }
        }

        if !verified {
            gc.AbortWithStatus(http.StatusUnauthorized)
        } else {
            gc.GenerateAuthorization()
            c.Next()
        }
    }
}
```

### Two-Layer Caching Architecture

**Layer 1: Ristretto In-Memory Cache**

```go
// cache/ristretto.go
func Ristretto(config config.Config) *ristretto.Cache {
    ristrettoOnce.Do(func() {
        singletonRistretto, _ = ristretto.NewCache(&ristretto.Config{
            NumCounters: 1e7,     // 10M keys tracked for frequency
            MaxCost:     1 << 30, // 1GB maximum memory
            BufferItems: 64,      // 64 keys per Get buffer (batching)
        })
    })
    return singletonRistretto
}
```

- Scope: Per-instance (not shared between gateway nodes)
- Eviction: LFU via TinyLFU admission policy
- Latency: Nanoseconds

**Layer 2: Redis Cluster**

```go
// cache/redis.go
func Redis(config config.Config) *redis.ClusterClient {
    redisInit.Do(func() {
        singletonRedis = redis.NewClusterClient(&redis.ClusterOptions{
            Addrs:    config.RedisClusterAddresses,
            PoolSize: 100,
            Password: config.REDIS_CLUSTER_PASSWORD,
        })
    })
    return singletonRedis
}
```

- Scope: Shared across all gateway instances
- Cluster: 3 nodes in production
- Latency: Milliseconds

**Lookup Order:**
```
Request --> [Ristretto: nanoseconds] --> HIT? Return
                     |
                     v MISS
            [Redis: milliseconds] --> HIT? Return + populate Ristretto
                     |
                     v MISS
            [Identity Service: 50-100ms] --> Return + populate both
```

### Reverse Proxy with Header Enrichment

```go
// handler/saas/saas.go
func ReverseProxy(module string, config config.Config) func(c *gin.Context) {
    return func(c *gin.Context) {
        appContext := util.GatewayContextFromGinContext(c, config)

        saasUrl := config.SAAS_URL
        if module == "social-profile-service" {
            saasUrl = config.SAAS_DATA_URL
        }

        remote, _ := url.Parse(saasUrl)
        proxy := httputil.NewSingleHostReverseProxy(remote)

        proxy.Director = func(req *http.Request) {
            req.Header = c.Request.Header
            req.Header.Set("Authorization", authHeader)
            req.Header.Set(header.PartnerId, partnerId)
            req.Header.Set(header.PlanType, planType)
            req.Header.Set(header.Device, deviceId)
            req.Header.Del("accept-encoding")
            req.Host = remote.Host
            req.URL.Scheme = remote.Scheme
            req.URL.Host = remote.Host
            req.URL.Path = "/" + module + c.Param("any")
        }

        proxy.ModifyResponse = responseHandler(appContext, c.Request.Method,
            c.Param("any"), c.Request.Header.Get("origin"), ...)

        proxy.ServeHTTP(c.Writer, c.Request)
    }
}
```

### Graceful Deployment

```bash
# 1. Take out of load balancer
curl -vXPUT http://localhost:$PORT/heartbeat/?beat=false
sleep 15                     # Wait for in-flight requests to drain

# 2. Kill old process
kill -9 $PID
sleep 10

# 3. Start new process
ENV=$CI_ENVIRONMENT_NAME ./saas-gateway >> "logs/out.log" 2>&1 &
sleep 20                     # Wait for startup

# 4. Put back in load balancer
curl -vXPUT http://localhost:$PORT/heartbeat/?beat=true
```

---

## Technical Decisions

### Decision 1: Why Go Generics for the REST Framework?

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **Go 1.18 generics** | Compile-time type safety, 6 framework files vs 36 | Less powerful than Java generics, cryptic error messages | **YES** |
| **Interface-based polymorphism** | Pre-generics standard | `interface{}` everywhere, runtime panics | No |
| **Code generation** | Template-based | Build complexity, stale files | No |
| **Reflection-based ORM** | Like Java Spring Data | Runtime overhead, no compile safety | No |

```go
// WITHOUT generics:
func (s *Service) Create(ctx context.Context, entry interface{}) (interface{}, error) {
    e := entry.(*ProfileCollectionEntry)  // UNSAFE -- runtime panic if wrong type
}

// WITH generics:
func (r *Service[RES, EX, EN, I]) Create(ctx context.Context, entry *EX) RES {
    createdEntry, err := r.manager.Create(ctx, entry)  // SAFE -- compile error if wrong type
}
```

> "We had 12 modules to build. Without generics, each module would need its own Service, Manager, and DAO -- roughly 36 boilerplate files. With generics, the core framework is 6 files, and each module only implements the DaoProvider interface and converter functions (`toEntity`, `toEntry`)."

### Decision 2: Why 4-Layer Architecture vs 3-Layer?

> "The Manager owns TWO things that don't belong in Service or DAO: data transformation (`toEntity`/`toEntry` converters) and business logic enforcement. Without the Manager, the Service would need to know about both DTOs and entities, violating single responsibility. In complex modules like Discovery, the Manager layer is critical -- it has sub-managers like SearchManager, TimeSeriesManager, HashtagsManager, and AudienceManager."

**Follow-up: "When would you NOT use 4 layers?"**
> "For simple microservices with only CRUD and no data transformation, 3 layers is fine. The Manager layer pays for itself when you have complex mapping logic or multiple sub-managers per domain."

### Decision 3: Why Watermill vs Direct RabbitMQ Client?

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **Watermill + AMQP** | Middleware chain for messages, same pattern as HTTP | Added dependency, `___` naming unconventional | **YES** |
| **Direct streadway/amqp** | More control | Build own retry, recovery, context extraction | No |
| **NATS** | Simpler pub/sub | Different infrastructure | No |
| **Kafka** | Heavy event streaming | Overkill for point-to-point queues | No |

> "Watermill provides a middleware chain for message handlers -- the SAME pattern we use for HTTP. With direct `streadway/amqp`, we would have had to build message context extraction, transaction management, retry logic, and panic recovery ourselves. The topic naming `exchange___queue` encodes both RabbitMQ exchange and queue in a single string."

### Decision 4: Why Chi Router for Coffee vs Gin for Gateway?

> "Coffee chose Chi because it's `net/http` compatible -- middleware is `func(http.Handler) http.Handler`. Our custom session middleware needs to wrap `http.Handler` and control commit/rollback. Chi's middleware composability is better for complex pipelines (10 layers). Gateway chose Gin because it's simpler for proxy + auth + logging, has built-in recovery and context management, and was the existing standard at GCC."

### Decision 5: Why Ristretto + Redis Two-Layer Cache?

> "The gateway handles every request. Session lookup is the bottleneck. With Redis only: every request = 1 network round trip (~1-2ms). With Ristretto + Redis: hot sessions (active users) are in Ristretto at nanosecond lookup. Ristretto uses TinyLFU admission policy -- it only caches keys accessed frequently enough. Random one-time requests don't pollute the cache."

**Follow-up: "How do you handle cache invalidation?"**
> "Redis is the source of truth. Ristretto has no explicit invalidation -- it relies on TTL and LFU eviction. For session revocation, we delete from Redis. Ristretto serves stale data for a few seconds at most."

### Decision 6: Why JWT + Redis Session vs Pure Token Validation?

> "Pure JWT has a fatal flaw for SaaS: you cannot revoke a session. Our approach: JWT contains claims (userId, partnerId), and the `sid` claim points to a Redis key. Redis `EXISTS` is O(1), sub-millisecond. Delete `session:{sid}` from Redis = instant session revocation. The Identity service fallback handles Redis flushes or cross-cluster sessions."

### Decision 7: Why Reverse Proxy vs API Composition?

> "The gateway's job is AUTH + ROUTING + ENRICHMENT, not business logic. Each Coffee module already returns complete responses. Reverse proxy means zero business logic in gateway, any HTTP method works, large responses stream through without buffering, and low memory usage. If we needed aggregation, I would add specific composition endpoints for those cases while keeping the default as reverse proxy."

### Decision 8: Why After-Commit Callbacks vs Sync Event Publishing?

> "If you publish an event and then the database transaction rolls back, downstream consumers process an event for data that doesn't exist. Our approach queues events during processing and only publishes in the after-commit callback. If the transaction rolls back, no events are published. The trade-off is that if the process crashes between commit and callback, events are lost -- but this is better than phantom events."

**Follow-up: "What about the outbox pattern?"**
> "The outbox pattern writes events to a database table in the same transaction, then a separate process polls and publishes. It gives exactly-once semantics but adds latency and infrastructure. For our use case of collection updates and profile refreshes, occasional lost events are acceptable."

---

## Interview Q&A

### Q1: "How did you implement multi-tenancy?"

> "Coffee uses a three-level tenant hierarchy: Partner, Account, and User. Every request carries these as HTTP headers. The gateway extracts them from the JWT token and enriches the request headers before proxying to Coffee. Inside Coffee, the ApplicationContext middleware reads these headers and builds a RequestContext struct that flows through the entire request lifecycle via Go's `context.Context`. The Partner is the paying entity -- they have a plan type (FREE, SAAS, PAID) that gates feature access."

**Follow-up: "How do you prevent data leakage between tenants?"**
> "Every database query includes the partner ID as a filter at the DAO layer. The gateway validates the partner ID against JWT claims, so a user can't spoof another partner's ID. The proxy Director OVERWRITES all headers from the authenticated JWT."

### Q2: "Walk me through how a request flows from client to database and back."

> "1. Client sends POST to `gateway/discovery-service/api/profile/instagram/search`
> 2. Gateway 7-layer pipeline: Recovery, Sentry, CORS, context, request ID, logging, AppAuth validates JWT + Redis session
> 3. Gateway reverse proxy enriches headers (partner ID, plan type) and proxies to Coffee
> 4. Coffee 10-layer pipeline: Request interceptor, slow query logger, Sentry, ApplicationContext extracts headers into RequestContext, ServiceSession starts PostgreSQL transaction with timeout
> 5. Discovery API handler parses search body, calls Service
> 6. Service (generic) calls Manager's Search
> 7. Manager calls DAO.Search with filters
> 8. DAO translates SearchFilters into GORM where clauses, executes against PostgreSQL or ClickHouse
> 9. Manager converts entities to entries using `toEntry`
> 10. Service wraps entries in response DTO with pagination cursor
> 11. Middleware commits transaction, executes after-commit callbacks
> 12. Response flows back through proxy to client"

### Q3: "How does the generic search/filter system work?"

> "Every search endpoint uses the same SearchQuery model with filters like `{filterType: 'GTE', field: 'followers', value: '10000'}`. The DAO layer translates each filter into a GORM where clause. Each module's DAO implements `AddPredicateForSearchJoins` for custom filter logic -- for example, the Discovery DAO maps `audience_gender=MALE` to JSONB path queries like `audience_gender.male_per >= 40`. This means we can add new filter fields without changing framework code."

### Q4: "Explain the two-layer caching strategy."

> "Layer 1 is Ristretto, an in-memory LFU cache -- 10M key slots, 1GB max, TinyLFU admission policy that only caches frequently accessed keys. Layer 2 is Redis cluster with 3 nodes and 100-connection pool. Lookup order: Ristretto (nanoseconds) -> Redis (milliseconds) -> Identity service (50-100ms). When Redis returns a hit, we also populate Ristretto. The key trade-off is consistency -- Ristretto is per-instance, so session invalidation from Redis may take a few seconds to reflect."

### Q5: "How does ClickHouse complement PostgreSQL?"

> "PostgreSQL handles OLTP -- all transactional operations. ClickHouse handles OLAP -- time-series data, leaderboard aggregations, engagement calculations across millions of profiles. Both are managed through the same session middleware. The RequestContext has both `Session` (PostgreSQL) and `CHSession` (ClickHouse). The middleware commits or rolls back BOTH on request completion."

### Q6: "How does the event system work?"

> "Publishing: Events are queued in RequestContext's event store during request processing. After the database transaction commits, the `PerformAfterCommit` callback fires and publishes each event. This ensures we never publish events for rolled-back transactions.
>
> Consuming: Seven listener handlers are registered on Watermill's router with its own middleware chain -- message context extraction, transaction session management, retry (3 attempts, 100ms backoff), and panic recovery. Each message handler gets its own database transaction, just like HTTP handlers."

### Q7: "How much boilerplate did Go generics eliminate?"

> "Without generics, 12 modules times 3 layers = 36 files of mostly identical code. With generics, the core framework is 6 files totaling about 300 lines. Each module only implements: the DaoProvider interface, two converter functions (toEntity and toEntry), and the API handler. Adding a new module takes about 30 minutes instead of a day."

### Q8: "What observability did you build?"

> "Four layers: 1) Prometheus metrics -- chi-prometheus with custom buckets (300ms to 30s), gateway `requests_winkl` counter with method/path/status labels. 2) Sentry error tracking -- captures panics with stack traces AND non-200 responses with full request body. 3) Structured logging -- Logrus (Coffee) and Zerolog (Gateway) with request ID correlation via `x-bb-requestid`. 4) Slow query logging -- Coffee logs requests exceeding 5 seconds to a dedicated daily log file."

### Q9: "How does the health check deployment work?"

> "Both systems expose `/heartbeat/` GET and PUT. Deployment: PUT beat=false (out of LB), sleep 15s (drain), kill process, start new binary, sleep 20s (init), PUT beat=true (back in LB). Production has 2 nodes deployed one at a time, ensuring at least one is always serving."

---

## Behavioral Stories

### Story: "Optimized API response times by 25%"

> **Setup:** "The SaaS platform was making a network call to the Identity service for every single request to validate the user session. At scale, this added 50-100ms per request."
>
> **Action:** "I designed a two-layer caching strategy. Ristretto as an L1 in-memory cache handles hot sessions in nanoseconds. Redis cluster as L2 handles the rest in milliseconds. The Identity service is only called on a complete cache miss."
>
> **Result:** "API response times improved by 25% overall. For repeat requests from active users, the improvement was even higher because Ristretto eliminates all network overhead."

### Story: "Reduced operational costs by 30%"

> **Setup:** "Analytics queries -- time-series data, leaderboard aggregations, engagement calculations -- were running on the same PostgreSQL database as transactional operations. Heavy analytics scans were degrading CRUD performance."
>
> **Action:** "I implemented a dual database strategy: PostgreSQL for OLTP and ClickHouse for OLAP. The RequestContext manages sessions for both databases, and the middleware commits or rolls back both."
>
> **Result:** "ClickHouse's columnar storage reduced analytics query costs by 30% while also improving query performance. PostgreSQL was freed from heavy scan workloads."

### Story: "Developed real-time social media insights modules, driving 10% user engagement growth"

> **Setup:** "The platform needed Genre Insights and Keyword Analytics to help brands discover trending content and track keyword performance."
>
> **Action:** "I built both modules following the generic 4-layer architecture. Genre Insights analyzes trending content by genre. Keyword Collection enables keyword-based search optimization. Both use Discovery's infrastructure for profile data and ClickHouse for analytics."
>
> **Result:** "These modules drove 10% user engagement growth by giving brands actionable insights -- trending genres, keyword performance, audience demographics."

### The Generics Story (Use for "Tell me about a technical design you're proud of")

> "When I started building Coffee, we had 12 business modules to implement. Go 1.18 had just released generics, and I saw an opportunity to build a type-safe framework instead of copy-pasting code 12 times. I designed a four-layer generic architecture: the Service parameterized by Response, Entry, Entity, and ID types. The result is that adding a new module takes about 30 minutes instead of a day. You implement the DaoProvider, write two converter functions, and wire the API routes. The framework handles pagination, error responses, transaction management, and session lifecycle."

---

## What-If Scenarios

### Scenario 1: "What if Redis goes down?"

> **DETECT:** Gateway auth middleware gets errors from `cache.Redis().Exists()`.
>
> **IMPACT:** The fallback chain saves us -- when Redis fails, auth falls through to the Identity service API call. Requests are SLOWER (50-100ms instead of 1-2ms) but NOT broken. Ristretto L1 cache still serves hot sessions in-memory -- those users see no impact.
>
> **RECOVER:** When Redis recovers, new lookups populate the cache again. Within minutes, the fast path is restored.
>
> **PREVENT:** Redis cluster with 3 nodes handles single-node failure. For full cluster failure, add circuit breaker pattern to fail fast to Identity service.

### Scenario 2: "What if a database transaction times out?"

> **DETECT:** ServiceSession middleware detects `context.DeadlineExceeded`. Slow query logger already recorded the request. Sentry receives the error with full request body.
>
> **IMPACT:** Single request fails with 504. Both PostgreSQL and ClickHouse sessions are explicitly rolled back.
>
> **RECOVER:** Rolled-back connection returns to pool immediately. Next request gets a fresh connection. No persistent state corrupted.
>
> **PREVENT:** Monitor slow query logs. Optimize queries or add indexes. For long operations, make them async via Watermill.

### Scenario 3: "What if the Watermill/RabbitMQ connection drops?"

> **IMPACT:** HTTP requests continue normally -- event publishing uses after-commit callbacks which are fire-and-forget. Data is saved, but events are lost. For listeners: RabbitMQ holds unacknowledged messages. When connection recovers, messages are redelivered.
>
> **PREVENT:** Add Prometheus counter for failed publishes. Implement outbox pattern for critical events.

### Scenario 4: "What if a partner's contract expires mid-session?"

> **IMPACT:** Next request gets `planType = FREE`. Premium fields are no longer returned. No error -- soft downgrade. This is the DESIRED behavior.
>
> **RECOVER:** When partner renews, next request picks up the new plan type. No cache invalidation needed.

### Scenario 5: "What if someone tries to spoof the x-bb-partner-id header?"

> **IMPACT:** None. The proxy Director OVERWRITES all headers from the authenticated JWT. Even if a client sends a fake header, the gateway replaces it. The architecture inherently prevents this.

### Scenario 6: "What if Discovery search returns millions of results?"

> **PROTECTION LAYERS:**
> 1. Pagination caps: page capped at 1000, size at 100
> 2. Request timeout: ServiceSession middleware enforces SERVER_TIMEOUT with rollback
> 3. Slow query logger: 5-second threshold catches approaching-timeout requests
> 4. Database-level: GORM `Limit`/`Offset` translates to SQL LIMIT/OFFSET

### Scenario 7: "What if you need to add a 14th microservice to the gateway?"

> One line of code:
> ```go
> router.Any('/new-service/*any', middleware.AppAuth(config), saas.ReverseProxy('new-service', config))
> ```
> No changes to auth, caching, logging, or metrics -- they all apply globally.

---

## How to Speak

### Pyramid Method -- Architecture Question

**Level 1 -- Headline:**
> "It's a two-component system: an API gateway handling auth and caching, proxying to a multi-tenant REST API with 12 business modules and dual database strategy."

**Level 2 -- Structure:**
> "The gateway receives all client requests. Its 7-layer middleware pipeline validates JWT tokens, checks Redis for active sessions, and enriches headers with partner ID and plan type. It then reverse-proxies to Coffee, which has its own 10-layer middleware pipeline managing transactions, timeouts, and observability. Coffee's 4-layer generic architecture means every module follows the same API-Service-Manager-DAO pattern. PostgreSQL handles CRUD, ClickHouse handles analytics, Watermill handles async events via RabbitMQ."

**Level 3 -- Go deep on ONE part:**
> "The most interesting design decision was using Go generics for the REST framework. The Service type has four type parameters -- Response, Entry, Entity, and ID. This means when a module creates a new Service instance, the compiler enforces that the right types flow through all four layers. Without generics, we would've needed 36 boilerplate files across 12 modules. With generics, the framework is 6 files."

**Level 4 -- OFFER:**
> "I can go deeper into the caching architecture, the multi-tenant auth flow, or how the dual database strategy works with ClickHouse -- which interests you?"

### Pivot Phrases

| If They Ask About... | Pivot To... |
|----------------------|-------------|
| Frontend/UI | "The SaaS frontend consumed Coffee's REST API. I can speak to the API design decisions..." |
| DevOps/Kubernetes | "We deployed on bare metal with GitLab CI. The interesting part was our graceful deployment with heartbeat toggling..." |
| Testing | "The generic framework made testing consistent -- each module's DAO was the unit test boundary. Let me tell you about the framework design..." |
| Scale numbers | "The platform served GCC's brand clients. What's more interesting is the architectural decisions at our scale..." |
| Why Go? | "Go was the company standard. The interesting choice was Go 1.18 generics for the framework..." |

### Words to Use

- "Type-safe" (not "generic code")
- "Multi-tenant" (not "different customers")
- "Dual database strategy" (not "two databases")
- "After-commit callbacks" (not "event publishing")
- "Header enrichment" (not "adding headers")
- "Reverse proxy" (not "forwarding requests")
- "LFU admission policy" (not "cache eviction")

### Closing Statement

> "What I'm most proud of with Coffee is the developer experience. A new engineer can add a business module in 30 minutes because the generic framework handles all the plumbing -- transactions, pagination, error handling, session management. The 4-layer pattern is consistent across all 12 modules. And on the gateway side, the two-layer caching reduced auth latency from 50-100ms to nanoseconds for active users. Both systems are still running in production."
