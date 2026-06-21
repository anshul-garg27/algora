# 07 — Architecture & Numbers Defense (Walmart Resume)

> **Purpose.** This is the "whiteboard + numbers" cheat sheet for the Walmart bullets. It does three things: (a) gives you a full ASCII architecture of the audit pipeline plus the cp-nrti request flow you can reproduce on a whiteboard; (b) defends **every single number** on the resume — how it was measured, how to re-derive it live, what to say when challenged, and the honest caveat; (c) maps failure modes, single points of failure, and what breaks at 10x.
>
> **Golden rule for the whole interview:** lead with the honest framing *before* they catch you. Every number below has a "code-vs-resume gap." Naming the gap yourself is senior signal; getting caught hiding it is disqualifying.
>
> **Repos referenced (all real, on disk at `~/Desktop/walmart`):**
> - `audit-api-logs-srv` — Tier 2 audit producer (Spring Boot 3.5.12 / Java 17, Avro + Schema Registry).
> - `dv-api-common-libraries` — Tier 1 capture library (Spring Boot 2.7.11 / Java 11 / javax.servlet).
> - `audit-api-logs-gcs-sink` — Tier 3 Kafka Connect GCS sink (NOT Spring Boot; Lenses SMT plugin).
> - `cp-nrti-apis` — supplier-facing inventory gateway (Spring Boot 3.5.14 / Java 17; real active/active Kafka failover; DC inventory search).

---

## (A) Architecture Diagrams

### A.1 — Full audit pipeline (Tier 1 → Tier 2 → Kafka → Tier 3 → GCS → BigQuery → supplier)

