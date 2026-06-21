# 10 — Authenticity Audit: Résumé & Docs vs. Real Source Code

> **Purpose.** This file is *the receipt*. Every claim in the `WALMART-INTERVIEW-QA` study docs — and every adjective/metric on the résumé — was re-verified line-by-line against the actual source under `/Users/a0g11b6/Desktop/walmart` (4 repos: `audit-api-logs-srv`, `audit-api-logs-gcs-sink`, `cp-nrti-apis`, `dv-api-common-libraries`, plus the `LUMINATE-CPERF-NRTI-APIS-NON-PROD-1_0` config bundle). When an interviewer says **"prove it,"** these are the exact files, classes, methods, line numbers, and config values you cite.
>
> **Thesis (carry this through every row): state the precise truth FIRST, then convert the gotcha into senior signal.** The code is strong; the only discipline required is to lead with the correction on ~10 flagged items instead of letting them be "caught."

---

## How to use this under fire

- **"Prove it" → read the `file:line`.** Every row below carries a real anchor. Don't paraphrase; quote the symbol.
- **They cite a résumé superlative** (`factory pattern`, `exactly-once`, `zero data loss`, `<5ms freshness`, `RestTemplate→WebClient`, `Spring Security migration`) → lead with the one-line correction from the relevant row, then explain *why the real design is actually defensible*.
- **Legend:** ✅ TRUE (in code) · 🟡 PARTIALLY-TRUE (true but needs precise scoping) · ⚠️ MISLEADING as written (reframe required) · ❌ FALSE / not in code · 🔵 UNVERIFIABLE in repo (ops/CCM/estimate — never claim as a code fact).
- **Evidence cells are 3-part:** `anchor` | what the code literally does | why it matters.

---

# B. Bullet 1 — Audit Logging (`audit-api-logs-srv` + `audit-api-logs-gcs-sink`)

> **Résumé phrasing under audit:** *"Spearheaded an end-to-end audit-logging platform processing millions of API events with <5ms P99 overhead, Avro + Schema Registry, SMT-based geo-routing to GCS Parquet / BigQuery, eliminating Splunk; org-wide standard."*

## B.1 — Per-phrase verification

| Claim phrase | Code evidence (file · class.method · line) | Verdict | Honest phrasing to use |
|---|---|---|---|
| "Spearheaded / end-to-end" | 3 repos exist and wire together (producer → topic → Connect sink). Several files (e.g. SMT filters) co-authored. | 🟡 | "I led the audit-logging path end-to-end and personally owned the producer + sink-filter design; the GCS connector tuning was collaborative." Credit the team. |
| "Processing **millions** of API events" | No counter in repo. Volume is a function of every audited service × traffic; `LoggingFilter` fires per request. | 🔵 | "Order-of-magnitude is millions/day across audited services; that's a traffic-derived estimate, not a metric I can point to in this repo." |
| "**<5ms P99**" | `AuditLoggingController.saveApiLog` returns `204` **before** publish; producer is async. The <5ms is the *added overhead* on the audited API (the async hop), **not** audit freshness. | ⚠️ | "<5ms is the synchronous overhead added to the caller — controller returns 204 then hands off to a thread pool. End-to-end freshness is **minutes** (sink `flush.interval=600s`)." |
| "**Avro** + Schema Registry, `auto.register.schemas=false`" | `KafkaProducerConfig.populateConfigProperties:90-92` → `VALUE_SERIALIZER_CLASS_CONFIG = KafkaAvroSerializer.class`, `SCHEMA_URL_CONSTANT = getSchemaRegistryUrls()`, `AUTO_GENERATED_CONSTANT = false`. | ✅ | True verbatim. `auto.register=false` means schemas are pre-registered — a breaking change fails the producer fast rather than silently evolving. |
| "Key serializer = String; key = `serviceName/endpoint`" | `KafkaProducerConfig:89` `KEY_SERIALIZER_CLASS_CONFIG = StringSerializer.class`; `AuditKafkaPayloadKey.getKafkaKey:26-28` → `serviceName + "/" + endpoint`. | ✅ | "Partition key is `serviceName + '/' + endpoint`, so all events for one endpoint land on one partition → per-endpoint ordering." |
| "**SMT-based geo-routing**" | `kc_config.yaml:75/93/111` → each connector chains `InsertRollingRecordTimestamp` then a country `Filter*`. Routing is *filter-drop*, not re-route. | 🟡 | "Geo-segregation is by SMT *filtering*: 3 connectors each read the whole topic and **drop** records whose `wm-site-id` isn't theirs — not a router that fans one record to one place." |
| "GCS **Parquet** / **BigQuery**" | `env_properties.yaml` KCQL `STOREAS PARQUET`, `INSERT INTO audit-api-logs-{us\|ca\|mx}-prod`. BigQuery = external tables over those buckets (not in repo). | 🟡 | "Sink writes Parquet to per-country GCS buckets; BigQuery reads them as external tables — that part is platform config, not this repo." |
| "Eliminating **Splunk**" | No Splunk reference in any of the 4 repos. | 🔵 | "Splunk replacement is the business rationale (cost + queryability via BigQuery); it's not something the code proves." |
| "**Org-wide standard**" | The *producer client* lives in `dv-api-common-libraries` (consumed at v0.0.61) so many services emit audit logs through it. | 🟡 | "The shared library is consumed broadly, so it's a de-facto standard for DV services — 'org-wide' is aspirational, scope it to Data Ventures." |
| "**2 weeks → 1 day**" onboarding | Not in repo. | 🔵 | Estimate from adoption experience; label it as such. |

