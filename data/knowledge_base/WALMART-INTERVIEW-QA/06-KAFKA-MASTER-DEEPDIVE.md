# 06 — Kafka Master Deep-Dive (Walmart NRTI / Audit Pipeline)

> **Purpose.** Interviewers test Kafka theory *through your own system*. This file pairs every core Kafka concept with the **exact way it shows up in your two pipelines**, and is brutally honest about the resume-vs-code gaps so you self-correct *before* they catch you.

## The two Kafka systems you actually own (do not conflate them)

| | **Audit pipeline** (`audit-api-logs-srv` → Kafka → `audit-api-logs-gcs-sink`) | **NRTI inventory pipeline** (`cp-nrti-apis`) |
|---|---|---|
| Topic(s) | `api_logs_audit_{dev\|stg\|prod}` | `cperf-nrt-prod-iac`, `cperf-nrt-prod-dsc` |
| Value serializer | **`KafkaAvroSerializer`** + Confluent Schema Registry | **`JsonSerializer`** (Spring), **no Schema Registry** |
| Key serializer | `StringSerializer` | `StringSerializer` |
| Producer durability config | **NOT set** — only bootstrap/serializers/schema-url/auto-register + conditional SSL (defaults ≈ `acks=1`) | **Explicitly set from CCM**: `acks=all`, `retries=10`, `enable.idempotence=false`, `lz4`, `linger=20ms`, `batch=8192`, `request.timeout=300000ms` |
| Failover | `kafkaSecondaryTemplate` bean exists but is **DEAD** — send path uses only `kafkaPrimaryTemplate.send()` in a log-only try/catch | **REAL** active/active: `CompletableFuture.exceptionally` re-sends to secondary-region template |
| Cluster | `kafka-v2-luminate-core-prod`, EUS2 + SCUS, :9093 | same cluster, :9093 |
| Consumer | **Kafka Connect** (Lenses GCS sink), 3 connectors w/ region SMTs | downstream services (NRTI is producer-only) |

**Honesty anchors (say these unprompted if cornered):**
- The "active/active CompletableFuture failover" bullet is **NRTI**, not audit-srv. Audit-srv's `kafkaSecondaryTemplate` is autowired but never used in the send path.
- The "near-zero data loss" claim is **unsupported in the audit producer** (no `acks`/idempotence/retries set → defaults near `acks=1`). It is defensible only for **NRTI** IAC events (`acks=all` + RF3/ISR2), and even there it's **at-least-once, not exactly-once** (`enable.idempotence=false`).
- Stack: audited services + NRTI are **Spring Boot 3.5.14 / Java 17 / Jakarta**; the GCS sink is **not Spring Boot at all** — it's a Kafka Connect SMT plugin JAR.

---

## 1. Topics, Partitions, Offsets

**General concept.** A *topic* is a named, append-only log. It is split into *partitions*; each partition is an ordered, immutable sequence. A record's position in a partition is its *offset* (monotonic per partition). **Ordering is guaranteed only within a partition, never across a topic.** Parallelism scales with partition count: one partition is consumed by at most one consumer in a group at a time. Offsets are committed per `(group, topic, partition)` so a consumer can resume after restart/rebalance.

**How we used it here.**
- Audit pipeline writes to a single logical topic `api_logs_audit_{env}`; **geographic split (US/CA/MX) is NOT done by topic** — it's one immutable stream, filtered downstream in the sink by SMT. This keeps producers dumb and the stream replayable.
- NRTI uses two purpose-split topics: `cperf-nrt-prod-iac` (inventory-action, system-of-record) and `cperf-nrt-prod-dsc` (direct-shipment, best-effort). Splitting by *business criticality* lets the two paths have different delivery semantics (IAC blocks + 503; DSC fire-and-forget + 201).
- Offsets in **EUS2 and SCUS are independent clusters** — after an active/active failover, the same logical event can land at different offsets in each. That's why dedup is keyed on a **message identity**, not offset (see §5).

---

