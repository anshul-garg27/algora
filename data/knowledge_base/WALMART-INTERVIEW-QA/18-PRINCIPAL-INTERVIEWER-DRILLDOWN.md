# 18 — The Principal Interviewer Drill-Down (Brutal Follow-Up Chains)

> **Persona:** A 10-year staff/principal engineer who has interviewed 1,000 people. They don't ask single questions — they ask a **chain** that gets deeper with every answer until they hit the floor of your knowledge or catch a bluff. Their goal is to find the exact line between "this person built it" and "this person stood next to it."
>
> **How to use:** Read the chain top to bottom. Each arrow is the *follow-up they ask after your answer*. If you can't answer level 4, that's your study target. The model answers are the floor — say at least this much. **The tell they're hunting for: vague nouns ("we configured it for reliability") instead of specific mechanisms ("acks=all with min.insync.replicas=2"), and claiming code exists when it doesn't.**
>
> ---
>
> ### Conventions used in this doc
> - **Every load-bearing claim ends in a citation tag** like `[audit-srv KafkaProducerService.java:47]`. If you can't point to the file, you don't say it as fact.
> - **`[SHIPPED]`** = code that exists in the repo today. **`[NOT IN REPO — proposed]`** = a fix I would write but have not. A principal will say "show me" — labeling this *yourself* is the senior tell. I grepped the repos: there is **no** `Resilience4j` / `CircuitBreaker` / `Bulkhead`, **no** `orTimeout`, **no** body-size guard, **no** `audit_publish_failed` metric, **no** `RejectedExecutionHandler` anywhere in `cp-nrti-apis` or `audit-api-logs-srv`. Those are all proposed.
> - **Two repos, two systems — never conflate them.** AUDIT = `audit-api-logs-srv` (producer) + `audit-api-logs-gcs-sink` (Kafka Connect) + `dv-api-common-libraries` (the audited-service-side filter). NRTI = `cp-nrti-apis`. They have *different* durability stories.
> - **Topic-level numbers (partitions / RF / min.insync / retention) are NOT in any repo** — they're provisioned via Walmart KaaS. I answer those with a *formula and the value I'd request*, never an invented number.

---

## CHAIN 1 — "Walk me through the audit pipeline." (the opener that becomes a trap)

**L1.** *"Walk me through what happens when a supplier calls an audited API."*
→ A servlet `Filter` in the shared library wraps the request/response, builds an audit payload, and `@Async`-POSTs it to `audit-api-logs-srv`. That controller returns **204 immediately**, hands the work to a thread pool, then a producer serializes to Avro and `send()`s to Kafka. A Kafka **Connect** sink (not Spring) filters by country header, writes Parquet to per-country GCS buckets, and BigQuery external tables sit over them. `[dv-api-common-libraries LoggingFilter.java:37,111 → audit-srv AuditLoggingController.java:58 (204) → KafkaProducerService.java:47 → audit-api-logs-gcs-sink/kc_config.yaml:63]`

**L2.** *"You said 204 immediately. Immediately after what, exactly? What's the last thing that runs on the customer's thread?"*
→ On the **audited service's** request thread, the last thing is the `@Async` submit of the audit POST — `LoggingFilter.doFilterInternal` calls `auditLogService.sendAuditLogRequest(...)`, which is an `@Async` method, so it returns to the customer as soon as the task is queued on the `Audit-log-executor-` pool. On the **audit-srv** side, the controller's last act is `loggingRequestService.processLoggingRequest(...)`, which calls `executorPoolService.executeTaskInThreadPool(task)` — a submit to a cached thread pool — and *then* returns 204. The Avro build + `kafkaPrimaryTemplate.send()` run on a pool thread, off the request thread. `[LoggingFilter.java:111; AuditLoggingController.java:58-60; LoggingRequestService.java:38; ExecutorPoolService.java:12-13]`

**L3.** *"So the customer gets a 204 before the record is on Kafka. If the broker is down, what does the customer see?"*
→ Still 204 — it's fire-and-forget, and the failure is *invisible*. Here's the precise mechanism people get wrong: `kafkaPrimaryTemplate.send()` returns a `CompletableFuture` and completes **asynchronously on the producer I/O thread**. The code wraps it in a synchronous `try/catch`:
```java
// audit-srv KafkaProducerService.java:44-52
try {
  log.info("sending kafka msg for trace id {} ...");
  kafkaPrimaryTemplate.send(kafkaMessage);          // returns a future; NOT awaited
} catch (Exception ex) {
  log.info("sending kafka msg failed for {}", ...); // only catches SYNC errors
}
```
That `catch` only sees **synchronous** failures — serialization errors, buffer-full / `BufferExhaustedException`. A broker outage, a failed ack, a timeout — those complete the *future* exceptionally and are **never observed**, because nothing calls `.get()` / `.thenAccept()` / `.exceptionally()` on it. There's no producer-side DLQ. So the record is silently lost and the customer's call still succeeds. `[KafkaProducerService.java:44-52 — note: no callback attached to the returned future]`

**L4.** *"So your 'audit logging system' can silently lose audit records and nobody knows. In a compliance context, is that acceptable? Defend it or fix it."*
→ I'll defend the scope and then close the blind spot honestly. This feed is supplier-debugging convenience / a Splunk replacement, not the legal system of record — so best-effort is the *deliberate* trade, and it's reinforced by another config fact: the producer sets **no `acks`**, so the client default **acks=1** applies (`KafkaProducerConfig.populateConfigProperties` sets only bootstrap, serializers, schema URL, `auto.register=false`, and conditional SSL — there is literally no `ProducerConfig.ACKS_CONFIG` line). So even the durability floor is acks=1, not acks=all. `[KafkaProducerConfig.java:85-119]` The fix I'd ship is small: attach a callback to the future, emit an `audit_publish_failed` counter `[NOT IN REPO — proposed]`, alert on the rate, and add a producer-side DLQ. If it *became* compliance-critical, I'd make capture synchronous-durable.

**L5.** *"You mentioned acks. Your team's CCM yml actually declares an acks value. So it's not really acks=1, is it?"*
→ It *declares* one, but it doesn't take effect — and that's a subtle, real trap. The acks value lives in the CCM yml, but `KafkaProducerConfig` never reads an acks getter off the `@ManagedConfiguration` interface (`AuditLogsKafkaCCMConfig`); `populateConfigProperties` only wires bootstrap/serializers/schema/SSL. A declared-but-unread property is dead config. So effective acks = client default = **1**. The honest sentence is "the yml *claims* acks but the binding is missing, so the broker sees acks=1." `[KafkaProducerConfig.java:85-119 — no acks getter referenced]`

**L6.** *"An outbox or synchronous-durable write adds a DB write to every API call. You just told me the whole point was zero latency impact. So which is it — fast or durable? You can't have both."*
→ Correct, it's a CAP-style trade and you pick per requirement. Today it's tuned for latency (best-effort audit, acks=1, async submit). If durability became the requirement, I'd move the cost off the hot path differently: write to a **local append-only log / WAL on the same pod** synchronously (microseconds, no network) and have a separate shipper drain it to Kafka — durable *and* off the customer's critical path. `[NOT IN REPO — proposed; the WAL/outbox shipper does not exist today]` That's the honest "how I'd actually solve fast-AND-durable" rather than pretending the current design already is.

