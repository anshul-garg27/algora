# 11 — How Walmart Kafka Works Internally (Grounded in Our Code, Citation-per-Claim)

> **Purpose:** A from-scratch, *defensible-at-principal-level* explanation of how Kafka actually operates *at Walmart* — the managed platform (KaaS/KCaaS), the dual-region topology, the security model (mTLS-at-mesh), the CCM config plane, and how our two pipelines (audit Avro + NRTI JSON) ride on top. **Every factual claim below cites a real `path:line — Class#method`.** Read it after `06-KAFKA-MASTER-DEEPDIVE.md`; that file covers Kafka theory + our config, **this** file covers the *Walmart platform plumbing* underneath and corrects several things people get wrong about our setup.
>
> **Citations key.** Claims are anchored inline as `(repo/path:line — Class#method)`. The four repos live under `/Users/a0g11b6/Desktop/walmart`:
> - `cp-nrti-apis` — NRTI producer (Spring Boot 3.5 / Java 17)
> - `audit-api-logs-srv` — audit producer (Spring Boot, fire-and-forget)
> - `audit-api-logs-gcs-sink` — audit sink (Kafka **Connect** worker, NOT Spring)
> - `dv-api-common-libraries` — the shared JAR that does the actual log *capture*
> Plus the resolved config bundle `LUMINATE-CPERF-NRTI-APIS-NON-PROD-1_0/nrtKafkaConfig.json`.

---

## 0. The 60-second mental model

```
                  WCNP (Azure Kubernetes) — TWO REGIONS, ACTIVE/ACTIVE
   ┌──────────────────────────────────────┐   ┌──────────────────────────────────────┐
   │  EUS2 (East US 2)                      │   │  SCUS (South Central US)               │
   │  ┌──────────────────────────────────┐ │   │ ┌──────────────────────────────────┐ │
   │  │ cp-nrti-apis pod                  │ │   │ │ cp-nrti-apis pod                  │ │
   │  │  Istio sidecar = mTLS terminates  │ │   │ │  Istio sidecar = mTLS terminates  │ │
   │  └───────┬───────────────┬──────────┘ │   │ └───────┬───────────────┬──────────┘ │
   │  PRIMARY │      SECONDARY │            │   │ PRIMARY │      SECONDARY │            │
   │   (local)│       (remote) │            │   │  (local)│       (remote) │            │
   │          ▼               ╲            │   │         ▼               ╲            │
   │  ┌────────────────┐       ╲           │   │ ┌────────────────┐       ╲           │
   │  │ kafka-v2-       │        ╲──────────┼───┼─►│ kafka-v2-       │       ╲          │
   │  │ luminate-core-  │◄───────────────────────┤ luminate-core-  │◄───────╲─────────┐│
   │  │ prod.eus :9093  │                   │   │ │ prod.scus:9093  │         (failover)││
   │  │ (3 brokers, RF~3)│                  │   │ │ (3 brokers, RF~3)│                  ││
   │  └────────────────┘                   │   │ └────────────────┘                   ││
   └──────────────────────────────────────┘   └──────────────────────────────────────┘
     audit sink (Kafka Connect worker) ALSO runs per-region: prod-eus2 + prod-scus blocks
     (audit-api-logs-gcs-sink/env_properties.yaml:92-144)

(*) The producer config literally sets PLAINTEXT, but bytes are NOT naked on the wire:
    Istio mTLS wraps pod↔broker traffic; the client speaks plaintext only to its local sidecar.
    Two INDEPENDENT ssl flags, both default false:
      NRTI:  nrtKafkaSslEnabled          (cp-nrti-apis/ccm.yml:206, prod 816/828/840/852 = false)
      AUDIT: auditLoggingKafkaSslEnabled (audit-api-logs-srv/ccm/PROD-1.0-ccm.yml:50,70,81 = false)
```

The three Walmart-specific things to **say out loud** in an interview:

1. **Kafka is a managed platform (KaaS).** We don't run brokers. We request a topic (name, partitions, RF, retention) and the platform provisions it; we only ever see **broker URLs injected via CCM** (`cp-nrti-apis/ccm.yml:119-127`, `audit-api-logs-srv` via `AuditLogsKafkaCCMConfig.getAuditKafkaPrimaryBrokerUrls`). **That is why partition count / RF / min.insync / retention are nowhere in our repos** — they live in the KaaS provisioning request, so I answer those with a **sizing formula**, never an invented number.
2. **Security is mostly at the Istio mesh, not the Kafka client.** Both producers default `ssl=false` and log *"mTLS is enforced for Kafka connections"* (`NrtKafkaProducerConfig.java:140`, `KafkaProducerConfig.java:117`).
3. **"Active/active multi-region" is application-level dual-write, not MirrorMaker/stretch — and ONLY the NRTI producer actually fails over.** The audit producer has a `kafkaSecondaryTemplate` bean that is **dead code** (`audit-api-logs-srv/.../KafkaProducerService.java:31` autowired, never called). NRTI is the one that re-sends to the other region on failure (`NrtKafkaProducerServiceImpl.handleFailure`).

If you remember nothing else: **NRTI fails over, audit does not; audit is effective acks=1; IAC has a NULL Kafka key; audit freshness is minutes, not milliseconds.**

---

## 1. The platform layer: KaaS and KCaaS

### 1.1 KaaS (Kafka-as-a-Service) — why partition/RF numbers live *outside* the app repo

At Walmart you **don't operate brokers**. A central platform team runs the clusters (`kafka-v2-luminate-core-{stg|prod}`, listener port **9093**). As an app team you:

- **Request a topic** through the platform self-serve flow: name, partition count, `replication.factor`, `retention.ms`, `cleanup.policy`, `min.insync.replicas`. This is a *provisioning request*, not source code — which is exactly why **grepping our repos for `replication.factor` or `num.partitions` returns nothing**. The only topic *names* we see are CCM values (`nrtIacKafkaTopicName`, `dscKafkaTopicName` at `cp-nrti-apis/ccm.yml:131,201`; `auditLoggingKafkaTopicName` defaultValue `api_logs_audit_prod` at `audit-api-logs-srv/ccm/PROD-1.0-ccm.yml:40-41`).
- Get **broker URLs + secrets injected**, referenced via CCM (`nrtKafkaPrimaryBrokerUrls`/`nrtKafkaSecondaryBrokerUrls` read in `NrtKafkaProducerConfig.java:108-110`).
- The platform owns broker patching, rebalancing, disk, JMX/monitoring, ACLs, and the topic's partition/replica placement.

**Interview consequence (the honest framing):** when asked *"how did you pick 12 partitions / RF3 / 7-day retention?"* the answer is **"sized by formula, provisioned via KaaS — those knobs aren't in our app repo."** See §10 for the formula. Do not invent a number.

