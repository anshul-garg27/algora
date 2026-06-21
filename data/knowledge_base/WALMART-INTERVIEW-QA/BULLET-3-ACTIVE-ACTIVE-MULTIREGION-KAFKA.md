# Bullet 3 — Active/Active Multi-Region Kafka with CompletableFuture Failover

> **Resume line (verbatim):**
> "Implemented Active/Active multi-region Kafka across EUS2/SCUS with CompletableFuture failover, achieving 15-min DR recovery (vs 1-hour RTO) with zero data loss."

---

## 0. TL;DR for the candidate (read this first)

The failover this bullet describes is **REAL and it lives in `cp-nrti-apis`**, specifically in:

- `cp-nrti-apis/src/main/java/com/walmart/cpnrti/services/impl/NrtKafkaProducerServiceImpl.java`
- `cp-nrti-apis/src/main/java/com/walmart/cpnrti/kafka/NrtKafkaProducerConfig.java`
- `cp-nrti-apis/src/main/java/com/walmart/cpnrti/configs/NrtKafkaCCMConfig.java`
- `cp-nrti-apis/ccm.yml` (broker URLs + tuning defaults + per-zone overrides)

It is a **producer-side application-level dual-write-on-failure** pattern: send to the primary-region Kafka cluster; if the send `CompletableFuture` completes exceptionally, send the **same** message to the secondary-region cluster. There are **4 `KafkaTemplate` beans** — IAC primary, IAC secondary, DSC primary, DSC secondary.

**Do NOT attribute this to `audit-api-logs-srv`.** That service has a `kafkaSecondaryTemplate` bean too, but it is **dead** — `KafkaProducerService.publishMessageToTopic` only ever calls `kafkaPrimaryTemplate.send(...)` inside a log-only `try/catch`. If the interviewer opens audit-srv, you must say "that's a different service; the failover bullet is the NRTI inventory event producer." (Section 6 scripts this.)

**Three things in this bullet are softer than they sound — own them before you're asked:**
1. **"Zero data loss"** — the code sets `acks=all` and `retries=10` (good), but `enable.idempotence=false` (`ccm.yml` line 197) and the failover is **at-least-once with possible duplicates and possible loss in narrow windows**. Not exactly-once. Defend it as "no *observable* loss for the business event under single-region failure," not literal zero.
2. **"15-min DR recovery (vs 1-hour RTO)"** — the *code* failover is **sub-second / per-message**, automatic. The "15 minutes" is the **operational/config-level** recovery (CCM region-pin flip / cluster rebuild), and "1-hour RTO" was the *old* manual runbook baseline. The resume conflates RPO/RTO terms — be precise.
3. **The two paths behave differently:** IAC publish **blocks** (`.join()`) and **rethrows 503** if both regions fail; DSC publish is **fire-and-forget** (no `.join()`) and swallows the failure. That inconsistency is real (`NrtKafkaProducerServiceImpl` lines 87–92 vs 124–126).

---

## 1. Plain-English: what this actually is (ELI5 → precise)

### ELI5
Imagine you mail a critical letter (an inventory event) and you have **two post offices** — one in East US (EUS2), one in South-Central US (SCUS). Both are open and working at the same time ("active/active"). You always try your nearest post office first. If it's shut (region outage), you **immediately walk to the other one** and mail the same letter there. You don't wait for someone to notice the first one is closed and reroute you — your own code does the reroute in milliseconds. That automatic "try-other-region-on-failure" is the `CompletableFuture` failover.

### Precise
`cp-nrti-apis` is a supplier-facing REST gateway. When a supplier posts an inventory action (`POST /store/inventoryActions`) or a direct-shipment capture (`POST /store/directshipment`), NRTI must publish a business event to Kafka so downstream consumers (`inventory-events-srv`) update inventory.

The Kafka cluster `kafka-v2-luminate-core-prod` is deployed in **two Azure regions**: **EUS2 = Azure East US 2** and **SCUS = Azure South Central US**. NRTI itself runs as two WCNP/Kubernetes deployments — one pinned to `zone: eus2`, one to `zone: scus`. CCM resolution path `/envProfile/envName/zone` gives each pod a **region-local primary** and the **other region as secondary**:

- A pod in `eus2`: primary = EUS brokers, secondary = SCUS brokers.
- A pod in `scus`: primary = SCUS brokers, secondary = EUS brokers.

(See `ccm.yml` `configOverrides` lines 805–852 — the broker lists are *swapped* per zone.)

On every publish, `NrtKafkaProducerServiceImpl`:
1. `kafkaPrimaryTemplate.send(message)` → returns a `CompletableFuture<SendResult>`.
2. `.thenAccept(...)` logs partition/offset on success.
3. `.exceptionally(ex -> { handleFailure(...) })` — on failure, re-sends the **same** message to `kafkaSecondaryTemplate` (the other region).

That is **application-level active/active failover** — no MirrorMaker, no stretch cluster, no waiting on a human or a DNS flip. The producer owns its own resilience.

---

## 2. The real architecture (grounded in code)

### 2.1 ASCII diagram — the NRTI dual-region producer

