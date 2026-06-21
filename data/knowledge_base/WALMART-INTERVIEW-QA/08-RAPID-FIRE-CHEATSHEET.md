# 08 — Rapid-Fire Cheat Sheet (Last-Minute Cram)

> Walmart / Anshul Garg. Covers all 5 resume bullets. Read this in the elevator.
> **Golden rule:** Every number on the resume is defensible IF you state it precisely. The danger is overclaiming. Lead with the honest framing before they catch you.
> **Repo map:** Audit producer = `audit-api-logs-srv`. GCS sink = `audit-api-logs-gcs-sink` (Kafka Connect, NOT Spring Boot). Capture lib = `dv-api-common-libraries`. Failover + DC API + SB3 migration all live in `cp-nrti-apis`.

---

## SECTION A — 100 Rapid-Fire Q → 1-Line A

### A1. Kafka audit pipeline architecture (Bullet 1)

1. **What are the three tiers?** Shared capture library → fire-and-forget Avro producer (`audit-api-logs-srv`) → Kafka Connect GCS sink with per-country SMT.
2. **Which tier returns 204?** Tier 2 producer: `AuditLoggingController.saveApiLog` returns HTTP 204 *before* any Kafka work.
3. **What makes the latency overhead sub-5ms?** The send happens off the request thread on a thread pool; the caller never blocks on Kafka.
4. **What is the partition/message key?** `serviceName + "/" + endpoint` (e.g. `NRT/transactionHistory`) via `AuditKafkaPayloadKey.getKafkaKey()`.
5. **Why key on service/endpoint?** Co-partitions one endpoint's records to one partition → per-endpoint ordering and grouping.
6. **Failure mode of that key?** Hot partition for a busy endpoint; fix = composite key `service/endpoint/consumer_id`.
7. **What's the topic name?** `api_logs_audit_{dev|stg|prod}` (from CCM), cluster `kafka-v2-luminate-core-prod`, port 9093.
8. **What serializer?** Key = `StringSerializer`, Value = `KafkaAvroSerializer` (Confluent 5.5.0), Avro 1.11.4.
9. **Where does data land?** Parquet on GCS → `audit-api-logs-{us|ca|mx}-prod` buckets → BigQuery external tables for supplier self-service.
10. **What did it replace?** Splunk dependency — suppliers now self-serve API debugging via BigQuery.
11. **Sub-5ms means what exactly?** Added *overhead on the audited API*, NOT end-to-end audit freshness (that's minutes — `flush.interval=600s`).
12. **Where is the thread pool defined (Tier 2)?** `ExecutorPoolService` = `Executors.newCachedThreadPool()` — **unbounded**, no queue cap, no rejection handler.
13. **Risk of that pool?** Unbounded thread growth → OOM under burst/downstream slowdown; no back-pressure.
14. **Proposed fix?** Bounded `ThreadPoolExecutor` + `RejectedExecutionHandler` + a dropped-audit metric.
15. **How does `send()` know a publish failed?** It doesn't — async, future unobserved, catch only logs; caller already got 204.

### A2. Avro / Schema Registry

16. **Where's the Avro contract?** `log.avsc`, 19 fields, namespace `com.walmart.dv.audit.model.api_log_events.LogEvent`.
17. **Compatibility mode?** BACKWARD — optional fields are null-with-default so new fields don't break old consumers.
18. **`auto.register.schemas` setting?** `false` — a pod cannot silently auto-register an incompatible schema in prod; promotion is controlled.
19. **Why Avro over JSON?** Compact typed binary + governed evolution via Schema Registry; Walmart streaming default.
20. **Why Avro over Protobuf?** Comparable, but Avro is first-class in Kafka Connect and the org standard.
21. **Schema Registry as SPOF?** Yes on both paths — a missing/unavailable registration fails producers; mitigate with registry HA + client caching.
22. **Header whitelist forwarded to Kafka?** `wm_consumer.id`, `wm_qos.correlation_id`, `wm_svc.name`, `wm_svc.version`, `wm_svc.env`, `wm-site-id`.
23. **Which header drives routing?** `wm-site-id` (country).

### A3. SMT geographic routing (US/CA/MX)

24. **Where does routing happen?** In the **sink** (Kafka Connect SMT), NOT at produce time — topic stays a single immutable stream.
25. **How many connectors?** 3 — one per country (US/CA/MX), `tasks.max=1` each.
26. **What's the SMT class?** `BaseAuditLogSinkFilter implements Transformation`; `apply()` returns the record if `verifyHeader()` else `null` (drop).
27. **US filter behavior?** Permissive catch-all — overrides `verifyHeader` to ALSO pass when the header is *missing*.
28. **CA/MX filter behavior?** Strict (inherit base) — drop if header missing or not matching.
29. **A record with NO `wm-site-id` — where does it go?** US bucket only. CA/MX drop it. Possible residency edge case → confirm with compliance.
30. **Gotcha on CA/MX?** The Javadoc says "or if header missing" but the **code** inherits strict base. Know the code, not the comment.
31. **Cost of 3 connectors?** 3x read amplification — every record consumed by all three connectors.
32. **Why accept 3x?** Isolation: independent offsets/lag, per-country failure domains, clean one-connector-per-bucket mapping.
33. **When would you change it?** At ~10x volume → flip to a single branching connector.
34. **Other SMT in the chain?** `InsertRollingRecordTimestamp` (yyyy-MM-dd GMT) before the country Filter.

### A4. GCS / Parquet / BigQuery / Connect

35. **Is the sink Spring Boot?** NO — it's a Kafka Connect SMT plugin JAR on `kcaas-base-image:11-major`, Lenses `GCPStorageSinkConnector` (gcs-lenses-connector 1.64). No main, no `Application`.
36. **Write format / framework?** KCQL writes **Parquet** `PARTITIONBY service_name,_header.date,endpoint_name`.
37. **Flush thresholds?** 50MB / 5000 records / 600s interval (whichever first).
38. **Why big flush sizes?** Few large files → avoids small-files problem; columnar Parquet → partition pruning for analytical queries.
39. **Cost of big flush?** Up to ~10 min buffer before queryable (near-real-time, not real-time).
40. **Error handling in sink?** `errors.tolerance=all`, DLQ on, `error.policy=RETRY`, `max.retries=5`, `max.poll.records=50`.
41. **Why BigQuery external tables?** Query Parquet in place; matches supplier analytical query pattern; no load job.
42. **Converter config?** `value.converter=AvroConverter`, `schemas.enable=true`.
43. **Why Connect over a hand-written consumer?** Free offset mgmt, rebalancing, retries, DLQ, Parquet/GCS batching — we only wrote ~75 lines of SMT.
44. **Cost of Connect choice?** Less control over internals; coupled to Lenses versioning; black box for deep failures.

### A5. Capture library / ContentCachingWrapper / thread pool (Bullet 2)

45. **Is `dv-api-common-libraries` a true Spring Boot starter?** NO — it's a shared library. No `src/main/resources`, no `spring.factories`, no `AutoConfiguration.imports`.
46. **So how do consumers wire it?** Explicit `@ComponentScan com.walmart.dv.filters + com.walmart.dv.services` AND supply their own `WebClient` bean.
47. **Why ContentCachingRequestWrapper/ResponseWrapper?** A servlet stream is read-once; the wrappers buffer bytes so both the app and the auditor can read the body.
48. **Must-call method or bug?** `copyBodyToResponse()` at the end — or the client gets an empty body.
49. **Filter type & order?** `LoggingFilter extends OncePerRequestFilter`, `@Order(Ordered.LOWEST_PRECEDENCE)`.
50. **Why LOWEST_PRECEDENCE?** Innermost filter → sees the fully-decorated request and the final response.
51. **Why OncePerRequestFilter?** Dedupes across internal dispatches (forwards/includes).
52. **Why a Filter over `@Aspect`/HandlerInterceptor?** Need raw read-once bytes before anything consumes them; aspect sees typed objects, misses pre-controller rejections.
53. **Async pool sizing?** `ThreadPoolTaskExecutor` core=6, max=10, queue=100, prefix `Audit-log-executor-` (`AuditLogAsyncConfig`, `@EnableAsync`).
54. **Rejection policy?** None set → default **AbortPolicy** → throws → audit log silently dropped when pool+queue saturate.
55. **What does the async method return?** `void` (`AuditLogService.sendAuditLogRequest` is `@Async`, fire-and-forget).
56. **How is the POST authed?** `AuthSign.getAuthSign` produces 4 headers: `WM_CONSUMER.ID`, `WM_SEC.AUTH_SIGNATURE`, `WM_SEC.KEY_VERSION`, `WM_CONSUMER.INTIMESTAMP`.
57. **WebClient reactive but...?** Called with `.block()` — no reactive benefit; one thread held per round-trip; dead `RestTemplate` import = half-finished migration.
58. **Payload field count?** 18 snake_case fields, Lombok `@Builder`, `@JsonInclude(NON_EMPTY)`.
59. **2 weeks → 1 day — measured?** Engineering *estimate* of pre-library bespoke effort; the credible core is stream-reuse + async + signing solved once, consumed as config.
60. **All behavior runtime-configurable?** Yes — CCM (Strati `@ManagedConfiguration`): feature flag, endpoint allow-list, response-body toggle, key path. Kill-switch with no redeploy.
61. **Endpoint allow-list matching?** Substring `contains()` — collision-prone (`/status` matches `/statusReport`); prefix/exact would be safer.
62. **Audit sink down → customer impact?** None visible: async + caught errors + already-returned response; cost = lost audit records, no retry/DLQ.

### A6. Active/Active multi-region Kafka + DR (Bullet 3)

63. **Where does failover actually live?** `cp-nrti-apis` → `NrtKafkaProducerServiceImpl`. NOT audit-srv.
64. **audit-srv's `kafkaSecondaryTemplate`?** Dead code — autowired but never used in the send path. Do NOT attribute failover to it.
65. **The failover mechanism in one line?** Send to region-local primary `KafkaTemplate`; on the `CompletableFuture.exceptionally`, re-send the same message to the other region's secondary template.
66. **How many templates?** 4 beans: IAC primary/secondary + DSC primary/secondary.
67. **What are EUS2 / SCUS?** Azure regions: East US 2 and South Central US. Both take live writes simultaneously (active/active).
68. **How is active/active configured?** CCM `configOverrides` resolved by zone: eus2 pods get primary=eus/secondary=scus; scus pods get them **swapped**.
69. **acks setting?** `acks=all` (durable to ISR).
70. **`enable.idempotence`?** **FALSE** → at-least-once with possible duplicates AND reordering. NOT exactly-once.
71. **retries?** 10. **compression?** lz4. **linger.ms?** 20. **batch.size?** 8192. **max.request.size?** 10MB.
72. **`request.timeout.ms`?** 300000 = **5 minutes** — undercuts "fast failover" for black-hole/slow failures.
73. **So what's actually sub-second?** Only *fast* failures (connection refused, no brokers). Mitigation: add `orTimeout(...)`.
74. **IAC vs DSC behavior?** IAC blocks with `.join()`, returns **503** on total failure. DSC is fire-and-forget, returns **201** even if both regions fail.
75. **Is the DSC 201 a bug?** Yes — a genuine smell (silent loss). Own it; fix = failure metric + DLQ.
76. **Serializer on this path?** Spring `JsonSerializer` (value), `StringSerializer` (key). **No Schema Registry** here — different product from the audit Avro path.
77. **Dedup key for failover duplicates?** Client-supplied `messageId` (copied into messageId + correlationId + `MESSAGE_ID` header). Consumer-side dedup.
78. **Risk of client-supplied messageId?** Collision → wrongful drop. Mitigate by namespacing `supplierId + messageId`.
79. **Is NRTI a consumer?** No — producer-only (no `@KafkaListener`); consumer DR/offset continuity lives downstream (`inventory-events-srv`).
80. **What does "zero data loss" really mean?** No observable loss of an *acknowledged IAC event* under single-region failure (acks=all + RF3/ISR2). Not exactly-once.
81. **Why not MirrorMaker 2?** Async replication → replication lag = data-loss window on failover + offset-translation complexity. App-level dual-write gives ~0 RPO per acked event.
82. **Why not a stretch cluster?** Cross-region replica acks add latency to *every* write and risk quorum thrash.

### A7. Spring Boot 3 / Jakarta / Java 17 migration (Bullet 4)

83. **Resume says 3.2 — what's in the pom?** Parent `3.5.14`, BOM `3.5.7`, Java 17. Open with: "led the 2.7→3.x jump, stayed current to 3.5.x."
84. **Parent vs BOM mismatch — which wins?** BOM (`spring-boot-dependencies` 3.5.7) wins for effective transitive versions.
85. **Jakarta migration status?** Essentially complete: 149 `jakarta.*` refs vs 2 residual `javax.*` (one is `javax.sql.DataSource` — correct Java SE, never moved).
86. **Spring Security migration?** **There is none** — zero Spring Security in repo. Auth = gateway-side `WM_SEC.*` + custom `OncePerRequestFilter RequestFilter` + interceptor + XSS/CORS filters.
87. **RestTemplate → WebClient migration?** Didn't happen — zero `RestTemplate` in `cp-nrti-apis`; WebClient was always the client.
88. **Hibernate 5→6 breakage?** Strict typing threw on enum/array columns. Fix: `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` and `SqlTypes.ARRAY`.
89. **Spring Kafka 2→3 breakage?** `ListenableFuture` → `CompletableFuture` (`.thenAccept`/`.exceptionally`) — same code that drives the region failover.
90. **Spring MVC 6 change?** `HttpStatus` → `HttpStatusCode`; new `NoResourceFoundException` handler.
91. **Why both webflux AND tomcat starters?** Servlet/Tomcat stack runs the app; WebClient (from webflux) is the HTTP client, called with `.block()`.

### A8. Flagger canary

92. **What's the rollout tool?** Flagger metric-gated canary on WCNP/Istio (`kitt.yml`).
93. **Canary steps?** `stepWeight 10`, `maxWeight 50`, `interval 2m`, `progressDeadlineSeconds 600`.
94. **"10% to 100%" with maxWeight 50 — explain?** Ramp analysis to 50% then *promote* to 100%. True end-to-end, but the analysis ceiling is 50%.
95. **What's the gate metric?** PromQL over Envoy `envoy_cluster_upstream_rq` = 5xx-rate, threshold 1%.
96. **Blind spot of the gate?** 5xx-only → misses semantic (wrong-200) regressions and latency regressions.
97. **What covers the blind spot?** R2C contract tests (threshold 80, Active), Automaton perf, RaaS resiliency, Looper e2e — all in stage.
98. **"Zero customer-impacting issues" — zero bugs?** No — a rollout-design property. A Hibernate enum bug *was* caught in stage. Don't claim zero bugs.
99. **Auto-rollback?** Prod `rollbackOnError: true`; rollback fires automatically when the 5xx gate trips.
100. **Why canary over blue/green?** Catches load-only regressions at small exposure + automatic metric-driven rollback; blue/green is an instant 100% switch with no partial signal.

### A9. OpenAPI design-first / DC Inventory Search API (Bullet 5)

101. **What's the endpoint?** `POST /dc/inventory/status` → `DcInventoryController.getDcInventory`, returns HTTP **200** (it's a read, not 201).
102. **Is it codegen'd?** No — DC/store controllers are **hand-written**. Only the items-assortment endpoint uses the `spring` generator. The `openapi` generator just bundles the spec.
103. **So what is "design-first" here?** A *process* + R2C contract tests — consumers built against the agreed spec + generated clients/mocks in parallel.
104. **How does design-first give 30% faster?** Critical-path compression *estimate* from parallelizing consumer integration — not an instrumented A/B metric. Say so.
105. **The 3 stages?** (1) edge validation/auth filter + Strati txn; (2) resolve supplier + UberKey GTIN translation + EI WebClient read; (3) map EI promo/turn-by-state → response.
106. **What's EI?** Enterprise Inventory — Walmart's point-in-time inventory system; called over reactive WebClient.
107. **The EI call oddity?** It's a **GET with a request body** (`sendHttpListRequest(uri, HttpMethod.GET, ...)`). RFC says GET bodies are undefined; done because EI's contract accepts it; would prefer POST.
108. **WebClient resilience config?** `.timeout(10s)`, `Retry.backoff(3, 100ms, max 2s)`, then `.block()`, catch → `NrtiUnavailableException`.
109. **`.block()` risk?** Thread starvation on the Tomcat pool under slow-EI bursts; fix = circuit breaker + bulkhead + reactive controllers.
110. **Retry safety?** Read is idempotent so retry is safe; but retry isn't predicate-filtered → could retry a deterministic 400. Add `.filter(isRetryable)`.
111. **Batch cap on DC `values`?** None — store status caps at 100, DC does not. 10k items = one blocked thread; fix = chunk + `CompletableFuture` fan-out + paginate.

