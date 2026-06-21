# Coffee + SaaS Gateway - Complete Interview Guide

> **Resume Bullets Covered:** 1, 6
> **Bullet 1:** "Optimized API response times by 25% and reduced operational costs by 30%" (Redis caching, ClickHouse analytics)
> **Bullet 6:** "Developed real-time social media insights modules, driving 10% user engagement growth" (Genre Insights, Keyword Analytics)
> **Company:** Good Creator Co. (GCC) - goodcreator.co
> **Repos:** `coffee`, `saas-gateway`

---

## Quick Navigation

| File | Purpose |
|------|---------|
| [01-technical-implementation.md](./01-technical-implementation.md) | Actual code: 4-layer REST, generics, middleware, caching |
| [02-technical-decisions.md](./02-technical-decisions.md) | "Why X not Y?" for 10 decisions with follow-ups |
| [03-interview-qa.md](./03-interview-qa.md) | Q&A covering multi-tenancy, API design, caching |
| [04-how-to-speak.md](./04-how-to-speak.md) | How to talk about this project in interviews |
| [05-scenario-questions.md](./05-scenario-questions.md) | "What if?" - 10 failure scenario walkthroughs |

---

## 30-Second Pitch

> "At Good Creator Co., I built the core backend for a SaaS influencer analytics platform. The main system, Coffee, is a multi-tenant Go REST API serving 50+ endpoints across 12 business modules -- discovery, leaderboards, collections, genre insights, keyword analytics. I designed a generic 4-layer architecture using Go generics so every module follows the same API-Service-Manager-DAO pattern with type-safe CRUD. It uses PostgreSQL for OLTP and ClickHouse for analytics, with Watermill for event-driven processing. In front of it sits the SaaS Gateway, which I also built -- an API gateway proxying all 13 microservices with JWT + Redis session auth, a two-layer cache (Ristretto + Redis), and header enrichment for multi-tenant routing."

---

## Key Numbers to Memorize

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

---

## Two-System Architecture Diagram

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

---

## Services Proxied by Gateway (13 Total)

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

---

## Resume Bullet Mapping

### Bullet 1: "Optimized API response times by 25% and reduced operational costs by 30%"

| Claim | Evidence in Code |
|-------|-----------------|
| API response time optimization | Two-layer caching (Ristretto nanosecond + Redis millisecond) in gateway; ClickHouse OLAP for analytics queries instead of PostgreSQL |
| Redis caching | `cache/redis.go` -- Redis cluster with 100 pool size for session caching; `cache/ristretto.go` -- 10M key in-memory LFU cache |
| ClickHouse analytics | `core/persistence/clickhouse/db.go` -- Separate OLAP connection; dual session management in `RequestContext.CHSession` |
| Operational cost reduction | ClickHouse columnar storage reduces analytics query costs; Ristretto eliminates redundant Identity service calls |

### Bullet 6: "Developed real-time social media insights modules"

| Claim | Evidence in Code |
|-------|-----------------|
| Genre Insights | `app/genreinsights/` -- Full module with API/Service/Manager/DAO layers |
| Keyword Analytics | `app/keywordcollection/` -- Keyword-based collection analytics |
| Discovery module | `app/discovery/` -- Profile search, time-series, hashtags, audience demographics |
| User engagement growth | Leaderboard rankings, collection analytics, post metrics summary tables |
