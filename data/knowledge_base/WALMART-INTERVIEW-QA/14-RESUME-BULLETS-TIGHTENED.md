# 14 — Resume Bullets, Tightened to Survive the Watch-Outs

> **Purpose:** Rewrites of the 5 Walmart bullets that keep the impact and keywords but remove the claims the code can't back — and, unlike a cheat-sheet, each rewrite now ships with the *exact* file/class/method/config receipt that makes every clause true, the wart the repo will reveal, a 2-3 turn spoken micro-script, and an honest attribution clause. This is the one-pager that stays in lockstep with the 300-line bullet deep-dives.
>
> **Principle:** Keep every number you can defend, soften every number you can't, never write a word you'd have to retract under "show me the code," and *cite the code yourself before they open it.*
>
> **How to use each block:** Pick variant **(B) Balanced** for the resume by default. Have **(A) Safe** ready if the panel is adversarial / very senior, and **(C) Impact-forward** for a recruiter screen or a non-engineering reader. The "Cite if challenged" and "Repo will show ___" rows are your armor — read them before any round.

---

## 0. Soft-number ledger (tape this to your monitor)

Every soft figure in these bullets, what it actually means, and the one-line guard so you never overclaim:

| Soft figure | What it really is | Source / guard |
|---|---|---|
| **<5ms P99** | **Overhead added to the audited API** on the hot path — NOT audit freshness. | Two async hops: Tier-1 `@Async` (`AuditLogAsyncConfig` 6/10/100) + Tier-2 HTTP-204-then-`newCachedThreadPool`. Freshness is *minutes* (`flush.interval=600s`). Never fuse the two latencies in one sentence. |
| **millions of events/day** | ~23 msg/s average (2M/day). It is **volume/day, not throughput/sec.** | Don't conflate with "high throughput." **Do NOT import the GCC `10M+` number** — that's a different project (doc 13 number-mismatch). Walmart audit = "millions/day." |
| **15-min DR recovery** | **Operational** RTO from a DR game-day, not the code path. | Not in any repo; the *code* failover is sub-second/per-message. Label it "operational, from DR game-days." The "1-hour" is the *old manual runbook* baseline. |
| **zero data loss** | At-least-once with consumer dedup. | NRTI: `enable.idempotence=false` (`ccm.yml` line 197) → reframe to "no observable loss of an **acknowledged** event under single-region failure." Audit: effective `acks=1` → can't claim loss-free at all. |
| **RF3** | **Inferred**, not committed config. | Each region shows 3 brokers ⇒ RF *almost certainly* 3; `replication.factor` is provisioned via KaaS and is **not in any repo**. Annotate as inferred or drop it from the line. |
| **2 weeks → 1 day** / **30% faster** | Engineering estimates, not instrumented. | Frame as "an adoption/critical-path estimate." Defensible because the genuinely hard part (stream-reuse, async, signing / consumer-build overlap) is now solved once. |

---

## 0a. Two Kafka worlds — never mix them under pressure

These two systems share zero config DNA. Cross-wiring them is the fastest way to lose credibility:

| | **Audit pipeline** (`audit-api-logs-srv` + `-gcs-sink`) | **NRTI publisher** (`cp-nrti-apis`) |
|---|---|---|
| Serialization | **Avro** + Confluent Schema Registry, `auto.register.schemas=false` | **JSON** (Spring `JsonSerializer`), **no** registry |
| Partition key | `serviceName + "/" + endpoint` (`AuditKafkaPayloadKey.getKafkaKey`) | IAC = **NULL key** (only a `MESSAGE_ID` *header* via `setHeader`); DSC = `tripId` |
| Durability | Producer sets **no** acks/idempotence/retries ⇒ **effective `acks=1`** | `acks=all`, `retries=10`, **`enable.idempotence=false`** ⇒ at-least-once |
| Failover | `kafkaSecondaryTemplate` bean exists but is **DEAD CODE** (never sent) | Real `CompletableFuture.exceptionally → secondary.send` (4 templates) |
| Topics | `api_logs_audit_{env}` (+ `_DLQ`) | `cperf-nrt-{env}-iac`, `cperf-nrt-{env}-dsc` |

---

## Bullet 1 — Audit Logging

❌ **Current:** "Designed a three-tier Kafka-based audit logging system with <5ms P99 latency impact processing millions of daily events, Avro serialization, SMT-based geographic routing (US/CA/MX), and GCS Parquet/BigQuery storage, enabling supplier self-service API debugging and eliminating Splunk dependency."

**Three rewrite variants** (each ≤2 lines):