### A10. Factory pattern / multi-site (US/CA/MX)

112. **Show me the factory class for US/CA/MX.** There **isn't one**. `grep factory` returns only `DefaultKafkaProducerFactory`, MapStruct `Mappers.getMapper`, and Spring `beans.factory` imports.
113. **So what is "factory pattern for multi-site"?** Config + DI: same artifact deployed per region with region-specific CCM (`SiteIdCCMConfig.getWmSiteId`, `EiApiCCMConfig` country code) + `*-INTL` companion in `sr.yaml`.
114. **How would a *real* factory look?** A site-keyed client registry/strategy factory selecting per-region EI clients/config in one process.
115. **What's a GTIN?** Global Trade Item Number — the canonical product identifier; suppliers send WM item numbers, UberKeys translates to GTINs.
116. **Tenant isolation mechanism?** `SiteIdFilterAspect` (AOP `@Around` on repository calls) toggles a Hibernate `siteIdFilter` per call; does NOT touch the EI HTTP call.

---

## SECTION B — Acronym Glossary

| Acronym | Expansion | What it means here |
|---|---|---|
| **CCM** | Centralized Configuration Management | Walmart's runtime config system (Strati `@ManagedConfiguration`). Feature flags, broker lists, country codes — change with no redeploy. Drives kill-switch, region pinning, SMT topic names. |
| **KITT** | Walmart's internal deployment/CI platform | `kitt.yml` defines stages, HPA, Flagger canary, build profiles, postDeploy gates. |
| **WCNP** | Walmart Cloud Native Platform | The Kubernetes/Istio platform apps run on. Canary + mesh live here. |
| **Strati** | Walmart's platform/runtime framework | Provides `@ManagedConfiguration` (CCM), child-transaction wrapping, observability. |
| **SMT** | Single Message Transform | Kafka Connect record-level transform. Here: per-country Filter (`BaseAuditLogSinkFilter`) + timestamp insert. |
| **NRTI / NRT** | Near-Real-Time Inventory | `cp-nrti-apis` — the supplier-facing inventory REST gateway. Owns failover, DC API, SB3 migration. |
| **DSC** | Direct Shipment / Direct-to-Consumer notification | The fire-and-forget Kafka path (`cperf-nrt-prod-dsc`) that returns 201 even on failure. |
| **IAC** | Inventory Action (event) | The system-of-record inventory write path (`cperf-nrt-prod-iac`); blocks + 503 on total failure. |
| **EI** | Enterprise Inventory | Walmart's point-in-time inventory source read by the DC API over WebClient. |
| **EI-PIT** | EI Point-In-Time | The specific EI lookup: `ei-pit-by-item-inventory-read.walmart.com`. |
| **GTIN** | Global Trade Item Number | Canonical product ID; WM item numbers are translated to GTINs via UberKeys. |
| **DC** | Distribution Center | The inventory location type the DC Search API queries (`dcNbr`). |
| **EAD** | Estimated/Expected Availability Date (inventory context) | Inventory availability attribute (mention only if asked; not central). |
| **UberKeys** | Walmart item-identifier translation service | Maps supplier WM item numbers ↔ GTINs. |
| **mTLS** | Mutual TLS | Enforced at the Istio mesh egress; Kafka client TLS is *off* (`...SslEnabled=false`) because the mesh handles it. |
| **ISR** | In-Sync Replicas | Replicas caught up to the leader. `acks=all` + RF3/ISR2 = an acked record survives one broker loss. |
| **RPO** | Recovery Point Objective | Max acceptable *data loss* (time). Here ~0 per acked IAC event (synchronous dual-write). |
| **RTO** | Recovery Time Objective | Max acceptable *downtime* to recover. Code failover = sub-second/per-message; operational regional recovery ~15 min (vs old ~1-hr manual runbook). |
| **EUS2** | East US 2 (Azure region) | One of the two active regions. |
| **SCUS** | South Central US (Azure region) | The other active region. |
| **HPA** | Horizontal Pod Autoscaler | Prod audit-srv min4/max8 @60% CPU; NRTI min6/max12 @60%. |
| **DLQ** | Dead Letter Queue | Sink has one (`errors.tolerance=all`); the producer and capture lib do NOT. |
| **R2C** | Walmart contract-testing framework | Stage gate (threshold 80) that catches semantic regressions the 5xx canary gate misses. |
| **KCQL** | Kafka Connect Query Language | Lenses connector's SQL-like config: `INSERT ... STOREAS PARQUET PARTITIONBY ...`. |
| **CVE** | Common Vulnerabilities and Exposures | Why Tomcat is pinned to 9.0.99 over the parent's managed version. |
| **SR (sr.yaml)** | Service Registry descriptor | Declares the service; `*-INTL` companion confirms per-region deploy for multi-site. |
| **GCS** | Google Cloud Storage | Parquet sink target; per-country buckets under project `wmt-dv-luminate-prod`. |
| **BQ** | BigQuery | External tables over the GCS Parquet for supplier self-service analytics. |