**L7 (the floor).** *"Be honest — is the current design a considered trade-off, or did nobody think about it?"*
→ A bit of both, and I won't pretend otherwise. The *async, off-hot-path* shape is clearly intentional — `ExecutorPoolService`, the 204, the `@Async` filter are deliberate. The *silent-loss* part (unobserved future, acks=1, declared-but-unread acks) reads more like accretion than a documented decision — there's no comment saying "we accept loss here." So my honest answer is: the latency posture was designed; the durability posture was inherited and never hardened. The senior move is to make the trade *explicit* — a one-paragraph design note + the failure metric — so the next person knows it's a choice, not a bug.

> **What they learned:** Do you understand that your design is a *choice* with a cost, can you name the exact line where loss becomes invisible, and will you separate "designed" from "inherited" instead of rationalizing everything?

---

## CHAIN 2 — "<5ms P99. Prove it." (the number interrogation)

**L1.** *"You claim <5ms P99 overhead. How did you measure that, and overhead on what?"*
→ It's the *added* P99 latency on the **audited endpoint**, audit-on vs audit-off — not end-to-end audit freshness. The only synchronous work on the customer's hot path is wrapping the request in `ContentCachingRequestWrapper`, building the payload, and the `@Async` submit; the network POST and Kafka send are off-thread. I'd frame it as "added P99 on the audited endpoint measured on/off," and I would **not** name a specific perf tool unless I can point to the suite, because I can't cite that from the repo. `[LoggingFilter.java:83-89 (caching wrappers), 111 (@Async hand-off)]`

**L2.** *"Building the payload copies the request and response bodies into memory. For a 5MB response, is that still <5ms?"*
→ Honestly, no. The `ContentCachingRequestWrapper`/`ContentCachingResponseWrapper` buffer the full body (`getContentAsByteArray()`), so capture cost scales with body size, and `copyBodyToResponse()` re-copies the response. There's **no body-size cap** anywhere in the filter. For typical inventory JSON (KB-scale) it's sub-ms; for a large/multipart endpoint it blows the budget and pressures heap. `[LoggingFilter.java:83-89, 93-102, 113]`

**L3.** *"So your <5ms claim is only true for small payloads. What stops a 50MB upload endpoint from being audited and OOMing you?"*
→ Only config discipline. Audit is **opt-in per endpoint** via a CCM allow-list — `shouldNotFilter` returns true (skip) unless the servlet path matches `auditLoggingConfig.enabledEndpoints()`. So we simply don't enable it on large-body endpoints. But that's *tribal knowledge*, not enforced — and I should state that boundary explicitly rather than let "<5ms" stand unqualified. `[LoggingFilter.java:124-128]`

**L4.** *"That's a convenient scoping. How do you stop a future engineer from adding a file-upload endpoint to that allow-list and taking the service down?"*
→ Today: nothing automated — it's a config-discipline gap. `[verified: no size guard in LoggingFilter]` The fix is a guard in `doFilterInternal` that skips capture (and emits a metric) above a configurable body-size threshold, so the safety becomes a property of the *code*, not of whoever edits the allow-list. `[NOT IN REPO — proposed]`

**L5 (the floor — the conflation trap).** *"Forget overhead. A record I audit right now — when can I actually query it in BigQuery? Is that also <5ms?"*
→ No — and this is the number people conflate. Hot-path overhead (<5ms) and **end-to-end freshness** are different claims. Freshness is *minutes*, gated by the **sink flush policy**, not by my producer. The Lenses GCS sink flushes a Parquet object on whichever fires first: `flush.size` (50MB), `flush.count` (5000 records), or `flush.interval` (**600s = 10 min**). At our modest audit volume, count/size rarely trip, so the **10-minute interval** dominates. So: overhead to the *caller* is sub-5ms; time-to-queryable in BigQuery is **up to ~10 minutes**. If someone hears "<5ms" and assumes the data is queryable in 5ms, that's a misread I have to correct up front. `[kc_config.yaml / KCQL flush.interval=600s — sink flush, not producer]`

> **What they learned:** Do you know the *boundary conditions* of your own number, and do you proactively separate "latency added to the caller" from "freshness of the data"? Conflating them is the #1 way this stat gets you caught.

---

## CHAIN 3 — "Active/active with zero data loss." (the durability corner — NRTI)

> **Scope guard (say this first):** active/active app-level dual-write is the **NRTI** story (`cp-nrti-apis`), *not* audit. Audit-srv has a `kafkaSecondaryTemplate` bean, but it's **dead code** — the publish path only ever calls `kafkaPrimaryTemplate.send()`; nothing invokes the secondary. So "active/active" is true for NRTI and **false** for audit. `[audit-srv KafkaProducerConfig.java:60-63 (secondary bean exists) vs KafkaProducerService.java:47 (only primary used)]`

**L1.** *"Explain your active/active failover for NRTI."*
→ Each region's deployment points its *primary* template at the region-local cluster and its *secondary* at the other region (broker URLs swapped per region in CCM). The IAC publish sends to primary; on the future's `.exceptionally`, it re-sends to the secondary region via `handleFailure`. `[NrtKafkaProducerServiceImpl.java:69 (primary send), 84-89 (.exceptionally → handleFailure), 159-175 (secondary send)]`

**L2.** *"'Zero data loss' — show me the config that guarantees it."*
→ The producer tuning is real and CCM-sourced, not hand-waved. `NrtKafkaProducerConfig.populateConfigProperties` reads every value off `NrtKafkaCCMConfig` getters:
```java
// cp-nrti-apis NrtKafkaProducerConfig.java:114-121
configProps.put(MAX_REQUEST_SIZE_CONFIG, ...getNrtKafkaMaxRequestSize());     // 10,000,000 (10MB)
configProps.put(COMPRESSION_TYPE_CONFIG, ...getNrtCompressionTypeConfig());   // lz4
configProps.put(ACKS_CONFIG,            ...getNrtAcksConfig());               // all
configProps.put(LINGER_MS_CONFIG,       ...getNrtLingerMsConfig());           // 20
configProps.put(BATCH_SIZE_CONFIG,      ...getNrtBatchSizeConfig());          // 8192
configProps.put(REQUEST_TIMEOUT_MS_CONFIG, ...getNrtRequestTimeoutMsConfig());// 300000 (5 min)
configProps.put(RETRIES_CONFIG,         ...getNrtKafkaRetriesConfig());       // 10
configProps.put(ENABLE_IDEMPOTENCE_CONFIG, ...getNrtKafkaIdempotenceConfig());// false
```
So acks=all + retries=10 + RF3 means an *acknowledged* record is replicated to `min.insync.replicas` before ack. But `enable.idempotence=false` is an **explicit getter value** (`nrtKafkaConfig.json` literally has `"nrtKafkaIdempotenceConfig": "false"`), so it's **at-least-once, not exactly-once** — I can't wave it away as an oversight. I'd reframe "zero loss" as "**no observable loss of an *acknowledged* event under single-region failure.**" `[NrtKafkaProducerConfig.java:114-121; nrtKafkaConfig.json: acks=all, retries=10, idempotence=false, lz4, batch=8192, linger=20, timeout=300000, maxReq=10000000]`

**L3.** *"acks=all with idempotence explicitly off. Walk me through a sequence where you lose ordering."*
→ For **DSC** (which *has* a key) it's the classic one: with `max.in.flight.requests>1` and retries, batch 1 fails and is retried while batch 2 (sent after) succeeds first → batch 2 lands before batch 1 on the partition. Idempotence would pin this with PID + per-partition sequence numbers; we don't enable it. But for **IAC the premise is mostly moot** — IAC has a **null partition key** (next level), so there's no stable per-partition stream to reorder in the first place. `[DscServiceHelper.java:264 sets KafkaHeaders.KEY; idempotence=false]`

