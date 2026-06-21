# Event-gRPC: Technical Decisions -- "Why X not Y?"

These 10 design decisions come up frequently in system design interviews. Each answer explains the tradeoff, references actual code, and provides a concise interview-ready response.

---

## 1. Why gRPC + HTTP hybrid vs pure REST?

**Decision:** gRPC on port 8017 for high-throughput event ingestion from mobile/backend clients, HTTP/Gin on port 8019 for webhooks, health checks, and metrics.

**Why gRPC for events:**
- Protocol Buffers give 5-10x smaller payloads than JSON for mobile clients on slow networks
- Strongly-typed contracts with 60+ event types via `oneof` -- compile-time safety across Go, Java, and JavaScript clients
- HTTP/2 multiplexing -- multiple event batches on a single connection
- Binary serialization is 3-5x faster than JSON parsing at 10K events/sec

**Why keep HTTP:**
- Third-party webhooks (Vidooly, Branch, WebEngage, Shopify) send standard HTTP POST with JSON
- `/metrics` endpoint for Prometheus (standard HTTP scraping)
- `/heartbeat` endpoint for load balancer health checks
- No control over third-party webhook format -- they will not adopt gRPC

**Code evidence:**
```go
// gRPC server in goroutine
go func() {
    s := grpc.NewServer()
    bulbulgrpc.RegisterEventServiceServer(s, &server{})
    s.Serve(lis)
}()

// HTTP server blocks main goroutine
router.SetupRouter(config).Run(":" + config.GinPort)
```

**Interview answer:** "We used gRPC for our own mobile and backend clients because protobuf gives us 5-10x smaller payloads and type safety across 60+ event types. But we kept an HTTP server alongside it because third-party integrations like Shopify and Branch.io only support webhooks, and our Prometheus metrics and load balancer health checks use standard HTTP."

---

## 2. Why RabbitMQ vs Kafka?

**Decision:** RabbitMQ with 11 exchanges and 26 queues for event routing.

**Why RabbitMQ:**
- **Smart routing needed:** Exchange-based routing with routing keys (e.g., `CLICK` events to click queue, `APP_INIT` to init queue). Kafka requires consumer-side filtering
- **Per-message acknowledgment:** Critical for retry logic -- if processing fails, the specific message can be re-queued. Kafka only tracks offsets
- **Dead letter exchanges:** Native DLQ support. Failed messages route to error exchanges after max retries. Kafka DLQ requires custom implementation
- **Lower operational overhead:** Single-node RabbitMQ vs Kafka cluster (ZooKeeper + brokers)
- **Message-level retry:** `x-retry-count` header incremented per message. Kafka would require a separate retry topic

**Why NOT Kafka:**
- We did not need ordered processing (events are independent)
- We did not need replay capability (events are append-only to ClickHouse)
- Our daily volume (10M events) is well within RabbitMQ capacity
- Would have been over-engineering for our team size at a startup

**Code evidence:**
```go
// Smart routing: event type name becomes routing key
rabbitConn.Publish(config.EVENT_SINK_CONFIG.EVENT_EXCHANGE,
    eventName,  // "LaunchEvent", "CLICK", "APP_INIT", etc.
    b, map[string]interface{}{})

// Retry with per-message header
msg.Headers[header.XRetryCount] = retryCount
rabbit.Publish(rabbitConsumerConfig.Exchange,
    rabbitConsumerConfig.RoutingKey, msg.Body, msg.Headers)
```

**Interview answer:** "We chose RabbitMQ because we needed smart routing -- exchange-based routing keys let us fan events from one gRPC endpoint to 26 specialized queues without consumer-side filtering. We also needed per-message acknowledgment for our retry logic. Kafka would have been overkill -- we didn't need ordering guarantees or replay, and at 10M daily events RabbitMQ handles the volume easily with lower ops overhead for a startup team."

---

## 3. Why buffered sinkers vs direct writes?

**Decision:** High-volume event streams (trace logs, post logs, sentiment) use buffered sinkers with batch flush; lower-volume streams (branch events, app init) use direct writes.

