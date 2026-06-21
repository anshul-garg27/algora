# Event-gRPC: Interview Q&A

Organized by topic area. Each answer is structured for a 2-3 minute verbal response with a hook, technical depth, and impact.

---

## Section A: gRPC and Protocol Buffers

### Q1: How does your gRPC service handle 60+ event types efficiently?

**A:** We use Protocol Buffers' `oneof` construct. The `Event` message has a single `oneof EventOf` field that can hold any of 60+ typed event messages -- `LaunchEvent`, `AddToCartEvent`, `CompletePurchaseEvent`, and so on. The client sends a batch of events in a single `dispatch` RPC call wrapped in an `Events` message with a shared `Header` for session and device context.

On the server side, we use Go reflection to extract the event type name (`reflect.TypeOf(e.GetEventOf())`) and strip the protobuf prefix. This gives us a clean string like `"LaunchEvent"` or `"AddToCartEvent"` that becomes the RabbitMQ routing key. So a single gRPC endpoint fans out to 26 specialized queues without any switch statement -- the routing is entirely data-driven.

The proto file also generates Java and JavaScript clients that we published to Maven and NPM. So Android, iOS, web, and backend services all share the same type-safe contract.

---

### Q2: Why did you choose gRPC over REST for event ingestion?

**A:** Three reasons. First, payload size -- protobuf binary encoding is 5-10x smaller than JSON, which matters for mobile clients on cellular networks sending thousands of events per session. Second, type safety -- with 60+ event types, REST would require ad-hoc JSON validation. Protobuf enforces the schema at compile time across Go, Java, and JavaScript. Third, HTTP/2 multiplexing -- clients can send multiple event batches over a single connection without head-of-line blocking.

That said, we kept an HTTP server alongside gRPC for third-party webhooks (Branch.io, Shopify, WebEngage send HTTP), Prometheus metrics scraping, and load balancer health checks. It's a pragmatic hybrid.

---

### Q3: How do you handle versioning and backward compatibility with the proto schema?

**A:** Protobuf is inherently backward-compatible. Each field has a unique number (`LaunchEvent = 9`, `HostActionEvent = 64`), and we never reuse or remove field numbers. When we add a new event type, we add a new `oneof` variant with a new field number. Old clients that don't know about the new type simply ignore it. Old servers receiving unknown fields skip them gracefully.

We also publish the generated client libraries through CI/CD -- the GitLab pipeline runs `protoc` to generate Go, Java (Maven), and JavaScript (NPM) packages. Teams adopt new event types by updating their dependency version, but old versions continue working.

---

### Q4: What is the role of the `Header` message in your proto?

**A:** The `Header` contains session-level context that's shared across all events in a batch: `sessionId`, `userId`, `deviceId`, `clientId`, `channel`, `os`, `appVersion`, and UTM parameters. Instead of repeating this context in every event, the client sends it once in the header, and our workers copy it to each event during transformation.

This reduces payload size significantly -- if a client sends 10 events, the header data appears once instead of 10 times. During transformation to the ClickHouse model, we merge the header fields into each event record for denormalized storage.

---

## Section B: RabbitMQ and Message Processing

### Q5: Explain your RabbitMQ architecture with 26 queues and 11 exchanges.

**A:** The architecture uses topic exchanges for content-based routing. When a worker processes an event batch, it groups events by type and publishes each group to the main exchange (`grpc_event.tx`) with the event type as the routing key. Downstream queues bind to specific routing keys -- for example, `clickhouse_click_event_q` binds to `CLICK`, `app_init_event_q` binds to `APP_INIT`, and `grpc_clickhouse_event_q` binds to `*` (wildcard for all types).

We have 11 exchanges covering different event domains: `grpc_event.tx` for main events, `branch_event.tx` for deep linking, `webengage_event.dx` for marketing, `beat.dx` for scraping logs, `affiliate.dx` for affiliate tracking, and error exchanges for dead letter routing.

Each queue has a configurable number of consumer workers -- from 2 for low-volume queues to 20 for post_log_events_q which is our highest-throughput queue. Total concurrent workers across all queues is 90+.

---

### Q6: How does your retry logic work? Why max 2 retries?

**A:** When a consumer fails to process a message, we check the `x-retry-count` header. If it doesn't exist, we set it to 1 and republish the message to the same exchange and routing key. On the second failure, the count reaches 2, which exceeds our threshold, so we route the message to an error exchange (dead letter queue) and ACK the original.

We cap at 2 because of poison messages. A malformed event that causes a parsing error will never succeed -- infinite retry would create an infinite loop. With QoS prefetch of 1, a stuck consumer blocks all subsequent messages in that queue. Two retries handle transient failures (brief network blip, momentary ClickHouse restart) while ensuring permanent failures get captured quickly in the DLQ for investigation.

---

### Q7: How do you handle RabbitMQ connection failures?

**A:** Auto-recovery via a connector loop. The `rabbitConnector` function runs in a goroutine and follows this pattern: connect to RabbitMQ, send a signal on the `connected` channel, register a close notification handler via `NotifyClose`, then block on `<-rabbitCloseError`. When the connection drops, the channel receives the error, and the loop reconnects.

