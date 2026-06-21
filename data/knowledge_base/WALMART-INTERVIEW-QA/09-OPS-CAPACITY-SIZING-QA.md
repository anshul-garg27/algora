# Walmart — Operational & Capacity / Sizing Q&A

> Anshul Garg · Walmart Luminate · Kafka audit pipeline + cp-nrti NRTI producer
>
> **Two separate Kafka systems — never conflate them.**
> **A) AUDIT pipeline** (`audit-api-logs-srv` Avro producer → Lenses Kafka Connect GCS sink): ONE business topic `api_logs_audit_{env}` (+ DLQ). Avro + Schema Registry. Key = `serviceName + "/" + endpoint`. Geo-routing in the SINK via `wm-site-id` header + Filter SMT.
> **B) NRTI pipeline** (`cp-nrti-apis` JSON producer): TWO topics `cperf-nrt-{env}-iac` + `cperf-nrt-{env}-dsc`. Spring `JsonSerializer`, NO Schema Registry. Key = client-supplied `messageId` (DSC also keys `tripId`).
>
> **Shared infra:** clusters `kafka-v2-luminate-core-{stg|prod}`, two Azure regions **EUS2** + **SCUS**, port **9093**, mTLS terminated at the **Istio** mesh. Active/active with broker lists swapped per region deployment. **3 broker hostnames per region** in config ⇒ RF almost certainly 3 (NOT confirmable in-repo).
>
> **Golden rule for this whole doc:** partition count, replication.factor, min.insync.replicas, retention.ms, and topic provisioning are **NOT in either repo** — they are set via **Walmart Kafka-as-a-Service (KaaS) self-serve**, external to the service code. For every one of these, the correct interview answer is: *"that's a KaaS-provisioned topic property, not in my service config — here's the value I requested and the formula I sized it with."* Never invent these numbers.

---

## 0. The 60-second "ops reality" answer key (MEMORIZE THIS TABLE)

This is the table to have burned into memory. It answers, literally and side-by-side: partition key? how many topics? how many partitions? how many consumers? replication factor? retention? — and *how each was decided*. Where a value is provisioned externally, it shows the value I **would have requested** plus the one-line reasoning.

| Question | **AUDIT system** (`api_logs_audit_prod`) | **NRTI system** (`cperf-nrt-prod-iac` / `-dsc`) |
|---|---|---|
| **How many topics?** | **1 business topic** `api_logs_audit_prod` + **1 DLQ** `api_logs_audit_prod_DLQ`. One homogeneous event type (one Avro `LogEvent`, one ingest API `v1/logRequest`). Env separated by name suffix, not business dimension. | **2 topics**: `cperf-nrt-prod-iac` (inventory-action) + `cperf-nrt-prod-dsc` (direct-shipment-confirmation). Split by domain because they have **opposite criticality** — IAC is a system-of-record mutation, DSC is best-effort. |
| **Partition KEY?** | `serviceName + "/" + endpoint` (`AuditKafkaPayloadKey.getKafkaKey()` line 27, set on `KafkaHeaders.KEY` in `KafkaProducerService` line 89). Per-(service,endpoint) ordering; mirrors KCQL `PARTITIONBY`. | **DSC** = `tripId` (`vendorId_deliveryDate_storeNbr_minPackNbr`, set on `KafkaHeaders.KEY` `DscServiceHelper` line 264). **IAC = NULL key** — `IacServiceHelper` sets only a `MESSAGE_ID` custom header, NOT `KafkaHeaders.KEY` ⇒ sticky/round-robin partitioning, **no broker-level ordering**. |
| **How many partitions?** | **NOT in repo — KaaS-provisioned.** Throughput needs ~1 (23 eps avg). I'd **request 6**: future consumer parallelism (3 connectors × room to raise `tasks.max`), even spread of 2 leaders/broker on a 3-broker cluster, headroom (repartitioning a keyed topic breaks ordering). | **NOT in repo — KaaS-provisioned.** Throughput tiny. I'd **request 6–12 each**, sized to *consumer parallelism + ordering-key cardinality* (high for both `messageId` and `tripId`), with 2–3× growth headroom because growing a keyed (DSC) topic later breaks ordering. |
| **How many consumers?** | **3** — Kafka Connect, 3 Lenses GCS-sink connectors (US catch-all, CA strict, MX strict), each `tasks.max=1`. Each connector = its own consumer group ⇒ topic read **3×** (3× read amplification) by design, for per-country isolation + separate GCS buckets. | **Producer side only** — consumers are downstream services I don't own. Consumer parallelism is capped at partition count. No fan-out read-amplification pattern; iac and dsc each have a dedicated downstream consumer. |
| **Replication factor?** | **NOT in repo — KaaS topic property.** Broker DNS fronts a 3-broker cluster, KaaS default RF=3. I'd **request RF=3** for an audit/compliance feed (survives 1 broker loss with quorum). | **NOT in repo — KaaS topic property.** 3 broker hostnames/region ⇒ RF=3. I'd **request RF=3** — IAC is a financial inventory mutation, zero-loss bar. |
| **min.insync.replicas?** | **NOT in repo (broker/topic).** I'd request **2** (with RF=3). Caveat: audit producer runs at client-default **acks=1**, so min.insync doesn't gate writes today — moot until acks=all is wired. | **NOT in repo (broker/topic).** I'd request **2** (with RF=3). This one *matters*: producer explicitly sets **acks=all** (`ccm.yml:172`), which only delivers zero-loss when paired with min.insync=2. |
| **Retention?** | **NOT in repo — KaaS topic config.** I'd **request 3–7 days**. Kafka is a transient buffer; source of truth is GCS Parquet + BigQuery (sink lands data within 10 min). 7 days lets me replay a full week. Disk ≈ 230 eps × 2KB × 86400 × 7 × RF3 ≈ **0.8 TB** cluster-wide. | **NOT in repo — KaaS topic config.** I'd **request 3–7 days**, sized to the worst plausible downstream (Enterprise Inventory) outage window + replay margin. |
| **acks?** | **1** (client default — nothing set in `KafkaProducerConfig.java`). Conscious telemetry-vs-source-of-truth tradeoff; the **#1 gap** I'd fix → acks=all. | **all** (`ccm.yml:172`, `NrtKafkaProducerConfig.java`). Zero-loss for financial inventory actions. |
| **idempotence?** | **false** (default) ⇒ at-least-once. | **false** (`ccm.yml:197`) ⇒ at-least-once; consumers dedup on `messageId`/`tripId`. |
| **Serialization?** | **Avro** (`KafkaAvroSerializer`) + Schema Registry, `auto.register.schemas=false`. Long-lived analytics-of-record → strict versioned schema. | **JSON** (Spring `JsonSerializer`), **NO Schema Registry**. Point-to-point operational handoff → simplicity. |
| **HPA (prod)?** | min **4** / max **8** @ cpuPercent **60**, 1–2 CPU (`kitt.yml` prod 409–418). | min **4** / max **8** @ 60% per brief; **committed prod `kitt.yml` is min 6 / max 12** (lines 478–487 / iacprod 586–595) — the 4/8 is the stage profile. State this honestly. |
| **Delivery semantic (end-to-end)?** | **At-least-once** (best-effort-once on produce today due to acks=1). Sink commits offsets after flush ⇒ duplicates possible in GCS, dedup in BigQuery. NOT exactly-once. | **IAC**: at-least-once, no ordering (null key), sync-with-failover, caller sees failure (maps to **HTTP 500**, docs say 503). **DSC**: at-least-once happy path, **at-most-once on both-region failure** (swallowed, returns 201). |

> **One-liner if pushed on "how did you get numbers you can't see in code?"**: *"For everything in my code — producer tuning, HPA, sink config — I quote exact lines. For topic-level settings that live in KaaS (partitions, RF, min.insync, retention), I'm honest they're not in my repos, and I defend a value with the formula: partitions from target_eps / per-partition throughput bounded by consumer parallelism and key cardinality; RF3 + min.insync2 from the durability the workload demands and the 3-broker-per-region topology I can see; retention from replay-need × the disk formula."*

---

## 1. Topic inventory — every topic, both systems, why that many

### AUDIT system
| Topic | Purpose | Source |
|---|---|---|
| `api_logs_audit_prod` (stg: `api_logs_audit_stg`; dev uses stg) | The one business topic — all audit `LogEvent`s | `PROD-1.0-ccm.yml:41-42`, `NON-PROD-1.0-ccm.yml:42` (`auditLoggingKafkaTopicName`) |
| `api_logs_audit_prod_DLQ` | Dead-letter for unprocessable records at the sink | `env_properties.yaml` (`errors.deadletterqueue.topic.name`), `ccm/PROD-1.0-ccm.yml:37` |
| `api_logs_audit_prod-prod-{config,offset,status}` | Kafka Connect internal state topics | `env_properties.yaml:115-117` |

**Why ONE business topic, not topic-per-service or topic-per-region?** Audit is a single homogeneous event type: one Avro `LogEvent` schema, one ingestion endpoint `POST v1/logRequest`. Topic-per-service would multiply partitions × RF × offset/coordination metadata by N for zero schema benefit and push routing logic into the producer. Topic-per-region is unnecessary because geo separation is a **SINK** concern, solved by the `wm-site-id` header + Filter SMT, not by topic topology. One topic keeps the producer config trivial (just a topic name in CCM) and lets KaaS manage one partition set. Environments are separated by name suffix (dev/stg/prod), not business dimension.

### NRTI system
| Topic | Purpose | Source |
|---|---|---|
| `cperf-nrt-prod-iac` (dev: `cperf-nrt-dev-iac`) | Inventory-action capture (store adjustments) | `ccm.yml:132`, `nrtKafkaConfig.json:10` |
| `cperf-nrt-prod-dsc` (dev: `cperf-nrt-dev-dsc`) | Direct-shipment-confirmation (freight notification) | `ccm.yml:202`, `nrtKafkaConfig.json:24` |

**Why TWO topics, not one?** Different domains, different consumers, different schemas, different ordering keys, and crucially **different durability SLAs**. IAC is an inventory mutation — losing one silently corrupts on-hand counts, so it's synchronous-with-failover and surfaces failure to the caller. DSC is a freight notification consumed by a separate pipeline — fire-and-forget. One topic would force one retention/partition/consumer-group policy onto two workloads with opposite criticality and couple their consumers.

---

## 2. Partitioning — keys, counts, hot-partition & ordering analysis

### 2.1 Keys
- **AUDIT**: `serviceName + "/" + endpoint`. `AuditKafkaPayloadKey.getKafkaKey()` line 27 literally returns `getServiceName() + FORWARD_SLASH + getEndpoint()`; set on `KafkaHeaders.KEY` in `KafkaProducerService` line 89. Gives **per-(service,endpoint) ordering**. Mirrors KCQL `PARTITIONBY service_name, endpoint_name` so the on-wire key and on-disk layout are consistent.
- **NRTI DSC**: `tripId = vendorId_shipmentDeliveryDate_storeNbr_minPackNbr` (`buildTripId` lines 117-134), set via `KafkaHeaders.KEY` in `DscServiceHelper.prepareDscKafkaMessage` line 264. **Per-trip ordering.**
- **NRTI IAC**: **NULL Kafka key** — `IacServiceHelper.prepareIacActionKafkaMessage` (lines 182-212) sets only a custom `MESSAGE_ID` header + `TOPIC` header, **not** `KafkaHeaders.KEY`. `messageId` is a payload/header field for dedup, **not** the partition key. ⇒ default sticky partitioner spreads IAC across partitions ⇒ **NO broker-level ordering**. This is a real finding I'd flag and fix by setting `KafkaHeaders.KEY = storeNbr` (or store+item composite).

### 2.2 Partition count — the formula (NOT in repo; KaaS-provisioned)
> `partitions = max( ceil(target_peak_eps / per_partition_ceiling), desired_consumer_parallelism )`

- **Throughput is never the binding constraint here.** Audit ~23 eps avg, ~100–230 eps peak, sub-KB Avro. Even at 10 KB/event that's ~2.3 MB/s — a single partition (handles MB/s to tens of MB/s) clears it.
- **What actually drives the count:** (1) future consumer parallelism — a group can't exceed partition count; (2) broker spread for RF3; (3) headroom, because repartitioning a *keyed* topic reshuffles key→partition mapping and breaks ordering.
- **AUDIT request: 6 partitions.** Lets me raise `tasks.max` toward 6 later with no repartition; lays out as 2 leaders/broker on a 3-broker cluster. Don't over-partition — more partitions = more open Parquet files in GCS = smaller objects.
- **NRTI request: 6–12 each.** Sized to consumer-team parallelism + ordering-key cardinality (both keys high-cardinality), with 2–3× growth headroom.

