# Event-gRPC: How to Speak About This Project

This guide provides pitches of varying lengths, STAR stories, and phrasing tips for naturally weaving Event-gRPC into interview conversations.

---

## Elevator Pitches

### 15-Second Pitch (Hallway Version)

> "I built the event ingestion backbone for a SaaS analytics platform -- a Go service that handles 10 million daily data points through gRPC, fans them across 26 RabbitMQ queues, and batch-writes to ClickHouse for 2.5x faster analytics."

### 30-Second Pitch (Intro Round)

> "At Good Creator Co., I designed and built Event-gRPC, the high-throughput event ingestion system for our influencer marketing analytics platform. It receives events from mobile and web clients via gRPC with 60+ typed event definitions in Protocol Buffers, routes them through 26 RabbitMQ queues with 90+ concurrent workers, and persists them to ClickHouse using a buffered sinker pattern for batch inserts. The system processes 10 million events daily, and the ClickHouse migration gave us 2.5x faster query performance over our previous PostgreSQL setup."

### 60-Second Pitch (Technical Deep Dive Intro)

> "At Good Creator Co., our analytics platform needed to ingest events from multiple sources -- mobile apps, web clients, and third-party webhooks from Shopify, Branch.io, and WebEngage -- all in real time. I built Event-gRPC, a Go service that handles this.
>
> Events arrive via gRPC for our own clients -- we defined 60+ event types in Protocol Buffers using the `oneof` pattern for type-safe polymorphism. Third-party events come in through HTTP webhooks on a parallel Gin server.
>
> Incoming events hit a worker pool -- configurable goroutines reading from a buffered channel. Workers group events by type, correct any future timestamps from bad device clocks, and publish to RabbitMQ with the event type as the routing key. RabbitMQ's exchange-based routing fans this into 26 specialized queues.
>
> On the consumer side, high-volume streams use a buffered sinker pattern: events accumulate in a Go channel and flush to ClickHouse in batches of 100 or every 5 minutes. This is critical because ClickHouse's columnar storage is optimized for batch writes. Lower-volume streams write directly.
>
> The system handles 10M+ daily events with 90+ concurrent consumers. ClickHouse gave us 2.5x faster analytics queries over PostgreSQL, and the whole thing self-heals with auto-reconnecting database connections and dead letter queues for failed messages."

---

## STAR Stories

### STAR Story 1: Designing the Asynchronous Processing Pipeline

**Situation:** GCC's analytics platform was receiving events from mobile apps, web clients, and third-party webhooks, but the existing approach was synchronous -- events were written directly to PostgreSQL, causing timeouts under load and corrupting analytics data when timestamps were wrong.

**Task:** I needed to design an asynchronous event processing pipeline that could handle 10M+ daily events across 60+ types with reliable delivery, correct timestamps, and faster analytics queries.

**Action:**
- Designed a gRPC service with Protocol Buffers defining 60+ event types using `oneof` for type-safe polymorphism
- Built 6 worker pools (one per event source) with buffered channels and configurable concurrency
- Implemented event grouping by type with timestamp correction -- clamping future timestamps to server time
- Set up RabbitMQ with 11 exchanges and 26 queues for content-based routing, each with retry logic (max 2) and dead letter queues
- Created two sinker patterns: direct writes for low-volume events and buffered sinkers (batch of 100 or 5-minute timer) for high-volume streams
- Migrated the analytics store from PostgreSQL to ClickHouse with multi-database support

**Result:** The system processes 10M+ daily data points with 90+ concurrent workers. ClickHouse queries run 2.5x faster than the previous PostgreSQL queries. The dead letter queue pattern caught data quality issues that were previously invisible. Zero-downtime deployments via gRPC health checks and load balancer integration.

---

### STAR Story 2: Building the Buffered Sinker for ClickHouse

**Situation:** After migrating from PostgreSQL to ClickHouse, we noticed the "too many parts" error -- ClickHouse's MergeTree engine was struggling with the high rate of small INSERT statements from our 20 post-log consumer workers.

**Task:** I needed to reduce the INSERT frequency without losing data or adding significant latency.

**Action:**
- Designed the buffered sinker pattern: each consumer pushes parsed events into a Go channel (10K capacity)
- A dedicated goroutine reads from the channel with a `select` statement that has two triggers: batch size (100 events) and time interval (5 minutes)
- When either trigger fires, the accumulated batch is flushed to ClickHouse in a single batch INSERT via GORM
- This reduced the INSERT rate from 20/second (one per consumer per message) to roughly 1 every few seconds

**Result:** The "too many parts" errors disappeared entirely. ClickHouse merge performance improved because it processed fewer, larger data parts. The dual-trigger ensures data freshness even during low-traffic periods -- nothing sits in the buffer for more than 5 minutes.

---

### STAR Story 3: Handling RabbitMQ Connection Failures

**Situation:** In production, the RabbitMQ server occasionally restarted for maintenance, causing all 90+ consumers to lose their connection. The service would crash and require manual restart.

**Task:** Make the service self-healing so that RabbitMQ restarts are transparent to the operation.

