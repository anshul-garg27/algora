# Bullet 1 — Three-Tier Kafka-Based Audit Logging System

> **Resume line (verbatim):** "Designed a three-tier Kafka-based audit logging system with <5ms P99 latency impact processing millions of daily events, Avro serialization, SMT-based geographic routing (US/CA/MX), and GCS Parquet/BigQuery storage, enabling supplier self-service API debugging and eliminating Splunk dependency."
>
> **Summary also claims:** 2M+ events/day, <5ms P99 overhead, org-wide integration standard.

This is the headline bullet. It is real, it is in production, and the architecture is genuinely good. The danger is *over-claiming* a few specific words ("zero data loss," "tuned producer," "Spring Boot sink") that the code does not back up. This document arms you to tell the true story confidently and to convert every weak spot into a "here's what I'd do next" answer that makes you look senior.

---

## 1. Plain-English: what this actually is

### ELI5
Every time a Walmart supplier calls one of our APIs (e.g. "how much of my product is on-hand at store 100?"), we want a permanent receipt of that call — who called, what endpoint, what they sent, what we returned, how long it took, what error if any. Before, those receipts went into **Splunk**, which is expensive and which suppliers can't see. We built a pipeline that captures every API call, ships it through **Kafka**, and lands it as **files in Google Cloud Storage** that **BigQuery** can query. Now a supplier can self-serve: "show me all my failed calls yesterday" — without a human pulling Splunk logs. We also keep US, Canada, and Mexico data in **separate buckets** because of data-residency rules.

### Precise
It is a three-tier asynchronous audit pipeline:

- **Tier 1 — Capture (in-process):** a shared library (`dv-api-common-libraries`) registers a servlet `LoggingFilter` inside each audited service. After the response is produced, it builds an `AuditLogPayload` and **`@Async`** POSTs it to the producer service. The request thread is never blocked on Kafka. (Owned by a sibling doc — referenced here.)
- **Tier 2 — Produce (`audit-api-logs-srv`):** a Spring Boot 3.5 / Java 17 REST service. `POST /v1/logs/api-requests` returns **HTTP 204 immediately**, then a **fire-and-forget thread pool** converts the payload to an **Avro `LogEvent`** and produces it to the Kafka topic `api_logs_audit_{dev|stg|prod}` using Confluent `KafkaAvroSerializer` + Schema Registry. Message **key** = `service_name/endpoint_name`; routing **header** = `wm-site-id`.
- **Tier 3 — Sink (`audit-api-logs-gcs-sink`):** **not** a Spring Boot app — a **Kafka Connect** deployment on Walmart's KCaaS base image. Three `GCPStorageSinkConnector` (Lenses StreamReactor) instances each read the **whole** topic and run a 2-step **SMT** (Single Message Transform) chain: insert a date header, then a **country filter** (`AuditLogSinkUSFilter/CAFilter/MXFilter`) that keeps only its country's records. Surviving records are buffered and written as **Parquet** to per-country GCS buckets; **BigQuery external tables** sit over those buckets.

The "three tiers" you should name in an interview: **Capture → Produce → Sink/Persist**.

---

## 2. The real architecture (grounded in code)

```
TIER 1 — CAPTURE  (dv-api-common-libraries 0.0.61, inside cp-nrti-apis; Java 11 / Spring Boot 2.7.11)
┌────────────────────────────────────────────────────────────────────────────────────┐
│ HTTP request → [security/tracing filters] → LoggingFilter (@Order LOWEST_PRECEDENCE) │
│   filters/LoggingFilter.java:                                                        │
│     • gate: FeatureFlagCCMConfig.isAuditLogEnabled()  (runtime CCM flag)             │
│     • skip /actuator; shouldNotFilter() = endpoint NOT in auditLoggingConfig list    │
│     • ContentCachingRequest/ResponseWrapper → capture bodies, epoch-second ts        │
│     • AuditLogFilterUtil.prepareRequestForAuditLog() → AuditLogPayload (18 fields)    │
│     • AuditLogService.@Async sendAuditLogRequest()  (taskExecutor core6/max10/queue100)│
│       → AuthSign 4 WM_* headers → reactive WebClient POST  ──────────────┐           │
└──────────────────────────────────────────────────────────────────────────┼──────────┘
                                                              HTTP POST JSON │ auditLogURI
                                                                             ▼
TIER 2 — PRODUCE  (audit-api-logs-srv; Spring Boot parent 3.5.12 / Java 17)
┌────────────────────────────────────────────────────────────────────────────────────┐
│ controllers/AuditLoggingController.saveApiLog(LoggingApiRequest)  → return 204 NOW   │
│   → services/LoggingRequestService.processLoggingRequest()                           │
│       target = Map<String,TargetedResources>.get("kafkaProducerService")             │
│       → services/ExecutorPoolService.executeTaskInThreadPool(task)                   │
│            pool = Executors.newCachedThreadPool()   ← UNBOUNDED (the real <5ms lever) │
│       → returns Boolean.TRUE synchronously (caller already has its 204)              │
│   → kafka/KafkaProducerService.publishMessageToTopic():                              │
│       topic   = AuditLogsKafkaCCMConfig.getAuditLoggingKafkaTopicName()              │
│       value   = AvroUtils.getLogEvent(req) → LogEvent (19-field Avro SpecificRecord) │
│       key     = AuditKafkaPayloadKey.getKafkaKey() = serviceName + "/" + endpoint    │
│       headers = whitelist{wm_consumer.id, wm_qos.correlation_id, wm_svc.name,        │
│                 wm_svc.version, wm_svc.env, wm-site-id}                               │
│       kafkaPrimaryTemplate.send(message)   ← wrapped in try/catch (log-only)         │
│   kafka/KafkaProducerConfig: key=StringSerializer, value=KafkaAvroSerializer,        │
│       schema.registry.url (CCM), auto.register.schemas=false, conditional mTLS JKS   │
│       (kafkaSecondaryTemplate bean exists but is NEVER sent through = dead code)      │
└────────────────────────────────────────────────────────────────────┼─────────────────┘
                                                                       ▼
            ┌──────────────────────────────────────────────────────────────────┐
            │ KAFKA TOPIC  api_logs_audit_prod                                   │
            │ cluster kafka-v2-luminate-core-prod, EUS2 + SCUS, :9093, mTLS      │
            │ key = service_name/endpoint_name   header = wm-site-id             │
            │ DLQ: api_logs_audit_prod_DLQ                                        │
            └──────────────────────────────────────────────────────────────────┘
                                          │  (the SAME record is read 3× — once per connector)
                                          ▼
TIER 3 — SINK  (audit-api-logs-gcs-sink; Kafka Connect on KCaaS base-image:11-major; NOT Spring)
┌────────────────────────────────────────────────────────────────────────────────────┐
│ worker: key.converter=StringConverter, value.converter=AvroConverter (schemas=true)  │
│ THREE GCPStorageSinkConnector instances (io.lenses.streamreactor...), tasks.max=1:   │
│                                                                                      │
│   US connector  transforms = InsertRollingRecordTimestamp, FilterUS                  │
│   CA connector  transforms = InsertRollingRecordTimestamp, FilterCA                  │
│   MX connector  transforms = InsertRollingRecordTimestamp, FilterMX                  │
│                                                                                      │
│   SMT 1: io.lenses.connect.smt.header.InsertRollingRecordTimestampHeaders            │
│            date.format=yyyy-MM-dd, timezone=GMT  → writes header `_header.date`       │
│   SMT 2: com.walmart.audit.log.sink.converter.AuditLogSink{US|CA|MX}Filter           │
│            apply(r) = verifyHeader(r) ? r : null    (null = record dropped)          │
│            US: site_id==US  OR  no wm-site-id header     (CATCH-ALL, permissive)      │
│            CA/MX: exact site_id match only; missing header → dropped (STRICT)         │
│                                                                                      │
│   KCQL (per connector/region): INSERT INTO `<bucket>:<dataset>.db/api_logs`          │
│     SELECT * FROM `api_logs_audit_prod`                                              │
│     PARTITIONBY service_name, _header.date, endpoint_name                            │
│     STOREAS PARQUET  PROPERTIES(flush.size=50000000, flush.count=5000,               │
│                                 flush.interval=600, key.suffix=_eus2|_scus)          │
│   errors.tolerance=all, DLQ headers on, error.policy=RETRY, max.retries=5            │
└────────────────────────────────────────────────────────┼─────────────────────────────┘
                                                           ▼
   GCS project wmt-dv-luminate-prod  (Parquet, partition service_name/_header.date/endpoint_name)
     • audit-api-logs-us-prod : us_dv_audit_log_prod.db/api_logs
     • audit-api-logs-ca-prod : ca_dv_audit_log_prod.db/api_logs
     • audit-api-logs-mx-prod : mx_dv_audit_log_prod.db/api_logs
                                                           ▼
   BigQuery EXTERNAL TABLES over the Parquet  →  suppliers self-serve their API audit logs
```