**Why buffered for high-volume:**
- ClickHouse is a columnar database optimized for batch inserts -- inserting 100 rows at once is barely more expensive than inserting 1 row
- Reduces network round trips: 1 INSERT per batch vs 100 separate INSERTs
- Post log queue has 20 workers -- without batching, 20 concurrent single-row inserts would bottleneck ClickHouse's merge tree
- The `select` on channel + ticker gives dual-trigger semantics: flush on batch size OR time interval

**Why direct for low-volume:**
- Branch events, app init events have low volume -- batching would add unnecessary latency
- These events often trigger downstream actions (referral processing, A/B assignment) where immediacy matters
- Simpler code path -- no need for a separate flush goroutine

**Code evidence:**
```go
// Buffered: post_log_events_q has 20 workers, batches of 100
postLogChan := make(chan interface{}, 10000)
postLogConsumerConfig.ConsumerCount = 20
go sinker.PostLogEventsSinker(postLogChan)

// Direct: app_init_event_q has 2 workers, immediate write
clickhouseAppInitEventConsumerCfg.ConsumerCount = 2
clickhouseAppInitEventConsumerCfg.ConsumerFunc = sinker.SinkAppInitEventToClickhouse
```

**Interview answer:** "We used a buffered sinker pattern for high-volume streams like post logs and trace logs. ClickHouse is columnar -- batch inserts are dramatically more efficient than row-by-row writes. The buffer accumulates events in a Go channel and flushes either when we hit 100 events or every 5 minutes, whichever comes first. For low-volume streams like branch events, we write directly because the added latency of batching isn't worth the complexity."

---

## 4. Why ClickHouse vs PostgreSQL for events?

**Decision:** ClickHouse as the primary analytics store, PostgreSQL retained only for transactional data (referrals, user accounts).

**Why ClickHouse for events:**
- **Columnar storage:** Analytics queries (aggregations, time-series) scan only relevant columns. A query like "count events by type this week" reads 1 column instead of full rows
- **10-100x compression:** Event data with repetitive strings (event names, device IDs) compresses dramatically in columnar format
- **2.5x faster retrieval** over PostgreSQL for the same queries (measured after migration)
- **Append-only workload:** Events are never updated -- perfect for ClickHouse's MergeTree engine
- **Scale-out architecture:** Can add shards as data grows without application changes

**Why keep PostgreSQL:**
- Referral events need transactions (check if user exists, then insert referral)
- User account creation requires ACID guarantees
- Schema-based multi-tenancy (`config.POSTGRES_EVENT_SCHEMA + "." + tableName`)
- These are low-volume, write-rarely workloads where PostgreSQL excels

**Code evidence:**
```go
// ClickHouse: batch insert for analytics
clickhouse.Clickhouse(config.New(), nil).Create(events)

// PostgreSQL: transactional referral processing
pg.PG(config.New()).Create(&referralEvent)
```

**Interview answer:** "We migrated our event analytics from PostgreSQL to ClickHouse and saw a 2.5x improvement in query performance. ClickHouse's columnar storage is ideal for our workload -- events are append-only, and analytics queries aggregate across millions of rows but only need a few columns. We kept PostgreSQL for transactional data like referrals and user accounts where we need ACID guarantees."

---

## 5. Why Go channels for worker pools vs goroutine-per-request?

**Decision:** Fixed-size worker pools with buffered channels instead of spawning a goroutine per incoming gRPC request.

**Why worker pools:**
- **Bounded concurrency:** At 10K events/sec, goroutine-per-request would spawn 10K goroutines per second, each holding a RabbitMQ channel. Channel exhaustion would crash the service
- **Backpressure:** When the channel is full, the `select` with timeout returns an error to the client instead of accepting unbounded work
- **Memory predictability:** Fixed pool size means predictable memory usage. Goroutine-per-request has unbounded memory growth under spikes
- **Connection reuse:** Workers hold long-lived RabbitMQ connections. Per-request goroutines would need connection pooling