**(A) Safe / bulletproof**
> "Designed a three-tier **asynchronous** Kafka audit pipeline (servlet-filter capture → fire-and-forget Avro producer → Kafka Connect GCS sink) that adds **<5ms P99 overhead** to audited APIs at **millions of events/day**; SMT-based geo-routing (US/CA/MX) writes Parquet to per-country GCS buckets with BigQuery self-service, **replacing Splunk** for supplier API debugging."
> *Why it survives:* "system"→"pipeline"; "latency impact"→"**overhead to audited APIs**" (kills the freshness conflation); keeps every clause that is literally in code. Drops nothing impressive, adds nothing unprovable.

**(B) Balanced — RECOMMENDED**
> "Designed a three-tier async Kafka audit pipeline (**`@Async` servlet-filter capture → HTTP-204 fire-and-forget Avro producer → Kafka Connect Lenses GCS sink**) adding **<5ms P99 overhead** to audited APIs at millions of events/day; **per-country SMT geo-routing (US/CA/MX)** lands Parquet in per-region GCS buckets queried by BigQuery, **replacing Splunk** with supplier self-service."
> *Why it survives:* names the real mechanisms (Lenses Connect sink, HTTP-204) that signal depth and are all code-true; still single-line-readable. Best mix of impact + defensibility.

**(C) Impact-forward**
> "Built Walmart's supplier API audit platform — an async three-tier Kafka pipeline (capture → Avro produce → GCS Parquet sink) at millions of events/day with **<5ms overhead** and data-resident US/CA/MX routing — **eliminating a costly Splunk dependency** with self-service BigQuery debugging."
> *Why it survives:* leads with outcome for a non-engineer reader; still labels "overhead" not "latency," still "millions/day" not "/sec." Softest on mechanism, so pair it with the spoken script the moment an engineer probes.

**Cite if challenged (the receipts):**
- `<5ms = overhead, two async hops`: Tier-1 `dv-api-common-libraries/.../services/AuditLogService.sendAuditLogRequest` is `@Async` on `AuditLogAsyncConfig` (core 6 / max 10 / queue 100, `AbortPolicy`); Tier-2 `controllers/AuditLoggingController.saveApiLog` returns **204** *before* any Kafka work, then `services/ExecutorPoolService` runs the send on `Executors.newCachedThreadPool()` (**unbounded** — the real <5ms lever *and* the OOM risk).
- `Avro + governed schema`: `kafka/KafkaProducerConfig` sets key=`StringSerializer`, value=`KafkaAvroSerializer`, `schema.registry.url`, `auto.register.schemas=false`. Key = `AuditKafkaPayloadKey.getKafkaKey()` = `serviceName + "/" + endpoint`; routing rides the **`wm-site-id` header**, not the key.
- `freshness = minutes`: sink KCQL `STOREAS PARQUET` with `flush.size=50MB / flush.count=5000 / flush.interval=600s`, `PARTITIONBY service_name,_header.date,endpoint_name` → GCS `audit-api-logs-{us|ca|mx}-prod` (project `wmt-dv-luminate-prod`), BigQuery external tables.
- `SMT routing`: 3 Lenses `GCPStorageSinkConnector` instances (`tasks.max=1` each), SMT chain `InsertRollingRecordTimestampHeaders` (yyyy-MM-dd, GMT) then `BaseAuditLogSinkFilter.apply` (`verifyHeader(wm-site-id) ? record : null`); US filter is the permissive catch-all (incl. header-less), CA/MX strict.

**Repo will show ___ (pre-empt it):**
- **Effective `acks=1`** — `KafkaProducerConfig.populateConfigProperties` never sets `acks`/`idempotence`/`retries` (a CCM yml may *declare* `acks` but the `@ManagedConfiguration` interface never *reads* it). So **never say "zero data loss" here.**
- **Unbounded `newCachedThreadPool()`** — no queue cap, no rejection → OOM risk under burst. It is *both* the <5ms mechanism and a stability liability.
- **`kafkaSecondaryTemplate` is dead code** — built and autowired but never sent through. Real failover is in NRTI, not audit-srv.
- **Sink is NOT Spring Boot** — it's Kafka Connect on the KCaaS base image. Three connectors ⇒ **3× read amplification** (deliberate isolation trade-off).
- **Unmasked headers** — capture copies *all* headers incl `WM_SEC.*`/`Authorization` (`mask.enable=false`) → a real secret/PII leak in the audit store. The CA/MX filter Javadoc even *lies* (says "or if header missing" but inherits the strict base).

