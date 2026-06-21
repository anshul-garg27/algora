# Interview Q&A Bank - Kafka Audit Logging

---

## Opening Questions

### Q1: "Tell me about this audit logging system you built."

**Level 1 Answer:**
> "When Walmart decommissioned Splunk, I built a replacement audit logging system. But I went beyond just logging - I designed it so external suppliers could query their own API interaction data. It handles 2 million events daily with zero API latency impact."

**Follow-up:** "Why was Splunk being decommissioned?"
> "Cost and licensing. Splunk is expensive at scale, and Walmart decided not to renew the enterprise license. For us, it was an opportunity to build something better."

**Follow-up:** "Can you walk me through the architecture?"
> "Sure. It's a three-component system. First, a reusable Spring Boot library that other services import - it has a filter that intercepts HTTP requests. Second, a Kafka publisher service that serializes to Avro and publishes to a multi-region Kafka cluster. Third, a Kafka Connect sink with custom filters that route records to geographic buckets in GCS. BigQuery sits on top for SQL queries."

**Follow-up:** "Why did you choose this architecture?"
> "The key constraint was supplier access. They needed SQL queries, not log grep. That ruled out traditional log aggregators. I chose:
> - GCS with Parquet because it's cheap at scale and BigQuery reads it natively
> - Kafka for durability - if GCS sink fails, no data loss
> - A library approach so teams get audit logging by adding a Maven dependency
> - Async processing because we couldn't impact API latency"

---

### Q2: "Why did you use a filter instead of AOP?"

> "Filters give us access to the raw HTTP request/response at the servlet level. With AOP, we'd only have access to method parameters and return values, not the actual HTTP body stream. Also, filters let us capture timing information before and after the entire filter chain, including security filters."

---

### Q3: "What happens if the audit service is down?"

> "The API continues to work normally. Audit logging is async and fire-and-forget. We catch all exceptions in AuditLogService and log them, but don't propagate. The user experience is unaffected. We monitor audit service health separately."

---

### Q4: "How do you handle large request/response bodies?"

> "ContentCachingWrapper buffers the body in memory. For very large payloads, we could hit memory issues. In practice, our APIs have payload limits (2MB) set at the gateway. We also have an option to disable response body logging for endpoints with large responses."

---

## Technical Deep Dive Questions

### Q5: "Explain the Kafka Connect SMT filter design."

> "SMT stands for Single Message Transform - it's Kafka Connect's plugin system for processing messages inline.
>
> I created an abstract base class called BaseAuditLogSinkFilter that implements the Transformation interface. It has one abstract method: getHeaderValue(), which subclasses override to return their target site ID.
>
> The apply() method checks if the record's wm-site-id header matches. If yes, return the record. If no, return null - which tells Kafka Connect to drop it.
>
> The clever part is the US filter. Legacy records don't have the wm-site-id header. So the US filter is permissive - it accepts records WITH the US header OR records with NO header. Canada and Mexico filters are strict - exact match only.
>
> This design means all records get processed, nothing is lost, and data ends up in the right geographic bucket."

**Follow-up:** "Why not filter at the producer side?"
> "Two reasons. First, separation of concerns - the producer's job is to publish reliably, not to know about downstream routing. Second, flexibility - if we add a new country, we just deploy a new connector. No changes to producers."

---

### Q6: "How does the async processing work in detail?"

> "Spring's @Async annotation is the key. When you annotate a method with @Async, Spring creates a proxy that submits the method call to an Executor instead of running it directly.
>
> I configured a ThreadPoolTaskExecutor with:
> - corePoolSize: 6 (threads always running)
> - maxPoolSize: 10 (can scale to this)
> - queueCapacity: 100 (buffer before rejection)
>
> When LoggingFilter calls auditLogService.sendAuditLogRequest(), the proxy submits the call to the executor. The filter returns immediately. The executor runs the method when a thread is available.
>
> If all 10 threads are busy and the queue is full (100 items), the default RejectedExecutionHandler throws an exception. But our sendAuditLogRequest catches all exceptions, so the request is silently dropped. This is intentional - we never want audit to fail the API."