**Key files to name (all verified on disk):**

| Tier | File | Role |
|---|---|---|
| 2 | `audit-api-logs-srv/.../controllers/AuditLoggingController.java` | `saveApiLog` returns 204 immediately |
| 2 | `.../services/LoggingRequestService.java` | resolves `kafkaProducerService`, submits to pool, returns `TRUE` |
| 2 | `.../services/ExecutorPoolService.java` | `Executors.newCachedThreadPool()` (unbounded) |
| 2 | `.../kafka/KafkaProducerService.java` | builds `Message<LogEvent>`, header whitelist, `kafkaPrimaryTemplate.send()` in try/catch |
| 2 | `.../kafka/KafkaProducerConfig.java` | producer config (bootstrap, serializers, schema-registry, SSL) — **no acks/idempotence/linger** |
| 2 | `.../utils/AvroUtils.java` | `LoggingApiRequest` → Avro `LogEvent`; `created_ts=now`, `consumer_id` from `wm_consumer.id` else `"NA"` |
| 2 | `.../models/AuditKafkaPayloadKey.java` | `getKafkaKey()` = `serviceName + "/" + endpoint` |
| 2 | `src/main/resources/avro/log.avsc` | the 19-field Avro contract, namespace `com.walmart.dv.audit.model.api_log_events` |
| 2 | `.../common/config/AuditLogsKafkaCCMConfig.java` | CCM `auditLoggingKafkaCCMConfig` (brokers/topic/SR url/ssl flag) |
| 3 | `gcs-sink/topic_to_buckets_records_flow.md` | the canonical flow diagram |
| 3 | `gcs-sink/kc_config.yaml` | 3 connectors, transform chains, retry/DLQ |
| 3 | `gcs-sink/env_properties.yaml` | per-env KCQL, bucket/dataset names, schema-registry URLs |
| 3 | `.../converter/BaseAuditLogSinkFilter.java` | strict base filter (`Transformation<R>`) |
| 3 | `.../converter/AuditLogSinkUSFilter.java` | permissive override (catch-all incl. header-less) |
| 3 | `.../converter/AuditLogSink{CA,MX}Filter.java` | strict, only override `getHeaderValue()` |
| 3 | `.../converter/AuditApiLogsGcsSinkPropertiesUtil.java` | maps country code → `WM_SITE_ID_FOR_<CC>` from env yaml |

---

## 3. Every design decision

