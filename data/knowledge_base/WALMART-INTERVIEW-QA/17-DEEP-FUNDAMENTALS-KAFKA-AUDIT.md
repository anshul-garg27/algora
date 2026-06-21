# 17 — Deep Fundamentals: Kafka Audit Project Internals

> **Purpose:** The "how does Kafka actually work, byte by byte" layer for the **audit logging** bullet (`audit-api-logs-srv` producer + `audit-api-logs-gcs-sink` Kafka-Connect sink). Pairs with `16` (Spring/concurrency), `11` (Walmart platform), `06` (Kafka master deep-dive), and `18` (NRTI). This is where you prove you understand Kafka the *system* — Avro wire format, partitioning math, the producer's internal threads, consumer-group rebalancing, Connect's offset machinery — **all tied to the actual audit config**, not a textbook default.

---

## ⚠️ SCOPE GUARD — READ THIS FIRST (do not get caught)

This document describes the **AUDIT producer**, which is **deliberately under-tuned**:

- It sets **only 5 properties** (`bootstrap`, key serializer, value serializer, schema-registry URL, `auto.register.schemas=false`) plus a conditional SSL block — `KafkaProducerConfig.populateConfigProperties` (`audit-api-logs-srv/.../kafka/KafkaProducerConfig.java:85-118`).
- It sets **NO** `acks`, `enable.idempotence`, `retries`, `linger.ms`, `batch.size`, or `compression.type` → **all Kafka client defaults apply → effective `acks=1`**, no batching tuning, no compression.
- The send is **fire-and-forget**: `kafkaPrimaryTemplate.send(kafkaMessage)` with the returned future **discarded entirely** (`KafkaProducerService.java:47`). There is **no `.thenAccept`, no `.exceptionally`, no failover**. `kafkaSecondaryTemplate` exists (`KafkaProducerConfig.java:60-63`) but is **dead code** — nothing in `audit-api-logs-srv` calls it.

> **The NRTI producer is a different service** (`cp-nrti-apis`, covered in doc `18`/`06`). NRTI sets `acks=all`, `retries=10`, `lz4`, `linger.ms=20`, `batch.size=8192`, `request.timeout.ms=300000`, and runs a real `.exceptionally` dual-region failover. **Do NOT attribute any of that to the audit producer.** Every NRTI fact in this doc is explicitly tagged "NRTI, not audit."

If an interviewer opens `KafkaProducerConfig.java` and you've claimed `acks=all` + lz4 + failover for audit, you're caught. So we describe what the code actually does and frame the under-tuning as a deliberate best-effort design for telemetry.

---

## PART 1 — THE PRODUCER, INTERNALLY

### 1.1 The full audit send path, with citations

The audited service never calls Kafka directly — it `POST`s to this service, which captures the log asynchronously. The hop chain is:

```
audited API  ──POST /v1/logRequest (or saveApiLog)──▶  AuditLoggingController
   AuditLoggingController.saveApiLog (AuditLoggingController.java:58-61)
     → loggingRequestService.processLoggingRequest(...)
     → returns ResponseEntity<>(HttpStatus.NO_CONTENT)   // HTTP 204, IMMEDIATELY
         LoggingRequestService.processLoggingRequest (LoggingRequestService.java:34-43)
           → target = targetedResourcesFactory.getOrDefault("kafkaProducerService", null)
           → executorPoolService.executeTaskInThreadPool(() -> target.processRequestToTarget(req))
               ExecutorPoolService.pool = Executors.newCachedThreadPool()  // UNBOUNDED (ExecutorPoolService.java:10)
                 → KafkaProducerService.processRequestToTarget → publishMessageToTopic (KafkaProducerService.java:39-52)
                     → kafkaPrimaryTemplate.send(kafkaMessage)   // future DISCARDED (line 47)
```

Key facts, each grounded:

1. **The controller returns 204 before Kafka is touched.** `AuditLoggingController.saveApiLog` (`AuditLoggingController.java:58-61`) calls `processLoggingRequest` and returns `HttpStatus.NO_CONTENT`. The caller's latency is the cost of *handing off to a thread pool*, not of producing to Kafka. (The `<5ms P99` resume number is *this* overhead added to the audited API, **not** audit-data freshness.)

2. **The async hand-off uses an UNBOUNDED cached thread pool.** `ExecutorPoolService` (`ExecutorPoolService.java:10`) is literally `Executors.newCachedThreadPool()`. There is **no queue cap and no rejection policy** — under a burst it does **not drop**, it **grows threads unboundedly** (each new task with no idle thread spawns a new one). That's an **OOM / thread-exhaustion risk**, a *different* failure mode from a bounded-pool `AbortPolicy` drop. (The `AbortPolicy`, core 6 / max 10 / queue 100 pool lives in the **common JAR** Tier-1 capture filter `dv-api-common-libraries`, not here — see doc `16`. Keep the two tiers distinct.)

3. **The actual `send()` is bare fire-and-forget.** `KafkaProducerService.publishMessageToTopic` (`KafkaProducerService.java:44-52`):
   ```java
   try {
     log.info("sending kafka msg for trace id {} and request Id {}", ...);
     kafkaPrimaryTemplate.send(kafkaMessage);   // line 47 — return value ignored
   } catch (Exception ex) {
     log.info("sending kafka msg failed for {}", loggingApiRequest.getTraceId());
     log.info("Send failure falling into exception and Auditing", ex);
   }
   ```
   The `try/catch` only catches **synchronous** throws — serializer failures (schema not found, registry unreachable at serialize time) and partition-metadata lookup failures. It does **not** observe the asynchronous broker ack/error, because the returned `CompletableFuture`/`ListenableFuture` is never retained. So an **async** failure (leader down after buffering, request timeout) is **invisible** to this service.

### 1.2 What `kafkaPrimaryTemplate.send(msg)` does inside the Kafka producer

`send()` does **not** synchronously hit the broker. Inside the `KafkaProducer`:

1. **Serialize** — key via `StringSerializer`, value via `KafkaAvroSerializer` (`KafkaProducerConfig.java:89-90`). The value becomes the Confluent Avro wire bytes (§2.1). Serialization is **synchronous on the calling thread** — this is the one place a failure surfaces inside the `catch` block.
2. **Partition** — the default `Partitioner` hashes the key (§1.4). The audit key is always non-null (§1.3), so placement is deterministic.
3. **Append to the RecordAccumulator** — the record is buffered into an in-memory **batch** keyed by partition. This is why `send()` returns a future immediately rather than blocking on the network.
4. **The `Sender` I/O thread** (`kafka-producer-network-thread`, one per producer instance) drains ready batches and ships them to brokers. Because audit sets **no `linger.ms`**, the client default applies (`linger.ms=0`) → the Sender sends a partition's batch **as soon as it can**, with effectively no deliberate accumulation window. Because audit sets **no `batch.size`** tuning, the default 16 KB applies. Because audit sets **no `compression.type`**, batches go **uncompressed** (`none`).
5. The broker acks per the **effective `acks=1`** (default — audit never sets it). With `acks=1` the **leader** appends to its log and acks **before** replication to followers. The future completes on the Sender thread — **but audit discards that future, so nothing in `audit-api-logs-srv` ever observes the completion.**

**The two-thread mental model (still correct, re-anchored):** there are two threads — the **app thread** (here, an *unbounded-cached-pool worker*, **not** Tomcat, because the controller already returned 204) which calls `send()` and gets a future; and the producer's single **Sender thread** doing the network I/O. The novel audit-specific twist: **because the future is discarded, the completion thread does no application work at all.** That *is* the design — best-effort telemetry.

**What `send()` does NOT do here (memorize this list):**
- No future handling (`.thenAccept`/`.whenComplete`/`get()`).
- No failover to a secondary template (the bean exists but is dead code).
- No producer-side `acks`/`retries`/`idempotence` tuning → defaults (`acks=1`, `retries=2147483647` *by client default in modern clients but bounded by `delivery.timeout.ms`*, idempotence off unless the client auto-enables it; the point is **the app set none of it**).
- No `linger.ms`/`batch.size`/`compression.type` → defaults (0 / 16 KB / none).

### 1.3 The partition key — `serviceName/endpoint`, cited

The key is built in `AuditKafkaPayloadKey.getKafkaKey` (`AuditKafkaPayloadKey.java:26-28`):
```java
public static String getKafkaKey(AuditKafkaPayloadKey auditKafkaPayloadKey) {
  return auditKafkaPayloadKey.getServiceName()
       + AppConstants.FORWARD_SLASH      // "/"
       + auditKafkaPayloadKey.getEndpoint();
}
```
and set onto the message in `KafkaProducerService.setHeaders` (`KafkaProducerService.java:88-89`):
```java
logEventMessageBuilder.setHeader(KafkaHeaders.TOPIC, auditLoggingTopicName)
    .setHeader(KafkaHeaders.KEY, AuditKafkaPayloadKey.getKafkaKey(kafkaMessageBodyKey));
```

So the key is genuinely `KafkaHeaders.KEY` (the actual partition key), e.g. `NRT/transactionHistory`. Three consequences:

- **Ordering per endpoint:** all records for one `service/endpoint` hash to one partition → per-endpoint ordering preserved (Kafka orders only within a partition).
- **Grouping + query locality:** it aligns with the sink's `PARTITIONBY service_name, _header.date, endpoint_name` (`env_properties.yaml:225` etc.) — the stream's natural partition key and the Parquet/BigQuery layout match, so supplier self-service queries that filter by service+endpoint hit a small set of GCS prefixes.
- **String key on the read side:** the sink's `key.converter` is `org.apache.kafka.connect.storage.StringConverter` (`kc_config.yaml:7`), so the key is read back as a plain String downstream — consistent with `StringSerializer` on the produce side.

**Contrast with NRTI IAC (a teaching contrast, not audit behavior):** NRTI's IAC path sets `MESSAGE_ID` only as a **header** (`setHeader`), **not** `KafkaHeaders.KEY` → IAC records have a **NULL partition key** → **no broker-level ordering** (sticky/round-robin placement). Only NRTI's DSC path keys on `tripId`. So "every Walmart topic I touched is keyed" is false — IAC is the counterexample, and it's worth naming to show you actually read the code.

**The hot-partition trap (great follow-up):** if one service/endpoint dominates traffic (say a supplier hammering `transactionHistory`), its partition gets hot while others idle → that partition's sink task backs up while others are idle. Mitigation without losing grouping: composite key `service/endpoint/consumerId` or a bounded salt suffix — you keep endpoint-level grouping but spread the hot endpoint across N partitions, trading strict per-endpoint ordering for per-`(endpoint,consumer)` ordering (acceptable for audit since each record is independent). Bad alternatives: `trace_id` (perfect spread, zero grouping); `wm-site-id` (only 3 values → 3 hot partitions).

### 1.4 Partitioning math + ordering, precisely

- Partition = `murmur2(keyBytes) % numPartitions` for a non-null key (the default partitioner). Audit always has a non-null key (§1.3), so placement is deterministic.
- **Null key** → sticky partitioning (batches to one partition until it fills, then rotates) in modern clients; round-robin in older ones. (This is the IAC case, **not** audit.)
- **Ordering is per-partition only.** With `retries>0` **and** `max.in.flight.requests.per.connection>1` **and** `enable.idempotence=false`, a retried batch can land **after** a later batch → reordering within a partition. For **audit** this is moot in practice because the produce volume per partition is modest and the app doesn't even observe failures — but the honest statement is "audit uses client defaults; idempotence is not explicitly enabled, so I would not *claim* in-partition exactly-once on the produce side."

### 1.5 The CCM-declared-but-unread trap (a standout "I audited my own config" point)

The producer's config comes from a Strati `@ManagedConfiguration` interface, `AuditLogsKafkaCCMConfig` (`audit-api-logs-srv/.../common/config/AuditLogsKafkaCCMConfig.java`). That interface exposes **only**:
```java
List<String> getAuditKafkaPrimaryBrokerUrls();     // line 26
List<String> getAuditKafkaSecondaryBrokerUrls();   // line 33
String       getAuditLoggingKafkaTopicName();      // line 40
String       getSchemaRegistryUrls();              // line 47
Boolean      getAuditLoggingKafkaSslEnabled();     // line 54
```
There is **no getter for `acks`, `idempotence`, `retries`, `linger`, `batch`, or `compression`.** So **even if** a CCM yml file *declared* `acks=all`, nothing reads it into the producer map — `populateConfigProperties` only ever consults these five getters (`KafkaProducerConfig.java:87-94`). This is the deepest "I read my own config carefully" point: a declared value that no code path consumes is a no-op, and the effective producer config is exactly the 5 properties plus optional SSL.