**L4.** *"Your messageId dedup — where does it run, and what's its failure mode?"*
→ Consumer-side, in downstream services — we're **producer-only** for NRTI. The `messageId` is **client-supplied** (it comes straight off the request: `IacKafkaPayloadHeader.messageId = nrtInventoryActionsRequest.getMessageId()`), so two distinct events with a colliding ID → a consumer wrongly drops a legitimate one. Mitigation: namespace the dedup key (e.g. `supplierId + messageId`) or generate it server-side. `[IacServiceHelper.java:73 (messageId from request); 189 (MESSAGE_ID header)]`

**L5.** *"You keep saying 'consumers dedup.' You don't own the consumers. So how do you actually know dedup happens at all?"*
→ Fair — I can't claim a guarantee I don't own. What I own is the *producer contract*: stable `messageId`, at-least-once delivery. Whether dedup is correct is a **cross-team contract** I'd verify with a consumer integration test and a documented idempotency requirement, not assume. End-to-end "zero data loss" is only as strong as that downstream contract — I'd want it tested, not asserted.

**L6.** *"Then why build at-least-once + downstream dedup instead of exactly-once?"*
→ Because exactly-once across regions **isn't available to us by topology**. Kafka EOS (idempotent + transactional producer) is **per-cluster** — a transaction can't span two independent clusters. On failover we write to a *different* cluster, so a cross-region transaction is impossible. So end-to-end EOS was off the table; at-least-once + idempotent consumers is the standard, achievable multi-cluster pattern. The real alternative is **MirrorMaker2 with offset translation**, which trades my sub-second app-level failover for platform-managed async replication. I chose app-level dual-write for failover speed and control, and accepted the dedup contract as the cost.

**L7 (the floor).** *"Given idempotence is off and you can't verify the consumer, what's the strongest *true* statement you can make about NRTI durability?"*
→ "Under a single-region Kafka failure, an **acknowledged** IAC event is re-sent to the surviving region and surfaces an **HTTP 500** to the caller if *both* regions fail (`NrtiUnavailableException` = `INTERNAL_SERVER_ERROR`; arguably should be a 503 + `Retry-After`), so an unacknowledged event is the caller's to retry — and duplicates/reordering are possible and must be tolerated downstream." That's the honest envelope. What I will **not** say is "exactly-once" or "guaranteed zero loss end-to-end," because neither is true for this topology, and the interviewer will know it.

> **What they learned:** Do you understand *why* exactly-once is impossible in your topology (per-cluster transactions), and can you state the precise, defensible durability envelope instead of the resume phrase?

---

## CHAIN 4 — "The .join() on the Tomcat thread." (the concurrency takedown — NRTI IAC)

**L1.** *"Your IAC publish calls .join(). What thread is that on, and why does IAC do it but DSC doesn't?"*
→ The Tomcat worker thread handling the HTTP request. IAC `.join()`s deliberately so it can **surface failure to the caller** — it's a system-of-record mutation. DSC is fire-and-forget (no join) because it's best-effort. `[NrtKafkaProducerServiceImpl.java:89 (.join()), 102-133 (DSC, no join)]`

**L2.** *"So the request thread blocks on Kafka. What's your Tomcat max threads?"*
→ The platform default (~200) **unless overridden** — and I checked: `cp-nrti-apis/src/main/resources/application.properties` only sets `server.tomcat.mbeanregistry.enabled=true`, **not** `server.tomcat.threads.max`. So it's the Spring Boot default unless KaaS/CCM overrides it at deploy time. I won't assert a hard 200 as if it's in my config — it isn't. `[application.properties:7 — no threads.max override]`

**L3.** *"Primary Kafka starts taking 2 seconds per send. You're doing 300 req/s. Do the math out loud."*
→ Little's Law: concurrent threads needed = arrival rate × latency = 300 × 2s = **600 threads**, but I have ~200 → the pool saturates, requests queue, then time out → cascading 503s. HTTP availability is now coupled to Kafka latency, because IAC blocks on `.join()`.

**L4.** *"And your request.timeout.ms is 5 minutes. So in the worst case a thread is stuck for...?"*
→ Up to **5 minutes** — `request.timeout.ms=300000` `[NrtKafkaProducerConfig.java:119; nrtKafkaConfig.json:7]`. A *black-hole* primary (accepts connections, never acks) doesn't fail fast; the future stays pending up to 5 minutes before `.exceptionally` even fires, so failover is bounded by `request.timeout.ms`, not by my `.exceptionally`. The service falls over long before failover triggers. That's the real bug.

**L5.** *"You designed this. Why didn't you catch it before prod?"*
→ The happy path and the *fast-fail* path (connection refused → instant) both look fine in testing; the **black-hole / slow-primary** case only shows under a partial network fault we didn't game-day. That's the gap. The fixes I'd ship — and I'm explicit that **none exist in the repo today**: `future.orTimeout(2, SECONDS)` to bound failover regardless of failure mode; a circuit breaker so a sick primary trips fast instead of timing out per-request; and a **bulkhead** (separate bounded pool for publishing) so Kafka latency can't drain the servlet pool. `[NOT IN REPO — proposed; grep finds no orTimeout / Resilience4j / Bulkhead in cp-nrti-apis]`

**L6.** *"If you add a circuit breaker, when it's open you're not writing to primary. Where do those events go?"*
→ Straight to the secondary region — the breaker's fallback is my existing `handleFailure` path `[NrtKafkaProducerServiceImpl.java:159-175]`. If both are open, fail fast with 503 so the supplier retries, instead of holding a thread for 5 minutes. The breaker converts a slow cascading failure into a fast clean one — strictly better for availability even though some events take the secondary path. (Still proposed.)

**L7 (the floor).** *"Even with all that — IAC blocks the request thread by design. Is synchronous publish on a servlet thread the right architecture at all?"*
→ Honestly, it's the right *semantics* (caller must know if a system-of-record write failed) implemented on the *wrong substrate* (a blocking servlet thread). The correct end-state is to make the caller-facing contract explicit — return 202 + a status the caller polls, or move IAC onto a reactive/non-blocking publish so a slow broker consumes a bounded async resource, not the request pool. I'd defend the *intent* (surface failure) and concede the *mechanism* (`.join()` on Tomcat) is a thread-occupancy liability I'd redesign.

