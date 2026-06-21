# Event-gRPC: Scenario Questions -- "What If X Fails?"

Ten production failure scenarios with root cause analysis, immediate response, and architectural solutions. Each answer demonstrates deep understanding of the system's failure modes.

---

## Scenario 1: RabbitMQ crashes in production

**Setup:** The RabbitMQ server goes down at 2 AM. All 26 consumer queues stop delivering messages. Events continue arriving via gRPC.

**What happens (automatically):**
1. The `rabbitConnector` goroutine detects the connection drop via `NotifyClose` channel
2. `connectToRabbit` enters its retry loop, attempting reconnection every 1 second
3. Worker pools continue receiving events from gRPC and buffering them in the 1000-capacity channels
4. Workers call `rabbit.Rabbit(config).Publish(...)` which fails because `rabbit.connection.IsClosed()` returns true -- events are lost from the publish side
5. Consumers' `for msg := range msgs` loops exit because the channel closes
6. The buffered channel fills up (1000 events), and subsequent dispatches hit the 1-second timeout, returning errors to gRPC clients

**Impact:** Event loss during the outage window. Buffered events in the channel (up to 1000) are lost if the process restarts. Consumers stop processing -- queue depth grows on RabbitMQ's disk (if it recovers) but events from the worker pool are dropped.

**Mitigation strategies:**
- Auto-reconnect is already built in -- when RabbitMQ comes back, the connector goroutine reconnects and consumers resume
- For zero event loss: add a persistent write-ahead log (WAL) before publishing to RabbitMQ. If publish fails, write to local disk and replay on recovery
- Deploy RabbitMQ in a clustered/mirrored configuration so a single node failure doesn't drop the broker
- Add monitoring alerts on the `rabbitCloseError` channel to page on-call immediately

**Interview framing:** "The auto-reconnect handles transient failures well, but for complete broker outages, we'd need either a RabbitMQ cluster with mirrored queues or a local WAL for publish-side durability."

---

## Scenario 2: ClickHouse becomes unreachable

**Setup:** The ClickHouse cluster is down for maintenance. All sinkers that write to ClickHouse start failing.

**What happens (automatically):**
1. Direct sinkers (`SinkEventToClickhouse`) return `false` because `clickhouse.Clickhouse(config, nil).Create(events)` returns an error
2. The RabbitMQ consumer sees `listenerResponse = false` and enters the retry path
3. First failure: message is republished with `x-retry-count=1`
4. Second failure: message is republished with `x-retry-count=2`
5. Third attempt: retry count >= 2, message routes to dead letter queue
6. Buffered sinkers (`TraceLogEventsSinker`) accumulate events in their Go channels (10K capacity) but `FlushTraceLogEvents` fails -- events are lost from the buffer
7. The `clickhouseConnectionCron` detects broken connections every 1 second and attempts reconnection

**Impact for direct sinkers:** Events retry twice, then land in the DLQ. After ClickHouse recovers, DLQ messages can be replayed. Maximum 2 attempts lost per event.

**Impact for buffered sinkers:** More concerning -- the batch flush fails, the buffer resets to empty, and those events are lost. The buffer refills from the channel, but previous batch is gone.

**Mitigation strategies:**
- For buffered sinkers: don't reset the buffer on flush failure. Keep the events and retry on the next tick. Risk: buffer grows unbounded if ClickHouse stays down for a long time
- Set up alerts on ClickHouse connection cron errors -- if it logs errors for more than 30 seconds, page the team
- DLQ replay tooling: a script that reads from error queues and republishes to the original exchange
- Read replicas: if only the primary is down, route reads to replicas (analytics queries continue working)

**Interview framing:** "The retry + DLQ pattern protects direct sinkers well, but the buffered sinkers have a gap -- a failed flush discards the batch. I'd fix this by only clearing the buffer after a successful flush."

---

## Scenario 3: A poison message enters the system

**Setup:** A mobile client sends a malformed event where the `Timestamp` field contains a non-numeric string like `"abc"`. The `transformer.InterfaceToInt64` function panics.