---

## SECTION C — The 10 Trap Questions (and the Honest Escape)

> Pattern for all of these: **acknowledge the gap first, reframe to what's true, then show you know the fix.** That's the senior signal.

**TRAP 1 — "Show me the producer config that gives near-zero data loss."**
*Escape:* "On the audit producer, I can't — `KafkaProducerConfig` only sets bootstrap + serializers, so it runs near `acks=1` and can lose a record on leader failure. The durability guarantee belongs to the **NRTI** path (`acks=all` + RF3/ISR2), not the audit path. To harden audit I'd set `acks=all`, `min.insync.replicas=2`, and `enable.idempotence=true`." (Never claim audit-srv is durable.)

**TRAP 2 — "Where's your failover code?" (interviewer opens audit-api-logs-srv)**
*Escape:* "Not there — `audit-api-logs-srv` only calls `kafkaPrimaryTemplate.send()` in a log-only try/catch, and `kafkaSecondaryTemplate` is dead code. The real failover is in `cp-nrti-apis` → `NrtKafkaProducerServiceImpl`, using `CompletableFuture.exceptionally` to re-send to the other region." Pre-empt this by naming the right repo first.

**TRAP 3 — "Prove zero data loss / isn't this just at-least-once?"**
*Escape:* "Correct — it's at-least-once, not exactly-once. `enable.idempotence=false`, so retries and failover can produce duplicates and reordering. 'Zero data loss' means *no loss of an acknowledged IAC event under single-region failure* — guaranteed by `acks=all` + RF3/ISR2 to the surviving region. Consumers dedup on the client-supplied `messageId`."

