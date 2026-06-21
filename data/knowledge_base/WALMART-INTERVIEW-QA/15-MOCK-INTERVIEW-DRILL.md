# 15 — Mock Interview: Drill Sheet (Chained Follow-Ups + Ops/Capacity)

> **How to use this drill.** Cover the answer block. Read the question aloud, answer aloud through *every* level, **then** uncover. This is not a flashcard deck — each question is a **chain**: L1 → L2 → … → **FLOOR**. The interviewer keeps asking the next follow-up until you bluff or hit bottom. **Your job: reach the marked FLOOR answer *voluntarily*, by ~level 2, before they drag you there.** That voluntary descent is the single biggest senior signal (see the tell-detector at the end).
>
> **The spine of every answer (keep this rhythm):** **precise truth first → trade-off → the fix.** Concede the gap, name the exact mechanism (not a vague noun), then state how you'd close it.
>
> **Citation rule:** every technical claim below carries a real `file:line` / class / method anchor. If you can't cite the receipt, you don't actually know it — you stood next to it. Memorize the anchors, not just the shape.
>
> **The 4 trap words to pre-empt** (each chain labels which one it defuses): `starter → library`, `factory → config`, `zero-loss → at-least-once`, `3.2 → 3.5.x`.
>
> **Cross-reference map** (this sheet is a fast self-test; the long-form proofs live in the siblings):
> | Chain | Deeper proof |
> |---|---|
> | Durability / EOS | `18` Chain 3, `09` §4–5 |
> | `.join()` + 5-min timeout | `18` Chain 4, `16` concurrency, `09` §8.3 |
> | IAC null key / ordering | `09` §2, `17` Kafka internals |
> | Residency / geo-routing | `18` Chain 6, `17`, `09` §3 |
> | Migration ownership | `18` Chain 5, `04` bullet |
> | Framework internals | `18` Chain 7, `16` |
> | Ops / sizing (Q16–Q25) | `09` (the full ops doc) |

---

## PART 1 — The 15 chained hardest questions

### Q1. "You claim near-zero / zero data loss — show me the producer durability config." 〔defuses *zero-loss → at-least-once*〕

**The trap:** answering "acks=all, zero loss" flat, as if one config covers both systems. There are **two** producers with **opposite** durability postures.

