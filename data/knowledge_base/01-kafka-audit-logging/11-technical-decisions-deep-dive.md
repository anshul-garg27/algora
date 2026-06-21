# Technical Decisions Deep Dive - "Why THIS and Not THAT?"

> **Every major decision in the Kafka Audit Logging system with alternatives, trade-offs, and follow-up answers.**
> This is what separates "good" from "excellent" in a hiring manager interview.

---

## Decision 1: Servlet Filter vs AOP vs Sidecar

### What's In The Code
```java
@Order(Ordered.LOWEST_PRECEDENCE)
@Component
public class LoggingFilter extends OncePerRequestFilter { ... }
```

### The Options

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **Servlet Filter** | Access raw HTTP body stream, runs in filter chain, captures auth failures | In-process overhead | **YES** |
| **AOP (@Around)** | Clean, annotation-based | Can't access raw HTTP body, only method params | No |
| **Sidecar (Envoy)** | Zero application changes | No application context (endpoint name, supplier ID, error details) | No |

### Interview Answer
> "AOP can only access method parameters and return values - not the raw HTTP body stream. For debugging, suppliers need the actual request body. A sidecar like Envoy works at the network layer - it can't see which endpoint was called semantically or which supplier made the request. Servlet filter gives us both: raw HTTP access AND application context."

### Follow-up: "What about performance impact?"
> "The filter adds ~1ms for ContentCachingWrapper. The actual audit is @Async so it doesn't block the response. P99 impact is under 5ms."

### Follow-up: "Why LOWEST_PRECEDENCE?"
> "So it runs LAST in the filter chain - after security filters. This means we capture the final state of the request, including auth failures. If we ran first, we'd miss what the security filter did."

---

## Decision 2: @Async Fire-and-Forget vs Synchronous vs Message Queue

### What's In The Code
```java
@Async
public void sendAuditLogRequest(AuditLogPayload payload, AuditLoggingConfig config) {
    try {
        httpService.sendHttpRequest(...);
    } catch (Exception e) {
        log.error("Audit failed for {}", payload.getRequestId(), e);
        // Don't throw - audit failure shouldn't break API
    }
}
```

### The Options

| Approach | Latency Impact | Data Safety | Complexity | Our Choice |
|----------|---------------|-------------|------------|------------|
| **@Async fire-and-forget** | Zero (non-blocking) | Can lose data if queue full | Simple | **YES** |
| **Synchronous** | +50ms per request | No loss | Simplest | No - blocks API |
| **In-process Kafka producer** | Low (~5ms) | Durable | Medium | Considered for v2 |
| **Reactive (WebFlux)** | Zero | Same as async | Complex | Overkill |

### Interview Answer
> "Synchronous would add 50ms to every API response - unacceptable for supplier-facing APIs with 200ms SLA. A direct Kafka producer from the library would be more durable but adds Kafka dependencies to every service. @Async with a bounded thread pool is the simplest approach that gives us zero latency impact. The trade-off is we can lose audit data if the queue fills - we mitigate with Prometheus metrics and 80% queue warning."

### Follow-up: "What if you lose audit data?"
> "It's a conscious trade-off. Audit data is valuable but not worth blocking API responses. We monitor rejected task count. In practice, we've lost less than 0.01% of events."

### Follow-up: "Why not publish directly to Kafka from the library?"
> "That would couple every consuming service to Kafka. They'd need Kafka dependencies, Schema Registry config, SSL certificates. The HTTP-based approach keeps the library lightweight - just add a Maven dependency. If I rebuilt this, I'd consider direct Kafka for the latency benefit, but the trade-off in coupling was the right call for adoption."

**Follow-up: "What about the publisher service's thread pool?"**
> "Different design. The library uses `ThreadPoolTaskExecutor(6/10/100)` — bounded, production-safe. The publisher service uses `Executors.newCachedThreadPool()` — unbounded, dynamic. I chose CachedThreadPool for the publisher because it's a dedicated service with controlled input, not a shared library running in someone else's JVM. If I rebuilt it, I'd use a bounded pool with backpressure."

---

## Decision 3: ThreadPool 6 Core / 10 Max / 100 Queue

### What's In The Code
```java
executor.setCorePoolSize(6);
executor.setMaxPoolSize(10);
executor.setQueueCapacity(100);
```

### Why These Numbers?