**Why buffered channels (not unbuffered):**
- Buffer of 1000 absorbs burst traffic without blocking the gRPC handler
- Acts as a shock absorber between ingestion rate and processing rate
- The 1-second timeout in `DispatchEvent` prevents indefinite blocking when buffer is full

**Code evidence:**
```go
// Buffered channel absorbs bursts
eventWrapperChannel = make(chan bulbulgrpc.Events,
    config.EVENT_WORKER_POOL_CONFIG.EVENT_BUFFERED_CHANNEL_SIZE)

// Fixed pool size
for i := 0; i < workerPoolSize; i++ {
    safego.GoNoCtx(func() { worker(config, eventChannel) })
}

// Backpressure: timeout instead of blocking forever
select {
case <-time.After(1 * time.Second):
    gCtx.Logger.Log().Msgf("Error publishing event: %v", events)
case eventChannel <- events:
    processedEvent = true
}
```

**Interview answer:** "We used fixed-size worker pools with buffered channels instead of goroutine-per-request. At 10K events per second, spawning a goroutine per request would exhaust our RabbitMQ channel limit and cause unbounded memory growth during traffic spikes. The buffered channel absorbs burst traffic, and if it fills up, the 1-second timeout returns a fast error to the client instead of blocking. This gives us predictable resource usage and natural backpressure."

---

## 6. Why Protocol Buffers vs JSON?

**Decision:** Protocol Buffers for the event schema, with protojson for RabbitMQ serialization.

**Why Protobuf:**
- **Type safety across languages:** One `.proto` file generates Go, Java, and JavaScript clients. JSON schemas are informal and error-prone
- **`oneof` for 60+ event types:** Each event type has its own message with specific fields. JSON would require ad-hoc validation
- **Smaller payloads:** Binary encoding is 5-10x smaller than JSON, critical for mobile clients on cellular networks
- **Forward/backward compatibility:** Adding new event types (new `oneof` variants) doesn't break existing clients
- **Code generation:** `protoc` generates serialization, deserialization, and gRPC stubs automatically

**Why protojson for RabbitMQ (not raw binary):**
- Downstream consumers may be in non-Go languages -- JSON is universally readable
- Debugging: JSON messages in RabbitMQ management UI are human-readable
- `protojson.Marshal` preserves the protobuf schema while producing standard JSON

**Code evidence:**
```protobuf
// Cross-language: Go, Java, JavaScript
option go_package = "proto/go/bulbulgrpc";
option java_package = "com.bulbul.grpc.event";

// Type-safe 60+ event types
oneof EventOf {
    LaunchEvent launchEvent = 9;
    AddToCartEvent addToCartEvent = 23;
    CompletePurchaseEvent completePurchaseEvent = 26;
    // ... 60+ total
}
```

```go
// Protobuf-to-JSON for RabbitMQ
b, err := protojson.Marshal(&e)
rabbitConn.Publish(exchange, eventName, b, headers)

// JSON-from-Protobuf on consumer side
protojson.Unmarshal(delivery.Body, grpcEvent)
```

**Interview answer:** "We used Protocol Buffers for the event schema because it gives us type safety across Go, Java, and JavaScript clients from a single definition file. The `oneof` construct lets us define 60+ event types with specific fields per type -- something JSON schemas can't enforce at compile time. For RabbitMQ messaging we serialize to protojson, which gives us human-readable JSON while preserving the schema structure."

---

## 7. Why sync.Once singleton vs global init?

**Decision:** All connection pools (RabbitMQ, ClickHouse, PostgreSQL, worker channels) use `sync.Once` for lazy initialization instead of package-level `init()`.

**Why sync.Once:**
- **Lazy initialization:** Connections only created when first needed, not at import time. This matters during testing -- importing the package doesn't force a DB connection
- **Thread-safe:** Multiple goroutines calling `Rabbit(config)` concurrently will only trigger one connection attempt. Package `init()` runs once but at import time, not first-use time
- **Config-dependent:** Connection parameters come from the `Config` struct, which is itself lazily loaded from `.env` files. `init()` would need to hardcode the config loading order
- **Testability:** Can mock or replace the singleton in tests without package-level side effects