The initial connection also has a 5-second timeout -- if RabbitMQ is unreachable at startup, we don't block forever. And the `connectToRabbit` function itself retries in a loop with 1-second backoff until it succeeds.

For the consumer side, if the connection drops mid-consumption, the message channel closes, the `for msg := range msgs` loop exits, the consumer goroutine completes, and `safego.GoNoCtx` recovers any panic. The consumer needs to be restarted when the connection recovers.

---

### Q8: What is QoS prefetch and why do you set it to 1?

**A:** `channel.Qos(1, 0, false)` tells RabbitMQ to deliver only 1 unacknowledged message to each consumer at a time. This is crucial for two reasons:

First, backpressure -- if a consumer is slow, RabbitMQ won't pile up messages in the consumer's buffer. This prevents out-of-memory issues on the consumer side.

Second, fair dispatch -- with multiple consumers on the same queue, RabbitMQ sends the next message to whichever consumer finishes first. Without prefetch, RabbitMQ would round-robin blindly, potentially overloading a slow consumer while a fast one sits idle.

The tradeoff is lower throughput per consumer -- each consumer processes one message at a time instead of pipelining. We compensate with more consumers (2-20 per queue, 90+ total) for parallelism.

---

## Section C: ClickHouse and Data Storage

### Q9: Why did you transition from PostgreSQL to ClickHouse?

**A:** The analytics team was running aggregation queries on PostgreSQL -- things like "count events by type per day for the last 30 days" or "average session duration by app version." These queries were scanning full rows in a row-oriented database, which was slow because each event has 20+ columns but the query only needs 2-3.

ClickHouse is columnar -- it stores each column separately on disk, so an aggregation over `event_name` and `event_timestamp` only reads those two columns. The result was 2.5x faster query performance. Plus ClickHouse compresses columnar data aggressively (10-100x for strings with repetitive values like event names), so storage costs dropped too.

We kept PostgreSQL for transactional operations -- referral processing needs ACID, and user account creation requires uniqueness constraints. ClickHouse doesn't support transactions or unique constraints.

---

### Q10: How does your multi-DB ClickHouse connection work?

**A:** The configuration stores multiple database names in a comma-separated environment variable that gets split into a string slice. At connection time, we iterate over all database names and create a GORM connection for each, stored in a `map[string]*gorm.DB`. Callers pass an optional `dbName` parameter -- if provided, they get the specific database connection; if nil, they get the default.

A health-check goroutine runs every second, iterating over the map and reconnecting any broken connections. It uses a mutex to prevent concurrent reconnection attempts from racing.

---

### Q11: What are your 18+ ClickHouse tables and how are they organized?

**A:** The tables map to event domains:

- **Core analytics:** `event` (main events), `error_event` (processing failures), `click_event` (click tracking with 600+ lines of fields)
- **App lifecycle:** `app_init_event`, `launch_refer_event`
- **Third-party:** `branch_event` (49 fields for attribution), `webengage_event`, `graphy_event`, `shopify_event`
- **Scraping logs:** `trace_log`, `post_log_event`, `profile_log`, `sentiment_log`, `scrape_request_log`, `profile_relationship_log`
- **Commerce:** `order_log`, `affiliate_order`, `bigboss_votes`
- **AB testing:** `ab_assignment`

Each table is backed by a Go model struct, and GORM generates the INSERT statements. The event-specific params are stored as JSONB strings (flexible schema within the fixed schema).

---

### Q12: How do batch inserts work in ClickHouse with GORM?

**A:** GORM's `db.Create([]model.Event{...})` generates a multi-row INSERT statement. For a batch of 100 events, it produces one `INSERT INTO event VALUES (row1), (row2), ..., (row100)` instead of 100 separate INSERTs.

This is critical for ClickHouse because the MergeTree engine creates one data part per INSERT. Too many small INSERTs causes "too many parts" errors and degrades merge performance. Batching ensures we create fewer, larger data parts.

Our buffered sinker pattern accumulates events in a Go channel and flushes at 100 events or 5 minutes (whichever comes first). The dual-trigger `select` on channel receive and ticker ensures both throughput efficiency and data freshness.

---

## Section D: Go Concurrency and Architecture

### Q13: Explain the worker pool pattern in your system.

**A:** We have 6 independent worker pools, one for each event source (main events, Branch, WebEngage, Vidooly, Graphy, Shopify). Each pool follows the same pattern:

1. A buffered channel (capacity 1000) acts as the work queue
2. N worker goroutines (configurable per pool) read from the channel
3. Each worker loops forever: receive an event batch, group by type, correct timestamps, publish to RabbitMQ
4. The channel and workers are initialized once via `sync.Once` for thread safety

The gRPC handler pushes events into the channel with a 1-second timeout. If the channel is full (all workers busy and buffer exhausted), the timeout fires and the client gets an error -- this is natural backpressure that prevents the service from accepting more work than it can process.

---

### Q14: How do you prevent a bad event from crashing the entire service?