**TRAP 4 — "Show me the Spring Boot starter's auto-config (spring.factories)."**
*Escape:* "There isn't one — and I should be precise: `dv-api-common-libraries` is a shared *library*, not an auto-configured starter. There's no `src/main/resources` at all. Consumers `@ComponentScan com.walmart.dv.*` and provide their own `WebClient` bean. The reuse win is real; the 'starter' word on the resume is loose — I'd call it a shared capture library."

**TRAP 5 — "Your library is Boot 2.7 / Java 11 / javax — how does the Boot 3 / jakarta service even load it?"**
*Escape:* "It's the one cross-version outlier. It works only because NRTI excludes the old `spring-boot-starter-webflux` from the jar and supplies its own WebClient bean, and the filter API surface it touches still resolves. It's fragile — the clean fix is a jakarta-targeted rebuild of the library. I'd flag this as tech debt I'd schedule."

**TRAP 6 — "Show me the SecurityFilterChain migration / WebSecurityConfigurerAdapter→ change."**
*Escape:* "There's no Spring Security in this repo — zero matches. Auth is gateway-side (`WM_SEC.*` signatures) plus custom servlet filters (`RequestFilter`, `XssFilter`, CORS) and an interceptor. So there was no Security 5→6 migration to do here; prior prep notes that claim one are wrong for this codebase." (Same for **RestTemplate→WebClient**: never existed here — WebClient was always the client.)