## 2. Partition Key Choice — `serviceName/endpoint` — Ordering + Hot-Partition Analysis

**General concept.** The producer picks a partition by `hash(key) % numPartitions` (sticky/round-robin when key is null). Same key ⇒ same partition ⇒ ordered. Key choice is a three-way trade among (a) the ordering guarantee you need, (b) even load distribution, and (c) co-location for grouping. A skewed key creates a **hot partition**: one broker/consumer saturates while others idle.

**How we used it here.** Audit message key = `AuditKafkaPayloadKey.getKafkaKey()` = `serviceName + "/" + endpoint` (e.g. `NRT/transactionHistory`).
- **Why:** co-partitions all audit records for one endpoint onto one partition → per-endpoint ordering and clean grouping; also makes the GCS Parquet partitioning (`PARTITIONBY service_name,_header.date,endpoint_name`) align with the stream's natural key.
- **Hot-partition failure mode:** a single very busy endpoint (say one supplier hammering `transactionHistory`) funnels all its traffic to **one** partition → that partition lags while others are idle; the sink task for it backs up.
- **Fix without losing grouping:** composite key `serviceName/endpoint/consumerId` (or add a bounded salt suffix). You keep grouping at the endpoint level but spread a hot endpoint's load across N partitions. Trade-off: you lose strict global per-endpoint ordering (now per-`(endpoint,consumer)`), which is acceptable for audit since each record is independent.
- **Honest note:** alternatives considered — null/random key (no ordering), `trace_id` (perfect spread, zero grouping), `wm-site-id` (only 3 distinct values → 3 hot partitions, worst of all).

---

## 3. Producer Tuning — acks / idempotence / retries / linger / batch / compression

**General concept.**
- `acks`: `0` = fire-and-forget (lossy), `1` = leader-ack (loses on leader crash before replication), `all`/`-1` = wait for all in-sync replicas.
- `min.insync.replicas` (broker/topic side): with `acks=all`, the write fails unless at least this many replicas are in sync — that's what makes `acks=all` actually durable.
- `enable.idempotence=true`: producer tags records with a producer-id + sequence number so the broker dedups retries → **no duplicates and no reordering into a partition**. Requires `acks=all`, `retries>0`, `max.in.flight.requests<=5`.
- `retries` + `delivery.timeout.ms`: how hard the client retries transient failures before giving up.
- `linger.ms` + `batch.size`: micro-batching — wait up to `linger.ms` to fill a `batch.size` buffer → fewer, bigger requests → throughput at the cost of a little latency.
- `compression.type` (`lz4`/`snappy`/`zstd`/`gzip`): compresses the batch → less network/disk.

**How we used it here — and the honest gap.**

**Audit producer (`KafkaProducerConfig.java`) — DOES NOT set durability.** It sets only:
```java
BOOTSTRAP_SERVERS_CONFIG          = primary/secondary broker list (from CCM)
KEY_SERIALIZER_CLASS_CONFIG       = StringSerializer.class
VALUE_SERIALIZER_CLASS_CONFIG     = KafkaAvroSerializer.class
schema.registry.url               = auditLogsKafkaCCMConfig.getSchemaRegistryUrls()
auto.register.schemas             = false
// + conditional SSL block, gated off in prod (mTLS at Istio)
```
There is **no `acks`, no `enable.idempotence`, no `retries`, no `linger`, no `batch`, no `compression`** → all default. Kafka client default `acks=1`, idempotence off. **So "near-zero data loss" is not provable for the audit path** — a leader failure between ack and replication loses that record, and the caller already got HTTP 204. The honest fix I'd propose: `acks=all` + `min.insync.replicas=2` + `enable.idempotence=true`.