```
                          POST /store/inventoryActions  (IAC)   |  POST /store/directshipment (DSC)
                                                  │
                                                  ▼
        cp-nrti-apis  (Spring Boot 3.5.x / Java 17 / Jakarta)  — runs in BOTH regions
        NrtiStoreServiceImpl.handleInventoryActionsEvent()  (line 399-416)
            └─ Strati child txn "publishIacKafkaMessage" (try-with-resources)
                  │
                  ▼
        NrtKafkaProducerServiceImpl.publishIacKafkaMessage(Message<IacKafkaPayload>)
        ─────────────────────────────────────────────────────────────────────────
        future = kafkaPrimaryTemplate.send(msg)          // region-LOCAL cluster
        future
          .thenAccept(r -> log offset/partition)         // success path
          .exceptionally(ex -> {                          // ◄── FAILOVER TRIGGER
              log.warn("Primary failed, trying Secondary");
              handleFailure(topic, msg, msgId).join();    // re-send to OTHER region
              return null;
          })
          .join();                                        // IAC BLOCKS the caller
              │                                                   │
              ▼ (success or secondary-success)                    ▼ (both regions fail)
          return 201                                  throw NrtiUnavailableException → HTTP 503

        ┌──────────────── 4 KafkaTemplate beans (NrtKafkaProducerConfig) ─────────────────┐
        │  kafkaPrimaryTemplate     (IAC, getNrtKafkaPrimaryBrokerUrls)                     │
        │  kafkaSecondaryTemplate   (IAC, getNrtKafkaSecondaryBrokerUrls)                   │
        │  kafkaDscPrimaryTemplate  (DSC, primary)                                          │
        │  kafkaDscSecondaryTemplate(DSC, secondary)                                        │
        └──────────────────────────────────────────────────────────────────────────────────┘
                  │                                                  │
   primary send   ▼                                   on primary failure ▼
   ┌───────────────────────────────────┐            ┌───────────────────────────────────┐
   │  Kafka  kafka-v2-luminate-core-prod│            │  Kafka kafka-v2-luminate-core-prod │
   │  EUS region  (Azure East US 2)     │   ◄────►   │  SCUS region (Azure South Central) │
   │  ...eus.prod.us.walmart.net:9093   │            │  ...scus.prod.us.walmart.net:9093  │
   │  topics: cperf-nrt-prod-iac        │            │  topics: cperf-nrt-prod-iac        │
   │          cperf-nrt-prod-dsc        │            │          cperf-nrt-prod-dsc        │
   └───────────────────────────────────┘            └───────────────────────────────────┘
        (acks=all, retries=10, lz4, linger=20ms, batch=8192, idempotence=FALSE)
                  │                                                  │
                  └──────────────► downstream consumers (inventory-events-srv) ◄──────────┘
                                   consume from whichever cluster has the record
```

### 2.2 The real code (quote-for-quote)

**`NrtKafkaProducerServiceImpl.java` — the 4 autowired templates (lines 35–50):**
```java
@Autowired @Qualifier(AppConstants.NRT_KAFKA_PRIMARY_TEMPLATE)
private KafkaTemplate<String, Message<IacKafkaPayload>> kafkaPrimaryTemplate;
@Autowired @Qualifier(AppConstants.NRT_KAFKA_SECONDARY_TEMPLATE)
private KafkaTemplate<String, Message<IacKafkaPayload>> kafkaSecondaryTemplate;
@Autowired @Qualifier(AppConstants.DSC_KAFKA_PRIMARY_TEMPLATE)
private KafkaTemplate<String, Message<DscKafkaMessage>> kafkaDscPrimaryTemplate;
@Autowired @Qualifier(AppConstants.DSC_KAFKA_SECONDARY_TEMPLATE)
private KafkaTemplate<String, Message<DscKafkaMessage>> kafkaDscSecondaryTemplate;
```

**The IAC failover (lines 67–92) — this is the headline code:**
```java
CompletableFuture<SendResult<String, Message<IacKafkaPayload>>> iscompletableFuture;
try {
  iscompletableFuture = kafkaPrimaryTemplate.send(iacKafkaMessage);
} catch (Exception ex) {                       // synchronous send() failure (e.g. serialization)
  log.info("Send failure falling into exception and Auditing", ex);
  throw new NrtiUnavailableException();
}
try {
  iscompletableFuture
      .thenAccept(iacSendResult -> {
        RecordMetadata metadata = iacSendResult.getRecordMetadata();
        log.info("Sent ... partition: {}, and offset: {}", ..., metadata.partition(), metadata.offset());
      })
      .exceptionally(ex -> {                    // ◄── PRIMARY async failure
        log.warn("Failed to Publish Iac Event ... Primary region ... trying in Secondary region", ex.getMessage());
        handleFailure(iacTopicName, iacKafkaMessage, messageId).join();   // re-send to SECONDARY
        return null;
      }).join();                                // BLOCK the request thread
} catch (CompletionException ex) {
  throw new NrtiUnavailableException();         // both regions failed → 503
}
```

**The IAC secondary send (`handleFailure`, lines 159–175):**
```java
private CompletableFuture<Void> handleFailure(String iacTopicName, Message<IacKafkaPayload> iacKafkaMessage, String messageId) {
  return kafkaSecondaryTemplate.send(iacKafkaMessage)
      .thenAccept(sendResult -> { /* log secondary success offset */ })
      .exceptionally(ex -> {
        log.error("Secondary send failed: ...", ...);
        throw new CompletionException(new NrtiUnavailableException());   // propagate → 503
      });
}
```

**The DSC path (lines 104–151) — note: NO `.join()`, fire-and-forget:**
```java
CompletableFuture<SendResult<String, Message<DscKafkaMessage>>> dscCompletableFuture
    = kafkaDscPrimaryTemplate.send(dscKafkaMessage);
dscCompletableFuture
    .thenAccept(dscSendResult -> { /* log success */ })
    .exceptionally(ex -> {
      log.warn("Failed to Publish Event ... Primary region ... trying in Secondary region", ...);
      handleFailure(dscTopicName, dscKafkaMessage, messageId, messageKey);   // re-send, NOT joined
      return null;
    });
// returns immediately; HTTP 201 regardless of eventual Kafka outcome
```