**Why NOT global init():**
- `init()` cannot accept parameters -- we need the `config.Config` struct
- `init()` runs at import time, which makes test setup painful
- Circular dependency risk: if `clickhouse.init()` needs `config.Config`, and `config.init()` needs something from another package

**Code evidence (pattern used in 4 places):**
```go
// ClickHouse: lazy init with config
var clickhouseInit sync.Once
func Clickhouse(config config.Config, dbName *string) *gorm.DB {
    clickhouseInit.Do(func() { connectToClickhouse(config) })
    return singletonClickhouseMap[...]
}

// RabbitMQ: lazy init with config
var rabbitInit sync.Once
func Rabbit(config config.Config) *RabbitConnection {
    rabbitInit.Do(func() { /* connect */ })
    return singletonRabbit
}

// Worker channel: lazy init with config
var channelInit sync.Once
func GetChannel(config config.Config) chan bulbulgrpc.Events {
    channelInit.Do(func() { /* create channel + pool */ })
    return eventWrapperChannel
}
```

**Interview answer:** "We used `sync.Once` for all connection pools instead of package `init()` because our connections are config-dependent -- the DB credentials come from environment-specific config that's also lazily loaded. `sync.Once` gives us thread-safe lazy initialization: the first goroutine that calls `Clickhouse(config)` creates the connection, and all subsequent calls get the cached instance. This also makes testing easier because importing the package doesn't force a database connection."

---

## 8. Why dead letter queues vs infinite retry?

**Decision:** Maximum 2 retries per message, then route to a dead letter queue (error exchange). No infinite retry.

**Why cap at 2 retries:**
- **Poison messages:** A malformed event that causes a parsing error will never succeed no matter how many times you retry. Infinite retry would create an infinite loop
- **Resource protection:** A stuck message blocks the consumer (QoS prefetch=1). Infinite retry on one bad message starves all other messages in the queue
- **Observability:** Dead letter queues make failures visible. Ops can inspect the error queue, fix the issue, and replay messages. Silent infinite retry hides problems
- **SLA compliance:** With 2 retries + DLQ, a transient failure (ClickHouse momentarily unreachable) gets retried, but a permanent failure (invalid schema) gets captured quickly

**Why NOT just drop failed messages:**
- Analytics data is valuable -- we want to capture and replay failed events after fixing the root cause
- Error queues provide a natural audit trail for data quality issues

**Code evidence:**
```go
retryCount := transformer.InterfaceToInt(retryCountInterface)
if retryCount >= 2 {
    requeue = false
    // Route to dead letter queue
    rabbit.Publish(*rabbitConsumerConfig.ErrorExchange,
        *rabbitConsumerConfig.ErrorRoutingKey, msg.Body, msg.Headers)
} else {
    retryCount++
}
```

**Interview answer:** "We capped retries at 2 and route failures to a dead letter queue. Infinite retry is dangerous because a poison message -- say, a malformed protobuf that always fails to parse -- would create an infinite loop and block the consumer. With our QoS prefetch of 1, that would starve all other messages. The DLQ gives us visibility into failures, and we can inspect and replay messages after fixing the root cause."

---

## 9. Why multi-DB ClickHouse vs single DB?

**Decision:** Support multiple ClickHouse databases from the same service, stored as `map[string]*gorm.DB`.

**Why multi-DB:**
- **Domain separation:** Different business domains (analytics events, scraping logs, partner data) in separate databases with independent schema evolution
- **Access control:** Different databases can have different user permissions. The analytics DB is read-heavy for dashboards; the log DB is write-heavy for ingestion
- **Operational isolation:** One database's maintenance (OPTIMIZE TABLE, mutations) doesn't affect other databases' read performance
- **Migration flexibility:** Can move one domain's database to a different ClickHouse cluster without changing others

**Why not separate services per DB:**
- All databases share the same ClickHouse cluster -- separate services would add unnecessary network hops
- A single connection cron monitors all databases -- simpler ops than N separate health checks
- The config is environment-driven: `CLICKHOUSE_DB_NAMES=analytics,logs,partner` in the `.env` file