## B.2 — The producer config matrix (the load-bearing "prove it")

`KafkaProducerConfig.populateConfigProperties` (lines 85–119) sets **only** these keys — and pointedly omits the durability knobs:

```java
// audit-api-logs-srv/.../kafka/KafkaProducerConfig.java:87-92
configProps.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, getKafkaBrokerUrl(isPrimaryTemplate));
configProps.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
configProps.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, KafkaAvroSerializer.class);
configProps.put(SCHEMA_URL_CONSTANT, auditLogsKafkaCCMConfig.getSchemaRegistryUrls());
configProps.put(AUTO_GENERATED_CONSTANT, false);
// + optional SSL block, gated on getAuditLoggingKafkaSslEnabled() — else logs "mTLS is enforced"
```

| Key | Set here? | Effective value | Consequence |
|---|---|---|---|
| `acks` | ❌ not set | **`1`** (client default) | Leader-only ack. Loss window if leader dies before replication. |
| `enable.idempotence` | ❌ not set | `false` (default w/ acks=1) | No producer-side dedup. |
| `retries` | ❌ not set | default | No tuned retry posture. |
| `linger.ms` / `batch.size` | ❌ not set | `0` / `16384` | Untuned batching. |
| `compression.type` | ❌ not set | `none` | No wire compression. |

**Pre-empt the rebuttal "but a CCM yml might declare acks":** `AuditLogsKafkaCCMConfig` is a `@ManagedConfiguration` **interface** (`io.strati`). It exposes exactly 5 getters: `getAuditKafkaPrimaryBrokerUrls`, `getAuditKafkaSecondaryBrokerUrls`, `getAuditLoggingKafkaTopicName`, `getSchemaRegistryUrls`, `getAuditLoggingKafkaSslEnabled` (`AuditLogsKafkaCCMConfig.java:25-54`). **There is no `getAcks()` getter and `populateConfigProperties` never reads one** — so even if a yml *declared* acks, it would be dead config. → **Effective `acks=1`. "Near-zero / zero data loss" is unsupported on the audit producer path.** Reframe: *"Audit is acks=1, fire-and-forget — appropriate for telemetry, not for a financial ledger. I'd raise it to acks=all + idempotence if losing an audit record were ever business-critical."*

## B.3 — The async fire-and-forget hop (the real latency lever + OOM risk)

Trace: `AuditLoggingController.saveApiLog:58-61` returns `new ResponseEntity<>(HttpStatus.NO_CONTENT)` **immediately** → `LoggingRequestService.processLoggingRequest:34-43` resolves the `kafkaProducerService` target and submits it → `ExecutorPoolService.executeTaskInThreadPool:12-13` → `KafkaProducerService.publishMessageToTopic:39-52`.

```java
// audit-api-logs-srv/.../services/ExecutorPoolService.java:10-14  (the whole pool)
ExecutorService pool = Executors.newCachedThreadPool();   // UNBOUNDED — no max, no queue cap, no RejectedExecutionHandler
public void executeTaskInThreadPool(Runnable task){ pool.execute(task); }
```

```java
// audit-api-logs-srv/.../kafka/KafkaProducerService.java:44-52
try {
  log.info("sending kafka msg for trace id {} ...");
  kafkaPrimaryTemplate.send(kafkaMessage);   // returns a CompletableFuture — NEVER observed
} catch (Exception ex) {
  log.info("sending kafka msg failed for {}", ...);   // catches only SYNCHRONOUS throws (e.g. serialization)
}
```

| Claim | Anchor | Verdict | Note |
|---|---|---|---|
| Returns **204** then publishes async | `AuditLoggingController.saveApiLog:60` (`saveRequest:44-46` is the legacy twin → also 204) | ✅ | Two endpoints; both 204-then-async. |
| Pool is **unbounded `newCachedThreadPool`** | `ExecutorPoolService.java:10` | ✅ | This *is* the <5ms lever (no backpressure on the caller) **and** the OOM/thread-explosion risk under a downstream Kafka stall — no `maximumPoolSize`, no queue, no rejection policy. Bounding it is my top hardening item. |
| Send is **log-only try/catch**, future unobserved | `KafkaProducerService.publishMessageToTopic:47-51` | ✅ | The returned `CompletableFuture` has **no `.get()`, no `whenComplete`, no callback** → an *asynchronous* broker failure is logged by Kafka's own producer but **not** caught here. "Catches almost nothing." |
| **`kafkaSecondaryTemplate` is DEAD CODE** | Bean declared `KafkaProducerConfig.kafkaSecondaryTemplate():60-63`; field autowired `KafkaProducerService.java:30-31`; **never `.send()`-ed** (only `kafkaPrimaryTemplate.send` at line 47). | ✅ | There is **no failover in audit-srv.** The active/active story is NRTI's, not audit's. Say so plainly. |
| Header allow-list copied to Kafka headers | `KafkaProducerService.setHeaders:92-98` | ✅ | **Exact set (corrected):** `Set.of("wm_consumer.id","wm_qos.correlation_id","wm_svc.name","wm_svc.version","wm_svc.env","wm-site-id")`, matched after `key.toLowerCase()`. *(The previous version of this doc fabricated `"wm_consumer.is.correlation_id"` — there is no such header. Fixed.)* |

## B.4 — The sink is Kafka Connect (Lenses), NOT Spring — the receipt

`audit-api-logs-gcs-sink` has **no `@SpringBootApplication`** — it's a Kafka-Connect deployment built on the `kcaas` base image. `kc_config.yaml` worker block:

```yaml
# audit-api-logs-gcs-sink/kc_config.yaml:7-46 (worker.*)
key.converter:   org.apache.kafka.connect.storage.StringConverter
value.converter: io.confluent.connect.avro.AvroConverter
value.converter.schemas.enable: true
group.id: com.walmart-audit-log-gcs-sink-0.0.1
security.protocol: PLAINTEXT          # all ssl.* commented — mTLS terminates at the Istio mesh
consumer.max.poll.records: 50
max.poll.interval.ms: 300000
session.timeout.ms: 15000
heartbeat.interval.ms: 5000
request.timeout.ms: 60000
```

Distributed-mode internal topics live in `env_properties.yaml` (`config/offset/status.storage.topic = api_logs_audit_{stg|prod}-...`, lines 32-34/115-117), proving it's a real Connect cluster.

| Claim | Anchor | Verdict |
|---|---|---|
| Sink is **Connect + Lenses `GCPStorageSinkConnector`**, not Spring | `kc_config.yaml:65` `connector.class: io.lenses.streamreactor.connect.gcp.storage.sink.GCPStorageSinkConnector` | ✅ |
| Avro converter **paired** with Schema Registry on read | `kc_config.yaml:8-9` `value.converter=AvroConverter` + `schemas.enable=true`; SR url per env in `env_properties.yaml:37/93/120` | ✅ (was missing from prior doc) |
| `consumer.max.poll.records=50` + timeouts | `kc_config.yaml:42-53` | ✅ |
| **3 named connectors**, each `tasks.max=1`, `errors.tolerance=all`, DLQ, RETRY max 5 | `kc_config.yaml:63/81/99` → `audit-log-gcs-sink-connector` (FilterUS), `-ca` (FilterCA), `-mx` (FilterMX); each `tasks.max:1` (66/84/102), `errors.tolerance:all`, `errors.deadletterqueue.context.headers.enable:true`, `connect.gcpstorage.error.policy:RETRY`, `connect.gcpstorage.max.retries:5`, `retry.interval:5000` | ✅ |
| Timestamp SMT format/zone | `kc_config.yaml:78-79` `date.format: "yyyy-MM-dd"`, `timezone: GMT` (`InsertRollingRecordTimestampHeaders`) | ✅ |
| **3× read amplification** | Mechanism: 3 *distinct connector names* in one Connect cluster → each gets its own per-connector consumer group (`connect-<connector-name>`) → each reads the **full** `api_logs_audit_*` topic, then SMT-filters. So the topic is consumed 3×. | ✅ (now pinned to the mechanism, not "3 manual group.ids") |

## B.5 — The filter-strictness trap ("read the code, not the comment")

All three subclasses carry the **identical** Javadoc *"Records are passed if the header matches … **or if the header is missing**."* But only US actually implements the "missing" branch:

```java
// BaseAuditLogSinkFilter.verifyHeader:52-64  — STRICT (anyMatch only)
return StreamSupport.stream(r.headers().spliterator(), true)
    .anyMatch(h -> HEADER_NAME.equals(h.key()) && StringUtils.equals(getHeaderValue(), String.valueOf(h.value())));
```

```java
// AuditLogSinkUSFilter.verifyHeader:42-56  — CATCH-ALL (anyMatch || noneMatch)
return StreamSupport.stream(...).anyMatch(h -> HEADER_NAME.equals(h.key()) && StringUtils.equals(getHeaderValue(), ...))
    || StreamSupport.stream(...).noneMatch(h -> HEADER_NAME.equals(h.key()));   // header-less → PASS
```

```java
// AuditLogSinkCAFilter:23-26  and  AuditLogSinkMXFilter:23-26  — override ONLY getHeaderValue(), inherit STRICT base
@Override protected String getHeaderValue() { return AuditApiLogsGcsSinkPropertiesUtil.getSiteIdForCountryCode("CA"); }  // "MX" for MX
```

| Claim | Anchor | Verdict | Honest phrasing |
|---|---|---|---|
| US filter is the **catch-all** (header-less passes) | `AuditLogSinkUSFilter.verifyHeader:47-49` adds `\|\| noneMatch(... wm-site-id)` | ✅ | "US is the permissive default — a record with no `wm-site-id` lands in the US bucket." |
| **CA *and* MX** Javadocs lie | `AuditLogSinkCAFilter.java:8-11` & `AuditLogSinkMXFilter.java:8-11` both say "or if the header is missing"; both inherit the strict `Base.verifyHeader`. | ✅ (corrected: prior doc named only CA) | "Both CA and MX Javadocs claim they pass header-less records; they don't — they inherit the strict base, so a header-less record is **dropped** by CA/MX and **only** caught by US. The comment is wrong; the code is the contract." |
| Site value comes from properties | `getSiteIdForCountryCode("US"/"CA"/"MX")` in `AuditApiLogsGcsSinkPropertiesUtil` | ✅ | — |

## B.6 — KCQL / bucket / flush detail

```sql
-- env_properties.yaml prod-eus2 (us), lines 221-235 (representative)
INSERT INTO `audit-api-logs-us-prod:us_dv_audit_log_prod.db/api_logs`
SELECT * FROM `api_logs_audit_prod`
PARTITIONBY service_name, _header.date, endpoint_name
STOREAS `PARQUET` PROPERTIES('flush.size'='50000000','flush.count'='5000','flush.interval'='600','key.suffix'='_eus2');
```