**`NrtKafkaProducerConfig.java` — region selection (lines 107–110):** the same `populateConfigProperties` builds both factories; the only difference is the bootstrap server list, chosen by the `primaryServer` boolean:
```java
configProps.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, String.join(",",
    Boolean.TRUE.equals(primaryServer) ? nrtKafkaCCMConfig.getNrtKafkaPrimaryBrokerUrls()
                                       : nrtKafkaCCMConfig.getNrtKafkaSecondaryBrokerUrls()));
```
And the **durability tuning that the bullet leans on (lines 114–121):**
```java
configProps.put(ProducerConfig.MAX_REQUEST_SIZE_CONFIG, ...getNrtKafkaMaxRequestSize());   // 10_000_000
configProps.put(ProducerConfig.COMPRESSION_TYPE_CONFIG, ...getNrtCompressionTypeConfig()); // lz4
configProps.put(ProducerConfig.ACKS_CONFIG, ...getNrtAcksConfig());                        // all
configProps.put(ProducerConfig.LINGER_MS_CONFIG, ...getNrtLingerMsConfig());               // 20
configProps.put(ProducerConfig.BATCH_SIZE_CONFIG, ...getNrtBatchSizeConfig());             // 8192
configProps.put(ProducerConfig.REQUEST_TIMEOUT_MS_CONFIG, ...getNrtRequestTimeoutMsConfig()); // 300000
configProps.put(ProducerConfig.RETRIES_CONFIG, ...getNrtKafkaRetriesConfig());             // 10
configProps.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, ...getNrtKafkaIdempotenceConfig()); // FALSE
```
> **IMPORTANT:** Unlike `audit-api-logs-srv` (which never reads these keys and runs on Kafka client defaults), **NRTI genuinely reads and applies `acks`, `retries`, `lz4`, `linger`, `batch`, `idempotence` from CCM.** This is your strongest evidence that the durability story is real — but note `idempotence=false`.

**`ccm.yml` actual production values (lines 119–210):**
| CCM key | Default value | Meaning |
|---|---|---|
| `nrtKafkaPrimaryBrokerUrls` | `kafka.kafka-v2-luminate-core-prod.eus.prod.us.walmart.net:9093` | EUS brokers |
| `nrtKafkaSecondaryBrokerUrls` | `kafka.kafka-v2-luminate-core-prod.scus.prod.us.walmart.net:9093` | SCUS brokers |
| `nrtKafkaAcksConfig` | `all` | wait for all in-sync replicas |
| `nrtKafkaRetriesConfig` | `10` | client retries before giving up |
| `nrtKafkaIdempotenceConfig` | `false` | **NOT** idempotent → at-least-once |
| `nrtKafkaCompressionTypeConfig` | `lz4` | compression |
| `nrtKafkaLingerMsConfig` | `20` | batch linger |
| `nrtKafkaBatchSizeConfig` | `8192` | batch bytes |
| `nrtKafkaRequestTimeoutMsConfig` | `300000` | 5-min per-request timeout |
| `nrtKafkaMaxRequestSize` | `10000000` | 10 MB |
| `nrtIacKafkaTopicName` | `cperf-nrt-prod-iac` | IAC topic |
| `dscKafkaTopicName` | `cperf-nrt-prod-dsc` | DSC topic |
| `nrtKafkaSslEnabled` | `false` | SSL off in client → mTLS at Istio egress |

**`ccm.yml` `configOverrides` (lines 805–852) — the active/active swap:**
```yaml
- name: "prod-eus2"   # pods in EUS2
    nrtKafkaPrimaryBrokerUrls:   "...eus.prod.us.walmart.net:9093"   # local = primary
    nrtKafkaSecondaryBrokerUrls: "...scus.prod.us.walmart.net:9093"  # remote = secondary
- name: "prod-scus"   # pods in SCUS
    nrtKafkaPrimaryBrokerUrls:   "...scus.prod.us.walmart.net:9093"  # local = primary
    nrtKafkaSecondaryBrokerUrls: "...eus.prod.us.walmart.net:9093"   # remote = secondary
```
This is the literal definition of **active/active**: both regions take live writes simultaneously, each preferring its co-located cluster, each able to absorb the other's load on failure.

### 2.3 End-to-end flow (IAC, the strict path)
1. Supplier `POST /store/inventoryActions` (header `wm_svc.name=channelperformance-iac`).
2. `RequestFilter` → `NrtiApiInterceptor` → controller → `NrtiStoreServiceImpl.handleInventoryActionsEvent`.
3. Authorization (`StoreGtinValidatorServiceImpl` over Postgres), build `Message<IacKafkaPayload>` (`IacServiceHelper.prepareIacActionKafkaMessage`), key/header carry the **client-supplied** `messageId` (`IacServiceHelper` line 73–74, 189).
4. Strati child txn opens; `nrtKafkaProducerService.publishIacKafkaMessage(...)`.
5. `kafkaPrimaryTemplate.send(...)` → local-region cluster. Success → 201.
6. On async failure → `.exceptionally` → `kafkaSecondaryTemplate.send(...)` (other region). Secondary success → 201. Secondary failure → `CompletionException(NrtiUnavailableException)` → **HTTP 503**.

---

## 3. Every design decision