```
                          SUPPLIER / EXTERNAL API CALLER
                                      │  (HTTPS, WM_SEC.* auth headers)
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│  TIER 1 — CAPTURE  (in-process, inside EVERY audited service e.g. cp-nrti-apis)     │
│  dv-api-common-libraries  (Spring Boot 2.7.11 / Java 11 / javax.servlet — SHARED LIB,│
│                            NOT an auto-configured starter; consumer @ComponentScans) │
│                                                                                      │
│   LoggingFilter (OncePerRequestFilter, @Order LOWEST_PRECEDENCE)                     │
│     • gate: featureFlagCCMConfig.isAuditLogEnabled()  (CCM kill-switch)              │
│     • skip /actuator; endpoint allow-list via substring contains()                   │
│     • wrap req/resp in ContentCachingRequestWrapper / ContentCachingResponseWrapper  │
│     • chain.doFilter(...) → copyBodyToResponse()  (else client gets empty body)      │
│     • build 18-field AuditLogPayload (snake_case JSON)                                │
│            │                                                                          │
│            ▼  hand off OFF the request thread                                         │
│   @Async ThreadPoolTaskExecutor  (core 6 / max 10 / queue 100, default AbortPolicy)   │
│     AuditLogService.sendAuditLogRequest()  → AuthSign (4 WM_SEC headers)              │
│     → WebClient.exchangeToMono(...).block()  (reactive client, used blocking)         │
└───────────────────────────────────┬──────────────────────────────────────────────┘
                                     │  signed JSON POST  (fire-and-forget; errors caught+logged)
                                     ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│  TIER 2 — PRODUCE  audit-api-logs-srv  (Spring Boot 3.5.12 / Java 17)               │
│                                                                                      │
│   AuditLoggingController.saveApiLog()                                                 │
│     └── returns HTTP 204 NO_CONTENT *immediately*  ◄── the "<5ms" lever              │
│   LoggingRequestService → ExecutorPoolService                                        │
│     └── Executors.newCachedThreadPool()  (UNBOUNDED — no queue cap, no reject handler)│
│   KafkaProducerService.publishMessageToTopic()                                        │
│     └── kafkaPrimaryTemplate.send(Message<LogEvent>)  in log-only try/catch          │
│         (kafkaSecondaryTemplate bean EXISTS but is DEAD on this path)                 │
│                                                                                      │
│   Serialization: KafkaAvroSerializer (value) + StringSerializer (key)                │
│   Key = serviceName + "/" + endpoint   (e.g. "NRT/transactionHistory")               │
│   Header: wm-site-id  (US/CA/MX)  + whitelist (wm_consumer.id, wm_svc.*, corr_id)    │
│   auto.register.schemas = false  ──────────────────┐                                 │
└─────────────────────────────────────┬─────────────│──────────────────────────────┘
                                       │             │ schema lookup/validate
                                       │             ▼
                                       │   ┌─────────────────────────────┐
                                       │   │  CONFLUENT SCHEMA REGISTRY  │  (on BOTH
                                       │   │  log.avsc, 19 fields,       │   produce &
                                       │   │  BACKWARD-compat evolution) │   consume —
                                       │   └─────────────────────────────┘   shared SPOF)
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│  KAFKA  topic = api_logs_audit_{dev|stg|prod}                                        │
│  cluster kafka-v2-luminate-core-prod   (EUS2 + SCUS, port 9093, mTLS via Istio)      │
│  partitioned by key (serviceName/endpoint) → per-endpoint ordering                   │
└───────────────┬───────────────────┬───────────────────┬──────────────────────────┘
                │ (every record read by ALL THREE — 3x read amplification)            │
        ┌───────▼───────┐   ┌───────▼───────┐   ┌───────▼───────┐
        │ TIER 3: CONNECT SINKS  (Kafka Connect on kcaas-base-image:11-major,         │
        │  Lenses io.streamreactor GCPStorageSinkConnector — NOT Spring Boot)         │
        │  tasks.max=1, errors.tolerance=all, DLQ on, RETRY max.retries=5,            │
        │  max.poll.records=50, value.converter=AvroConverter schemas.enable=true     │
        │                                                                             │
        │  US connector        CA connector        MX connector                       │
        │  SMT chain:          SMT chain:          SMT chain:                          │
        │  1) InsertRolling-   (same)              (same)                              │
        │     RecordTimestamp                                                          │
        │     → _header.date (yyyy-MM-dd GMT)                                          │
        │  2) Filter (BaseAuditLogSinkFilter.apply): verifyHeader(wm-site-id) ? r:null │
        │     • US OVERRIDES verifyHeader → ALSO passes when header MISSING (catch-all)│
        │     • CA / MX inherit STRICT base → missing header DROPPED                   │
        └───────┬───────────────────┬───────────────────┬──────────────────────────┘
                ▼                    ▼                    ▼
        KCQL: INSERT ... STOREAS PARQUET PARTITIONBY service_name,_header.date,endpoint_name
        flush.size=50MB / flush.count=5000 / flush.interval=600s   key.suffix _eus2|_scus
                ▼                    ▼                    ▼
   gs://audit-api-logs-    gs://audit-api-logs-    gs://audit-api-logs-
       us-prod                 ca-prod                 mx-prod        (project wmt-dv-luminate-prod)
                └────────────────────┴───────────────────┘
                                     ▼
                       ┌─────────────────────────────┐
                       │  BIGQUERY external tables    │  (Parquet-on-GCS, query in place,
                       │  partition pruning by        │   partition-pruned by date/service)
                       │  service/date/endpoint       │
                       └──────────────┬──────────────┘
                                      ▼
                       SUPPLIER SELF-SERVICE API DEBUGGING
                       (replaced Splunk dependency)
```

**Latency reality on this diagram:** the **"<5ms P99" lives between TIER 1's `@Async` hand-off and TIER 2's `204`** — it is *added overhead on the audited request*. End-to-end *freshness* (record visible in BigQuery) is **minutes**, governed by `flush.interval=600s`. Never conflate the two.

### A.2 — cp-nrti-apis request flow (DC inventory search + active/active Kafka)