**🗣️ Spoken micro-script (2-3 turns):**
1. *Open:* "The `<5ms` is added overhead on the *audited* API's hot path, not audit freshness — freshness is minutes because the Connect sink flushes every 600 seconds. Two async hops give the low overhead: an `@Async` capture in the shared lib, and the producer returning HTTP 204 before it ever touches Kafka."
2. *Likely follow-up — "so you guarantee delivery?":* "No, and I'll be precise: the producer config sets no `acks`/idempotence, so the client default of effectively `acks=1` applies — `KafkaProducerConfig.populateConfigProperties` literally never sets them. The pipeline *shape* is durable; the producer durability wasn't hardened."
3. *Close (turns the wart into seniority):* "First things I'd change: `acks=all` + `min.insync.replicas=2` + idempotence, and replace that `newCachedThreadPool` with a bounded pool + a 'dropped-audit' rejection metric. And I'd mask `WM_SEC.*`/`Authorization` at capture — today they land unmasked."

**Attribution:** "I owned tiers 2 and 3 (the Avro producer and the Connect/SMT sink) and the end-to-end design; tier-1 capture is the shared lib (Bullet 2)." See `BULLET-1-KAFKA-AUDIT-LOGGING.md`; receipts in `10-AUTHENTICITY-AUDIT.md`; consistency in `13-GAPS-AND-CONTRADICTIONS.md`.

---

## Bullet 2 — Common JAR

❌ **Current:** "Spearheaded a reusable Spring Boot starter JAR with async HTTP body capture (ContentCachingWrapper + @Async thread pool), adopted as the organization standard, reducing integration from 2 weeks to 1 day per service."

**Three rewrite variants:**

**(A) Safe / bulletproof**
> "Built a reusable **audit-capture library** (servlet `OncePerRequestFilter` + `ContentCaching` wrappers + bounded **`@Async`** pool) adopted across our CPerf/Luminate services, partnering on the broader effort; cut per-service audit integration from **~2 weeks to ~1 day** (estimate)."
> *Why it survives:* "starter JAR"→"library" (the trap word is gone); "spearheaded"→"built ... partnering on" (honest attribution); "organization standard"→true scope; "(estimate)" disarms the metric.

**(B) Balanced — RECOMMENDED**
> "Built and drove adoption of a reusable **audit-capture library** — servlet-filter `ContentCaching` capture + a bounded **`@Async`** ship hop that keeps the audited request off the crypto/network path — adopted across CPerf services, cutting integration from **~2 weeks to ~1 day**."
> *Why it survives:* keeps the impressive mechanism (off-thread `@Async` hop) and the adoption story, drops "starter," and the "~" signals an estimate without weakening it.

**(C) Impact-forward**
> "Owned the design of a drop-in audit-capture library that made adding API auditing a **config change, not a rewrite** — adopted as the de-facto CPerf standard and collapsing per-service integration from **~2 weeks to ~1 day**."
> *Why it survives:* outcome-led; "de-facto standard" is honest ("adopted across CPerf," not literally all Walmart); still no "starter."

**Cite if challenged (the receipts):**
- `ContentCaching + filter`: `filters/LoggingFilter` is `@Order(LOWEST_PRECEDENCE)` extends `OncePerRequestFilter`; wraps `ContentCachingRequest/ResponseWrapper`, gates on `featureFlagCCMConfig.isAuditLogEnabled()` + the `enabledEndpoints` allow-list, and must call `copyBodyToResponse()` or the client gets an empty body.
- `bounded @Async`: `configs/auditlog/AuditLogAsyncConfig` — `setCorePoolSize(6); setMaxPoolSize(10); setQueueCapacity(100); setThreadNamePrefix("Audit-log-executor-")`; no `RejectedExecutionHandler` ⇒ default **`AbortPolicy`** (asserted by `AuditLogAsyncConfigTest`).
- `off-thread ship`: `services/AuditLogService.sendAuditLogRequest` is `@Async`; signs 4 `WM_*` headers via `AuthSign` then posts via `AuditHttpServiceImpl` (reactive `WebClient` used with `.block()`).

**Repo will show ___ (pre-empt it):**
- **NOT a starter** — there is **no `src/main/resources`**, so no `spring.factories` and no `AutoConfiguration.imports`. Consumers must `@ComponentScan com.walmart.dv.filters/services` (proof: `NrtiApiApplication`) and **provide their own `WebClient` bean** (`WebClientConfig`).
- **Boot 2.7.11 / Java 11 outlier** — every consumer is Boot 3 / Java 17; cross-version reuse works because NRTI *excludes* `spring-boot-starter-webflux` from the jar and supplies its own WebClient. In-repo version `0.0.45`, consumed `0.0.61`.
- **`mask.enable=false`** — `AuditLogFilterUtil` copies all headers incl `Authorization`/`WM_SEC.*` → secret/PII leak.
- **Dead `RestTemplate` import** in `AuditHttpServiceImpl` (half-finished migration; the live client is WebClient `.block()`); `@Async` `AbortPolicy` silently drops audit logs on saturation (no delivery guarantee). `request/response_size_bytes` are `toString().getBytes().length` — effectively meaningless.