| # | Decision | Why | Alternatives considered | Trade-off / what we gave up |
|---|---|---|---|---|
| 1 | **Active/active dual cluster (both regions live)** | Zero-downtime writes; each region serves local pods → low latency; either region can absorb full load | **Active/passive** (cold/warm standby): cheaper but standby idle, slower recovery, capacity unproven until DR. **Single region**: no DR. | 2× Kafka infra cost; offsets diverge across clusters; downstream must dedup; ordering only per-partition-per-cluster |
| 2 | **Producer-side application failover (`CompletableFuture.exceptionally → secondary.send`)** | Sub-second automatic recovery owned by the service; no dependency on infra team / human runbook; works even mid-request | **MirrorMaker 2** (async cluster replication): replication lag = data loss window on failover, offset translation complexity. **Stretch cluster** (one cluster across regions): cross-region replica acks add latency, split-brain on partition. **Confluent Cluster Linking**: not standard in our platform era. | Producer must hold both clients (2× connections/memory); duplicate possible (same msg in both clusters); secondary path is hotter code (less battle-tested) |
| 3 | **Region pinning via CCM `/envProfile/envName/zone` with swapped broker lists** | Config-driven, no code change to flip which region is "primary" for a deployment; one image runs in both regions | Hardcode brokers per env; separate images per region (deploy sprawl). | CCM correctness is now a DR dependency; a bad zone resolution sends both pods to the same cluster |
| 4 | **`acks=all` + `retries=10` + `request.timeout=300s`** | Durability: leader waits for all in-sync replicas before ack; transient blips retried before failover fires | `acks=1` (faster, loses on leader crash); `acks=0` (fire-and-forget, lossy). | Higher write latency; `retries>0` without idempotence can **reorder** and **duplicate** |
| 5 | **`enable.idempotence=false`** | (Honest) likely chosen to avoid the broker-version/`max.in.flight` constraints of the platform era; keeps config simple | `enable.idempotence=true` (dedup within a producer session, prevents retry duplicates, requires `acks=all`, `retries>0`, `max.in.flight<=5`). | Loses producer-side exactly-once-into-a-partition; retries and failover can produce **duplicates** → pushes dedup responsibility onto consumers |
| 6 | **IAC blocks (`.join()`) and returns 503 on total failure; DSC fire-and-forget** | IAC is the system-of-record write — supplier must know it failed so they can retry. DSC (direct-shipment notification) is treated as best-effort. | Make both block; make both async. | **Inconsistent semantics** (a real smell): a dropped DSC event returns a misleading 201. Blocking IAC ties request latency to Kafka health. |
| 7 | **Client-supplied `messageId` as the event identity** | Lets the supplier set an idempotency key; lets consumers dedup the duplicate that failover/retries can create | Server-generated UUID per send (would change on each retry → no dedup help). | Trusts the client to send a *stable, unique* messageId; a buggy client breaks dedup |
| 8 | **`nrtKafkaSslEnabled=false` (SSL off in Kafka client) + mTLS at Istio egress** | Offload TLS to the service mesh; simpler client config; cert rotation handled by platform | mTLS in the Kafka client (JKS keystores, manual rotation — code path exists, lines 124–138, just disabled). | Security depends on Istio sidecar being present and correctly configured; in-process the connection is plaintext |
| 9 | **Reuse the same `populateConfigProperties` for primary & secondary** | DRY — only the bootstrap list differs | Two separate config methods. | If you ever needed asymmetric tuning per region, you'd have to refactor |

---

## 4. Deep-dive Q&A (fundamentals → internals → scenarios → behavioral)

### A. FUNDAMENTALS

**Q1. What does "active/active multi-region" actually mean here?**
"Both Azure regions — EUS2 and SCUS — run live Kafka clusters that take production writes at the same time. NRTI is deployed in both regions; each pod treats its co-located cluster as primary and the other region's cluster as its failover secondary. That's in `ccm.yml` lines 805–852: the EUS2 deployment has EUS as primary/SCUS as secondary, and the SCUS deployment has them swapped. It's active/active because neither region is idle — both serve real traffic — and either can absorb the other's load."

**Q2. Why Kafka in two regions at all? What's the failure you're guarding against?**
"An entire Azure region or the Luminate-Core Kafka cluster in one region going down. NRTI is on the write path for supplier inventory events; if our only Kafka cluster is unreachable, suppliers can't record inventory actions and downstream inventory state goes stale. Dual region means a regional outage degrades to a sub-second per-message failover instead of a full outage."

**Q3. What's the difference between active/active and active/passive, and why active/active?**
"Active/passive keeps a standby cluster idle until disaster, then you cut over. It's cheaper but the standby is unproven capacity, cutover is slower, and you can't serve from it normally. Active/active keeps both hot, so failover is instant and capacity is continuously validated. The cost is roughly double infra and the complexity of two clusters whose offsets diverge — which is why dedup matters downstream. For a write path with strict latency and DR expectations, active/active was the right call."

**Q4. Walk me through what `CompletableFuture` gives you here.**
"`KafkaTemplate.send()` in Spring Kafka (3.x) returns a `CompletableFuture<SendResult>`. The send is asynchronous — it returns immediately while the record sits in the producer's accumulator and is delivered in the background. I chain `.thenAccept()` for the success log and `.exceptionally()` as the failure hook. `.exceptionally` is exactly where I bolt on the cross-region failover: when the primary future completes with an exception, I synchronously kick off `kafkaSecondaryTemplate.send()` and `.join()` it so the original request thread waits for the secondary outcome before returning."

**Q5. What are the topics and message structure?**
"Two topics: `cperf-nrt-prod-iac` for inventory actions and `cperf-nrt-prod-dsc` for direct-shipment captures (CCM `nrtIacKafkaTopicName` / `dscKafkaTopicName`). The Spring `Message` carries the topic in `KafkaHeaders.TOPIC`. Value serializer is `JsonSerializer` (NRTI), key serializer is `StringSerializer`. The IAC key/headers carry the client's `messageId` (also copied into `correlationId`) — see `IacServiceHelper` lines 73–74 and 189."

### B. INTERMEDIATE

**Q6. Why `acks=all`? What does it buy and cost?**
"`acks=all` means the partition leader won't acknowledge my write until all in-sync replicas have it. Combined with a sensible `min.insync.replicas` on the broker (we rely on 2) and replication factor 3, I can lose a broker and not lose an acknowledged record. The cost is latency — I wait for replication before the future completes — but for an inventory system-of-record write that's the right trade. It's set in `ccm.yml` line 172 and applied in `NrtKafkaProducerConfig` line 116."

**Q7. You set `retries=10` but `enable.idempotence=false`. What's the consequence?**
"Honest answer: with retries on and idempotence off, two things can happen. First, **duplicates** — if a write actually succeeded but the ack was lost, the retry writes it again. Second, **reordering** — a retried record can land after a later record in the same partition. So my delivery guarantee is **at-least-once, not exactly-once**. I lean on the client-supplied `messageId` so downstream consumers can dedup. If I were hardening this, I'd flip `enable.idempotence=true` (which pins `max.in.flight.requests<=5` and requires `acks=all`, both compatible) to get exactly-once *into a single cluster* and eliminate the retry-duplicate/reorder class entirely."