> **Interview line:** "I verified the producer config two ways — the put-calls in `KafkaProducerConfig`, and the CCM interface that backs them. The interface has no acks getter, so even a YAML that declared acks wouldn't take effect. The effective producer is `acks=1` by default, by omission, not by a tuned choice. I'd call that out and propose `acks=all` + `min.insync.replicas=2` + `enable.idempotence=true` if the durability bar moved."

### 1.6 The conditional SSL block — why it's usually a no-op

`populateConfigProperties` adds a full JKS truststore/keystore SSL block **only if** `getAuditLoggingKafkaSslEnabled()` is true (`KafkaProducerConfig.java:94-118`). In our mesh, **mTLS is enforced at the Istio sidecar**, so client-side SSL is typically **disabled** and traffic to the broker is PLAINTEXT *from the app's point of view* (the sidecar wraps it). The `else` branch even logs `"mTLS is enforced for Kafka connections."` (line 117). The sink confirms the same posture: `security.protocol: PLAINTEXT` (`kc_config.yaml:14,23,32`).

---

## PART 2 — AVRO & SCHEMA REGISTRY, ON THE WIRE

### 2.1 What an audit Avro value actually looks like (byte-level)

The value serializer is `KafkaAvroSerializer` (`KafkaProducerConfig.java:90`). A Confluent Avro-serialized value is **NOT** self-describing JSON. The bytes are:
```
[ 0x00 ][ 4-byte schema ID (big-endian int) ][ Avro binary payload ]
  magic      Schema Registry ID                 values in schema order, no field names
```
- **Magic byte** `0x00` (1 byte) = Confluent wire-format version.
- **Schema ID** (4 bytes) = integer pointing to the exact writer schema in the Schema Registry.
- **Payload** = Avro **binary** encoding — no field names, just values **in schema declaration order** (that's why it's far smaller than JSON, which repeats every field name as text).

On the read side the sink's `value.converter` is `io.confluent.connect.avro.AvroConverter` with `value.converter.schemas.enable: true` (`kc_config.yaml:8-9`), pointed at `value.converter.schema.registry.url` (prod: `http://schema-registry-service.prod.schema-registry.ms-df-streaming.prod.walmart.com`, `env_properties.yaml:93,120`). The converter reads the 4-byte ID, fetches+caches the writer schema, and reconstructs the `LogEvent`.

### 2.2 `auto.register.schemas=false` — real, cited, and why it matters

`KafkaProducerConfig.java:92` puts:
```java
configProps.put(AUTO_GENERATED_CONSTANT, false);   // == "auto.register.schemas"
```
with the registry URL from CCM (`getSchemaRegistryUrls()`, `KafkaProducerConfig.java:91`; prod default `https://intelligent-sync-schema-registry-prod.streaming-csr.k8s.glb.us.walmart.net`, `audit-api-logs-srv/ccm/PROD-1.0-ccm.yml:45-46`).

- With `auto.register=true`, the serializer would register the schema on the fly and cache the returned ID. With **`false`**, the schema **must already be registered** (done in a controlled CI step) → the serializer only **looks up** the ID for the schema it's about to write.
- **Why `false` is safer:** it prevents a buggy or rushed producer from silently registering an **incompatible** schema version in production. Schema changes are gated by the registry's compatibility check at registration time (CI), not at runtime.
- **Failure mode (honest gap):** if the schema isn't registered, or the registry is unreachable at serialize time, `KafkaAvroSerializer` **throws synchronously** → caught by `KafkaProducerService` (`KafkaProducerService.java:48`) → **logged only** → that audit record is **lost** (no producer-side DLQ). Mitigation I'd add: a local schema-ID cache (the client already caches per-ID, but pre-warming helps) plus a `serialize_failure` counter and alert.

### 2.3 The real schema: `log.avsc` (`LogEvent`, 19 fields)

`audit-api-logs-srv/src/main/resources/avro/log.avsc` defines `record LogEvent`, namespace `com.walmart.dv.audit.model.api_log_events`. Required vs optional matters for evolution:

| Field | Avro type | Req/Opt |
|---|---|---|
| `source_request_id` | `string` | **required** |
| `endpoint_path` | `string` | **required** |
| `method` | `string` | **required** |
| `response_code` | `int` | **required** |
| `consumer_id` | `string` | **required** |
| `request_ts` | `long` | **required** |
| `response_ts` | `long` | **required** |
| `created_ts` | `long` | **required** |
| `endpoint_name` | `string` | **required** |
| `service_name` | `string` | **required** |
| `api_version` | `["null","string"]` default `null` | optional |
| `trace_id` | `["null","string"]` default `null` | optional |
| `supplier_company` | `["null","string"]` default `null` | optional |
| `request_body` | `["null","string"]` default `null` | optional |
| `response_body` | `["null","string"]` default `null` | optional |
| `error_reason` | `["null","string"]` default `null` | optional |
| `request_size_bytes` | `["null","int"]` default `null` | optional |
| `response_size_bytes` | `["null","int"]` default `null` | optional |
| `headers` | `["null","string"]` default `null` | optional |

This grounds the BACKWARD-compat argument concretely: the **future-proof** way to extend this schema is to add another `["null", X]`-with-`default:null` optional field — exactly the shape the 9 optional fields already use.

### 2.4 How `LogEvent` is populated — `AvroUtils.getLogEvent`, cited

`AvroUtils.getLogEvent` (`AvroUtils.java:16-44`) is where the wire record is built. Three behaviors worth knowing cold:

1. **`headers` is one JSON string, not a map** (`AvroUtils.java:42` + `getJsonString` lines 46-49):
   ```java
   .setHeaders(getJsonString(loggingApiRequest.getHeaders()))
   ...
   ObjectWriter objectWriter = new ObjectMapper().writer().withDefaultPrettyPrinter();
   return objectWriter.writeValueAsString(value);
   ```
   The entire HTTP header map is serialized to a **single pretty-printed JSON string** that rides in the one Avro `headers` field. **PII/secret-leak implication:** whatever headers were captured (potentially `WM_SEC.*` / `Authorization` when the upstream common-JAR filter has masking off, `mask.enable=false`) land verbatim in that string, then in Parquet, then queryable in BigQuery. This is the audit-side surface of the common-JAR unmasked-header leak (doc `16`). Honest line: "the producer faithfully serializes whatever the capture filter handed it; the masking gap is upstream, but it surfaces here in cleartext at rest."

2. **`created_ts` is producer-side wall-clock, not event time** (`AvroUtils.java:39`):
   ```java
   .setCreatedTs(System.currentTimeMillis())
   ```
   So `created_ts` = "when this audit service built the record," **not** when the audited request happened. The actual request/response times are `request_ts`/`response_ts` (passed in by the caller). If asked "is `created_ts` event time?" — **no**, it's ingestion time at the audit service; use `request_ts` for event-time analytics.

3. **`consumer_id` defaults to `"NA"`** when the `wm_consumer.id` header is absent (`AvroUtils.java:51-57`). Since `consumer_id` is a **required** Avro field, it can never be null — the `"NA"` sentinel keeps the required-string contract satisfied. Request/response bodies are `.toString()`'d (lines 27-30) and may be null → they map to the optional `["null","string"]` body fields.

### 2.5 Schema evolution & compatibility modes (grounded in `log.avsc`)

- **BACKWARD** (the right default here): a **new** schema can read **old** data. You may **add an optional field with a default** (e.g. another `["null","string"]` default `null`, exactly like `trace_id`) and **remove** a field. You may **not** add a *required* field. → upgrade **consumers first**.
- **FORWARD**: **old** schema reads **new** data → you may add a required field / remove an optional one → upgrade **producers first**.
- **FULL**: both directions.
- **Schema resolution:** the reader uses the **writer's** schema (from the embedded 4-byte ID) reconciled against the **reader's** schema by **field name + defaults**. That's how a consumer compiled against v1 reads bytes written with v2 — missing fields fall back to their declared `default`.

> **Interview line:** "Because the data lands in long-lived Parquet/BigQuery, BACKWARD is the correct compatibility mode. To add a field — say `region` — I add `{\"name\":\"region\",\"type\":[\"null\",\"string\"],\"default\":null}`, register it through CI where the registry enforces compatibility, and old readers plus all existing Parquet stay valid. With `auto.register.schemas=false`, an incompatible change fails in CI, never in prod."

### 2.6 Why Avro → Parquet is a natural pairing

- **Avro = row-oriented** binary — ideal on the wire / streaming, one record at a time, compact, schema-evolvable.
- **Parquet = column-oriented** — ideal at rest for analytics: read only the columns a query touches, strong columnar compression, predicate pushdown.
- The Lenses GCS sink's KCQL says `STOREAS PARQUET` (`env_properties.yaml:226` etc.), converting the Avro stream into batched Parquet objects; BigQuery external tables then do columnar scans over the GCS buckets. Right tool at each stage: Avro on the wire, Parquet at rest.

---

## PART 3 — THE CONSUMER / KAFKA CONNECT SINK

> The sink is **not Spring** — it's **Kafka Connect distributed mode** running the Lenses `io.lenses.streamreactor.connect.gcp.storage.sink.GCPStorageSinkConnector` on Walmart's KCaaS base image. `kc_config.yaml` defines **three connector instances**, and `env_properties.yaml` supplies per-env/per-region config.

### 3.1 Worker-cluster `group.id` vs per-connector consumer group (the 3× mechanism, precisely)

There are **two different "group" concepts**, and the imprecise version of this gets corrected fast in an interview:

- **`group.id: kcaas-audit-logs-gcs-sink-connector`** (`env_properties.yaml:30, 58, 86, 113, 140`) is the **Connect WORKER-cluster group id** — the distributed-mode cluster coordination group, **shared by all three connectors**. It's *not* a sink consumer group. (The same file even warns: "used in forming the Connect cluster group … must not conflict with consumer group IDs.")
- Each **connector** (`audit-log-gcs-sink-connector`, `-ca`, `-mx`) gets its **own sink consumer group**, named `connect-<connectorName>` by Connect. **Three connectors ⇒ three independent sink consumer groups ⇒ each reads the *whole* topic independently ⇒ 3× read amplification.**

So the **3× conclusion is right**, but the mechanism is "three connectors each with their own `connect-<name>` consumer group," **not** "three distinct worker `group.id`s."

- **Internal storage topics:** prod uses `api_logs_audit_prod-prod-{config,offset,status}` (`env_properties.yaml:115-117`); stage uses `api_logs_audit_stg-{config,offset,status}` (`env_properties.yaml:32-34`). These hold connector configs, committed offsets, and task status for distributed mode.

### 3.2 The three-connector geo-routing layout (US permissive, CA/MX strict)

From `kc_config.yaml:63-115`, all three connectors share `tasks.max: 1`, `errors.tolerance: all`, the GCS error policy, and the SMT pattern `InsertRollingRecordTimestamp, Filter<CC>`:

| Connector | SMT filter | Filter behavior | Prod bucket (`env_properties.yaml`) |
|---|---|---|---|
| `audit-log-gcs-sink-connector` (US) | `AuditLogSinkUSFilter` (line 76) | **permissive** — passes matching `wm-site-id` **OR header-less** | `audit-api-logs-us-prod` (line 222) |
| `audit-log-gcs-sink-connector-ca` | `AuditLogSinkCAFilter` (line 94) | **strict** — drops header-less | `audit-api-logs-ca-prod` (line 341) |
| `audit-log-gcs-sink-connector-mx` | `AuditLogSinkMXFilter` (line 112) | **strict** — drops header-less | `audit-api-logs-mx-prod` (line 460) |

GCP project for all three: `wmt-dv-luminate-prod` (`env_properties.yaml:232` etc.). BigQuery external tables sit over each bucket.

### 3.3 SMTs run in the worker, per record — order matters