| Claim | Anchor | Verdict |
|---|---|---|
| PARQUET, `PARTITIONBY service_name,_header.date,endpoint_name` | every connector block in `env_properties.yaml` | ✅ |
| Flush **50MB / 5000 / 600s** for stage+prod | e.g. `:227-229` (us prod), `:345-348` (ca prod), `:464-467` (mx prod) | ✅ |
| The "5MB / no-count" block | **dev-only**: `env_properties.yaml:159` (US `dev` profile) uses `flush.size=5242880` with no `flush.count`. **Every stage/prod profile is 50MB/5000/600.** | ✅ (corrected: prior doc called this vague "per-env variance"; it's a dev-only artifact) |
| Per-country buckets, project `wmt-dv-luminate-prod`, `key.suffix _eus2`/`_scus`, `gcp.auth.mode FILE secret.ref://gcs_key.json`, indexes `.indexes-eus2`/`-scus` | `env_properties.yaml` (project at `:232` etc.; suffix `:230/253`; auth `:233-234`; indexes `:235/258`) | ✅ |

**Bullet 1 numeric authenticity score: 8.5/10.** Mechanics fully real and now line-cited. Deductions: `<5ms` and `millions` and `Splunk` and `org-wide` are scope/estimate claims, not code facts — flagged above.

---

# C. Bullet 3 — Active/Active Multi-Region Kafka (`cp-nrti-apis`)

> **Résumé phrasing under audit:** *"Architected an active/active multi-region Kafka pipeline (2M+ events) with CompletableFuture-based automatic failover, zero data loss, and 15-min DR vs 1-hour RTO."*

## C.1 — Per-phrase verification

| Claim phrase | Code evidence | Verdict | Honest phrasing |
|---|---|---|---|
| "**Active/active** multi-region" | `NrtKafkaProducerConfig` builds 4 templates (primary/secondary × IAC/DSC), broker URLs swapped per deployment in `ccm.yml`; each region sends region-local-primary, cross-sends on failure. | ✅ | "Each region writes its local-primary cluster; on send failure it re-sends to the *other* region's cluster. Active/active at the app layer." |
| "**2M+ events**" | No counter in repo. | 🔵 | Traffic-derived estimate; label it. |
| "**CompletableFuture-based** failover" | `NrtKafkaProducerServiceImpl.publishIacKafkaMessage:67-92` uses `CompletableFuture` + `.exceptionally(...).join()`. | ✅ | True — but the *behavior* of the two paths differs sharply (see C.3). |
| "**Automatic** failover" | IAC: `.exceptionally` → `handleFailure` (secondary `.send`) → `.join()`. | ✅ | True for IAC; DSC's failover is fire-and-forget. |
| "**Zero data loss**" | `enable.idempotence=false` (`ccm.yml:196`), `acks=all` (`:171`). | ⚠️ | "At-least-once, not exactly-once. Reframe: *no observable loss of an **acknowledged** event under single-region failure*; dedup is consumer-side on `messageId`." |
| "**15-min DR vs 1-hour RTO**" | **Not in code.** Conflates RPO/RTO; comes from DR game-days / CCM region-pin flips. | 🔵 | "That's an operational metric from DR drills, not code. The *code* failover is per-message, sub-second on a clean exception." |

## C.2 — Producer tuning matrix (NRTI *does* set these — unlike audit)

The NRTI producer config **reads every tuning key** from CCM (`NrtKafkaProducerConfig.populateConfigProperties:114-121`) — a real contrast with the audit producer:

```java
// cp-nrti-apis/.../kafka/NrtKafkaProducerConfig.java:114-121
configProps.put(ProducerConfig.MAX_REQUEST_SIZE_CONFIG,  nrtKafkaCCMConfig.getNrtKafkaMaxRequestSize());
configProps.put(ProducerConfig.COMPRESSION_TYPE_CONFIG,  nrtKafkaCCMConfig.getNrtCompressionTypeConfig());
configProps.put(ProducerConfig.ACKS_CONFIG,              nrtKafkaCCMConfig.getNrtAcksConfig());
configProps.put(ProducerConfig.LINGER_MS_CONFIG,         nrtKafkaCCMConfig.getNrtLingerMsConfig());
configProps.put(ProducerConfig.BATCH_SIZE_CONFIG,        nrtKafkaCCMConfig.getNrtBatchSizeConfig());
configProps.put(ProducerConfig.REQUEST_TIMEOUT_MS_CONFIG,nrtKafkaCCMConfig.getNrtRequestTimeoutMsConfig());
configProps.put(ProducerConfig.RETRIES_CONFIG,           nrtKafkaCCMConfig.getNrtKafkaRetriesConfig());
configProps.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG,nrtKafkaCCMConfig.getNrtKafkaIdempotenceConfig());
```

| Key | `ccm.yml` defaultValue | Anchor | Implication |
|---|---|---|---|
| `acks` | `all` | `ccm.yml:171-172` | Wait for ISR — strong durability. |
| `retries` | `10` | `ccm.yml:191-192` | Producer retries 10× before giving up. |
| `enable.idempotence` | **`false`** | `ccm.yml:196-197` | **At-least-once.** `acks=all` + `retries=10` + idempotence-off ⇒ possible **duplicates / reorder**. This is the proof that "exactly-once / zero loss" is wrong. |
| `compression.type` | `lz4` | `ccm.yml:166-167` | Fast compression for the 10MB-max payloads. |
| `linger.ms` | `20` | `ccm.yml:176-177` | 20ms batching window. |
| `batch.size` | `8192` (8KB) | `ccm.yml:181-182` | Small batches. |
| `request.timeout.ms` | `300000` (5 min) | `ccm.yml:186-187` | **Undercuts "fast failover"** for a black-hole broker — a hung send can wait up to 5 min before `.exceptionally` fires. Volunteer this. |
| `max.request.size` | `10000000` (10MB) | `ccm.yml:161-162` | Large IAC payloads allowed. |
| `ssl.enabled` | `false` | `ccm.yml:206`, per-env `:816+` | mTLS at Istio mesh; code logs *"mTLS is enforced"* (`NrtKafkaProducerConfig:140`). |
| serializer | JSON, **no Schema Registry** | `NrtKafkaProducerConfig:111-112` (`StringSerializer` key, `JsonSerializer` value) | A different world from audit's Avro+SR. |

## C.3 — The IAC-500-vs-DSC-201 asymmetry (a real smell — own it)

> **Status precision:** `NrtiUnavailableException` is `@ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)` (and the `NrtiRestExceptionHandler` `@ExceptionHandler(NrtiUnavailableException.class)` is also `@ResponseStatus(INTERNAL_SERVER_ERROR)`), so the literal IAC total-failure status is **HTTP 500, not 503**. Say 500; note "arguably should be 503 + `Retry-After`" as the fix.

```java
// IAC — BLOCKS the request thread, surfaces 500 on total failure
// NrtKafkaProducerServiceImpl.publishIacKafkaMessage:68-92
try { iscompletableFuture = kafkaPrimaryTemplate.send(iacKafkaMessage); }
catch (Exception ex) { throw new NrtiUnavailableException(); }            // sync throw → 500
try {
  iscompletableFuture
     .thenAccept(r -> log.info("Sent ... partition {} offset {}", ...))
     .exceptionally(ex -> { handleFailure(iacTopicName, iacKafkaMessage, messageId).join(); return null; })
     .join();                                                             // BLOCKS servlet thread
} catch (CompletionException ex) { throw new NrtiUnavailableException(); } // secondary also failed → 500
```

```java
// DSC — fire-and-forget, returns 201 regardless
// NrtKafkaProducerServiceImpl.publishDscKafkaMessage:111-126
CompletableFuture<...> dscCompletableFuture = kafkaDscPrimaryTemplate.send(dscKafkaMessage);
dscCompletableFuture.thenAccept(r -> log.info(...))
    .exceptionally(ex -> { handleFailure(dscTopicName, dscKafkaMessage, messageId, messageKey); return null; });
// NO terminal .join(), NO rethrow → method returns immediately; controller sends 201
```
`handleFailure(iac…)` **returns** `CompletableFuture<Void>` and on secondary failure `throw new CompletionException(new NrtiUnavailableException())` (`:159-175`). `handleFailure(dsc…)` is **`void`** and only logs on secondary failure (`:135-151`).

| Claim | Anchor | Verdict |
|---|---|---|
| Failover lives in `NrtKafkaProducerServiceImpl`, **not** audit-srv | whole class | ✅ |
| IAC: primary `.send` → `.exceptionally` → secondary → `.join()` → **500** on total fail | `:69, 87, 89, 91` + `NrtiUnavailableException` (`@ResponseStatus(INTERNAL_SERVER_ERROR)` = **HTTP 500**, *not* 503) | ✅ |
| IAC **blocks** the servlet thread (`.join()`) | `:89` outer `.join()` | ✅ (thread-occupancy risk; with `request.timeout.ms=300000`, a hung send pins the thread up to 5 min) |
| DSC is **fire-and-forget**, returns **201 regardless** | `:113-126` (no `.join()`, no rethrow); `handleFailure(dsc):135` is `void` | ✅ |
| 4 templates | `NrtKafkaProducerConfig:57-90` | ✅ |

**Honest phrasing:** *"There's a deliberate-looking asymmetry: IAC is synchronous-with-failover and returns 500 if both regions fail (`NrtiUnavailableException` is `@ResponseStatus(INTERNAL_SERVER_ERROR)` — the caller must know inventory actions didn't land); DSC is fire-and-forget and always 201. If I were hardening it I'd make DSC's contract explicit — right now a total DSC failure is invisible to the caller — and I'd arguably switch IAC's failure to a 503 + `Retry-After` since it's a retryable unavailability."*

## C.4 — IAC null partition key vs DSC `tripId` key (a prime ordering question)

```java
// IAC: sets MESSAGE_ID as a HEADER, NEVER KafkaHeaders.KEY
// IacServiceHelper.prepareIacActionKafkaMessage:186-211
MessageBuilder.withPayload(...)
  .setHeader(KafkaHeaders.TOPIC, iacTopicName)
  .setHeader(AppConstants.MESSAGE_ID, nrtInventoryActionsRequest.getMessageId())   // line 189 — a header, not the key
  ... (no KafkaHeaders.KEY anywhere) ...
```

```java
// DSC: sets the partition KEY = tripId
// DscServiceHelper.prepareDscKafkaMessage:262-269
MessageBuilder.withPayload(...)
  .setHeader(KafkaHeaders.KEY, buildTripId(dscRequest))   // line 264 — real partition key
  .setHeader(KafkaHeaders.TOPIC, dscTopicName) ...
```

| Claim | Anchor | Verdict | Honest phrasing |
|---|---|---|---|
| IAC has a **NULL partition key** → no per-key ordering | `IacServiceHelper:189` sets `MESSAGE_ID` header; **no `KafkaHeaders.KEY`** | ✅ (new — was missing) | "IAC messages have a null key, so the partitioner is sticky/round-robin → **no broker-level ordering guarantee for IAC**. If two events for the same node arrive close together, the consumer can see them out of order. `messageId` is a header for dedup, not a partition key." |
| DSC is keyed by `tripId` | `DscServiceHelper:264` `KafkaHeaders.KEY = buildTripId(...)` | ✅ | "DSC keys on `tripId`, so all events for one trip share a partition → ordered per trip." |

**Bullet 3 numeric authenticity score: 8/10.** Code mechanics fully verified and now far deeper (tuning matrix, IAC/DSC asymmetry, null-key ordering). `2M+`, `15-min DR`, `zero data loss` remain ops/estimate claims — reframed.

---

# D. Bullet 4 — Spring Boot 3 / Java 17 Migration (`cp-nrti-apis`)

> **Résumé phrasing under audit:** *"Led migration to Spring Boot 3.2 / Java 17, including RestTemplate→WebClient and SecurityFilterChain, with a Flagger canary ramping 10%→100% and zero customer-impacting incidents."*

| Claim phrase | Code evidence | Verdict | Honest phrasing |
|---|---|---|---|
| "**Spring Boot 3.2**" | `pom.xml:5-8` parent `spring-boot-starter-parent` **`3.5.14`**; BOM 3.5.7 elsewhere; `java.version 17` (`pom.xml:26`); Jakarta namespace (`jakarta.validation` in `DcInventoryController:21`). | 🟡 | "Lead with the correction: pom is **3.5.14**, not 3.2 — I led the 2.7→3.x jump and kept it current. Java 11→17." |
| "**Java 17**" | `pom.xml:26` `<java.version>17</java.version>` | ✅ | True. (Note: the *common JAR* is the lone Java-11/2.7.11 outlier — see Bullet 2.) |
| "**RestTemplate → WebClient**" | `cp-nrti-apis` has **no `RestTemplate`** anywhere — `HttpServiceImpl` already uses `WebClient` (`:71-94`). | ❌ | "There is no RestTemplate in this repo, so I can't claim a RestTemplate→WebClient migration here. (The *common JAR* has a dead `RestTemplate` import — proof the migration was already done upstream, not by me on this repo.)" |
| "**SecurityFilterChain** migration" | No `spring-boot-starter-security`, no `SecurityFilterChain`, no `WebSecurityConfigurerAdapter` in repo. Auth = gateway `WM_SEC.*` headers + custom servlet filters (`RequestFilter`, `XssFilter`, `NrtCorsFilter`, `StoreInboundRequestFilter`, `NrtResponseFilter`). | ❌ | "No Spring Security in the repo — auth is gateway-injected `WM_SEC.*` headers validated by hand-rolled servlet filters. Don't claim a Security migration." |
| "**Flagger canary 10%→100%**" | `kitt.yml:727-729` `stepWeight: 10`, `maxWeight: 50`, `interval: 2m`. | 🟡 | "It ramps in 10% steps to a 50% ceiling, then Flagger *promotes* to 100% — so '10→100' is true via the promote step, not a continuous ramp to 100." |
| Gate is **5xx-rate, threshold 1%** | `kitt.yml:734-735` metric *"Check for Internal Server Error (5XX)"*, `threshold: 1` over a 2-min window. | ✅ | "The only canary gate is 5xx-rate >1%. Volunteer the gap: a wrong-but-200 response or a latency regression sails through — I'd add a latency SLO + semantic check." |
| "**Zero customer-impacting incidents**" | Rollout property, not in code. | 🔵 | Label as a rollout outcome, not a code fact. |

**Bullet 4 numeric authenticity score: 6.5/10.** The two embedded sub-claims (`RestTemplate→WebClient`, `SecurityFilterChain`) are **false for this repo** — lead with that honesty; it reads as senior. The version correction and 5xx-only canary gate are strong, real talking points.

---

# E. Bullet 5 — DC Inventory Search API (`cp-nrti-apis`)

> **Résumé phrasing under audit:** *"Built a multi-site DC inventory API using a factory pattern, OpenAPI design-first 3-stage pipeline, 30% faster, with reactive WebClient calls to Enterprise Inventory."*

| Claim phrase | Code evidence | Verdict | Honest phrasing |
|---|---|---|---|
| "**Factory pattern**" for multi-site | No site-keyed `*Factory`. Only framework factories (`DefaultKafkaProducerFactory`, MapStruct `Mappers`). Multi-site = **same artifact per region + CCM** (`SiteIdCCMConfig`) + an **AOP aspect**. | ❌ | "There's no factory pattern. Multi-site is one artifact deployed per region with CCM config, plus `SiteIdFilterAspect` — an `@Around` AOP advice, not GoF factory. I'd describe it as config-driven multi-tenancy." |
| `SiteIdFilterAspect` does site filtering via AOP | `SiteIdFilterAspect:32` `@Pointcut("execution(* com.walmart.cpnrti.repository..*(..))")` + `:39-58` `@Around applySiteIdFilter(ProceedingJoinPoint)` enabling/disabling a Hibernate filter around every repo call. | ✅ | "Every repository call is wrapped by an aspect that toggles a siteId DB filter — automatic tenant isolation at the data layer." |
| "**Multi-site** US/CA/MX" | Single artifact; site resolved via CCM + the aspect; **no `*Factory` class**. | ✅ (mechanism) | True — just not via "factory." |
| "**OpenAPI design-first**" | It's a *process*. Codegen runs the `spring` generator on **only** `api-spec/schema/openapi_items_assortment.json` (`pom.xml:805,808` `<generatorName>spring</generatorName>`, `<inputSpec>...openapi_items_assortment.json</inputSpec>`). A second exec uses the `openapi` generator (docs only) on `openapi.json`. | 🟡 | "Design-first is a team process. The **only codegen'd controller is items-assortment**; the DC controller is **hand-written**." |
| "**3-stage pipeline**" | Ambiguous; not a single code artifact. | 🔵 | Scope it precisely or drop it. |
| DC endpoint | `DcInventoryController:104-105` `@ResponseStatus(HttpStatus.OK)` + `@PostMapping(value="/inventory/status")` (base path `AppConstants.NRTI_DC_APIS`), returns `ResponseEntity.ok()...` (`:146-149`). **Hand-written, not codegen'd.** | ✅ | "POST `…/inventory/status` → 200, hand-written controller (not generated)." |
| "**Reactive WebClient** to Enterprise Inventory" | `HttpServiceImpl.executeHttpRequest:71-94` `webClient.method(...).timeout(Duration.ofSeconds(10)).retryWhen(Retry.backoff(3, ofMillis(100)).maxBackoff(ofSeconds(2)).onRetryExhaustedThrow(...)).block()`. | ✅ (with caveat) | "WebClient with `.timeout(10s)` + `Retry.backoff(3, 100ms, max 2s)` — but `.block()` on the servlet thread, so it's reactive-client-on-MVC: a slow EI pins a Tomcat thread (occupancy risk)." |
| EI call shape | `DcInventoryServiceImpl:138-141` `httpService.sendHttpListRequest(uri, HttpMethod.GET, new HttpEntity<>(createDcInventoryHttpRequestBody(...)), ...)` — a **GET with a request body**. | ✅ | "The EI read is an unusual **GET-with-body** — works through WebClient but is non-idiomatic; some proxies strip GET bodies." |
| "**30% faster**" | Not in repo. | 🔵 | Estimate; label it. |

**Bullet 5 numeric authenticity score: 6/10.** `factory pattern` is the single biggest overclaim — pre-empt it. The real mechanisms (AOP siteId filter, hand-written DC controller, codegen-only-for-items-assortment, WebClient+`.block()`, GET-with-body) are all strong, specific, and honest.

---

# F. Bullet 2 — Common JAR (`dv-api-common-libraries`) — gap now closed

> **Résumé phrasing under audit:** *"Authored an org-wide Spring Boot starter that standardized audit logging via a single annotation."* (Previously this bullet was the one un-verified hole — it is now fully read.)

| Claim phrase | Code evidence | Verdict | Honest phrasing |
|---|---|---|---|
| "**Spring Boot starter**" | `pom.xml:6-7` `dv-api-common-libraries` **v0.0.45**, parent `spring-boot-starter-parent` **2.7.11** (`:18`), `java.version 11` (`:30`). **No `src/main/resources` directory at all** → **no `spring.factories`, no `META-INF/spring/...AutoConfiguration.imports`.** | ⚠️ | "It's a **plain library, not a true starter** — there's no auto-configuration metadata, so consumers must `@ComponentScan com.walmart.dv.*` and supply their own `WebClient` bean. Calling it a 'starter' is loose; it's a shared dependency." |
| "Single artifact, **org-wide**" | Consumed at v0.0.61 by `cp-nrti-apis` (`pom.xml:471`); in-repo source is v0.0.45. | 🟡 | "Widely consumed across DV services; 'org-wide' = de-facto within Data Ventures." |
| "**Java/Spring outlier**" | 2.7.11 / Java 11 while the services it serves run 3.5.x / Java 17. | ✅ | "The library is the lone 2.7/Java-11 holdout — a real upgrade-debt item I'd call out." |
| Async capture pool | `AuditLogAsyncConfig:17-26` `@EnableAsync` `ThreadPoolTaskExecutor` core **6** / max **10** / queue **100** / prefix `Audit-log-executor-`. | ✅ | **Correction to canon's "AbortPolicy":** the code calls only `setCorePoolSize/MaxPoolSize/QueueCapacity` and **never sets a `RejectedExecutionHandler`**, so the effective policy is Spring's `ThreadPoolTaskExecutor` default = **`AbortPolicy`** (throws `TaskRejectedException`). Net effect is the same — **once 10 threads + 100 queued are full, audit-log submissions are dropped/throw** — but say "default AbortPolicy (not explicitly set)," not "configured AbortPolicy." |
| `LoggingFilter` ordering / body capture | `LoggingFilter:35` `@Order(Ordered.LOWEST_PRECEDENCE)`, `:37` extends `OncePerRequestFilter`, `:83-86` wraps `ContentCachingRequest/ResponseWrapper`. | ✅ | "Runs last so it sees the final response; bodies are read-once via content-caching wrappers." |
| Audit POST transport | `AuditHttpServiceImpl:23,50-59` reactive `WebClient.method(...).block()`; **dead `import org.springframework.web.client.RestTemplate` at line 15** (unused). | ✅ | "It posts audit logs over WebClient `.block()`; the leftover RestTemplate import is dead — proof the WebClient move already happened upstream." |
| **Unmasked header copy** (real PII/secret leak) | `AuditLogFilterUtil.getServiceHeaders:94-108` iterates `request.getHeaderNames()` and puts **every** header (name→value) into the audit map with **no masking/allow-list**. `AppConstants:13-17` defines `CONSUMER_AUTH_SIGNATURE = "WM_SEC.AUTH_SIGNATURE"`, `WM_SVC_KEY_VERSION = "WM_SEC.KEY_VERSION"`. `AuditHttpServiceImpl:52` forwards **all** entity headers (`headers.addAll(...)`). No `mask.enable` anywhere. | ⚠️ (HIGH) | "**This is a genuine security gap I'd fix first:** the util copies *all* request headers verbatim — including `WM_SEC.AUTH_SIGNATURE`, `WM_SEC.KEY_VERSION`, `Authorization` — into the audit payload with no masking, then forwards them downstream. I'd add an allow-list + masking before claiming this is production-safe." |

**Note vs the audit producer (B.5):** this common-JAR `getServiceHeaders` copies *everything*; the `audit-srv` `KafkaProducerService.setHeaders` (B.1) re-filters to a 6-key allow-list before the topic. So the leak is on the *capture/forward* leg, mitigated (not fully) at the Kafka leg.

**Bullet 2 numeric authenticity score: 7.5/10** (upgraded from "🟡 cross-ref only"). Fully verified. "Starter" is loose (it's a library); the unmasked-header copy is a real finding to own.

---

# G. Operational / capacity anchors (so "scaling" has a real artifact)

| Metric | Anchor | Value |
|---|---|---|
| NRTI **stage** HPA | `cp-nrti-apis/kitt.yml:157-159` | `min 4 / max 8`, `cpuPercent 60` |
| NRTI **prod** HPA | `cp-nrti-apis/kitt.yml:485-487` | `min 6 / max 12`, `cpuPercent 60` |
| NRTI **iacprod** HPA | `cp-nrti-apis/kitt.yml:593-595` | `min 6 / max 12`, `cpuPercent 60` |
| Audit-srv **prod** HPA | `audit-api-logs-srv/kitt.yml:416-418` | `min 4 / max 8`, `cpuPercent 60` |
| Audit-srv **non-prod** HPA | `audit-api-logs-srv/kitt.yml:103-104` | `min 1 / max 2` |
| Flagger canary | `cp-nrti-apis/kitt.yml:727-729, 735` | `stepWeight 10 / maxWeight 50 / interval 2m`; 5xx gate `threshold 1` |

**Correction applied to canon framing:** NRTI **prod is min6/max12** (not min4/max8 — that's the *stage* profile). Use the right number per environment.

> **Topology numbers NOT in any repo:** partition count, `replication.factor`, `min.insync.replicas`, retention. The broker list shows 3 brokers per region ⇒ RF is *almost certainly* 3, but the rest is provisioned via Walmart KaaS. **Answer those with a sizing formula, never an invented number** (e.g. `partitions ≥ peak_throughput / per_partition_throughput`, and `≥ max consumer parallelism`).

---

# H. Claims with NO in-code backing (say "estimate / ops" — never "the code proves it")

| Claim | Where it lives | How to present |
|---|---|---|
| `<5ms P99` | overhead estimate (async hop), not freshness | "added overhead, not end-to-end; freshness is minutes (flush 600s)" |
| `millions` / `2M+ events` | traffic-derived | order-of-magnitude estimate |
| `eliminated Splunk` | business rationale | cost/queryability driver, not in code |
| `org-wide standard` | adoption | de-facto within Data Ventures |
| `2 weeks → 1 day` onboarding | adoption | estimate |
| `15-min DR vs 1-hour RTO` | DR game-days / CCM | ops metric; conflates RPO/RTO |
| `zero data loss` | — | reframe: at-least-once, no observable loss of an *acknowledged* event |
| `zero customer-impacting incidents` | rollout | rollout outcome |
| `30% faster` | — | estimate |

---

# I. Summary scorecard

| Bullet | Code-verified? | Score | Lead-with-this correction | Soft/ops numbers to flag |
|---|---|---|---|---|
| 1 — Audit logging | ✅ Fully (now line-cited) | **8.5/10** | `<5ms`=overhead not freshness; effective `acks=1` (no durability knobs set; CCM has no acks getter) ⇒ "zero loss" unsupported; dead `kafkaSecondaryTemplate`; unbounded `newCachedThreadPool` | millions, Splunk, org-wide, 2wk→1day |
| 2 — Common JAR | ✅ Fully (gap closed) | **7.5/10** | It's a **library not a starter** (no resources dir / spring.factories); **unmasked WM_SEC.* / Authorization header copy** is a real leak; dead RestTemplate import | org-wide |
| 3 — Active/Active NRTI | ✅ Fully (deepened) | **8/10** | `enable.idempotence=false` ⇒ at-least-once not exactly-once; **IAC null partition key** (no ordering) vs DSC `tripId`; IAC-500 vs DSC-201 asymmetry; `request.timeout.ms=300000` undercuts "fast failover" | 2M+, 15-min DR, zero loss |
| 4 — SB3 / Java17 | ✅ Fully | **6.5/10** | pom is **3.5.14** not 3.2; **no RestTemplate→WebClient** in repo; **no Spring Security** (gateway WM_SEC.* + servlet filters); canary 10→50→promote-100, 5xx-only gate | zero customer-impact |
| 5 — DC Inventory | ✅ Fully | **6/10** | **No factory pattern** (AOP `SiteIdFilterAspect` + per-region CCM); DC controller **hand-written**, codegen only for items-assortment; WebClient `.block()` on MVC thread; **GET-with-body** to EI | 30% faster, 3-stage |

**Overall code-authenticity: ~7.3/10.** Every mechanism is real and now anchored. The score is held down only by marketing adjectives/metrics that live in ops or estimates — and this doc tells you exactly which sentence to say so each one becomes senior-level candor instead of a caught overclaim.

**Bottom line:** walk in confident. The discipline is unchanged from day one — **state the precise truth first**, then explain why the real design is defensible (and what you'd harden). That single move converts every "gotcha" in this file into signal.