**Q8. The primary `send()` is wrapped in try/catch AND has `.exceptionally`. Why both?**
"Two distinct failure surfaces. The synchronous `try/catch` around `kafkaPrimaryTemplate.send()` catches failures that happen *before* the record is enqueued — serialization errors, or `send()` blocking on metadata fetch and timing out (`max.block.ms`). The `.exceptionally` catches *asynchronous* delivery failures after the record was accepted into the buffer — broker unreachable, timeout, not-enough-replicas. The failover-to-secondary lives in `.exceptionally` because that's the path that fires on a real region/broker outage. The synchronous catch just rethrows 503 (line 70–73)."

**Q9. IAC does `.join()`; DSC does not. Explain and defend.**
"IAC chains `.exceptionally(...).join()` (line 89), so the request thread blocks until the event is durably in *some* region; if both fail it throws `NrtiUnavailableException` → 503, and the supplier knows to retry. DSC (lines 113–126) attaches the same failover but never `.join()`s — it returns 201 immediately and the secondary send happens on the producer's I/O thread, fire-and-forget. The rationale was that IAC is the authoritative inventory write (must not be silently lost) while DSC is a notification we treat as best-effort. **I'll be honest that this asymmetry is a smell** — a dropped DSC returns a misleading 201. If I owned it today I'd make DSC at least emit a failure metric and DLQ, or block it too."

**Q10. How does a pod know which region is "primary"?**
"CCM resolution path `/envProfile/envName/zone`. Each deployment runs with a `zone` (eus2 or scus). The `configOverrides` in `ccm.yml` map `zone: eus2` to EUS-primary/SCUS-secondary and `zone: scus` to the swap. So the *same* code and the *same* image read 'primary' as their local cluster. No code branches on region — it's pure config resolution."

**Q11. What serialization/Schema Registry is involved?**
"For NRTI's IAC/DSC the value serializer is Spring's `JsonSerializer` (line 112 of `NrtKafkaProducerConfig`) — JSON, no Schema Registry on this path. That's distinct from the *audit* pipeline (`audit-api-logs-srv`), which uses Confluent `KafkaAvroSerializer` + Schema Registry with `auto.register.schemas=false`. I keep these separate in my head because they're different products."

### C. DEEP / INTERNALS

**Q12. Walk the exact `CompletableFuture` chain for an IAC primary failure, step by step.**
"1) `kafkaPrimaryTemplate.send(msg)` returns `future`. 2) Background I/O thread tries EUS; it times out / gets not-enough-replicas. 3) The future completes exceptionally. 4) `.thenAccept` is skipped (it only runs on normal completion). 5) `.exceptionally(ex -> {...})` runs on the completing thread: logs the warn, calls `handleFailure(topic, msg, msgId).join()`. 6) `handleFailure` does `kafkaSecondaryTemplate.send(msg)` → SCUS, with its own `.thenAccept`/`.exceptionally`; on secondary failure it throws `CompletionException(NrtiUnavailableException)`. 7) The outer `.join()` (line 89) unwraps and rethrows that as `CompletionException`, caught at line 90, rethrown as `NrtiUnavailableException` → 503. On secondary *success*, `.exceptionally` returns null and the outer `.join()` completes normally → 201."

**Q13. Which thread runs `.exceptionally` and `handleFailure`? Any pool-exhaustion risk?**
"Because I don't pass an executor, the callbacks run on whatever thread completes the future — typically the Kafka producer's network/IO thread (`kafka-producer-network-thread`) or the calling thread if already complete. The `.join()` on IAC then blocks the **request (Tomcat) thread** until the secondary resolves. That's the real risk: if both regions are slow, IAC requests pile up on Tomcat worker threads and I can exhaust the servlet pool. The producer also has `max.block.ms` and `request.timeout.ms=300000` (5 min) which is *very* long — a slow primary could hold a request thread for minutes before failover even triggers. At 10x scale I'd cut `request.timeout.ms`, add an `orTimeout()` on the future, and bound the blocking with a circuit breaker."

**Q14. `request.timeout.ms=300000` is 5 minutes. Is that a problem for failover speed?**
"Yes, and it's a watch-out I'd raise proactively. `delivery.timeout.ms`/`request.timeout.ms` govern how long the client tries the primary before the future fails. At 5 minutes, a hard primary outage means a request could hang up to ~5 minutes before `.exceptionally` fires the failover. For 'sub-second failover' to be true, the failure has to be a *fast* failure (connection refused, no brokers) — a *slow* failure (network black hole) would be bounded by that timeout. The mitigation is lower timeouts plus `future.orTimeout(...)` so I bound failover latency explicitly rather than trusting the default."

**Q15. Offsets diverge across the two clusters. Why does that matter and how do you handle it?**
"EUS and SCUS are independent Kafka clusters — partition offsets are not coordinated. An event written to EUS at offset 500 might be the 'same' business event written to SCUS at offset 12 after a failover. So consumers can't use offset as identity, and they can't naively resume on the other cluster after failover and expect continuity. We handle identity at the **application layer** via `messageId`. For consumption, downstream consumes both clusters (or follows the active one) and dedups on `messageId`. This is the fundamental tax of dual-write active/active vs a single replicated cluster."

**Q16. What does 'zero data loss' actually require, and do you meet it?**
"True zero loss needs: (1) `acks=all` ✅, (2) `min.insync.replicas>=2` with `replication.factor>=3` (broker-side, we rely on RF3/ISR2) ✅, (3) `enable.idempotence=true` ❌ (we have false), (4) `retries>0` ✅ (10), (5) producer that doesn't drop on failure ✅ for IAC (blocks + failover + 503), ⚠️ for DSC (fire-and-forget). So I meet it for IAC under *single*-region failure: the message is durably committed in at least one region before I ack 201, and if neither acks I return 503 so the caller retries — no silent loss. Where I'm honest: idempotence=false means duplicates are possible (not loss), DSC can silently drop, and if BOTH regions are simultaneously unreachable the IAC caller gets a 503 and the durability is now *their* retry responsibility — we don't buffer to disk. So 'zero data loss' is accurate for the IAC business event under realistic single-region DR, not a literal exactly-once guarantee."