### 1.2 KCaaS (Kafka-Connect-as-a-Service) — the no-code consumer

Tier 3 of the audit pipeline (`audit-api-logs-gcs-sink`) is **not a Spring Boot app** — it's a **Kafka Connect worker**. Proof: the image is the KCaaS base, not a JVM app with a `main()` (`audit-api-logs-gcs-sink/Dockerfile:1` → `FROM docker.ci.artifacts.walmart.com/gdap-mystique-docker/kcaas-base-image:11-major`), and we ship a plugin uber-jar into `$PLUGIN_PATH` (`Dockerfile:13`).

What KCaaS gives you:

- A managed Connect **worker cluster** running in **distributed mode** (it needs internal topics `*-config`/`*-offset`/`*-status`, declared at `env_properties.yaml:32-34,115-117`).
- It runs your **connectors** (US/CA/MX), each declared in `kc_config.yaml:63-115`, each with `tasks.max: 1` (`kc_config.yaml:66,84,102`).
- Built-in **DLQ** (`errors.deadletterqueue.context.headers.enable: true`, `kc_config.yaml:70`), **error tolerance** (`errors.tolerance: all`, `kc_config.yaml:69`), **sink retry policy** (`connect.gcpstorage.error.policy: RETRY`, `connect.gcpstorage.max.retries: 5`, `connect.gcpstorage.retry.interval: 5000` at `kc_config.yaml:71-73`).

**Why it matters:** Connect is the *no-code consumer*. You don't write a `@KafkaListener`; you declare **where data goes** in **KCQL** and **transform** in **SMTs**. The KCQL lives in `env_properties.yaml` (e.g. prod-US `INSERT INTO 'audit-api-logs-us-prod:...' SELECT * FROM 'api_logs_audit_prod' PARTITIONBY service_name, _header.date, endpoint_name STOREAS 'PARQUET'`, `env_properties.yaml:221-231`) — **not** in `kc_config.yaml`, which only carries `connector.class`/`tasks.max`/`transforms`/error-policy. That split matters (a common mistake is to say "it's all in kc_config" — it isn't).

---

## 2. The two regions, one cluster name

Both regions run a cluster *named* `kafka-v2-luminate-core-prod` on `:9093` (`cp-nrti-apis/ccm.yml:121,127`). They are **separate physical clusters** the platform keeps as peers; our apps treat them as **primary (local) / secondary (remote)**. The per-region role flip is pure config:

```yaml
# cp-nrti-apis/ccm.yml — prod region overrides
# EUS2 deployment (lines 814-816)
nrtKafkaPrimaryBrokerUrls:   "kafka.kafka-v2-luminate-core-prod.eus.prod.us.walmart.net:9093"
nrtKafkaSecondaryBrokerUrls: "kafka.kafka-v2-luminate-core-prod.scus.prod.us.walmart.net:9093"
nrtKafkaSslEnabled: false
# SCUS deployment (lines 826-828) — primary/secondary SWAPPED
nrtKafkaPrimaryBrokerUrls:   "kafka.kafka-v2-luminate-core-prod.scus.prod.us.walmart.net:9093"
nrtKafkaSecondaryBrokerUrls: "kafka.kafka-v2-luminate-core-prod.eus.prod.us.walmart.net:9093"
nrtKafkaSslEnabled: false
```

The **same artifact** in both regions therefore produces an active/active picture: each region actively writes to its own cluster, and each can absorb the other's traffic on failover.

**This is application-managed replication, not broker-managed.** There is no MirrorMaker/MM2 mirroring topics between the two clusters anywhere in the repos; cross-region durability is achieved by the **producer dual-write on failure** — and *only in NRTI* (`NrtKafkaProducerServiceImpl.handleFailure`, see §4). The trade-off: under *normal* operation a successfully-sent message lives in **one** region's cluster only (the local one), not both. Cross-region redundancy only kicks in when the local send fails.

> ⚠️ **Honesty checkpoint.** A successful single send is durable **within one region** (assuming RF≥2 + min.insync.replicas≥2, which KaaS provisions — see §10), not **across both regions**, in the happy path. "Zero data loss across a regional outage" holds only for (a) messages produced *during* the outage that fail over, and (b) in-region replication durability. It does **not** mean every message is mirrored to both regions. Say it precisely.

---

## 3. Two producers, two completely different config stories

This is the section interviewers love and most people get wrong. **The audit producer and the NRTI producer share almost nothing.** Side by side, by file:line:

| Property | **Audit** `KafkaProducerConfig.populateConfigProperties` (`audit-api-logs-srv/.../KafkaProducerConfig.java:85-119`) | **NRTI** `NrtKafkaProducerConfig.populateConfigProperties` (`cp-nrti-apis/.../NrtKafkaProducerConfig.java:107-142`) |
|---|---|---|
| `bootstrap.servers` | set, line 87-88 | set, line 108-110 |
| key serializer | `StringSerializer`, line 89 | `StringSerializer`, line 111 |
| value serializer | `KafkaAvroSerializer`, line 90 | `JsonSerializer`, line 112 |
| schema registry url | set (`SCHEMA_URL_CONSTANT`), line 91 | — (no registry) |
| `auto.register.schemas` | **false**, line 92 | — |
| `acks` | **NOT SET** → client default `acks=1` | `all` (line 116, from `getNrtAcksConfig`) |
| `retries` | **NOT SET** → default | `10` (line 120, from `getNrtKafkaRetriesConfig`) |
| `enable.idempotence` | **NOT SET** | `false` (line 121) → **AT-LEAST-ONCE** |
| `linger.ms` | **NOT SET** | `20` (line 117) |
| `batch.size` | **NOT SET** | `8192` (8KB) (line 118) |
| `compression.type` | **NOT SET** | `lz4` (line 115) |
| `max.request.size` | **NOT SET** | `10000000` (10MB) (line 114) |
| `request.timeout.ms` | **NOT SET** → default 30s | `300000` (**5 min**) (line 119) |
| ssl branch | gated on `auditLoggingKafkaSslEnabled` (line 94) | gated on `nrtKafkaSslEnabled` (line 124) |

### 3.1 The "CCM declares but the interface never reads it" trap (audit)

The audit producer sets **only** bootstrap/serializers/schema-url/auto.register (+ optional SSL). It reads its config from the `AuditLogsKafkaCCMConfig` `@ManagedConfiguration` interface — and that interface **has no getter for acks/retries/idempotence**, so even if a CCM yml *declared* `acks`, `KafkaProducerConfig` never calls a getter for it and it **does not take effect**. The net result is **Kafka client defaults → effective `acks=1`**. There is no idempotence, no explicit retries.