```
                 SUPPLIER  ──HTTPS──▶  Istio gateway (mTLS, WM_SEC.* auth at edge)
                                            │
                                            ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│  cp-nrti-apis  (Spring Boot 3.5.14 / Java 17 / Jakarta; servlet+Tomcat stack)       │
│                                                                                      │
│  STAGE 1 — EDGE  RequestFilter (OncePerRequestFilter, @Order LOWEST_PRECEDENCE-100) │
│    • validate WM_CONSUMER.ID → 401 if absent    • open Strati txn                    │
│    • NrtiApiInterceptor + bean validation (@NotNull dcNbr, itemIdentifier=wmItemNbr) │
│                                                                                      │
│  ── Path A: POST /dc/inventory/status (READ, returns 200) ──────────────────────┐   │
│  STAGE 2 — AUTHORIZE + FETCH  DcInventoryServiceImpl                              │   │
│    • SupplierMappingServiceImpl → ParentCompanyMapping (Postgres nrt_consumers,  │   │
│      Caffeine 6h cache)                                                           │   │
│    • UberKeyReadService.getGtinsFromWmItemNbrs  (WM item# → GTIN)                 │   │
│    • StoreGtinValidatorServiceImpl.getMappedGtins                                 │   │
│    • HttpServiceImpl → reactive WebClient .timeout(10s) .retryBackoff(3,100ms,2s) │   │
│         .block()  ──▶  Enterprise Inventory (EI-PIT-BY-ITEM)  GET-with-body        │   │
│  STAGE 3 — MAP  EIServiceHelper → DcInventoryItem (PROMO/TURN by state)           │   │
│  ───────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
│  ── Path B: inventory action event (WRITE) ──────────────────────────────────────┐  │
│  NrtiStoreServiceImpl.handleInventoryActionsEvent  (Strati child txn)              │  │
│    └── NrtKafkaProducerServiceImpl  (THE REAL ACTIVE/ACTIVE FAILOVER)              │  │
│        future = kafkaPrimaryTemplate.send(msg)        // region-LOCAL cluster      │  │
│        future.thenAccept(logOffset)                                                │  │
│             .exceptionally(ex -> handleFailure(...).join())  // RE-SEND to OTHER   │  │
│                                              region's kafkaSecondaryTemplate       │  │
│        .join()   // IAC blocks request thread; both fail → NrtiUnavailableException │  │
│                  //                                       → HTTP 503               │  │
│        (DSC path: fire-and-forget, NO .join(), returns 201 even on total failure)  │  │
│  ───────────────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────┬─────────────────────────┬──────────────────────┘
                                     ▼                          ▼
              EUS2 pod: primary=...eus...:9093          SCUS pod: primary=...scus...:9093
                        secondary=...scus...:9093                 secondary=...eus...:9093
                        (CCM zone resolution SWAPS them — both regions take live writes)
                                     │                          │
                          topics: cperf-nrt-prod-iac / cperf-nrt-prod-dsc
                          acks=all, retries=10, idempotence=FALSE, RF3/ISR2
                          JsonSerializer (NO Schema Registry on this path)
```

---

## (B) Defending Every Number on the Resume

> Format per number: **What it claims → How it was measured / how to derive it live → If challenged → Honest caveat.**

### B.1 — "sub-5ms P99 latency impact"

- **Claims:** the audit pipeline adds < 5ms at P99 to the *audited* API's response time.
- **How measured / derive live:** This is *added overhead*, not end-to-end latency. The mechanism: TIER 1 `LoggingFilter` only does (1) wrap req/resp in ContentCaching wrappers, (2) build the payload, (3) `executor.submit()` to the `@Async` pool — then returns. The expensive work (crypto signing via `AuthSign`, the outbound `WebClient` POST) runs on a *pool thread*, off the request hot path. TIER 2 returns `204 NO_CONTENT` *before* any Kafka work. So the request thread's added cost is: wrapper allocation + payload build + a queue enqueue ≈ sub-millisecond; the 5ms P99 budget is dominated by the wrapper buffering of the response body. Validated via **Automaton/JMeter perf profiles asserting the 204** and measuring the audited endpoint's P99 with audit on vs off (CCM flag flip — same build, A/B).
- **If challenged ("show me the timing"):** "It's a delta measurement — same service, CCM flag on vs off, JMeter P99 on the audited endpoint. The flag-driven design *is* the test harness. The win is architectural: the only synchronous work added is buffering + an enqueue; everything costly is on the `@Async` pool and the producer returns 204 before touching Kafka."
- **Honest caveat:** The < 5ms is **overhead on the audited request, not audit freshness** (which is minutes due to `flush.interval=600s`). And the mechanism that buys the latency — async hand-off with no back-pressure (Tier 1 `AbortPolicy`, Tier 2 unbounded `newCachedThreadPool`) — is the *same* mechanism that risks dropped audit logs under burst. Body buffering also scales with body size × concurrency, so the 5ms holds for normal payloads, not 50MB multipart uploads.