| Setting | Value | Reasoning |
|---------|-------|-----------|
| **Core: 6** | ~100 req/sec × 50ms/audit = 5 threads needed. +1 headroom | Based on traffic analysis |
| **Max: 10** | Handles spikes without thread explosion | 2x normal is enough |
| **Queue: 100** | Buffer bursts. Each payload ~2KB = 200KB total | Won't cause OOM |

### Interview Answer
> "Based on traffic analysis. Our APIs handle about 100 requests per second per pod. Each audit HTTP call takes about 50ms. So we need 5 threads to keep up. I set 6 core for headroom. Max 10 handles traffic spikes. Queue of 100 handles burst traffic - at 2KB per payload, that's only 200KB of memory."

### Follow-up: "A senior engineer challenged the queue size..."
> "He was right. When the queue fills, tasks are silently rejected. I added three safeguards: Prometheus metric for rejected tasks, WARN log at 80% capacity, and documentation explaining the trade-off. That 80% warning has triggered once - caught a downstream slowdown."

---

## Decision 4: Avro vs JSON vs Protobuf

### What's In The Code
```java
LogEvent event = AvroUtils.getLogEvent(request);
// Serialized to binary with Schema Registry
```

### The Options

| Format | Size | Schema | Evolution | Kafka Ecosystem | Our Choice |
|--------|------|--------|-----------|-----------------|------------|
| **Avro** | 30% of JSON (~70% smaller) | Enforced via Schema Registry | Backward/forward compatible | Native (Confluent) | **YES** |
| **JSON** | 100% (baseline) | None | Breaking changes possible | Works but no schema | No |
| **Protobuf** | ~30% of JSON | .proto files | Compatible | Supported but less native | Considered |

### Interview Answer
> "Three reasons: schema enforcement prevents bad data from entering the pipeline, binary format is 70% smaller which matters at 2 million events per day - that's significant Kafka storage savings, and schema evolution lets us add fields without breaking consumers. We chose Avro over Protobuf because it integrates natively with the Confluent Kafka ecosystem and Schema Registry."

### Follow-up: "What if Schema Registry is down?"
> "Producers cache schemas locally after first fetch. Existing schemas continue working. New schema registrations fail until Registry recovers - we monitor Registry health separately."

---

## Decision 5: Kafka Connect vs Custom Consumer vs Flink

### The Options

| Approach | Dev Time | Offset Mgmt | Scaling | Error Handling | Our Choice |
|----------|----------|-------------|---------|----------------|------------|
| **Kafka Connect** | 2-3 days | Built-in | Automatic | DLQ + retries built-in | **YES** |
| **Custom Consumer** | 2-3 weeks | Manual | Manual | Manual | No |
| **Apache Flink** | 1-2 weeks | Built-in | Auto | Complex | Overkill |
| **Cloud Functions** | 1 week | Event-driven | Auto | Cold starts | No |

### Interview Answer
> "Kafka Connect gives us offset management, scaling, fault tolerance, and retry logic out of the box. A custom consumer would take 2-3 weeks to build the same features. Flink is powerful but overkill for a simple sink operation. Connect is battle-tested and let us focus on our SMT filter logic instead of infrastructure."

### Follow-up: "But you had so many production issues with Connect..."
> "True - the debugging incident exposed that Connect's defaults aren't production-ready. But those were configuration issues, not architectural ones. A custom consumer would have had different but equally challenging production issues - offset management bugs, rebalancing problems, OOM. The infrastructure Connect provides is worth the configuration effort."

---

## Decision 6: SMT Filter (Sink-Side) vs Producer-Side Routing

### What's In The Code
```java
public abstract class BaseAuditLogSinkFilter<R extends ConnectRecord<R>>
    implements Transformation<R> {
    public R apply(R record) {
        if (verifyHeader(record)) return record;   // Pass
        return null;                                 // Drop
    }
}
```

### The Options

| Approach | Where Filtering Happens | Adding New Country | Coupling | Our Choice |
|----------|------------------------|-------------------|----------|------------|
| **SMT Filter (sink-side)** | At consumption | Deploy new connector only | Loose | **YES** |
| **Producer-side routing** | At publishing | Change producer code | Tight | No |
| **Multiple topics** | By topic name | New topic + consumer | Medium | Considered |

### Interview Answer
> "Separation of concerns. The producer's job is to publish reliably, not to know about downstream routing. If we add a new country, we just deploy a new connector with a new filter - no changes to the publisher. Also, the US filter is permissive (accepts records with OR without headers) which handles legacy data gracefully. That logic belongs at the sink, not the producer."

---

## Decision 7: Parquet vs JSON vs ORC for Storage

