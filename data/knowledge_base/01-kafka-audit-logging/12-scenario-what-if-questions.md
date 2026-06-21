# Scenario-Based "What If?" Questions - Kafka Audit Logging

> **Hiring managers LOVE these.** They test if you truly understand your system under failure.
> Use the framework: DETECT → IMPACT → MITIGATE → RECOVER → PREVENT

---

## Q1: "What if Kafka is completely down?"

> **DETECT:** "Audit error rate spikes in Prometheus. Kafka health check fails."
>
> **IMPACT:** "Audit events are lost during the outage. BUT - supplier API responses are NOT affected. @Async fire-and-forget means the API is completely decoupled from Kafka health."
>
> **MITIGATE:** "Dual-region publishing. If primary (EUS2) is down, CompletableFuture chains to secondary (SCUS). If BOTH are down, exceptions are caught and logged."
>
> **RECOVER:** "When Kafka recovers, new events flow normally. Events during outage are lost - Kafka wasn't available to receive them."
>
> **PREVENT:** "Multi-region Active/Active. Would need local disk buffer to survive both-region-down (not implemented, but on roadmap)."

---

## Q2: "What if the GCS sink stops writing but no one notices?"

> "This is EXACTLY what happened to us - the Silent Failure incident.
>
> **What happened:** Kafka Connect was running, messages were in the topic, but nothing was reaching GCS. No alerts fired because we only monitored 'is it running?' not 'is it processing correctly?'
>
> **Root causes found over 5 days:**
> 1. NPE in SMT filter on null headers → try-catch added
> 2. Consumer poll timeouts → config tuning
> 3. KEDA autoscaling feedback loop → switched to CPU-based HPA
> 4. JVM heap exhaustion → increased to 7GB
>
> **What we added AFTER:**
> - Consumer lag alerts (warning at 100, critical at 500)
> - GCS write rate monitoring (if rate drops to 0, alert)
> - JVM memory metrics in Grafana
> - Dropped record counters
>
> **Lesson:** Monitor OUTPUTS not just INPUTS. 'Messages in topic' doesn't mean 'messages reaching GCS.'"

---

## Q3: "What if the common library JAR has a bug that affects all 3+ teams?"

> **DETECT:** "Multiple teams report audit failures simultaneously. Or our own monitoring shows audit error spike across services."
>
> **IMPACT:** "All services using the library are affected. Audit logging fails for ALL of them."
>
> **MITIGATE:** "The library catches ALL exceptions - audit bugs never break the API. So supplier-facing APIs continue working. Just audit data is affected."
>
> **RECOVER:** "Roll back Maven dependency version. Each team can independently pin to a known good version. Or we release a hotfix version and teams upgrade."
>
> **PREVENT:** "Comprehensive tests in the library. We have unit tests for LoggingFilter, AuditLogService, and configuration. R2C contract testing validates the audit API spec. Code review for all library changes."

---

## Q4: "What if the thread pool queue fills up at 100?"

> "Tasks beyond 100 are rejected by RejectedExecutionHandler. Since @Async catches exceptions, audit logs are silently dropped.
>
> **How we know:** Prometheus metric `audit_log_rejected_count` increments. WARN log fires at 80% queue capacity.
>
> **This happened once:** During a downstream slowdown, the 80% warning triggered. We identified the slow audit-api-logs-srv and scaled it up. Queue never actually filled.
>
> **Why 100 and not 1000?** Bounded queue prevents OOM. At 2KB per payload, 100 items = 200KB. 1000 items = 2MB. Not a memory issue either way, but bounded queues force us to detect problems rather than silently queuing indefinitely."

---

## Q5: "What if a supplier sends a massive 10MB request body?"

> "ContentCachingWrapper caches the ENTIRE body in memory. 10MB per request × 100 concurrent requests = 1GB just for body caching.
>
> **How we prevent this:**
> 1. API gateway enforces payload limit (2MB max) - PR #49-51 set this
> 2. If somehow a large body gets through, ContentCachingWrapper has a configurable limit
> 3. For endpoints with large responses, `isResponseLoggingEnabled` can be set to false via CCM
>
> **The real incident:** Before we set the 2MB limit, some inventory responses (hundreds of items) were causing 413 errors in the audit publisher. We were silently losing audit data for large responses. PR #49 fixed this."

---

## Q6: "What if Avro schema becomes incompatible?"

> **DETECT:** "Producer fails fast - Schema Registry rejects the schema registration. Build/deployment fails."
>
> **IMPACT:** "No new messages published with the new schema. Old messages continue flowing with existing schema."
>
> **MITIGATE:** "Schema Registry is in BACKWARD compatibility mode. New schema must be readable by old consumers. If not, registration is rejected BEFORE any message is published."
>
> **RECOVER:** "Fix the schema to be backward compatible. Add new fields with defaults. Never remove required fields."
>
> **PREVENT:** "Schema compatibility check in CI/CD pipeline. Schema changes go through code review."