SMTs run **inside the Connect worker, on the task thread, one record at a time, between consume and the converter's write.** The chain is **ordered** (`kc_config.yaml:75`): `transforms: InsertRollingRecordTimestamp, FilterUS` — so:

1. **`InsertRollingRecordTimestamp` runs FIRST** (`io.lenses.connect.smt.header.InsertRollingRecordTimestampHeaders`, `kc_config.yaml:77-79`): `date.format: "yyyy-MM-dd"`, `timezone: GMT`. It writes a `_header.date` value (today's GMT date) onto the record. **This is the field `PARTITIONBY service_name, _header.date, endpoint_name` later uses** to build the daily GCS path — so the order is load-bearing: filter-then-partition needs the date header to already exist.
2. **`Filter<CC>` runs SECOND**: the SMT contract is **return the record to keep it, return `null` to drop it**. That's how geo-routing happens with zero custom consumer code.

### 3.4 `verifyHeader` — fail-closed, parallel stream, and the US permissive override

The strict base (`BaseAuditLogSinkFilter.verifyHeader`, `BaseAuditLogSinkFilter.java:52-63`):
```java
public boolean verifyHeader(R r) {
  try {
    return StreamSupport.stream(r.headers().spliterator(), true)   // parallel stream
        .anyMatch(header -> HEADER_NAME.equals(header.key())       // "wm-site-id"
            && StringUtils.equals(getHeaderValue(), String.valueOf(header.value())));
  } catch (Exception e) {
    log.error("Failed in BaseAuditLogSinkFilter ...", ...);
  }
  return false;   // FAIL-CLOSED: any exception ⇒ drop
}
```
- **Strict (CA via `AuditLogSinkCAFilter`, MX via `AuditLogSinkMXFilter`):** keep **only** records whose `wm-site-id` equals this country's site id; **drop header-less records.** (CA/MX are one-line subclasses overriding only `getHeaderValue()` — `AuditLogSinkCAFilter.java:23-26`.)
- **Permissive (US via `AuditLogSinkUSFilter.verifyHeader`, `AuditLogSinkUSFilter.java:42-56`):** keep records that match the US site id **OR** that have **no `wm-site-id` header at all**:
  ```java
  return StreamSupport.stream(r.headers().spliterator(), true)
            .anyMatch(h -> HEADER_NAME.equals(h.key())
                 && StringUtils.equals(getHeaderValue(), String.valueOf(h.value())))
         ||
         StreamSupport.stream(r.headers().spliterator(), true)
            .noneMatch(h -> HEADER_NAME.equals(h.key()));   // header-less ⇒ pass (US catch-all)
  ```
  **So header-less records land ONLY in the US bucket.** That's a deliberate residency catch-all: anything without an explicit site-id is treated as US.
- **The Javadoc lies for CA/MX:** their class docs say "or if the header is missing," but they inherit the **strict** base that **drops** header-less records — only US actually overrides to be permissive. (Great "docs vs code" honesty point: I'd fix the CA/MX Javadoc.)
- **Fail-closed + parallel stream:** any exception during header inspection returns `false` → the record is dropped, not retried in-SMT. The stream is parallel (`spliterator(), true`); for the tiny header set this is negligible but technically spins up the common ForkJoinPool.

Site-id strings come from `AuditApiLogsGcsSinkPropertiesUtil.getSiteIdForCountryCode` (`AuditApiLogsGcsSinkPropertiesUtil.java:42-45`), which reads `WM_SITE_ID_FOR_<CC>` from a properties file chosen by the `STRATI_RCTX_ENVIRONMENT_TYPE` env var (`...PropertiesUtil.java:28-32`). Prod values (`audit_api_logs_gcs_sink_prod_properties.yaml:1-3`):
```
WM_SITE_ID_FOR_US=1704989259133687000
WM_SITE_ID_FOR_MX=1704989390144984000
WM_SITE_ID_FOR_CA=1704989474816248000
```

### 3.5 Offset management = at-least-once on the sink

- Connect commits consumer offsets **after** a successful flush to GCS. If a worker crashes **between** the GCS flush and the offset commit, on restart it re-reads from the last committed offset → **duplicate Parquet objects/rows possible** → **at-least-once**. Dedup is downstream (BigQuery on `source_request_id`) or via deterministic object naming.
- `consumer.max.poll.records: 50` (`kc_config.yaml:49`), `consumer.max.poll.interval.ms: 300000` (line 50) → the task must process a poll batch within **5 minutes** or the broker considers it dead and triggers a rebalance. Flushes must stay under that.

### 3.6 Two retry layers — do NOT conflate them

There are **two distinct error/retry mechanisms**, and merging them is a common slip:

1. **GCS-write retry (storage layer):** `connect.gcpstorage.error.policy: RETRY`, `connect.gcpstorage.max.retries: 5`, `connect.gcpstorage.retry.interval: 5000` (`kc_config.yaml:71-73`). This retries the **GCS object write** up to 5× with a 5 s interval — it is **not** Kafka producer/consumer retries.
2. **Connect-native error tolerance + DLQ:** `errors.tolerance: all` (`kc_config.yaml:69`) + `errors.deadletterqueue.context.headers.enable: true` (line 70). The DLQ topic is `api_logs_audit_prod_DLQ` (`env_properties.yaml:220, 243`). This is what routes a **poison record** (e.g. one the converter/SMT can't process) to the DLQ so the connector keeps moving.

So: a **GCS write** that keeps failing is retried by the **error policy** (5×); a **bad record** is tolerated and sent to the **DLQ** by `errors.tolerance=all`. Alert on DLQ depth, inspect, fix, replay.

### 3.7 Rebalancing & the assignor caveat

- If a task/worker joins or leaves, the group **rebalances** (reassigns partitions); during a stop-the-world rebalance, consumption pauses.
- `consumer.session.timeout.ms: 15000` + `consumer.heartbeat.interval.ms: 5000` (`kc_config.yaml:51-52`) → if heartbeats stop for 15 s, the member is evicted → rebalance. `consumer.request.timeout.ms: 60000` (line 53).
- **Assignor caveat (corrected):** the `partition.assignment.strategy` line is **commented out** (`kc_config.yaml:55-56`), so it is **not explicitly configured** — the client default applies (`[RangeAssignor, CooperativeStickyAssignor]`). Don't claim "we deliberately use CooperativeStickyAssignor"; the truthful version is "we left it at the default, which includes the cooperative (incremental) assignor." With `tasks.max: 1` per connector, within-connector rebalances are trivial anyway.

### 3.8 Flush / landing facts (prod, cited) + the dev footnote

Prod KCQL `PROPERTIES` block (`env_properties.yaml:226-231` US-eus2, mirrored in all prod blocks):
```
STOREAS PARQUET PROPERTIES(
  'flush.size'   = '50000000',   # 50 MB
  'flush.count'  = '5000',       # 5000 records
  'flush.interval' = '600',      # 600 seconds = 10 minutes
  'key.suffix'   = '_eus2'       # or '_scus' in the SCUS region (line 230 vs 253)
);
PARTITIONBY service_name, _header.date, endpoint_name
INSERT INTO `audit-api-logs-us-prod:...` / `...-ca-prod:...` / `...-mx-prod:...`
gcp.project.id = wmt-dv-luminate-prod
```
**A file flushes on whichever of {50 MB, 5000 records, 600 s} hits first.** The **600 s interval is the dominant freshness ceiling** at low/moderate volume.

> **Dev footnote:** the `dev` block (`env_properties.yaml:159-162`) uses `flush.size=5242880` (**5 MB**) and **omits `flush.count`** entirely — a dev/stage-vs-prod difference. So "5 MB / 600 s, no record-count trigger" in dev vs "50 MB / 5000 / 600 s" in stage+prod. Worth a footnote if asked about environment parity.

---

## PART 4 — DELIVERY SEMANTICS, END TO END (AUDIT-SPECIFIC, HONEST)

### 4.1 Trace one audit record's guarantees (corrected mechanisms)

```
1. Capture hand-off (unbounded cached pool)            → ExecutorPoolService.java:10
     newCachedThreadPool: grows threads unboundedly under burst
     → failure mode is OOM/thread-exhaustion, NOT a clean drop
2. Produce (effective acks=1, future discarded)         → KafkaProducerService.java:47
     leader acks before replication → thin LOSS window on leader failure
     caller already got HTTP 204 → loss is invisible upstream
3. Topic (RF≈3, but acks=1 doesn't WAIT for it)         → see 4.4
     RF3 protects only AFTER the leader replicates; acks=1 doesn't guarantee
     replication at ack time
4. Connect sink (at-least-once, commit-after-flush)     → 3.5
     crash mid-flush re-delivers → DUPLICATE Parquet rows possible
5. GCS Parquet → BigQuery                                → durable at rest; dedupe at query
```

**The two weakest links are the first two hops:** the unbounded-pool capture (exhaustion risk) and the near-`acks=1` produce (thin loss window). The third+fourth hops can *duplicate* (at-least-once), not lose. So the honest end-to-end label is **"mostly-once with a thin loss window and possible GCS duplicates"** — **not** zero-loss, **not** exactly-once.

### 4.2 The three semantics, defined crisply (and where audit actually sits)

- **At-most-once:** fire-and-forget, no waiting → may lose, never duplicates. The **audit produce hop** leans here (`acks=1`, future discarded).
- **At-least-once:** commit/ack after process, with retries → never loses an *acked* record, may duplicate. The **audit Connect sink** is here (commit-after-flush).
- **Exactly-once:** idempotent producer + transactions (+ `read_committed` consumers) → neither lose nor duplicate. **Audit does NOT have this** — be explicit.

Net for audit: **produce ≈ at-most-once (loss-leaning)** stacked with **sink = at-least-once (dup-leaning)** → "mostly-once + thin loss + possible dupes." Dedupe in BigQuery on `source_request_id`.

### 4.3 Why exactly-once wasn't used (defensible trade, not a shortcut)

- EOS needs `enable.idempotence=true` (producer-id + sequence numbers) **and** a transactional producer (`transactional.id`) **and** `read_committed` consumers — plus broker transaction coordination. It adds latency, complexity, and operational surface.
- For **audit telemetry** (best-effort observability that's already fronted by a 204 and an unbounded async pool), EOS is overkill — the data's value is aggregate trends, and duplicates are deduped cheaply at query time on `source_request_id`. So the deliberate choice is **best-effort produce + at-least-once sink + query-time dedupe**.
- The one durability upgrade I'd actually propose (cheap, high-value): set `acks=all` + `min.insync.replicas=2` + `enable.idempotence=true` on the **produce** side to close the leader-failure loss window. That's a config change, not an architecture change.

### 4.4 RF3 vs `acks=1` — the precise statement

The platform topics on `kafka-v2-luminate-core-prod` almost certainly run **RF3** (each region's broker list shows 3 brokers), and the platform default is `min.insync.replicas=2`. **But with audit's effective `acks=1`, the producer does NOT wait for replication** — the **leader** acks as soon as it appends to its own log. RF3 protects against broker loss **only after** the leader has replicated to followers, which `acks=1` does **not** guarantee at ack time. So: "RF3 is real, but on the audit path it only helps *after* replication, and acks=1 doesn't make the producer wait for that." (Per `06-KAFKA-MASTER-DEEPDIVE.md:119`.)

### 4.5 Freshness vs overhead (cite the 600 s)

- **Freshness:** because the sink flushes on `flush.interval=600` seconds (`env_properties.yaml:229`), audit data is visible in BigQuery within **up to ~10 minutes** (sooner if 50 MB or 5000 records hits first). That is the real freshness number.
- **`<5ms P99`:** that's the **async-hop overhead added to the audited API** (controller returns 204 immediately, §1.1) — a completely different metric. Never conflate "5 ms" with "audit is fresh in 5 ms."

### 4.6 Partition/RF sizing — formula, not invented numbers

Each region's broker list shows **3 brokers** ⇒ **RF is almost certainly 3**. But the **partition count, `replication.factor`, `min.insync.replicas`, and `retention`** are **not in the repo** — they're provisioned by Walmart **Kafka-as-a-Service (KaaS)**. So answer sizing with a **formula**, never a guessed number:

> **Partitions** = `ceil(target_throughput / per_partition_throughput)`, then `max(that, peak_consumer_parallelism)`, and `>=` the max tasks you'd ever run. For this sink, partitions must be `>=` `tasks.max` per connector (currently 1, so any partition count works today; bump `tasks.max` only up to the partition count). I'd size from the busiest endpoint's records/sec and a conservative per-partition ceiling, then round up for headroom — and confirm the actual provisioned number with the KaaS team rather than guess.

---

## PART 5 — RAPID-FIRE DEEP Q&A (every answer cited; audit-vs-NRTI fixed)

**Q1. Does the audit producer set `acks`?**
→ **No.** `KafkaProducerConfig.populateConfigProperties` (`KafkaProducerConfig.java:87-92`) sets only bootstrap, key/value serializers, schema-registry URL, and `auto.register.schemas=false`. `acks` is unset → **default `acks=1`**.

**Q2. What thread runs the audit `send()`, and what observes its result?**
→ An **unbounded cached-pool worker** (`ExecutorPoolService.java:10`) runs it — **not** Tomcat (the controller already returned 204). **Nothing observes the result**: the future from `kafkaPrimaryTemplate.send(...)` is **discarded** (`KafkaProducerService.java:47`); the surrounding `try/catch` only catches synchronous serialize/metadata throws.

**Q3. Does the audit producer have failover to a secondary region?**
→ **No.** `kafkaSecondaryTemplate` exists (`KafkaProducerConfig.java:60-63`) but is **dead code** — nothing calls it. The real `.exceptionally` dual-region failover is in **NRTI's** `NrtKafkaProducerServiceImpl`, a different service (doc `18`).

**Q4. Is the audit `send()` blocking?**
→ No. It serializes synchronously, buffers in the RecordAccumulator, and returns a future immediately; the single `kafka-producer-network-thread` (Sender) does the network I/O.

**Q5. So is anything `lz4`-compressed / batched with `linger.ms=20` on the audit path?**
→ **No** — that's the **NRTI** config. Audit sets no `compression.type` (→ `none`), no `batch.size` (→ default 16 KB), no `linger.ms` (→ 0). Don't import NRTI tuning into the audit story.

**Q6. What's the audit partition key, and why?**
→ `serviceName + "/" + endpoint` (`AuditKafkaPayloadKey.java:26-28`), set as `KafkaHeaders.KEY` (`KafkaProducerService.java:89`). It co-partitions one endpoint's records (per-endpoint ordering) and aligns with the sink's `PARTITIONBY service_name,_header.date,endpoint_name` for query locality.

**Q7. How is the audit key different from NRTI's IAC key?**
→ Audit sets the **real partition key** (`KafkaHeaders.KEY`). NRTI **IAC** sets `MESSAGE_ID` only as a **header**, so IAC has a **NULL partition key** and **no broker-level ordering**; only NRTI DSC keys on `tripId`.

**Q8. What does an Avro audit value look like on the wire?**
→ `[0x00 magic][4-byte schema ID][Avro binary]` (Confluent format). Values in schema order, no field names — far smaller than JSON.

**Q9. Schema Registry is down — what happens to the audit producer?**
→ `KafkaAvroSerializer` can't resolve the schema ID → **throws synchronously** → caught+logged (`KafkaProducerService.java:48`) → **record lost** (no producer DLQ). Mitigate with schema-cache warming + a `serialize_failure` metric.

**Q10. Why `auto.register.schemas=false`?**
→ `KafkaProducerConfig.java:92`. It forces schemas to be registered via gated CI (compatibility-checked) instead of a buggy producer silently registering an incompatible version in prod.

**Q11. Is `created_ts` the event time?**
→ **No.** `AvroUtils.java:39` sets `created_ts = System.currentTimeMillis()` at the **audit service**, i.e. ingestion time. Use `request_ts`/`response_ts` for event-time analytics.

**Q12. Why are headers stored as one Avro string?**
→ `AvroUtils.java:42,46-49` serializes the whole header map to a single pretty-printed JSON string. Implication: any unmasked `WM_SEC.*`/`Authorization` (common-JAR `mask.enable=false`) lands in cleartext at rest — a real PII surface.

**Q13. How many times is the audit topic read, and why?**
→ **3×.** Three connectors (`kc_config.yaml:63,81,99`), each with its **own** `connect-<name>` sink consumer group, each reading the whole topic. The shared `group.id` in config is the **worker-cluster** id, not a consumer group.

**Q14. Why do header-less records land only in the US bucket?**
→ `AuditLogSinkUSFilter.verifyHeader` (`AuditLogSinkUSFilter.java:42-56`) passes records that match the US site id **OR** have **no `wm-site-id`** (`noneMatch`). CA/MX inherit the **strict** `BaseAuditLogSinkFilter` (`:52-63`) that **drops** header-less records. US is the residency catch-all.

**Q15. Which SMT runs first, and why does order matter?**
→ `InsertRollingRecordTimestamp` runs **before** the country `Filter` (`kc_config.yaml:75`). It writes `_header.date` (GMT, `yyyy-MM-dd`) that `PARTITIONBY service_name,_header.date,endpoint_name` later needs for the daily GCS path.

**Q16. What does a filter SMT return to drop a record?**
→ `null`. `BaseAuditLogSinkFilter.apply` returns `r` to keep, `null` to drop (`BaseAuditLogSinkFilter.java:39-45`).

**Q17. Is `verifyHeader` fail-open or fail-closed?**
→ **Fail-closed.** Any exception → returns `false` → record dropped (`BaseAuditLogSinkFilter.java:57-62`). It also uses a parallel stream over the headers.

**Q18. Difference between the GCS retry policy and the DLQ?**
→ Two layers. GCS-write retries: `connect.gcpstorage.error.policy=RETRY`, `max.retries=5`, `retry.interval=5000` (`kc_config.yaml:71-73`) — retries the *object write*. DLQ: `errors.tolerance=all` + `errors.deadletterqueue.context.headers.enable=true` (`kc_config.yaml:69-70`) routes *poison records* to `api_logs_audit_prod_DLQ` (`env_properties.yaml:220`).

**Q19. Connect assignor — cooperative or eager?**
→ **Not explicitly set.** `partition.assignment.strategy` is **commented out** (`kc_config.yaml:55-56`) → client default `[RangeAssignor, CooperativeStickyAssignor]`. Don't claim it as a deliberate choice.

**Q20. How does the sink avoid losing data on crash?**
→ It commits offsets only **after** a successful GCS flush → on restart it resumes from the last commit → **at-least-once** (possible duplicate Parquet objects).

**Q21. What's the audit data freshness SLA, and why?**
→ Up to **~10 minutes** — `flush.interval=600` s (`env_properties.yaml:229`), or sooner on 50 MB / 5000 records. The `<5ms` figure is the async-hop overhead on the audited API (204 first), not freshness.

**Q22. What flushes a Parquet file?**
→ Whichever of `flush.size=50 MB`, `flush.count=5000`, `flush.interval=600 s` fires first (`env_properties.yaml:227-229`). Dev differs: 5 MB, no count (`:159`).

**Q23. What's the risk of `tasks.max=1` per connector?**
→ One task reads all partitions → no intra-connector parallelism. Fine at current volume; to scale, raise `tasks.max` (≤ partition count). `tasks.max:1` at `kc_config.yaml:66,84,102`.

**Q24. Effective delivery semantics end-to-end for audit?**
→ "Mostly-once with a thin loss window and possible GCS dupes": produce ≈ `acks=1` (loss on leader failure, caller already 204) + sink at-least-once (dup on crash-mid-flush). Not zero-loss, not EOS.

**Q25. Does RF3 make the audit produce durable?**
→ Not at ack time. With `acks=1` the leader acks before replication; RF3 protects only *after* the leader replicates (`06:119`). To make it durable: `acks=all` + `min.insync.replicas=2`.

**Q26. Why didn't you use exactly-once?**
→ EOS needs idempotent + transactional producers + `read_committed` consumers; high latency/complexity for best-effort telemetry. We chose at-least-once + BigQuery dedupe on `source_request_id` as the cheaper equivalent.

**Q27. How would you make the audit produce lossless without EOS?**
→ `acks=all` + `min.insync.replicas=2` + `enable.idempotence=true` (a config change), and **observe the future** (`whenComplete`) with a failure metric + a producer-side fallback (local spool/DLQ).

**Q28. Where does the security protocol get set on the sink?**
→ `security.protocol: PLAINTEXT` (`kc_config.yaml:14,23,32`) — mTLS is enforced at the Istio mesh, so the client speaks PLAINTEXT to the sidecar.

**Q29. How are the country site-ids resolved?**
→ `AuditApiLogsGcsSinkPropertiesUtil.getSiteIdForCountryCode` reads `WM_SITE_ID_FOR_<CC>` (`...PropertiesUtil.java:42-45`) from a file chosen by `STRATI_RCTX_ENVIRONMENT_TYPE` (`:28-32`). Prod: US=`...687000`, MX=`...984000`, CA=`...248000` (`audit_api_logs_gcs_sink_prod_properties.yaml:1-3`).

**Q30. How big is the audit topic's partition count / retention?**
→ **Not in the repo** — KaaS-provisioned. RF is almost certainly 3 (3 brokers/region). I'd size partitions by `ceil(throughput / per-partition-throughput)`, `>= tasks.max`, and confirm with the KaaS team — I won't invent a number.

**Q31. What's the topic and DLQ naming?**
→ Business topic `api_logs_audit_{dev|stg|prod}` (e.g. prod `api_logs_audit_prod`, `env_properties.yaml:219`); DLQ `api_logs_audit_{env}_DLQ` (prod `api_logs_audit_prod_DLQ`, `:220`).

**Q32. Could a `max.poll` timeout cause a rebalance on the sink?**
→ Yes — `consumer.max.poll.interval.ms=300000` (`kc_config.yaml:50`): if a task takes >5 min between polls, it's evicted and the group rebalances. Big flushes must finish well under that.

**Q33. Why is `consumer_id` never null even when the header is missing?**
→ `AvroUtils.getConsumerIdFromHeader` returns `"NA"` when `wm_consumer.id` is absent (`AvroUtils.java:51-57`), satisfying the **required** `consumer_id` string field in `log.avsc`.

---

## PART 6 — One-paragraph "I understand the AUDIT pipeline deeply" answer (provably true)

"The audit producer is **deliberately best-effort**, and I can defend every line of it. The controller returns **HTTP 204 immediately** (`AuditLoggingController.java:58-61`), then hands the send to an **unbounded cached thread pool** (`ExecutorPoolService.java:10`) where `KafkaProducerService` calls `kafkaPrimaryTemplate.send(...)` and **discards the future** (`KafkaProducerService.java:47`) — so the produce is fire-and-forget with **no failover** (the secondary template is dead code). The producer sets **only five properties** — bootstrap, String key serializer, `KafkaAvroSerializer`, schema-registry URL, and `auto.register.schemas=false` (`KafkaProducerConfig.java:87-92`) — so everything else is default: **effective `acks=1`**, no batching, no compression. On the wire each value is Confluent Avro — `[0x00][4-byte schema ID][binary]` — and because `auto.register=false`, schemas are gated through CI, not registered at runtime. The key is `service/endpoint` (`AuditKafkaPayloadKey.java:26`) for per-endpoint ordering and to mirror the sink's `PARTITIONBY service_name,_header.date,endpoint_name`. On the read side it's **Kafka Connect, not Spring**: three Lenses GCS-sink connectors, each with its own consumer group — that's the **3× read amplification** — each running `InsertRollingRecordTimestamp` (writes `_header.date`) **then** a country filter, where **US is permissive** (header-less records fall through to the US bucket, `AuditLogSinkUSFilter.java:47-49`) and CA/MX are strict. The sink flushes Avro into columnar **Parquet at 50 MB / 5000 records / 600 s** (`env_properties.yaml:227-229`), committing offsets after the flush — **at-least-once**, so a crash mid-flush can duplicate Parquet rows. Net: **mostly-once with a thin loss window on leader failure and possible GCS dupes** — I'd never call it zero-loss or exactly-once. Freshness is **~10 minutes** (the 600 s flush), and the `<5ms` number is the async-hop overhead on the audited API, a different metric. If the durability bar moved, the cheap fix is `acks=all` + `min.insync.replicas=2` + `enable.idempotence=true` and actually observing the send future — a config change, not a rewrite."