> **Interview line:** *"Audit is effective `acks=1`. A CCM file could declare an acks value but our `@ManagedConfiguration` interface for audit never exposes a getter, so `populateConfigProperties` never reads it — it's dead config. NRTI is the opposite: every tuning knob is an explicit `getNrt…()` getter that `populateConfigProperties` puts into the producer map, so NRTI tuning genuinely applies."*

### 3.2 NRTI tuning genuinely applies — and here are the resolved values

NRTI reads each knob from `NrtKafkaCCMConfig` getters (`cp-nrti-apis/.../NrtKafkaCCMConfig.java:89-124`) and the resolved values are visible in the LUMINATE bundle:

```json
// LUMINATE-CPERF-NRTI-APIS-NON-PROD-1_0/nrtKafkaConfig.json (configResolution.resolved)
"nrtKafkaAcksConfig": "all",            // line 8
"nrtKafkaRetriesConfig": "10",          // line 5
"nrtKafkaIdempotenceConfig": "false",   // line 25  → AT-LEAST-ONCE (NOT exactly-once)
"nrtKafkaBatchSizeConfig": "8192",      // line 21  → 8KB
"nrtKafkaLingerMsConfig": "20",         // line 22  → 20ms
"nrtKafkaCompressionTypeConfig": "lz4", // line 28
"nrtKafkaMaxRequestSize": "10000000",   // line 26  → 10MB
"nrtKafkaRequestTimeoutMsConfig": "300000" // line 7 → 5 minutes
```

`acks=all` + `retries=10` + `idempotence=false` is honestly **at-least-once**: a retried send can duplicate, and without `enable.idempotence=true` (or `max.in.flight.requests=1`) ordering can break on retry. Correctness depends on **downstream dedup by `messageId`**, not on the producer.

### 3.3 mTLS exact config (SSL_PROTOCOL vs SECURITY_PROTOCOL)

A precise distinction that catches people: the NRTI producer always sets **`SslConfigs.SSL_PROTOCOL_CONFIG = "PLAINTEXT"`** by default (`NrtKafkaProducerConfig.java:122`, `AppConstants.KAFKA_PLAIN_TEXT_PROTOCOL="PLAINTEXT"` at `cp-nrti-apis/.../AppConstants.java:217`). It only sets **`CommonClientConfigs.SECURITY_PROTOCOL_CONFIG = "SSL"`** inside the `sslEnabled==true` branch (`NrtKafkaProducerConfig.java:130`, `KAFKA_PROTOCOL="SSL"` at `AppConstants.java:216`). So strictly: the client sets *ssl.protocol*, not *security.protocol*, in the default path. The thing that literally sets `security.protocol: PLAINTEXT` is the **Connect worker** config (`kc_config.yaml:14,23,32` — worker/consumer/producer all PLAINTEXT, every `ssl.*` line commented). The audit producer mirrors NRTI's branch logic (`KafkaProducerConfig.java:94-118`). JKS truststore/keystore come from `/etc/secrets` only when the flag is on (`KafkaProducerConfig.java:46,102-114`; NRTI via `AppUtil.getFileContents(...)` at `NrtKafkaProducerConfig.java:132-136`).

**What's really happening:** Istio sidecars establish **mutual TLS** for all pod↔broker traffic (SPIFFE identities, auto-rotating certs). The Kafka client speaks "plaintext" only over loopback to its local sidecar; the sidecar encrypts on the wire; the destination sidecar decrypts. The bytes are never cleartext on the network — the encryption boundary just moved out of the app. The two `ssl-enabled` flags are **independent** (`nrtKafkaSslEnabled` vs `auditLoggingKafkaSslEnabled`), both default false; the client-side JKS path is a deliberate fallback for broker-direct TLS if the mesh ever can't be trusted.

---

## 4. Failover: who actually has it (and the IAC/DSC asymmetry)

### 4.1 Audit: NO failover (dead secondary bean)

`audit-api-logs-srv` *looks* like it has dual-region failover — it autowires a secondary template (`KafkaProducerService.java:31`). But `publishMessageToTopic` only ever calls the **primary**:

```java
// audit-api-logs-srv/.../KafkaProducerService.java:39-52
public void publishMessageToTopic(LoggingApiRequest loggingApiRequest) {
  var topicName = auditLogsKafkaCCMConfig.getAuditLoggingKafkaTopicName();
  var kafkaMessage = prepareAuditLoggingKafkaMessage(loggingApiRequest, topicName);
  try {
    log.info("sending kafka msg ...");
    kafkaPrimaryTemplate.send(kafkaMessage);   // <-- primary ONLY; secondary never used
  } catch (Exception ex) {                      // catches almost nothing: send() is async
    log.info("Send failure falling into exception and Auditing", ex);
  }
}
```

`kafkaSecondaryTemplate` (line 31) is **dead code** — never referenced. And because `send()` returns a future, the `try/catch` around it catches construction errors only, not async send failures. So **audit has no region failover and no real send-error handling**: a broker-side failure is silently lost (no DLQ at the producer).

### 4.2 NRTI IAC: synchronous, fails over, returns 5xx on total failure

```java
// cp-nrti-apis/.../NrtKafkaProducerServiceImpl.java:60-100 (IAC)
iscompletableFuture = kafkaPrimaryTemplate.send(iacKafkaMessage);   // line 69 (sync ex → NrtiUnavailableException)
iscompletableFuture
   .thenAccept(... log partition/offset ...)                        // line 76-83
   .exceptionally(ex -> {                                           // primary failed
       handleFailure(iacTopicName, iacKafkaMessage, messageId).join();  // line 87: re-send to SECONDARY region
       return null;
   }).join();                                                       // line 89: BLOCKS the calling thread
// catch (CompletionException) → throw new NrtiUnavailableException();   line 90-91 → HTTP 5xx
```

The IAC `handleFailure` overload (`:159-175`) sends to `kafkaSecondaryTemplate`; if the secondary *also* fails it **rethrows** `throw new CompletionException(new NrtiUnavailableException())` (line 173), which the outer `.join()` surfaces as a `CompletionException` → `NrtiUnavailableException` → 5xx. So **a total dual-region failure correctly returns an error to the supplier so they retry.**

### 4.3 NRTI DSC: fire-and-forget, returns 201 even on total failure (a real smell)

```java
// cp-nrti-apis/.../NrtKafkaProducerServiceImpl.java:104-133 (DSC)
dscCompletableFuture = kafkaDscPrimaryTemplate.send(dscKafkaMessage);  // line 112
dscCompletableFuture
   .thenAccept(... log ...)                                            // line 113-120
   .exceptionally(ex -> { handleFailure(...); return null; });         // line 121-126: NO .join()
// method returns → caller returns 201 regardless
```