**🗣️ Spoken micro-script (2-3 turns):**
1. *Open (self-correct before they probe):* "I'll be precise — it's a shared Spring Boot *library*, not a true auto-configured starter. There's no `spring.factories`, so consumers component-scan `com.walmart.dv.*` and supply a `WebClient` bean. 'Starter' on the resume was shorthand."
2. *Follow-up — "what's the actual win, then?":* "The off-thread `@Async` hop. The request thread only pays for the `ContentCaching` wrappers and submitting a `Runnable`; signing and the network POST happen on a bounded 6/10/100 pool, so an audit-sink outage can never fail a customer call."
3. *Close:* "If I hardened it I'd ship an `AutoConfiguration.imports` so it's a real zero-config starter, recompile against Jakarta to retire the Boot-2.7 outlier, and mask `WM_SEC.*`/`Authorization` — today it copies them unmasked with `mask.enable=false`."

**Attribution:** "I owned the capture-tier design (filter + `ContentCaching`, the async model + pool sizing, the CCM flag/allow-list, the signed-POST integration) and drove its adoption; `Nayana.BG` is the listed pom developer, so it was collaborative — I credit the team for the rest." See `BULLET-2-COMMON-STARTER-JAR.md`; receipts `10-AUTHENTICITY-AUDIT.md`; consistency `13-GAPS-AND-CONTRADICTIONS.md`.

---

## Bullet 3 — Active/Active Multi-Region Kafka

❌ **Current:** "Implemented Active/Active multi-region Kafka across EUS2/SCUS with CompletableFuture failover, achieving 15-min DR recovery (vs 1-hour RTO) with zero data loss."

**Three rewrite variants:**

**(A) Safe / bulletproof**
> "Implemented **active/active multi-region Kafka publishing** across EUS2/SCUS with **per-message `CompletableFuture` failover** (`acks=all`, `retries=10`, **`enable.idempotence=false` ⇒ at-least-once with messageId consumer dedup**); sub-second automatic failover and **~15-min operational DR** (down from a ~1-hour manual runbook)."
> *Why it survives:* encodes the honesty *inline* — `idempotence=false`/at-least-once is in the line itself, so it can't read as exactly-once; "operational DR" labels the 15-min; no RF claim at all (drops the inferred number).

**(B) Balanced — RECOMMENDED**
> "Implemented producer-side **active/active dual-region failover** (EUS2/SCUS) for supplier inventory events: each region writes locally and on the send `CompletableFuture`'s failure path re-sends to the other region — `acks=all` + **at-least-once with messageId dedup** (not exactly-once), giving sub-second auto-failover and **~15-min operational DR**."
> *Why it survives:* "active/active dual-region failover" is precise (not "continuous mirroring"); the parenthetical kills the exactly-once read; keeps the strong, code-true `acks=all` + per-message failover.

**(C) Impact-forward**
> "Built sub-second automatic **multi-region failover** for Walmart's supplier inventory-event stream (EUS2/SCUS) so a regional Kafka outage degrades to a per-message reroute instead of downtime — **no observable loss of an acknowledged event** under single-region failure."
> *Why it survives:* leads with resilience outcome; uses the canon-exact "no observable loss of an acknowledged event" instead of "zero data loss"; sub-second is true for *fast* failures (caveat ready in script).

**Cite if challenged (the receipts):**
- `failover lives here`: `cp-nrti-apis/.../services/impl/NrtKafkaProducerServiceImpl` — `kafkaPrimaryTemplate.send(msg)` returns `CompletableFuture<SendResult>`; `.exceptionally(ex -> handleFailure(...).join())` re-sends to `kafkaSecondaryTemplate`. **4 templates** (IAC + DSC × primary/secondary) in `kafka/NrtKafkaProducerConfig`.
- `tuning is real (unlike audit)`: `NrtKafkaProducerConfig` *reads and applies* from `nrtKafkaConfig.json` + `ccm.yml`: `acks=all`, `retries=10`, **`enable.idempotence=false`** (`ccm.yml` line 197), `batch.size=8192`, `linger.ms=20`, `compression.type=lz4`, `request.timeout.ms=300000` (5 min), `max.request.size=10_000_000`.
- `active/active swap`: `ccm.yml configOverrides` (≈805-852) swap primary/secondary broker URLs per `zone` (eus2 vs scus); brokers `kafka-v2-luminate-core-prod.{eus|scus}.prod.us.walmart.net:9093`.
- `keys`: IAC sets only a `MESSAGE_ID` *header* (`IacServiceHelper`) — **NULL partition key, no broker ordering**; DSC keys on `tripId`.