**NRTI producer (`NrtKafkaProducerConfig.populateConfigProperties`) — DOES set them, from CCM:**
```java
COMPRESSION_TYPE_CONFIG  = lz4
ACKS_CONFIG              = all
LINGER_MS_CONFIG         = 20
BATCH_SIZE_CONFIG        = 8192
RETRIES_CONFIG           = 10
ENABLE_IDEMPOTENCE_CONFIG = false   // <-- the catch
REQUEST_TIMEOUT          = 300000ms (5 min)
MAX_REQUEST_SIZE         = 10000000
```
So NRTI IAC is genuinely durable (`acks=all` + RF3/ISR2), but with **`enable.idempotence=false` + `retries=10`** the guarantee is **at-least-once with possible duplicates AND reordering**. That is *the* gap to volunteer: I'd flip idempotence on (all prerequisites are already met) to get rid of retry-duplicates and per-partition reordering for free.

**The `request.timeout.ms=300000` (5 min) gotcha.** For a *black-hole* network failure, the `CompletableFuture` can't fail (and thus failover can't fire) for up to 5 minutes. Only **fast** failures (connection refused / no brokers) give the advertised sub-second failover. Mitigation: `orTimeout(...)` on the future to bound failover latency independent of `request.timeout.ms`.

---

## 4. KafkaAvroSerializer + Confluent Schema Registry + Compatibility + Evolution

**General concept.** With Avro + Confluent Schema Registry, the producer registers the writer schema, the registry returns an integer **schema ID**, and the serialized payload is `[magic byte][4-byte schema ID][Avro binary]`. Consumers fetch the writer schema by ID and deserialize against their reader schema. The registry enforces a **compatibility mode** on the subject:
- **BACKWARD** (default): new schema can read data written by old schema → safe to **add optional/defaulted fields** and **remove fields**. Consumers upgrade first.
- **FORWARD**: old schema can read new data → add fields with defaults, but don't remove required ones. Producers upgrade first.
- **FULL**: both. **NONE**: no checks.