**What happens (automatically):**
1. The worker goroutine panics during timestamp conversion
2. `safego.GoNoCtx` catches the panic via `defer recover()`, logs the stack trace
3. The goroutine exits -- one worker is lost from the pool
4. The remaining workers continue processing from the shared channel
5. If the poison message was already in RabbitMQ, the consumer panics similarly, is caught by `safego`, and the message sits unacknowledged
6. RabbitMQ redelivers the unacked message to another consumer, which also panics
7. After redelivery + 2 retries, the message hits the DLQ

**Impact:** One worker goroutine dies per poison message encounter (not restarted). Over time, if many poison messages arrive, the worker pool shrinks. The service still functions but with reduced capacity.

**Mitigation strategies:**
- Add input validation before timestamp conversion -- check that `Timestamp` is numeric
- Make worker goroutines restart after panic recovery (currently they exit)
- Add circuit breaker: if more than N panics in M seconds, alert and stop processing
- Schema validation at the gRPC ingestion layer -- reject invalid events before they enter the pipeline

**Interview framing:** "The panic recovery prevents a crash, but we lose a worker. The fix is two-fold: input validation at the gRPC layer to reject bad data early, and worker restart logic so recovered goroutines respawn instead of exiting."

---

## Scenario 4: The worker pool channel is full (backpressure)

**Setup:** A marketing campaign causes a 5x traffic spike. The event worker pool's buffered channel (capacity 1000) fills up because workers can't publish to RabbitMQ fast enough.

**What happens (automatically):**
1. `DispatchEvent` tries to push events into the channel
2. The `select` statement hits the `time.After(1 * time.Second)` case
3. The function returns `errors.New("Error publishing event")`
4. The gRPC `Dispatch` handler returns `Response{Status: "ERROR"}`
5. The client receives the error and knows the event was not accepted

**Impact:** Events are dropped at the ingestion layer. The client gets an explicit error (not a timeout or crash). If the client has retry logic, it can buffer locally and retry.

**Mitigation strategies:**
- **Scale horizontally:** Add more instances behind the load balancer to absorb the spike
- **Increase channel buffer:** Change `EVENT_BUFFERED_CHANNEL_SIZE` from 1000 to 5000 via env variable
- **Increase worker pool size:** Change `EVENT_WORKER_POOL_SIZE` to add more RabbitMQ publishers
- **Client-side batching:** Mobile clients should batch events and send fewer, larger requests
- **Auto-scaling:** Use container orchestration (Kubernetes HPA) to scale based on gRPC error rate

**Interview framing:** "The 1-second timeout is intentional backpressure -- we'd rather tell the client 'slow down' than accept unbounded work and crash. The fix for a sustained spike is horizontal scaling, not removing the backpressure."

---

## Scenario 5: A consumer worker is stuck on a slow ClickHouse write

**Setup:** One consumer worker encounters a ClickHouse node with high CPU. The `db.Create(events)` call takes 30 seconds instead of the usual 200ms. QoS prefetch is 1.

**What happens:**
1. The worker is blocked on the slow write for 30 seconds
2. With QoS=1, RabbitMQ won't send another message to this worker until it ACKs
3. Other consumers on the same queue continue processing normally
4. Queue depth may grow slightly but is distributed across other consumers
5. When the write completes, the worker ACKs and resumes normal processing

**Impact:** One consumer is temporarily slow, but overall queue processing continues. No message loss. No crash.

**Why this is okay:**
- QoS=1 prevents the slow consumer from accumulating a backlog
- Multiple consumers per queue (2-20) ensure one slow worker doesn't halt the queue
- ClickHouse's `write_timeout=20` setting in the DSN would eventually timeout a truly stuck write

**Mitigation strategies:**
- Add a context with timeout to ClickHouse writes: `db.WithContext(ctx).Create(events)` with 10-second deadline
- Monitor ClickHouse query latency via Prometheus
- Circuit breaker: if 3 consecutive writes exceed 5 seconds, stop consuming and wait for recovery

**Interview framing:** "QoS prefetch of 1 is the key protection here. It means a slow consumer only hurts itself, not other consumers. The other workers keep processing while this one is blocked."

---

## Scenario 6: Memory leak in a buffered sinker