> **What they learned:** Can you reason about your system *under load and partial failure* with real numbers (Little's Law, the 5-min timeout), and separate a correct intent from a flawed mechanism?

---

## CHAIN 5 — "You 'led' the Spring Boot 3 migration." (the ownership probe)

**L1.** *"What was the hardest single bug in the migration?"*
→ A Hibernate 6 enum mapping. Under Hibernate 5 a Postgres enum column persisted/read fine; Hibernate 6's stricter type system mapped it differently and reads came back **wrong — a wrong-200, not an exception**. Fixed with `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` on the entity fields. `[cp-nrti-apis ParentCompanyMapping.java:127,135 — @JdbcTypeCode(SqlTypes.NAMED_ENUM)]`

**L2.** *"A wrong-200. Your canary gate is 5xx-rate. So the canary would have promoted that bug to 100%. How did you actually catch it?"*
→ Exactly — that's the limitation of a 5xx-only gate. The canary block is literally:
```yaml
# cp-nrti-apis/kitt.yml:726-746
canaryAnalysis:
  stepWeight: 10
  maxWeight: 50
  interval: 2m
canaryReplicaPercentage: 50
canaryService:
  - name: "Check for Internal Server Error (5XX)"
    threshold: 1            # 5XX > 1% over a 2-minute interval fails the canary
    query: |  # PromQL on outbound 5XX rate
```
A wrong-200 produces **zero 5XX**, so the gate is blind to it. It was caught earlier — in **stage**, by contract tests comparing response bodies, before canary. So I credit the staged soak + contract tests for "zero customer impact," not the canary. `[kitt.yml:727 stepWeight:10, :728 maxWeight:50, :729 interval:2m, :735 threshold:1]`

**L3.** *"So your canary is essentially blind to correctness regressions. Why even canary then?"*
→ The canary protects against **infra/availability** regressions (5XX spikes, crashes) on **real production traffic** that stage can't replicate. Correctness is caught earlier by contract/integration tests. They're complementary layers — the canary isn't the correctness gate; that's a test-pyramid job.

**L4.** *"Then close the gap. Add a metric to that gate that would catch a latency or correctness regression — be specific."*
→ Two additions: (1) a **latency gate** — a PromQL P99 query on the canary service with a threshold (e.g. fail if canary P99 > 1.2× baseline) — `goldenSignalMetrics` is already imported at `kitt.yml:14`, so I'd extend `canaryService` with a second check rather than invent infra. (2) For correctness, a **shadow/diff check** comparing canary vs primary response bodies on mirrored traffic. (1) is cheap and closes the latency blind spot the 5XX-only gate has today. `[kitt.yml:14 goldenSignalMetrics imported; :732 canaryService is the extension point]`

**L5.** *"Show me you did the migration. Spring Kafka's send() return type changed in 3.x. From what to what, and what code of yours broke?"*
→ `ListenableFuture` → `CompletableFuture`. The Spring Kafka 2.x style was `addCallback(onSuccess, onFailure)`; the current code uses `.thenAccept(...).exceptionally(...).join()` — and I verified there's **no** `ListenableFuture` or `addCallback` left in the repo, consistent with the rewrite. I'll frame the "before" as the *known Spring Kafka 2.x API* rather than swearing my exact prior code existed (no git history in front of me to prove that), but the failover code is unambiguously written in the 3.x `CompletableFuture` idiom. `[NrtKafkaProducerServiceImpl.java:76-89 (.thenAccept/.exceptionally/.join); grep: no ListenableFuture/addCallback in repo]`

**L6 (the floor).** *"The Jakarta rename — your common-libraries JAR is still `javax.servlet` but the app is Jakarta. How does a `javax.servlet.Filter` even load in a Jakarta container? Be precise or admit you don't know."*
→ It doesn't, *if* it were registered as a container filter — the types are incompatible (`javax.servlet.Filter` ≠ `jakarta.servlet.Filter`). The proof it's still javax: `LoggingFilter` imports `javax.servlet.FilterChain` / `javax.servlet.http.HttpServletRequest` `[dv-api-common-libraries LoggingFilter.java:15-17]`, and that JAR is Spring Boot **2.7.11 / Java 11** `[common pom.xml:17-18,30]`, while `cp-nrti-apis` is Spring Boot **3.5.14 / Java 17 / Jakarta** `[cp-nrti pom.xml:7-8,26]`. It coexists only because the consuming app **provides its own Jakarta filters**, doesn't register the old JAR's filter as a bean, and **excludes the JAR's webflux starter** so the old reactive stack doesn't leak in (`cp-nrti pom.xml:474` excludes `spring-boot-starter-webflux` under the `dv-api-common-libraries` dependency, consumed at version **0.0.61** vs the in-repo **0.0.45**). The genuinely correct fix is a Jakarta-targeted rebuild of the library; the current coexistence is fragile tech debt I'd flag. `[cp-nrti pom.xml:470-474 (dep 0.0.61 + webflux exclusion); common pom.xml:7 (version 0.0.45)]`

> **What they learned:** Did you *do* the migration (the wrong-200 enum bug, the `ListenableFuture→CompletableFuture` reshape, the javax/Jakarta coexistence hazard) or ride along — and do you know the canary gate's exact numbers and blind spots?

---

## CHAIN 6 — "Geo-routing in the sink." (the design-judgment grill + residency)

**L1.** *"Why filter by country in the sink instead of at produce time?"*
→ One immutable topic = the simplest producer; residency enforced at the **storage boundary** where the per-country buckets live. Three Connect connectors each filter their country via an SMT. `[kc_config.yaml:63 (US), :81 (CA), :99 (MX)]`

**L2.** *"Three connectors each read the entire topic. That's 3x the broker read traffic. Justify that cost."*
→ Each connector is a separate consumer group (`tasks.max:1` each), so yes — the topic is read **3×** (3× read amplification) by design. `[kc_config.yaml:66,84,102 tasks.max:1]` It buys per-country isolation (one country can lag/retry/pause independently) and dead-simple per-country config. At our audit volume the egress is acceptable; at ~10× I'd collapse to a single connector that branches to per-bucket sinks to kill the amplification. (The cost math is its own chain below.)

**L3.** *"A record shows up with no `wm-site-id` header. Which bucket does it land in, and is that a residency violation?"*
→ **US bucket** — and here's the exact line that makes it so. The base filter drops anything that doesn't strictly match its site id:
```java
// BaseAuditLogSinkFilter.java:40-44, 52-56
public R apply(R r) { return verifyHeader(r) ? r : null; }          // null = drop
public boolean verifyHeader(R r) {
  return StreamSupport.stream(r.headers().spliterator(), true)
      .anyMatch(h -> HEADER_NAME.equals(h.key())
          && StringUtils.equals(getHeaderValue(), String.valueOf(h.value())));  // strict
}
```
CA and MX inherit that strict `anyMatch`, so a header-less record is **dropped** by them. But the **US filter overrides** `verifyHeader` to add a catch-all:
```java
// AuditLogSinkUSFilter.java:42-49
return StreamSupport.stream(r.headers().spliterator(), true)
        .anyMatch(h -> HEADER_NAME.equals(h.key()) && StringUtils.equals(getHeaderValue(), ...))
    ||  StreamSupport.stream(r.headers().spliterator(), true)
        .noneMatch(h -> HEADER_NAME.equals(h.key()));   // <-- catch-all: header MISSING → pass
```
That one `noneMatch` clause means: header missing → US passes it. So if a **non-US** service forgets the header, its data silently lands in the **US** bucket = a residency leak. That's a real risk, and the exact line to change is `AuditLogSinkUSFilter.java:48-49`. `[BaseAuditLogSinkFilter.java:40-44,52-56; AuditLogSinkUSFilter.java:42-49]`

**L4.** *"So your residency guarantee depends on every producer remembering a header. That's not a guarantee, that's a hope. Make residency structurally enforced."*
→ Agreed — header-driven routing is best-effort, not enforced. Structural options: (a) route to **per-country topics at produce time** so the topic itself is the residency boundary; (b) make the header **mandatory** — quarantine header-less records to a dedicated bucket instead of defaulting to US (i.e. delete the `noneMatch` catch-all and add a "no-site-id" sink); (c) **derive country server-side** from the authenticated supplier identity rather than trusting a client header. (c) is strongest because it removes client trust entirely.

**L5 (the floor).** *"Option (a) means a topic per country. You praised 'one immutable topic' for simplicity. Your two instincts contradict each other. Which principle wins and why?"*
→ They optimize different things and the answer is requirement-driven. "One topic" optimizes producer simplicity + operational surface; "topic per country" optimizes residency enforcement + kills the 3× read amplification. When residency is a **compliance/legal** requirement (real money/legal risk), enforcement beats simplicity → per-country topics win and I accept the extra topics. When it's a soft preference, simplicity wins. The skill isn't holding one principle dogmatically; it's knowing which *requirement* dominates this decision. Here residency is legal → move enforcement to produce-time, even though it contradicts my default "keep the producer simple."

> **What they learned:** Can you point to the *single line* (`noneMatch` catch-all) that turns a missing header into a residency leak, and adjudicate two competing principles with a requirement instead of reciting "keep it simple"?

---

## CHAIN 7 — The "do you actually understand the framework" sniper rounds

Single shots that instantly reveal depth. No chain — just whether you know it cold. (Filter ones cite `dv-api-common-libraries/LoggingFilter.java`.)

- *"Your `@Async` bean — JDK proxy or CGLIB, and how would I tell?"* → CGLIB by default (Spring Boot sets `proxyTargetClass=true`); check `bean.getClass().getName()` for `$$EnhancerBySpringCGLIB` / `$$SpringCGLIB`.
- *"Mark the `@Async` method `final`. What happens?"* → CGLIB can't override a final method → the advice doesn't apply → it runs **synchronously**, silently. No error. (Same hazard kills `@Transactional` on final methods.)
- *"Call your `@Async` method from another method in the same class. Async?"* → No — self-invocation bypasses the proxy; runs on the caller thread.
- *"Where does the JDBC connection live during a `@Transactional` method?"* → Bound to the thread via `TransactionSynchronizationManager` (a ThreadLocal). That's why a transaction doesn't cross an `@Async` thread hop — the new thread has no bound connection.
- *"`ThreadPoolTaskExecutor` core 6, max 10, queue 100 — when does it create thread #7?"* → Only after the queue (100) is full. Order is **core → queue → max → reject**. Most people say core → max → queue (wrong). This is the *audited-service-side* pool: `AuditLogAsyncConfig.taskExecutor()` sets core 6 / max 10 / queue 100 and `initialize()`. `[dv-api-common-libraries AuditLogAsyncConfig.java:17-26]`
- *"That pool sets no `RejectedExecutionHandler`. What happens at saturation?"* → Spring's `ThreadPoolTaskExecutor` default is **AbortPolicy** → it throws `RejectedExecutionException` on the *caller* (the audited request thread) once core+queue+max are all full → the audit log is **silently dropped** for that request. Two distinct pools, two distinct failure modes — see CHAIN 8. `[AuditLogAsyncConfig.java:17-26 — no setRejectedExecutionHandler]`
- *"Your filter is `OncePerRequestFilter`. Why 'once per request' — when would a plain Filter run twice?"* → On internal forwards/includes and async dispatch the request re-enters the chain; the base class uses a request-attribute flag to dedupe so audit isn't double-recorded. `[LoggingFilter.java:37 extends OncePerRequestFilter]`
- *"`@Order(Ordered.LOWEST_PRECEDENCE)` on the filter — why last?"* → So every other filter (auth, XSS, CORS) has run and the response is fully formed before audit captures it; capturing first would record a half-built response. `[LoggingFilter.java:35]`
- *"Why a Filter and not a `HandlerInterceptor` for body capture?"* → Only a Filter sees the raw servlet request early enough to wrap it in `ContentCachingRequestWrapper`; the body stream is read-once, and an interceptor runs *after* the body's already consumed by the dispatcher. `[LoggingFilter.java:83-89]`
- *"Avro value, String key — why isn't the key Avro too?"* → The key is a routing/partitioning token (`serviceName + "/" + endpoint`); it needs determinism, not schema evolution. Avro on the key adds registry overhead for no benefit. `[AuditKafkaPayloadKey.java:26-27; KafkaProducerConfig.java:89-90 (StringSerializer key, KafkaAvroSerializer value)]`
- *"`enable.idempotence=true` — what does the broker do differently?"* → The producer gets a PID and per-partition sequence numbers; the broker rejects duplicates and out-of-order sequences, de-duping retries and pinning order (caps in-flight to 5). NRTI has this **off** (`idempotence=false`), by explicit config. `[NrtKafkaProducerConfig.java:121]`
- *"`acks=all` — 'all' of what?"* → All **in-sync replicas** (`min.insync.replicas`), not all replicas. If ISR shrinks below min.insync, the producer gets an error instead of a false ack — that's the durability point. NRTI sets acks=all; audit-srv is acks=1 (default, no acks line). `[NrtKafkaProducerConfig.java:116 vs KafkaProducerConfig.java:85-119]`

---

## CHAIN 8 — "What keeps you up at night?" (the closer — and the two-pool trap)

**L1.** *"What's the thing about this system that keeps you up at night?"*
→ The audit silent-drop surface — and I have to be precise, because it's **two different pools in two different repos with two different failure modes**, not one:
> **(A) audit-srv** `ExecutorPoolService` = `Executors.newCachedThreadPool()` — **unbounded**, **no** rejection policy. It never *rejects*; under a burst it grows threads without bound → thread/OOM blowup. `[ExecutorPoolService.java:10, called from LoggingRequestService.java:38]`
> **(B) dv-api-common-libraries** `AuditLogAsyncConfig.taskExecutor` = `ThreadPoolTaskExecutor` core 6 / max 10 / queue 100, **no** `RejectedExecutionHandler` → Spring default **AbortPolicy** → on saturation it **throws and silently drops** the audit log. `[AuditLogAsyncConfig.java:17-26]`
> So pool (A) can **OOM** (unbounded growth) and pool (B) can **silently drop** (bounded + AbortPolicy). They are *not* the same thing — "AbortPolicy on an unbounded pool" would be self-contradictory; the unbounded one has no policy at all. On top of both, send failures are only logged, never surfaced (CHAIN 1). We'd find out from a *gap in the data*, not an alert.

**L2.** *"Good. So why is it still like that? You knew. Why didn't you fix it?"*
→ Honest answer: it's never failed in prod, so it's been below the line against feature work — classic "works until it doesn't." Each fix is small and *currently does not exist*: bound pool (A) and give it a `RejectedExecutionHandler` `[NOT IN REPO — proposed]`; set an explicit handler + a dropped-audit metric on pool (B) `[NOT IN REPO — proposed]`; attach a failure callback to the producer future. That's roughly a half-day that removes a silent-data-loss + OOM class of failure. Cheap insurance.

**L3.** *"Which one keeps you up more, and which is the half-day PR?"*
→ Pool (A)'s unbounded growth scares me more — a silent drop loses one record; an OOM takes the whole pod down and *then* drops everything in flight, region-wide under a correlated burst. The half-day PR is bounding (A) with a fixed pool + `CallerRunsPolicy` (back-pressure onto the submitter instead of OOM) and adding the metric. Bounded-with-back-pressure converts an availability-killer into a measurable slowdown.

**L4 (the floor — the senior signal).** *"If it's a half-day fix for a serious risk and you know exactly what to do, the fact that it's not done is a prioritization failure. Whose?"*
→ Mine, partly — knowing a cheap fix for a real risk and not making the case for it loudly enough is on me, not "the backlog." The senior move isn't just *knowing* the gap; it's **quantifying** it (silent compliance-data loss + OOM blast radius across the region) so the team can make an informed call, and writing the one-day fix as a ready-to-merge PR so "no time" stops being the reason. I'd own that.

> **What they learned:** Can you keep two failure modes straight without conflating them, and turn "I know a gap" into "I drive the fix" instead of blaming the backlog?

---

## CHAIN 9 — "How many partitions?" (the ops/sizing trap — the number you must NOT invent)

**L1.** *"How many partitions does your audit topic have?"*
→ I don't have that in my repo, and I won't guess. Partition count, RF, `min.insync.replicas`, and retention are **KaaS-provisioned topic properties**, external to the service code — none of them appear in `audit-api-logs-srv` or `cp-nrti-apis`. What I *can* tell you is the value I'd **request** and the formula behind it. (Saying "I think it's 12" here is the fastest way to get caught.)

**L2.** *"Fine. What would you request, and how did you decide?"*
→ Formula: `partitions = max( ceil(target_peak_eps / per_partition_ceiling), desired_consumer_parallelism )`. For audit, throughput is *never* the binding constraint — sub-KB Avro at modest eps is ~MB/s, which a single partition clears. What binds it is **consumer parallelism** (a group can't exceed partition count, and I have 3 sink connectors with room to raise `tasks.max`) and **broker spread** for RF3. So I'd request **6**: even spread on a 3-broker cluster + headroom, because repartitioning a *keyed* topic later reshuffles key→partition and breaks ordering. `[partition key = AuditKafkaPayloadKey.java:26-27]`

**L3.** *"RF and min.insync — same answer?"*
→ Same provenance (KaaS, not in repo), and I'd request **RF=3 / min.insync=2** — the broker DNS fronts a 3-broker-per-region cluster, so RF3 is the natural fit and survives one broker loss with quorum. Caveat I'd volunteer: for **audit**, min.insync=2 is *moot today* because the producer runs at acks=1 (no acks line) — min.insync only gates writes under acks=all. For **NRTI** it's load-bearing, because NRTI explicitly sets acks=all `[NrtKafkaProducerConfig.java:116]`, so acks=all + min.insync=2 is what actually delivers the zero-loss-of-acknowledged guarantee.

**L4.** *"Now scale me to 100×. What breaks first?"*
→ Not the brokers — the **sink**. At 100× audit volume, the 3× read amplification (CHAIN 6) becomes the dominant cost, and the 10-min `flush.interval` means objects fill on `flush.size`/`flush.count` instead, generating far more, smaller Parquet files → BigQuery scan cost climbs (CHAIN 10). I'd (1) collapse the 3 connectors into one branching connector to kill amplification, (2) raise partition count + `tasks.max` for parallelism, and (3) tune flush so Parquet objects stay large (fewer, bigger files scan cheaper). The producer side barely notices; the *storage/query* side is where 100× hurts.

**L5 (the floor).** *"You just sized a system from numbers you admit you can't see. Why should I trust any of it?"*
→ Because I'm explicit about the line between *measured* and *requested*. Everything in my code — producer tuning, HPA, sink flush, the filter — I quote by file:line. For topic-level settings that live in KaaS, I tell you they're not in my repo and I defend a value with a formula tied to things I *can* see: the 3-broker topology, the consumer-group count, the event size, the ordering-key cardinality. A senior answer isn't "I memorized 12"; it's "here's how I'd derive it and here's the failure mode if I got it wrong." Inventing a number I can't ground is exactly the bluff you're hunting for.

> **What they learned:** Do you know the *boundary* of your own knowledge — what's in your code vs. what's provisioned externally — and can you size with a defensible formula instead of fabricating a number?

---

## CHAIN 10 — "What does this cost?" (the money chain — read amplification + BigQuery)

**L1.** *"Your audit pipeline — where does the money actually go?"*
→ Three places: (1) Kafka **read egress** — the topic is read **3×** because the 3 sink connectors are 3 separate consumer groups (`tasks.max:1` each) `[kc_config.yaml:63,81,99]`; (2) **GCS storage** of Parquet; (3) **BigQuery scan** cost on the external tables over those buckets. The compute (producer, HPA min4/max8 @60% CPU for audit prod) is the cheap part.

**L2.** *"That 3x read — is it 3x the bytes off disk, or 3x the network?"*
→ Effectively both per consume: each connector independently fetches the full partition set, so the brokers serve the topic's bytes three times. It's a *deliberate* trade for per-country isolation, but at scale it's pure waste — two of the three reads discard most records (CA and MX strictly drop everything that isn't theirs; US is the catch-all). `[AuditLogSinkUSFilter.java:42-49; BaseAuditLogSinkFilter.java:40-44]`

**L3.** *"BigQuery bills on bytes scanned. What in your design makes scans expensive, and what makes them cheap?"*
→ Cheap: the data is **Parquet** (columnar — BigQuery scans only referenced columns) and **partitioned on disk** by `service_name, _header.date, endpoint_name` via the KCQL `PARTITIONBY`, so date-bounded, service-scoped queries prune hard. Expensive: small files. If flush produces many tiny Parquet objects (high volume tripping `flush.count=5000` long before the 10-min interval), per-file overhead and poor compression inflate scanned bytes. The lever is flush tuning — keep objects large. `[KCQL STOREAS PARQUET, PARTITIONBY service_name,_header.date,endpoint_name; flush.size=50MB/flush.count=5000/flush.interval=600s]`

**L4.** *"So how would you cut the bill by half without losing the per-country guarantee?"*
→ Kill the amplification: replace the 3 single-task connectors with **one** connector whose SMT/router branches to the three per-country GCS sinks — one read of the topic, three write destinations. That removes 2 of the 3 reads (the dominant egress cost) while keeping per-country buckets intact. Then enforce large Parquet objects (raise effective flush size, or compact) so BigQuery scans fewer, denser files. The residency guarantee is unchanged because the *routing* still keys on `wm-site-id`; I've only de-duplicated the *read*.

**L5 (the floor).** *"You designed 3 connectors knowing it's 3x the read. Was that a mistake?"*
→ At the volume we run, no — it bought operational simplicity (independent per-country lag/pause/retry, dead-simple config) for a read cost that's negligible on a low-throughput audit feed. It *becomes* a mistake at ~10×, which is why I have the single-branching-connector design ready as the next step. The honest framing: it was the right call for *today's* scale and the wrong call for *tomorrow's*, and knowing the exact crossover (when egress + small-file scan cost exceeds the ops savings) is the actual engineering judgment — not "always minimize reads."

> **What they learned:** Do you connect architecture to dollars (read egress, columnar scan, file size) and know the *crossover* where a simplifying choice flips to a costly one — or do you only think in latency and availability?

---

## CHAIN 11 — "Is this even a Spring Boot starter?" (the abstraction-honesty trap)

**L1.** *"You call `dv-api-common-libraries` a 'starter.' Walk me through how a consuming service auto-configures it."*
→ I'll correct the word first: it's a **shared Maven library, not a true Spring Boot starter.** A real starter ships auto-configuration that activates on the classpath. This JAR does **not** — there's no `META-INF/spring.factories` and no `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`; in fact it has no `src/main/resources` to put them in. So nothing auto-wires. `[dv-api-common-libraries — no spring.factories / AutoConfiguration.imports]`

**L2.** *"Then how does a consumer actually pick up the filter and beans?"*
→ Manually. The consuming app has to `@ComponentScan` `com.walmart.dv.*` to discover `@Component`/`@Configuration` classes (the `LoggingFilter`, `AuditLogAsyncConfig`, etc.), and it must provide its own `WebClient` bean because the JAR's `AuditHttpServiceImpl` depends on one but the JAR doesn't supply it. So "drop the dependency and it works" is false — there's required wiring on the consumer side. `[LoggingFilter.java:36 @Component; AuditLogAsyncConfig.java:13-15 @Configuration; AuditHttpServiceImpl uses WebClient.block()]`

**L3.** *"That sounds fragile. What concretely goes wrong if a consumer forgets a step?"*
→ Two real failure modes. (1) Forget the component scan → the filter never registers → audit silently does nothing (no error, just no data). (2) The **version skew** — the JAR is built Spring Boot 2.7.11 / Java 11 and is `javax.servlet`, but it's consumed by a Boot 3 / Jakarta app, so the consumer must *exclude the JAR's webflux starter* and avoid registering the javax filter, or the old reactive stack and incompatible servlet types leak in (CHAIN 5 L6). It works today by careful exclusions, not by design. `[cp-nrti pom.xml:470-474 (consumed 0.0.61 + webflux exclusion); common pom.xml:17-18,30 (2.7.11/Java 11)]`

**L4.** *"Also — your library copies request headers into the audit log. All of them?"*
→ Yes, and this is a real PII/secret-leak finding. The audited-service-side path copies headers **including `WM_SEC.*` / `Authorization` unmasked** (`mask.enable=false`), so credentials can end up in the audit store. On the producer side, `KafkaProducerService.setHeaders` does restrict to an allow-list (`wm_consumer.id`, `wm_qos.correlation_id`, `wm_svc.*`, `wm-site-id`) `[KafkaProducerService.java:92-98]`, but the upstream capture in the common library is permissive. I'd flag the unmasked-secret copy as the highest-severity item in the whole system. `[dv-api-common-libraries audit capture — mask.enable=false, copies WM_SEC.*/Authorization]`

**L5 (the floor).** *"So you've been calling a manually-wired, version-skewed, PII-leaking JAR a 'starter.' Is the resume wrong?"*
→ The *word* oversells it; the *work* is real. What I actually own is a reusable cross-cutting audit-capture library adopted by multiple services — that's genuine leverage. But "Spring Boot starter" implies auto-configuration this doesn't have, so the precise claim is "a shared audit/observability **library** with a manual integration contract." I'd rather say that and be unassailable than say "starter" and get dismantled on `spring.factories`. And the version skew + unmasked secrets are tech debt I'd name as the roadmap, not hide.

> **What they learned:** Do you use framework terms precisely (library vs. starter, the auto-config mechanism), and will you right-size your own resume claim before the interviewer right-sizes it for you?

---

## CHAIN 12 — "You led DC inventory end-to-end." (the attribution probe — the genre that sinks people)

**L1.** *"You say you led the DC inventory feature end-to-end. Walk me through the controller."*
→ `DcInventoryController` exposes `POST /inventory/status`, `@ResponseStatus(HttpStatus.OK)` (200), takes a `DcInventoryStatusRequest` (`dcNbr` + a list of item values) plus an optional `itemIdentifier` param, validates via `NrtBusinessValidatorService`, resolves the supplier mapping, dedups the item numbers, and calls `dcInventoryService.getDcInventoryStatus(...)`. The downstream Enterprise Inventory call is an unusual **GET-with-body** over a reactive `WebClient` with `.timeout(10s)` + `Retry.backoff(3, 100ms, max 2s)` + `.block()`. `[DcInventoryController.java:104-151; HttpServiceImpl.java:71-94 (GET-with-body, timeout/retry/block)]`

**L2.** *"git blame shows Keshav Gatla and Ambiorix Cruz Angeles wrote most of that controller. What was *yours*?"*
→ Fair, and I'll be precise rather than claim the whole thing. The DC controller was largely authored by Keshav and Ambiorix — I credit them. My real slice was elsewhere in the same effort: the **OpenAPI design-first process** and the codegen path for the items-assortment surface (the DC controller itself is hand-written; only items-assortment is generated via the Spring generator), the **multi-site CCM config** wiring (US/CA/MX as the same artifact per region + config, `SiteIdCCMConfig` etc. — there's no `*Factory` class, it's config-driven), and review/integration. So "led end-to-end" is collaborative; my owned contributions are the design-first/codegen process, the multi-site config, and the producer/Kafka path — not every line of the DC controller.

**L3.** *"So 'end-to-end' is an overstatement. Doesn't that undercut the whole resume?"*
→ It tightens it, it doesn't undercut it. The defensible version is "drove the design-first API process and multi-site config for the feature, and built the Kafka publish path, alongside Keshav and Ambiorix who owned the DC controller internals." That's still substantial ownership — and it's *credible*, because I can name what was mine and what wasn't. The candidate who claims every line gets caught on the first `git blame` question; the one who credits the team and owns a clear slice reads as more senior, not less.

**L4 (the floor).** *"Why should I believe you contributed anything real if you just handed credit to two other engineers?"*
→ Because I can defend my slice at the same depth I defend theirs. Ask me about the multi-site config: it's the same artifact deployed per region with CCM-driven `SiteIdCCMConfig`, **no factory class**, because the variation is data, not code paths. Ask me about the Kafka path: I can walk the IAC null-key / DSC-tripId asymmetry, the acks/idempotence config, the `.join()`/500 vs fire-and-forget/201 contract split — line by line. Owning a *real* slice deeply beats claiming a *whole* I can't defend. That depth on my own piece is the proof.

> **What they learned:** Under an attribution probe, do you collapse (over-claimed, can't defend) or hold (credit the team, own a real slice, defend it at depth)? This is the genre most likely to sink a strong-on-paper candidate.

---

## CHAIN 13 — "Your DSC returns 201 even when it lands nowhere." (the contract-asymmetry takedown)

**L1.** *"IAC and DSC are both NRTI publishes. Do they return the same thing on total failure?"*
→ No — and the asymmetry is the most interview-defensible "real smell" in the system. **IAC** `.join()`s the future and throws `NrtiUnavailableException` → **HTTP 500** if both regions fail (`NrtiUnavailableException` is `@ResponseStatus(INTERNAL_SERVER_ERROR)`, and the `@ExceptionHandler(NrtiUnavailableException.class)` in `NrtiRestExceptionHandler` is also `INTERNAL_SERVER_ERROR` — so the literal status is **500, not 503**; arguably it *should* be 503 + `Retry-After`). **DSC** is fire-and-forget — it returns **201 regardless**, even if both regions fail. `[NrtKafkaProducerServiceImpl.java:87-92 (IAC join → NrtiUnavailableException); NrtiUnavailableException.java:14 (@ResponseStatus INTERNAL_SERVER_ERROR); 102-133 (DSC no join, no throw)]`

**L2.** *"Show me exactly where DSC swallows the failure."*
→ The DSC primary send attaches `.exceptionally` that calls `handleFailure(...)` and returns `null` — no join, no rethrow. And the DSC `handleFailure` itself attaches another `.exceptionally` that only **logs** and returns `null`:
```java
// NrtKafkaProducerServiceImpl.java:121-126 (DSC primary) and 135-151 (DSC handleFailure)
.exceptionally(ex -> { log.warn("...trying in Secondary region"); handleFailure(...); return null; });
// handleFailure(DSC):
.exceptionally(ex -> { log.error("Unable to send message ... {}", ...); return null; });  // swallowed
```
Contrast the **IAC** `handleFailure`, which on secondary failure `throw`s a `CompletionException(new NrtiUnavailableException())` so the outer `.join()` propagates it to an HTTP 500. So IAC's secondary failure is *surfaced*; DSC's is *swallowed*. `[NrtKafkaProducerServiceImpl.java:135-151 (DSC, returns null) vs 159-175 (IAC, throws CompletionException)]`

**L3.** *"So a supplier of DSC events can get a 201 for an event that landed nowhere. Defend it or fix it."*
→ Defensible *only* as an explicit best-effort contract with a downstream reconciliation SLA — DSC is a freight notification, not an inventory mutation, so the design treats it as lossy-tolerant. But a **201 that means "accepted, maybe persisted"** is a lying status code if it isn't documented. The fix is to align DSC's error semantics: either surface failure like IAC (join + map both-region failure to a 5xx — IAC's is 500 today, ideally 503 + `Retry-After`), or keep it async but return **202 Accepted** and publish a reconciliation contract, so the supplier knows the durability guarantee. Returning 201 ("created") for something that may not exist is the part I'd change.

**L4 (the floor).** *"Was this asymmetry a decision or an accident?"*
→ The *direction* is a decision — IAC (system-of-record) must surface failure, DSC (notification) can be best-effort; that's defensible and matches the two-topic criticality split. But the *expression* of it — DSC returning 201 with a silently-swallowed secondary failure and no documented SLA — looks like an accident, because nothing says "this is intentionally best-effort." So: right instinct, under-specified contract. The senior fix is cheap — correct the status code, document the guarantee — and it converts a "lying 201" smell into a clear, intentional API contract.

> **What they learned:** Can you read the *exact* code paths where two siblings diverge (`throw CompletionException` vs `return null`), tell a deliberate trade-off from an under-specified one, and fix the contract rather than defend a misleading status code?

---

## The interviewer's scorecard (what they're secretly grading)

| Signal | Junior tell | Senior tell |
|---|---|---|
| Numbers | recites resume stat ("<5ms", "zero loss") | knows its boundary conditions and separates overhead from freshness |
| Failure | "it's reliable" | names the exact sequence + line (the unobserved future, the `noneMatch` catch-all) |
| Trade-offs | "we kept it simple" | adjudicates two principles with a requirement; knows the cost crossover |
| Ownership | "the backlog deprioritized it" | "that's partly on me; here's the PR" |
| Attribution | claims every line | credits the team, owns a real slice, defends it at depth |
| Depth | stops at the API | knows the thread, the proxy, the wire format, the config provenance |
| Honesty about code | asserts mechanisms that aren't there | labels `[SHIPPED]` vs `[NOT IN REPO — proposed]` unprompted |
| Sizing | invents a partition count | "that's KaaS — here's the formula and the value I'd request" |

**Your job in every chain: get to the floor answer voluntarily, before they have to drag you there.** The candidate who says level-5 honesty at level 2 — and who can tell you which line of code makes the claim true or false — is the one who gets the offer.

---

## Evidence Appendix — every load-bearing claim → file:line

| Claim | File:line |
|---|---|
| Audit producer: sync try/catch around async `send()`, no callback → silent loss | `audit-srv KafkaProducerService.java:44-52` (send at :47) |
| Audit producer sets NO acks/idempotence/retries → client default **acks=1** | `audit-srv KafkaProducerConfig.java:85-119` |
| Audit `kafkaSecondaryTemplate` is **dead code** (only primary used) | `KafkaProducerConfig.java:60-63` vs `KafkaProducerService.java:47` |
| Controller returns 204, hands to pool | `AuditLoggingController.java:58-60`; `LoggingRequestService.java:38` |
| audit-srv pool = **unbounded** `newCachedThreadPool` (OOM risk, no policy) | `ExecutorPoolService.java:10` |
| Audit partition key = `serviceName + "/" + endpoint` | `AuditKafkaPayloadKey.java:26-27`; set at `KafkaProducerService.java:89` |
| Audit producer key=String, value=Avro | `KafkaProducerConfig.java:89-90` |
| NRTI producer tuning (acks=all, retries=10, idempotence=false, lz4, batch=8192, linger=20, timeout=300000, maxReq=10MB) | `NrtKafkaProducerConfig.java:114-121`; values in `nrtKafkaConfig.json` |
| NRTI IAC = **null partition key** (MESSAGE_ID header only, no `KafkaHeaders.KEY`) | `IacServiceHelper.java:188-189` (TOPIC + MESSAGE_ID, no KEY) |
| NRTI DSC = keyed on `tripId` | `DscServiceHelper.java:264` (`KafkaHeaders.KEY`) |
| IAC `.join()` → `NrtiUnavailableException` → **HTTP 500** (`@ResponseStatus(INTERNAL_SERVER_ERROR)`, not 503); secondary throws `CompletionException` | `NrtKafkaProducerServiceImpl.java:87-92, 159-175`; `NrtiUnavailableException.java:14` |
| DSC fire-and-forget → 201; secondary failure swallowed (`return null`) | `NrtKafkaProducerServiceImpl.java:102-133, 135-151` |
| EI call = GET-with-body, WebClient `.timeout(10s)` + `Retry.backoff(3,100ms,max2s)` + `.block()` | `HttpServiceImpl.java:71-94` |
| Hibernate 6 enum fix `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` | `ParentCompanyMapping.java:127,135` |
| Canary: stepWeight 10 / maxWeight 50 / interval 2m / 5XX threshold 1% | `cp-nrti kitt.yml:726-746`; goldenSignal import `kitt.yml:14` |
| NRTI prod HPA min 6 / max 12 @ 60% CPU on `eus2-prod-a30, scus-prod-a63` | `cp-nrti kitt.yml:436,478-487` |
| Tomcat threads NOT overridden (only mbeanregistry) | `cp-nrti application.properties:7` |
| Common JAR `@Async` pool core6/max10/queue100, no RejectedExecutionHandler → AbortPolicy | `dv-api-common-libraries AuditLogAsyncConfig.java:17-26` |
| LoggingFilter javax.servlet, `@Order(LOWEST_PRECEDENCE)`, ContentCaching wrappers, enabledEndpoints allow-list | `LoggingFilter.java:15-17, 35-37, 83-89, 124-128` |
| Sink: 3 connectors (US/CA/MX), each `tasks.max:1`, errors.tolerance=all, RETRY max.retries 5, consumer.max.poll.records 50 | `kc_config.yaml:42,49,63,81,99 + per-connector blocks` |
| Base sink filter: `apply` returns null to drop, strict `anyMatch` | `BaseAuditLogSinkFilter.java:40-44, 52-56` |
| US sink filter: catch-all `noneMatch` (header missing → pass) = residency leak | `AuditLogSinkUSFilter.java:42-49` |
| Common JAR Spring Boot 2.7.11 / Java 11, in-repo 0.0.45, consumed 0.0.61 + webflux exclusion | `common pom.xml:7,17-18,30`; `cp-nrti pom.xml:470-474` |
| cp-nrti Spring Boot 3.5.14 / Java 17 / Jakarta | `cp-nrti pom.xml:7-8,26` |
| DC controller `POST /inventory/status` 200, hand-written; DC feature largely Keshav Gatla & Ambiorix Cruz Angeles | `DcInventoryController.java:104-151` |