**Code evidence:**
```go
// Config: comma-separated DB names
CLICKHOUSE_DB_NAMES: strings.Split(os.Getenv("CLICKHOUSE_DB_NAMES"), ",")

// Multi-DB map
singletonClickhouseMap map[string]*gorm.DB

// Caller specifies which DB
func Clickhouse(config config.Config, dbName *string) *gorm.DB {
    if dbName != nil {
        if db, ok := singletonClickhouseMap[*dbName]; ok {
            return db
        }
    }
    return singletonClickhouseMap[config.CLICKHOUSE_CONNECTION_CONFIG.CLICKHOUSE_DB_NAME]
}
```

**Interview answer:** "We supported multiple ClickHouse databases from the same service because different business domains need separate schema evolution and access control. Analytics events, scraping logs, and partner data each have their own database. The `Clickhouse(config, &dbName)` function takes an optional database name -- callers specify which DB they need, and if they don't, they get the default. One connection cron monitors all databases, so operational complexity stays low."

---

## 10. Why GORM vs raw SQL for ClickHouse?

**Decision:** GORM ORM with the ClickHouse driver for all database operations.

**Why GORM:**
- **Batch insert convenience:** `db.Create([]model.Event{...})` generates a multi-row INSERT statement automatically. Raw SQL batch inserts require manual value interpolation
- **Model-driven:** Go structs with `gorm` tags define the schema. Adding a new field to the model automatically includes it in INSERTs without changing SQL strings
- **Driver abstraction:** Same API for ClickHouse and PostgreSQL. Switching the connection from PG to ClickHouse required zero changes to sinker code
- **Connection lifecycle:** GORM manages connection pooling, idle connections, and connection max lifetime

**Tradeoff accepted:**
- GORM adds some overhead vs raw SQL -- but for INSERT-heavy workloads (no complex JOINs or subqueries), the overhead is negligible
- ClickHouse-specific features (MergeTree settings, OPTIMIZE TABLE) are done via raw DDL, not through GORM

**Code evidence:**
```go
// Batch insert via GORM -- handles value interpolation for 100+ rows
result := clickhouse.Clickhouse(config.New(), nil).Create(events)

// Model defines schema
type TraceLogEvent struct {
    Id             string
    HostName       string
    ServiceName    string
    Timestamp      time.Time
    TimeTaken      int64
    Method         string
    URI            string
    Headers        JSONB `sql:"type:jsonb"`
    ResponseStatus int64
}
```

**Interview answer:** "We used GORM because our primary operation is batch inserts -- `db.Create([]Event{...})` generates multi-row INSERTs automatically, which would be tedious to build manually with raw SQL for 100-event batches. GORM also gives us model-driven schema management: adding a field to the Go struct automatically includes it in inserts. The same API works for both ClickHouse and PostgreSQL, which let us switch the analytics backend without changing sinker code."

---

## Quick Reference Card

| # | Decision | Chose | Over | Key Reason |
|---|----------|-------|------|------------|
| 1 | Protocol | gRPC + HTTP | Pure REST | Type safety + 3rd party webhooks |
| 2 | Message Broker | RabbitMQ | Kafka | Smart routing + per-message ACK |
| 3 | Write Pattern | Buffered sinkers | Direct writes (for high-vol) | ClickHouse batch optimization |
| 4 | Analytics DB | ClickHouse | PostgreSQL | 2.5x faster, columnar, append-only |
| 5 | Concurrency | Worker pools | Goroutine-per-request | Bounded resources, backpressure |
| 6 | Serialization | Protobuf | JSON | Type safety, 5-10x smaller |
| 7 | Initialization | sync.Once | Global init() | Config-dependent, testable |
| 8 | Error Handling | DLQ (max 2 retry) | Infinite retry | Poison message protection |
| 9 | DB Architecture | Multi-DB ClickHouse | Single DB | Domain separation, access control |
| 10 | ORM | GORM | Raw SQL | Batch insert convenience |