### The Options

| Format | Compression | Query Speed | BigQuery | Cost at 2M/day | Our Choice |
|--------|------------|-------------|----------|-----------------|------------|
| **Parquet** | 90% | Fast (columnar) | Native external tables | ~$500/month | **YES** |
| **JSON files** | ~30% | Slow (scan all) | Needs transformation | ~$5,000/month | No |
| **ORC** | 85% | Fast (columnar) | Not native | N/A | No |
| **BigQuery direct** | N/A | Fastest | Native | ~$3,000/month (streaming) | No (cost) |

### Interview Answer
> "Parquet gives us 90% compression, columnar format so BigQuery reads only needed columns, and native BigQuery support via external tables. JSON files would be 10x larger and 10x more expensive. Direct BigQuery streaming inserts are fast but expensive at 2M events/day. Parquet in GCS is the sweet spot: cheap storage, powerful queries."

### Follow-up: "Why not Apache Iceberg?"
> "Iceberg would give us ACID transactions and easier GDPR deletes. It's on our roadmap. At the time, raw Parquet was simpler and met our requirements. If I rebuilt this today, I'd use Iceberg from day one."

**Follow-up: "How do suppliers actually query the data?"**
> "Two query layers. Internal teams use Hive via Data Discovery — Walmart's internal SQL tool. The Hive table `us_dv_audit_log_prod.api_logs` has external tables pointing to GCS Parquet files, refreshed daily via Airflow. For complex JSON queries, we use `json_extract_scalar()` to traverse request/response bodies. External suppliers use BigQuery external tables with row-level security."

**Follow-up: "How is the Hive table refreshed?"**
> "An Airflow workflow called `Prod_Metrics_Hive_Tbl_Refresh_WF` runs daily and executes `MSCK REPAIR TABLE` to pick up new date partitions. There's also an Automic job as a backup. The table is partitioned by `service_name`, `date`, and `endpoint_name` — matching our GCS folder structure."

---

## Decision 8: Active/Active vs Active/Passive for Multi-Region

### The Options

| Approach | Failover Time | Cost | Complexity | Our Choice |
|----------|--------------|------|------------|------------|
| **Active/Active** | ~15 min (achieved) | 2x infrastructure | Complex (dedup needed) | **YES** |
| **Active/Passive** | ~30 min | 1.5x (standby wasted) | Simple | No |
| **Single region** | N/A (no failover) | 1x | None | Not an option (compliance) |

### Interview Answer
> "Audit is write-heavy and compliance couldn't tolerate 30-minute failover delays. Active/Active gives immediate failover. The cost is 2x infrastructure, but compliance failure costs far more. We achieve 15-minute recovery, well under our 1-hour RTO target."

### Follow-up: "How do you handle duplicates?"
> "Geographic routing via wm-site-id header minimizes overlap. Kafka idempotent producer prevents duplicates within same cluster. Deduplication in sink based on request_id handles any remaining overlap. Worst case: duplicates, never data loss."

---

## Decision 9: ContentCachingWrapper vs Custom Buffering

### What's In The Code
```java
ContentCachingRequestWrapper contentCachingRequestWrapper =
    new ContentCachingRequestWrapper(request);
ContentCachingResponseWrapper contentCachingResponseWrapper =
    new ContentCachingResponseWrapper(response);
```

### Why Spring's Built-in Wrapper?

| Approach | Body Access | Memory | Edge Cases | Our Choice |
|----------|------------|--------|------------|------------|
| **ContentCachingWrapper** | Read twice (cached) | Entire body in memory | Handles charset, multipart | **YES** |
| **Custom InputStream wrapper** | Complex, error-prone | Same | Must handle all edge cases | No |
| **Read body, pass bytes** | Requires changing all controllers | Same | Controller changes everywhere | No |

### Interview Answer
> "HTTP request bodies are InputStreams - you can only read them once. Without caching, either the filter or controller reads the body, not both. ContentCachingWrapper is Spring's built-in solution - well-tested, handles charset encoding, multipart, and other edge cases. A custom wrapper would require re-implementing all of that. The trade-off is memory - the entire body is in memory - but our gateway enforces a 2MB payload limit."

---

## Decision 10: isResponseLoggingEnabled Config Flag

### What's In The Code
```java
if (Boolean.TRUE.equals(auditLoggingConfig.isResponseLoggingEnabled())) {
    responseBody = convertByteArrayToString(
        contentCachingResponseWrapper.getContentAsByteArray(), ...);
}
```