**TRAP 7 — "Show me the factory class for US/CA/MX multi-site."**
*Escape:* "There's no GoF runtime factory across regions — `grep factory` returns only framework factories (`DefaultKafkaProducerFactory`, MapStruct). Multi-site is **config + deploy-time**: same artifact per region with region-specific CCM (`SiteIdCCMConfig`, `EiApiCCMConfig` country code) and an `*-INTL` deploy. 'Factory pattern' on the resume maps to config+DI variant selection; a true in-process factory would be a site-keyed client registry, which is how I'd consolidate regions into one deployment."

**TRAP 8 — "Show me the generated DC controller from your design-first spec."**
*Escape:* "DC controllers are hand-written — only the items-assortment endpoint uses the `spring` generator; the `openapi` generator just bundles the spec. Design-first here is a *process* (lock the contract, consumers build against generated clients/mocks in parallel) enforced by R2C contract tests, not by server codegen for DC. And the published `api-spec.yaml` drifted (plural `/stores`, no `/dc`) — the maintained source is `openapi.json`. That drift is exactly why contract-test discipline matters."

**TRAP 9 — "Your resume says Spring Boot 3.2, the pom says 3.5.14 / BOM 3.5.7."**
*Escape:* "I led the 2.7→3.x major jump and we stayed current to 3.5.x — the resume rounds it to 3.2. On parent vs BOM: the `spring-boot-dependencies` BOM (3.5.7) wins for effective transitive versions; the parent (3.5.14) is the plugin/managed baseline." State both numbers confidently.