**Setup:** The `PostLogEventsSinker` has 20 consumers pushing into a 10K-capacity channel. A bug in the parser causes `nil` events to be pushed to the channel. The sinker accumulates nil events in the buffer that never trigger a successful ClickHouse write.

**What happens:**
1. Buffer grows with nil/empty events
2. When buffer reaches 100, `FlushPostLogEvents` is called
3. GORM's `db.Create(events)` either fails (nil pointers) or creates empty rows
4. Buffer resets to empty, but the cycle repeats
5. Memory usage stays bounded (buffer resets every 100 events or 5 minutes)
6. ClickHouse fills with garbage empty rows, corrupting analytics data

**Impact:** Data quality issue rather than memory leak. The buffer pattern prevents unbounded memory growth, but bad data flows downstream.

**Mitigation strategies:**
- Add nil checks in the buffer function: `if event == nil { return false }` (already done in some sinkers)
- Add row-level validation before batch insert: skip nil/empty events
- ClickHouse materialized views can filter out empty rows
- Monitor ClickHouse row counts vs expected event rates -- a sudden spike of empty rows triggers an alert

**Interview framing:** "The buffer pattern bounds memory, so it's not a leak in the traditional sense. But it can propagate bad data. The fix is validation at the buffer entry point and monitoring for anomalous row patterns in ClickHouse."

---

## Scenario 7: Graceful deployment fails mid-process

**Setup:** During deployment, the `kill -9` command runs before the load balancer has fully drained the instance. In-flight gRPC requests are terminated.

**What happens:**
1. `/heartbeat/?beat=false` marks instance as unhealthy
2. Load balancer stops sending NEW requests (takes ~5 seconds to propagate)
3. Script sleeps 15 seconds for drain
4. `kill -9` terminates the process immediately
5. Any events in the worker pool's buffered channel (up to 1000) are lost
6. Any RabbitMQ messages being processed (unACKed) are redelivered by RabbitMQ to other consumers
7. Buffered sinker goroutines die with unflushed batches in memory

**Impact:** Potential loss of up to 1000 events in the channel + unflushed batches (up to 100 per sinker). RabbitMQ messages are redelivered.

**Mitigation strategies:**
- Use `SIGTERM` instead of `kill -9` and implement a graceful shutdown handler in Go that flushes buffers and drains the channel
- Increase the drain wait time from 15 seconds to 30 seconds
- Add a pre-shutdown hook that flushes all buffered sinkers before kill
- Container orchestration (Kubernetes) handles graceful shutdown with `preStop` hooks

**Interview framing:** "The biggest gap is the `kill -9` -- it doesn't give the process a chance to flush. I'd implement a `SIGTERM` handler that flushes buffered sinkers, drains the worker channel, and waits for in-flight consumers to ACK before exiting."

---

## Scenario 8: Clock skew between gRPC server and clients

**Setup:** A batch of mobile clients has clocks set 24 hours in the future due to a timezone bug in the app. They send thousands of events with future timestamps.

**What happens (automatically):**
1. The worker receives the events
2. For each event, the timestamp correction logic runs:
   ```go
   if et.Unix() > timeNow.Unix() {
       e.Events[i].Timestamp = strconv.FormatInt(timeNow.Unix()*1000, 10)
   }
   ```
3. Future timestamps are clamped to server time
4. Events are published to RabbitMQ with corrected timestamps
5. ClickHouse receives events with accurate insert times

**Impact:** Minimal. The timestamp correction catches this exact scenario. However, the original client timestamp is lost -- we overwrite rather than storing both.

**Mitigation strategies:**
- Store both `original_timestamp` and `corrected_timestamp` in the ClickHouse model for forensic analysis
- Add a flag `timestamp_corrected: true` so analysts know which events were adjusted
- Send client clock offset in the gRPC header for server-side correction
- Alert if more than 10% of events in a window are timestamp-corrected (indicates a client bug)

**Interview framing:** "We built timestamp correction specifically for this scenario. The tradeoff is we lose the original client timestamp. In retrospect, I'd store both and add a correction flag for data quality transparency."

---

## Scenario 9: RabbitMQ dead letter queue fills up

**Setup:** A ClickHouse schema migration breaks the event model. All events fail to insert. After 2 retries each, they all land in the DLQ. The DLQ grows to millions of messages.