- **L1 (truth, per-service):** "Different per service, and I'll be precise. The **audit** producer and the **NRTI** producer are tuned completely differently."
- **L2 (audit receipt):** "The audit producer sets **no** durability config at all. `KafkaProducerConfig.populateConfigProperties()` (`audit-api-logs-srv`, lines 87–92) puts only `BOOTSTRAP_SERVERS`, `KEY_SERIALIZER=StringSerializer`, `VALUE_SERIALIZER=KafkaAvroSerializer`, the schema-registry URL, and `auto.register.schemas=false`. It sets **no `acks` key**, so the Kafka **client default `acks=1`** applies — exactly `1`, not 'near' 1. A leader failure before replication loses that record."
- **L3 (the CCM nuance — say this unprompted, it's pure senior signal):** "There's a trap in the config too: the NON-PROD CCM yml *declares* `acks=all`, `retries=10`, `lz4`, etc., but the `AuditLogsKafkaCCMConfig` `@ManagedConfiguration` interface only exposes `brokerUrls/topic/schemaUrl/sslEnabled` — those tuning keys are **never read**, so they **do not take effect**. They represent intended tuning that still needs to be wired into the producer factory. PROD ccm doesn't even declare them."
- **L4 (NRTI receipt):** "The **NRTI inventory** producer *does* set durability: `acks=all` (`ccm.yml:172`), `retries=10` (`ccm.yml:192`), but `enable.idempotence=false` (`ccm.yml:197`). So it's **at-least-once**, not exactly-once. The honest claim is 'no observable loss of an *acknowledged* IAC event under single-region failure,' guaranteed by acks=all + RF3 + min.insync=2 to the surviving region — with consumer-side dedup on `messageId`."
- **FLOOR:** "So 'zero data loss' is true only as *no loss of an acknowledged event*, only on NRTI, and only assuming `min.insync.replicas=2` is provisioned (it's a KaaS topic property, not in my repo). The audit path is genuinely at acks=1 today and that's my #1 reliability gap — the fix is two lines: expose the CCM props and put them in `configProps`."

**Reflex:** name the two services separately; the audit default is *exactly* acks=1, and I have the file:line.
**Score 0–3:** 0 = "zero loss." 1 = splits the two but no receipt. 2 = cites `KafkaProducerConfig:87–92` + `ccm.yml:172/197`. 3 = also volunteers the CCM-declares-but-never-read nuance + the min.insync caveat.

---

### Q2. "Prove the end-to-end guarantee is not exactly-once — and walk me through a sequence where you lose ordering." 〔defuses *zero-loss → at-least-once*〕

**The trap:** waving at "at-least-once" without being able to (a) produce the concrete reorder sequence, or (b) explain *why* exactly-once is structurally impossible here.

- **L1:** "It can't be exactly-once. NRTI has `enable.idempotence=false` (`ccm.yml:197`); the audit sink (Kafka Connect) commits offsets *after* GCS delivery, so a crash mid-flush re-delivers a batch → duplicate Parquet rows. Both are at-least-once."
- **L2 (the reorder sequence — say it as a sequence, not a noun):** "With `enable.idempotence=false`, `retries=10`, and the default `max.in.flight.requests=5`: batch 1 fails and is being retried while batch 2 (sent after it) succeeds first → batch 2 now sits *before* batch 1 on the partition. Turning on `enable.idempotence=true` would pin order with a producer PID + per-partition sequence numbers and cap in-flight at 5 — at no throughput cost on a modern broker. That's why flipping it is my top recommended change."
- **L3 (the dedup contract + its failure mode):** "Dedup is **consumer-side** on a stable `messageId` — and `messageId` is **client-supplied**, so two distinct events with a colliding ID make the consumer wrongly drop a legitimate one. Mitigation: namespace the dedup key by `supplierId + messageId`, or generate it server-side. I also don't own the consumers, so dedup correctness is a *cross-team contract* I'd verify with an integration test, not assume."
- **FLOOR (why EOS is impossible *in this topology*):** "Even if I wanted end-to-end exactly-once, it's off the table: Kafka EOS (idempotent + transactional producer) is **per-cluster**. My active/active failover writes to **two independent clusters** — a transaction can't span them. So at-least-once + idempotent consumers is the only achievable pattern under dual-write. The alternative would be MirrorMaker2 with offset translation, which trades my sub-second failover for platform-managed replication. I chose app-level dual-write for failover speed and accepted the dedup contract as the cost."

**Reflex:** EOS is per-cluster; dual-write makes it structurally impossible. I can produce the reorder sequence on demand.
**Score 0–3:** 2 = reorder sequence + idempotence fix. 3 = also reaches the EOS-is-per-cluster floor and the client-supplied-messageId collision.

---

### Q3. "Walk me through the audit pipeline. … You said 204 immediately — what's the last thing that runs on the customer's thread?"

**The trap:** describing the happy path and missing that the customer is told "success" *before* the record is durable.

- **L1:** "Filter captures body → `@Async` POST to `audit-api-logs-srv` → controller returns **204** → Avro serialize → produce to Kafka → 3 Connect connectors filter by country → Parquet on GCS → BigQuery."
- **L2 (thread granularity):** "The 204 is returned by `AuditLoggingController.saveApiLog` (lines 58–60, `new ResponseEntity<>(HttpStatus.NO_CONTENT)`) *before* any Kafka work. The last thing on the customer's thread is `ExecutorPoolService.executeTaskInThreadPool(task)` — which is `pool.execute(task)` at `ExecutorPoolService.java:13` against `Executors.newCachedThreadPool()` (`:10`). The Avro serialize + `kafkaPrimaryTemplate.send()` run on a **pool** thread."
- **L3 (the consequence):** "So if the broker is down, the customer **still gets 204** — it's fire-and-forget. The audit record is lost; the send failure is only logged, there's no producer-side DLQ. That's the deliberate trade: audit must never affect the customer's call."
- **L4 (defend it):** "For our use case — supplier debugging convenience, a Splunk replacement — best-effort is acceptable; it's not the compliance system of record. But I'd close the blind spot: observe the send future, emit an `audit_publish_failed` metric, alert on rate, add a producer-side DLQ."
- **FLOOR (fast AND durable):** "If durability became the requirement, an outbox adds a DB write to every call — which kills the zero-latency point. The honest answer: write to a **local append-only WAL on the pod** synchronously (microseconds, no network) and have a separate shipper drain it to Kafka. Durable *and* off the customer's critical path. It's a CAP-style choice; today it's tuned for latency."

**Reflex:** 204 at `AuditLoggingController:58–60` precedes the produce; broker-down still returns 204.
**Score 0–3:** 2 = cites the 204 line + the pool submit. 3 = reaches the WAL/outbox fast-AND-durable floor.

---

### Q4. "The audit `send()` is async and the catch only logs — how do you know a broker publish failed?"

**The trap:** claiming the try/catch protects you. It doesn't — it's around the *submit*, on the wrong thread.

- **L1 (honest gap):** "Today I don't reliably. The send future is unobserved, there's no app-level DLQ, and the caller already has its 204."
- **L2 (the precise mechanism):** "Worse: the try/catch around an *async* `.send()` runs on the calling thread, so it only catches synchronous serialization/buffer-alloc errors. Broker-side failures and timeouts complete the future *later*, on an I/O thread, and slip past the catch entirely. It's a false sense of safety."
- **L3 (contrast that proves I know the right pattern):** "NRTI does it correctly — `NrtKafkaProducerServiceImpl` attaches `.thenAccept(...).exceptionally(...)` to the `CompletableFuture` (lines 76–89), so it actually observes the outcome. Audit just logs in a sync catch."
- **FLOOR:** "Fix: attach `whenComplete`/`addCallback` to the send future, emit a failure metric, route hard failures to a DLQ topic, and (separately) bound the pool so a backed-up broker can't spawn unbounded threads. Cheap, and it converts a silent-drop into an alert."

**Reflex:** the catch is around the submit on the calling thread — async broker failures land on the future, unobserved.
**Score 0–3:** 2 = explains why the catch misses async failures. 3 = contrasts with NRTI's `.exceptionally` and gives the callback+DLQ fix.

---

### Q5. "Show me the `spring.factories` / `AutoConfiguration.imports` that makes this a starter." 〔defuses *starter → library*〕

**The trap:** the word "starter" on the resume. There is no auto-configuration.

- **L1:** "There is none — there's no `src/main/resources` in `dv-api-common-libraries` at all, so no `spring.factories`, no `META-INF/spring/...AutoConfiguration.imports`. It's a shared **library**, not an auto-configured starter."
- **L2 (how it's actually wired):** "Consumers must `@ComponentScan com.walmart.dv.*` to pick up the `LoggingFilter`/services, and they must **provide their own `WebClient` bean** — the library doesn't define one. I lead with that caveat: 'starter' is loose résumé wording; the real win is reuse, not auto-config."
- **FLOOR:** "If I wanted it to be a true starter I'd add an `@AutoConfiguration` class behind `AutoConfiguration.imports`, gate it on `@ConditionalOnProperty`/`@ConditionalOnMissingBean`, and ship the `WebClient` and filter as opt-out beans — so a consumer gets it by dependency alone. That's a half-day of work and it's the honest difference between 'library' and 'starter.'"

**Reflex:** no `src/main/resources` → library, not starter; consumers `@ComponentScan` + supply WebClient.
**Score 0–3:** 2 = "library, no auto-config." 3 = states the exact files that would make it a real starter.

---

### Q6. "This JAR is SB 2.7.11 / Java 11 / `javax.servlet` but consumers are SB3 / Java 17 / `jakarta` — how does it load?"

**The trap:** hand-waving "it just works." Be precise about *why* the incompatible Filter doesn't blow up.

- **L1:** "It's the one cross-version outlier — the library is Spring Boot 2.7.11 / Java 11 with `javax.servlet` imports; everything that consumes it (`cp-nrti-apis`) is SB3 / Java 17 / `jakarta`."
- **L2 (the type-incompatibility floor — say this, it's the discriminator):** "A `javax.servlet.Filter` **cannot** load as a container filter in a jakarta servlet container — the types are flatly incompatible (`javax.servlet.Filter` ≠ `jakarta.servlet.Filter`). It works *only* because the consumer **never registers the JAR's filter** as a container filter. The consumer provides its own jakarta filters and uses the library's *non-servlet* pieces, while **excluding the JAR's `spring-boot-starter-webflux`** so the old reactive stack doesn't leak in and it can supply its own WebClient."
- **FLOOR:** "It's the most fragile compat surface in the system. The genuinely correct fix is a **jakarta-targeted rebuild** of the library (multi-release jar or a 3.x branch). I'd flag the current coexistence as tech debt I'd schedule, not pretend it's clean."

**Reflex:** incompatible Filter types; works only because the consumer doesn't register the JAR's filter and excludes the webflux starter.
**Score 0–3:** 2 = "excludes webflux, own WebClient." 3 = states the `javax.servlet.Filter ≠ jakarta.servlet.Filter` type incompatibility explicitly.

---

### Q7. "You copy all request headers into the audit payload with masking off — including `Authorization` / `WM_SEC.*` — isn't that a secret/PII leak?"

**The trap:** getting defensive. This is a real leak; volunteer it.

- **L1 (concede immediately):** "Yes, and I'll raise it proactively — it's a genuine security gap, not a feature."
- **L2 (mechanism):** "The capture path copies **every** request header into the audit payload, and CCM `mask.enable=false`, so `Authorization` and the `WM_SEC.*` signature headers go into Kafka → Parquet → BigQuery **unmasked**. Anyone with BigQuery read on the audit dataset can read live auth material."
- **FLOOR:** "Fix at **capture time**, not downstream: an allow-list of headers (or a deny-list for `Authorization`/`WM_SEC.*`/cookies) and `mask.enable=true` so secrets never enter the payload in the first place. Doing it at capture makes the safety a code property, not tribal config. I'd also rotate any keys that may have been exposed."

**Reflex:** mask off + copy-all-headers = unmasked secrets in BigQuery; fix at capture, allow-list.
**Score 0–3:** 2 = names the leak + mask.enable=false. 3 = fixes at capture time with allow-list + rotation.

---

### Q8 + Q9 (FUSED). "`request.timeout.ms` is 300000 (5 min) AND IAC does `.join()` on the Tomcat thread. Under a slow/black-hole primary at 10× load, what happens — and how is failover still 'fast'?"

> These two were separate shallow questions before; they're the **same failure mode** and the principal fuses them. This is the highest-signal chain in the whole NRTI story. 〔Little's Law takedown.〕

- **L1 (what thread):** "The `.join()` is at `NrtKafkaProducerServiceImpl:89` — it blocks the **Tomcat worker thread** handling the HTTP request until primary-or-secondary resolves."
- **L2 (the pool size):** "Tomcat default `server.tomcat.threads.max=200`."
- **L3 (do the math):** "Little's Law: concurrent threads = arrival rate × service time. At 300 req/s with the primary taking 2s/send, I need 300 × 2 = **600 threads**, but I have 200 → the pool saturates, requests queue, then time out → **cascading 503s**. HTTP availability is now coupled to Kafka latency."
- **L4 (the fused insight — the real bug):** "And `request.timeout.ms=300000` (`ccm.yml:187`) means a **black-hole** primary (hung socket, not connection-refused) holds each thread up to **5 minutes** before the future completes exceptionally and failover even fires. So failover speed is bounded by `request.timeout.ms`, **not** by my `.exceptionally` at line 84. The service falls over long before failover triggers. A *fast* failure (connection refused, no brokers) is caught instantly by the synchronous `try { kafkaPrimaryTemplate.send() } catch` at lines 69–73 — sub-second. It's only the slow/black-hole case that's deadly, which is why we didn't catch it: it needs a partial network fault we didn't game-day."
- **FLOOR:** "Three fixes: (1) `future.orTimeout(2, SECONDS)` to bound failover **regardless of failure mode**; (2) a Resilience4j **circuit breaker** so a sick primary trips fast instead of per-request 5-min timeouts — and when it's open, events go straight to the secondary region (the breaker's fallback is my existing `handleFailure` secondary-send path at `NrtKafkaProducerServiceImpl:159–175`); if both are open, fail fast 503; (3) a **bulkhead** (separate bounded pool for publishing) so Kafka latency can't consume the servlet pool. The breaker turns a slow cascading failure into a fast clean one. The same `.block()` thread-occupancy risk exists on the EI WebClient read (`.timeout(10s)` + `Retry.backoff(3,100ms,max2s)` + `.block()`) — ~`200/10 = 20` concurrent EI-bound requests before the pool fills."

**Reflex:** `.join()` at `:89` is on the Tomcat thread; failover is bounded by `request.timeout.ms=300000`, not `.exceptionally`. 300×2s=600>200 → cascade.
**Score 0–3:** 1 = "it blocks a thread." 2 = does the 600-vs-200 math. 3 = reaches "failover is bounded by the 5-min timeout, not `.exceptionally`" + the orTimeout/circuit-breaker/bulkhead floor.

---

### Q10. "DSC returns HTTP 201 even when both regions fail and the event is dropped — defend or admit."

**The trap:** defending a misleading status code.

- **L1 (admit):** "I admit it — it's a genuine inconsistency versus IAC's block-and-fail."
- **L2 (mechanism, contrast with IAC):** "DSC's `publishDscKafkaMessage` (`NrtKafkaProducerServiceImpl:104–133`) attaches `.thenAccept(...).exceptionally(... handleFailure ...)` but **never `.join()`s** — it's fire-and-forget. The service catch swallows the exception and the controller returns **201 unconditionally**. IAC, by contrast, `.join()`s at `:89` and throws `NrtiUnavailableException` → HTTP 500 on total failure (OpenAPI annotates 503 — a doc/behavior mismatch I'd fix to the retryable 503)."
- **FLOOR:** "As best-effort freight telemetry the fire-and-forget is tolerable, but the **201 is the lie** — it claims durability we didn't achieve. Fix without breaking the 201 latency SLA: a transactional **outbox** — persist a failed DSC to the existing Postgres (15-conn Hikari pool is already there) and relay it in the background — plus a failure metric + DLQ. Then 201 means 'durably accepted,' which is honest."

**Reflex:** DSC has no `.join()` (104–133) → 201 regardless; IAC `.join()`s at :89 → 500. The 201 is the smell.
**Score 0–3:** 2 = names the no-`.join()` asymmetry. 3 = the outbox fix that keeps the 201 honest.

---

### Q11. "Your resume says Spring Boot 3.2 but the pom shows 3.5.14 / BOM 3.5.7 — which is it?" 〔defuses *3.2 → 3.5.x*〕

- **L1 (correct up front):** "Correction first: I led the 2.7→3.x major jump and we stayed **current to 3.5.x**. The résumé '3.2' is stale wording."
- **L2 (parent vs BOM, which wins):** "The `spring-boot-starter-parent` is `3.5.14`; the `spring-boot-dependencies` BOM is `3.5.7`. For effective transitive versions the **BOM wins** — it's the managed dependency baseline. I state both numbers confidently rather than dodging the discrepancy."
- **FLOOR:** "The concrete things the jump changed in *my* code: `ListenableFuture → CompletableFuture` in Spring Kafka (which reshaped the failover code I showed you), Hibernate 6 strict typing on enums, `javax → jakarta`. It was a real migration, not a version bump I watched."

**Reflex:** lead with the correction; BOM (3.5.7) governs effective versions.
**Score 0–3:** 2 = corrects to 3.5.x + BOM-wins. 3 = ties it to specific code changes (Kafka future type, Hibernate enum).

---

### Q12. "Show me your `SecurityFilterChain` / `WebSecurityConfigurerAdapter → SecurityFilterChain` migration." 〔trap: assumes Spring Security exists〕

- **L1 (defuse the trap):** "There's **no Spring Security in the repo** — zero matches. So there was no Security 5→6 migration to do here, and I won't claim one."
- **L2 (what auth actually is):** "Auth is **gateway-side** via `WM_SEC.*` signature headers, plus custom **servlet filters** in `cp-nrti-apis` — `RequestFilter`, `XssFilter`, `NrtCorsFilter` — not `SecurityFilterChain` beans. Tenant scoping is an AOP `SiteIdFilterAspect` toggling a Hibernate filter, driven by `SiteIdCCMConfig`."
- **FLOOR:** "If we *did* adopt Spring Security I'd put the WM_SEC verification in a `OncePerRequestFilter` registered in a `SecurityFilterChain` bean and keep the gateway as the first line — but that's a design I'd propose, not something I did. Prior prep notes that claim a Security migration are wrong for this codebase."

**Reflex:** no Spring Security in repo; auth = gateway WM_SEC.* + custom servlet filters.
**Score 0–3:** 2 = "no Spring Security, gateway + filters." 3 = names the three filters + SiteIdFilterAspect.

---

### Q13. "Your Flagger gate is 5xx-only — what regression slips past it, and how was the worst migration bug actually caught?"

- **L1:** "Semantic **'wrong-200'** bugs and **latency** regressions slip past — the gate is a PromQL 5xx-rate over Envoy with threshold **1%** (`kitt.yml`), stepWeight 10 → maxWeight 50 → promote 100. A bug that returns a *200 with wrong data* never trips it."
- **L2 (the concrete bug + why the canary was blind):** "A **Hibernate 6 enum mapping** bug did exactly that: under Hibernate 5 the enum persisted/read fine; Hibernate 6's strict type system mapped it differently and reads came back **wrong — a wrong-200, not an exception**. Fixed with `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` on the mapping. The 5xx canary would have happily promoted it to 100%."
- **L3 (what actually caught it):** "It was caught in **stage** by **R2C contract tests** comparing response bodies (threshold 80, Active) plus Automaton perf — *before* canary. That's why I credit the staged soak + contract tests, not the canary, for 'zero customer impact.'"
- **FLOOR:** "The layers are complementary: the canary protects against infra/availability regressions on real prod traffic that stage can't replicate; correctness is a test-pyramid job caught earlier. I'd still **add latency + error-content SLOs** to the canary gate so it isn't purely 5xx-blind."

**Reflex:** 5xx gate is blind to wrong-200 + latency; the enum bug was caught in stage by R2C, not the canary.
**Score 0–3:** 2 = names wrong-200 + R2C catch. 3 = ties it to `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` and the complementary-layers reasoning.

---

### Q14. "Show me the factory class for US/CA/MX." 〔defuses *factory → config*〕

- **L1 (defuse):** "There is no `*Factory` — `grep factory` returns only framework factories (`DefaultKafkaProducerFactory`, MapStruct `Mappers.getMapper`, Spring `beans.factory`). 'Factory' on the résumé is loose wording."
- **L2 (what multi-site actually is):** "Multi-site is the **same artifact deployed per region** with region-specific **CCM** config — `SiteIdCCMConfig` (the `wm-site-id`), `EiApiCCMConfig` (country code) — and an AOP `SiteIdFilterAspect`, plus a `*-INTL` companion in `sr.yaml`. It's config + DI variant selection at deploy time, not a runtime GoF factory."
- **FLOOR:** "If we needed *runtime* multi-tenancy in a single deployment, a real factory would be a **site-keyed strategy/client registry** selecting per-region EI clients/config in one process. That's the consolidation I'd build; today it's per-region deploy because that's all the requirement needed."

**Reflex:** no `*Factory`; multi-site = per-region deploy + CCM (SiteIdCCMConfig/EiApiCCMConfig) + SiteIdFilterAspect.
**Score 0–3:** 2 = "config + per-region deploy, no factory." 3 = describes the real site-keyed registry you'd build.

---

### Q15. "If it's design-first with codegen, show me the generated DC controller."

- **L1 (precise scope of codegen):** "Only the **items-assortment** endpoint is codegen'd via the **`spring` generator**. The DC and store controllers are **hand-written** — `DcInventoryController.getDcInventory` → `POST /dc/inventory/status` → HTTP **200** (it's a read). The `openapi` generator on the project merely *bundles* the spec; it doesn't generate the DC server."
- **L2 (so what is design-first):** "Design-first here is a **process**: we locked the OpenAPI contract so consumers built against generated clients/mocks **in parallel** — that's where the ~30% critical-path compression estimate comes from — backed by **R2C contract tests** for DC, not server codegen."
- **FLOOR:** "I'm careful not to over-credit codegen: the published `api-spec.yaml` even drifted (plural `/stores`, no `/dc`); the maintained source is `openapi.json`. That drift is exactly why the contract-test discipline matters more than the generator. The 30% is an engineering estimate, not an instrumented A/B."

**Reflex:** `spring` generator only for items-assortment; DcInventoryController is hand-written, POST /dc/inventory/status → 200.
**Score 0–3:** 2 = "DC hand-written, only items-assortment codegen'd." 3 = adds the spec-drift + 30%-is-an-estimate honesty.

---

## PART 2 — Framework-internals sniper round (instant-depth, no chain)

> Single shots. They reveal in one answer whether you built it or stood next to it. Say it cold.

1. **"Your `@Async` bean — JDK proxy or CGLIB, and how would I tell?"** → CGLIB (Spring Boot `proxyTargetClass=true`); check `bean.getClass().getName()` for `$$EnhancerBySpringCGLIB` / `$$SpringCGLIB`.
2. **"Mark the `@Async` method `final`. What happens?"** → CGLIB can't override a final method → advice doesn't apply → it runs **synchronously**, silently, no error.
3. **"Call your `@Async` method from another method in the same class — async?"** → No. Self-invocation bypasses the proxy → runs on the caller thread.
4. **"`ThreadPoolTaskExecutor` core 6 / max 10 / queue 100 (the common-lib audit pool) — when does thread #7 get created?"** → Only **after the queue (100) is full**. Order is **core → queue → max → reject**. Most people say core → max → queue (wrong).
5. **"That pool's rejection policy?"** → Default **AbortPolicy** → throws `RejectedExecutionException` → the audit event is **silently dropped** under saturation (the *second* drop surface, distinct from the producer's unbounded `newCachedThreadPool`).
6. **"`acks=all` — all of what?"** → All **in-sync replicas** (gated by `min.insync.replicas`), **not** all replicas. If ISR shrinks below min.insync the producer gets an error instead of a false ack — that's the durability point.
7. **"`enable.idempotence=true` — what does the broker do differently?"** → Producer gets a **PID** + per-partition **sequence numbers**; broker rejects duplicates and out-of-order sequences, dedups retries, pins order, caps in-flight at 5.
8. **"Your filter is `OncePerRequestFilter` — when would a plain Filter run twice?"** → On internal forwards/includes and async dispatches the request re-enters the chain; the base class uses a request-attribute flag to dedupe so audit isn't double-recorded.
9. **"Why a Filter, not a `HandlerInterceptor`, for body capture?"** → Only a Filter sees the raw servlet request early enough to wrap it in `ContentCachingRequestWrapper`; the body stream is **read-once** and an interceptor runs after it's already consumed.
10. **"Avro value, String key — why isn't the key Avro too?"** → The key (`service/endpoint`) is a routing/partitioning token needing **determinism**, not schema evolution. Avro on the key adds registry overhead for no benefit.

---

## PART 3 — Ops & capacity drills (sizing-by-formula discipline)

> The recurring move here: for anything in **my code** I quote `file:line`; for **KaaS-provisioned** topic properties (partitions, RF, min.insync, retention) I say *"not in my repo — here's the value I'd request and the formula,"* and I **never invent the provisioned number.** All anchors below trace to doc `09`.

### Q16. "What's the partition key for each topic — show me, including the inventory-action events."

**The trap (the sharpest single gotcha in NRTI):** assuming IAC keys on `messageId`. It doesn't — IAC has a **null partition key**.

- "**Audit:** `serviceName + "/" + endpoint` — `AuditKafkaPayloadKey.getKafkaKey()` returns `getServiceName() + FORWARD_SLASH + getEndpoint()`, set on `KafkaHeaders.KEY` in `KafkaProducerService`. Per-(service,endpoint) ordering; mirrors KCQL `PARTITIONBY service_name, endpoint_name`."
- "**DSC:** `tripId` (`vendorId_deliveryDate_storeNbr_minPackNbr`), set on `KafkaHeaders.KEY` in `DscServiceHelper`. Per-trip ordering."
- "**IAC: NULL key.** `IacServiceHelper.prepareIacActionKafkaMessage` (lines 182–212) sets `KafkaHeaders.TOPIC` (`:188`) and a `MESSAGE_ID` **header** (`:189`) — but **never** `KafkaHeaders.KEY`. So the default sticky partitioner spreads IAC across partitions → **no broker-level ordering**. `messageId` is a dedup token, not the partition key."
- **FLOOR:** "That's a real finding I'd flag and fix: set `KafkaHeaders.KEY = storeNbr` (or store+item composite) so same-store actions co-partition and order. Until then the honest statement is 'IAC is at-least-once *with no ordering*; consumers must be order-independent and idempotent.'"

**Reflex:** IAC sets MESSAGE_ID header at `IacServiceHelper:189`, no `KafkaHeaders.KEY` → null key → no ordering. DSC keys tripId.

### Q17. "How many topics, and why that many?"

- "**Audit: 1** business topic `api_logs_audit_prod` + **1 DLQ** (`PROD-1.0-ccm.yml:41`). One homogeneous event type — one Avro `LogEvent`, one ingest API. Topic-per-service would multiply partitions/RF/offset metadata by N for zero schema benefit; topic-per-region is unnecessary because geo is a **sink** concern."
- "**NRTI: 2** — `cperf-nrt-prod-iac` + `cperf-nrt-prod-dsc` (`ccm.yml:132/202`). Split by **opposite criticality**: IAC is a system-of-record inventory mutation (sync-with-failover, caller-visible failure); DSC is best-effort freight (fire-and-forget). One topic would force one policy on two opposite SLAs."

### Q18. "How many partitions for the audit topic — and how did you decide?"

- **FLOOR (formula, not a number):** "**Not in my repo — KaaS-provisioned**; my config carries only the topic *name*. Throughput needs ~1 (23 eps avg). The formula: `partitions = max(ceil(target_peak_eps / per_partition_ceiling), desired_consumer_parallelism)`. Throughput is never binding here — even 10 KB/event at 230 eps is ~2.3 MB/s, well under one partition. So I'd **request 6**, driven by (1) future consumer parallelism (a group can't exceed partition count), (2) even broker spread (2 leaders/broker on 3 brokers), (3) headroom — because **repartitioning a keyed topic reshuffles key→partition and breaks ordering**. I won't fabricate the provisioned value."

### Q19. "Replication factor and `min.insync.replicas`?"

- **FLOOR:** "**Both KaaS topic properties, not in my repo.** Each region's bootstrap list shows **3 broker hostnames**, so RF is almost certainly **3** — and RF=3 is the only defensible choice for an audit-of-record + financial inventory feed (survives one broker loss with quorum). I'd pair it with **`min.insync.replicas=2`**: with RF=3 a write needs 2 of 3 in-sync → durable through one broker outage, still writable. min.insync=3 blocks writes on any single broker loss (too brittle); min.insync=1 defeats acks=all. Note: min.insync only *matters* on NRTI today, because audit runs at acks=1 — moot there until acks=all is wired."

### Q20. "Retention — and size the disk."

- **FLOOR:** "**KaaS topic config, not in repo.** I'd request **3–7 days**. Kafka is a transient buffer; the source of truth is GCS Parquet + BigQuery (sink lands data within ~10 min via `flush.interval=600`). Sizing: `disk = eps × avg_msg_size × retention_sec × RF`. Audit at 23 eps, 500B, 3 days, RF3 = `23 × 500 × 259200 × 3 ≈ 8.6 GB` — tiny. 7 days lets me replay a full week; longer buys little because reprocessing reads from GCS, not Kafka. For NRTI I'd size to the worst plausible Enterprise-Inventory outage window + replay margin; if indefinite replay were needed I'd argue for **log compaction** keyed on tripId/messageId instead of time retention."

### Q21. "How many consumers read the audit topic, and what's the read amplification?"

- "**Three.** The sink is **Kafka Connect** (Lenses `GCPStorageSinkConnector`), **not** Spring — three connector instances on the same topic: US (the permissive **catch-all**, incl. header-less), CA strict, MX strict, each `tasks.max=1` → **3 tasks = 3 consumers**. Each connector is its own consumer group → the topic is read **3× (3× read amplification)**, by design."
- **FLOOR:** "Justified by per-country isolation: independent offsets, lag, RETRY, failure domains — a bad CA filter or CA-side GCS outage can't stall US/MX, and the Lenses sink can't cleanly fan one record to 3 buckets+datasets in one task. At ~70 eps fetch the bandwidth is nothing vs the isolation. I'd revisit a single demuxing connector only at ~10× volume."

### Q22. "How did you pick `tasks.max = 1`?"

- "`tasks.max = min(partitions, desired_parallelism)`. At 23 eps avg / ~230 peak one task drains the topic with huge headroom — `max.poll.records=50` polled many times/sec, work is a cheap SMT filter + batched Parquet write. One task = single-threaded, in-order, simple offsets. **Ceiling:** one task owns all partitions, so raising partitions later requires raising `tasks.max` **together** — never beyond partition count (extra tasks sit idle). Scale path is lag-driven, not reflexive."

### Q23. "Throughput math — events/day to disk, and the GCS file-count."

- "**EPS:** ~2M events/day ÷ 86,400 = **~23 eps avg**; design for **~100–230 eps peak** (5–10× business-hours concentration). **Bytes:** ~500B–2KB Avro → ~11.5 KB/s avg. **GCS flush:** `STOREAS PARQUET`, `flush.size=50MB / flush.count=5000 / flush.interval=600s` — whichever fires first. At our volume no country/region hits 50MB or 5000 records in 10 min, so the **600s timer dominates** → `86400/600 = 144` objects/day/country/region, ~864/day total. That timer is what caps object count and keeps each Parquet file MB-sized — avoiding the **small-file problem** (tiny files inflate GCS listing + BigQuery scan cost). Trade = up to 10-min freshness lag, which is *why* the resume '<5ms' is API-overhead, not audit freshness."

### Q24. "Size the HPA — and why is CPU the wrong signal for NRTI?"

- "**Audit-srv prod:** min **4** / max **8** @ 60% CPU (`kitt.yml` 409–418). **NRTI prod:** the committed `kitt.yml` is **min 6 / max 12** (478–487 / iacprod 586–595) — the min4/max8 profile is **stage**; I state that honestly. **Why min 4–6:** 2-region × 2-pod redundancy so a region/AZ drain still serves baseline. **Why 60%:** 40% headroom to absorb a burst during the ~30–60s a new pod takes to become ready."
- **FLOOR:** "CPU is the **wrong** primary signal for NRTI because its threads sit **blocked** on `.join()`/`.block()`, not burning CPU — so an unbounded `newCachedThreadPool` blowup is *invisible* to a CPU HPA. Better signals: Tomcat thread-pool utilization, in-flight request count, or RPS via KEDA/custom metric, with CPU as a backstop. We already export `tomcat_sessions_*`, `jvm_threads_*`, and `hikaricp_connections_*`. That's also why NRTI's min was doubled vs audit — blocked threads need more pods than pure CPU math suggests."

### Q25. "Consumer lag alerting and rebalancing — what's wired, and what breaks on a deploy?"

- "**Lag alerts** (`kafka-consumer-lag-alerts.yaml`): warn `lenses_topic_consumer_lag > 100` for 5m, critical `> 500` for 5m. At 230 eps, lag 100 ≈ <0.5s behind — early-warning. **Page on critical** (stuck sink → BigQuery freshness SLA at risk). Known cleanup: the alert *message text* says 50/100 but the *expr* says 100/500 — a real text/expr mismatch I'd fix."
- "**Rebalancing:** `partition.assignment.strategy` is commented out → Connect default `[RangeAssignor, CooperativeStickyAssignor]` → negotiates to **cooperative (incremental)** — so restarting/deploying a worker doesn't stop-the-world revoke all 3 country sinks at once. With `tasks.max=1` per connector, rebalances are rare (only worker restart/deploy)."
- **FLOOR:** "The Connect sink is deliberately **not HPA'd** — autoscaling would trigger rebalances that disrupt all sinks. You scale it by `tasks.max` + worker count on purpose. The 7g heap (`-Xmx7g`) is sized for Parquet buffering (3 connectors each buffering up to 50MB + Avro decode); single-worker-per-region is mitigated by active/active (effectively 2 workers, each draining its own region)."

---

## Scoring rubric (score per chain-depth, not per question)

| Score (per chain) | Meaning |
|---|---|
| **3** | Reached the marked **FLOOR** answer *voluntarily* by ~L2, with at least one `file:line` receipt. Senior. |
| **2** | Right shape + correct mechanism, but had to be pushed to the floor, or missing the citation. |
| **1** | Right direction, vague nouns ("we made it reliable"), no receipt. |
| **0** | Missed the trap / overclaimed (e.g. "zero loss," "it's a starter," "we migrated Spring Security"). |

**Pass bar:** average **≥ 2.5** across all 25, **and zero 0s** on Q1/Q2/Q8+9/Q16 (the durability + concurrency + null-key chains where overclaiming is fatal). Re-drill any chain you can't take to its floor without prompting; then re-read its cross-referenced sibling.

## The tell-detector (what they're secretly grading)

| Signal | Junior tell | Senior tell (what you must show) |
|---|---|---|
| Numbers | recites résumé stat ("<5ms", "zero loss") | knows its boundary conditions ("<5ms is API overhead; freshness is ~10 min, `flush.interval=600`") |
| Failure | "it's reliable" | names the exact sequence ("300 req/s × 2s = 600 threads > 200 → cascade") |
| Config | "we configured it for durability" | "`acks=all` `ccm.yml:172`; audit defaults acks=1 because `KafkaProducerConfig:87–92` sets none" |
| Trade-offs | "we kept it simple" | adjudicates two principles with a requirement (one-topic vs per-country: residency-is-legal wins) |
| Ownership | "the backlog deprioritized it" | "that's partly on me — here's the half-day PR" |
| Depth | stops at the API | knows the thread, the proxy, the wire format, the `file:line` |
| Honesty | defends every claim | volunteers the gap before it's found |

---

## The 5 reflexes to internalize (the spine of every floor answer)

1. **Two Kafka worlds — never conflate them.** Audit = Avro + Schema Registry (`auto.register.schemas=false`), acks=1 default, key `service/endpoint`, geo in the **sink**. NRTI = JSON, **no Schema Registry**, acks=all + idempotence=false, IAC **null key** / DSC tripId, failover in code.
2. **Failover lives in `cp-nrti-apis` (`NrtKafkaProducerServiceImpl`), not audit-srv.** Audit's `kafkaSecondaryTemplate` is **dead code** — built and autowired, never called. Never attribute failover to audit-srv.
3. **Pre-empt the 4 trap words with a receipt:** `starter → library` (no `src/main/resources`), `factory → config` (per-region deploy + CCM), `zero-loss → at-least-once` (idempotence=false; EOS is per-cluster), `3.2 → 3.5.x` (BOM 3.5.7 governs).
4. **Sizing-by-formula, never a fabricated number.** Partitions/RF/min.insync/retention are KaaS-provisioned and *not in the repo* — quote the formula and the value I'd request; quote `file:line` only for what's actually in my code.
5. **Every gap ends with a fix, and ownership ends with a PR.** What keeps me up at night: the silent-drop audit path — unbounded `newCachedThreadPool` (`ExecutorPoolService:10`) in the producer + the `@Async` AbortPolicy pool (core6/max10/queue100) in the common JAR, with send failures only logged. It's never failed in prod, so it stayed below the line — that's partly on me; the fix is a half-day PR (bound the pool + `RejectedExecutionHandler` + an `audit_publish_failed` metric). Credit where due: the DC inventory feature was largely authored with **Keshav Gatla** & **Ambiorix Cruz Angeles**, the common-JAR pom by **Nayana.BG** — own my real contribution, credit the team.