### 2.3 Hot-partition & skew analysis
- **AUDIT**: `serviceName/endpoint` cardinality is modest, so a few chatty services can dominate one partition. Accepted because (a) the sink is batch-oriented, not latency-critical; (b) downstream is Parquet/BigQuery analytics where global order is irrelevant; (c) the key mirrors KCQL `PARTITIONBY`. **Fix if a single service ever saturated a partition:** salt the key (`service/endpoint/{shard}`) — sacrificing strict per-endpoint ordering audit doesn't truly need — or null-key round-robin that producer. **Detect** via per-partition messages-in / bytes-in + per-partition lag (one partition hot, its task lagging while others idle). You can't fix skew by adding partitions alone if the key concentrates — the hash still lands the hot key on one partition.
- **NRTI**: `messageId`/`tripId` are high, uniform cardinality ⇒ even spread, scales fine.

### 2.4 Ordering — what's actually guaranteed
- **AUDIT**: per (service, endpoint) — ordered for any single API's audit trail. No global cross-service ordering (correct: an audit trail is meaningful per-resource, not as one global stream). At-least-once sink ⇒ a duplicate may appear in GCS; treat the trail as ordered-with-possible-dups and dedup on a record id if strict.
- **NRTI DSC**: per-trip ordering preserved (same `tripId` → same partition).
- **NRTI IAC**: **no ordering** at all (null key).
- **Retry/idempotence ordering caveat (both producers):** with `retries>0`, `idempotence=false`, and default `max.in.flight=5`, a retried earlier batch can land after a later one and reorder *within* a partition. Mitigated by consumer-side reconciliation on `messageId`/`tripId`. Turning on `enable.idempotence=true` *preserves* ordering even with retries and in-flight>1 — which is exactly why it's the top recommended change.

---

## 3. Consumers & consumer groups

### 3.1 The audit 3-connector design
The sink is **Kafka Connect** (Lenses `io.lenses.streamreactor.connect.gcp.storage.sink.GCPStorageSinkConnector`), **not Spring**. THREE connector instances all subscribe to the SAME topic (`kc_config.yaml:63-115`):
- `audit-log-gcs-sink-connector` (US, **also the permissive catch-all** including header-less records)
- `audit-log-gcs-sink-connector-ca` (CA, strict)
- `audit-log-gcs-sink-connector-mx` (MX, strict)

Each `tasks.max=1` ⇒ **3 sink tasks = 3 consumers**. Each connector is its own consumer group (`connect-<connector-name>`, implicit Connect behavior) ⇒ the topic is read **3×** = **3× read amplification**.

**Why 3 connectors, not one branching connector?** Geo isolation + per-country operability: separate consumer groups, offsets, lag, RETRY behavior, and failure domains — a bad CA filter or CA-side GCS outage can't stall US/MX. The Lenses GCS sink also can't cleanly fan one record to 3 different buckets+datasets with 3 different KCQL statements in one task. Cost = 3× broker fetch (~70 eps / ~700 peak), negligible for a 3-broker cluster.

**Is 3× read amplification a problem?** No — at 23 eps avg the saved bandwidth is worth far less than the operational isolation. Revisit single-connector-with-routing only at much higher volume.

### 3.2 Connect coordination vs data groups
- 1 **worker coordination group**: `group.id = kcaas-audit-logs-gcs-sink-connector` (`env_properties.yaml:30/58/86/113/140`) — cluster coordination, NOT a data-consumer group.
- 3 **data consumer groups** (one per connector) — the 3× read.
- 3 **internal topics**: `api_logs_audit_prod-prod-{config,offset,status}`.

### 3.3 `tasks.max = 1`
`tasks.max = min(partitions, desired_parallelism)`. At 23 eps avg / 230 peak one task drains the topic with huge headroom (`max.poll.records=50`, work = cheap SMT filter + batched Parquet write). One task also means single-threaded, in-order, simple offset management. Ceiling: one task owns ALL partitions, so raising partitions later requires raising `tasks.max` too. Stay at 1 until lag (alert >100) says otherwise; scale path = raise `tasks.max` up to partition count, never beyond (extra tasks sit idle).

### 3.4 Consumer poll/session/heartbeat tuning (`kc_config.yaml:42-53`)
| Knob | Value | Why |
|---|---|---|
| `max.poll.records` | **50** | Small batch keeps each poll well under `max.poll.interval` even when a GCS flush + Parquet encode is slow; KCQL flush thresholds (not poll size) control GCS batching. |
| `max.poll.interval.ms` | **300000 (5m)** | Generous headroom for a 50MB Parquet flush + GCS upload + RETRY(5)×5s without being evicted. |
| `session.timeout.ms` | **15000** | 3 missed heartbeats before declared dead. |
| `heartbeat.interval.ms` | **5000** | Standard 1:3 ratio with session timeout — fast failure detection without flapping on a brief GC pause. |
| `request.timeout.ms` | **60000** | Per-request RPC bound (mirrored under `consumer.*`). |

### 3.5 Rebalancing — cooperative
`partition.assignment.strategy` is commented out ⇒ Connect default `[RangeAssignor, CooperativeStickyAssignor]` ⇒ negotiates to **cooperative (incremental)**. Avoids stop-the-world revoke-everything, so restarting/deploying a worker doesn't pause all 3 country sinks at once. With `tasks.max=1` per connector, rebalances are rare (only worker restart/deploy).

### 3.6 Why Connect, not a Spring consumer?
Pure topic→object-store ETL: batching, Parquet encoding, retries, DLQ, offset management — all declarative via KCQL with zero bespoke consumer code. A Spring consumer would re-implement batching, Parquet writing, GCS retry, and DLQ by hand. Trade = less control over threading/rebalance + bound to the connector's at-least-once. My only custom code is the 3 small country Filter SMTs.

### 3.7 Connect offset management & guarantee
Connect commits consumer offsets **after** records are successfully delivered to GCS, so on a crash it resumes from the last committed offset — **at-least-once into GCS**: a crash mid-flush re-delivers a batch ⇒ duplicate rows in Parquet. RETRY(5) + DLQ keep transient/poison failures from losing data. Duplicate audit rows are tolerable and dedupable in BigQuery. Not exactly-once.

---

## 4. Producer configuration — every knob, audit vs NRTI

### 4.1 NRTI producer (CONFIRMED, `nrtKafkaConfig.json` + `ccm.yml`)
| Knob | Value | Why / alternative / tradeoff |
|---|---|---|
| `acks` | **all** (`ccm.yml:172`) | IAC is a financial mutation; acks=all + RF3 + ISR2 = zero acked-loss on 1 broker failure. acks=1 risks loss on leader death pre-replication; acks=0 fire-and-pray. Cost = latency, fine because publish is async to the user. |
| `retries` | **10** (`ccm.yml:192`) | 10 × backoff absorbs leader elections/ISR shrink within the 5-min `request.timeout`, then app-level region failover. Bounded (not MAX_INT) so a poison send can't block a request thread forever. **TEST config uses 2147483647 — test-only; would be catastrophic in prod with a blocking `.join()`.** |
| `enable.idempotence` | **false** (`ccm.yml:197`) ⇒ **at-least-once** | Consumers dedup on `messageId`/`tripId`. **Top recommended change**: flip to `true` — free with acks=all on modern brokers, eliminates dup + restores per-partition ordering at no throughput cost. |
| `request.timeout.ms` | **300000 (5m)** (`ccm.yml:187`) | Let retries exhaust against a flaky broker before failing over. Tension: IAC `.join()` blocks a servlet thread, so a 5-min hang pins a thread — I'd decouple with a tighter `delivery.timeout.ms`. (Test: 30000.) |
| `batch.size` | **8192 (8KB)** (`ccm.yml:182`) | Low-volume latency-sensitive single events; large batches just add latency waiting to fill. 8KB ≈ one event, still gets lz4 + coalescing. |
| `linger.ms` | **20** (`ccm.yml:177`) | 20ms micro-linger coalesces concurrent events (fewer requests, better compression) at trivial latency. 0 = lowest latency/worst batching; 100ms+ breaks the near-real-time feel. |
| `compression.type` | **lz4** (`ccm.yml:167`) | Best speed/ratio for repetitive JSON; lower CPU than gzip (matters on a CPU-scaled hot path), better ratio than snappy. zstd compresses harder but costs more CPU. Cuts cross-region egress on failover. |
| `max.request.size` | **10000000 (10MB)** (`ccm.yml:162`) | DSC/IAC payloads can exceed 1MB default (many destinations/loads/packs/line items). Must stay ≤ broker `message.max.bytes` / `replica.fetch.max.bytes` (KaaS-side — confirmed with platform). (Test: 100000.) |
| key serializer | StringSerializer | Key is a string. |
| value serializer | Spring `JsonSerializer` (`NrtKafkaProducerConfig.java:111-112`) | No Schema Registry — point-to-point, stable POJOs, debuggable with console consumer. Cost = no enforced schema compatibility. |

### 4.2 AUDIT producer (CONFIRMED: NONE explicitly set)
`KafkaProducerConfig.java` `populateConfigProperties()` (lines 85-119) sets ONLY: `bootstrap.servers`, key=`StringSerializer`, value=`KafkaAvroSerializer`, `schema.registry.url`, `auto.register.schemas=false`, optional SSL. **No acks/retries/idempotence/linger/batch keys.** ⇒ **Kafka client defaults apply: acks=1, default retries, idempotence off.**

**The CCM trap:** NON-PROD ccm *defines* `acks=all`, `retries=10`, `lz4`, `linger.ms=20`, `batch.size=8192`, `request.timeout.ms=300000`, `max.request.size=10000000` (lines 56-85) — BUT the `AuditLogsKafkaCCMConfig` interface only exposes `brokerUrls/topic/schemaUrl/sslEnabled`, so **those tuning keys are never read and do NOT take effect**. PROD ccm doesn't even define them. The honest framing: *those numbers represent my intended tuning, captured in CCM, that still needs to be wired into the producer factory.*

**Why acks=1 is defensible (and the gap):** audit is observability data, not source-of-truth (durability lives in GCS/BigQuery). acks=1 trades a tiny single-broker-loss window for lower latency and less back-pressure on request-path threads. BUT for compliance data I'd want acks=all + idempotence; the fix is two lines (expose the CCM props, put them in `configProps`) and it's the **single highest-value reliability change**.

**Avro + `auto.register.schemas=false`:** producer must fetch/validate the schema id from the registry to serialize. `auto.register=false` prevents a drifting producer from silently registering a new schema version and forking the Parquet/BigQuery contract — schema changes go through a governed out-of-band process. Confluent client caches schema ids in-process so steady-state doesn't hit the registry per message. The registry is a SPOF on both ends (serialize/deserialize); combined with the fire-and-forget unbounded pool, a registry stall backs up threads *invisibly*.

### 4.3 HTTP contracts & async dispatch
- **AUDIT**: `POST v1/logRequest` returns **204 No Content**, fire-and-forget (`AuditLoggingController` 44-46/58-60). The 204 means "accepted into the in-process queue," NOT durability — the async send hasn't run yet. Dispatched into `Executors.newCachedThreadPool()` (**UNBOUNDED**, `ExecutorPoolService.java:10`) from `LoggingRequestService` 38-40.
- **AUDIT produce failure handling**: `kafkaPrimaryTemplate.send()` wrapped in a sync try/catch that **only logs** (`KafkaProducerService` 44-51). **No secondary re-send.** Worse — the try/catch around an *async* `.send()` only catches serialization/buffer-alloc errors on the calling thread; broker-side failures/timeouts complete the future *later* and slip past it. False sense of safety. Fix = attach a callback (`whenComplete`/`addCallback`) and hook secondary failover there.
- **AUDIT two-template gap**: `kafkaPrimaryTemplate` + `kafkaSecondaryTemplate` both built (`KafkaProducerConfig` 52-63) and autowired, but only primary is used in the send path — secondary is dead code. Unlike NRTI.
- **NRTI IAC**: `kafkaPrimaryTemplate.send()`; on the `CompletableFuture.exceptionally` → `handleFailure()` re-sends via **secondary-region** template; whole chain `.join()` **blocks the request thread**; on total failure throws `NrtiUnavailableException`. Maps to **HTTP 500** (`@ResponseStatus(INTERNAL_SERVER_ERROR)`, `NrtiUnavailableException.java:14`) — note OpenAPI annotates **503** (`IacControllerV1:58`), a doc/behavior mismatch I'd fix (503 is the correct retryable status).
- **NRTI DSC**: `kafkaDscPrimaryTemplate.send()`; `.exceptionally` → secondary; **NO `.join()`** ⇒ fire-and-forget; service catch block swallows the exception (`NrtiStoreServiceImpl` 784-793) and the controller returns **201 Created unconditionally** (`NrtiStoreControllerV1` 451 & 483). ⇒ silent loss if both regions fail. Fix without breaking the 201 SLA: transactional **outbox** — persist failed DSC to Postgres (15-conn Hikari pool already there) + background relay.