**What happens:**
1. Every direct sinker returns `false` because GORM fails with a schema mismatch
2. Each message retries twice, then routes to the error exchange
3. DLQ queues grow rapidly: 10K events/sec * 3 attempts * all 10 direct consumer queues
4. RabbitMQ disk usage spikes
5. Eventually RabbitMQ hits disk watermark and triggers flow control, blocking all publishers
6. Worker pool channels fill up, dispatch timeouts fire, gRPC clients get errors
7. The entire pipeline is effectively down

**Impact:** Full pipeline failure if DLQ is not monitored and acted upon quickly.

**Mitigation strategies:**
- **Alert on DLQ depth:** If any error queue exceeds 1000 messages in 5 minutes, page the team
- **DLQ TTL:** Set a time-to-live on DLQ messages (e.g., 24 hours) so they expire if not replayed
- **Circuit breaker:** If a sinker fails N consecutive times, stop consuming from that queue and alert (prevents further DLQ flooding)
- **Schema migration process:** Test migrations in staging with production-like data before production deployment
- **DLQ replay tooling:** A script that reads from error queues, optionally transforms messages, and republishes to the original exchange

**Interview framing:** "The DLQ is a safety net, not a solution. Without monitoring and circuit breakers, a systemic failure (like a bad schema migration) turns the DLQ into a secondary problem. The fix is monitoring DLQ depth and having a circuit breaker that stops consumption when a queue's error rate exceeds a threshold."

---

## Scenario 10: Multiple ClickHouse databases have different availability

**Setup:** The multi-DB ClickHouse setup has databases `analytics` and `logs`. The `logs` database's node goes down, but `analytics` is healthy. Sinkers writing to `logs` fail while sinkers writing to `analytics` succeed.

**What happens (automatically):**
1. The `clickhouseConnectionCron` runs every 1 second
2. For the `logs` database, `singletonClickhouseMap["logs"].DB()` returns an error
3. `connectionBroken = true` -- the cron attempts to reconnect
4. Reconnection fails (node is down), logs an error, and continues to the next database
5. The `analytics` database connection is healthy -- no action needed
6. Sinkers writing to `logs` fail, trigger retries, eventually hit DLQ
7. Sinkers writing to `analytics` continue normally

**Impact:** Partial failure -- log ingestion stops, analytics ingestion continues. Events hitting the `logs` database route to DLQ after retries.

**Why multi-DB helps here:** If we had a single database, a node failure would take down all event ingestion. With multi-DB, only the affected domain stops.

**Mitigation strategies:**
- ClickHouse replicas: the `logs` database should have a replica that the connection cron can failover to
- Write to a fallback database if the primary is down (requires sinker logic to be db-aware)
- Alert on per-database connection cron errors
- The mutex in `connectToClickhouse` prevents race conditions during reconnection

**Interview framing:** "Multi-DB isolation gives us partial failure instead of total failure. If the logs database goes down, analytics keep working. The 1-second health cron detects the failure immediately, and the sinker-level retry + DLQ captures any events that couldn't be written."

---

## Quick Reference: Failure Modes Summary

| Scenario | Auto-Recovery? | Data Loss Risk | Key Protection |
|----------|---------------|----------------|----------------|
| RabbitMQ crash | Yes (reconnect loop) | Channel buffer events | Auto-reconnect, DLQ |
| ClickHouse down | Partial (cron reconnect) | Buffered sinker batches | Retry + DLQ |
| Poison message | Yes (panic recovery) | None (message hits DLQ) | safego wrapper |
| Backpressure spike | Yes (timeout) | Rejected events | 1-sec timeout, client error |
| Slow consumer | Yes (QoS isolation) | None | QoS prefetch=1 |
| Memory leak | Bounded (buffer reset) | Data quality issue | Buffer size limits |
| Bad deployment | Partial | Channel + unflushed buffers | Drain + sleep |
| Clock skew | Yes (timestamp correction) | Original timestamp | Future timestamp clamp |
| DLQ overflow | No (needs human) | Flow control cascade | Alert on DLQ depth |
| Partial DB failure | Yes (per-DB cron) | Affected domain only | Multi-DB isolation |
