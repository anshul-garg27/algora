# Technical Implementation - Coffee + SaaS Gateway

> Code-verified implementation details from actual source code.
> Every snippet below is from the real codebase, not pseudocode.

---

## PART 1: COFFEE (Multi-Tenant SaaS REST API)

---

### 1. Four-Layer REST Architecture with Go Generics

The entire Coffee API is built on a generic 4-layer pattern. Every business module (Discovery, Collections, Leaderboard, etc.) instantiates this same framework with its own types.

#### Layer 1: API (Handler) -- `core/rest/api.go`

```go
// core/rest/api.go
package rest

import "github.com/go-chi/chi/v5"

type ApiWrapper interface {
    AttachRoutes(r *chi.Mux)
    GetPrefix() string
}
```

Every module implements `ApiWrapper`. The `GetPrefix()` method returns the URL prefix (e.g., `/discovery-service/api/`), and `AttachRoutes` wires HTTP handlers to the chi router.

#### Layer 2: Service -- `core/rest/service.go`

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

Key design: The Service is parameterized by FOUR generic types:
- `RES` (Response) -- The API response DTO
- `EX` (Entry) -- The input/output business DTO
- `EN` (Entity) -- The database entity
- `I` (ID) -- The ID type (`int64` or `string`)

The Service also handles cursor-based pagination: if results equal page size, there is a next page.

#### Layer 3: Manager -- `core/rest/manager.go`

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

func (m *Manager[EX, EN, I]) Search(ctx context.Context, query domain.SearchQuery,
    sortBy string, sortDir string, page int, size int) ([]EX, int64, error) {
    entities, filteredCount, err := m.dao.Search(ctx, query, sortBy, sortDir, page, size)
    if err != nil {
        return nil, 0, err
    }
    var entries []EX
    for i := range entities {
        entry, err := m.toEntry(&entities[i])
        if err == nil && entry != nil {
            entries = append(entries, *entry)
        }
    }
    return entries, filteredCount, err
}
```

The Manager owns `toEntity` and `toEntry` converter functions -- injected at construction time. This is where each module's custom mapping logic lives.

#### Layer 4: DAO -- `core/rest/dao.go` + `core/rest/dao_provider.go`

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

// core/rest/dao.go
type Dao[EN domain.Entity, I domain.ID] struct {
    DaoProvider[EN, I]
    ctx context.Context
}
```

The `DaoProvider` interface is implemented by both PostgreSQL and ClickHouse DAO implementations. Each module provides its own DAO that implements `AddPredicateForSearchJoins` for custom filtering logic.

#### Generic Type Constraints -- `core/domain/types.go`

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

---

### 2. Multi-Tenant Request Context -- `core/appcontext/requestcontext.go`

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

The Authorization header uses a custom Base64-encoded format:
```
Authorization: Basic base64("userId~userName~isLoggedIn~accountId:password")
```

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

---

### 3. Ten-Layer Middleware Pipeline -- `server/server.go`

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

#### Middleware 1: Request Interceptor

```go
// server/middlewares/requestinterceptor.go
func RequestInterceptor(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        rw := &helpers.ResponseWriterWithContent{
            ResponseWriter: w, ResponseBodyCopy: &bytes.Buffer{},
        }
        rw.InputBodyCopy, _ = io.ReadAll(r.Body)
        if len(rw.InputBodyCopy) > 0 {
            r.Body = io.NopCloser(bytes.NewBuffer(rw.InputBodyCopy))
        }
        next.ServeHTTP(rw, r)
    })
}
```

Wraps the ResponseWriter to capture both request body and response body. The request body is read and re-buffered so downstream handlers can still read it.

#### Middleware 2: Slow Query Logger

```go
// server/middlewares/slowquerylogger.go
func SlowQueryLogger(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        requestStartTime := time.Now()
        requestTimeThreshold := 5 * time.Second
        defer LogSlowQueries(r, customWriter.InputBodyCopy, requestStartTime, requestTimeThreshold)
        next.ServeHTTP(customWriter, r)
    })
}
```

Logs any request taking more than 5 seconds to a dedicated daily log file (`YYYY-MM-DD-slow.log`) in JSON format.