**Q17. What about ordering? Failover can reorder events.**
"Within one cluster's partition, order is preserved per key — but `retries>0` + idempotence=false can reorder on retry. Across a failover, ordering is definitely not guaranteed: events before the outage are in EUS, events during are in SCUS. For inventory actions, downstream reconciles using the event's own timestamps/sequence in the payload rather than Kafka order, and the operations are designed to be commutative/idempotent on `messageId`. If strict ordering mattered I'd need idempotence=true + a single source-of-truth partition, which active/active dual-write inherently fights."

**Q18. Why not MirrorMaker 2 instead of dual-write?**
"MM2 asynchronously replicates one cluster to the other. The problem on a write path: replication lag *is* your data-loss window — if EUS dies with 2 seconds of un-replicated records, those are lost when you cut to SCUS. MM2 also needs offset translation (`MirrorCheckpointConnector`) for consumer failover, and it's a separate moving part to operate. Dual-write from the producer means the record is committed to the surviving region *synchronously at write time* (for IAC), so my RPO is effectively zero per acknowledged IAC event rather than 'whatever MM2 lag was.' The cost is producer complexity and duplicates; MM2's cost is lag-window loss. For a system-of-record write, synchronous dual-write-on-failure wins."

**Q19. Why not a stretch cluster across regions?**
"A stretch cluster places replicas of one logical cluster across EUS and SCUS, so `acks=all` inherently means cross-region durability. It's elegant but cross-region replica acknowledgement adds tens of ms to every write, and a network partition between regions can cause leader-election thrash or unavailability (you need careful rack-aware placement + observer/witness for quorum). Our platform's Luminate-Core clusters are per-region, so stretch wasn't on the menu — and the latency cost on every write (not just failover) was undesirable."

**Q20. Both clusters can receive the same message during failover. How do consumers not double-process?**
"Consumer-side idempotency keyed on `messageId`. Downstream (`inventory-events-srv`) treats `messageId` as the dedup key — applying the same event twice is a no-op. That's why server doesn't generate a fresh UUID per send (which would defeat dedup); it preserves the **client-supplied** `messageId` end-to-end. Concretely the consumer either checks a processed-id store/cache before applying, or makes the downstream write itself idempotent (upsert keyed by messageId)."

**Q21. `nrtKafkaSslEnabled=false` — isn't that insecure for cross-region traffic?**
"The Kafka *client* TLS is disabled, but transport security is enforced at the **Istio service-mesh egress with mTLS** (`tlsMode: MUTUAL`). The code even has the full JKS keystore/truststore path (`NrtKafkaProducerConfig` lines 124–138) — it's just gated off by the flag. So the wire is still encrypted+mutually-authenticated by the sidecar; we offloaded it from the app. The honest risk: if a pod ran without the sidecar, the Kafka connection would be plaintext. In a hardened design I'd either enforce client mTLS or assert sidecar presence."

### D. SCENARIO / "WHAT IF"

**Q22. EUS2 region goes fully down. Walk me through what happens to an EUS2 pod's request.**
"The EUS2 pod's primary is EUS (down). `kafkaPrimaryTemplate.send()` future completes exceptionally (fast-fail if connection refused, or after `request.timeout.ms` if black-holed). `.exceptionally` fires → `kafkaSecondaryTemplate.send()` to SCUS (up). SCUS commits with `acks=all`, future succeeds, the IAC returns 201. The supplier sees a normal success, maybe with marginally higher latency. No data loss, automatic, no human. Meanwhile the SCUS-region pods are unaffected (their primary is SCUS). If the WCNP ingress also fails over traffic away from the dead region, the EUS pods just stop receiving requests entirely."

**Q23. Both regions are down simultaneously. What happens?**
"IAC: secondary send also fails → `CompletionException(NrtiUnavailableException)` → HTTP 503. The supplier retries later. We do **not** buffer to disk — durability becomes the caller's retry responsibility. DSC: silently drops (returns 201) — that's the weak spot. From the SCALING doc, the producer's in-memory buffer holds ~30s of events but beyond a brief blip, dual-region-down means we accept that audit/best-effort events are lost and alert immediately. For IAC the 503 contract prevents silent loss."

**Q24. Primary succeeds but you got a duplicate in secondary. How?**
"That shouldn't happen with the current code on a clean success — `.exceptionally` only fires on primary *failure*, so we don't dual-write on success. The duplicate risk is *within* a single cluster from `retries=10` + idempotence=false: a write whose ack was lost gets retried and committed twice. Across clusters, a duplicate happens only if the primary actually committed but reported failure (ack lost) and we then also wrote to secondary. Both cases are handled the same way — consumer dedup on `messageId`."

**Q25. The interviewer opens `audit-api-logs-srv` and sees only `kafkaPrimaryTemplate.send()` with a log-only catch. 'Where's your failover?'**
"Different service. `audit-api-logs-srv` is the *audit-logging* producer — best-effort fire-and-forget telemetry, returns 204 immediately. It has a `kafkaSecondaryTemplate` bean wired up (`KafkaProducerConfig` lines 60–63) but the send path (`KafkaProducerService.publishMessageToTopic` line 47) only uses primary inside a log-only try/catch — so on that service the secondary is effectively **dead code / unfinished**. The active/active failover the resume bullet refers to is the **business-event producer in `cp-nrti-apis`** — `NrtKafkaProducerServiceImpl` — which has the real `CompletableFuture.exceptionally → secondary.send` for both IAC and DSC. I'd never claim audit-srv has failover; that would be caught immediately."

**Q26. A `messageId` collision across two suppliers — what breaks?**
"If two different events share a `messageId`, consumer dedup would wrongly drop the second as a duplicate. `messageId` is client-supplied (`IacServiceHelper` line 73), so we trust suppliers to use globally-unique IDs (typically a UUID or their own idempotency key). The mitigation would be to namespace dedup by `supplierId + messageId` rather than `messageId` alone. Worth flagging as a hardening item."