### B.2 — "millions of daily events" / "2M+ events/day"

- **Claims:** the pipeline processes millions of audit events per day.
- **How measured / derive live:** Every audited supplier API call produces exactly one audit record (one `AuditLogPayload` → one Avro `LogEvent` → one Kafka record). So daily volume = daily audited request count across all consuming services. Derive it for them: "If the supplier-facing fleet handles low-double-digit requests/sec sustained, that's `~15 req/s × 86,400 s ≈ 1.3M/day` per service; across the audited services it clears a few million." Cross-check from the sink side: `flush.count=5000` per file and many files/day per bucket implies millions of records.
- **If challenged ("exact number?"):** "It's an order-of-magnitude figure from request volume × 1 record/request, not a metered counter I'm quoting to the digit. The architecture is sized for it: Kafka partitioned by serviceName/endpoint, Connect with `max.poll.records=50` batching to 50MB/5000-record Parquet files."
- **Honest caveat:** "Millions/day" is a **fleet aggregate**, not a single endpoint, and it's derived from request throughput, not pulled from a single authoritative dashboard I personally own. Don't claim a precise "2,000,000" — claim "single-digit millions per day" and show the derivation.

### B.3 — "15-min DR recovery (vs 1-hour RTO)" — zero data loss

- **Claims:** disaster recovery recovers in 15 minutes versus a prior 1-hour RTO.
- **How measured / derive live:** Two distinct things are happening, and the resume conflates them — say so up front:
  1. **Automatic per-message failover is sub-second:** `NrtKafkaProducerServiceImpl` — `kafkaPrimaryTemplate.send()` returns a `CompletableFuture`; `.exceptionally()` re-sends the *same message* to the other region's `kafkaSecondaryTemplate`. No human, no runbook.
  2. **The 15-min number is operational regional recovery** — CCM zone-resolution flip / cluster-health-back — measured in DR game-days, versus a prior **~1-hour manual runbook**.
- **If challenged ("define RPO vs RTO; prove 15 min"):** "RTO = time to restore service; RPO = acceptable data-loss window. The *code* failover gives effectively-zero RPO per acknowledged IAC event because `acks=all` + RF3/ISR2 means it's durable in the surviving region or the supplier got a 503 to retry. The 15 minutes is **RTO for full regional recovery**, an operational figure from game-days — I don't have an in-repo artifact that stamps '15 min' or '1 hour'; those are operational measurements, and I'll present them as such."
- **Honest caveat:** `request.timeout.ms=300000` (5 min). For a *black-hole* network failure (packets silently dropped), the primary `send()` future won't fail for up to 5 minutes, so failover is only sub-second for *fast* failures (connection refused, no brokers). Mitigation I'd add: `.orTimeout(...)` to bound it. Also: the 15-min/1-hour numbers are operational, not code-provable — never present them as instrumented.

### B.4 — "zero data loss"

- **Claims:** no data loss across the failover / pipeline.
- **How measured / derive live:** Defensible **only** as: *"no observable loss of an acknowledged IAC inventory event under single-region failure."* Mechanism: `acks=all` (ccm.yml line 172) + RF3/ISR2 means an acked record survives a broker loss; if the local region is fully down, `.exceptionally()` commits it synchronously to the other region; if *both* fail, the supplier gets a **503 to retry** — so it's never silently dropped.
- **If challenged ("prove it's not exactly-once / where can it still lose?"):** "It's **at-least-once, not exactly-once** — `enable.idempotence=false` (ccm.yml line 197) with `retries=10` means retries and failover can produce **duplicates and reordering**. That's why event identity is the **client-supplied messageId** (copied to messageId + correlationId + MESSAGE_ID header) so downstream consumers dedup. 'Zero data loss' means no *loss*, not no *dupes*."
- **Honest caveat:** This applies to the **IAC path in cp-nrti-apis only**. (1) The **audit pipeline** (Tier 2) has **no such guarantee** — it never sets `acks`/`idempotence`/`retries` (defaults near `acks=1`), so a leader failure there *can* lose an audit record; its `kafkaSecondaryTemplate` is **dead code**. (2) The **DSC path** is fire-and-forget and returns 201 even on total failure — a genuine silent-loss smell I'd own. So scope the claim to acknowledged IAC events, and never attribute failover to the audit producer.