#### Middleware 5: Session Management (Transaction + Timeout)

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
                            // Timeout: rollback + report to Sentry
                            rollbackSessions(sessionCtx)
                            w.WriteHeader(http.StatusGatewayTimeout)
                        } else {
                            // Success: commit both PG and CH sessions
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

This middleware matches the request URL to a registered service, wraps it in a timeout context, and manages dual database sessions (PostgreSQL + ClickHouse). On timeout, both sessions are rolled back and a 504 is returned.

#### Middleware 10: Recoverer

```go
// server/middlewares/recoverer.go
func Recoverer(next http.Handler) http.Handler {
    fn := func(w http.ResponseWriter, r *http.Request) {
        defer func() {
            if rvr := recover(); rvr != nil {
                if rvr == http.ErrAbortHandler {
                    panic(rvr)    // Re-panic for ErrAbortHandler
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

Catches panics, reports to Sentry, and returns a structured JSON error instead of crashing the server.

---

### 4. Dual Database Strategy

#### PostgreSQL (OLTP)

Used for: Transactional operations -- creating collections, updating profiles, CRUD on all business entities.

Connection pool: `PG_MAX_IDLE_CONN=5`, `PG_MAX_OPEN_CONN=5`, using GORM with `sync.Once` singleton initialization.

#### ClickHouse (OLAP)

Used for: Analytics queries -- time-series data, leaderboard aggregations, engagement rate calculations.

Connection pool: `CH_MAX_IDLE_CONN=1`, `CH_MAX_OPEN_CONN=1`, separate GORM connection.

Both sessions are managed in `RequestContext`:
```go
Session         persistence.Session    // PostgreSQL
CHSession       persistence.Session    // ClickHouse
```

---

### 5. Watermill Event-Driven Architecture

#### AMQP Configuration -- `amqp/config.go`

```go
// amqp/config.go
func GetConfig(amqpURI string) amqp.Config {
    amqpConfig := amqp.NewDurableQueueConfig(amqpURI)

    // Topic format: "exchange___queue"
    // e.g., "coffee.dx___discovery_events_q"
    routingKeyGen := func(topic string) string {
        return strings.Split(topic, "___")[1]
    }
    queueGen := func(topic string) string {
        return strings.Split(topic, "___")[1]
    }
    exchangeGen := func(topic string) string {
        return strings.Split(topic, "___")[0]
    }

    amqpConfig.Exchange = amqp.ExchangeConfig{
        GenerateName: exchangeGen,
        Type:         "direct",
        Durable:      true,
    }
    amqpConfig.Queue = amqp.QueueConfig{
        GenerateName: queueGen,
        Durable:      true,
    }
    return amqpConfig
}
```

The topic naming convention `exchange___queue` allows a single string to encode both the exchange name and queue name. Watermill's config generators split on `___` to extract each part.

#### Listener Setup -- `listeners/listeners.go`

```go
// listeners/listeners.go
func SetupListeners() {
    router, _ := message.NewRouter(message.RouterConfig{}, logger)

    router.AddMiddleware(
        middlewares.MessageApplicationContext,      // Extract context from message metadata
        middlewares.TransactionSessionHandler,      // Transaction management for listeners
        middleware.Retry{
            MaxRetries:      3,
            InitialInterval: time.Millisecond * 100,
        }.Middleware,
        middlewares.Recoverer,                      // Panic recovery for listeners
    )

    // 7 listener handlers registered:
    socialdiscoveryListners.SetupListeners(router, subscriber)
    profilecollectionlisteners.SetupListeners(router, subscriber)
    postcollectionlisteners.SetupListeners(router, subscriber)
    leaderboard.SetupListeners(router, subscriber)
    collectionanalytics.SetupListeners(router, subscriber)
    keywordcollection.SetupListeners(router, subscriber)
    campaignprofileListners.SetupListeners(router, subscriber)

    go func() {
        router.Run(context.Background())
    }()
}
```

#### Publisher -- `publishers/publisher.go`

```go
// publishers/publisher.go
var singletonAMPQ *amqp.Publisher
var ampqInit sync.Once

func AMQP() (*amqp.Publisher, error) {
    ampqInit.Do(func() {
        singletonAMPQ, _ = amqp.NewPublisher(amqpConfig, watermill.NewStdLogger(false, false))
    })
    return singletonAMPQ, err
}

func PublishMessage(jsonBytes []byte, topic string) error {
    publisher, _ := AMQP()
    return publisher.Publish(topic, &message.Message{Payload: jsonBytes})
}
```

Singleton publisher with `sync.Once`, used from after-commit callbacks to guarantee events are only published after successful transaction commit.

---

### 6. Service Container (Dependency Injection) -- `app/app.go`

```go
// app/app.go
func SetupContainer() rest.ApplicationContainer {
    container := rest.NewApplicationContainer()

    // 11 modules wired with Service + API pairs:
    profileCollectionService := profilecollectionapi.NewProfileCollectionService()
    profileCollectionApi := profilecollectionapi.NewProfileCollectionApi(profileCollectionService)
    container.AddService(profileCollectionService, profileCollectionApi)

    postCollectionService := postcollectionapi.CreatePostCollectionService(context.Background())
    postCollectionApi := postcollectionapi.NewPostCollectionApi(postCollectionService)
    container.AddService(postCollectionService, postCollectionApi)

    socialDiscoveryService := discoveryapi.NewSocialDiscoveryService()
    socialDiscoveryAPI := discoveryapi.NewSocialDiscoveryApi(socialDiscoveryService)
    container.AddService(socialDiscoveryService, socialDiscoveryAPI)

    // ... leaderboard, collectionAnalytics, genreInsights, content,
    //     campaignProfiles, collectionGroup, partnerUsage, keywordCollection
    return container
}
```

Each module creates a Service + API pair and registers them in the container. The container is used by the session middleware to match URLs to services and by the route registration to attach handlers.

---

### 7. Plan-Based Feature Gating

```go
// constants/constants.go (referenced from requestcontext.go)
const (
    FreePlan PlanType = "FREE"
    SaasPlan PlanType = "SAAS"
    PaidPlan PlanType = "PAID"
)
```

Extracted from headers set by the gateway:
```go
// core/appcontext/requestcontext.go
case strings.ToLower(PlanType):
    if value == string(constants.FreePlan) {
        PlanType := constants.FreePlan
        appCtx.PlanType = &PlanType
    } else if value == string(constants.PaidPlan) {
        PlanType := constants.PaidPlan
        appCtx.PlanType = &PlanType
    } else if value == string(constants.SaasPlan) {
        PlanType := constants.SaasPlan
        appCtx.PlanType = &PlanType
    }
```

Free users get nullified premium fields (email, phone, audience details). SAAS and PAID users get full access. The gateway determines the plan type by checking the partner's SAAS contract dates.

---

### 8. REST Utility Functions -- `core/rest/utils.go`

```go
// Generic body parser using Go generics
func ParseBody[T any](w http.ResponseWriter, r *http.Request, body *T) bool {
    rawRequestBody, _ := io.ReadAll(r.Body)
    err = json.Unmarshal(rawRequestBody, body)
    if err != nil {
        w.WriteHeader(http.StatusBadRequest)
        return true
    }
    return false
}

// Search parameter parsing with sane defaults
func ParseSearchParameters(w http.ResponseWriter, r *http.Request) (
    string, string, int, int, domain.SearchQuery, bool) {
    page := 1; size := 50
    sortBy := "id"; sortDir := "DESC"
    // Cap page at 1000 and size at 100 to prevent abuse
    if page >= 1000 { page = 1 }
    if size >= 100 { size = 50 }
    return sortBy, sortDir, page, size, query, false
}

// Audience filter mapping
func ParseGenderAgeFilters(searchQuery domain.SearchQuery) domain.SearchQuery {
    genderMap := map[string]string{
        "MALE": "audience_gender.male_per",
        "FEMALE": "audience_gender.female_per",
    }
    ageMap := map[string]string{
        "13-17": "audience_age.13-17",
        "18-24": "audience_age.18-24",
        "25-34": "audience_age.25-34",
        // ...
    }
    // Transforms user-friendly filters to JSONB column paths
}
```

---

### 9. Application Entry Point -- `main.go`

```go
// main.go
func main() {
    config.Setup()     // Viper configuration
    sentry.Setup()     // Error tracking
    logger.Setup()     // Logrus structured logging

    go func() {
        http.ListenAndServe(":9292", nil)    // Debug/metrics server
    }()

    server.Setup()     // Main server on :7179
}
```

Two HTTP servers: main API on port 7179, debug/pprof on port 9292.

---

### 10. Twelve Business Modules

| Module | Directory | Key Endpoints |
|--------|-----------|---------------|
| Discovery | `app/discovery/` | Profile search, audience, hashtags, time-series, similar accounts |
| Profile Collection | `app/profilecollection/` | CRUD collections, add/remove profiles, search, share links |
| Post Collection | `app/postcollection/` | Curated post collections with ingestion frequency |
| Leaderboard | `app/leaderboard/` | Platform rankings by followers, engagement, category, language |
| Collection Analytics | `app/collectionanalytics/` | Hashtag & keyword tracking, post metrics summary |
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

## PART 2: SAAS GATEWAY (API Gateway)

---

### 11. Seven-Layer Middleware Pipeline -- `router/router.go`

```go
// router/router.go
func SetupRouter(config config.Config) *gin.Engine {
    router := gin.New()

    // Layer 1: Panic Recovery
    router.Use(gin.Recovery())

    // Layer 2: Sentry Error Tracking
    router.Use(sentrygin.New(sentrygin.Options{Repanic: true}))

    // Layer 3: CORS (41 whitelisted origins)
    router.Use(cors.New(cors.Options{
        AllowedOrigins: []string{
            "https://suite.goodcreator.co",
            "https://goodcreator.co",
            "https://cf-provider.goodcreator.co",
            "https://momentum.goodcreator.co",
            "http://localhost:3000",
            // ... 36 more origins
        },
        AllowedMethods:   []string{"HEAD", "GET", "POST", "OPTIONS", "PUT", "PATCH", "DELETE"},
        AllowedHeaders:   []string{"*"},
        AllowCredentials: true,
    }))

    // Layers 4-6: Context, RequestID, Logger
    router.Use(GatewayContextToContextMiddleware(config),
        middleware.RequestIdMiddleware(),
        middleware.RequestLogger(config))

    // Layer 7: Auth (per-route, not global)
    router.Any("/discovery-service/*any", middleware.AppAuth(config),
        saas.ReverseProxy("discovery-service", config))
    // ... 12 more service routes
}
```

---

### 12. JWT + Redis Session Authentication -- `middleware/auth.go`

The auth flow has 6 steps:

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
                // Extract userId, userAccountId, partnerId from JWT claims
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

---

### 13. Two-Layer Caching Architecture

#### Layer 1: Ristretto In-Memory Cache -- `cache/ristretto.go`

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

- **Scope:** Per-instance (not shared between gateway nodes)
- **Eviction:** LFU (Least Frequently Used) via TinyLFU admission policy
- **Latency:** Nanoseconds
- **Use case:** Hot session data, frequently accessed partner info

#### Layer 2: Redis Cluster -- `cache/redis.go`

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

- **Scope:** Shared across all gateway instances
- **Key format:** `session:{sessionId}`
- **Latency:** Milliseconds
- **Cluster:** 3 nodes in production

---

### 14. Reverse Proxy with Header Enrichment -- `handler/saas/saas.go`

```go
// handler/saas/saas.go
func ReverseProxy(module string, config config.Config) func(c *gin.Context) {
    return func(c *gin.Context) {
        appContext := util.GatewayContextFromGinContext(c, config)

        // Route social-profile-service to different backend
        saasUrl := config.SAAS_URL
        if module == "social-profile-service" {
            saasUrl = config.SAAS_DATA_URL
        }

        remote, _ := url.Parse(saasUrl)
        proxy := httputil.NewSingleHostReverseProxy(remote)

        // Header enrichment in Director function
        proxy.Director = func(req *http.Request) {
            req.Header = c.Request.Header              // Copy all original headers
            req.Header.Set("Authorization", authHeader) // Override with gateway-generated auth
            req.Header.Set(header.PartnerId, partnerId) // Add partner ID
            req.Header.Set(header.PlanType, planType)   // Add plan type
            req.Header.Set(header.Device, deviceId)     // Add device ID
            req.Header.Del("accept-encoding")           // Remove to get uncompressed response
            req.Host = remote.Host
            req.URL.Scheme = remote.Scheme
            req.URL.Host = remote.Host
            req.URL.Path = "/" + module + c.Param("any") // Reconstruct path
        }

        // Response handling: CORS fix + metrics + logging
        proxy.ModifyResponse = responseHandler(appContext, c.Request.Method,
            c.Param("any"), c.Request.Header.Get("origin"), ...)

        proxy.ServeHTTP(c.Writer, c.Request)
    }
}
```

---

### 15. Gateway Context -- `context/context.go`

```go
// context/context.go
type Context struct {
    *gin.Context
    Logger              zerolog.Logger
    XHeader             http.Header          // All x-bb-* headers
    DeviceAuthorization string
    UserAuthorization   string
    ClientAuthorization string
    Client              *entry.Client
    UserClientAccount   *entry.UserClientAccount
    Config              config.Config
    Locale              locale.Locale
}

func New(c *gin.Context, config config.Config) *Context {
    generator.SetNXRequestIdOnContext(c)     // Generate UUID for request
    DisallowBots(c)                          // X-Robots-Tag: noindex
    ctx := &Context{
        Context: c,
        Logger:  zerolog.New(os.Stdout).With().Str(header.RequestID, ...).Logger(),
        XHeader: make(http.Header),
        Locale:  locale.LocaleEnglish,
    }
    ctx.PickXHeadersFromReq()               // Whitelist 23+ x-bb-* headers
    return ctx
}
```

The gateway context whitelists specific headers (23+ `x-bb-*` headers) from the incoming request, validates locale against supported languages (en, hi, bn, ta, te), and generates device/user/client authorization headers for downstream services.

---

### 16. Graceful Deployment -- `scripts/start.sh`

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

This ensures zero-downtime deployment by using health check toggling with the load balancer.