**How we used it here.**
- `value.serializer = io.confluent.kafka.serializers.KafkaAvroSerializer`, `schema.registry.url` from CCM, **`auto.register.schemas=false`**.
- **Why `false` matters:** it forces controlled, governed schema promotion. A rogue pod **cannot silently auto-register** an incompatible schema in prod; registration is a deliberate ops step. Trade-off: a missing/unregistered schema **fails the producer** — Schema Registry is a hard dependency on the produce path *and* the read path (the sink's `AvroConverter` also resolves IDs against it), so it's effectively a shared SPOF; mitigate with registry HA + client-side schema caching.
- **The `LogEvent` schema (`log.avsc`), 19 fields, namespace `com.walmart.dv.audit.model.api_log_events.LogEvent`:** required fields are `source_request_id`, `endpoint_path`, `method`, `response_code` (int), `consumer_id`, `request_ts`/`response_ts`/`created_ts` (long), `endpoint_name`, `service_name`. **Evolution-safe optional fields are unions `["null","string"]` with `"default": null`** — `api_version`, `trace_id`, `supplier_company`, `request_body`, `response_body`, `error_reason`, `request_size_bytes`/`response_size_bytes` (`["null","int"]`), `headers`. That null-with-default pattern is *exactly* what makes the schema **BACKWARD-compatible**: I can add a new optional field and old consumers still read old records (they see the default), new consumers read old records (missing field → null).
- **Sink side:** the Connect worker uses `value.converter: io.confluent.connect.avro.AvroConverter` with `value.converter.schemas.enable: true`, so it deserializes the Avro back into a Connect `Struct` before the SMT chain and the Parquet write.

---

## 5. Delivery Semantics — at-least-once vs exactly-once — and where we land

**General concept.**
- **At-most-once:** ack early / don't retry → can lose, never duplicates.
- **At-least-once:** retry until acked → never lose (given durability) but **can duplicate**.
- **Exactly-once (EOS):** idempotent producer + transactions (`transactional.id`, `read_committed`) across produce→consume→produce, *or* an idempotent/transactional sink. Costs throughput and complexity.

**Where we land — honestly.**
- **NRTI IAC:** `acks=all` + RF3/ISR2 + `retries=10` but `enable.idempotence=false` ⇒ **at-least-once**. Acked events survive a single-region broker loss (so "no loss of an *acknowledged* event"), but failover/retries can produce **duplicates and reordering**. That's why event identity is the **client-supplied `messageId`** (copied into `messageId` + `correlationId` + the `MESSAGE_ID` header), so **downstream consumers dedup** — dedup correctness depends on suppliers sending globally-unique IDs (a collision causes a wrongful drop; mitigate by namespacing `supplierId + messageId`).
- **Audit path:** at-least-once on the **sink** side (Connect commits offsets after the GCS flush, so a crash mid-flush re-delivers → possible duplicate Parquet rows), combined with **near-`acks=1`** on the produce side (small *loss* window on leader failure). So end-to-end it is **neither exactly-once nor zero-loss** — it's "mostly-once with a thin loss window and possible GCS dupes." Say this plainly; do not claim EOS.

---

## 6. Replication / ISR / min.insync.replicas

**General concept.** Each partition has `replication.factor` copies; one is leader, the rest followers. The **ISR (in-sync replica set)** is the replicas caught up within `replica.lag.time.max.ms`. On leader failure, a new leader is elected from the ISR. `acks=all` + `min.insync.replicas=N` means a write is only acked once N replicas have it — that's the durability contract. With RF3 / `min.insync.replicas=2` you can lose one broker with zero acknowledged-data loss.

**How we used it here.** The platform topics on `kafka-v2-luminate-core-prod` run **RF3 with ISR/min.insync.replicas=2** (platform-managed). For **NRTI IAC**, `acks=all` rides on top of that → an acked IAC event is durable in at least one region; if it can't be, the supplier gets a **503 to retry** (no silent loss). For the **audit producer**, since `acks` is unset (default 1) the *broker-side* RF3 exists but the *producer* doesn't wait for it — so the replication factor protects against broker loss only *after* the leader has replicated, which `acks=1` does not guarantee at ack time. (Restating the §3 gap from the replication angle.)

---

## 7. Retention & Replay

**General concept.** Topics retain data by `retention.ms` and/or `retention.bytes` (or `cleanup.policy=compact` to keep the latest value per key). Because partitions are immutable logs, a consumer can **reset its offset** (`--to-earliest`, `--to-datetime`, a specific offset) and **replay** — invaluable for rebuilding a downstream store or recovering from a bad transform.

**How we used it here.**
- Keeping the audit stream a **single un-split topic** is what makes replay clean: to backfill or re-bucket US/CA/MX I just reset the relevant Connect connector's consumer-group offsets and let the SMTs re-run — no producer involvement.
- Each region's GCS sink connector has its **own consumer group offsets**, so I can replay one country's pipeline (e.g. re-emit MX Parquet after a mapping fix) without touching US/CA.
- Replay safety caveat: because the sink is at-least-once, a replay produces **duplicate Parquet objects**; dedupe happens at query time in BigQuery (or via object overwrite by the deterministic partition path).

---

## 8. Security — mTLS

**General concept.** Kafka can secure transport with TLS and authenticate clients with **mTLS** (client presents a cert) or SASL. `security.protocol` selects `PLAINTEXT` / `SSL` / `SASL_SSL`. In a service mesh, TLS can be terminated/originated by sidecars instead of the Kafka client.

**How we used it here.** TLS is **terminated at the Istio mesh (mTLS)**, so the Kafka *clients* run `security.protocol=PLAINTEXT` to the local sidecar:
- Audit producer: `auditLoggingKafkaSslEnabled=false` in prod CCM → the SSL block in `KafkaProducerConfig` is skipped (the log line literally says "mTLS is enforced for Kafka connections"). The full JKS truststore/keystore code path **exists but is gated off**.
- NRTI: `nrtKafkaSslEnabled=false`; same pattern — full JKS path present in `NrtKafkaProducerConfig` but disabled.
- Sink worker: `security.protocol: PLAINTEXT` (+ explicit `consumer.` / `producer.` prefixed PLAINTEXT) in `kc_config.yaml`, all the `ssl.*` lines commented out.

Trade-off to state: PLAINTEXT-to-sidecar is correct *inside* a mesh but would be wrong if the client ever talked to a broker directly without mTLS — security depends on the mesh boundary holding.

---

## 9. Kafka Connect + SMT Internals (the region Filter SMTs)

**General concept.** Kafka Connect is a framework for streaming data in/out of Kafka without writing consumer code. A **sink connector** runs as **tasks** inside Connect workers; the framework gives you offset management, group rebalancing, retries, and a dead-letter queue for free. A **Single Message Transform (SMT)** is a per-record `Transformation<R>` applied in a **chain** between the converter and the connector: each SMT's `apply(record)` returns a (possibly modified) record, **or `null` to drop it**. Transforms run **in declared order**.

**How we used it here.** Three GCS sink connectors, one per country, defined in `kc_config.yaml`, each `tasks.max: 1`, `errors.tolerance: all`, DLQ headers on, `connect.gcpstorage.error.policy: RETRY` with `max.retries: 5`. Each has a **two-step transform chain**:

```
transforms: InsertRollingRecordTimestamp, FilterUS   (resp. FilterCA / FilterMX)
```
1. **`InsertRollingRecordTimestamp`** (Lenses SMT) stamps a `date` header `yyyy-MM-dd` in **GMT** — used downstream in the Parquet `PARTITIONBY ...,_header.date,...`.
2. **`FilterUS/CA/MX`** = our custom `Transformation` subclasses. The base class `BaseAuditLogSinkFilter`:
   ```java
   public R apply(R r) { return verifyHeader(r) ? r : null; }   // null = drop
   // verifyHeader: stream r.headers(), pass iff a header key "wm-site-id"
   //               EQUALS getHeaderValue() (the env's site-id for this country)
   ```
   So the topic carries every country's records; **each connector keeps only the records whose `wm-site-id` header matches its country and drops the rest** by returning `null`. `getHeaderValue()` resolves the env-specific site-id via `AuditApiLogsGcsSinkPropertiesUtil.getSiteIdForCountryCode("US"/"CA"/"MX")`.

**The critical code-vs-comment gotcha (know the code, not the Javadoc):**
- **CA and MX Javadoc say** "Records are passed if the header matches *or if the header is missing*." **That is false** — `AuditLogSinkCAFilter`/`MXFilter` only override `getHeaderValue()` and **inherit the strict base `verifyHeader`**, which requires an exact match. A header-less record is **dropped** by CA and MX.
- **Only `AuditLogSinkUSFilter` actually overrides `verifyHeader`** to add the catch-all:
  ```java
  anyMatch(key=="wm-site-id" && value==US-site-id)
    || noneMatch(key=="wm-site-id")      // <-- header missing ⇒ also pass
  ```
  So **US is the catch-all bucket**: any record with no `wm-site-id` (or US) lands in US only. CA/MX strict. That's a deliberate "missing data must land *somewhere*" choice — but it's a **residency edge case** (a mis-tagged CA record with a dropped header would silently land in the US bucket); flag it for compliance.

**Why Connect instead of a hand-written `@KafkaListener`:** we wrote ~75 lines of SMT and got offset management, rebalancing, retry, DLQ, and Parquet/GCS batching for free. Trade-off: less control of internals, coupling to Lenses connector versioning, and the sink is a **Connect plugin JAR — not a Spring Boot app** (no `main`, no `Application` class). Correct any doc that calls it Spring Boot.

**3× read amplification (own it):** three connectors each consume the **whole** topic, so every record is read 3×. Deliberate isolation trade (independent offsets/lag/failure domains per country, clean one-connector-per-bucket mapping). At ~10× volume it flips toward a **single branching connector** (e.g. partition-router writing to per-country prefixes).

---

## 10. Multi-Cluster / Active-Active

**General concept.** Cross-region resilience options:
- **MirrorMaker 2 / Cluster Linking:** async replicate topics between clusters. Simple, but replication lag is your RPO on failover, and offsets must be translated.
- **Stretch cluster:** one cluster spanning regions. Strong consistency, but cross-region replica acks add latency to *every* write and risk quorum thrash.
- **Producer-side dual-write (application-level):** the app writes to both regions itself. Sub-second, app-owned failover with ~zero RPO per acked event, at the cost of holding two clients and diverging offsets.

**How we used it here (NRTI, the real one).** **Producer-side application-level active/active.**
- 4 templates in `NrtKafkaProducerConfig`: `kafkaPrimaryTemplate`/`kafkaSecondaryTemplate` (IAC) and `kafkaDscPrimaryTemplate`/`kafkaDscSecondaryTemplate` (DSC).
- **Region pinning is pure CCM config**, not code: `ccm.yml` `configOverrides` resolve by `/envProfile/envName/zone`. **`zone:eus2` pods** get `primary = ...eus.prod...:9093`, `secondary = ...scus...`; **`zone:scus` pods get them swapped.** One image, both regions take live writes simultaneously → active/active.
- **Failover (IAC path):**
  ```java
  future = kafkaPrimaryTemplate.send(msg);
  future.thenAccept(/* log offset */)
        .exceptionally(ex -> { handleFailure(...).join(); return null; })  // re-send to secondary region
        .join();   // blocks request thread; total failure -> NrtiUnavailableException -> HTTP 503
  ```
  `handleFailure` does `kafkaSecondaryTemplate.send(msg)...exceptionally(throw CompletionException(NrtiUnavailableException))`. So a regional Kafka outage degrades to a **per-message sub-second failover** to the other region instead of an outage.
- **DSC path is fire-and-forget** (no `.join()`) and returns **201 even on total failure** — a real asymmetry/smell to own, not hide.
- **Numbers, stated as what they are:** the *code* failover is sub-second & per-message. "**15-min DR recovery vs 1-hour RTO**" is an **operational/config-level** figure (CCM region-pin flip / cluster health-back) from DR game-days vs an old manual runbook — there is no in-repo artifact proving 15 min or 1 hour; present them as operational, not code-derived. Also note **RPO vs RTO** are conflated in the resume: real RPO ≈ 0 for an acked IAC event; "15 min" is an RTO-ish operational recovery time.
- **Audit path has NO real failover** — `kafkaSecondaryTemplate` exists but the send path uses only `kafkaPrimaryTemplate.send()` in a log-only try/catch. Do not attribute NRTI's failover to audit-srv.

---

## Rapid-Fire Kafka Q&A (37)

1. **Q: What guarantees ordering in Kafka?** A: Only within a single partition; across a topic there is no order.
2. **Q: Your audit partition key?** A: `serviceName + "/" + endpoint` (e.g. `NRT/transactionHistory`).
3. **Q: Why that key?** A: Co-partitions one endpoint's records for per-endpoint ordering and to align with the GCS Parquet partitioning.
4. **Q: Its failure mode?** A: A single busy endpoint becomes a hot partition (one partition saturated, others idle).
5. **Q: Fix the hot partition without losing grouping?** A: Composite key `service/endpoint/consumerId` (or a bounded salt) to spread within an endpoint.
6. **Q: `acks=1` vs `acks=all`?** A: `1` = leader-only ack (loses if leader dies pre-replication); `all` = wait for all in-sync replicas.
7. **Q: What does the audit producer set for acks?** A: Nothing — it's unset, so Kafka default `acks=1`. "Near-zero loss" isn't provable there.
8. **Q: What does NRTI set?** A: `acks=all`, `retries=10`, `lz4`, `linger=20ms`, `batch=8192`, `request.timeout=300000ms`, `enable.idempotence=false` — all from CCM.
9. **Q: So is NRTI exactly-once?** A: No — idempotence is off, so at-least-once with possible duplicates/reordering.
10. **Q: Why is that not zero data loss then?** A: It's "no loss of an *acknowledged* IAC event under single-region failure," and dedup is pushed to consumers via `messageId`.
11. **Q: What does `min.insync.replicas` do?** A: With `acks=all`, the write fails unless ≥ N replicas are in sync — that's what makes `acks=all` durable. Ours is 2 (RF3).
12. **Q: What does `enable.idempotence=true` require and give?** A: Requires `acks=all`, `retries>0`, `max.in.flight<=5`; gives no duplicates and no reordering into a partition.
13. **Q: NRTI already meets those prereqs — why not turn it on?** A: It should be; leaving it off (likely a platform-era default) is the gap I'd fix.
14. **Q: `linger.ms` / `batch.size` purpose?** A: Micro-batching — trade a little latency for throughput by sending fewer, fuller requests.
15. **Q: Compression type used?** A: `lz4` on NRTI; none configured on audit (default `none`).
16. **Q: Audit value serializer?** A: `KafkaAvroSerializer` + Confluent Schema Registry.
17. **Q: NRTI value serializer?** A: Spring `JsonSerializer`, no Schema Registry — different pipeline, don't conflate.
18. **Q: What is `auto.register.schemas=false`?** A: Producers can't silently register a new/incompatible schema in prod; promotion is a governed step.
19. **Q: Downside of `false`?** A: A missing registration fails the producer; Schema Registry is a hard dependency on both produce and sink-read paths.
20. **Q: What's in the Avro payload bytes?** A: magic byte + 4-byte schema ID + Avro binary.
21. **Q: LogEvent compatibility mode?** A: BACKWARD — optional fields are `["null", T]` with `"default": null`, so old/new readers interoperate.
22. **Q: How do you add a field safely?** A: Add it as a nullable union with a default; never make a new field required.
23. **Q: How many LogEvent fields / namespace?** A: 19 fields, `com.walmart.dv.audit.model.api_log_events.LogEvent`.
24. **Q: What runs the audit consumer?** A: Kafka Connect (Lenses `GCPStorageSinkConnector`), not a Spring app.
25. **Q: How many connectors and why?** A: Three (US/CA/MX) for isolated per-country failure domains and clean per-bucket mapping; costs 3× read amplification.
26. **Q: How does a region filter actually drop a record?** A: The SMT's `apply()` returns `null` for non-matching `wm-site-id`.
27. **Q: A record with no `wm-site-id` header — where does it go?** A: US only (US filter's `noneMatch` catch-all); CA/MX strict-match and drop it.
28. **Q: CA/MX Javadoc says they pass header-less records — true?** A: No — they inherit the strict base; only US overrides `verifyHeader`. Comment lies; code is strict.
29. **Q: Transform order in the chain?** A: `InsertRollingRecordTimestamp` then the country `Filter` — declared order is execution order.
30. **Q: What free services does Connect give you?** A: Offset management, group rebalancing, retries, DLQ, Parquet/GCS batching.
31. **Q: Connect's rebalance protocol?** A: Cooperative-sticky (incremental) — keeps unaffected partition assignments instead of stop-the-world; default in `[RangeAssignor, CooperativeStickyAssignor]`, and each connector has `tasks.max:1` so within-connector rebalances are trivial.
32. **Q: Why one immutable topic instead of topic-per-region?** A: Keeps producers dumb, the stream replayable, and isolation/routing in the sink where it's cheap to change.
33. **Q: How do you replay a single country's pipeline?** A: Reset that connector's consumer-group offsets and let its SMTs re-run; others untouched.
34. **Q: Replay side effect?** A: Duplicate Parquet objects (sink is at-least-once); dedupe at query time / deterministic object paths.
35. **Q: Kafka client security to brokers?** A: `PLAINTEXT` — mTLS is terminated at the Istio sidecar; JKS code paths exist but are gated off.
36. **Q: Multi-region approach and why not MirrorMaker?** A: Producer-side dual-write (CompletableFuture `.exceptionally` to the other region) — sub-second, app-owned, ~0 RPO per acked event; MM2's replication lag would be the RPO and adds offset translation.
37. **Q: Where does the real failover live?** A: `cp-nrti-apis` `NrtKafkaProducerServiceImpl`, IAC path. Audit-srv's `kafkaSecondaryTemplate` is dead code.