**A:** Every goroutine is wrapped in `safego.GoNoCtx()`, which does `defer recover()` at the top of the goroutine. If any worker panics (say, nil pointer dereference on a malformed event), the recovery catches the panic, logs the stack trace, and the goroutine exits gracefully.

Without this, Go's default behavior would kill the entire process -- all 90+ workers and both servers. With 10K events/sec, a single malformed event could take down the whole system.

We have two variants: `safego.Go(gCtx, f)` for business logic goroutines (logs to structured logger with context), and `safego.GoNoCtx(f)` for infrastructure goroutines (logs to standard logger).

---

### Q15: How does the event dispatch handle backpressure?

**A:** Three levels of backpressure:

1. **Channel buffer (1000 events):** Absorbs burst traffic. If the workers are momentarily busy, events queue up in the buffer
2. **1-second timeout:** If the buffer is full, the `select` statement times out after 1 second and returns an error to the gRPC client. The client knows to retry or alert
3. **RabbitMQ QoS (prefetch=1):** Each consumer processes one message at a time. If ClickHouse is slow, consumers back up, queues grow, and RabbitMQ eventually triggers flow control on publishers

This creates an end-to-end backpressure chain: ClickHouse slowdown -> consumer backup -> queue growth -> publisher flow control -> worker pool channel full -> dispatch timeout -> gRPC error to client.

---

### Q16: How does timestamp correction work and why is it needed?

**A:** Mobile clients send event timestamps based on the device clock, which can be wrong -- set to the future due to timezone bugs, NTP sync issues, or deliberate manipulation. A future timestamp in the analytics database would corrupt time-series queries.

Our workers check each event's timestamp against the server's current time. If `event_timestamp > now`, we replace it with the server time:

```go
et := time.Unix(transformer.InterfaceToInt64(e.Events[i].Timestamp)/1000, 0)
if et.Unix() > timeNow.Unix() {
    e.Events[i].Timestamp = strconv.FormatInt(timeNow.Unix()*1000, 10)
}
```

We only correct future timestamps, not past ones. A past timestamp might indicate offline events that were batched and sent later -- that's a valid use case. Future timestamps are never valid.

---

## Section E: System Design and Operations

### Q17: How does your graceful deployment work?

**A:** The deployment script follows a drain-then-replace pattern:

1. **Drain:** Send `PUT /heartbeat/?beat=false` to mark the instance as unhealthy. The gRPC health check starts returning `NOT_SERVING`, and the load balancer stops sending new requests
2. **Wait 15 seconds:** Let in-flight requests complete
3. **Kill:** Stop the old process
4. **Start:** Launch the new binary
5. **Wait 20 seconds:** Let the new process initialize (connect to RabbitMQ, ClickHouse, PostgreSQL)
6. **Restore:** Send `PUT /heartbeat/?beat=true` to mark it healthy again

The load balancer continuously checks the gRPC health endpoint and only routes traffic to healthy instances. This achieves zero-downtime deployment.

---

### Q18: How would you scale this system to handle 10x the traffic?

**A:** Multiple approaches:

1. **Horizontal scaling:** The service is stateless (no in-process state beyond connection singletons). Deploy more instances behind the load balancer
2. **Worker pool tuning:** Increase `EVENT_WORKER_POOL_SIZE` and `EVENT_BUFFERED_CHANNEL_SIZE` via environment variables. No code change needed
3. **RabbitMQ scaling:** Add more consumer workers per queue (e.g., post_log from 20 to 50). For extreme scale, switch hot queues to Kafka for partitioned consumption
4. **ClickHouse sharding:** ClickHouse supports distributed tables across shards. Move high-volume tables to sharded clusters
5. **Batch size tuning:** Increase the buffer limit from 100 to 1000 for higher throughput per flush

---

### Q19: What monitoring and observability do you have?

**A:** Three pillars:

1. **Metrics (Prometheus):** Exposed via `/metrics` endpoint. Gin collects HTTP metrics automatically. Custom metrics can be added for queue depth, batch sizes, and error rates
2. **Error tracking (Sentry):** Every unhandled exception is captured with full stack trace, grouped by error type, and tagged with the environment (production, staging). Sentry middleware on Gin catches HTTP handler panics
3. **Structured logging:** Request logger middleware captures method, path, status, duration, and request body for every HTTP request. The `safego` wrapper logs panics with full goroutine stack traces

For RabbitMQ specifically, the management UI provides queue depth, message rates, and consumer utilization.

---

### Q20: How do you handle the proto-to-model transformation for 60+ event types?

**A:** The `TransformToEventModel` function in `eventsinker.go` uses a sequential nil-check pattern. For each possible event type, it checks if that getter returns non-nil (e.g., `e.GetLaunchEvent() != nil`). If so, it marshals the event-specific data to JSON and stores it in the `EventParams` field as a flexible JSONB column.

This is admittedly verbose (the file is 1477 lines), but it's straightforward and avoids reflection-heavy magic. Each event type is explicitly handled, making it easy to add custom transformation logic per event type. In a future refactor, we could use a registry pattern or code generation to reduce boilerplate, but the explicit approach ensures no events are silently dropped.