### Why A Config Flag?

> "One team wanted response body logging for debugging. Another team didn't - their responses were large (100KB+) and would increase storage costs 10x. Making it a CCM config flag means each team decides independently. No code changes, no redeployment - just a config toggle. This was the key to library adoption across 3 teams - the 20% that was different became configurable."

---

### Decision 11: Backward-Compatible Migration with UNION ALL Views

When replacing Splunk, existing dashboards used `ww_dv_platform_log.nrti_api_logging` tables. We couldn't break them.

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **UNION ALL views** | Zero disruption, gradual migration | Slightly slower queries | **YES** |
| **ETL migration** | Clean data | Downtime, complex transformation | No |
| **Dual-write** | Real-time both | Double processing cost | No |

> "I created Hive views (`nrti_api_logging_vw`, `feeds_api_logging_vw`) that UNION ALL the old Splunk-era tables with the new audit log tables. Existing reports and dashboards kept working with zero changes. Teams migrate at their own pace."

**Key Transformations in the View:**
- Endpoint normalization: `transactionHistory` → `nrti_transactionHistory`
- Correlation ID extraction: `REGEXP_EXTRACT(headers, 'wm_qos.correlation_id')`
- Timestamp conversion: Unix epoch ms → ISO 8601 format
- Environment filtering: Only `prod` records included

---

## Quick Reference: All 11 Decisions

| # | Decision | Chose | Over | Key Reason |
|---|----------|-------|------|------------|
| 1 | Servlet Filter | Raw HTTP access | AOP, Sidecar | Body stream + app context |
| 2 | @Async fire-and-forget | Zero latency | Sync, Direct Kafka | Keep library lightweight |
| 3 | ThreadPool 6/10/100 | Traffic-based | Unbounded | Bounded memory + monitoring |
| 4 | Avro | Schema + 70% smaller | JSON, Protobuf | Kafka ecosystem native |
| 5 | Kafka Connect | Built-in infra | Custom consumer, Flink | 2 days vs 2 weeks |
| 6 | SMT filter (sink-side) | Loose coupling | Producer routing | Add country = new connector |
| 7 | Parquet | 90% compression | JSON, ORC, BQ direct | Cheap storage + native BQ |
| 8 | Active/Active | 15-min failover | Active/Passive | Compliance requirement |
| 9 | ContentCachingWrapper | Well-tested | Custom buffering | Edge cases handled |
| 10 | isResponseLoggingEnabled | Per-team config | Hardcoded | Enabled 3-team adoption |
| 11 | UNION ALL views | Zero disruption | ETL migration, Dual-write | Splunk replacement backward-compat |

---

## Deep Design Questions Interviewers WILL Ask

### "Why a separate publisher service? Why not publish directly to Kafka from the library?"

> "Three reasons:
> 1. **Coupling** — Direct Kafka from the library means every consuming service needs Kafka dependencies, Schema Registry config, SSL certificates, and Avro serialization. That's a heavy dependency for a simple audit feature.
> 2. **Operational isolation** — If Kafka has issues, I want ONE service handling retries and error logging, not 4+ services all dealing with Kafka errors independently.
> 3. **Schema evolution** — Avro schema changes happen in the publisher. Library consumers don't need to rebuild when the schema evolves.
>
> **Trade-off**: Extra network hop adds ~50ms latency. But since audit is async fire-and-forget, this doesn't impact API response time.
>
> **If I rebuilt today**: I'd consider publishing directly from the library to eliminate the hop, now that teams are more mature with Kafka. The coupling concern was valid early on but less relevant now."

### "Why Kafka and not a direct database write?"

> "Four reasons:
> 1. **Durability** — Kafka retains messages for 7 days. If GCS or the sink fails, no data is lost. We proved this during the 5-day silent failure — zero data loss because Kafka retained everything.
> 2. **Decoupling** — The producer doesn't need to know about GCS, Hive, or BigQuery. It just publishes to a topic. We can add new sinks without touching the producer.
> 3. **Throughput** — At 2M+ events/day, direct database writes would overwhelm any OLTP database. Kafka handles millions/sec trivially.
> 4. **Multi-region** — Kafka's built-in replication across EUS2 and SCUS gives us DR for free.
>
> **Alternative considered**: Direct GCS writes from the publisher. Rejected because GCS writes are slow (100-500ms) and would create backpressure on the async thread pool."

### "Why not use OpenTelemetry for this instead of building custom?"