### B.5 — "reducing integration from 2 weeks to 1 day per service"

- **Claims:** the shared capture library cut per-service audit integration from ~2 weeks to ~1 day.
- **How measured / derive live:** Engineering estimate of *pre-library bespoke effort* vs *post-library adoption*. Pre-library, each team hand-wrote: read-once stream handling (ContentCaching), an async off-thread executor, request signing (4 WM_SEC headers), the payload contract, CCM wiring, and error-swallowing — call it ~2 weeks with testing. Post-library: add the Maven dependency, `@ComponentScan com.walmart.dv.filters + .services`, provide a `WebClient` bean, set CCM (feature flag + endpoint allow-list + key path) — ~1 day.
- **If challenged ("measured or estimated?"):** "Estimated, not instrumented — it's the standard before/after engineering estimate. The credible core is that stream-reuse, async hand-off, and signing are solved *once* and consumed as config, so the variable per-service work collapses to dependency + scan + CCM."
- **Honest caveat:** It's a **shared library, not a true auto-configured starter** — there's no `src/main/resources`, no `spring.factories`, no `AutoConfiguration.imports`; the consumer must component-scan and supply a `WebClient` bean. And "spearheaded" is collaborative (Nayana.BG is a listed pom developer) — own the *design, reusability, and adoption drive*, not sole authorship. Also note the cross-version reuse caveat: the lib is Boot 2.7 / Java 11 / javax while consumers are Boot 3 / Java 17 / jakarta (works because NRTI excludes webflux and supplies its own WebClient; the clean fix is a jakarta rebuild).

### B.6 — "parallel consumer integration (30% faster)"

- **Claims:** OpenAPI design-first let consumer teams integrate ~30% faster.
- **How measured / derive live:** Critical-path compression, not an A/B metric. Design-first means the contract (`api-spec/schema/openapi.json`) is locked *before* the backend is finished; consumers generate client SDKs + mock servers and build against them in parallel rather than waiting for a live endpoint. The 30% is the wall-clock saved by parallelizing consumer work against the serial baseline.
- **If challenged ("did you measure 30%?"):** "It's a critical-path-compression estimate from parallelizing consumer integration, not an instrumented A/B. The mechanism is real: spec → generated client + mock → consumers integrate before backend GA, enforced by R2C contract tests."
- **Honest caveat:** Design-first is real **as a process**, but **not enforced by codegen for the DC endpoint** — only the items-assortment endpoint uses the `spring` generator; **DC/store controllers are hand-written**. The root `api-spec.yaml` even drifted (advertises plural `/stores`, `/volts`, omits `/dc`; deployed routes are singular). So present 30% as an estimate, and credit R2C contract tests for keeping design-first honest. Don't claim sole end-to-end authorship of the DC API (Keshav Gatla / Ambiorix Cruz Angeles authored much of it).

### B.7 — "Flagger canary releases (10% to 100%)"

- **Claims:** canary rollout ramping from 10% to 100% of traffic.
- **How measured / derive live:** `kitt.yml` (lines 722–748): `stepWeight: 10`, `maxWeight: 50`, `interval: 2m`, `progressDeadlineSeconds: 600`, `canaryReplicaPercentage: 50`. The analysis gate is a PromQL query over Envoy `envoy_cluster_upstream_rq` computing `5xx-rate/total*100` with threshold `1` (1%). Prod has `rollbackOnError: true`. So traffic ramps in 10% steps to **50% (maxWeight) during the metric-gated analysis phase**, then **promotes to 100%** when healthy. End-to-end it *is* 10% → 100%.
- **If challenged ("maxWeight is 50, not 100"):** "Correct — `maxWeight: 50` is the *analysis* ceiling. Flagger ramps in 10% steps to 50% while the 5xx gate watches each step, then promotes the canary to 100% on success. '10% to 100%' is the end-to-end rollout; the 50% is the analysis cap, not the final state."
- **Honest caveat:** The gate is **5xx-rate only** — it's blind to *semantic* regressions (wrong-200, e.g. a Hibernate enum returning truncated data) and to *latency* regressions. Those were covered in **stage** by R2C contract tests + Automaton perf, not by the canary gate. Volunteer this — it's senior signal.