The DSC `handleFailure` overload (`:135-151`) returns `void` and only **logs** on secondary failure (line 145-150). There is **no `.join()`**, so the request thread never observes failure. **DSC returns 201 even when both regions are down.** That is an asymmetry vs IAC and a bug-smell I own (fix: emit a failure metric + DLQ, or return 202 honestly).

> **Trick-question ammo:** *"Show me where audit fails over."* → It doesn't; the secondary bean is dead code. *"Where does NRTI block the request thread?"* → IAC `.join()` at line 89. *"Where does NRTI silently swallow a failure?"* → DSC `handleFailure` (line 145-150) with no join.

---

## 5. Partition keys & ordering (the most-corrected fact in this doc)

| Pipeline | Kafka key | Where set | Ordering / dedup consequence |
|---|---|---|---|
| **Audit** | `serviceName + "/" + endpoint` | `KafkaProducerService.setHeaders` sets `KafkaHeaders.KEY` (`audit-api-logs-srv/.../KafkaProducerService.java:88-89`) from `AuditKafkaPayloadKey.getKafkaKey` (`AuditKafkaPayloadKey.java:26-28`) | All records for one service/endpoint co-locate on one partition → per-endpoint ordering + efficient Parquet `PARTITIONBY service_name,...,endpoint_name`. |
| **NRTI — DSC** | `tripId` | `DscServiceHelper.prepareDscKafkaMessage` sets `KafkaHeaders.KEY = buildTripId(...)` (`cp-nrti-apis/.../DscServiceHelper.java:264`) | All events for a trip land on one partition → per-trip ordering. |
| **NRTI — IAC** | **NULL** | `IacServiceHelper.prepareIacActionKafkaMessage` sets only `KafkaHeaders.TOPIC` and a `MESSAGE_ID` *header* (`cp-nrti-apis/.../IacServiceHelper.java:188-189`), **never `KafkaHeaders.KEY`** | **No partition key → round-robin/sticky partitioning → NO broker-level ordering for IAC.** `messageId` is a *header only* (`AppConstants.MESSAGE_ID="messageId"`, `AppConstants.java:239`); dedup/ordering is **entirely a downstream concern** keyed on that header. |

**This corrects the common error** that "NRTI keys by messageId." It does not. IAC sets `messageId` as a header for downstream dedup, not as the partition key, so IAC events can be spread across partitions and arrive out of order. Only DSC has a broker-level ordering guarantee (by `tripId`).

> **Interview phrasing:** *"Audit keys by service/endpoint; NRTI DSC keys by tripId; NRTI IAC has a **null** Kafka key — `messageId` is only a header — so IAC has no broker-level ordering and relies entirely on downstream dedup by `messageId`."*

---

## 6. End-to-end byte journeys (the two wire worlds)

### 6.1 Audit world (Avro, fire-and-forget, no failover)

```
API hits ANY dv-* service
  → dv-api-common-libraries LoggingFilter.doFilterInternal (capture happens IN THE COMMON JAR)
      gated by FeatureFlagCCMConfig.isAuditLogEnabled() (LoggingFilter.java:71; flag at FeatureFlagCCMConfig.java:14-15)
  → @Async POST to audit-api-logs-srv  v1/logRequest
  → AuditLoggingController.saveApiLog returns HTTP 204 NO_CONTENT IMMEDIATELY
      (AuditLoggingController.java:58-61)
  → ExecutorPoolService.executeTaskInThreadPool runs on Executors.newCachedThreadPool() — UNBOUNDED
      (ExecutorPoolService.java:10,12-14)
  → KafkaProducerService.publishMessageToTopic:
       Avro-serialize LogEvent via KafkaAvroSerializer (KafkaProducerConfig.java:90), schema by ID,
         auto.register.schemas=false (KafkaProducerConfig.java:92)
       key = "serviceName/endpoint" (AuditKafkaPayloadKey.getKafkaKey)
       allowed headers copied: wm_consumer.id, wm_qos.correlation_id, wm_svc.name/version/env, wm-site-id
         (KafkaProducerService.java:92-98)
       kafkaPrimaryTemplate.send()  [acks=1 default, no idempotence, no retries set, NO failover]
  → topic api_logs_audit_prod  (one immutable stream)
  → Kafka Connect worker (per region prod-eus2 + prod-scus): 3 connectors each read the WHOLE topic
       SMT1 InsertRollingRecordTimestampHeaders → adds _header.date = yyyy-MM-dd, GMT (kc_config.yaml:77-79)
       SMT2 FilterUS / FilterCA / FilterMX → keep my-country records, drop others
       KCQL → Parquet → audit-api-logs-{us|ca|mx}-prod GCS bucket (env_properties.yaml:221/341/459)
  → BigQuery external tables over the buckets → supplier self-service analytics
```

- **Serialization:** Avro + **Confluent Schema Registry** (`auto.register.schemas=false` → schemas pre-registered in CI; producer embeds only the schema **ID**, keeping payloads small and enforcing compatibility).
- **Why Avro here:** high-volume, long-lived analytics data → columnar Parquet + schema evolution + enforcement. JSON would bloat storage and lose schema enforcement.
- **Freshness reality:** the Connect sink buffers until `flush.size=50000000` (50MB) **or** `flush.count=5000` **or** `flush.interval=600` (10 min) — all three in `env_properties.yaml:227-229` (prod-US). So **audit freshness is minutes**, not "<5ms." The "<5ms" figure is the *producer-side overhead* added to the audited API by the async hop, **not** end-to-end freshness.

### 6.2 NRTI inventory world (JSON, real failover)

```
Supplier POST /inventory/actions → cp-nrti-apis IacServiceHelper builds Message<IacKafkaPayload> (JSON)
  → NrtKafkaProducerServiceImpl.publishIacKafkaMessage
       kafkaPrimaryTemplate.send() to LOCAL region
         acks=all, retries=10, idempotence=false, lz4, linger=20ms, batch=8KB, max.request=10MB, req.timeout=5min
  → CompletableFuture:
       success → log partition/offset (NrtKafkaProducerServiceImpl.java:80-83)
       failure → .exceptionally → handleFailure → kafkaSecondaryTemplate.send() to OTHER region → .join()
                 secondary fails too → CompletionException(NrtiUnavailableException) → HTTP 5xx
  → topic cperf-nrt-{env}-iac consumed by DOWNSTREAM Walmart services (we are producer-only)

DSC path: POST shipment → publishDscKafkaMessage → same shape BUT fire-and-forget,
          no .join(), returns 201 even on total failure (§4.3)
```