---

## 5. Replication, ISR & durability

| Property | Value | Source / honesty |
|---|---|---|
| `replication.factor` | **3** (requested/assumed) | NOT in repo — KaaS topic property. Inferred from 3 broker hostnames/region (`nrtKafkaConfig.json:11-20`). RF=3 survives 1 broker loss with quorum; the only defensible choice for audit-of-record + financial inventory actions. RF=2 can't satisfy min.insync=2 during any single failure; RF>3 wastes disk at 3 brokers. |
| `min.insync.replicas` | **2** (requested, with RF=3) | NOT in repo — broker/topic level. With RF=3, a write needs 2 of 3 in-sync ⇒ durable through one broker outage, still writable. min.insync=3 blocks all writes on any single broker loss (too brittle); min.insync=1 defeats acks=all. |
| Broker count | **≥3 per region** | Each region's bootstrap list = 3 hostnames. Exact total beyond that is a platform detail; 3 is the floor, consistent with RF3. Bootstrap is a load-balanced/round-robin DNS name per region. |

**What "zero data loss" actually needs:** acks=all **AND** RF≥3 **AND** min.insync.replicas≥2, together. Each acked write is then persisted on ≥2 brokers before the producer proceeds.
- **NRTI** has this on the produce side (acks=all set) *assuming* min.insync=2 is provisioned — I'd confirm with platform; if it were 1, acks=all degrades to acks=1 durability.
- **AUDIT** does **NOT** — acks defaults to 1, so min.insync is moot on its write path. This is the honest gap.

**DR / cross-region replication mechanism (MirrorMaker2? Brooklin?): NOT in repo.** Platform-managed. At the application layer my active/active story is the producer dual-template failover (in NRTI code). Whether the two regional clusters mirror at the broker layer is a platform concern I didn't own.

---

## 6. Retention, DLQ, replay & reprocessing

### 6.1 Retention (NOT in repo — KaaS topic config)
- **Sizing**: `disk = eps × avg_msg_size × retention_seconds × RF`. Audit at 3 days, RF3, 500B: `23 × 500 × 259200 × 3 ≈ 8.6 GB` avg, low tens of GB at peak — tiny.
- **AUDIT request: 7 days** (or as low as 3). Kafka is a transient buffer; source of truth is GCS Parquet + BigQuery (sink lands data within 10 min via `flush.interval=600`). 7 days lets me replay a full week if the sink is down or a Parquet batch is bad. Longer buys little — reprocessing reads from GCS, not Kafka.
- **NRTI request: 3–7 days** — cover the worst plausible downstream (Enterprise Inventory) outage + replay margin. If indefinite replay were needed, argue for **log compaction** keyed on `tripId`/`messageId` instead of time retention.

### 6.2 DLQ (AUDIT sink)
- `errors.tolerance=all`, `errors.deadletterqueue.context.headers.enable=true`, DLQ `api_logs_audit_prod_DLQ` (`kc_config.yaml:69-70`).
- `errors.tolerance=all` ⇒ a record that fails Avro deserialization or an SMT is routed to the DLQ **with context headers**, not stalling the task (no head-of-line block on the audit feed). Tradeoff: it can silently divert volume to the DLQ ⇒ **alert on DLQ depth**.
- **All 3 connectors share ONE DLQ** — good (one place to inspect) but loses per-country attribution unless you rely on the `context.headers` (which is why that flag matters). Don't split into 3 unless triage volume demands it.

### 6.3 RETRY policy vs DLQ (different failure types)
- `connect.gcpstorage.error.policy=RETRY`, `connect.gcpstorage.max.retries=5`, `connect.gcpstorage.retry.interval=5000ms` (`kc_config.yaml:71-73`) handles **transient SINK-side** failures (GCS 5xx, throttling, timeouts) by retrying the GCS write before failing.
- DLQ (`errors.tolerance=all`) handles **per-RECORD** failures (deserialization/SMT). They don't overlap: RETRY = write target, DLQ = record content.

### 6.4 Replay & reprocessing
- **Recent gap (within retention)**: reset the specific connector's consumer-group offsets (e.g., to a timestamp), re-consume, re-write to GCS. At-least-once ⇒ duplicates, dedup in BigQuery.
- **Aged out of Kafka**: source of truth is GCS Parquet ⇒ reprocessing is a GCS/BigQuery job, not a Kafka replay.
- **Targeted (e.g., only CA records from last Tuesday)**: cleanest is downstream — CA Parquet is already `PARTITIONBY service_name, _header.date, endpoint_name`, so last Tuesday's CA data is a date-partitioned prefix in `audit-api-logs-ca-prod`; just re-run the BigQuery load over that `_header.date` partition, no Kafka involved. Other 2 connectors untouched (independent groups). If re-deriving through the sink, reset only the CA connector's offsets to Tuesday's timestamp, only if inside retention.

---

## 7. Throughput & latency math

### 7.1 events/day → eps
- **AUDIT**: ~2M+ events/day ÷ 86,400 = **~23 eps average**. Average lies — design for peak. Assume 5–10× business-hours concentration ⇒ **~100–230 eps peak**.
- **NRTI**: similar order of magnitude — ~23 eps avg, ~100–230 eps peak.

### 7.2 eps → bytes/sec → disk
- Audit Avro ≈ 500B–2KB (estimate, not measured). At 500B: `23 × 500 ≈ 11.5 KB/s` avg, ~115 KB/s at 10× peak.
- Disk (3-day RF3): `11.5KB/s × 259200 × 3 ≈ 8.6 GB`. Confirms retention is cheap.

### 7.3 P99 latency budget
- **NRTI IAC** (on critical path, blocks on `.join()`): steady-state P99 = single-digit-to-low-tens of ms (`linger.ms=20` adds ≤20ms; acks=all adds one replication round-trip). The 5-min `request.timeout` only bites during a broker outage, when it fails over to secondary.
- **AUDIT**: produce is off the request thread (async pool), so it doesn't touch the caller's P99 at all (204 returns immediately).

### 7.4 GCS file-count / flush math (AUDIT sink)
KCQL prod (`env_properties.yaml` prod blocks): `STOREAS PARQUET`, `flush.size=50000000 (50MB)`, `flush.count=5000`, `flush.interval=600 (10 min)` — whichever fires first writes a Parquet object. (dev: `flush.size=5242880`/5MB, no flush.count.)
- At 230 eps peak split across US/CA/MX × EUS2/SCUS, no single country/region hits 50MB or 5000 records in 10 min ⇒ **the 600s timer dominates**.
- Objects/day/country/region = `86400 / 600 = 144`. Across 3 countries × 2 regions ≈ **~864 objects/day** under the timer, each a 10-min Parquet batch.
- Worst case all 2M in one country: `2,000,000 / 5000 = 400 objects/day` from `flush.count` — still MB-scale.
- **This is the math that justifies the 10-min timer:** it caps object count and keeps each Parquet file MB-sized, avoiding the **small-file problem** (tiny files inflate GCS listing + per-file read overhead + BigQuery external-table scan cost). Trade = up to 10-min freshness lag. Drop `flush.interval` if fresher data is needed (more, smaller files).
- `PARTITIONBY service_name, _header.date, endpoint_name` ⇒ BigQuery external tables **partition-prune**: a query filtered to one service/date scans only that prefix. Mirrors the Kafka key. `_header.date` (yyyy-MM-dd, **GMT**) comes from the `InsertRollingRecordTimestampHeaders` SMT, which runs **before** the Filter SMT so surviving records carry the date stamp; GMT keeps all 3 countries on one consistent date boundary.

---

## 8. Scaling & capacity planning

### 8.1 HPA
| Service | Prod | Non-prod | Source |
|---|---|---|---|
| `audit-api-logs-srv` | min **4** / max **8** @ cpuPercent 60, req CPU 1 / mem 1Gi, lim CPU 2 / mem 2Gi | min 1 / max 2, 250m–500m | `kitt.yml` 409-418 / 94-104 |
| `cp-nrti-apis` | min **4** / max **8** @ 60% per brief; **committed prod `kitt.yml` = min 6 / max 12** (478-487, iacprod 586-595); 4/8 is the **stage** profile (156-159) | dev 2/4; iacstage & sandbox 1/2 | `kitt.yml` |
| AUDIT sink Connect worker | min=max=**1 per region** (single fat worker), req CPU 10 / mem 10Gi / eph 15G, lim CPU 12 / mem 12Gi / eph 20G, `KAFKA_HEAP_OPTS -Xmx7g -Xms5g` G1GC | stage 1 worker, 1-2 CPU, 1024-5120Mi | `kitt.yml` 199-212 / 247-260 / 40-49 |

**Why min 4?** 2-region × 2-pod redundancy — survive an AZ/region drain and still serve baseline, never a SPOF, keep both regions warm in active/active.
**Why cpuPercent 60?** Leaves 40% headroom to absorb a burst during the ~30–60s a new pod takes to become ready, so we scale out before saturation.
**Why max 8 (or 12)?** 2× burst, matched to 5–10× business-hours peak. For NRTI, threads sit *blocked* on `.join()`/`.block()`, so you need more pods than pure CPU math suggests — hence min was doubled to get max.
**CPU is NOT the ideal signal for NRTI** (thread-blocked, not CPU-bound). Better: Tomcat thread-pool utilization, in-flight request count, or RPS via a KEDA/custom metric; keep CPU as a backstop. We already export `tomcat_sessions_*` and `hikaricp_connections_*`.
**Connect sink is NOT HPA'd** — you scale Connect by `tasks.max` + worker count deliberately, because autoscaling triggers rebalances that disrupt all sinks. 7g heap sized for Parquet buffering (3 connectors each buffering up to 50MB + Avro decode). Single worker/region is mitigated by active/active (effectively 2 workers, each drains its own region).

### 8.2 Thread-pool sizing — Little's Law
> `concurrency L = arrival_rate λ × service_time W`