**Q27. Failover works for sends, but what about consumer failover and offset continuity?**
"That's the harder half and lives in the consumer services, not NRTI. Because offsets diverge, a consumer that was reading EUS can't resume SCUS at the same offset. The pattern is either: (a) consumers run in both regions reading their local cluster and dedup downstream, or (b) on failover the consumer starts from the secondary's current end and relies on the producer having dual-written the in-flight window. NRTI only owns the producer side; I'd be candid that end-to-end consumer DR is a system property I contributed the producer half of."

**Q28. How do you test this failover without taking down a region?**
"Integration: Testcontainers/embedded Kafka with two broker sets; point primary at a port I can kill mid-test and assert the record lands on secondary. Unit: mock both `KafkaTemplate`s, complete the primary future exceptionally, verify `kafkaSecondaryTemplate.send()` is invoked exactly once and that secondary failure throws `NrtiUnavailableException`. Chaos: in staging, network-partition or kill the local broker and assert 201 still returns and the record appears in the other cluster. The RaaS resiliency gate in our pipeline does broker-kill scenarios."

**Q29. At 10x volume, what breaks first and what do you change?**
"First pain: the IAC `.join()` blocking Tomcat threads. Under 10x with any primary latency, request threads saturate. Fixes in order: (1) lower `request.timeout.ms` from 300s and add `future.orTimeout(N)` to bound failover latency; (2) move off blocking `.join()` — return 202/queue and confirm async, or use a bounded executor for the failover so it can't exhaust the request pool; (3) `enable.idempotence=true` to kill retry-duplicates/reorders; (4) raise `batch.size`/`linger.ms` for throughput; (5) add a circuit breaker so a dead primary trips fast instead of every request paying the timeout; (6) per-region producer metrics + DLQ for the both-down case so we stop relying on best-effort buffering."

### E. BEHAVIORAL

**Q30. Why did you build the failover in the producer instead of asking the platform team for replicated clusters?**
"Time-to-resilience and ownership. Cluster-linking/MirrorMaker is a platform capability with its own lead time and a lag-based RPO I didn't want on a system-of-record write. Owning failover in my service gave me a synchronous, sub-second, zero-RPO-per-acked-event guarantee for IAC, testable in my own pipeline, with no cross-team dependency. The trade I accepted was producer complexity and consumer-side dedup, which I considered manageable given we already had a stable `messageId`."

**Q31. What's the thing you're least proud of in this implementation?**
"The IAC/DSC asymmetry and the 300s timeout. DSC returning 201 on a silently dropped event is a correctness gap — best-effort is fine, but it should at least emit a failure metric and DLQ, not look like success. And `request.timeout.ms=300000` undercuts the 'fast failover' story for black-hole failures. If I were doing it again I'd standardize the two paths, bound the failover with `orTimeout`, and turn on idempotence."

**Q32. How did you validate the 15-minute DR number?**
"It's an operational-recovery figure, not the per-message code latency. The code failover is sub-second. The 15 minutes is the time to operationally recover from a *config/cluster-level* event — e.g. flipping the CCM region pin or standing a cluster back up and confirming health — measured in DR game-days against the prior manual runbook that was an hour. I'm careful to separate 'automatic per-message failover (sub-second)' from 'full operational recovery (~15 min)' so I'm not overstating the code."

---

## 5. Defending the numbers

**"Active/Active across EUS2/SCUS"** — verifiable in `ccm.yml`: prod broker URLs are `...eus.prod.us.walmart.net:9093` and `...scus.prod.us.walmart.net:9093` (lines 121–127), and `configOverrides` (805–852) swap primary/secondary per `zone`. Both regions take live writes. **Solid, fully grounded.**

**"CompletableFuture failover"** — `NrtKafkaProducerServiceImpl` lines 67–92 (IAC) and 104–151 (DSC): `kafkaPrimaryTemplate.send()` returns `CompletableFuture<SendResult>`, `.exceptionally` re-sends via `kafkaSecondaryTemplate`. **Solid, fully grounded — quote the exact lines.**

**"15-min DR recovery (vs 1-hour RTO)"** — *Be precise.* The **code** failover is sub-second/per-message and automatic. The **15 minutes** is operational recovery (CCM region-pin flip / cluster health-back), measured in DR game-days vs the old ~1-hour manual runbook. Note the resume mixes terms: "DR recovery" ≈ RTO; the proper RPO claim is "≈0 per acknowledged IAC event." If pushed: *"The automatic failover is sub-second; 15 minutes is the operational RTO for a full regional recovery, down from a one-hour manual process — and RPO is effectively zero for acknowledged inventory events because of `acks=all` plus dual-write-on-failure."*