**Follow-up:** "Why those specific thread pool sizes?"
> "Based on traffic analysis. Our APIs handle about 100 requests per second per pod. Each audit call takes about 50ms. So we need 5 threads to keep up (100 * 0.05). I set 6 core for headroom. Max 10 handles spikes. Queue of 100 handles burst traffic."

---

### Q7: "Why Avro over JSON?"

> "Three reasons:
> 1. **Schema enforcement** - Prevents bad data from entering the system
> 2. **Size** - ~70% smaller than JSON (binary format)
> 3. **Schema evolution** - Can add fields without breaking consumers
>
> We use Schema Registry for centralized schema management. If someone tries to publish incompatible data, the producer fails fast."

---

### Q8: "Why Parquet for storage?"

> "Two main reasons:
> 1. **Compression** - 90% smaller than JSON files
> 2. **Columnar format** - BigQuery only reads the columns needed for a query
>
> For compliance data that's queried infrequently but must be retained for 7 years, the storage cost savings are significant."

---

## Behavioral Questions

### Q9: "Tell me about a debugging experience."

> *Use the FULL timeline version from [06-debugging-stories.md](./06-debugging-stories.md) and [09-how-to-speak-in-interview.md](./09-how-to-speak-in-interview.md). Tell it as a story with "Fixed? No." moments, not bullet points:*
>
> "Two weeks after launch, I noticed GCS buckets stopped receiving data. No alerts, no errors. The system was failing silently.
>
> **Day 1** - Checked the obvious. Kafka Connect running? Yes. Messages in topic? Millions backing up. So the issue was between consumption and write.
>
> **Day 2** - Enabled DEBUG logging, found NPE in SMT filter on null headers. Added try-catch. Fixed? **No.**
>
> **Day 3** - Found consumer poll timeouts. Tuned configs. Fixed? **Still no.**
>
> **Day 4** - This is where it got interesting. KEDA autoscaling was causing a feedback loop - more lag → more scaling → more rebalancing → more lag. Infinite loop! Disabled KEDA.
>
> **Day 5** - JVM heap exhaustion. Increased from 512MB to 2GB.
>
> **Result:** Zero data loss - Kafka retained everything. Backlog cleared in 4 hours. Created runbook used twice since.
>
> **Key learning:** Distributed systems fail in unexpected combinations. Now I build 'silent failure' monitoring into every system."

---

### Q10: "How did you get other teams to adopt the library?"

> "Three steps:
> 1. **Understood requirements** - Met with engineers from other teams, documented the union of needs
> 2. **Made differences configurable** - One team wanted response body logging, another didn't - made it a config flag
> 3. **Reduced friction** - Wrote docs, did brown-bag session, personally paired on integration PRs
>
> Result: Three teams adopted within a month. Integration time went from 2 weeks to 1 day."

---

### Q11: "Tell me about feedback you received."

> "A senior engineer criticized my thread pool configuration during code review. Said the queue size of 100 was arbitrary and could cause silent data loss.
>
> My first instinct was defensive. But I paused and ran the numbers. He was right about silent loss - when queue fills, tasks are rejected with no indication.
>
> I added: a metric for rejected tasks, a warning log when queue is 80% full, and documentation of the trade-off. Thanked him in the PR comments.
>
> The library is more robust because of that review. We've actually had the queue warning trigger once - caught a downstream slowdown early."

---

## "What If" Questions

### Q12: "What if you needed 100x the throughput?"

> "Current: 2M events/day = ~23 events/sec
> Target: 200M events/day = ~2300 events/sec
>
> **Library:** Switch from HTTP to direct Kafka publishing - removes a network hop
> **Kafka:** Increase partitions from 12 to 48 for more parallelism
> **Connect:** Scale horizontally - add 2-3 more workers
> **GCS:** Can handle it; might adjust file sizes
>
> Cost would scale ~10x, not 100x, because of batching efficiency."