**Repo will show ___ (pre-empt it):**
- **`enable.idempotence=false`** → at-least-once; directly weakens any "zero loss." Pre-empt: "at-least-once + consumer dedup on messageId."
- **IAC vs DSC asymmetry** — IAC `.join()`s and returns **500** on total failure (`NrtiUnavailableException` is `@ResponseStatus(INTERNAL_SERVER_ERROR)` — literal status is 500, not 503; arguably *should* be 503 + `Retry-After`); **DSC is fire-and-forget and returns 201 regardless** (a real smell — a dropped DSC looks like success).
- **`request.timeout.ms=300000` (5 min)** — undercuts "fast failover" for a *black-hole* (slow) failure; sub-second is only true for *fast* failures (connection-refused / no-brokers).
- **IAC `.join()` blocks the Tomcat thread** — pool-exhaustion risk at scale.
- **RF3 is inferred** (3 brokers per region) — `replication.factor` is provisioned via KaaS and is **not in any repo**; never present it as committed config.
- **NRTI is producer-only** — no `@KafkaListener`; consumer failover/offset-continuity is downstream, not your code.

**🗣️ Spoken micro-script (2-3 turns):**
1. *Open:* "It's producer-side application-level dual-write-on-failure: each region writes its local cluster, and on the send future's `.exceptionally` it re-sends the same message to the other region — sub-second and automatic, no human."
2. *Follow-up — "zero data loss?":* "Reframe: no *observable* loss of an *acknowledged* IAC event under single-region failure, via `acks=all`. It's at-least-once, not exactly-once — `enable.idempotence=false` — so duplicates are possible and deduped downstream on a client-supplied `messageId`."
3. *Follow-up — "and DSC?" / "is it uniform?":* "No, and I'll own the asymmetry: IAC blocks and returns 500 on total failure (the `NrtiUnavailableException` is annotated `INTERNAL_SERVER_ERROR` — I'd actually switch it to a 503 + `Retry-After` since it's a retryable unavailability) so the supplier retries; DSC is fire-and-forget and returns 201 even on failure — I'd add a DSC failure metric + DLQ. And the 5-minute `request.timeout.ms` means 'sub-second' is only for fast failures; I'd add `future.orTimeout(...)` to bound black-hole hangs. RF3 I'd call inferred — three brokers per region — not a config I can point at."

**Attribution:** "I owned the producer-side failover in `cp-nrti-apis`; consumer-side DR is downstream and I won't claim it." Do **not** attribute failover to `audit-api-logs-srv` (its secondary template is dead code). See `BULLET-3-ACTIVE-ACTIVE-MULTIREGION-KAFKA.md`; receipts `10-AUTHENTICITY-AUDIT.md`; consistency `13-GAPS-AND-CONTRADICTIONS.md`.

---

## Bullet 4 — Spring Boot 3 / Java 17 Migration

❌ **Current:** "Led Spring Boot 2.7 to 3.2 / Java 11 to 17 migration for the main supplier-facing API with Flagger canary releases (10% to 100%), achieving zero customer-impacting issues."

**Three rewrite variants:**

**(A) Safe / bulletproof**
> "Led the **Spring Boot 2.7→3.x / Java 11→17** migration of our supplier-facing inventory API (Jakarta namespace, **Hibernate 6 `@JdbcTypeCode`** enum/array fixes, Spring Kafka `ListenableFuture→CompletableFuture`), shipped behind a **Flagger/Istio canary** (10%→50% steps, 5xx-gated auto-rollback, then promote to 100%) with **zero customer-impacting issues**."
> *Why it survives:* "3.2"→"3.x" (matches the 3.5.x pom); names the *real* hard parts (cited, specific); canary described accurately (50% maxWeight, then promote).

**(B) Balanced — RECOMMENDED**
> "Led the **Spring Boot 2.7→3.x / Java 11→17** migration of the main supplier-facing API — Jakarta namespace, **Hibernate 6** strict typing (`@JdbcTypeCode` for PG enums + `Integer[]`), Spring Kafka 2→3 — rolled out as a **Flagger canary on Istio** (+10% to 50%, 1% 5xx auto-rollback gate, promote to 100%) with **zero customer-impacting issues**."
> *Why it survives:* same depth, slightly tighter; the `@JdbcTypeCode` detail is the single most code-grounded proof you can offer.