### B.8 — "zero customer-impacting issues" (SB3/Java17 migration)

- **Claims:** the Spring Boot 3 / Java 17 migration shipped with zero customer-impacting issues.
- **How measured / derive live:** This is a **property of the staged rollout**, not "zero bugs." Sequence: BOM-first upgrade → one week in **stage** with R2C contract tests + Automaton perf + RaaS resiliency + Looper e2e → Flagger canary with automatic 5xx rollback gate → promote to 100%. A real **Hibernate 6 enum bug was caught in stage** (fixed with `@JdbcTypeCode(SqlTypes.NAMED_ENUM)`), *before* prod.
- **If challenged ("zero bugs, really?"):** "Not zero *bugs* — zero *customer-impacting* issues. We caught a Hibernate 6 strict-typing enum bug in stage and fixed it before any traffic. 'Zero customer impact' is a claim about the rollout design — stage soak + canary + auto-rollback — not a claim that the migration was bug-free."
- **Honest caveat:** The resume says **"3.2"** but the pom is **parent 3.5.14 / BOM 3.5.7** — open with this correction ("led the 2.7→3.x jump, stayed current to 3.5.x"). Two prior-doc claims are **false for this repo**: there is **no Spring Security migration** (zero Spring Security; auth is gateway-side + servlet filters) and **no RestTemplate→WebClient migration** (zero RestTemplate; WebClient was always the client). Don't assert either.

---

## (C) Failure Modes, SPOFs & What Breaks at 10x

### C.1 — Single Points of Failure