---

## Q7: "What if one GCS bucket gets corrupted?"

> "Three separate buckets (US, CA, MX) with three separate connectors.
>
> **If US bucket is corrupted:** Only US audit data affected. CA and MX continue working.
>
> **Recovery:** GCS has versioning and lifecycle policies. We can restore from a previous version. Messages are still in Kafka (retention period) - we can replay them.
>
> **BigQuery impact:** External tables point to GCS. Corrupted files would cause query errors. We'd need to identify and remove/replace corrupted files."

---

## Q8: "What if someone pushes a bad SMT filter update?"

> "This is essentially what happened with the null header issue (PR #35).
>
> **Impact:** Filter could drop ALL records (return null for everything) or crash the connector.
>
> **Detection:** Consumer lag spikes immediately. GCS write rate drops to zero.
>
> **Recovery:** Roll back the Connect deployment. Kafka retains messages - nothing lost. Deploy fix.
>
> **Prevention:**
> - Unit tests for all filter classes (US, CA, MX + base class)
> - Container tests with WireMock
> - Stage deployment before production
> - `errors.tolerance: none` with DLQ means bad records go to dead letter, connector doesn't stop"

---

## Q9: "What happens during Black Friday at 10x traffic?"

> "Current: 2M events/day = ~23/sec. At 10x: **20M events/day** = ~230/sec.
>
> **Library tier:** Thread pool handles it - 6 core threads at 50ms/call = 120 calls/sec per pod. With 5 pods = 600/sec. Fine.
>
> **Publisher tier:** HTTP throughput is the bottleneck. May need to scale pods.
>
> **Kafka tier:** 12 partitions at 23/sec = trivial. At 230/sec still fine. Kafka handles millions/sec.
>
> **Connect tier:** GCS write batching. Larger batches = fewer writes = more efficient at higher throughput.
>
> **Pre-scaling checklist:**
> 1. Increase Connect worker replicas
> 2. Increase publisher pod count
> 3. Pre-warm thread pools (increase core from 6 to 10)
> 4. Increase Kafka retention for safety buffer
> 5. Disable response body logging for high-volume endpoints (reduce payload size)"

---

## Q10: "What if you need to replay the last 24 hours of audit data?"

> "Kafka retains messages for 7 days. To replay:
>
> 1. Reset Connect consumer group offset to 24 hours ago
> 2. Connect re-consumes and re-writes to GCS
> 3. Deduplicate in BigQuery using `request_id` (same request_id = same event)
>
> **Caution:** Replaying creates duplicate files in GCS. BigQuery queries need DISTINCT on request_id during the replay period.
>
> **Better approach:** Apache Iceberg table would handle upserts properly. On our roadmap."

---

## Q11: "What if a new country needs to be added (e.g., UK)?"

> **DETECT:** "Product team requests UK market support."
>
> **IMPACT:** "No existing data affected. Current US/CA/MX continue working."
>
> **IMPLEMENT:**
> 1. Add UK site ID mapping to `audit_api_logs_gcs_sink_prod_properties.yaml`
> 2. Create `AuditLogSinkUKFilter.java` extending `BaseAuditLogSinkFilter` — 5 lines of code
> 3. Add new connector in `kc_config.yaml` with `FilterUK` transform
> 4. Create new GCS bucket `audit-api-logs-uk-prod`
> 5. Create Hive external table for UK data
>
> **Timeline:** "About 2 days — most time spent on CRQ and testing, not code. The architecture was designed for this extensibility."
>
> **This is the power of sink-side SMT filtering:** "Adding a country = deploying a new connector. Zero changes to the producer or library."

---

## Q12: "What if you need to delete a specific supplier's data for compliance (GDPR)?"

> **DETECT:** "Legal/compliance request for supplier data deletion."
>
> **IMPACT:** "Hard with immutable GCS Parquet files. Can't delete individual records."
>
> **Current Process:**
> 1. Identify all Parquet files containing supplier's data (query Hive by `consumer_id`)
> 2. Read each file, filter out supplier's records, write new file
> 3. Replace original file in GCS
> 4. Verify deletion via Data Discovery query
>
> **Better Design (if rebuilding):**
> "Two approaches: (1) **Apache Iceberg** tables support row-level deletes natively — this is on our roadmap. (2) **Crypto-shredding** — encrypt each record with a supplier-specific key. For deletion, destroy the key. Data remains but is unreadable."
>
> **PREVENT:** "Design for compliance from day one. We now discuss data governance requirements before building any new pipeline."

---

*For each answer, connect to a REAL incident if possible: "This actually happened..." makes it 10x more credible.*