**(C) Impact-forward**
> "Modernized the supplier-facing inventory API off end-of-life Spring Boot 2.7/Java 11 to **Spring Boot 3 / Java 17**, de-risking the major-version breaking changes with a **metric-gated Flagger canary** that auto-rolls-back on 5xx — **zero customer-impacting issues** across the rollout."
> *Why it survives:* outcome-led; "zero customer-impacting" reads (correctly) as a property of the rollout design, not "zero bugs."

**Cite if challenged (the receipts):**
- `versions`: `pom.xml` parent `spring-boot-starter-parent` **3.5.14**, BOM `springboot.version=3.5.7` (effective), `java.version=17`, `<release>17</release>`.
- `Jakarta`: 149 `jakarta.*` references vs 2 residual `javax.*` (one — `javax.sql.DataSource` in `PostgresDbConfiguration` — is *correct*; `javax.sql` is JDK, never moved).
- `Hibernate 6 (the anchor)`: `entity/ParentCompanyMapping.java` adds `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` for the PG enum; `entity/NrtStoreGtinMapping.java` adds `@JdbcTypeCode(SqlTypes.ARRAY)` for `Integer[] store_number`.
- `Spring Kafka 2→3`: `NrtKafkaProducerServiceImpl` rewrote `ListenableFuture` → `CompletableFuture<SendResult>` with `.thenAccept`/`.exceptionally`.
- `canary`: `kitt.yml` (≈722-748) `stepWeight: 10`, `maxWeight: 50`, `interval: 2m`, gate = PromQL over `envoy_cluster_upstream_rq` 5xx-rate `threshold: 1` (line ≈735); prod HPA `min 6 / max 12 @ cpuPercent 60`.

**Repo will show ___ (pre-empt it):**
- **No Spring Security** — zero matches for `spring-security`/`SecurityFilterChain`/`WebSecurityConfigurerAdapter`. Auth = gateway `WM_SEC.*` + custom servlet filters (`RequestFilter`/`XssFilter`/`NrtCorsFilter`) + `NrtiApiInterceptor`. **Don't claim a Security 5→6 migration.**
- **No RestTemplate** — `grep RestTemplate src/main` = 0; WebClient was already the client. **Don't claim a RestTemplate→WebClient migration.**
- **"3.2" is stale** — pom is 3.5.x; say "led the 2.7→3.x jump, stayed current."
- **Canary gate is 5xx-only** — blind to semantic (200-with-wrong-data) and latency regressions; those are caught by R2C contract tests + Automaton perf in stage.
- **`.toList()` cleanup is partial** (14 new vs 19 remaining `Collectors.toList`) — don't claim a sweeping rewrite.

**🗣️ Spoken micro-script (2-3 turns):**
1. *Open:* "The version bump was the easy part; the breaking changes were the work — Jakarta namespace, Hibernate 6's stricter typing, and Spring Kafka's `ListenableFuture→CompletableFuture`."
2. *Follow-up — "give me a concrete breaking change":* "Hibernate 6 stopped implicitly mapping our PostgreSQL enum and `Integer[]` columns — it compiles fine and throws at *query* time. The fix was `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` on `ParentCompanyMapping` and `SqlTypes.ARRAY` on `NrtStoreGtinMapping.store_number`. We caught it in **stage**, not prod."
3. *Follow-up — "how was it zero-impact?":* "Process, not luck. The Flagger gate is 5xx-only — blind to a semantic 200-with-wrong-data regression — so contract tests in stage carry that load; the canary just bounds unknown-unknowns to ~10% for ≤2 minutes. And to pre-empt: there was **no Spring Security migration** (auth is gateway-side) and **no RestTemplate→WebClient migration** (WebClient was already in use)."

**Attribution:** "I led this migration end-to-end — scoped the breaking-change inventory, drove the BOM-first upgrade, wrote the entity/Kafka changes, configured the canary, and ran the prod rollout." See `BULLET-4-SPRINGBOOT3-JAVA17-MIGRATION.md`; receipts `10-AUTHENTICITY-AUDIT.md`; consistency `13-GAPS-AND-CONTRADICTIONS.md`.

---

## Bullet 5 — DC Inventory Search API

❌ **Current:** "Developed DC Inventory Search API end-to-end using OpenAPI design-first approach, enabling parallel consumer integration (30% faster) with 3-stage pipeline and factory pattern for multi-site support (US/CA/MX)."

**Three rewrite variants:**