**"Zero data loss"** — Defensible **only** as "no observable loss of an acknowledged IAC business event under single-region failure," via `acks=all` (ccm.yml 172) + RF3/ISR2 + failover-or-503. **Caveats you must volunteer:** `enable.idempotence=false` (line 197) → at-least-once with possible duplicates; DSC is fire-and-forget (can silently drop); both-regions-down returns 503 (loss becomes caller's retry responsibility, no disk buffering). Say *"zero loss, not exactly-once — duplicates are possible and handled by consumer-side dedup on messageId."*

---

## 6. HONEST watch-outs (if they open the code)

1. **`audit-api-logs-srv` secondary is dead** — `KafkaProducerService.publishMessageToTopic` (line 47) only calls `kafkaPrimaryTemplate.send()`; the `kafkaSecondaryTemplate` bean (KafkaProducerConfig 60–63) is autowired but never used. **Script:** "That's the audit telemetry service, not the failover bullet — failover is in cp-nrti's `NrtKafkaProducerServiceImpl`." Never claim audit-srv has working failover.
2. **`enable.idempotence=false`** (ccm.yml 197) — directly weakens "zero data loss." Pre-empt it: "at-least-once + consumer dedup; I'd turn idempotence on to harden."
3. **DSC fire-and-forget returns 201 even on total failure** (lines 113–133, no `.join()`) — inconsistent with IAC. Own it as a known smell.
4. **`request.timeout.ms=300000` (5 min)** — undercuts "fast failover" for black-hole failures; failover is only sub-second on *fast* failures. Mitigation: `orTimeout` + lower timeout.
5. **IAC `.join()` blocks the Tomcat request thread** — couples request latency to Kafka health; pool-exhaustion risk at scale. (Section Q13/Q29.)
6. **`messageId` is client-supplied** (`IacServiceHelper` 73) — dedup correctness depends on the supplier sending unique IDs; collision = wrongful drop.
7. **RPO/RTO conflation in the resume wording** — "15-min DR recovery (vs 1-hour RTO)" mixes terms. Be ready to define RPO (data-loss window ≈0 for acked IAC) vs RTO (time-to-recover ≈15 min operational, sub-second automatic per message).
8. **"Active/active" with no consumer-side DR ownership in NRTI** — NRTI is producer-only (no `@KafkaListener`). Consumer failover/offset-continuity lives in downstream services; don't claim end-to-end consumer DR as your code.
9. **SSL disabled in client** (`nrtKafkaSslEnabled=false`) — explain mTLS-at-Istio; the in-app connection is plaintext if the sidecar is absent.
10. **`@SneakyThrows` + broad catches** hide root causes; failover decisions are made on `Exception` generically, not typed Kafka exceptions — a retryable-vs-fatal distinction would be better.

---

## 7. Follow-up rabbit holes (and crisp answers)

- **"`max.in.flight.requests.per.connection` default is 5 with retries — combined with idempotence=false, reordering?"** → "Yes, reordering is possible on retry. Turning idempotence on keeps `max.in.flight<=5` *and* deduplicates+orders by sequence number, fixing it. Today downstream tolerates reorder via payload timestamps + messageId idempotency."
- **"What's `min.insync.replicas` and who sets it?"** → "Broker/topic config, not producer. We rely on ISR=2 with RF=3 so `acks=all` tolerates one replica down. If ISR drops below 2, `acks=all` writes fail with NotEnoughReplicas — which would *trigger my failover to the other region*, actually a feature here."
- **"If primary commits but ack is lost and you failover, you have the record in both clusters with different offsets — reconcile?"** → "Consumer dedups on messageId regardless of cluster/offset; offsets are never used as identity."
- **"Why `CompletableFuture` and not Reactor `Mono`, since the codebase uses WebClient/Reactor?"** → "Spring Kafka's `KafkaTemplate.send()` returns `CompletableFuture` in 3.x (it moved off `ListenableFuture`). I stayed with the native return type rather than wrapping in Reactor for a single send+fallback. For the EI HTTP calls I do use Reactor (`Retry.backoff`)."
- **"`thenAccept` vs `thenApply` vs `whenComplete` — why `thenAccept`?"** → "`thenAccept` consumes the result without returning a value (I just log offset). `thenApply` would transform it. `whenComplete` sees both result and exception but doesn't swallow — I specifically wanted `.exceptionally` to *recover* (re-send to secondary and return null), which `whenComplete` can't do cleanly. So `thenAccept` (success log) + `exceptionally` (recover) was the right pair."
- **"`orTimeout` — would you add it?"** → "Yes. `future.orTimeout(2, SECONDS)` would bound how long I wait on primary before treating it as failed and failing over, decoupling failover latency from the 5-minute `request.timeout.ms`."
- **"What happens to the producer's in-flight buffer on a region kill?"** → "Records in the accumulator that haven't been acked get retried (up to `retries=10`/`delivery.timeout`); if they ultimately fail, the future completes exceptionally and my `.exceptionally` failover catches them for IAC. For DSC there's no join so a tail of records could be lost."
- **"Could you lose ordering between primary-committed and secondary-committed events for the same key?"** → "Yes across the failover boundary. Mitigated by idempotent, commutative downstream application keyed on messageId + event timestamp."
- **"Split-brain?"** → "Not applicable to dual-write producers the way it is to a stretched quorum — there's no shared leadership to split. The cost I pay instead is divergence/duplication, handled by dedup. A stretch cluster is where split-brain bites."

---

## 8. One-paragraph + 30-second pitch

**One paragraph.** In `cp-nrti-apis`, the supplier-facing inventory-event producer, I implemented application-level active/active failover across Walmart's two Azure Kafka regions, EUS2 and SCUS. The service runs in both regions; via CCM (`/envProfile/envName/zone`) each pod treats its co-located `kafka-v2-luminate-core-prod` cluster as primary and the other region as secondary, with broker lists swapped per zone in `ccm.yml`. On every publish, `NrtKafkaProducerServiceImpl` sends to the primary `KafkaTemplate`, and on the returned `CompletableFuture`'s `.exceptionally` it re-sends the identical message to the secondary-region template — sub-second, automatic, no human in the loop. With `acks=all`, RF3/ISR2, and `retries=10`, an acknowledged inventory action is durably committed in at least one region or the caller gets a 503 to retry, so there's no silent loss of the business event. I'm candid that it's at-least-once not exactly-once (`enable.idempotence=false`), so duplicates are deduped downstream on a client-supplied `messageId`, and that DSC is best-effort while IAC blocks-and-503s.

**30-second verbal.** "Our inventory-event service runs in both Azure regions, EUS2 and SCUS, each writing to its local Kafka cluster as primary. On every send I get a `CompletableFuture` back from `KafkaTemplate`, and in its `.exceptionally` I automatically re-send the same message to the other region's cluster — so a regional Kafka outage degrades to a sub-second per-message failover instead of an outage. With `acks=all` and replication factor 3, an acknowledged inventory action is durable in at least one region or the supplier gets a 503 to retry, so no silent data loss. It's at-least-once, so I keep a stable `messageId` for consumer-side dedup. The automatic failover is sub-second; full operational regional recovery is about 15 minutes, down from a roughly one-hour manual runbook."