- **Serialization:** Spring `JsonSerializer` (`NrtKafkaProducerConfig.java:112`), **no Schema Registry** — contract is the OpenAPI/JSON schema; consumers are internal Walmart services.
- **Why JSON here:** lower volume, human-debuggable, tightly-coupled internal consumers, no analytics-storage concern.
- **Downstream coupling (compounds the IAC `.join()` risk):** the Enterprise Inventory read uses a reactive `WebClient` that **blocks the servlet thread**: `.timeout(Duration.ofSeconds(10))` + `.retryWhen(Retry.backoff(3, 100ms).maxBackoff(2s))` + `.block()` (`cp-nrti-apis/.../HttpServiceImpl.java:80-94`). Combined with IAC's `.join()`, a slow EI or a slow primary broker can pin a Tomcat thread for up to ~10s+retries. There is **no `orTimeout` anywhere** in `cp-nrti-apis/src` (verified by grep → empty), so a black-hole send is bounded only by `request.timeout.ms=300000` (5 min). That directly limits the "sub-second failover" claim to *fast* failures.

**Cardinal rule:** never mix the two worlds. Avro + Schema Registry + key=`service/endpoint` + Connect sink = **audit**. JSON + no registry + DSC key=`tripId` / IAC null-key = **NRTI**.

---

## 7. The audit sink in depth (Connect worker, 3 connectors, SMT routing)

### 7.1 Topology: 3 connectors → 3 consumer groups → 3× read amplification

`kc_config.yaml:60-115` declares three connectors — `audit-log-gcs-sink-connector` (US), `-ca`, `-mx` — each `tasks.max: 1`. Because each connector is its own Connect connector, each forms its **own consumer group** and reads the **entire** `api_logs_audit_prod` topic independently. **Net effect: the topic is read 3× (3× broker read amplification).** That's a deliberate isolation/simplicity trade (each country independently pausable/scalable; residency enforced at the storage boundary). At ~10× current volume I'd collapse to one connector that branches by header to per-bucket sinks to cut egress.

The worker is deployed **per region** — there are `prod-eus2` and `prod-scus` worker blocks (`env_properties.yaml:92-117` and `119-144`), distinguished by `indexes.name` `.indexes-eus2` vs `.indexes-scus` and `key.suffix` `_eus2`/`_scus`. So the real topology is "3 connectors × 2 regions," richer than "one cluster, one consumer."

### 7.2 SMT chain and the catch-all routing (with the lying Javadoc)

Each connector runs two SMTs (`kc_config.yaml:75-79`, etc.): `InsertRollingRecordTimestampHeaders` (adds `_header.date`, `yyyy-MM-dd`, GMT) then a country filter. The filter hierarchy:

```java
// BaseAuditLogSinkFilter.apply (BaseAuditLogSinkFilter.java:40-45): keep record iff verifyHeader, else null
// verifyHeader (line 52-64): STRICT — anyMatch(wm-site-id header present AND value == getHeaderValue())
//   → CA/MX inherit this strict base → a record with NO wm-site-id header is DROPPED.

// AuditLogSinkUSFilter.verifyHeader OVERRIDES (AuditLogSinkUSFilter.java:42-56):
//   anyMatch(wm-site-id == US value)  OR  noneMatch(wm-site-id header present)
//   → US is the CATCH-ALL: header-less records land in the US bucket.
```

**Proof from the unit tests** (`AuditLogSinkUSFilterTest.java`):
- `testUsFilterWithValidWmSiteId` → US value → `assertNotNull` (kept). (line 42-51)
- `testUsFilterWithNoWmSiteId` → header absent → `assertNotNull` (**kept by US**). (line 53-63)
- `testUsFilterWithInvalidWmSiteId` → MX value → `assertNull` (dropped by US). (line 66-75)