| # | Decision | Why | Alternatives considered | Trade-off / what we gave up |
|---|---|---|---|---|
| D1 | **Async, fire-and-forget capture** (Tier 1 `@Async` POST; Tier 2 returns 204 then runs the Kafka send on a pool) | Auditing must add **near-zero latency** to the business API. The supplier's request thread must not wait on Kafka. | Synchronous publish in the request path; co-locate logging in the app and write directly. | If the audit POST or Kafka send fails, the **caller never learns**; we trade delivery certainty for latency. No back-pressure signal. |
| D2 | **Kafka as the backbone** (vs direct-to-GCS, vs DB) | Decouples producers from the sink, absorbs bursts, lets us add consumers later (replay, alerting) without touching producers. Durable, replayable buffer. | Write straight to GCS from each service; push to a DB; push to Splunk HTTP. | Operational cost of running Kafka + Connect + Schema Registry; a new SPOF (Schema Registry) on the path. |
| D3 | **Avro + Confluent Schema Registry**, `auto.register.schemas=false` | Compact binary, strong typing, **governed** schema evolution. `false` means schemas are promoted through a registry workflow, not silently auto-registered by whatever pod boots first → prevents accidental incompatible changes. | JSON (self-describing but bloated, no enforced compatibility); Protobuf (great, but Avro is the Walmart streaming default + first-class Connect support). | Operational coupling to Schema Registry; a forgotten registration breaks producers in that env; binary payloads aren't human-readable on the wire. |
| D4 | **Message key = `service_name/endpoint_name`** | Co-partitions all records for a given API on one partition → **per-endpoint ordering**, and naturally groups a "noisy" endpoint together. | Random/null key (max spread, no ordering); `trace_id` (perfect spread, no grouping); `wm-site-id` (only 3 values → 3 hot partitions). | **Hot-partition risk**: a single high-traffic endpoint (e.g. NRT `inventory/status`) concentrates load on one partition. Cardinality is bounded by #services × #endpoints. |
| D5 | **Routing on a Kafka *header* (`wm-site-id`), not the key** | The key is needed for ordering/partitioning; residency routing is an orthogonal concern, so it rides in a header set by the producer's whitelist. | Encode country in the key; route on a body field (requires deserializing in the SMT). | Header can be missing → US catch-all semantics (D8). Routing decision is decoupled from partitioning, which is good, but means the SMT must read headers. |
| D6 | **Geo-routing done in the SINK via SMT (3 connectors)**, not at produce time | One topic = one immutable audit stream, simplest producer. Residency is a **read/landing** concern, so we split at the last possible moment. Each country gets an **isolated failure domain** (CA bucket outage doesn't stall US). | (a) Topic-per-region at produce time; (b) producer-side custom partitioner; (c) one branching connector; (d) separate consumer apps. | **3× read amplification**: every record is consumed by all 3 connectors (3× broker egress, 3× SMT CPU). Justified because audit volume is modest and isolation/operability win. |
| D7 | **Lenses StreamReactor `GCPStorageSinkConnector` via Kafka Connect** (not a hand-written Spring consumer) | Connect gives us offset management, rebalancing, retries, DLQ, exactly the Parquet/GCS batching we need — for free. We wrote only ~75 lines of SMT. **Reuse over rebuild.** | Spring Boot `@KafkaListener` + custom GCS Parquet writer + custom offset/retry/DLQ logic. | Less control over internals; tied to Lenses behavior/versioning; the connector is a black box when something deep breaks. |
| D8 | **US filter is permissive (catch-all incl. header-less); CA/MX strict** | US is the default tenant. A record with a missing/unknown `wm-site-id` must land *somewhere* and not be silently lost → it goes to US. CA/MX must be strict for residency (don't pollute CA bucket with ambiguous data). | All-strict (lose header-less records); a 4th "unknown/quarantine" bucket. | Any mis-tagged or header-less record lands **only in US** — a residency edge case to confirm with compliance. CA/MX silently drop missing headers. |
| D9 | **Parquet on GCS + BigQuery external tables** | Audit queries are **analytical** (scan a date range, filter by service/endpoint, aggregate errors). Columnar Parquet + partition pruning makes that cheap; GCS is the cheap landing zone; BigQuery external tables query in place — no second copy/ETL. | Row formats (CSV/JSON/Avro) on GCS; native BigQuery ingest; a warehouse load job. | External tables are slightly slower than native BQ and need partition hygiene; tiny Parquet files (the "small files" problem) hurt scan efficiency → hence large `flush.size`. |
| D10 | **Partition by `service_name / _header.date / endpoint_name`** | Matches the supplier query pattern ("my service, this date, this endpoint") → BigQuery/Hive partition pruning scans only relevant prefixes. | Partition by ingestion time only; no partitioning (full scans). | High-cardinality endpoints create many small partitions; date is GMT so day-boundary semantics differ from local time. |
| D11 | **Big flush thresholds** (`flush.size=50MB`, `flush.count=5000`, `flush.interval=600s`) | Produce **few, large** Parquet objects → avoids the small-files problem, cheaper GCS ops, faster BQ scans. | Small flush (low latency to GCS, but tiny files); time-only flush. | Up to ~10 min of audit data sits in connector memory before it's visible in GCS → audit logs are **near-real-time, not real-time**. A task crash can re-deliver the last unflushed window (at-least-once). |
| D12 | **CCM-driven config everywhere** (`@ManagedConfiguration`, layered `kc_config ← env_properties ← CCM`) | Flip brokers, topic, SSL, feature flags, even disable auditing entirely — **at runtime, no redeploy**. | Hardcoded/app-properties config; env vars only. | Config sprawl across CCM + yaml; the source of truth for a value can be non-obvious; SSL is in CCM, not the committed yaml (looks "off" if you only read the repo). |
| D13 | **Active/active EUS2 + SCUS deployment**, de-conflicted by `key.suffix` `_eus2`/`_scus` + separate index objects | Region resilience; both regions' Connect workers can write to the *same* GCS bucket without clobbering each other's files/indexes. | Active/passive (one region idle); region-specific buckets. | Two live writers into shared buckets → must manage object-name collisions (solved by suffix), slightly more complex offset/index bookkeeping. |

---

## 4. Deep-dive Q&A

### FUNDAMENTALS

**Q1. Give me the 60-second overview.**
"I designed a three-tier audit pipeline: capture, produce, sink. A shared library inside each API service asynchronously captures every request/response and POSTs it to a producer service. That producer — `audit-api-logs-srv` — returns 204 immediately, then on a background thread serializes the record to Avro and publishes it to a Kafka topic, `api_logs_audit_prod`, with the message key `service_name/endpoint_name` and a `wm-site-id` header. The consumer side is a Kafka Connect deployment with three Lenses GCS sink connectors, one each for US, CA, MX. Each runs a Single Message Transform that filters records by the `wm-site-id` header and writes Parquet into that country's GCS bucket. BigQuery external tables sit over those buckets so suppliers can self-serve their API audit history. The whole point was async, near-zero latency overhead, geo-segregated storage, and getting us off Splunk."

**Q2. Why audit logging at all — what problem did it solve?**
"Two problems. First, **cost and access**: API audit data lived in Splunk, which is expensive and which external suppliers can't query — every 'why did my call fail?' became a support ticket and a human pulling Splunk. Second, **self-service debugging**: suppliers integrate against our NRTI inventory APIs and need to see their own traffic — request, response, status, error reason, latency. Landing it in BigQuery turns that into a query they run themselves. So the bullet's 'enabling supplier self-service API debugging and eliminating Splunk dependency' is the business outcome."

**Q3. What are the three tiers, concretely?**
"Tier 1 capture is the `LoggingFilter` in `dv-api-common-libraries` — a servlet filter at lowest precedence that wraps request/response, builds an `AuditLogPayload`, and `@Async`-POSTs it. Tier 2 produce is `audit-api-logs-srv` — REST in, Avro out to Kafka. Tier 3 sink is `audit-api-logs-gcs-sink` — Kafka Connect, three connectors, Parquet to GCS. I own tiers 2 and 3 and the end-to-end narrative."

**Q4. What's in an audit record?**
"The wire contract is the Avro schema `log.avsc`, 19 fields: `source_request_id`, `api_version`, `endpoint_path`, `trace_id`, `supplier_company`, `method`, `request_body`, `response_body`, `response_code`, `error_reason`, `consumer_id`, `request_ts`, `response_ts`, `request_size_bytes`, `response_size_bytes`, `headers` (a JSON string), `created_ts`, `endpoint_name`, `service_name`. The required, non-null fields are `source_request_id`, `endpoint_path`, `method`, `response_code`, `consumer_id`, the three timestamps, `endpoint_name`, `service_name`; everything else is nullable-with-default for evolution. `AvroUtils.getLogEvent()` does the mapping and sets `created_ts = System.currentTimeMillis()` and `consumer_id` from the `wm_consumer.id` header, defaulting to `"NA"`."

**Q5. Why Kafka and not a direct write to GCS or a database?**
"Decoupling and durability. If each service wrote straight to GCS, every service would carry GCS creds, retry logic, and Parquet batching, and a GCS hiccup would couple back into the request path. Kafka is a durable, replayable buffer that absorbs bursts and lets me add consumers — replay, real-time alerting, a second sink — without touching any producer. A DB would be the wrong shape: this is append-only, high-volume, analytical-read data, not transactional."

**Q6. Why Avro over JSON or Protobuf?**
"Avro is compact binary with a schema, and with Confluent Schema Registry I get governed evolution — I can add a nullable field and old consumers keep working under BACKWARD compatibility. JSON is self-describing but 3–10× bigger on the wire and gives no compatibility enforcement. Protobuf is comparable to Avro technically, but Avro is the Walmart streaming default and is first-class in Kafka Connect's `AvroConverter`, so it was the path of least resistance with the most platform support. The sink's `value.converter=io.confluent.connect.avro.AvroConverter` with `schemas.enable=true` reads exactly what the producer's `KafkaAvroSerializer` wrote."

### INTERMEDIATE

**Q7. How do you achieve <5ms P99 latency impact?**
"The capture is off the critical path in two stages. In Tier 1, the `LoggingFilter` does the build + sign + POST on the `@Async` `taskExecutor` (core 6 / max 10 / queue 100), so the supplier's response is already on the wire. In Tier 2, `AuditLoggingController.saveApiLog` returns 204 *before* any Kafka work — `LoggingRequestService` hands the publish to `ExecutorPoolService`, an `Executors.newCachedThreadPool()`, and returns `TRUE` synchronously. So the only thing on the request thread is the cost of the body-caching wrappers and submitting a `Runnable`. The Kafka serialization, Schema Registry lookup, and network send all happen on the pool thread. That's the mechanism behind <5ms — it's an *added overhead on the audited API*, not the end-to-end audit latency."

**Q8. What's the message key and what does it buy you?**
"`AuditKafkaPayloadKey.getKafkaKey()` returns `serviceName + "/" + endpoint` — e.g. `NRT/transactionHistory`. Kafka hashes the key to pick a partition, so all records for one service+endpoint go to the same partition, giving me **per-endpoint ordering** and grouping. The trade-off is hot partitions: a very busy endpoint pins one partition. For audit logs that's acceptable because strict ordering isn't critical and the downstream is a batch sink, but if it became a bottleneck I'd switch high-volume endpoints to a composite key like `service/endpoint/consumer_id` to spread load while keeping useful grouping."

**Q9. What is an SMT and why route in the sink with one?**
"An SMT — Single Message Transform — is a lightweight, per-record hook in Kafka Connect that runs between the connector and the converter. It can mutate, enrich, or **drop** a record (returning `null` drops it). I used two: a Lenses `InsertRollingRecordTimestampHeaders` that stamps a `yyyy-MM-dd` GMT date into the `_header.date` header for time-based file partitioning, and my own country filter that returns the record if its `wm-site-id` matches, else `null`. I routed in the sink because the topic should stay a single immutable stream and residency is a landing concern — splitting at the sink keeps producers dumb and gives me three isolated connector failure domains."

**Q10. Why three connectors instead of one? Isn't reading the topic 3× wasteful?**
"Yes, it's literally 3× read amplification — each record is consumed once per connector. I accepted that deliberately. The wins: each country is an **isolated failure domain** (a CA GCS permission problem can't stall US delivery), each has independent offsets and consumer lag, and each maps cleanly to one KCQL/bucket so the config is dead simple. For modest audit volume, the extra broker egress is cheap relative to the operability and blast-radius benefits. If volume grew 10×, I'd reconsider a single connector with KCQL/SMT branching to one read, accepting a shared failure domain."

**Q11. Walk me through the country-filter code.**
"`BaseAuditLogSinkFilter<R>` implements `Transformation<R>`. Its `apply(r)` returns `r` if `verifyHeader(r)` else `null`. The base `verifyHeader` does a parallel-stream `anyMatch` over the record's headers for `wm-site-id` equal to `getHeaderValue()`, and is **fail-closed** — any exception returns false, so a malformed record is dropped rather than stalling the task. `AuditLogSinkUSFilter` **overrides** `verifyHeader` to also pass when there is **no** `wm-site-id` header (`noneMatch`), making it the catch-all. `CAFilter` and `MXFilter` only override `getHeaderValue()` and inherit the strict base. The site-id strings come from `AuditApiLogsGcsSinkPropertiesUtil`, which reads `WM_SITE_ID_FOR_<CC>` from an env-specific properties file selected by `STRATI_RCTX_ENVIRONMENT_TYPE`."

**Q12. Where does the data physically land and how is it partitioned?**
"GCS project `wmt-dv-luminate-prod`, three buckets: `audit-api-logs-us-prod` (`us_dv_audit_log_prod.db/api_logs`), `-ca-prod`, `-mx-prod`. The KCQL is `INSERT INTO <bucket> SELECT * FROM api_logs_audit_prod PARTITIONBY service_name, _header.date, endpoint_name STOREAS PARQUET`. So the object key path is service → date → endpoint, which is exactly the supplier query shape, enabling partition pruning. BigQuery external tables are defined over those Parquet paths."

**Q13. Why Parquet and big flush sizes?**
"Parquet is columnar, so an audit query that selects a few columns and filters by date/service reads only those column chunks in the relevant partitions — cheap scans in BigQuery. Big flush thresholds (50MB / 5000 records / 600s) produce few large files, avoiding the small-files problem that would otherwise blow up GCS object counts and slow BQ. The cost is freshness: up to ~10 minutes of data buffers before it's queryable. For audit/debugging that latency is fine."

### DEEP / INTERNALS

**Q14. Is the producer tuned for durability — acks, idempotence, retries?**
"Honest answer: **no, and I want to flag that.** `KafkaProducerConfig.populateConfigProperties` sets only `bootstrap.servers`, `key.serializer=StringSerializer`, `value.serializer=KafkaAvroSerializer`, `schema.registry.url`, `auto.register.schemas=false`, and conditional SSL props. It does **not** set `acks`, `enable.idempotence`, `retries`, `linger.ms`, `batch.size`, or `compression.type`. So the Kafka client **defaults** apply — for this client era that's effectively `acks=1`, no idempotence. That means on a leader failure between ack and replication we could lose a record. So if someone says 'you claimed zero data loss,' I correct it: the *pipeline shape* is durable, but the *producer durability config was not hardened*. The fix is one method: set `acks=all`, `min.insync.replicas=2` on the topic, `enable.idempotence=true`, and `retries` high with `delivery.timeout.ms`. I'd lead with that as the first thing I'd change."

**Q15. The send is in a try/catch that only logs. What happens on failure?**
"In `KafkaProducerService.publishMessageToTopic`, `kafkaPrimaryTemplate.send()` is wrapped in `try/catch (Exception)` that only logs. Two issues: (1) `KafkaTemplate.send()` is async and returns a future, so a *broker-side* failure (e.g. not enough ISR) won't even throw synchronously — it completes the future exceptionally, which we don't observe; the catch only covers synchronous failures like serialization. (2) Combined with the 204-then-fire-and-forget design, **the caller never learns about a failed publish**. There's no app-level retry or DLQ on the produce side. I'd address it by attaching a callback to the future (`whenComplete`) that increments a failure metric and writes to an app-side DLQ, and by hardening the producer config so transient failures are retried by the client."

**Q16. There's a `kafkaSecondaryTemplate`. Is there dual-region failover here?**
"That's a subtle one I'll own. `KafkaProducerConfig` builds both `kafkaPrimaryTemplate` and `kafkaSecondaryTemplate` (secondary uses the SCUS broker list), and `KafkaProducerService` autowires both — but the send path only ever calls `kafkaPrimaryTemplate.send()`. So the **secondary template is dead code** in this service; the only real regional behavior is that CCM swaps which region is 'primary' per zone (`prod-eus2` vs `prod-scus` overrides flip the broker lists). The *real* active/active primary→secondary Kafka failover lives in `cp-nrti-apis` (`NrtKafkaProducerConfig`, four templates, `primary.send().exceptionally(→secondary)`). So when I talk failover, I attribute the genuine failover code to NRTI and I'm precise that the audit producer relies on region-level active/active deployment plus CCM, not an in-code template fallback."

**Q17. Schema Registry is on the path. What's the failure mode and isn't it a SPOF?**
"On the producer, `KafkaAvroSerializer` looks up/validates the schema ID against the registry (and caches it). If the registry is unreachable on a cache miss, the serialize fails — which in this design just logs and drops that record. On the sink, `AvroConverter` resolves the writer schema by ID for deserialization. So yes, Schema Registry is a shared dependency. Mitigations: the serializer caches schema IDs so steady-state traffic doesn't hit the registry per message; `auto.register.schemas=false` means we don't depend on registration at runtime, only resolution; and the registry itself is an HA Walmart platform service. At 10×, I'd want explicit alerting on serializer errors and a circuit-breaker that spills to an app DLQ rather than dropping."

**Q18. Why `auto.register.schemas=false`?**
"Governance. With `true`, the first producer to start would auto-register whatever schema it has, including an accidental incompatible change, and you find out in production. With `false`, schemas are promoted through a controlled registry workflow, and a producer carrying a non-registered/incompatible schema fails fast instead of corrupting the subject's history. It forces schema changes to be deliberate."

**Q19. How does Kafka Connect manage offsets, and what's your delivery guarantee end-to-end?**
"Connect runs in distributed mode; each connector's consumer group commits offsets to Kafka after records are successfully delivered to the sink (here, after a Parquet flush to GCS). On a task crash or rebalance, it resumes from the last committed offset, so the unflushed window is re-read and re-written — that's **at-least-once**, which can yield duplicate rows in GCS for the records in flight at crash time. Combined with `acks=1` on the produce side, the overall guarantee is 'at-least-once if the produce succeeds, with a small loss window on leader failure.' For an audit/debugging store, near-complete with possible rare dupes is acceptable; I'd dedupe in BigQuery on `source_request_id` if exactness mattered."

**Q20. What's the consumer group / rebalancing setup in the sink?**
"From `kc_config.yaml`: `tasks.max=1` per connector (one task because audit volume is modest and Parquet batching is simpler single-task), `max.poll.records=50`, `max.poll.interval.ms=300000` (5 min), `session.timeout.ms=15000`, `heartbeat.interval.ms=5000`. The 5-minute poll interval is generous so a slow GCS flush doesn't trip a rebalance. Each connector is its own consumer group (`group.id` per Connect cluster); the three country connectors run in the same Connect worker cluster but as distinct connector configs."

**Q21. How does active/active EUS2+SCUS not double-write or clobber files in shared buckets?**
"Both regional Connect clusters write to the *same* GCS bucket, so the de-confliction is by object naming: KCQL sets `key.suffix=_eus2` vs `_scus` and `indexes.name=.indexes-eus2` vs `.indexes-scus`. So each region writes distinct object names and maintains its own index objects — no collisions, no shared mutable state. They consume the same topic from their region-local brokers (`kafka-v2-luminate-core-prod.eus...` / `.scus...`)."

**Q22. mTLS — where is it enforced and why is `auditLoggingKafkaSslEnabled=false`?**
"In `KafkaProducerConfig`, SSL props (JKS truststore/keystore from `/etc/secrets`) are added only when `auditLoggingKafkaSslEnabled` is true. In the prod CCM (`PROD-1.0-ccm.yml`) that flag is **false**, and the log line says it explicitly: 'mTLS is enforced for Kafka connections' at the **Istio** layer. So transport security is handled by the service-mesh sidecar (`tlsMode: MUTUAL`, the kitt annotations exclude only specific outbound ports), not by the Kafka client's own SSL. Same on the sink — `kc_config.yaml` has `security.protocol: PLAINTEXT` with the SSL block commented out, because the mesh terminates mTLS. That's a legitimate platform pattern; I just need to be precise that it's mesh-level, not client-level."

**Q23. The headers field — how is it stored and what's the risk?**
"`AvroUtils.getJsonString(headers)` serializes the whole header map to a JSON string into the Avro `headers` field. `KafkaProducerService.setHeaders` separately whitelists only `wm_consumer.id`, `wm_qos.correlation_id`, `wm_svc.name`, `wm_svc.version`, `wm_svc.env`, `wm-site-id` as **Kafka message headers**. But the **body `headers` field** carries whatever the upstream capture put there. In the common lib, the capture copies **all** request headers with no masking — including `Authorization`/`WM_SEC.*` signatures. So the audit store can contain secrets/PII. I flag this proactively as the top thing I'd fix: mask sensitive headers at capture time (drop `WM_SEC.*`, `Authorization`, cookies) before they ever leave the service."

### SCENARIO / "what if"

**Q24. The cached thread pool is unbounded. What happens under a traffic burst?**
"That's the real stability risk and I'll name it. `Executors.newCachedThreadPool()` creates a new thread per task when none is idle, with no queue cap and no rejection. Under a sustained burst — say a retry storm or a downstream Kafka slowdown so tasks don't drain — thread count grows unbounded, each thread costs ~1MB stack, and we risk `OutOfMemoryError`/`OutOfMemoryError: unable to create new native thread`, taking down the pod. Ironically the same unbounded pool is what gives the snappy 204. The right design is a **bounded `ThreadPoolExecutor`** with a fixed max, a bounded queue, and an explicit `RejectedExecutionHandler` that increments a 'dropped audit' metric — you bound memory and you get observability into shedding. I'd pair that with producer-config hardening so tasks drain faster."

**Q25. A record arrives with no `wm-site-id` header. Where does it go?**
"Only to the **US** bucket. `AuditLogSinkUSFilter.verifyHeader` passes records whose header is missing (the `noneMatch` branch); CA and MX inherit the strict base and drop missing-header records. So header-less or mis-tagged records land in US only. That's a deliberate catch-all so nothing is silently lost, but it's a residency edge case — I'd confirm with compliance that 'unknown origin → US' is acceptable, and consider a dedicated 'unknown' bucket if not."

**Q26. The sink can't write to GCS for 30 minutes. What happens?**
"Connect's GCS error policy is RETRY with `max.retries=5`, `retry.interval=5000ms`; `errors.tolerance=all` with DLQ headers enabled routes poison records to `api_logs_audit_prod_DLQ`. For a transient GCS outage, the connector retries; because offsets only commit after a successful flush, nothing is lost — when GCS recovers, it resumes from the last committed offset and the buffered/unflushed window is re-read. Kafka retention (the topic holds days of data) is the safety net: as long as the outage is shorter than retention, we catch up. If it exceeded retention, we'd lose the aged-out records — a reason to size retention generously for audit."

**Q27. Schema evolution: a producer adds a field. Does the sink break?**
"Not if I add it correctly. Adding a **nullable field with a default** is BACKWARD-compatible: the sink's `AvroConverter`, resolving by schema ID, can read new-schema records against an older reader schema (missing fields take defaults) and vice versa. Every optional field in `log.avsc` is already `["null", T]` with `default: null` exactly for this. What breaks: adding a **required** field, removing a field other consumers need, or changing a type — those are FORWARD/FULL violations and the registry (with the right compatibility level) would reject them. My rule is: only ever add nullable-with-default fields to this schema."

**Q28. A supplier says 'my call yesterday is missing from BigQuery.' How do you debug?**
"I trace tier by tier. (1) Did capture fire? Check the source service's `LoggingFilter` logs and whether `isAuditLogEnabled` and the endpoint allow-list covered that path. (2) Did the producer accept it? It returned 204 regardless, so I check `audit-api-logs-srv` logs for the `source_request_id`/`trace_id` (we log on send) and for serialize/send errors. (3) Was it produced? Inspect the topic for that key/offset window. (4) Did the right connector keep it? If `wm-site-id` was wrong, it may have been filtered to the wrong bucket or dropped by CA/MX strictness; check the DLQ. (5) Has it flushed yet? Up to ~10 min buffer + GMT date partition boundary can make 'yesterday' land in a different partition than expected. The `trace_id` threads it all together."

**Q29. How would you make this exactly-once / lossless end to end?**
"Produce side: `acks=all` + `min.insync.replicas=2` + `enable.idempotence=true` (idempotent producer dedupes retries within a session). For true end-to-end EOS you'd need transactions across produce, but the sink is Connect, so the pragmatic answer is at-least-once produce + idempotent sink semantics: keep a stable `source_request_id` and **dedupe in BigQuery** (e.g. a view with `ROW_NUMBER() OVER (PARTITION BY source_request_id)`). For audit data, at-least-once + dedupe-on-read is the right cost/benefit; full Kafka transactions would add latency and complexity I don't need."

**Q30. Volume 10×'s overnight. What's your scaling plan?**
"Order of operations: (1) harden + tune the producer (`linger.ms`, `batch.size`, `compression.type=lz4`, idempotence) so we batch and the cached pool drains faster; replace the unbounded pool with a bounded one. (2) Increase topic **partitions** and, if a single endpoint is hot, change the key to a composite to spread it. (3) Bump sink `tasks.max` above 1 so each connector parallelizes across partitions. (4) Re-evaluate the 3-connector fan-out — at 10× the 3× read amplification becomes a real cost, so I'd consider a single connector with KCQL/SMT branching. (5) Watch the small-files vs freshness trade-off on flush sizes. (6) Add autoscaling on the producer (kitt HPA is already 60% CPU)."

**Q31. What if Schema Registry is down at producer startup?**
"Steady state is fine because schema IDs are cached, but a cold start that needs to resolve/validate a schema on first publish would fail those sends — and in this design they'd be logged-and-dropped. That's another reason to (a) harden against drops with an app DLQ + metric, and (b) rely on the registry's HA. Crucially, `auto.register.schemas=false` means we never *write* to the registry at runtime, only read, which narrows the failure surface."

### BEHAVIORAL

**Q32. What was the hardest part?**
"Getting the latency contract right without sacrificing reliability — and being honest about where that line landed. The async, fire-and-forget design nails the <5ms overhead, but I learned in review that the unbounded pool and unhardened producer were quietly trading away durability and stability for that latency. The hard part was recognizing that the 'fast' version shipped, and articulating the concrete follow-ups (bounded pool, `acks=all`, DLQ) as the responsible next iteration rather than pretending it was already perfect."

**Q33. What are you proudest of?**
"The reuse judgment on tier 3. The lazy path was a Spring Boot consumer with hand-rolled GCS Parquet writing, offsets, retries, and DLQ. Instead I used Kafka Connect with the Lenses GCS connector and wrote ~75 lines of SMT for the only thing that was actually ours — geographic routing. That cut the code we own to almost nothing while getting battle-tested offset management, retries, and DLQ for free. Knowing what *not* to build is the senior move."

**Q34. What would you do differently?**
"Three things, in priority order: harden the producer (`acks=all`, `min.insync.replicas=2`, idempotence, retries); replace the unbounded `newCachedThreadPool` with a bounded pool + rejection metric so we shed gracefully and observably under burst; and mask sensitive headers (`WM_SEC.*`, `Authorization`) at capture so secrets never reach the audit store. None are big — they're the difference between 'works' and 'production-grade.'"

**Q35. How did you make this an org-wide standard?**
"By making adoption nearly free. The capture lives in a shared library — a service component-scans `com.walmart.dv.*`, provides a `WebClient` bean, and flips a CCM flag; no per-service Kafka or GCS code. The producer and sink are shared infrastructure. So onboarding a new service to audit is config, not code. That's what let it spread beyond NRTI as the default way DV CPerf services get audited."

---

## 5. Defending the numbers

| Claim | How it's measured / derived | What to say if pushed |
|---|---|---|
| **<5ms P99 latency impact** | It's the *added overhead on the audited API*, not audit end-to-end latency. The request thread only pays for: ContentCaching wrappers + building the payload + submitting a `Runnable` to a pool (Tier 1) and, on the producer, returning 204 before any Kafka work (Tier 2). Perf was validated with **Automaton/JMeter** load tests (the `perf/wcnp_stage_*vu_perf.json` profiles, ramping to ~25–50 virtual users, all asserting 204). The kitt readinessProbe exports `http_client_requests_seconds_*` to Prometheus, so the producer's own latency is observable. | "It's measured as the delta the filter adds, P99, under load. The async design means the only synchronous cost is body-caching and a pool submit — single-digit ms. I did **not** measure audit *end-to-end* freshness as 5ms; that's minutes because of the connector flush window. I'm careful about which latency I'm quoting." |
| **Processing millions of daily events / 2M+ events/day** | One audit record per audited API call. 2M/day ≈ **23 events/sec average**, with peaks higher. Times 3 on the consume side (3 connectors) ≈ 70 reads/sec. | "2M/day is ~23 msg/s average — comfortably within a single partition and one task per connector, which is exactly why `tasks.max=1` and the modest pod sizing (prod HPA 4–8 replicas at 60% CPU) are sufficient. It's 'millions of events,' not 'millions per second' — I won't oversell the throughput tier." |
| **SMT-based geographic routing (US/CA/MX)** | Verifiable in code: 3 connectors in `kc_config.yaml`, each with a `Filter{US|CA|MX}` SMT (`com.walmart.audit.log.sink.converter.*`) keyed on `wm-site-id`; 3 buckets in `env_properties.yaml`. | "Routing is literally a `Transformation<R>` that returns the record or null based on the `wm-site-id` header. US is the catch-all; CA/MX strict." |
| **GCS Parquet / BigQuery storage** | KCQL `STOREAS PARQUET ... PARTITIONBY service_name, _header.date, endpoint_name` into `wmt-dv-luminate-prod` buckets; BigQuery external tables over them. | "Parquet for columnar analytical scans; external tables so suppliers query in place with no second copy." |
| **Eliminating Splunk dependency** | Before: API audit data in Splunk (costly, not supplier-visible). After: queryable in BigQuery by suppliers. | "It's a cost + self-service win. I'd frame it qualitatively unless I have the exact Splunk-spend delta in front of me." |
| **Org-wide integration standard** | Capture is a shared Maven lib (`dv-api-common-libraries`, consumed at 0.0.61) adopted across DV CPerf services via component-scan + CCM flag. | "Adoption is config-only, which is why it became the default. I'll say 'across our DV CPerf services,' not literally every Walmart team." |

---

## 6. HONEST watch-outs

These are the things that bite if the interviewer opens the code. Pre-empt them; each becomes a "here's how I'd address it" that scores points.

1. **"Zero data loss" is not backed by config.** `KafkaProducerConfig` never sets `acks`, `enable.idempotence`, or `retries` → client defaults (`acks=1`). **Say:** "The durability config wasn't hardened; with `acks=1` we risk loss on leader failure. I'd set `acks=all` + `min.insync.replicas=2` + `enable.idempotence=true`." Do **not** claim zero loss.
2. **Unbounded `newCachedThreadPool()`.** No back-pressure, no rejection, OOM risk under burst. It is the *mechanism* behind <5ms **and** a stability liability. Own both sides; fix = bounded pool + rejection metric.
3. **Send is fire-and-forget with a log-only catch, and `send()` is async** — a broker-side failure won't even throw synchronously. The caller (and supplier) never learn of a failed publish. Fix = future callback + app DLQ + metric.
4. **`kafkaSecondaryTemplate` is dead code.** Built and autowired, never sent through. The real in-code primary→secondary failover is in `cp-nrti-apis`, not here. Attribute failover correctly.
5. **The sink is NOT Spring Boot.** It's a Kafka Connect SMT plugin JAR on the KCaaS base image (no `main()`, no `Application`, no api-spec). If your notes or doc 01 say "Spring Boot," correct it.
6. **CA/MX Javadoc lies.** `AuditLogSinkCAFilter`/`MXFilter` Javadoc says "or if the header is missing," but the code inherits the **strict** base (missing → dropped). Only `AuditLogSinkUSFilter` actually implements the missing-header catch-all. Know the code, not the comment.
7. **Unmasked sensitive headers.** The body `headers` field can carry `WM_SEC.*`/`Authorization` because the upstream capture copies all headers with no masking. A real PII/secret-leak in the audit store. Raise it before they find it.
8. **3× read amplification** is a real cost, not an accident. Frame it as a deliberate isolation/operability trade-off, with "single branching connector" as the 10× alternative.
9. **`AppUtil.addingHeaders` hardcodes `WM-Site-Id=US`** as a default before merging real headers — another reason header-less records bias to US. Minor, but be ready.
10. **Version drift in artifacts.** Shield report shows `spring-boot-starter-web 3.2.8`; the pom parent is `3.5.12` (effective Spring Boot 3.5.x). If asked "what version," say "parent 3.5.12 / Java 17; the shield report is an older snapshot." `kafka-avro-serializer 5.5.0`, `avro 1.11.4`.
11. **Local-path leakage in non-prod config** (`/Users/wmUserId/Downloads/Devkafkacerts/gcskey.json` in `env_properties.yaml` dev block) — non-prod placeholder, but looks like leftover local config. Prod uses `secret.ref://gcs_key.json`.

---

## 7. Follow-up rabbit holes

**RH1. "Why epoch-second timestamps in capture but `created_ts` in millis in the producer?"**
"Capture records `request_ts`/`response_ts` as `Instant.now().getEpochSecond()` (seconds), while `AvroUtils` sets `created_ts = System.currentTimeMillis()` (millis). It's a mild unit inconsistency. For latency you'd want sub-second precision, so I'd standardize on millis (or micros) end-to-end. The `_header.date` used for partitioning is GMT `yyyy-MM-dd`, derived separately by the Lenses SMT, so partitioning is unaffected."

**RH2. "Could you compute request latency from the record?"**
"`response_ts - request_ts` gives served-time, but at second granularity it's coarse and `request_size_bytes`/`response_size_bytes` in the common lib are computed from `toString().getBytes().length` of the wrapper objects — effectively meaningless. So I trust timestamps and codes for debugging, not the size fields, and I'd fix the size computation to read actual body lengths."

**RH3. "Why one task per connector — isn't that a throughput cap?"**
"At ~23 msg/s it's not a cap; one task keeps Parquet batching simple and avoids cross-task file contention. The lever for scale is `tasks.max` (≤ partition count) — I'd raise it with partitions if volume grew."

**RH4. "What ordering guarantees does the supplier see in BigQuery?"**
"Within a partition (one service+endpoint), Kafka preserves order, but the GCS files are flushed in batches and BigQuery doesn't guarantee row order on scan — so suppliers should order by `request_ts`/`created_ts` in their query. I don't promise physical ordering in the store."

**RH5. "Why not Kafka Streams for routing instead of SMTs?"**
"Overkill. Routing is a stateless per-record filter on a header — exactly what an SMT is for. Kafka Streams would add a stateful app to run, deploy, and monitor for zero benefit here. SMT keeps the routing colocated with the sink and stateless."

**RH6. "How do BigQuery external tables stay in sync with new Parquet files?"**
"External tables over a GCS prefix pick up new objects automatically on query (no reload), with partition pruning on the `service_name/date/endpoint` path. The trade-off vs native BQ is slightly slower scans and you manage partition layout yourself — fine for append-only audit data, and it avoids a second ingestion pipeline."

**RH7. "Retention — how long does the topic hold data, and why does it matter?"**
"Topic retention is the recovery window for the sink: as long as a GCS/connector outage is shorter than retention, we replay and lose nothing. So retention should comfortably exceed worst-case sink downtime. It's also the replay window if I ever need to rebuild a bucket from Kafka."

**RH8. "What's the consumer lag story / how do you know the sink is healthy?"**
"Each connector is its own consumer group, so I monitor per-connector lag and the Connect REST `/connectors/{name}/status` (it's the startupProbe). Rising lag on one country connector isolates the problem to that bucket/region — a direct payoff of the 3-connector isolation choice."

---

## 8. One-paragraph + 30-second pitch

**One paragraph (written):**
I designed a three-tier asynchronous audit pipeline — capture, produce, sink — that records every supplier API call to Walmart Data Ventures' Luminate Channel Performance services. A shared library captures request/response in a servlet filter and `@Async`-POSTs it to `audit-api-logs-srv`, which returns HTTP 204 immediately and then, on a background pool, serializes the record to Avro and publishes it to the Kafka topic `api_logs_audit_prod` with key `service_name/endpoint_name` and a `wm-site-id` routing header, using Confluent Schema Registry with `auto.register.schemas=false` for governed evolution. The consumer side is Kafka Connect with three Lenses GCS sink connectors (US/CA/MX), each running a Single Message Transform that filters by `wm-site-id` and writes Parquet, partitioned by service/date/endpoint, into a per-country GCS bucket that BigQuery external tables expose for supplier self-service. The async design keeps the latency overhead on the audited API in the single-digit-millisecond range; the geographic SMT routing satisfies data residency; and Parquet-on-GCS-plus-BigQuery replaced an expensive, non-self-service Splunk dependency. The honest next iterations are hardening producer durability (`acks=all`, idempotence), replacing an unbounded thread pool with a bounded one, and masking sensitive headers — all small, high-leverage fixes I can speak to in detail.

**30-second verbal:**
"It's a three-tier audit pipeline: a shared library captures every API call and async-POSTs it; `audit-api-logs-srv` returns 204 instantly, then publishes an Avro record to Kafka keyed by service and endpoint with a country header; and Kafka Connect runs three GCS sink connectors — US, CA, MX — each with a Single Message Transform that filters by that header and writes Parquet to a per-country bucket, with BigQuery on top so suppliers self-serve. Async design keeps the latency overhead tiny, SMT routing handles data residency, and it got us off Splunk. The honest follow-ups are hardening producer durability and bounding the thread pool — I can walk through exactly how."