**TRAP 10 — "Prove 'zero customer-impacting issues' and the '30% faster' / '15-min DR' numbers."**
*Escape:* "'Zero customer-impacting issues' is a property of the **staged rollout**, not 'zero bugs' — we caught a Hibernate enum bug *in stage* before prod; the canary 5xx gate + R2C/Automaton stage gates kept it off customers. '30% faster' is a critical-path-compression *estimate* from parallelizing consumer integration, not an instrumented A/B. '15-min DR vs 1-hr RTO' is operational: the *code* failover is sub-second/per-message and automatic; 15 min is the operational regional recovery measured in DR game-days against an old ~1-hr manual runbook. I present all three as engineering estimates / design properties, not measured metrics."

---

## SECTION D — One-Breath Pitches (memorize the openers)

- **B1 Kafka audit:** "Three-tier async audit pipeline — shared capture lib → 204-then-publish Avro producer → Kafka Connect GCS sink with per-country SMT into BigQuery. Replaced Splunk with supplier self-service."
- **B2 capture lib:** "Reusable audit-capture library: servlet filter + ContentCaching wrappers capture the body, an @Async pool signs and POSTs it off the hot path. ~2 weeks → ~1 day per service. It's a shared library, not a true auto-config starter."
- **B3 active/active:** "Producer-side dual-region failover in NRTI — `CompletableFuture.exceptionally` re-sends to the other region's Kafka. acks=all + RF3 = no loss of an acked event; it's at-least-once so consumers dedup on messageId."
- **B4 SB3 migration:** "Coordinated Boot 2.7→3.x + Java 11→17 cut: Jakarta, Hibernate 6 strict typing, Spring Kafka CompletableFuture. BOM-first, week-long stage soak, Flagger 5xx-gated canary to 50% then promote. Zero customer-impacting issues."
- **B5 DC API:** "Supplier-facing DC inventory read — OpenAPI design-first so consumers integrated in parallel (~30% faster). Three stages: edge validation → authorize + GTIN-translate + read EI over WebClient → map promo/turn-by-state. Multi-site is per-region config, not a runtime factory."