**Action:**
- Implemented the `rabbitConnector` pattern: a forever-loop goroutine that connects, waits for close notification via `NotifyClose`, and auto-reconnects with 1-second backoff
- Wrapped the initial connection with a 5-second timeout so the service starts even if RabbitMQ is temporarily down
- Used `sync.Once` to ensure only one connection attempt happens regardless of how many goroutines call `Rabbit(config)` concurrently
- Applied the same auto-reconnect pattern to ClickHouse (1-second health cron) and PostgreSQL

**Result:** RabbitMQ restarts became transparent -- the service detects the dropped connection, reconnects within seconds, and consumers resume processing. The same pattern for ClickHouse and PostgreSQL means the service can ride out brief database maintenance windows without manual intervention.

---

## Key Phrases to Use

### When Describing Scale
- "10 million daily data points across 60+ event types"
- "90+ concurrent consumer workers across 26 RabbitMQ queues"
- "10K events per second ingestion rate"
- "6 independent worker pools with configurable concurrency"

### When Describing Architecture Choices
- "We used Protocol Buffers' `oneof` for type-safe polymorphism across 60+ event types"
- "Content-based routing via RabbitMQ exchanges -- the event type name becomes the routing key"
- "Buffered sinker pattern: batch accumulation with dual-trigger flush (size OR time)"
- "Singleton connections with lazy initialization via `sync.Once`"
- "End-to-end backpressure from ClickHouse through RabbitMQ to the gRPC handler"

### When Describing Impact
- "2.5x faster analytics queries after migrating from PostgreSQL to ClickHouse"
- "Zero data loss with dead letter queues capturing failed messages for replay"
- "Zero-downtime deployments via gRPC health checks and load balancer drain"
- "Self-healing connections -- the service rides out database restarts automatically"

### When Describing Go Expertise
- "Worker pool pattern with buffered channels for bounded concurrency"
- "Every goroutine wrapped in panic recovery to prevent cascade failures"
- "`sync.Once` for thread-safe lazy initialization of all connection pools"
- "Go's `select` statement for dual-trigger batch flushing"
- "Protobuf reflection for dynamic event type routing"

---

## Common Follow-Up Questions and Pivot Points

### "What was the hardest part of this project?"

**Pivot to:** Buffered sinker design. "The hardest part was getting the batch flush right for ClickHouse. We needed to balance throughput (batch as many events as possible) against latency (don't let events sit in the buffer too long). The dual-trigger `select` on batch size and time interval solved this elegantly -- but I had to tune the batch size and interval through load testing to find the sweet spot."

### "What would you do differently?"

**Pivot to:** Code generation. "The event transformation code in `eventsinker.go` is 1477 lines of sequential nil-checks for each of the 60+ event types. I would use code generation from the proto definition to auto-generate these transformations. I'd also add circuit breakers around the ClickHouse writes -- right now a down ClickHouse relies on the RabbitMQ retry, but a circuit breaker would be more responsive."

### "How did you test this?"

**Pivot to:** Integration approach. "We had unit tests for the parsers and transformation functions, and integration tests that spun up local RabbitMQ and ClickHouse instances. The real confidence came from the dead letter queue pattern -- in staging, we could see exactly which events failed and why. We also used Prometheus metrics to monitor queue depth and batch sizes, catching issues before they hit production."

### "How does this compare to systems at larger scale (Google, etc.)?"

**Pivot to:** Principles. "The fundamental patterns are the same -- worker pools for bounded concurrency, message queues for decoupling, batch writes for columnar stores, and dead letter queues for error handling. At Google scale, you'd swap RabbitMQ for Pub/Sub, ClickHouse for Bigtable or BigQuery, and add partition-level parallelism. But the architecture -- ingest, route, buffer, batch-write -- scales to any volume. The difference is operational tooling, not design."

---

## Do's and Don'ts

### DO
- Lead with the problem ("10M daily events needed reliable ingestion")
- Mention the numbers: 60+ types, 26 queues, 90+ workers, 2.5x faster
- Explain WHY you chose each technology (gRPC for type safety, RabbitMQ for smart routing)
- Reference specific code patterns (worker pool, buffered sinker, sync.Once)
- Connect to the resume bullet: "This is the system behind the 10M daily data points bullet"

### DON'T
- Don't say "I just set up RabbitMQ" -- explain the exchange/routing architecture
- Don't describe ClickHouse as "just a database" -- emphasize columnar, batch-optimized, 2.5x improvement
- Don't skip the backpressure story -- it shows you think about failure modes
- Don't forget the HTTP hybrid -- it shows pragmatism over dogmatic architecture
- Don't undersell the proto work -- 688 lines of typed definitions across 3 languages is significant

---

## Mapping to Common Interview Themes

| Interview Theme | Event-gRPC Example |
|-----------------|-------------------|
| **System Design** | "Design a real-time event pipeline" -- this IS that system |
| **Distributed Systems** | RabbitMQ routing, auto-reconnect, DLQ, eventual consistency |
| **Go Proficiency** | Worker pools, channels, sync.Once, goroutines, panic recovery |
| **Database Design** | ClickHouse vs PostgreSQL tradeoff, batch inserts, multi-DB |
| **API Design** | gRPC + REST hybrid, proto versioning, health checks |
| **Reliability** | Retry logic, DLQ, auto-reconnect, graceful deployment |
| **Performance** | Buffered sinkers, batch inserts, 2.5x improvement |
| **Scale** | 10M daily, 90+ workers, configurable concurrency |