| SPOF | Where | Failure mode | Mitigation / what to say |
|---|---|---|---|
| **Confluent Schema Registry** | Both produce (Tier 2, `auto.register.schemas=false`) and consume (Tier 3, `AvroConverter schemas.enable=true`) | If SR is unreachable, producers can't serialize and the sink can't deserialize → audit pipeline stalls. With `auto.register=false`, a missing/unpromoted schema *fails the producer*. | SR is HA-clustered at platform level; cache schemas client-side; `false` is deliberate (prevents a rogue pod auto-registering an incompatible schema). Honest: it's a shared dependency on *both* paths. |
| **Primary Kafka cluster (per region)** | Tier 2 audit produce; cp-nrti IAC/DSC | Tier 2 has **no failover** (secondary template is dead) → leader failure can lose an audit record (defaults near `acks=1`). cp-nrti **does** fail over via `.exceptionally()`. | Audit: propose `acks=all` + `min.insync.replicas=2` + `enable.idempotence=true`. cp-nrti: already mitigated for IAC. |
| **Tier 2 unbounded thread pool** | `Executors.newCachedThreadPool()` | Under burst or downstream Kafka slowdown, threads grow unboundedly → OOM; no back-pressure. | Fix = bounded `ThreadPoolExecutor` + `RejectedExecutionHandler` + a dropped-audit metric. |
| **Tier 1 bounded pool saturation** | `@Async` core 6 / max 10 / queue 100, default `AbortPolicy` | Pool + queue full → `RejectedExecutionException` → audit log **silently dropped** (only a log line). | Add a rejection metric; consider a bounded retry; never let it affect the customer request (it doesn't — request already returned). |
| **CCM zone resolution** | cp-nrti active/active region pinning | A bad zone resolution could point *both* regions' pods at the *same* cluster, silently defeating active/active. | CCM correctness is a DR dependency; validate in game-days. |
| **EI (Enterprise Inventory)** | cp-nrti DC read, `.block()` on WebClient | Slow EI under burst → Tomcat thread starvation (thread-per-request held by `.block()`). | Add circuit breaker + bulkhead; consider reactive controllers. |

### C.2 — What breaks at 10x volume

- **3x read amplification flips cost-negative.** Three Connect connectors each read *every* record (US/CA/MX SMT filter). At modest volume this is a fine isolation trade-off; at 10x the broker egress (3× the topic) dominates → switch to **one branching connector** or topic-per-region routing.
- **Tier 2 unbounded pool → OOM.** 10x burst with any downstream slowdown grows threads without bound. Must bound the pool first.
- **Hot partition on a busy endpoint.** Key = `serviceName/endpoint`; a single hot endpoint (e.g. `NRT/transactionHistory`) pins all its traffic to one partition. Fix without losing grouping: composite key `service/endpoint/consumerId`.
- **cp-nrti `.join()` thread starvation.** IAC `.join()` blocks the Tomcat request thread on Kafka health; at 10x with a slow primary the servlet pool exhausts. Fix: `.orTimeout()` + bound the wait; consider async controllers.
- **Body buffering memory.** ContentCaching wrappers buffer the whole body in heap (memory ∝ body size × concurrency); no size cap → large/multipart endpoints risk OOM. Add a size cap.
- **DC search has no batch cap.** `values` list is uncapped (unlike store-status capped at 100); 10,000 item numbers = one giant GET-with-body on one blocked thread. Fix: chunk + `CompletableFuture` fan-out + paginate.
- **GCS small-files / flush tuning.** At 10x, `flush.interval=600s` may produce too-large files or memory pressure per task (`tasks.max=1`); revisit flush thresholds and task parallelism.

---

## (D) 5-Minute System Design Whiteboard (audit platform)

Draw this top-to-bottom, narrate the 3 tiers + storage. Memorize the 6 labels and 4 spoken trade-offs.

```
  [Supplier API call]
         │
         ▼
  ┌──────────────────┐   "Capture in a shared servlet filter. Body is a read-once
  │ 1. CAPTURE        │    stream, so I wrap it in ContentCaching wrappers, then hand
  │ shared lib        │    the record to an @Async pool — request thread never waits."
  │ ContentCaching +  │
  │ @Async pool       │
  └────────┬─────────┘
           │ signed JSON POST (fire-and-forget)
           ▼
  ┌──────────────────┐   "Thin producer returns 204 instantly, then publishes Avro to
  │ 2. PRODUCE        │    Kafka. Key = service/endpoint for per-endpoint ordering.
  │ audit-srv → 204   │    wm-site-id header carries the country. Schema Registry
  │ Avro + SchemaReg  │    governs evolution (auto-register OFF)."
  │ key=svc/endpoint  │
  └────────┬─────────┘
           ▼
  [ KAFKA: api_logs_audit_prod ]  (single immutable stream; EUS2+SCUS)
           │
   ┌───────┼────────┐               "Routing happens in the SINK via 3 per-country
   ▼       ▼        ▼                 connectors, each with an SMT that filters on
 [US]    [CA]     [MX]  Connect       wm-site-id. Producers stay dumb; isolated
 SMT     SMT      SMT   sinks         per-country failure domains. Trade-off: 3x
 filter  filter   filter             read amplification — fine at this volume."
   ▼       ▼        ▼
 [GCS Parquet US/CA/MX]              "Parquet on GCS, partitioned by service/date/
           │                          endpoint, big flush sizes — columnar +
           ▼                          partition pruning matches the query pattern."
  [ BigQuery external tables ]
           │
           ▼
  [ Supplier self-service debugging — replaced Splunk ]
```

**Four trade-offs to say out loud while drawing:**
1. **Async fire-and-forget buys latency, costs delivery certainty** — if a send fails, the caller already got 204; no app-level DLQ. I'd harden Tier 2 with `acks=all` + idempotence + bounded pool.
2. **Routing in the sink (not at produce)** keeps one immutable stream and dumb producers, at the cost of 3x read amplification — I'd revisit at 10x with a single branching connector.
3. **Avro + Schema Registry** gives compact typed payloads + governed evolution, but couples both paths to SR as a shared dependency.
4. **Parquet + 600s flush** trades real-time freshness (queryable in ~minutes) for cheap, prunable analytical storage — correct for the supplier debugging use-case.

**If they push deeper, the honest hardening list:** bound the Tier 2 pool (`ThreadPoolExecutor` + rejection metric); add `acks=all`/`min.insync.replicas=2`/`enable.idempotence=true`; mask `WM_SEC.*`/`Authorization` headers at capture (current code copies them unmasked — a real PII/secret leak to raise proactively); add a 4th "unknown/quarantine" bucket so header-less records aren't silently funneled to US (current US filter is the catch-all; CA/MX drop missing-header records — a residency edge case to confirm with compliance).