**(A) Safe / bulletproof**
> "Contributed to the **DC Inventory Search API** (`POST /dc/inventory/status`) under an **OpenAPI design-first** contract that let consumers integrate in parallel (~30% faster onboarding, estimate); a **3-stage pipeline** (edge-validate → authorize + GTIN translate + reactive EI read → map by inventory-type/state), with **per-region multi-site config (US/CA/MX) via CCM**."
> *Why it survives:* "Developed ... end-to-end"→"Contributed to" (honest authorship); "factory pattern"→"per-region config via CCM" (no `*Factory` exists); "30% faster"→"(estimate)"; design-first kept as a contract, not codegen.

**(B) Balanced — RECOMMENDED**
> "Partnered on the **DC Inventory Search API** with an **OpenAPI design-first** contract enabling parallel consumer integration (~30% faster onboarding); a clean **3-stage pipeline** (validate → authorize + WM-item→GTIN translation + reactive EI read → map PROMO/TURN by state) with **per-region multi-site config (US/CA/MX)** via CCM."
> *Why it survives:* "Partnered on" is honest; the 3-stage breakdown signals real understanding; "per-region config via CCM" is exactly what the code does (trap word gone).

**(C) Impact-forward**
> "Helped ship a supplier-facing **DC Inventory Search API** on a design-first OpenAPI contract that unblocked consumers to integrate against generated clients in parallel (~30% faster), backed by a 3-stage authorize-translate-read pipeline over Walmart's Enterprise Inventory."
> *Why it survives:* outcome-led, still "helped ship" (not sole-author); "design-first" framed as the parallelization lever (true), no factory claim.

**Cite if challenged (the receipts):**
- `endpoint + 3 stages`: `controller/DcInventoryController` `@PostMapping("/inventory/status")` → 200. Stage 1 `filters/RequestFilter` + `interceptors/NrtiApiInterceptor` + `NrtBusinessValidatorService.validateDCInventoryStatusRequest`; Stage 2 `SupplierMappingServiceImpl` → `UberKeyReadService.getGtinsFromWmItemNbrs` → `StoreGtinValidatorServiceImpl.getMappedGtins` (authorize on `globalDuns`) → `HttpServiceImpl` reactive WebClient `.timeout(10s)` + `Retry.backoff(3,100ms,max2s).block()`; Stage 3 `EIServiceHelper.getDcInventories` maps to `DcInventoryItem` (PROMO/TURN × state).
- `multi-site = config`: `configs/SiteIdCCMConfig.getWmSiteId()`, `EiApiCCMConfig.getEIDcInventory*` are Strati `@ManagedConfiguration`; `wmSiteId`/country default `"US"`; CA/MX = same artifact + CCM overrides (`*-INTL` companion in `sr.yaml`).

**Repo will show ___ (pre-empt it):**
- **No `*Factory` class** — `grep -rn "factory" src/main` returns only framework factories (`DefaultKafkaProducerFactory`, MapStruct `Mappers`, Spring `beans.factory`). Multi-site = per-region deploy + CCM + header-based controller dispatch, **not** a GoF factory.
- **DC controllers are hand-written** — the `spring` generator runs only on `openapi_items_assortment.json`; for `openapi.json` the `openapi` generator just **bundles** the spec (no Java). Design-first is a *process*, not server codegen for DC.
- **GET-with-body to EI** — `HttpServiceImpl.sendHttpListRequest(uri, GET, entity, ...)` sends a GET with a body (unusual; an EI-contract constraint).
- **`.block()` on a reactive WebClient inside Tomcat MVC** — thread-occupancy/starvation risk on the servlet pool under a slow EI.
- **Authorship** — DC files largely **Keshav Gatla & Ambiorix Cruz Angeles**; use "I contributed / partnered on."

**🗣️ Spoken micro-script (2-3 turns):**
1. *Open (attribution + scope up front):* "I'll be accurate about ownership — the DC endpoint itself was built across the team; my owned slices were the surrounding NRTI work (sandbox metrics, store-GTIN flow, HPA/scaling, Snyk/logging) and the Spring Boot 3 modernization this runs on, plus championing the design-first contract."
2. *Follow-up — "what does design-first buy you?":* "Consumers generate a typed client and a mock from the agreed spec and build in parallel, so their work hides behind our backend build — that overlap is the ~30%, an estimate, not an instrumented metric. For DC the controllers are hand-written to the spec; only items-assortment is codegen'd."
3. *Follow-up — "the factory pattern?":* "There's no GoF `*Factory` — 'multi-site' is the same artifact deployed per region with different CCM config, plus header-based controller dispatch. If we needed true runtime US/CA/MX in one process I'd build a site-keyed strategy registry. One honest caveat on the read path: the EI call is a reactive WebClient `.block()` inside Tomcat — fine today, but I'd add a circuit breaker/bulkhead before it can starve the request pool."