> "OpenTelemetry is designed for traces and metrics — structured spans with start/end times. Our audit system captures full request and response BODIES — the actual JSON payloads. OTel doesn't natively handle large body capture.
>
> Also, OTel backends (Jaeger, Tempo) aren't designed for long-term queryable storage. Suppliers need to run SQL queries on their data for months — that's a data warehouse use case, not an observability use case.
>
> **What I would add**: OTel for TRACING in addition to our audit system. If I had OTel tracing from day one, the 5-day debugging incident would have been solved in hours."

### "Why Parquet and not just JSON files in GCS?"

> "Cost and query performance. Let me quantify:
> - **Storage**: 2M events × ~4KB each × 365 days = ~2.9TB/year in JSON. With Parquet's 90% compression: ~290GB/year. That's $65/yr vs $650/yr just for storage.
> - **Query**: When a supplier queries 'show me all 400 errors', BigQuery/Hive with Parquet reads ONLY the response_code column. With JSON, it has to parse every field in every record. For a table with 1B+ records, this is 10-100x faster.
> - **Schema**: Parquet embeds the schema in each file. No external schema registry needed for the query layer."

### "How did you handle the fact that HTTP bodies are streams you can only read once?"

> "This is THE key technical challenge in Tier 1. HTTP `InputStream` can only be read once. If the filter reads it, the controller gets empty input.
>
> Spring provides `ContentCachingRequestWrapper` and `ContentCachingResponseWrapper`. They intercept the stream, cache the bytes internally, and allow multiple reads.
>
> **Critical detail**: After the filter reads the cached body for auditing, we MUST call `contentCachingResponseWrapper.copyBodyToResponse()`. Without this one line, the client gets an empty response body. This single line is the difference between 'working' and 'catastrophic production bug'.
>
> **Why not a custom BufferedInputStream?** ContentCachingWrapper handles charset encoding, multipart forms, chunked transfer encoding, and other edge cases. A custom solution would need to handle all of these — weeks of work for something Spring already solved."

### "What happens at exactly-once vs at-least-once semantics?"

> "We chose **at-least-once** for the audit pipeline:
> - **Producer side**: Kafka producer with `acks=all` and 10 retries ensures the message reaches Kafka. Duplicate publishes are possible on retry.
> - **Kafka Connect side**: Connect commits offsets after successful GCS write. If the pod crashes between write and commit, the same records may be re-consumed and re-written.
> - **Deduplication**: We use `source_request_id` (UUID) for dedup at the query layer. `SELECT DISTINCT` on request_id handles any duplicates.
>
> **Why not exactly-once?** Kafka Transactions + idempotent producer + Connect exactly-once mode adds significant overhead and complexity. For an audit system where duplicates are harmless (same data, same ID), at-least-once with application-level dedup is the pragmatic choice."

### "How did you convince 4 teams to adopt your library?"

> "I didn't come with a solution — I came with questions:
> 1. **Discovery**: Noticed 3 teams independently building audit logging. Same function, different implementations.
> 2. **Requirements gathering**: Met each team lead 1:1. 'What endpoints? What latency constraints? Need response bodies?'
> 3. **Common vs configurable**: Found 80% common requirements. Made the 20% difference configurable: `isResponseLoggingEnabled`, `enabledEndpoints` regex, `serviceApplication` name.
> 4. **Friction-free adoption**: One Maven dependency, one CCM config block. No code changes to the consuming service.
> 5. **Hands-on support**: Personally paired with each team on their integration PR. Wrote documentation and ran a brown-bag demo.
> 6. **Measuring success**: Integration time dropped from 2 weeks to 1 day. That data point sold the 4th team (BULK-FEEDS) without me needing to pitch at all."

### "What's the biggest mistake you made on this project?"

> "KEDA autoscaling on Kafka consumer lag. It seemed logical — more lag means more work, so scale up.
>
> But I didn't think through the second-order effect: scaling Kafka consumers triggers a consumer group rebalance. During rebalance, NO messages are consumed. So lag increases. KEDA sees more lag, scales more. More rebalancing. Infinite loop.
>
> **What I should have done**: Test autoscaling with realistic production traffic patterns, not just unit tests. The feedback loop only manifests under sustained load with real consumer group behavior.
>
> **What I learned**: Always test scaling behavior with production-like load, including failure modes. And never scale consumers based on consumer lag — use CPU or custom metrics instead."

---

*When they ask "Why X?", answer: "We considered [alternatives]. We chose [X] because [reason]. The trade-off is [downside]. We mitigated by [action]."*