---

### Q13: "What if you needed real-time querying?"

> "Current design optimizes for cost and batch analytics. For real-time, I'd add Elasticsearch as a second sink for recent data (last 7 days), keep GCS for long-term. Query router directs recent queries to ES, historical to BigQuery."

---

### Q14: "What if a regulator asked for all data for a specific supplier to be deleted?"

> "Hard with immutable storage like GCS. Current process:
> 1. Identify all Parquet files with that supplier's data
> 2. Read, filter out their records, write new file
> 3. Delete original
>
> Better design for future: encrypt each record with supplier-specific key. For deletion, delete the key (crypto-shredding). Data remains but is unreadable."

---

### Q15: "If you rebuilt this from scratch, what would you change?"

> "Three things:
> 1. **Skip the publisher service** - Publish directly to Kafka from library (fewer failure points)
> 2. **Add OpenTelemetry from day one** - Debugging the silent failure would've been faster
> 3. **Use Apache Iceberg instead of raw Parquet** - Better for ACID transactions and GDPR deletes"

---

## Quick Answers

### "Why LOWEST_PRECEDENCE for the filter?"
> "Run after all security filters so we capture the final state, including auth failures."

### "Why ContentCachingWrapper?"
> "HTTP streams can only be read once. Without caching, either filter or controller could read the body, not both."

### "Why fire-and-forget?"
> "Audit shouldn't impact API latency. If we blocked waiting for confirmation, a slow audit service would slow all APIs."

### "How do suppliers access their data?"
> "BigQuery external tables with row-level security. Each supplier can only see their own records."

### "What's the latency impact?"
> "P99 under 5ms. The filter adds ~1ms for caching, the rest happens asynchronously after response is sent."

**"How did you validate data accuracy?"**
> "I cross-referenced API Proxy request counts against Hive/Data Discovery record counts daily. Found a 5-7% data loss — up to 130K records/day lost to 413 Payload Too Large errors. After setting the 2MB gateway limit, counts matched exactly."

**"What's your testing strategy?"**
> "Four layers: unit tests with 80%+ coverage across all tiers, integration tests with Testcontainers for Kafka, R2C contract testing as a CI/CD gate, and 36 E2E test scenarios covering happy path, error handling, and analytics queries. Plus load testing at 3x production volume."

**"How do you handle secrets and security?"**
> "AKeyless for secret management — SSL certs, GCS keys, and private keys mounted at runtime. Every audit request is signed with HMAC-SHA256 using a per-service consumer ID and rotating key. Headers are allowlisted — only 6 specific headers forwarded to Kafka to prevent sensitive data leakage."

**"What's your CI/CD pipeline?"**
> "Code push triggers Looper CI — Maven build, SonarQube analysis, Snyk security scan. Then R2C contract tests validate API spec compliance. Stage deploy to both EUS2 and SCUS regions. Automaton performance tests run post-deploy. Production requires a CRQ, then Flagger canary deployment rolls from 10% to 50% traffic with automated rollback if 5xx rate exceeds 1%."

**"What monitoring do you have?"**
> "Grafana golden signals dashboards for health, latency, and memory. Prometheus metrics on every pod. Consumer lag alerts at 50K warning and 75K critical. Dynatrace APM with distributed tracing via OpenTelemetry. GCS write rate monitoring — if rate drops to zero, we get alerted immediately."

**"How many teams use this?"**
> "Four teams and growing: NRT (Near Real Time APIs), IAC (Inventory Activity Capture), cp-nrti-apis, and BULK-FEEDS. Each team configures independently via CCM — they just add the Maven dependency and set their endpoint regex patterns."

**"What's the data query layer?"**
> "GCS stores Parquet files. Hive external tables sit on top via Data Discovery — Walmart's internal query tool. We also have BigQuery external tables for suppliers who need SQL access. An Airflow workflow refreshes Hive partitions daily, and an Automic job handles the MSCK REPAIR TABLE operations."

---

*Practice these out loud until they feel natural!*