- **Audit capture @Async pool (common-lib, `AuditLogAsyncConfig.java`)**: core **6** / max **10** / queue **100** / **AbortPolicy** — the **CORRECT** pattern. `L = 23 × 0.03 ≈ 0.7` threads avg, ~7 at 10× peak. Core 6 covers steady state, max 10 covers peak, queue 100 absorbs micro-bursts, AbortPolicy **sheds load** (drops the audit event, throws) rather than blocking the business request thread — right for non-critical telemetry. When the queue fills → `RejectedExecutionException` → event dropped, business call protected. If audit were compliance-critical, switch to CallerRunsPolicy or a local outbox.
- **Audit-srv `ExecutorPoolService` = `Executors.newCachedThreadPool()` — UNBOUNDED (the WRONG one).** Max pool = `Integer.MAX_VALUE`, `SynchronousQueue` (tasks can't queue). If Kafka/Schema-Registry slows, sends back up, threads spawn without limit → **OOM/thread exhaustion**. HPA on CPU won't catch it (threads are *blocked*, not burning CPU) — the worst kind of failure: invisible. **Fix**: bounded `ThreadPoolExecutor` (core ≈ #CPU, capped max, bounded `ArrayBlockingQueue`, CallerRuns/Abort policy) — copy the common-lib 6/10/100 template so overload fails fast (could surface 503) instead of melting down.

### 8.3 NRTI thread-occupancy risk (Little's Law in reverse)
The EI read path (`HttpServiceImpl` 80-94): WebClient `.timeout(10s)` + `Retry.backoff(3, 100ms, max 2s)` + `.block()` pins a servlet thread up to ~10s/attempt, worst case ~20–30s/request. Tomcat ~200 threads ⇒ ceiling ≈ `200 / 10 = 20` concurrent EI-bound requests before the pool fills. At a 10× peak with a slow EI, the pool saturates and **every** endpoint on that pod queues. Mitigations: conservative 60% CPU to scale early, short DB timeouts (conn 2s / socket 5s), and ideally **tighten EI per-attempt timeout to 2–3s + go non-blocking** so a slow EI doesn't consume threads 1:1.

### 8.4 DB connection math (NRTI Hikari, `ccm.yml` 877-915)
`maximumPoolSize=15`, `minimumIdle=10`, `connectionTimeout=2s`, `validationTimeout=1s`, `socketTimeout=5s`, `idleTimeout=120s`. **12 pods × 15 = up to 180 connections** — must stay under the Azure Postgres Flexible Server `max_connections` (+ headroom for other clients). If undersized, pods at max scale get connection-refused → `hikaricp_connections_timeout_total` climbs → 5XXs. minIdle 10 keeps connections warm; connTimeout 2s fails fast so DB pressure doesn't cascade into thread-pool exhaustion. **Pod count and DB max_connections are coupled capacity decisions.**

### 8.5 "Size this for 10× / 100×"
- **10× audit (~230 eps avg, ~1–2k peak)**: still small. Order: (1) watch lag — don't repartition reflexively; (2) if a task lags, raise partitions **AND** `tasks.max` together; (3) maybe add a 2nd Connect worker/region; (4) flush thresholds (50MB/5000) now fire before the timer — fine, better freshness; (5) bound the producer pool + acks=all; (6) re-check broker disk vs 7-day retention. Do reliability (5) + observability **before** raw scaling. Bump HPA max to 12–16 if CPU headroom needs it. **Kafka partition count is the LAST lever, not the first.**
- **100× audit (~2300 eps avg, 10–20k peak)**: a real stream → **architecture review**. (1) partitions become a genuine throughput lever; (2) single-task-per-connector breaks → raise `tasks.max` to partition count, probably a dedicated Connect cluster; (3) acks=1 + unbounded pool become liabilities → bounded pool + reconsider batching; (4) 3× read amplification now matters → consolidate to one demuxing consumer or split into per-country topics; (5) GCS small-file pressure → tune flush; (6) re-examine the `serviceName/endpoint` key for hot partitions (salt the dominant service).
- **NRTI 10×**: the **servlet thread pool breaks first**, not Kafka. Plan: (1) raise HPA max + switch autoscale signal to thread/RPS; (2) non-blocking failover / shorter `delivery.timeout`; (3) tighten EI timeout, go non-blocking; (4) then partitions/consumers if lag appears.

---

## 9. DR / multi-region ops — failover mechanics & RPO/RTO honesty

**Setup**: active/active across EUS2 + SCUS on `kafka-v2-luminate-core-{stg|prod}`, port 9093, mTLS at Istio. Broker lists **swapped per region**: pods in EUS use EUS=primary, SCUS=secondary; pods in SCUS swap them (`cp-nrti ccm.yml configOverrides` 805-852; audit `PROD-1.0-ccm.yml` 60-81). Prod clusters: `eus2-prod-a30`, `scus-prod-a63`.

**NRTI failover (in code, working):** `NrtKafkaProducerServiceImpl` — IAC sends to primary template (line 69); the `CompletableFuture.exceptionally` (line 84) → `handleFailure()` re-sends to `kafkaSecondaryTemplate` (line 161); `.join()` (line 89) blocks until primary-or-secondary resolves; total failure throws `NrtiUnavailableException` (HTTP 500). DSC has the same primary/secondary structure but fire-and-forget.

**AUDIT failover (NOT working — dead code):** both templates built + autowired, but `KafkaProducerService` only ever calls `kafkaPrimaryTemplate.send()` and logs on failure (47-51). Secondary never invoked. ⇒ On a primary-region Kafka outage, EUS pods **log-and-drop**; the unbounded pool backs up; SCUS pods keep working. **Fix**: port NRTI's secondary-template failover (the template is already wired — it just needs the fallback call on the send-future's failure callback).

**Blast radius if EUS2 Kafka goes fully down:**
- **NRTI**: EUS pods fail primary → spill to SCUS (added latency + cross-region egress); SCUS pods unaffected. Not an outage — that's the point of active/active. Risk: IAC `.join()` waits through the primary failure before failover, raising thread occupancy on EUS pods → want a tight `delivery.timeout`. Confirm SCUS alone has capacity headroom for full failover.
- **AUDIT**: partial loss for EUS-resident pods (no failover today). Durable backstop = GCS, written from whichever region stayed up.

**RPO/RTO honesty:** my application-layer guarantee is that **new** writes survive a regional outage via failover. Whether **pre-outage** topic data mirrors across regions is platform-managed broker-layer replication I did **not** own — I wouldn't claim it. The clusters are independent; each region's sink drains its own cluster.

**Deploy safety (NRTI, `kitt.yml`):** `preStop sleep 30` (Istio sidecar drain, line 647); startupProbe wait 30/interval 5/ft 24; liveness 10/ft 5; readiness 5/ft 5 (699-720). **Flagger canary** (726-748): stepWeight 10 → maxWeight 50, interval 2m, progressDeadline 600s, auto-rollback if 5XX rate >1% over 2m; `rollbackOnError: true` (427). A bad deploy is caught at 10% traffic. Gap: async sends not yet acked at SIGTERM could be lost — the 30s drain mitigates, and the IAC `.join()` actually helps (won't return until the send completes).

**Security:** port 9093 is the secured listener but the app/Connect speaks **PLAINTEXT** to its local Istio sidecar (`kc_config.yaml:14` `security.protocol=PLAINTEXT`; `auditLoggingKafkaSslEnabled=false` / `nrtKafkaSslEnabled=false` in prod CCM) — **mTLS terminated at the sidecar**. The in-app JKS keystore/truststore branch is a fallback that's off in prod (code comment: "mTLS is enforced for Kafka connections"). Keeps cert rotation out of the app.

---

## 10. Monitoring & on-call

**Consumer-lag alerts (AUDIT, `kafka-consumer-lag-alerts.yaml`):** warn `lenses_topic_consumer_lag > 100` for 5m, critical `> 500` for 5m (PromQL expr lines 14/28). At 230 eps, lag 100 = <0.5s behind, 500 = ~2s — early-warning thresholds. **Page on critical** (stuck sink → BigQuery freshness SLA at risk). **Known cleanup**: the alert *message text* says 50/100 but the *expr* says 100/500 — a real text/expr mismatch I'd fix.

**Metrics exported (NRTI `kitt.yml` 749-811, `/actuator/prometheus`):** `http_server_requests_seconds_*` (latency/RPS), `http_client_requests_seconds_*` (downstream EI/Kafka), `jvm_threads_*` (the blocked-thread signal that actually predicts saturation), `hikaricp_connections_*` (pending/active/timeout_total — DB pressure), `tomcat_sessions_*`, `jvm_gc_*`, `process_cpu_usage`.

**Capacity dashboard (the load-bearing panels):**
- **Producer**: send rate + error rate per region, **region-failover count** (the "Failed to Publish in Primary... trying in Secondary" warning — `NrtKafkaProducerServiceImpl` 85/122), produce P99, IAC 503/500 rate, 204 throughput (audit ingress proxy).
- **Topic**: per-partition messages-in + lag, under-replicated partitions, ISR shrink.
- **Sink**: per-connector lag (`lenses_topic_consumer_lag`), task status, **DLQ depth/rate per country** (spike = filter/deserialization failures), `connect.gcpstorage` RETRY counts, flush rate + object-size distribution, BigQuery freshness (time since last Parquet landed).
- **Pod**: CPU vs 60% target, pod count vs min/max, **thread-pool active + rejection count** (catches the unbounded-pool blowup).
- **Cross-cutting**: Schema Registry latency/error (SPOF), rate of **header-less records hitting the US catch-all** (data-residency).

**What pages:** DLQ depth growing, lag crossing threshold + trending up, under-replicated/ISR<min.insync, Connect task FAILED, IAC error-rate elevated, region-failover count spiking, thread-pool rejections >0, pod stuck at max replicas with CPU pinned.

**The single best "is the producer in trouble?" panel (NRTI):** secondary-failover rate + `jvm_threads_live_threads` + p95 `http_server_requests` latency. Tells you in one glance: healthy / degraded-but-coping (failover firing, threads fine) / heading-for-saturation (failover firing AND threads climbing).

**Tooling honesty:** lag was watched via the platform's Kafka observability (Lenses / managed-kafka-consumer-service); real prod EPS comes from Dynatrace/Prometheus — the repo doesn't commit measured prod throughput or a specific lag SLO number.

---

## 11. FULL rapid-fire ops Q&A (grouped by category)

### Topics

**Q: How many Kafka topics does the audit pipeline use, and why one not topic-per-service or topic-per-region?**
One business topic `api_logs_audit_prod` + DLQ `api_logs_audit_prod_DLQ` (`PROD-1.0-ccm.yml:41`). Audit is one homogeneous event type — one Avro `LogEvent`, one ingest API. Topic-per-service multiplies partitions/RF/offset metadata by N for zero schema benefit and pushes routing into the producer; topic-per-region is unnecessary because geo is a SINK concern (wm-site-id + Filter SMT). One topic, env-suffixed, keeps the producer trivial.

**Q: How many topics on the NRTI side and why two?**
Two: `cperf-nrt-prod-iac` + `cperf-nrt-prod-dsc` (`ccm.yml:132/202`). Split by domain/criticality — IAC is a system-of-record inventory mutation (sync-with-failover, caller-visible failure), DSC is best-effort freight (fire-and-forget). One topic would force one retention/partition/group policy on opposite-criticality workloads.

**Q: How does geo-routing actually work in the audit sink?**
Producer copies `wm-site-id` into headers. Each connector runs a Filter SMT after the timestamp SMT (FilterUS/CA/MX). CA/MX are strict (`BaseAuditLogSinkFilter.verifyHeader` exact match, 52-63). US is the catch-all (`AuditLogSinkUSFilter` 47-49) — passes if `wm-site-id==US` OR no header (`noneMatch`). Each connector writes only its country's records to `audit-api-logs-{us|ca|mx}-prod`.

**Q: Why is the US connector the catch-all and what's the risk?**
US `verifyHeader` has an extra OR clause (passes header-less records); CA/MX require exact match. Benefit: no record silently dropped — always a home. Risk: data-residency — a CA/MX record that lost its header lands in the US bucket. Monitor the header-less→US rate; a spike = producer bug.

**Q: End-to-end path of one audit event?**
Business service fires on its bounded @Async pool (6/10/100) → audit-srv serializes Avro (schema-validated), keys `service/endpoint`, produces to `api_logs_audit_prod` with `wm-site-id` header → 3 Connect connectors consume, stamp date header, filter by country, batch-write Parquet to per-country GCS buckets on flush thresholds → BigQuery external tables over the buckets. DLQ catches bad records; RETRY handles transient GCS errors.

**Q: End-to-end path of one IAC event?**
API call into cp-nrti → may read Enterprise Inventory via reactive WebClient (10s timeout, Retry 3×, `.block()`) → builds JSON `IacKafkaPayload` keyed `messageId` → produce to `cperf-nrt-prod-iac` primary template with acks=all; on failure `.exceptionally` → secondary region → whole thing `.join()`ed so the HTTP response blocks until success or 500/503 → downstream consumers dedup on `messageId`.

**Q: Why route geo in the sink, not the producer?**
Keeps the producer geo-agnostic and the topic single. Producer just emits with a `wm-site-id` header. Adding a country = a Connect-config change, not a producer redeploy; per-country data residency (separate buckets/projects) is enforced at the storage boundary where it belongs.

### Partitions

**Q: What's the partition key for each topic and what does it give you?**
Audit: `serviceName/endpoint` → per-(service,endpoint) ordering, mirrors KCQL PARTITIONBY. DSC: `tripId` → per-trip ordering. IAC: **null key** → sticky/round-robin, no ordering. The keys also serve as dedup tokens downstream (messageId for IAC, tripId for DSC).

**Q: Does IAC have ordering guarantees? Be precise.**
No, not at the broker level. `IacServiceHelper` sets a `MESSAGE_ID` header but not `KafkaHeaders.KEY`, so records spread across partitions by the sticky partitioner — two events for the same store/GTIN can land on different partitions and be consumed out of order. Fix: set `KafkaHeaders.KEY = storeNbr` or store+item. Today: "at-least-once with no ordering on IAC; consumers must be order-independent and idempotent."

**Q: How many partitions for the audit topic and how decided?**
Honest: NOT in repo — KaaS-provisioned, my config carries only the topic NAME. Load needs ~1 (23 eps). I'd request **6** for future consumer parallelism (raise `tasks.max` to 6 with no repartition), even broker spread (2 leaders/broker on 3 brokers), headroom (repartitioning a keyed topic breaks ordering).

**Q: Why is partition count a future-proofing decision, not a throughput one?**
2M/day = 23/sec; even 10× peak (230/sec) is thousands of msg/s below one partition + one consumer's ceiling (`max.poll.records=50` polled many times/sec). Adding partitions doesn't help latency/throughput today — it only matters for running >1 consuming task in parallel. And repartitioning a keyed topic reshuffles key→partition and breaks ordering, so over-provision modestly up front.

**Q: If throughput only needs one partition, why request more than one?**
(1) Future consumer parallelism — a group can't exceed partition count, so it's the scaling ceiling; (2) broker spread — RF3 across 3 brokers distributes leadership; (3) even rebalance distribution. Balanced against NOT over-partitioning (more partitions = more open Parquet files = smaller GCS objects).

**Q: Where does an IAC message's partition end up at runtime?**
Null key ⇒ default sticky partitioner picks it (batches to one partition until it fills/lingers, then rotates). Spreads roughly evenly, no relation to messageId/storeNbr/GTIN. The log line (`NrtKafkaProducerServiceImpl` 80-82) prints `metadata.partition()`/`offset()` so I can see the spread. DSC is deterministic: `hash(tripId) % numPartitions`.

**Q: How would adding partitions later hurt you, given your keys?**
DSC breaks: `hash(tripId) % N` — change N and the same tripId maps elsewhere, splitting an active trip's events across old/new partitions → out-of-order during transition. IAC is harmless (null key). That asymmetry is why I over-provision the DSC topic 2–3× up front. If forced to grow DSC partitions: do it in a low-traffic window accepting a brief ordering blip, or new topic + cut over consumers.

**Q: At 100×, would you change the audit partition key?**
Yes, re-examine for hot partitions — `serviceName/endpoint` cardinality is modest, so a few hot endpoints skew. Fix: salt the hot service's key (`service/endpoint/{shard}`, sacrificing strict per-endpoint ordering audit doesn't need) or a higher-cardinality key. NRTI's `messageId`/`tripId` are already high/uniform.

**Q: How do you detect and handle a hot partition?**
Per-partition messages-in/bytes-in + per-partition lag (one partition hot, its task lagging while others idle). Handle by changing key distribution — salt the hot key across partitions, or higher-cardinality key. Adding partitions alone won't fix a concentrating key (hash still lands it on one partition).

**Q: How did you actually arrive at numbers provisioned externally?**
For things in my code (producer tuning, HPA, sink config) I quote exact lines. For KaaS topic settings I'm honest they're not in my repos and defend a value with a formula: partitions from target_eps / per-partition throughput bounded by parallelism + key cardinality; RF3/min.insync2 from durability + the 3-broker topology I can see; retention from replay-need × the disk formula.

### Consumers

**Q: How many consumers read the audit topic?**
Three — Kafka Connect with 3 Lenses GCS-sink connectors (US/CA/MX), each `tasks.max=1` = 3 tasks = 3 consumers, all on `api_logs_audit_prod`. Each connector is its own consumer group ⇒ topic read 3× (3× read amplification).

**Q: Why 3 connectors, not one branching to 3 buckets?**
Geo isolation + per-country operability: separate groups, offsets, lag, RETRY, failure domains — a bad CA filter/GCS outage can't stall US/MX. The Lenses sink can't cleanly fan one record to 3 buckets+datasets with 3 KCQLs in one task. Cost = 3× fetch, negligible at 23 eps.

**Q: What's the read amplification and is it a problem?**
Exactly 3× (3 consumer groups). ~70 eps / ~700 peak of fetch — nothing for a 3-broker cluster. Only a concern at much higher volume; isolation is worth far more than the bandwidth.

**Q: How did you pick `tasks.max=1`?**
`min(partitions, desired_parallelism)`. At 23 eps one task drains with huge headroom (50-record polls, cheap SMT + batched Parquet write). Extra tasks sit idle. Scale path: raise `tasks.max` toward partition count if lag appears.

**Q: Why JSON for NRTI but Avro for audit?**
Audit is long-lived analytics-of-record (Parquet + BigQuery) → strict versioned schema with `auto.register.schemas=false` to prevent uncontrolled evolution. NRTI is point-to-point between known services, stable POJOs → JSON keeps it simple/debuggable. Cost = no enforced schema compatibility. For a higher-fanout topic I'd push for Avro.

**Q: What's the consumer-side contract given idempotence=false?**
Consumers MUST dedup on the business key — IAC on `messageId` (payload + `MESSAGE_ID` header), DSC on `tripId` (key + `TRIP_ID` header). They keep a seen-set/upsert so a replayed/retried event is a no-op. That code is in the consumer services, not my repo — it's the explicit interface obligation that makes at-least-once acceptable.

**Q: Why Connect instead of a Spring consumer (audit)?**
Pure topic→object-store ETL: batching, Parquet, retries, DLQ, offsets — all declarative via KCQL, zero bespoke code. A Spring consumer would re-implement all of it. Trade = less threading control + bound to at-least-once. My only custom code is the 3 country Filter SMTs.

**Q: How does Connect manage offsets, and the guarantee?**
Commits offsets after successful delivery to GCS → resumes from last committed offset on crash → at-least-once into GCS (crash mid-flush re-delivers a batch = duplicate Parquet rows). RETRY(5) + DLQ prevent transient/poison loss. Dedup in BigQuery. Not exactly-once.

**Q: Why `max.poll.records=50`?**
Bounds work between polls so the consumer reliably heartbeats within `max.poll.interval=300000` and isn't evicted. 50 is small on purpose — each record flows through SMT + Parquet batch; KCQL flush thresholds (5000/50MB) control GCS batching, not poll size.

**Q: Consumer count formula?**
`consumers_in_group = min(partition_count, target_eps / per_consumer_eps)`. Hard ceiling = partitions (extra consumers sit idle). Size partitions first (high enough for the parallelism you'll ever need), then set consumer/task count to clear lag, never exceeding partitions. Audit's ratio is <1 → one task/connector; the 3 groups exist for geo fan-out, not throughput.

**Q: How many consumers read each NRTI topic / read amplification?**
On NRTI I'm the producer — consumers are separate downstream services I don't own; I won't claim their count. Consumer parallelism is capped by partition count. No fan-out read-amplification pattern (unlike audit's 3×); iac and dsc each have a dedicated consumer.

### Producer tuning

**Q: Full producer tuning for NRTI and justify acks=all.**
acks=all, retries=10, idempotence=false, request.timeout=300000, batch.size=8192, linger.ms=20, lz4, max.request.size=10000000. acks=all because IAC is an inventory mutation — silent loss corrupts stock; acks=all + RF3 + ISR2 = zero-loss. acks=1 loses on leader death pre-replication; acks=0 fire-and-pray. Cost = latency, fine because publish is async to the user.

**Q: batch.size=8192 / linger.ms=20 — why so small?**
Low-volume latency-sensitive path, not a firehose. A big batch only helps if you have enough events/window to fill it; we don't — we'd just add latency. 8KB ≈ one event, still gets lz4 + coalescing. linger.ms=20 lets a couple concurrent events ride one batch at trivial cost. 0 = lowest latency/worst batching; 100ms+ breaks near-real-time.

**Q: Why lz4?**
Best throughput-to-ratio for JSON (repeated keys). Faster/lower-CPU than gzip (matters on a CPU-scaled hot path), better ratio than snappy. Cuts network egress (cross-region failover) + broker storage. zstd compresses harder but more CPU.

**Q: Why max.request.size=10MB?**
DSC carries many destinations/loads/packs; IAC many line items — tail events exceed the 1MB default (RecordTooLargeException). 10MB is a safe ceiling. Critical pairing: must be ≤ broker `message.max.bytes` / `replica.fetch.max.bytes` (KaaS-side, confirmed with platform).

**Q: idempotence=false — what does it cost?**
At-least-once. With retries=10, a send that times out after the broker persisted it gets retried → duplicate; under retry, ordering within a partition isn't guaranteed either. Safe only because consumers dedup. **Top recommended change**: flip to true — free with acks=all on modern brokers, no duplicates + restored ordering at no throughput cost; consumer dedup becomes defense-in-depth.

**Q: retries=10 — why not more, and what's the test-config trap?**
10 × backoff absorbs leader elections/ISR shrink within the 5-min timeout before app-level region failover. Bounded so a poison send can't pin a request thread forever. The TEST config's `2147483647` is a unit-test fixture — in prod with a blocking `.join()` it would hang a thread indefinitely. Prod's bounded 10 is correct.

**Q: request.timeout.ms=5min — isn't that dangerous?**
It's long so retries exhaust against a flaky broker before failing over. Tension: IAC `.join()` blocks a servlet thread, so a 5-min hang pins a thread — terrible for the pool. Fix: keep a reasonable request.timeout but set a tighter `delivery.timeout.ms` and fail over to secondary fast. For a sync IAC path I'd bias toward "never hang a thread."

**Q: The audit producer — what tuning did you apply?**
None beyond essentials: `KafkaProducerConfig.java` sets only bootstrap, key/value serializer, schema URL, `auto.register.schemas=false`, optional SSL. Client defaults apply: acks=1, default retries, no idempotence. Conscious telemetry-vs-source-of-truth tradeoff — acks=1 trades a tiny loss window for lower latency/less back-pressure. The #1 gap I'd fix.

**Q: If audit acks defaults to 1, what's the loss risk and fix?**
At acks=1 the leader acks before followers replicate, so a leader failover in that window loses the record silently — bad for compliance. Fix: set acks=all + idempotence=true + min.insync=2. The intent is already in the CCM (acks=all declared) but never wired in because `AuditLogsKafkaCCMConfig` only exposes brokerUrls/topic/schema/ssl. Two-line fix: expose those props + put them in configProps.

**Q: Audit endpoint — sync or async, what does the caller get?**
Fire-and-forget, returns **204** immediately. `processLoggingRequest` dispatches the send into a thread pool (`LoggingRequestService` 38-40) and the controller returns 204 before Kafka acks. Decouples callers from Kafka/Schema-Registry latency — right for an audit sidecar — but the 204 is not a durability guarantee.

**Q: What does the 204 actually guarantee?**
Nothing about durability — only that the request was accepted into the in-process queue, not written/acked. A caller seeing 204 cannot assume persistence. Acceptable for a non-blocking sidecar (don't add latency/failure to the business call), but reliability must be enforced inside the producer (acks=all, failover, bounded pool), not signaled to the caller.

**Q: The audit async executor pool and its risk?**
`ExecutorPoolService` = `Executors.newCachedThreadPool()` — UNBOUNDED (max = Integer.MAX, SynchronousQueue). With the 204-immediately controller, a Kafka/Schema-Registry stall backs sends up, threads spawn without limit → OOM. HPA on CPU won't catch it (threads blocked, not CPU). Fix: bounded pool (copy common-lib 6/10/100/AbortPolicy) so overload rejects fast (could surface 503).

**Q: What's the difference between the two audit thread pools?**
Capture pool (common-lib `AuditLogAsyncConfig`, @Async) = bounded 6/10/100/AbortPolicy — correct, protects the business request. `ExecutorPoolService` (audit-srv) = unbounded cached pool — the one to fix. The business↔audit boundary is well-protected; the unbounded one is internal to the audit service, risk contained but real.

**Q: What happens when the capture pool's queue (100) fills?**
AbortPolicy throws `RejectedExecutionException` → the audit event is dropped rather than blocking the business request. Correct for telemetry: audit must never take down the actual API. If compliance-critical, switch to CallerRunsPolicy (back-pressure) or a local outbox.

**Q: The try/catch around an async send — is it catching anything?**
Largely no. `send()` returns a future; the network send is async. A sync try/catch around `.send()` (`KafkaProducerService` 47-51) only catches serialization/buffer-alloc errors on the calling thread — NOT broker-side failures/timeouts/NotEnoughReplicas, which complete the future later. False sense of safety. Fix: attach a callback (`whenComplete`/`addCallback`) — also where the secondary failover hooks in.

**Q: Is the audit two-template (primary/secondary) design fully used?**
No — half-wired. Both templates built (`KafkaProducerConfig` 52-63) + autowired, but `publishMessageToTopic` only calls `kafkaPrimaryTemplate.send()` and logs on failure; secondary is dead code. Fix: on the send-future's failure callback, re-send via secondary — mirroring NRTI. Turns active/active into real cross-region resilience for the audit producer.

**Q: Why CompletableFuture and not sync send or @Async (NRTI)?**
`KafkaTemplate.send()` already returns a CompletableFuture; I chain `.thenAccept`/`.exceptionally` to log success + drive region failover declaratively ("try primary, on failure try secondary, on total failure throw"). For IAC I `.join()` to surface a sync error; DSC deliberately doesn't. `@Async` on a separate pool would decouple from the request thread (better thread occupancy) but lose the sync error for IAC, which is the whole point of the IAC contract.

**Q: Why `auto.register.schemas=false` and what does it protect?**
Prevents a drifting producer from silently registering a new schema version + evolving the topic uncontrolled — risky for an audit feed consumed by a strict Avro sink + BigQuery. False = schemas registered out-of-band through a governed process; an unexpected schema fails fast at serialization. Trade = someone must register schema changes before a producer deploy — exactly the discipline compliance wants.

**Q: linger.ms=20 + lz4 are in the audit CCM — what would they buy if applied?**
linger.ms=20 = up to 20ms batching for throughput at negligible latency (fine for fire-and-forget audit). lz4 shrinks Avro on-wire/on-disk cheaply (fast, low CPU). Both sensible — but declared in NON-PROD CCM and never read, so today the producer sends uncompressed, linger=0. Wiring them in is part of the same fix as acks=all.

**Q: Message size and its effect on batch.size / max.request.size (audit)?**
No measured payload in repo; ~1–2KB/event working estimate. NON-PROD CCM declares batch.size=8192 / max.request.size=10MB but they're unread. If applied: 8KB batch ≈ 4–8 events at linger 20, reasonable micro-batch at 23 eps; 10MB headroom so a large event/burst never gets rejected. Honest framing: intended tuning captured in CCM, still needs wiring.

**Q: Why is the IAC happy path annotated @ResponseStatus(OK) when docs say 201?**
The IAC controller method is `@ResponseStatus(OK)` (`IacControllerV1:123`) while OpenAPI documents 201; the effective status comes from the returned entity, not purely the annotation. DSC is cleanly `@ResponseStatus(CREATED)` + `.status(CREATED)`. Documentation drift on IAC (200 annotated / 201 documented / entity-driven) — I'd reconcile to a consistent 201 for an event-creation endpoint. Contract-cleanliness, not data-loss.

### Replication & durability

**Q: How do you decide RF and what would you request?**
NOT in repo — KaaS topic/cluster property; my config only knows the bootstrap endpoint. Each region's broker DNS fronts a 3-broker cluster, KaaS default RF=3. For audit/compliance + financial inventory, RF=3 is right regardless — survives 1 broker loss with quorum. RF=2 leaves no redundancy during recovery.

**Q: min.insync.replicas and interaction with acks?**
With RF=3, request min.insync=2 — a produce needs 2 of 3 in-sync, durable through one broker outage, still available. Only bites at acks=all. NRTI sets acks=all so it matters there (assuming ISR2 provisioned). Audit runs at acks=1, so ISR is moot until acks=all is wired. min.insync=3 blocks writes on any single broker loss (too brittle); 1 defeats acks=all.

**Q: What does RF3 + acks=all buy for "zero loss," and the gap?**
Every acked write persists on ≥2 brokers before the producer proceeds, so losing any one broker loses zero acked messages and the cluster keeps writing. Cross-region active/active adds region-outage resilience. Gap: RF + min.insync are KaaS-side — I assert RF=3 from 3 broker hostnames + platform standard; I'd confirm min.insync=2 (if 1, acks=all degrades to acks=1 durability).

**Q: How many brokers and how do you know?**
≥3 per region — exactly 3 hostnames in each region's bootstrap list (`nrtKafkaConfig.json:11-20`). Cluster `kafka-v2-luminate-core-{stg|prod}`, EUS2 + SCUS, port 9093, mTLS at Istio. Exact total beyond the bootstrap list is a platform detail; 3 is the floor, consistent with RF3. Bootstrap is a load-balanced DNS name per region.

### Retention

**Q: What retention did you set and why (audit)?**
NOT in repo — KaaS topic config. Request 7 days. Kafka is a transport buffer; source of truth is GCS Parquet + BigQuery (sink lands within 10 min). 7 days lets me replay a full week if the sink's down or a batch is bad. Disk ≈ 230 × 2KB × 86400 × 7 × RF3 ≈ 0.8 TB cluster-wide. Longer buys little (reprocessing reads GCS).

**Q: Retention strategy for NRTI?**
NOT in repo — KaaS. Request ≥24–72h (3–7 days) sized from consumer-outage tolerance + replay margin so an overnight outage or bad-deploy rollback loses nothing. Balance against disk (lz4 helps). For indefinite replay, argue log compaction keyed on tripId/messageId instead of time retention.

### Throughput

**Q: Walk me through the audit throughput math.**
2M+/day ÷ 86,400 ≈ 23 eps avg. Average lies — audit tracks business hours, so design for 5–10× peak ≈ 100–230 eps. Sub-KB Avro. Even peak bytes/sec is well under a single partition's ceiling — throughput was never the binding constraint, which is why partitions are sized on parallelism/durability.

**Q: Compute bytes/sec and disk for retention.**
bytes/sec = eps × avg_msg. At 500B: 23 × 500 ≈ 11.5 KB/s avg, ~115 KB/s at 10×. Disk = bytes/sec × retention_seconds × RF. 3 days RF3: 11.5KB/s × 259200 × 3 ≈ 8.6 GB avg, low tens of GB at peak — tiny. Retention is cheap.

**Q: P99 latency budget on the produce path?**
NRTI IAC blocks on `.join()`, so it's on the critical path: bounded by request.timeout=5min worst case, but steady-state P99 = single-digit-to-low-tens ms (linger ≤20ms + one acks=all round-trip). The 5-min timeout only bites during a broker outage → fail over. Audit produce is off the request thread (async pool) → doesn't touch the caller's P99 (204 returns immediately).

**Q: Do the throughput numbers justify partition/consumer counts?**
They justify keeping both small. 23 eps avg, ~230 peak — one partition + one task absorb it with room (50-record polls many times/sec). Partitions (request 6) are about future parallelism, not load; `tasks.max=1` is intentional. The lag alert (warn 100) tells me if that breaks.

**Q: What load have you tested at?**
Committed stage load test (`perf/wcnp_stage_test_perf_iteration_30users.json`): 15 VUs ramping 5/step, read-heavy weights (TransactionHistory 40, InventoryStatus 20, StoreInbound 20, DC 10, single-GTIN 5, itemValidation 5) plus IAC + DSC capture. Exercises the produce path under concurrent read load — exactly where thread-blocking risk shows. Plus a stage Resiliency (chaos) test. For prod EPS I'd pull Dynatrace; repo doesn't commit measured prod throughput.

**Q: Which side is the bottleneck — producer or consumer?**
Neither is a throughput bottleneck at 23 eps. The binding constraint is durability latency on produce (acks=all + replication for NRTI) and write-flush cadence on consume (Parquet→GCS). The more fragile side is the consume/sink: where lag accumulates, GCS can throttle, DLQ/retry matters. Producers are well-protected by HPA + region failover.

### Scaling / HPA

**Q: How did you size the HPA (min 4 / max 8 @ 60%)?**
min 4 = 2-region × 2-pod redundancy, survive an AZ/region drain, never a SPOF. 60% CPU leaves 40% headroom for the ~30–60s pod-startup window so we scale out before saturation. max 8 = 2× burst for 5–10× business-hours peak. CPU req 1 / lim 2 lets a pod burst to 2 cores. (NRTI prod committed is actually min6/max12; 4/8 is stage.)

**Q: Why scale on CPU 60% — is CPU the right signal?**
For audit it's an honest proxy (serialize-Avro + compress + send is CPU-bound at our volume). For NRTI it's NOT ideal — the real bottleneck is blocked-thread count from `.join()`/`.block()`; a pod can have low CPU with a full servlet pool. Better: thread-pool utilization / in-flight / RPS via KEDA; CPU as backstop. We export `tomcat_sessions_*` + `hikaricp_connections_*` to wire it.

**Q: How are the Connect sink workers scaled — HPA?**
No HPA. Prod = min=max=1 per region (single fat worker, 10-12 CPU, 10-12Gi, eph 15-20G, `-Xmx7g -Xms5g` G1GC). Connect isn't autoscaled on CPU because adding/removing workers triggers rebalances disrupting all sinks; you scale by `tasks.max` + worker count deliberately. 7g heap sized for Parquet buffering (3 connectors × up to 50MB) + Avro decode.

**Q: Single sink worker (min=max=1) — isn't that a SPOF?**
Per region yes, but active/active = effectively two workers (EUS+SCUS), each draining its own cluster, so a single worker failure stalls only that region's sink and Connect restarts the pod. Kept at one/region deliberately (scaling triggers rebalances; 3 lightweight tasks need no more). For in-region HA I'd run 2 workers, accepting the rebalance cost.

**Q: How does the audit HPA handle the unbounded-pool failure mode?**
It doesn't — CPU-based HPA is sized for normal load, not a Schema-Registry stall. Under a produce stall the unbounded pool grows threads/queued tasks while CPU stays low, so the autoscaler won't save it; the pod OOMs/thrashes. The fix is the bounded pool, not more pods.

**Q: Apply Little's Law to size the thread pool.**
`L = λ × W`. Capture pool: λ ≈ 23 eps, W ≈ 10–30ms ⇒ L ≈ 0.7 threads avg, ~7 at 10× peak. The common-lib pool (core 6 / max 10 / queue 100 / AbortPolicy) lines up: 6 core for steady state, 10 for peak, 100 queue for micro-bursts, AbortPolicy sheds beyond. The math validates the config.

**Q: Which thread pool is wrong and why?**
`ExecutorPoolService` = `newCachedThreadPool()` — unbounded (max Integer.MAX, SynchronousQueue). A Kafka slowdown spawns unbounded threads → exhaustion/OOM under back-pressure. Fix: bounded ThreadPoolExecutor sized by Little's Law (core ≈ #CPU, capped max, bounded ArrayBlockingQueue, CallerRuns/Abort). Copy the common-lib 6/10/100 template.

**Q: Size this for 10× / 100×.**
10×: still small — watch lag, don't repartition reflexively; if a task lags raise partitions+tasks together; maybe a 2nd Connect worker/region; flush thresholds fire before the timer (fine, better freshness); bound the producer pool + acks=all; re-check disk. Reliability + observability before raw scaling; Kafka partitions are the last lever. 100×: architecture review — partitions become a throughput lever; single-task model breaks (raise tasks.max, dedicated Connect cluster); fix acks=1 + unbounded pool; revisit 3× read amplification; tune GCS small-file pressure; salt the hot audit key. NRTI 10×: servlet thread pool breaks first — raise HPA max + thread/RPS autoscale, non-blocking failover, tighten EI timeout, then partitions/consumers.

**Q: DB connection math at max scale (NRTI)?**
12 pods × maximumPoolSize 15 = up to 180 Postgres connections from this service alone — must stay under Azure Postgres Flexible Server `max_connections` + headroom. If undersized, pods at max get connection-refused → `hikaricp_connections_timeout_total` climbs → 5XXs. minIdle 10 keeps connections warm; connTimeout 2s fails fast so DB pressure doesn't cascade into thread-pool exhaustion. Pod count and DB max_connections are coupled.

**Q: Why blocking `.block()`/`.join()` in a reactive WebClient stack?**
It's a blocking Spring MVC / Tomcat app (springboot-web-jre17), not WebFlux end-to-end. WebClient is reactive but the controller contract is synchronous, so we bridge with `.block()` (EI reads) / `.join()` (publish) to return a concrete ResponseEntity. Pragmatic, simple. Cost = thread occupancy. Clean fix = return Mono/CompletableFuture so the servlet thread is released during the await (larger refactor). Current trade = simplicity over thread efficiency, sized around with HPA headroom.

**Q: Quantify the servlet-pool risk at 10× (EI path).**
EI path: WebClient `.timeout(10s)` + Retry.backoff(3, 100ms, 2s) + `.block()` pins a thread up to ~10s/attempt, ~20–30s worst case. Little's Law: ~200 threads / 10s = ~20 concurrent EI-bound requests before the pool fills. At 10× with a slow EI you blow past that and the pod stops accepting work. Hence conservative 60% CPU, tight DB timeouts, and I'd tighten the EI per-attempt timeout to 2–3s + go non-blocking.

**Q: How did you pick min 6 / max 12 for NRTI prod?**
min 6 covers baseline + survives an AZ/rolling-deploy drain + keeps both regions warm. max 12 covers 5–10× peak plus thread-blocking overhead — because threads sit idle-blocked you need more pods than CPU math suggests, so I doubled min. 60% triggers early. I'd validate against actual p95 thread-pool utilization and tune max down if overprovisioned.

### Rebalancing

**Q: Cooperative or eager, and does it matter (audit)?**
Cooperative — `partition.assignment.strategy` commented out ⇒ default `[Range, CooperativeStickyAssignor]` negotiates to cooperative-sticky. Incremental rebalancing doesn't stop-the-world; restarting/deploying a worker doesn't pause all 3 country sinks. With `tasks.max=1`/connector, rebalances only happen on worker restart/deploy.

**Q: What happens during a Connect worker deploy/restart?**
Cooperative-sticky rebalance = only affected tasks pause briefly + resume from last committed offset; other tasks keep running. Offsets commit after flush, so a task resumes and may re-process the in-flight batch (at-least-once → possible duplicates, deduped downstream). No data loss, brief lag bump. min=max=1/region means a deploy momentarily stops that region's sink — readiness/liveness on port 8083 + active/active keep the other region draining.

**Q: Ordering & lag during a consumer rebalance (NRTI)?**
Rebalance reassigns partitions, consumers pause, lag spikes transiently. DSC (keyed tripId) preserves per-trip order (key still maps to the same partition, one consumer/partition). IAC (null key) never had cross-partition ordering, so no worse. Risk = duplicate processing of uncommitted offsets — exactly why at-least-once + dedup matters. I size partitions so the group has room and rebalances are cheap.

**Q: How do you keep rebalances cheap (audit sink)?**
session.timeout=15000, heartbeat=5000 (1:3), max.poll.interval=300000. The 5-min poll interval gives the task time for a 50-record batch + Parquet flush without eviction/rebalance. Cooperative-sticky default avoids stop-the-world. At tasks.max=1/group, rebalances are essentially non-events.

### Lag

**Q: How do you monitor consumer lag and the thresholds?**
Via `lenses_topic_consumer_lag` (managed-kafka-consumer-service) in `kafka-consumer-lag-alerts.yaml`: warn >100 for 5m, critical >500 for 5m. At 230 eps, 100 = <0.5s behind, 500 = ~2s — early warning before BigQuery freshness is at risk. Page on critical. Cleanup: alert message text says 50/100 but expr says 100/500 — a mismatch I'd fix.

**Q: Lag climbing on CA but US/MX fine — diagnose?**
Independent consumer groups localize it immediately (not broker/topic-wide). Check: (1) CA GCS throttling/errors — `connect.gcpstorage` RETRY exhaustion in worker logs; (2) CA DLQ filling — records failing the CA filter/deserialization; (3) CA filter mis-evaluating site-id after an env_properties change. tasks.max=1 means no parallelism without raising partitions+tasks. GCS hiccup self-heals via RETRY(5); poison storm drains to DLQ. The 10-min flush means some lag is normal.

**Q: Where would you watch lag and alert (NRTI producer view)?**
Downstream groups own it, but as producer I care because lag = my events aren't processed. Alert on per-partition records-lag-max trending up + the lag-derivative (growing faster than it drains). Since IAC partitions cap consumer parallelism, sustained lag = "need more partitions/consumers." On produce: record-error-rate, request-latency approaching request.timeout, and the "trying in Secondary region" warning firing.

**Q: How do you handle a lag spike (audit)?**
First lever: raise `tasks.max` toward partition count (more tasks pull in parallel, capped at partitions). If maxed, the bottleneck is the GCS write — tune flush.count/size/interval or check GCS throttling. Honest: no specific lag SLO pinned in repo; at 23 eps the single task never fell behind.

### Delivery semantics

**Q: End-to-end delivery semantic of the audit pipeline?**
At-least-once, with the caveat that produce currently risks loss at acks=1. Sink commits offsets after a successful flush; on crash it reprocesses uncommitted records → duplicates possible into GCS (at-least-once), no exactly-once. Nothing configures EOS/transactions. So: best-effort-once produce today (→ at-least-once once acks=all is set), at-least-once sink, dedup downstream in BigQuery. Won't claim exactly-once.

**Q: Is NRTI exactly-once, at-least-once, or at-most-once?**
At-least-once, explicit: idempotence=false + acks=all + retries=10 → a retry after a lost ack can duplicate. Chose at-least-once over EOS because downstream is idempotent on messageId/tripId, so the idempotent-producer overhead + single-in-flight constraints weren't worth it. Never claim exactly-once.

**Q: With retries=10 + idempotence off, how prevent duplicates corrupting inventory?**
Two layers: the key IS the dedup token (messageId) so duplicates land on the same partition in order and the consumer dedups before applying the action; and the action is modeled idempotent on that id. End-to-end effect is effectively once. Turning on idempotence only fixes producer-side dupes, not consumer reprocessing — so consumer dedup is still needed; given that, producer idempotence was redundant cost (but I'd still flip it for ordering).

**Q: Enumerate where audit records can be lost end-to-end.**
(1) Producer acks=1 — record acked by a failing leader before replication, silent loss. (2) Pod crash — records in the unbounded async pool not yet sent (memory-only). (3) No secondary failover — primary-region outage → EUS pods log-and-drop. (4) Filter — wrong/missing header mis-routes (to US) = residency issue, not loss. (5) Sink — at-least-once = duplicates not loss, but errors.tolerance=all diverts unprocessable records to DLQ; if unmonitored that's effectively silent loss. Top 3 to fix: acks=all, bounded pool, secondary failover.

**Q: If you saw duplicate audit records in BigQuery, how reason about it?**
Expected, not a bug — at-least-once sink. Duplicates arise when the connector reprocesses records whose offsets weren't committed before a crash/rebalance (offsets commit after flush, so a crash mid-flush re-writes the batch). Confirm it correlates with a worker restart/rebalance/RETRY-then-recover in logs. Fix = dedup downstream in BigQuery on a stable record id (request/trace id in LogEvent), not chase EOS in Kafka. Worry only if duplicate *volume* is huge (crash loop).

**Q: Summarize NRTI delivery semantics per topic in one sentence each.**
IAC: at-least-once, NO ordering (null key), sync-with-cross-region-failover, caller-visible failure on total outage (maps to HTTP 500) — consumers dedup on messageId. DSC: at-least-once happy path but at-most-once on both-regions failure (exception swallowed, always 201), per-trip ordering via tripId — consumers dedup on tripId. Both rely on consumer idempotency (idempotence=false); both get in-region zero-loss from acks=all + RF3 + (assumed) min.insync=2 and region resilience from active/active.

### Ordering

**Q: How do you ensure ordering for compliance audit trails?**
Per (service, endpoint) via the key — every event for the same API → same partition → ordered. No global cross-service ordering (correct: an audit trail is per-resource/API, not one global stream; global would force a single partition). Downstream, `_header.date` + timestamps let BigQuery reconstruct chronology. Caveat: at-least-once sink means a possible duplicate in GCS, so treat as ordered-with-possible-dups, dedup on a record id if strict.

**Q: Could enabling idempotence break ordering, and does it matter here?**
It *protects* ordering — idempotence=true guarantees no duplicates and preserves order even with retries (max.in.flight ≤5). The hazard is retries WITHOUT idempotence: a failed batch retried after a later batch succeeded reorders within a partition. Today (retries default, idempotence off) a transient retry could reorder. So idempotence=true + acks=all both improves durability and removes reordering — no downside for this workload.

**Q: How guarantee a DSC event for the same trip stays ordered if sent twice quickly?**
DSC keys on tripId → same partition, appended in send order (Kafka preserves per-partition order). Catch with idempotence=false: under a retry, in-flight ordering can theoretically be disturbed (max.in.flight not pinned to 1). So happy-path ordered, retry storm could reorder. idempotence=true guarantees order even under retry — another reason it's the top change. Consumer dedups on tripId regardless, so a duplicate is absorbed even if order is briefly perturbed.

**Q: What single-in-flight / ordering caveat comes from your retry settings?**
With retries>0, idempotence off, default max.in.flight=5, a failed-then-retried batch can reorder behind a later succeeded batch. Accepted because the consumer reconciles on messageId. For hard ordering without idempotence I'd set max.in.flight=1 (throughput cost), or just turn on idempotence (preserves order even with in-flight>1). I chose consumer-side reconciliation as cheaper.

### DR

**Q: Describe the active/active dual-region setup and how the producer picks a region.**
Both EUS2 + SCUS run their own cluster; pods deployed to both (`eus2-prod-a30`, `scus-prod-a63`). Region binding via CCM overrides keyed on zone: prod-eus2 sets primary=eus/secondary=scus, prod-scus swaps them. The producer builds primary + secondary templates from those URL lists. NRTI uses the secondary on failure; audit only uses primary (asymmetry).

**Q: Does the audit producer fail over to secondary on send failure?**
No — a real gap vs NRTI. Both templates built (52-63) but `publishMessageToTopic` only calls primary inside a try/catch that logs (47-51); secondary is autowired but unused. On a primary-region outage the audit producer logs-and-drops. Fix: port NRTI's failover (the secondary template is wired, just needs the fallback call on the future's failure path).

**Q: If EUS2 Kafka goes down entirely — audit?**
Partial loss for EUS pods (no failover) — they log send failures, unbounded pool backs up; SCUS pods keep working. Fix = secondary-template failover so EUS pods re-send to SCUS. Even then, independent clusters mean a record produced to EUS but not yet consumed isn't readable from SCUS — but sinks run per-region, each draining its own cluster. Durable backstop = GCS from whichever region stayed up.

**Q: Show where the NRTI region failover happens in code.**
`NrtKafkaProducerServiceImpl`: IAC line 69 sends to primary; the future's `.exceptionally` (84) → `handleFailure()` (161) sends to `kafkaSecondaryTemplate`; `.join()` (89) blocks until resolved; total failure throws `NrtiUnavailableException` (503-intended, 500-actual). DSC has the same structure, fire-and-forget.

**Q: Why does IAC return error on failure but DSC silently 201?**
Criticality. IAC is an inventory mutation — losing it corrupts state, so `.join()` + throw surfaces failure so the caller retries. DSC is lower-stakes/latency-sensitive — fire-and-forget, exception only logged (784-788), 201 unconditionally (483). A deliberate consistency-vs-availability split per stream.

**Q: Is 503 or 500 on IAC failure? Be exact.**
OpenAPI documents 503 (`IacControllerV1:58`) but the mapped status is **500** — `NrtiUnavailableException` is `@ResponseStatus(INTERNAL_SERVER_ERROR)` (line 14). Arguably a bug — a downstream-unavailable condition should be 503 (retryable) not 500 (looks like our bug). I'd change it to SERVICE_UNAVAILABLE so clients/mesh treat it as retryable.

**Q: The IAC `.join()` inside an HTTP request — operational risk?**
Servlet pool exhaustion. `.join()` blocks the Tomcat thread until the whole primary-then-secondary chain completes; with request.timeout=5min + retries=10, a stuck send holds a thread for minutes. At ~230 eps peak, if sends hang even a few seconds, in-flight requests pile up, the ~200-thread pool saturates, and every endpoint queues. Mitigate: scale early at 60% CPU (but CPU is wrong for blocked threads → add thread/RPS autoscale), lower delivery.timeout so a doomed send fails fast to secondary.

**Q: DSC fire-and-forget failure mode and fix without breaking 201?**
Silent loss if both regions fail (caller already got 201, no back-pressure/retry signal). Fix: on the secondary-send `.exceptionally`, persist the failed DSC to a durable Postgres outbox (15-conn Hikari already there) + background relay retries to Kafka. Transactional outbox — fast 201 + durable eventual delivery. Today it's a genuine at-most-once gap.

**Q: Blast radius if EUS2 Kafka goes fully down (NRTI)?**
EUS pods fail primary → spill to SCUS (latency + egress); SCUS pods unaffected — degradation, not outage. Risk: IAC `.join()` waits through the primary failure before failover → thread occupancy rises on EUS pods → want a tight delivery.timeout. Lag could rise if SCUS consumers can't absorb both regions. Confirm SCUS has full-failover capacity (RF/ISR are KaaS-side).

**Q: How does a deploy not drop in-flight messages (NRTI)?**
preStop `sleep 30` (line 647) — sidecar + in-flight drain window before SIGTERM. Flagger canary (726-748): stepWeight 10 → maxWeight 50 over 2m, auto-rollback if 5XX >1% over 2m; `rollbackOnError: true` (427). A bad deploy is caught at 10% traffic. Gap: async sends not acked at SIGTERM could be lost — 30s drain mitigates; the IAC `.join()` helps (won't return until the send completes).

**Q: How is mTLS / transport security handled?**
mTLS terminated at the Istio sidecar, not in-app JKS. `nrtKafkaSslEnabled`/`auditLoggingKafkaSslEnabled` default false in prod overrides; producer logs "mTLS is enforced for Kafka connections." JKS plumbing + mounted secrets exist as a fallback. App speaks plaintext to its local sidecar, which does mutual TLS on port 9093 over the mesh. Keeps cert rotation out of the app.

**Q: Why 9093 + PLAINTEXT in the Connect config if it's mTLS?**
9093 is the secured listener but Connect sets `security.protocol=PLAINTEXT` (`kc_config.yaml:14`), SSL blocks commented out — mTLS is at the sidecar, not the client. The pod talks plaintext to its local sidecar; the sidecar does mutual TLS to the broker. PLAINTEXT in-app is correct given mesh-level mTLS; in-app SSL is an off-by-default fallback.

### Monitoring

**Q: What metrics on a dashboard for these pipelines?**
Producer: send rate + error rate per region, async pool thread count + queue depth (catch the unbounded-pool backup before OOM), 204 throughput (ingress proxy), region-failover count. Topic/consumer: `lenses_topic_consumer_lag` per group (warn 100/crit 500), records-consumed per connector, under-replicated partitions, ISR shrink. Sink: GCS write success/error, `connect.gcpstorage` RETRY counts, DLQ depth per country, flush rate + object-size distribution, BigQuery freshness. Plus Schema Registry latency/error (SPOF) + header-less→US rate (residency). Page on lag, DLQ depth, pool depth.

**Q: What alerts page someone?**
DLQ depth growing, lag crossing threshold + trending up, under-replicated/ISR<min.insync, Connect task FAILED, IAC error-rate elevated, region-failover count spiking, thread-pool rejections >0, pod stuck at max replicas with CPU pinned.

**Q: Single best "producer in trouble?" panel (NRTI)?**
The cross-region failover count ("Failed to Publish in Primary... trying in Secondary," lines 85/122). Near zero = primaries healthy; a spike = a region degrading (paying cross-region latency/egress + risking IAC `.join()` thread occupancy). Pair with `jvm_threads_live_threads` (saturation) + p95 `http_server_requests` latency: healthy / degraded-but-coping / heading-for-saturation in one glance.

**Q: Schema Registry as a SPOF — how?**
On both ends. Producer (KafkaAvroSerializer, auto.register=false) must fetch/validate the schema id to serialize — if the registry is down/slow, serialization blocks/fails; the fire-and-forget unbounded pool means a registry stall backs up threads *invisibly*. Sink AvroConverter needs it to deserialize. Mitigations: Confluent client caches schema ids in-process; auto.register=false means schemas managed deliberately. I'd HA the registry + add a producer-side timeout + bounded pool so an outage sheds load.

**Q: How does the EI 10s timeout relate to the 5s pool socketTimeout?**
Different layers. 5s socketTimeout / 2s connectionTimeout / 1s validationTimeout = low-level connection-pool guards (fail fast on a dead socket). 10s WebClient timeout + Retry.backoff(3, 100ms, 2s) = the higher-level call budget wrapping potentially >1 socket attempt. A socket dies at 5s, retry kicks in with backoff, the call is capped at 10s. Tight low-level timeouts under a slightly looser retrying budget = fail fast on dead connections, ride out a brief blip.

### DLQ

**Q: How does the audit DLQ work and what triggers it?**
Each connector: `errors.tolerance=all`, `errors.deadletterqueue.context.headers.enable=true`, DLQ `api_logs_audit_prod_DLQ`. tolerance=all routes a record that fails Avro deserialization or an SMT to the DLQ with error-context headers instead of stalling the task — no head-of-line block. DLQ retains the record for forensic replay. Flip side: tolerance=all can silently divert volume → alert on DLQ depth.

**Q: errors.tolerance=all — could you silently lose data?**
Tolerance with a safety net, not silent loss — bad records go to the DLQ with context headers, not /dev/null, and errors.log.enable is on. Trade = availability over strictness: keep draining good records vs stop-the-world on one poison message. DLQ is the audit trail; alert on its depth. For strict zero-tolerance, set errors.tolerance=none and accept the connector halting.

**Q: RETRY vs DLQ — how do they differ and combine?**
Different failure types. `connect.gcpstorage.error.policy=RETRY` (max.retries=5, retry.interval=5000ms) handles transient SINK-side failures (GCS 5xx, throttling) by retrying the write. DLQ (errors.tolerance=all) handles per-RECORD failures (deserialization/SMT). No overlap: RETRY = write target, DLQ = record content.

**Q: One shared DLQ for 3 connectors — a problem?**
All 3 share `api_logs_audit_prod_DLQ`. Arguably good (one place to inspect) but loses per-country attribution unless you use the context headers — which is why `errors.deadletterqueue.context.headers.enable=true` matters (tags each record with connector/error). Risk = mixed failure modes in one stream; mitigate by alerting on rate + slicing by header. Wouldn't split into 3 unless triage volume demands it.

### Flush tuning

**Q: Explain the flush sizing — 50MB / 5000 / 600s.**
KCQL prod triggers: flush.size=50MB, flush.count=5000, flush.interval=600s — whichever fires first writes a Parquet object. At 230 eps peak split US/CA/MX × 2 regions, no country/region hits 50MB or 5000 records in 10 min, so the 600s timer dominates → ~144 objects/day/country/region. Deliberate freshness-vs-file-size trade: up to 10-min lag for big, query-efficient Parquet files.

**Q: What's the small-file problem and how does the config avoid it?**
Tiny files kill object-storage analytics: per-file read overhead, metadata cost, slow GCS listing, degraded BigQuery external-table scans. The config makes the 600s timer dominant so files accumulate ~10 min into MB-sized Parquet. flush.count=5000 is a backstop (even 2M/day in one country = 400 objects/day, still large). Cost = up to 10-min freshness. For near-real-time, cut flush.interval, accept smaller files.

**Q: Do the math — GCS objects/day.**
Per country/region: 86400/600 = 144 flushes/day. 3 countries × 2 regions ≈ ~864/day under the timer. Worst case all 2M in one country: 2,000,000/5000 = 400/day. The math that justifies the 10-min timer — bounds object count, keeps files BigQuery-efficient.

**Q: How does KCQL PARTITIONBY interact with query performance?**
`PARTITIONBY service_name, _header.date, endpoint_name` lays GCS objects in a directory hierarchy by those keys. BigQuery external tables partition-prune: a query filtered to one service/date scans only that prefix. Mirrors the Kafka key on disk. Trade = many prefixes — but the 10-min flush makes each file large, giving few large files per prefix (ideal Parquet layout).

**Q: What does the InsertRollingRecordTimestamp SMT do and why before the filter?**
Inserts a rolling date header (yyyy-MM-dd, GMT) → `_header.date` for daily GCS partitioning. Runs first (before the country Filter) so every surviving record carries the date stamp before the filter decides to keep it — the header must exist on records that get written. GMT is deliberate so all 3 countries partition on one consistent date boundary, keeping downstream partitions aligned.

### Cost

**Q: How would you cost-optimize the audit pipeline?**
(1) 3× read amplification — cheap now, but at scale evaluate one connector + downstream routing. (2) Apply lz4 (declared, unread) to cut broker storage/network. (3) Retention — 7 days recommended, but if reprocessing always uses GCS, trim to 3 days (~60% less broker disk). (4) Sink workers are big (10-12 CPU, 7g heap, 2 regions) — right-size CPU after observing usage; the dominant cost at low volume. (5) GCS — 10-min flush already produces efficient large Parquet (minimizes BigQuery scan cost). Biggest waste = over-provisioned Connect workers vs 23 eps.

**Q: Cost story for NRTI Kafka choices?**
lz4 cuts broker storage + cross-region egress (real Azure cost on failover). acks=all + RF3 triples storage for durability — the price of zero-loss, defended for IAC. Retention length = direct disk cost → size to outage-tolerance, not "forever." Compute: min6/max12 × 1-2 CPU; because the workload is thread-blocked not CPU-bound, there's over-provisioning risk just to have threads — fixing the blocking model lets us run fewer pods. Biggest cost+correctness win = go non-blocking + turn on idempotence.

**Q: Why partition Parquet by service_name, date, endpoint?**
To make BigQuery queries cheap + pruneable. Audit queries filter by date (time window) and often service/endpoint. Partitioning on exactly those columns prunes to the relevant files → faster + cheaper (BigQuery bills on bytes scanned). Mirrors the Kafka key — consistent end to end.

**Q: How would you cost-optimize overall?**
Compute: 4-8 pods at 1-2 CPU, scaled at 60% so no idle over-provisioning. Kafka: cheap at this volume (small partitions, RF3, short retention → low tens of GB). Real lever = GCS/BigQuery: Parquet flush sizing (50MB) avoids small-file proliferation; date/service/endpoint partitioning prunes scans. The 3× read costs a bit of Connect compute, negligible Kafka egress at 23 eps. At 100× revisit 3× read + small-file pressure as top cost risks.

### Misc / "what would you change"

**Q: If you could change three things about the NRTI producer?**
(1) idempotence=true — free with acks=all, kills dupes + restores ordering, makes consumer dedup defense-in-depth. (2) Set `KafkaHeaders.KEY` on IAC (storeNbr or store+item) for deterministic partitioning/ordering. (3) Kill request-thread blocking — shorter delivery.timeout so a doomed send fails fast to secondary + a transactional outbox for DSC so the 201 path can't silently lose data. All correctness wins; (3) is also a cost win (fewer pods). Plus map `NrtiUnavailableException` to 503 not 500.

**Q: If you could change one thing about either system?**
Replace the unbounded `Executors.newCachedThreadPool()` in audit-srv `ExecutorPoolService` with a bounded pool sized by Little's Law (copy the good common-lib 6/10/100 pattern). It's the one place a downstream Kafka slowdown could cascade into thread exhaustion/OOM — low-risk to fix, removes a real production failure mode. Second: make the audit producer's durability explicit (set acks deliberately) so the tradeoff is in code, not implicit.

**Q: Top operational risks in priority order (audit)?**
(1) Producer durability — acks=1 + idempotence off because CCM tuning is declared-but-unread → silent loss on failover; wire acks=all + idempotence. (2) Unbounded async pool + fire-and-forget 204 — backs up + OOMs under a stall instead of shedding; bounded pool. (3) Async send error handling is ineffective (sync try/catch around an async future) + no secondary failover despite both templates existing; future callback that fails over. (4) Schema Registry SPOF on both ends, no producer timeout. (5) US catch-all absorbs header-less CA/MX records — residency concern to monitor. (6) Minor: lag-alert text vs expr mismatch (50/100 vs 100/500). First three before claiming production-grade for compliance.

**Q: What would you measure before going to prod to validate sizing?**
A load test at projected peak (repo has 10/30/50 VU stage perf JSON): produce P99 under load, CPU stays under 60% before max pods, no thread-pool rejections on the bounded pool, sink keeps lag near zero, GCS files land at ~10-min cadence with right-sized Parquet. Plus chaos: kill a broker to confirm acks=all + min.insync=2 keeps NRTI writing; kill the primary region to confirm failover end-to-end. Sizing is a hypothesis; load + chaos tests validate it.

---

## 12. Honest gaps recap — the exact words to say

These are NOT in either repo. Say so plainly, then size with the formula. Never invent a number.

| Gap | The exact words | The sizing answer |
|---|---|---|
| **Partition count** (all topics) | "The exact partition count isn't in my service repos — the topics are provisioned through Walmart's Kafka-as-a-Service self-serve platform, external to my code. My config only references the topic NAME." | "I sized the request: `partitions = max(ceil(peak_eps / per-partition-ceiling), consumer_parallelism)`. At ~23 eps / ~230 peak with sub-KB records, throughput needs ~1 partition — so it's a parallelism/ordering decision. I'd request 6 (audit) / 6–12 (NRTI) for future consumer parallelism + broker spread + headroom, because repartitioning a keyed topic breaks ordering." |
| **replication.factor** | "RF is a topic/cluster property set at provisioning via KaaS, not in my client config — I can't point you to a line of code." | "Each region's broker DNS fronts a 3-broker cluster, and KaaS default + the durability bar (audit-of-record, financial inventory) make RF=3 the only defensible choice. I requested/assume RF=3." |
| **min.insync.replicas** | "min.insync lives on the broker/topic, not in my client config, so it's not in these repos." | "I'd request 2 with RF=3 so a write needs 2 of 3 in-sync — durable through one broker outage, still writable. For NRTI I set acks=all precisely so this pairing matters; for audit acks defaults to 1 so it's moot until I wire acks=all." |
| **retention.ms / retention.bytes** | "Retention is a topic-level KaaS setting, not in my repo — my producer never sets it." | "I sized from replay need: audit lands in GCS within 10 min so Kafka is a transient buffer → request 3–7 days (~0.8 TB at peak RF3). NRTI → 3–7 days covering the worst downstream outage. Disk = eps × avg_msg × retention_seconds × RF." |
| **Topic provisioning / topic-creation** | "I requested the topic + DLQ + Connect internal topics through KaaS; the repo only carries the client/connector config — no AdminClient, no terraform." | — |
| **Exact message size** | "Not measured in the repo — I use ~1–2KB/event (audit Avro) as a working estimate for sizing math and flag it as an estimate." | — |
| **DR cross-region replication mechanism** (MirrorMaker2/Brooklin) | "Cross-region broker-layer replication is platform-managed — not in my repo." | "At the application layer my active/active story is the producer dual-template failover (in NRTI code). Whether the two regional clusters also mirror at the broker layer I didn't own." |
| **Consumer group per audit connector** | "env_properties only sets the Connect WORKER group.id (`kcaas-audit-logs-gcs-sink-connector`). The per-connector SINK consumer-group id (`connect-<connector-name>`) is implicit Connect behavior, not written in the repo." | "Each connector gets its own consumer group — which is exactly why the topic is read 3×." |
| **Measured prod EPS / lag** | "The ~2M/day (~23 eps avg, ~100–230 peak) is a business estimate; the peak factor is mine, not in the repo. I'd quote Dynatrace/Prometheus for the real number, and no specific lag SLO is pinned in the repo." | — |
| **Exactly-once** | "EOS is not configured anywhere — sink is at-least-once (offset commit after flush), producer has no idempotence. End-to-end is at-least-once with possible duplicates on retry." | — |
| **NRTI prod HPA discrepancy** | "The brief says min4/max8 but the committed prod `kitt.yml` is min6/max12 — the 4/8 is the stage profile. I'll go with what's in the file." | — |