**Attribution:** "Contributed to / partnered on the DC endpoint; my owned slice was the surrounding NRTI + SB3 work and the contract-first discipline. Credit Keshav Gatla & Ambiorix Cruz Angeles for the core DC files." See `BULLET-5-DC-INVENTORY-SEARCH-API.md`; receipts `10-AUTHENTICITY-AUDIT.md`; consistency `13-GAPS-AND-CONTRADICTIONS.md`.

---

## Summary section rewrite

❌ "...processing 2M+ events/day. Built a Kafka-based audit platform with multi-region Active/Active architecture..."

**Three variants:**

**(A) Safe**
> "...handling **millions of events/day**. Built a **Kafka audit platform** (Avro → Connect → GCS/BigQuery) and a separate **active/active multi-region inventory-event publisher**, and led a **Spring Boot 3 / Java 17** migration behind Flagger canaries."

**(B) Balanced — RECOMMENDED**
> "...at **millions of events/day**. Built a **Kafka audit platform** and an **active/active multi-region inventory-event publisher** with per-message `CompletableFuture` failover, and led a **Spring Boot 3 / Java 17** migration rolled out behind metric-gated Flagger canaries."

**(C) Impact-forward**
> "...powering Walmart supplier inventory + audit at **millions of events/day** — a Kafka audit platform off Splunk, sub-second multi-region failover for inventory events, and a Spring Boot 3 / Java 17 modernization shipped with zero customer-impacting issues."

*Why:* "2M+"→"millions" (matches INDEX, avoids an unsourced number, and **guards against importing the GCC `10M+` figure** — they are different projects, doc 13). Keeps the two products **separate** (audit platform ≠ inventory publisher) so they never fuse under questioning.

---

## BANNED phrases → safer substitutes

Truthful *and* still strong. If a banned phrase is on the page or about to leave your mouth, swap it:

| ❌ Banned phrase | Why it's unsafe (the receipt that kills it) | ✅ Safer substitute |
|---|---|---|
| "exactly-once" | NRTI `enable.idempotence=false` (`ccm.yml` 197) ⇒ at-least-once | "at-least-once with **messageId consumer dedup**" |
| "zero data loss" (unqualified) | NRTI at-least-once; audit effective `acks=1` (no acks set) | NRTI: "no observable loss of an **acknowledged** event under single-region failure"; audit: "durable *shape*; producer durability not yet hardened" |
| "Spring Boot **starter** JAR" | no `src/main/resources` / `spring.factories` / `AutoConfiguration.imports` | "reusable shared **library** (consumers component-scan + supply a WebClient)" |
| "**factory pattern** for multi-site" | no `*Factory` class (`grep` = framework factories only) | "**per-region deploy + CCM config** (+ DI / header-based dispatch)" |
| "RestTemplate → WebClient **migration**" | `grep RestTemplate src/main` = 0; WebClient was already there | "validated the existing WebClient against WebFlux/Reactor 6 changes" |
| "Spring Security 5→6 **migration**" | no `spring-security`/`SecurityFilterChain` in repo | "auth is gateway `WM_SEC.*` + custom servlet filters — Security migration cost was zero for us" |
| "Spring Boot **3.2**" | pom parent 3.5.14 / BOM 3.5.7 | "led the **2.7→3.x** jump; on 3.5.x today" |
| "<5ms audit **latency**" | freshness is minutes (`flush.interval=600s`) | "<5ms **overhead** added to the audited API" |
| "**2M+** / **millions per second**" | ~23 msg/s avg; 2M is unsourced; 10M+ is the GCC project | "**millions of events/day**" (never /sec, never import GCC's 10M+) |
| "canary 10% → **continuously to 100%**" | Flagger `maxWeight: 50` then promote | "ramps **+10% to 50%**, then **promotes** to 100%" |
| "**Spearheaded / Developed end-to-end**" (solo) | collaborative; pom dev `Nayana.BG`; DC by Keshav/Ambiorix | "**Built/Owned** [my slice]; **partnered with the team** on the rest" |
| "**RF3** / replication.factor=3" | not in any repo; only inferred from 3 brokers | "RF likely 3 (**inferred** from 3 brokers per region; KaaS-provisioned)" |
| "Spring Boot **sink**" | sink is **Kafka Connect** (Lenses), not Spring | "**Kafka Connect** Lenses GCS sink" |
| "15-min DR (code)" | code failover is sub-second; 15-min is operational | "sub-second automatic failover; **~15-min operational DR** (game-day, not in repo)" |
