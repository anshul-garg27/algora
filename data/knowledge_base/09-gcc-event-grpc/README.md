# Event-gRPC: High-Throughput Event Ingestion Service

## Company Context

**Good Creator Co. (GCC)** -- SaaS platform for influencer marketing analytics, powering real-time insights for brands and creators across mobile, web, and third-party integrations.

**Event-gRPC** is the central nervous system for all analytics data -- a Go-based event ingestion service that receives, validates, routes, and persists 10M+ daily data points across 60+ event types.

---

## Resume Bullets Covered

| Bullet | Text | How Event-gRPC Maps |
|--------|------|---------------------|
| **Bullet 2** | "Designed an asynchronous data processing system handling 10M+ daily data points" | gRPC ingestion with 6 worker pools, 26 RabbitMQ queues, 90+ concurrent workers processing events from mobile/web/backend clients |
| **Bullet 3** | "Built a high-performance logging system with RabbitMQ, transitioning to ClickHouse, 2.5x faster retrieval" | Buffered sinker pattern (ticker + batch flush) writing to ClickHouse; 18+ analytical tables replacing slow PostgreSQL queries |

---

## Architecture Diagram

```
CLIENT APPLICATIONS (Mobile, Web, Backend Services)
                    |
        gRPC (Protobuf)  +  HTTP (JSON)
                    |
    +=======================================+
    |         EVENT-GRPC SERVICE            |
    |                                       |
    |  gRPC Server (:8017)                  |
    |    - dispatch(Events) RPC             |
    |    - Health Check (Watch/Check)       |
    |                                       |
    |  HTTP Server (:8019, Gin)             |
    |    - /heartbeat (LB control)          |
    |    - /metrics (Prometheus)            |
    |    - /vidooly/event                   |
    |    - /branch/event                    |
    |    - /webengage/event                 |
    |    - /shopify/event                   |
    |    - /graphy/event                    |
    |                                       |
    |  6 Worker Pools                       |
    |    Event | Branch | WebEngage         |
    |    Vidooly | Graphy | Shopify         |
    |    (buffered channels, 1000 cap each) |
    +=======================================+
                    |
            Publish (JSON/Protobuf)
                    |
    +=======================================+
    |         RABBITMQ BROKER               |
    |  11 Exchanges, 26 Queues              |
    |  90+ Consumer Workers                 |
    |  Retry logic (max 2) + DLQ            |
    |  Prefetch QoS=1, Durable queues       |
    +=======================================+
                    |
        +-----------+-----------+
        |           |           |
   ClickHouse   PostgreSQL   External APIs
   (Analytics)  (Transact.)  (WebEngage,
   18+ tables   Schema-based  Identity,
   Multi-DB     Pool: 10/20   SocialStream)
   GORM ORM
   Auto-reconnect (1s cron)
```

---

## Key Numbers

| Metric | Value |
|--------|-------|
| Total Lines of Code | 10,000+ |
| Go Source Files | 90+ |
| Proto Definition | 688 lines |
| Event Types | 60+ (oneof in proto) |
| Worker Pools | 6 |
| RabbitMQ Exchanges | 11 |
| RabbitMQ Queues | 26 configured in main.go |
| Consumer Workers | 90+ concurrent |
| Buffered Channel Capacity | 1000 per pool + 10,000 per sinker |
| ClickHouse Tables | 18+ |
| Sinker Functions | 20+ (direct + buffered) |
| Batch Flush Threshold | 100 events (buffered sinkers) |
| Flush Interval | 5 minutes (ticker) |
| Ingestion Target | ~10K events/sec |
| Daily Data Points | 10M+ |
| Direct Dependencies | 30+ |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Go 1.14 |
| RPC Framework | gRPC + Protocol Buffers |
| HTTP Framework | Gin |
| Message Broker | RabbitMQ (streadway/amqp) |
| Analytics DB | ClickHouse (GORM driver) |
| Transactional DB | PostgreSQL (jinzhu/gorm) |
| Cache | Redis Cluster + Ristretto |
| Monitoring | Prometheus + Sentry |
| CI/CD | GitLab CI |
| Client Libraries | Go, Java (Maven), JavaScript (NPM) |

---

## File Index

| File | Purpose |
|------|---------|
| [01-technical-implementation.md](./01-technical-implementation.md) | Actual code from the repo with annotations |
| [02-technical-decisions.md](./02-technical-decisions.md) | 10 "Why X not Y?" design decisions |
| [03-interview-qa.md](./03-interview-qa.md) | Q&A pairs for gRPC, RabbitMQ, ClickHouse |
| [04-how-to-speak.md](./04-how-to-speak.md) | Speaking guide, elevator pitches, STAR stories |
| [05-scenario-questions.md](./05-scenario-questions.md) | 10 "What if X fails?" production scenarios |

---

## Quick Elevator Pitch

> "I built Event-gRPC, the real-time event ingestion backbone for GCC's influencer analytics platform. It's a Go service that handles 10M+ daily data points across 60+ event types. Events arrive via gRPC, get validated and grouped by type with timestamp correction, then fan out through 26 RabbitMQ queues to 90+ consumer workers. High-volume streams use a buffered sinker pattern -- events accumulate in Go channels and flush in batches to ClickHouse, which gave us 2.5x faster retrieval over the previous PostgreSQL setup. The whole system self-heals with auto-reconnecting database connections and dead letter queues for failed messages."