**The flag worth raising:** the CA/MX filter Javadoc (and even the US filter's class Javadoc at `AuditLogSinkUSFilter.java:13-14`) claims records pass "or if the header is missing" — but CA/MX inherit the *strict* base `verifyHeader`, which has **no** `noneMatch` branch, so they actually **drop** header-less records. The Javadoc is a **documented lie**; only US truly catches header-less records. That's a residency concern if a non-US service forgets `wm-site-id` (its logs silently route to the US bucket). Site IDs resolve via `AuditApiLogsGcsSinkPropertiesUtil.getSiteIdForCountryCode("US")` (`AuditLogSinkUSFilter.java:58-59`).

### 7.3 Worker consumer + sink settings (cited)

- Converters: `value.converter=io.confluent.connect.avro.AvroConverter` (`kc_config.yaml:8`), `key.converter=org.apache.kafka.connect.storage.StringConverter` (`kc_config.yaml:7`), `value.converter.schemas.enable: true` (`kc_config.yaml:9`).
- Consumer poll/timeouts: `max.poll.records: 50` (`kc_config.yaml:42`), `consumer.max.poll.records: 50` (`:49`), `session.timeout.ms: 15000` (`:45/:52`), `request.timeout.ms: 60000` (`:46/:53`), `heartbeat.interval.ms: 5000` (`:44`).
- KCQL/storage (in `env_properties.yaml`, prod): `STOREAS PARQUET`, `PARTITIONBY service_name, _header.date, endpoint_name`, `flush.size=50000000`/`flush.count=5000`/`flush.interval=600`, `gcp.project.id=wmt-dv-luminate-prod`, buckets `audit-api-logs-{us|ca|mx}-prod`, DLQ `api_logs_audit_prod_DLQ` (`env_properties.yaml:219-235` US, `337-354` CA, `456-473` MX).
- Group id (worker cluster, distributed mode): `kcaas-audit-logs-gcs-sink-connector` (`env_properties.yaml:113,140`).

---

## 8. CCM resolution flow (Strati `@ManagedConfiguration` → CCM env yml → secret.ref)

- **CCM (Strati `@ManagedConfiguration`)** is the live config plane. A typed interface annotated `@Configuration(configName=...)` with `@Property` getters (e.g. `NrtKafkaCCMConfig.java:11-12,18-19`; `FeatureFlagCCMConfig.java:7-15`) is injected via `@ManagedConfiguration` (`NrtKafkaProducerConfig.java:36-37`). At runtime the platform resolves each `@Property` to a value from the environment's CCM yml (e.g. `cp-nrti-apis/ccm.yml`), with **region overrides** (the `prod`/`eus`/`scus` blocks at `ccm.yml:805-852`).
- **Live-flippable vs not:** values like topic names and `nrtKafkaSslEnabled` are read on each access of the getter; but the **producer map** is built once in `populateConfigProperties` when the `DefaultKafkaProducerFactory`/`KafkaTemplate` bean is created (`NrtKafkaProducerConfig.java:57-100`). So flipping `acks`/`ssl` in CCM does **not** rebuild an already-constructed producer — it needs a producer-factory refresh/redeploy to take effect. Worth saying out loud when asked "can you change acks at runtime."
- **KITT (`kitt.yml`)** is the deployment manifest: stages, HPA (§9), the Flagger canary (§9), and **secret mounts** under `/etc/secrets` (the audit producer reads `path:/etc/secrets` at `KafkaProducerConfig.java:46`).
- **Secrets** are file-mounted (`/etc/secrets/...`) or `secret.ref://` / `secret.value://` in Connect (`env_properties.yaml:188,234` `secret.ref://gcs_key.json`; commented JKS refs at `kc_config.yaml:16-21`). Never inline. One non-prod placeholder path exists in the `dev` block (`env_properties.yaml:165` `gcskey.json`), prod uses `secret.ref://`.

**Chain:** KaaS provisions topic + injects broker URLs/secrets → CCM env yml resolves `@Property` values (with region overrides) → app reads via `@ManagedConfiguration` at bean-construction time → KITT deploys + canaries the pod.

---

## 9. Capacity & runtime (the real numbers an interviewer will probe)

| Knob | Value | Citation |
|---|---|---|
| **NRTI HPA prod** | min **6** / max **12** @ cpuPercent **60** | `cp-nrti-apis/kitt.yml:485-487` and `593-595` (two prod profiles) |
| NRTI HPA stage | min **4** / max **8** @ 60 | `cp-nrti-apis/kitt.yml:157-159` |
| NRTI HPA other/dev profile | min **2** / max **4** @ 60 (and a min1/max2 profile) | `kitt.yml:99-101`, `308-310` |
| **Audit HPA prod** | min **4** / max **8** @ 60 | `audit-api-logs-srv/kitt.yml:416-418` |
| Audit HPA (lower env) | min **1** / max **2** @ 60 | `audit-api-logs-srv/kitt.yml:103-104` |
| **audit-srv async pool** | `Executors.newCachedThreadPool()` — **UNBOUNDED** | `audit-api-logs-srv/.../ExecutorPoolService.java:10` |
| **Flagger canary (NRTI)** | `stepWeight: 10`, `maxWeight: 50`, `interval: 2m`, `progressDeadlineSeconds: 600` | `cp-nrti-apis/kitt.yml:727-730` |
| Canary gate | 5xx-rate `threshold: 1` (i.e. 1%) over 2m | `cp-nrti-apis/kitt.yml:735` |

**The unbounded pool is a real risk:** `newCachedThreadPool` spawns a thread per task under burst with no queue cap. Combined with the fire-and-forget audit producer, a traffic spike can explode threads → OOM. The thing that makes audit fast (204-then-async) is the thing that can kill it.

**The canary gate is blind to latency and semantics.** The PromQL is literally:

```promql
# cp-nrti-apis/kitt.yml:737-748
sum(rate(envoy_cluster_upstream_rq{cluster_name=~"outbound...-canary...", response_code_class=~"5.*", ...}[2m]))
/
sum(rate(envoy_cluster_upstream_rq{cluster_name=~"outbound...-canary...", ...}[2m])) * 100 > 0 or on() vector(0)
```

It only counts **5xx ratio**. A canary that returns **200-but-wrong** (bad payload, dropped field) or one that's **slow but ≤1% 5xx** sails through. That's why semantic + latency regressions need stage contract tests + perf gates, not just the canary.

---

## 10. Broker topology — what we can and cannot assert

- **Stage lists 3 brokers per region.** The resolved stage config enumerates exactly three broker hostnames each side: EUS2 `kafka-1589333338-{1,2,3}-...eus...:9093` and SCUS `kafka-886515205-{1,2,3}-...scus...:9093` (`nrtKafkaConfig.json:11-20`).
- **Prod uses a single DNS endpoint per region.** `kafka.kafka-v2-luminate-core-prod.{eus|scus}.prod.us.walmart.net:9093` (`cp-nrti-apis/ccm.yml:121,127,814-815`) — a load-balanced bootstrap, not an enumerated broker list.
- **Therefore RF is an *inference*, not a fact.** 3 brokers in stg ⇒ RF is *almost certainly* 3 (RF can't exceed broker count). But **partition count / `replication.factor` / `min.insync.replicas` / `retention.ms` are NOT in any repo** — they're KaaS-provisioned. Never invent a number.
- **Sizing formula (what I say instead of a number):** `partitions = max(ceil(target_throughput / per_partition_throughput), target_consumer_parallelism)`, then round up for headroom; pair `acks=all` with `min.insync.replicas = RF - 1` (so RF3 ⇒ misr=2 tolerates one broker loss while staying writable). Full derivation in `09-OPS-CAPACITY-SIZING-QA.md`.

---

## 11. Walmart-specific failure modes

1. **CCM misresolve / region override drift.** If a `prod-scus` override is missing/wrong, the SCUS pod could point its "primary" at EUS2 (or fail to resolve broker URLs), turning local writes into cross-region writes (latency) or startup failures. Mitigation: validate resolved CCM per region in canary; the `@ManagedConfiguration` getters fail fast on missing properties.
2. **Cert rotation at the mesh.** Istio auto-rotates mTLS certs; a rotation bug or a mesh policy that disables mTLS turns our PLAINTEXT client into **cleartext on the wire** — the mesh is the security SPOF (the client-side JKS fallback exists for exactly this, behind the ssl flag).
3. **KaaS quota / throttle.** Brokers are shared infra; if we exceed our provisioned partition/throughput quota, sends throttle. NRTI absorbs this with `linger=20ms` batching + `lz4`; audit (no tuning) just gets slower and, being acks=1 + fire-and-forget, can quietly drop under broker pressure.
4. **Connect cooperative-rebalance storm.** Each audit connector is `tasks.max:1`, so a single-task rebalance is cheap — but the worker also runs the internal config/offset/status topics; a worker restart or a bad connector config can churn the group. `session.timeout.ms=15000` (`kc_config.yaml:45`) bounds detection.
5. **Schema Registry outage (audit only).** `KafkaAvroSerializer` must resolve the schema ID against the registry (`value.converter.schema.registry.url`, `env_properties.yaml:93`). If it's unreachable, produce/consume fails. On the producer side it's caught-and-logged only (no DLQ) → audit record lost. Fix I'd propose: local schema cache + a delivery-failure metric.
6. **Connector lag isolation.** A slow connector (say MX) doesn't block US/CA (separate consumer groups), but its bucket falls behind; freshness for that country degrades on top of the already-minutes `flush.interval=600`.
7. **Unbounded `newCachedThreadPool` under burst** (§9) → thread explosion → OOM in audit-srv.
8. **Black-hole network for IAC.** With no `orTimeout` (grep-empty) and `request.timeout.ms=300000`, a hung send blocks the IAC `.join()` thread for up to 5 minutes → Tomcat pool exhaustion at load (compounded by the EI `WebClient.block()`). Fix: `future.orTimeout(2, SECONDS)` + bulkhead/circuit-breaker.

---

## 12. NEW interview questions (platform/topology; not in 06/08/09)

> Cross-references replace the schema/delivery Q&As that 06/08/09 already cover; the space is reinvested into code-citation questions.

### Platform & topology
**Q1. Who runs your Kafka brokers? What do you actually own?**
→ Brokers are run by the platform team via **KaaS**. We own the topic *request* (partitions/RF/retention — provisioned, not in repo), producer config via CCM, and for audit the Connect plugin + SMTs. We don't patch/rebalance/place replicas. *(`ccm.yml:119-127` broker URLs injected; no `replication.factor` anywhere in repo.)*

**Q2. How do you actually know your RF is 3? Show me.**
→ I don't know it for certain — it's an **inference**. Stage enumerates exactly 3 brokers per region (`nrtKafkaConfig.json:11-20`), and RF can't exceed broker count, so RF≈3 is very likely; prod uses a single DNS bootstrap (`ccm.yml:121`) so I can't read RF from config. The real RF/partitions/min.insync live in the KaaS provisioning request. I'd state the sizing formula, not a number.

**Q3. Your config says `PLAINTEXT` — defend it in a security review.**
→ TLS is terminated by **Istio mTLS** at the sidecar; the client speaks plaintext only over loopback. Precisely: the client sets `ssl.protocol=PLAINTEXT` by default (`NrtKafkaProducerConfig.java:122`) and only sets `security.protocol=SSL` + JKS when `nrtKafkaSslEnabled=true` (default false, `ccm.yml:206/816`). The wire is never cleartext unless mesh policy regresses; client JKS is the fallback for that case.

**Q4. Is your "active/active" broker-replicated or app-replicated, and does *every* service fail over?**
→ **App-replicated**, and **only NRTI fails over**. NRTI re-sends to the other region in `NrtKafkaProducerServiceImpl.handleFailure`. Audit's `kafkaSecondaryTemplate` is autowired (`KafkaProducerService.java:31`) but **never called** — dead code, no failover. No MirrorMaker anywhere.

**Q5. Stretch cluster across EUS2/SCUS instead — what changes?**
→ You'd get synchronous cross-region RF and no app failover code, but pay inter-region latency on every `acks=all` write and risk split-brain on a region partition. Our async dual-write keeps local writes fast and degrades gracefully; we own dedup as the cost.

**Q6. How does a topic get created here, and why isn't the partition count in your repo?**
→ It's a KaaS provisioning request (name/partitions/RF/retention/cleanup.policy). The platform creates it and injects broker URLs/secrets we read via CCM. The app only knows the topic *name* (`nrtIacKafkaTopicName`, `ccm.yml:131`); the partition count is platform-side, which is exactly why it's not greppable.

### Kafka Connect / KCaaS
**Q7. Prove the audit sink is Kafka Connect, not a Spring consumer.**
→ `Dockerfile:1` is `FROM ...kcaas-base-image:11-major` and `Dockerfile:13` copies a plugin uber-jar into `$PLUGIN_PATH`. There's no `@KafkaListener` and no `main()` — it's a Connect worker in distributed mode (internal topics at `env_properties.yaml:115-117`).

**Q8. Where is the KCQL defined — kc_config or env_properties?**
→ **env_properties.yaml**, not kc_config. `kc_config.yaml` only has `connector.class`/`tasks.max`/`transforms`/error-policy (`:63-115`). The `INSERT INTO ... STOREAS PARQUET PARTITIONBY ...` + flush/bucket/project all live in `env_properties.yaml` (e.g. prod-US `:221-235`). Conflating them is a common mistake.

**Q9. A record arrives with NO `wm-site-id` header. Where does it land — and prove it?**
→ **US bucket only.** `AuditLogSinkUSFilter.verifyHeader` ORs `noneMatch(header present)` (`:42-56`), so it's the catch-all; CA/MX inherit the strict base (`BaseAuditLogSinkFilter.verifyHeader:52-64`) and **drop** header-less records — despite their Javadoc claiming otherwise. Proof: `testUsFilterWithNoWmSiteId` → `assertNotNull` (`:53-63`). Residency concern if a non-US service forgets the header.

**Q10. Your 3 connectors each read the whole topic — justify the 3× egress.**
→ Isolation + simplicity: one immutable topic, residency enforced at the storage boundary, each country independently pausable/scalable (`kc_config.yaml:63-115`, each `tasks.max:1` = its own consumer group). Cost is 3× broker read amplification. At ~10× volume I'd switch to one connector branching by header.

**Q11. `flush.size`/`flush.count`/`flush.interval` — what's your real freshness SLA?**
→ 50MB **or** 5000 records **or** 600s, whichever first (`env_properties.yaml:227-229`). So audit freshness is **minutes**, not the "<5ms" — that's producer-side overhead on the audited API, a different latency.

**Q12. How does Connect avoid data loss on worker restart?**
→ It commits consumer offsets only after a successful sink flush; on restart it resumes from the last committed offset (at-least-once → possible duplicate GCS objects, deduped by object naming/downstream). Poison records go to the DLQ after `max.retries=5` (`kc_config.yaml:69-72`).

### Producers / config plane
**Q13. Show me where IAC sets its partition key.**
→ Trick question — **it doesn't**. `IacServiceHelper.prepareIacActionKafkaMessage` sets `KafkaHeaders.TOPIC` and a `messageId` *header* (`:188-189`) but never `KafkaHeaders.KEY`. IAC has a **null key** and no broker ordering. Only DSC keys (by `tripId`, `DscServiceHelper.java:264`).

**Q14. Audit producer durability — what's the real `acks`?**
→ **Effective `acks=1`.** `KafkaProducerConfig.populateConfigProperties` sets only bootstrap/serializers/schema-url/auto.register (+ optional SSL) and the `AuditLogsKafkaCCMConfig` interface has no acks getter, so client defaults apply. Even a CCM-declared acks wouldn't take effect because nothing reads it. I'd harden with `acks=all` + `min.insync.replicas=2` + idempotence.

**Q15. NRTI tuning — does it actually apply, and what are the values?**
→ Yes. `NrtKafkaProducerConfig.java:114-121` puts each value from a `NrtKafkaCCMConfig` getter into the producer map. Resolved: `acks=all`, `retries=10`, `idempotence=false`, `batch=8KB`, `linger=20ms`, `lz4`, `max.request=10MB`, `request.timeout=300000` (`nrtKafkaConfig.json:5-28`). That's honestly **at-least-once**.

**Q16. Change `acks` from `all` to `1` in prod without redeploying — can you?**
→ Partly. It's a CCM value, but the producer map is built once at bean construction (`NrtKafkaProducerConfig.java:57-100`). Flipping CCM updates the getter, but an already-constructed `KafkaTemplate` won't pick it up without a producer-factory refresh/redeploy. I'd be honest that it's not truly hot.

**Q17. How are Kafka secrets delivered to the pod?**
→ File-mounted under `/etc/secrets` via KITT (audit reads `path` default `/etc/secrets`, `KafkaProducerConfig.java:46`; NRTI via `AppUtil.getFileContents`, `:132-136`); Connect uses `secret.ref://`/`secret.value://` (`env_properties.yaml:188`). Never inline; only a non-prod placeholder path exists (`:165`).

### Operational / failover
**Q18. `request.timeout.ms` is 5 minutes — how is failover "sub-second"?**
→ Only for **fast** failures (connection refused / no brokers) where the future completes exceptionally immediately. A black-hole network waits up to 5 min before `.exceptionally`, and there's **no `orTimeout`** in the codebase (grep-empty). Fix: `future.orTimeout(2, SECONDS)` to bound failover for hung sends.

**Q19. IAC does `.join()` on the Tomcat thread — what happens at 10× load with a slow primary?**
→ Request threads block on Kafka (`NrtKafkaProducerServiceImpl.java:89`) → servlet pool exhaustion → cascading 5xx. Compounded by the EI read `WebClient...timeout(10s)...block()` (`HttpServiceImpl.java:80-94`) on the same thread. Fix: bulkhead + circuit breaker + bounded timeout, or move publish off-thread with a bounded queue.

**Q20. DSC returns 201 even when both regions fail. Defend or fix.**
→ Can't defend as correctness — it's an asymmetry vs IAC's block-and-5xx; DSC's `handleFailure` only logs (`:145-150`), no `.join()`. As best-effort telemetry it's tolerable but misleading. Fix: failure metric + DLQ, and return 202/5xx honestly or guarantee async durability.

**Q21. Where's your "15-minute DR recovery" in the code?**
→ It isn't — and I'm careful about RPO vs RTO. The **per-message code failover** (NRTI re-send to secondary) is the RPO mechanism (sub-second for fast failures). The **15-minute figure is an operational RTO target** (CCM region-pin flip + cluster health-back) from DR game-days, vs an older ~1-hour manual runbook. Neither the 15-min nor the 1-hour number has an in-repo artifact; I label them as ops, not code.

**Q22. How do you monitor this pipeline, and what's the honest gap?**
→ Connect exposes consumer lag / DLQ depth / task status; the app exposes Prometheus at `/actuator/prometheus` (`kitt.yml:752-754`); KaaS has broker dashboards. **Gap:** the audit producer has **no delivery metric** — only `log.info` lines (`KafkaProducerService.java:45-50`), and audit is fire-and-forget acks=1, so a silent loss wouldn't alert. I'd add a send-failure counter + alert.

### Design judgment
**Q23. Re-architect the audit geo-routing today — what would you do?**
→ Either (a) route at **produce time** to per-country topics (no read amplification, residency at source) at the cost of producer complexity + a topic per country, or (b) one connector with a branching transform to per-bucket sinks. Pick by volume: current scale favors today's simplicity; 10× favors (a)/(b).

**Q24. Make the audit producer lossless without hurting the "<5ms".**
→ The <5ms is the 204-then-async hop — independent of durability. So `acks=all` + idempotence + a **bounded** queue (replace `newCachedThreadPool`) keeps the caller's 204 instant, hardens durability, and a dropped-audit metric gives backpressure visibility.

**Q25. Why key audit by `service/endpoint` but DSC by `tripId` and IAC by nothing?**
→ Audit co-locates same-endpoint records for per-endpoint ordering + efficient Parquet `PARTITIONBY service_name,...,endpoint_name`. DSC keys by `tripId` so all events for a trip are ordered on one partition. IAC has no ordering requirement at the broker — events are independent and dedup is downstream by `messageId` header — so it intentionally has a null key.

**Q26. A supplier sends 10,000 items in one inventory request — what breaks on the Kafka side?**
→ `max.request.size=10000000` (10MB, `nrtKafkaConfig.json:26`) caps the produced record; a huge payload could exceed it → send fails. There's no batch cap on the DC `values` input. Fix: chunk the request and enforce a batch-size limit at the edge.

**Q27. Poison message the sink can't write — what happens?**
→ Connect routes it to the **DLQ** (`errors.tolerance: all` + DLQ headers, `kc_config.yaml:69-70`) after `connect.gcpstorage.max.retries=5` (`:72`); the connector keeps processing. Alert on DLQ depth (`api_logs_audit_prod_DLQ`, `env_properties.yaml:220`) and replay after fixing the record/schema.

**Q28. The canary passed but prod broke — how?**
→ The Flagger gate is **5xx-ratio only** over 2m (`kitt.yml:735-748`). A 200-but-wrong payload, a dropped audit field, or a sub-1%-5xx latency regression all pass it. Semantic correctness needs stage contract tests; latency needs a separate perf gate.

---

## 13. One-paragraph spoken summary (memorize this — corrected)

"At Walmart, Kafka is a managed platform — KaaS runs the brokers; we just declare topics and read broker URLs and secrets through CCM, which is why partition count and RF aren't even in our repo. We run two Azure regions, EUS2 and SCUS; our **inventory** service treats its local cluster as primary and the other region's as secondary and fails over **per-message in code** via `CompletableFuture.exceptionally` — so it's application-level active/active, not MirrorMaker. Importantly, **only NRTI fails over** — the audit producer has a secondary template that's dead code, so audit has no failover and is effectively `acks=1`, fire-and-forget. Security is mTLS at the Istio mesh, which is why the client config says PLAINTEXT — the bytes are encrypted by the sidecars. We run two serialization worlds: audit is Avro + Confluent Schema Registry, landing in GCS Parquet via a managed Kafka **Connect** sink whose SMTs geo-route by a `wm-site-id` header — three connectors, each reading the whole topic, so 3× read amplification, with US as the catch-all. The inventory pipeline is plain JSON, no registry, `acks=all` but idempotence off — honestly at-least-once with downstream dedup. And one thing people get wrong: **IAC has no Kafka key** — `messageId` is just a header — so IAC has no broker-level ordering; only DSC keys, by `tripId`. Audit freshness is **minutes** (`flush.interval=600s`), not the sub-5ms producer overhead. I can point to the exact line for every one of those claims."
