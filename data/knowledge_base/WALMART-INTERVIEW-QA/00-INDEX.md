# Walmart Interview Prep — Master Index

> Candidate: **Anshul Garg** · Team context: **Channel Performance (CPerf) / Luminate**, supplier-facing inventory & audit platform on **WCNP (Azure, EUS2 + SCUS) + Istio**.
> This is the navigation hub for five per-bullet deep-dive study files. Each bullet was reverse-engineered from the **actual source code** under `/Users/a0g11b6/Desktop/walmart`, so every claim here is grounded in code — including the places where the **resume wording is looser than the code supports**. Read the watch-outs (Section E) before any interview; they are the things most likely to get you cornered.

---

## A. The Five Bullets at a Glance

| # | Bullet (resume) | File | One-line: what it actually is | 30-second pitch |
|---|---|---|---|---|
| **1** | Three-tier Kafka-based **audit logging** system, sub-5ms P99 latency impact, millions of daily events, Avro, SMT geo-routing (US/CA/MX), GCS Parquet/BigQuery; replaced Splunk with supplier self-service. | [`BULLET-1-KAFKA-AUDIT-LOGGING.md`](./BULLET-1-KAFKA-AUDIT-LOGGING.md) | A three-tier async pipeline: shared servlet-filter capture → a fire-and-forget producer (`audit-api-logs-srv`) that returns **HTTP 204** then publishes **Avro** to Kafka keyed by `service/endpoint` with a `wm-site-id` header → a **Kafka Connect** GCS sink with **per-country SMT filters (US/CA/MX)** writing **Parquet** to per-country buckets, BigQuery on top. | "Three-tier audit pipeline: a shared lib captures every API call and async-POSTs it; the producer returns 204 instantly then publishes an Avro record keyed by service/endpoint with a country header; Kafka Connect runs three GCS sink connectors, each with an SMT that filters by that header and writes Parquet to a per-country bucket, BigQuery for self-service. Async keeps the overhead tiny, SMT routing handles data residency, and it got us off Splunk. Honest follow-ups: harden producer durability (acks=all, idempotence) and bound the thread pool." |
| **2** | Reusable **Spring Boot starter JAR** with async HTTP body capture (`ContentCachingWrapper` + `@Async`), org standard, integration 2 weeks → 1 day. | [`BULLET-2-COMMON-STARTER-JAR.md`](./BULLET-2-COMMON-STARTER-JAR.md) | `dv-api-common-libraries` — a shared **Spring Boot 2.7.11 / Java 11** JAR (a **library, NOT a true auto-configured starter**) whose servlet `LoggingFilter` wraps request/response in ContentCaching wrappers, builds an 18-field `AuditLogPayload`, and ships it off-thread via an `@Async` pool (core 6/max 10/queue 100) as a **signed JSON POST** to `audit-api-logs-srv`. | "I built the audit-capture library every CPerf service uses. A servlet filter wraps request and response in ContentCaching wrappers (the body is a read-once stream), captures it, and hands it to an async pool that signs and POSTs it to the central audit service. The async hop is the trick: the customer's request never waits on crypto or the network. It's CCM feature-flag driven, so teams flip it on per endpoint with no redeploy — turning ~2 weeks of bespoke audit code into ~1 day. I'm precise that it's a shared library, not a true auto-configured starter, and I know where to harden it: jakarta rebuild, header masking, bounded retry." |
| **3** | **Active/Active multi-region Kafka** across EUS2/SCUS with `CompletableFuture` failover, 15-min DR recovery (vs 1-hour RTO), zero data loss. | [`BULLET-3-ACTIVE-ACTIVE-MULTIREGION-KAFKA.md`](./BULLET-3-ACTIVE-ACTIVE-MULTIREGION-KAFKA.md) | **Producer-side** active/active dual-region failover in **`cp-nrti-apis`**: send to the region-local primary cluster; on the send `CompletableFuture`'s `.exceptionally`, re-send the same message to the other region's secondary `KafkaTemplate` — sub-second, automatic, no runbook. | "Our inventory-event service runs in both Azure regions, each writing to its local Kafka as primary. On every send I get a CompletableFuture; in its `.exceptionally` I re-send the same message to the other region's cluster, so a regional outage degrades to a sub-second per-message failover. With acks=all and RF3, an acknowledged inventory action is durable in at least one region or the supplier gets a 503 to retry — no silent loss. It's at-least-once, so I keep a stable messageId for consumer-side dedup. Automatic failover is sub-second; full operational regional recovery is ~15 minutes, down from a ~1-hour manual runbook." |
| **4** | Led **Spring Boot 2.7→3.2 / Java 11→17 migration** for the main supplier-facing API with **Flagger canary** (10%→100%), zero customer-impacting issues. | [`BULLET-4-SPRINGBOOT3-JAVA17-MIGRATION.md`](./BULLET-4-SPRINGBOOT3-JAVA17-MIGRATION.md) | A coordinated **Spring Boot 2.7→3 + Java 11→17** major-version migration of `cp-nrti-apis` (the external supplier-facing inventory REST gateway), shipped as a **Flagger metric-gated canary** on WCNP/Istio. | "I owned a Spring Boot 2.7→3 and Java 11→17 migration on our supplier-facing inventory API. The hard part was the breaking changes — Jakarta namespace, Hibernate 6 strict typing, Spring Kafka's ListenableFuture→CompletableFuture — not the version number. I upgraded BOM-first, kept the servlet stack to limit risk, soaked a week in stage with contract and perf tests, then rolled out as a Flagger canary on Istio: 10% steps with an automatic 5xx-rate rollback gate, promoting to 100% only when healthy. Zero customer-impacting issues — precise: that's a property of the staged rollout; we caught a Hibernate enum bug in stage before prod." |
| **5** | **DC Inventory Search API** end-to-end, **OpenAPI design-first** → parallel consumer integration (30% faster), 3-stage pipeline + **factory pattern** for multi-site (US/CA/MX). | [`BULLET-5-DC-INVENTORY-SEARCH-API.md`](./BULLET-5-DC-INVENTORY-SEARCH-API.md) | A supplier-facing REST endpoint (`POST /dc/inventory/status` in `cp-nrti-apis`) that authorizes a supplier, translates WM item numbers → GTINs via UberKeys, reads point-in-time DC inventory from **Enterprise Inventory (EI)** over a reactive WebClient, and reshapes it into supplier-scoped JSON broken down by inventory type (**PROMO/TURN**) and state. | "I worked on cp-nrti-apis, the supplier-facing inventory gateway, including its DC inventory search endpoint. It's OpenAPI design-first — we locked the contract up front so consumer teams built against generated clients and mocks in parallel, cutting integration wall-clock ~a third. A request runs three stages: validate at the edge; resolve and authorize the supplier and translate item numbers to GTINs before reading EI over a reactive WebClient with timeout/retry; then map EI's promo/turn inventory-by-state into a clean response with per-item partial errors. Multi-site US/CA/MX is the same code deployed per region with different CCM config. I'm precise about where 'factory' is config-and-DI versus a true runtime factory." |

---

## A.1 Cross-cutting study docs (read alongside the 5 bullets)

| File | What it is |
|------|-----------|
| [`06-KAFKA-MASTER-DEEPDIVE.md`](./06-KAFKA-MASTER-DEEPDIVE.md) | Kafka theory tied to *our* real config (30+ rapid Q&A) |
| [`07-ARCHITECTURE-AND-NUMBERS-DEFENSE.md`](./07-ARCHITECTURE-AND-NUMBERS-DEFENSE.md) | Full ASCII diagrams + every résumé number defended |
| [`08-RAPID-FIRE-CHEATSHEET.md`](./08-RAPID-FIRE-CHEATSHEET.md) | 80–120 one-line Q→A, acronym glossary, trap questions |
| [`09-OPS-CAPACITY-SIZING-QA.md`](./09-OPS-CAPACITY-SIZING-QA.md) | **Operational reality**: topics, partition key, partition/consumer counts, RF, retention, producer tuning, throughput math, HPA/Little's-Law, DR, monitoring — **125 Q&A**. Start at its Section 0 "ops reality answer key". |
| [`10-AUTHENTICITY-AUDIT.md`](./10-AUTHENTICITY-AUDIT.md) | **Docs-vs-code receipt.** Every study-doc claim re-verified line-by-line against real source under `/Users/a0g11b6/Desktop/walmart`, with file+line evidence. Verdict: prep is highly accurate; ~8 soft/ops-only numbers flagged. Read before claiming anything as "code-proven." |
| [`11-WALMART-KAFKA-INTERNALS.md`](./11-WALMART-KAFKA-INTERNALS.md) | **How Walmart Kafka actually runs:** KaaS/KCaaS managed platform, dual-region topology, mTLS-at-Istio-mesh (why config says PLAINTEXT), CCM/KITT config plane, both serialization worlds end-to-end, failure modes, **+32 NEW interview Q&A** not in 06/08/09. |
| [`12-BULLET-2-CODE-VERIFICATION.md`](./12-BULLET-2-CODE-VERIFICATION.md) | Line-by-line proof that the common JAR is a library not a starter (closes the gap from doc 10): pool config, javax/jakarta outlier, masking-off leak, dead RestTemplate, all code-cited. |
| [`13-GAPS-AND-CONTRADICTIONS.md`](./13-GAPS-AND-CONTRADICTIONS.md) | Cross-doc consistency check: number mismatches, internal contradictions to reconcile, genuine uncovered gaps, and tape-to-monitor consistency rules. |
| [`14-RESUME-BULLETS-TIGHTENED.md`](./14-RESUME-BULLETS-TIGHTENED.md) | ❌→✅ rewrites of all 5 bullets that survive the watch-outs, each with a spoken add-on. |
| [`15-MOCK-INTERVIEW-DRILL.md`](./15-MOCK-INTERVIEW-DRILL.md) | Top-15 hardest questions as a self-scored drill sheet (0–2 rubric, target 26+/30). |
| [`flashcards.html`](./flashcards.html) | **Interactive flip-card + cheat-sheet web page** (Tailwind, Walmart colors, filter by bullet). Open in a browser. |
| [`16-DEEP-FUNDAMENTALS-CONCURRENCY-ANNOTATIONS-SB3.md`](./16-DEEP-FUNDAMENTALS-CONCURRENCY-ANNOTATIONS-SB3.md) | **Under-the-hood for the migration + audit bullets:** thread-per-request model, how `@Async`/`@Transactional` proxies actually fire, JDK vs CGLIB proxies, ThreadLocal/MDC propagation across async, `CompletableFuture` failover mechanics, virtual threads, and every real SB2.7→3 breaking change (Jakarta, Hibernate 6 `@JdbcTypeCode`, spring-kafka `ListenableFuture`→`CompletableFuture`). Code-grounded. |
| [`17-DEEP-FUNDAMENTALS-KAFKA-AUDIT.md`](./17-DEEP-FUNDAMENTALS-KAFKA-AUDIT.md) | **Kafka byte-by-byte:** producer internals (RecordAccumulator, Sender thread, linger/batch/lz4), partitioning + hot-partition trap, ordering & reordering with idempotence=false, **Avro wire format** (magic byte + schema ID), schema-evolution compat modes, Connect consumer-group/offset/rebalance mechanics, and end-to-end delivery semantics. |
| [`18-PRINCIPAL-INTERVIEWER-DRILLDOWN.md`](./18-PRINCIPAL-INTERVIEWER-DRILLDOWN.md) | **The brutal one.** 8 multi-level follow-up *chains* from a 10-year principal interviewer who drills each answer to the floor (the 204/data-loss corner, the <5ms boundary, the .join() load-math takedown, exactly-once-is-impossible-in-your-topology, the Jakarta load trap, residency-is-a-hope, ownership). Plus framework sniper rounds + the secret scorecard. Drill until you reach the floor answer voluntarily. |
| [`19-ROLEPLAY-FULL-TRANSCRIPTS.md`](./19-ROLEPLAY-FULL-TRANSCRIPTS.md) | **Full role-play transcripts** — I play both the principal (🟥 PE) and the ideal candidate (🟩 You), word-for-word, for 7 chains. Mermaid diagrams. Cover the green lines and reproduce them. Teaches the concede→mechanism→fix rhythm. |
| [`20-SYSTEM-DESIGN-ROUND.md`](./20-SYSTEM-DESIGN-ROUND.md) | **"Design an audit-logging platform from scratch"** — where YOUR system is the textbook answer. Requirements → estimation → 3-tier design → 5 deep dives → failure modes → 100x scaling → alternatives table → 60-sec wrap. Mermaid diagrams throughout. |
| [`chains-and-design.html`](./chains-and-design.html) | **Interactive page** with expandable role-play chain cards + the full system-design walkthrough + live-rendered Mermaid diagrams + the 3-beat rhythm tab. Open in a browser. |

> **The single most-asked-for answer key** lives in `09` Section 0: partition key / #topics / #partitions / #consumers / RF / retention / "how did you decide each" — for both the audit and NRTI systems, side by side, with the honest "provisioned via KaaS, sized by formula" framing for the numbers that aren't in the code.

---

## B. The End-to-End Mental Model — How the Walmart Work Fits Together

There are **two distinct products** that share infrastructure conventions, plus **one cross-cutting platform discipline** (the migration). Do not conflate them — the single most common way to get caught is mixing the audit Avro/Schema-Registry path with the NRTI JSON inventory path.

### B.1 The Audit Platform (Bullets 1 + 2) — "every supplier API call gets recorded, off the hot path"

```
  Any CPerf service (e.g. cp-nrti-apis)
        │
        │  [BULLET 2]  dv-api-common-libraries (shared JAR, SB 2.7.11 / Java 11 / javax.servlet)
        │  LoggingFilter (OncePerRequestFilter, LOWEST_PRECEDENCE)
        │    → ContentCachingRequestWrapper + ContentCachingResponseWrapper (body is read-once)
        │    → build 18-field AuditLogPayload
        │    → @Async pool (core6/max10/queue100, AbortPolicy)  ← latency win lives HERE
        │    → AuthSign (4 WM_SEC headers) → signed JSON POST  (fire-and-forget, errors only logged)
        ▼
  [BULLET 1 · Tier 2]  audit-api-logs-srv (SB 3.5.12 / Java 17)
        AuditLoggingController.saveApiLog → returns HTTP 204 IMMEDIATELY  ← sub-5ms overhead lever
        → ExecutorPoolService (UNBOUNDED Executors.newCachedThreadPool — OOM-under-burst risk)
        → KafkaProducerService.send(kafkaPrimaryTemplate)  (log-only try/catch; secondary template is DEAD CODE)
        → Avro (KafkaAvroSerializer + Schema Registry, auto.register.schemas=false)
          key = serviceName/endpoint  ·  header wm-site-id  ·  topic api_logs_audit_{env}
        ▼
  [BULLET 1 · Tier 3]  Kafka Connect (NOT Spring Boot — Lenses GCPStorageSinkConnector plugin)
        3 connectors (US / CA / MX), tasks.max=1, errors.tolerance=all + DLQ
        each with an SMT (BaseAuditLogSinkFilter): verifyHeader(wm-site-id) ? pass : drop
          - US filter = permissive catch-all (also passes header-less)
          - CA / MX  = strict (header-less dropped)
        → KCQL: PARQUET, PARTITIONBY service_name,_header.date,endpoint_name
          → audit-api-logs-{us|ca|mx}-prod GCS buckets  (flush 50MB/5000/600s)
        ▼
  BigQuery external tables  →  supplier self-service debugging  (replaced Splunk)
```

Key truths:
- **The "sub-5ms" is overhead added to the audited API, not end-to-end audit freshness.** Freshness is *minutes* (flush.interval = 600s). Quote the right latency.
- **Two async hops** keep the hot path clean: the `@Async` POST in the JAR (Bullet 2), then the **204-then-publish** in the producer (Bullet 1).
- **Geo-routing is in the sink (SMT), not at produce time** — the topic is one immutable stream; cost is **3x read amplification** (every record read by all three connectors).

### B.2 The NRTI Inventory Gateway (Bullets 3 + 4 + 5) — "the supplier-facing inventory REST API: `cp-nrti-apis`"

`cp-nrti-apis` is **one service** that all three of these bullets describe from different angles:

- **Bullet 5 — what it does:** Supplier-facing inventory reads. `POST /dc/inventory/status` (DC inventory) and store/items-assortment endpoints. Design-first OpenAPI contract; 3-stage pipeline (edge validate → authorize + UberKey GTIN translate + EI read over reactive WebClient → map PROMO/TURN-by-state). Multi-site US/CA/MX = same artifact per region + CCM config (**not** a GoF factory).
- **Bullet 3 — how it writes events durably:** When it *publishes* inventory-action events (IAC) and direct-shipment notifications (DSC), it does **active/active dual-region Kafka** via `NrtKafkaProducerServiceImpl` — `CompletableFuture.exceptionally` re-sends to the other region. `acks=all`, `retries=10`, `enable.idempotence=false` (so at-least-once). IAC blocks (`.join()`) and returns **503** on total failure; DSC is fire-and-forget and returns **201** regardless (a real asymmetry/smell).
- **Bullet 4 — how it was modernized:** This same service was migrated **SB 2.7→3 / Java 11→17** (code is now **3.5.14 parent / BOM 3.5.7**, not "3.2"), shipped via **Flagger canary** (stepWeight 10, maxWeight 50, then promote to 100; 5xx-rate gate, threshold 1%).

So: **Bullet 5 is the API surface, Bullet 3 is its event-publishing durability layer, Bullet 4 is the framework upgrade of the whole thing** — all `cp-nrti-apis`. The audit pipeline (Bullets 1+2) is a *separate* product that `cp-nrti-apis` happens to be a *consumer* of (via the common JAR).

### B.3 Shared platform conventions (true across all five)
- **CCM (Strati `@ManagedConfiguration`)** is the runtime config/feature-flag system everywhere — kill-switches, endpoint allow-lists, broker lists, site IDs, region pinning.
- **Two regions, EUS2 + SCUS**, port **9093**, cluster `kafka-v2-luminate-core-prod`; **mTLS at the Istio mesh** so Kafka client TLS is often `false`.
- **WCNP + Istio + Flagger** is the deploy/rollout substrate; **KITT** (`kitt.yaml`) is the deployment manifest.
- **Two Kafka serialization worlds, do not mix:** Audit path = **Avro + Confluent Schema Registry**; NRTI inventory path = **Spring `JsonSerializer`, no Schema Registry**.

---

## C. Recommended Study Order

1. **Bullet 5 first** ([DC Inventory](./BULLET-5-DC-INVENTORY-SEARCH-API.md)) — it's the concrete *product* (`cp-nrti-apis`), so it anchors the mental model for what the service actually does before you layer durability and migration on top.
2. **Bullet 3** ([Active/Active Kafka](./BULLET-3-ACTIVE-ACTIVE-MULTIREGION-KAFKA.md)) — the durability layer of the same service; teaches the `CompletableFuture` failover and the at-least-once / acks discussion you'll reuse everywhere.
3. **Bullet 1** ([Audit Logging](./BULLET-1-KAFKA-AUDIT-LOGGING.md)) — the flagship distributed-systems story (three tiers, Avro, SMT routing, Connect). Most surface area, most hard questions; study after you're warm on Kafka basics from Bullet 3.
4. **Bullet 2** ([Common JAR](./BULLET-2-COMMON-STARTER-JAR.md)) — Tier 1 of the audit pipeline; reinforces Bullet 1 and adds the servlet-filter / `@Async` / ContentCaching details. Pairs naturally right after Bullet 1.
5. **Bullet 4** ([SB3 Migration](./BULLET-4-SPRINGBOOT3-JAVA17-MIGRATION.md)) — last, because it references entities, the Kafka producer, and the rollout system from all the others; it's the synthesis bullet (Jakarta, Hibernate 6, Spring Kafka 3, Flagger).

**If you only have 30 minutes:** read Section E (watch-outs) end-to-end, then the 30-second pitches in Section A, then the Top-15 in Section D. Those three will keep you from being blindsided.

---

## D. Top 15 Hardest Questions Across All Bullets (with where to find the answer)

| # | Question | Bullet / File | Short honest answer |
|---|---|---|---|
| 1 | "You claim **near-zero / zero data loss** — show me the producer durability config." | **1** (audit) & **3** (NRTI) | **Different per service.** Audit producer sets **no** acks/idempotence/retries (defaults ≈ acks=1 → loss on leader failure) — propose acks=all + min.insync.replicas=2 + idempotence. NRTI **does** set acks=all + retries=10 but `enable.idempotence=false`, so it's **at-least-once**, defensible only as "no observable loss of an *acknowledged* IAC event under single-region failure." |
| 2 | "Prove the end-to-end guarantee is **not exactly-once**." | **1**, **3** | At-least-once sink + near-acks=1 (audit) or no-idempotence (NRTI) → small loss window and/or duplicates + possible reordering. Dedup is consumer-side on the stable messageId. |
| 3 | "The audit **thread pool is unbounded `newCachedThreadPool`** — what happens under burst?" | **1** | Unbounded thread growth → OOM; no back-pressure. The same thing that makes it fast (no queue cap) is the risk. Fix: bounded `ThreadPoolExecutor` + `RejectedExecutionHandler` + dropped-audit metric. |
| 4 | "The audit `send()` is async and the catch **only logs** — how do you know a broker publish failed?" | **1** | You don't — the future is unobserved, no app DLQ, caller already got 204. Honest gap; fix = observe the future + emit failure metric. |
| 5 | "Show me the **`spring.factories` / AutoConfiguration.imports** that makes this a starter." | **2** | There is none — **no `src/main/resources` at all**. It's a shared library, not an auto-configured starter; consumers must `@ComponentScan com.walmart.dv.*` and provide their own `WebClient` bean. Lead with this caveat. |
| 6 | "This JAR is **SB 2.7.11 / Java 11 / javax.servlet** but consumers are **SB 3 / Java 17 / jakarta** — how does it even load?" | **2**, **4** | Works only because NRTI **excludes the webflux starter** from the JAR and supplies its own WebClient; the code imports `javax.servlet`. Riskiest compat claim — clean fix is a **jakarta-targeted rebuild**. |
| 7 | "You copy **all request headers** into the audit payload with **masking off** — including `Authorization` / `WM_SEC.*`. Isn't that a secret/PII leak?" | **1**, **2** | Yes — genuine gap (capture is unmasked, CCM `mask.enable=false`). Raise it **proactively**; fix = mask at capture. |
| 8 | "`request.timeout.ms` is **300000 (5 min)** — so for a black-hole network failure your failover can't fire for 5 minutes. How is failover 'fast'?" | **3** | Only *fast* failures (connection refused, no brokers) give sub-second failover. Pre-empt with an `orTimeout` mitigation; be precise about what's sub-second vs not. |
| 9 | "IAC does **`.join()` on the Tomcat thread** — under 10x load with a slow primary, doesn't that exhaust the servlet pool?" | **3**, **5** | Yes — request-thread occupancy is coupled to Kafka health (and the same `.block()` risk exists on the EI WebClient read). Fix: circuit breaker + bulkhead + bounded timeout. |
| 10 | "**DSC returns HTTP 201 even when both regions fail** and the event is dropped — defend or admit." | **3**, **4** | Admit it: genuine inconsistency vs IAC's block-and-503. Best-effort telemetry treatment; would add a failure metric + DLQ rather than a misleading 201. |
| 11 | "Your resume says **Spring Boot 3.2** but the pom shows **3.5.14 / BOM 3.5.7** — which is it?" | **4** | Open with the correction: "led the 2.7→3.x jump and stayed current to 3.5.x." (BOM wins for effective versions; explain the parent-vs-BOM mismatch.) |
| 12 | "Show me your **SecurityFilterChain** / WebSecurityConfigurerAdapter→SecurityFilterChain migration." | **4** | **There is no Spring Security in the repo** — this is the trap. Auth is gateway-side (`WM_SEC.*`) + custom servlet filters (`RequestFilter`, `XssFilter`, `NrtCorsFilter`). Don't assert a Security migration. |
| 13 | "Your **Flagger gate is 5xx-only** — what regression slips past it?" | **4** | Semantic 'wrong-200' (e.g., the Hibernate enum/array bug) and latency regressions. Volunteer this as a senior admission; credit R2C contract tests + Automaton perf in stage for covering it. |
| 14 | "Show me the **factory class for US/CA/MX**." | **5** | There **is no `*Factory`** — multi-site is the same artifact deployed per region with different CCM config (`SiteIdCCMConfig`, `EiApiCCMConfig`). Reframe 'factory' as config + DI; describe how you'd build a real site-keyed client registry/strategy. |
| 15 | "If it's **design-first with codegen**, show me the generated DC controller." | **5** | Only the **items-assortment** endpoint is codegen'd via the `spring` generator; **DC/store controllers are hand-written**. Design-first is a *process* + R2C contract tests for DC, not server codegen. |

**Honorable mentions** (also in-scope, see the per-bullet `hardestQuestions`):
- "Three connectors triple broker egress — justify 3x amplification vs one branching connector." → **1**
- "A record with no `wm-site-id` — which bucket, residency violation?" → US catch-all only; CA/MX drop it → **1**
- "Why a `Filter` not a `HandlerInterceptor`/`@Aspect`? Why `OncePerRequestFilter` + `LOWEST_PRECEDENCE`?" → **2**
- "Why is the EI call a **GET with a request body**?" → **5**
- "A supplier sends 10,000 item numbers — what breaks?" (no batch cap on DC `values`) → **5**
- "Why **producer-side dual-write** instead of MirrorMaker 2 / stretch cluster?" → **3**

---

## E. The Consolidated HONEST Watch-Outs (every code-vs-resume gap, in one place)

> Read this before every interview. These are the gaps between the resume wording and what the code actually does. In every case the move is the same: **state the precise truth first, then explain the trade-off and the fix.** Volunteering these reads as senior signal; getting caught on them reads as inflation.

### Cross-cutting (attribution & scope)
- **"Spearheaded / Led / Developed end-to-end" is collaborative.** The DC inventory files (Bullet 5) were largely authored by **Keshav Gatla** and **Ambiorix Cruz Angeles**; the common JAR (Bullet 2) lists **Nayana.BG** as pom developer. Own your real contribution (design, reusability, adoption, scaling/HPA, Snyk/logging, the SB3 migration) and credit the team for the rest.
- **Don't mix the two Kafka worlds.** Audit = **Avro + Schema Registry**, key `service/endpoint`. NRTI inventory = **JSON serializer, no Schema Registry**, key = client `messageId`. Conflating them is an instant tell.

### Bullet 1 — Audit Logging
- **"Near-zero data loss" is unsupported by the producer config.** No acks/idempotence/retries set → defaults near acks=1 → leader failure can lose a record. Propose acks=all + min.insync.replicas=2 + enable.idempotence.
- **The sub-5ms mechanism is an UNBOUNDED `newCachedThreadPool`** with no back-pressure — fast *and* an OOM risk. Fix = bounded pool + `RejectedExecutionHandler` + dropped-audit metric.
- **`kafkaSecondaryTemplate` in audit-srv is DEAD CODE.** The send path uses only `kafkaPrimaryTemplate.send()` in a log-only try/catch. **Real Kafka failover lives in `cp-nrti-apis`, not audit-srv** — do not attribute in-code failover to the audit producer.
- **Tier 3 sink is NOT Spring Boot** — it's a **Kafka Connect SMT plugin JAR** (Lenses `GCPStorageSinkConnector`), no `main`/`Application`. (Prior doc 01 mislabels it.)
- **CA/MX filter Javadoc lies:** the comment says "or-if-header-missing" but the code inherits the **strict** base (header-less dropped). Only the **US** filter is the catch-all. Know the code, not the comment.
- **Audit body `headers` copies ALL request headers unmasked** — incl. `WM_SEC.*` / `Authorization`. Real secret/PII leak; raise proactively, fix = mask at capture.
- **"Sub-5ms" is added overhead on the audited API, NOT audit freshness** (which is minutes, `flush.interval=600s`). Be precise which latency you quote.
- **3x read amplification is a deliberate isolation trade-off, not free** — at ~10x volume it flips toward a single branching connector.
- **Version drift:** a shield report shows `spring-boot-starter-web 3.2.8` but the pom parent is **3.5.12** (effective 3.5.x); the report is an older snapshot. State **3.5.12 / Java 17**.
- Minor smells to acknowledge if asked: `AppUtil.addingHeaders` hardcodes `WM-Site-Id=US` default; `request/response_size_bytes` computed from `toString().getBytes().length` (meaningless); `env_properties.yaml` dev block leaks a local `gcskey.json` path (non-prod placeholder; prod uses `secret.ref://`).

### Bullet 2 — Common Starter JAR
- **It is NOT a Spring Boot starter.** No `src/main/resources`, no `spring.factories`, no `AutoConfiguration.imports`. Consumers must component-scan `com.walmart.dv.*` **and provide a `WebClient` bean.** Lead with this honesty caveat.
- **The lone SB 2.7.11 / Java 11 / javax.servlet outlier** vs SB 3 / Java 17 / jakarta consumers. The pom *declares* `jakarta.servlet-api 6.1.0` "provided" but the code imports `javax.servlet`; cross-version reuse works only because NRTI **excludes webflux** and supplies its own WebClient. Most likely place to get cornered — clean fix is a jakarta rebuild.
- **No masking:** `getServiceHeaders()` copies every header incl. `Authorization`/`WM_SEC.*`; CCM `logging.security.mask.enable=false`. Same leak as Bullet 1, raise proactively.
- **No delivery guarantee at this tier:** fire-and-forget `@Async`, no retry, no DLQ; pool+queue saturation → default **AbortPolicy silently drops** audit logs; `@Async` returns `void` with **no metrics** — only log lines signal a drop.
- **`request_size_bytes`/`response_size_bytes` are meaningless** (servlet object `toString().getBytes().length`), with a dead `Objects.isNull` guard on a primitive `int`.
- **Dead `RestTemplate` import + reactive `WebClient` used with `.block()`** = half-finished, non-reactive design; no body-size cap → heap pressure / broken streaming on large/multipart endpoints.
- **"Spearheaded" is collaborative** (Nayana.BG is pom developer) — own design/reusability/adoption, not sole authorship.
- **Don't attribute the producer's "<5ms / 204-immediately" to this JAR** — the lib's latency win is specifically the `@Async` off-thread hop.
- Endpoint allow-list uses **substring `contains()`** matching (collision-prone, e.g. `/status` matches `/statusReport`); fine in practice, prefix/exact safer.
- `kitt.yaml`/`sr.yaml` are **vestigial deployable-service scaffolding on a non-deployable library**; README is one line. A true org-standard starter would ship docs + auto-config.
- **Version drift:** in-repo pom is `0.0.45`; NRTI consumes `0.0.61`.

### Bullet 3 — Active/Active Multi-Region Kafka
- **"Zero data loss" → reframe as "no observable loss of an acknowledged IAC event under single-region failure."** `enable.idempotence=false` → **at-least-once** with possible duplicates/reorder, NOT exactly-once. Volunteer this.
- **Attribute to `cp-nrti-apis`, NOT audit-api-logs-srv** (whose secondary template is dead code). Claiming audit-srv has failover gets caught instantly.
- **"15-min DR recovery vs 1-hour RTO" conflates RPO/RTO** and has **no in-repo artifact**. The *code* failover is sub-second/per-message/automatic; the 15 min is **operational/config-level** (CCM region-pin flip / cluster health-back) from DR game-days vs an old ~1-hour manual runbook. Present those as operational figures, not code-proven.
- **`request.timeout.ms=300000` (5 min) undercuts "fast failover"** for slow/black-hole failures; only fast failures give sub-second. Pre-empt with an `orTimeout` mitigation.
- **DSC publish is fire-and-forget (no `.join()`) and returns 201 even on total failure** — inconsistent with IAC's block-and-503. Own it, don't hide it.
- **`messageId` is client-supplied** → dedup correctness depends on suppliers sending globally-unique IDs; collision → wrongful drop. Mitigation: namespace dedup by `supplierId+messageId`.
- **NRTI is producer-only (no `@KafkaListener`)** — consumer-side DR/offset continuity lives in downstream services; can't claim end-to-end consumer failover as your own code.

### Bullet 4 — Spring Boot 3 / Java 17 Migration
- **Resume "3.2" but pom is parent 3.5.14 / BOM 3.5.7.** Open with the correction or get caught on `cat pom.xml`.
- **No Spring Security in the repo** — prior prep docs claiming a `WebSecurityConfigurerAdapter→SecurityFilterChain` migration are **FALSE for this repo**. Reframe as gateway-auth + servlet filters.
- **No RestTemplate in the repo** — prior docs claiming a `RestTemplate→WebClient` migration are **FALSE**; WebClient was already the client.
- **Specific PR/count claims are not verifiable** (e.g. "35 `Collectors.toList()` replaced," "PR #1312: 158 files/145 imports/42 test files," no single labeled migration PR in git log). **Defensible counts only:** 149 `jakarta.*` refs, 2 residual `javax.*`, 14 `.toList()`, 19 remaining `Collectors.toList()`.
- **Flagger gate is 5xx-only** — blind to semantic (wrong-200) and latency regressions; credit R2C/Automaton in stage. A Hibernate enum bug **was caught in stage**.
- **`maxWeight: 50`, not 100** — "10%→100%" is true end-to-end (ramp to 50% then promote to 100%) but state it precisely.
- **"Zero customer-impacting issues" is a rollout-design property, not "zero bugs."** Claiming zero bugs is dishonest and easily probed.
- **Both webflux and tomcat starters present** — explain WebClient-on-servlet-stack with `.block()`, not a contradiction.
- The consumed `dv-api-common-libraries 0.0.61` is itself **still SB2.7/Java 11/javax**; the pom excludes its webflux starter to stop the old reactive starter leaking in — a cross-version coexistence detail to be ready for.

### Bullet 5 — DC Inventory Search API
- **"Factory pattern for multi-site (US/CA/MX)" has NO backing `*Factory` class** — only framework factories (`DefaultKafkaProducerFactory`, MapStruct `Mappers`). Multi-site = per-region deploy + CCM config (both `wmSiteId` and country code default to `US` in this repo). **The single biggest overclaim — pre-empt it.**
- **"OpenAPI design-first" is real as a process but NOT enforced by codegen for DC** — DC/store controllers are **hand-written**; only items-assortment uses the `spring` generator; the `openapi` generator merely bundles the spec.
- **DC feature largely authored by other engineers** (Keshav Gatla, Ambiorix Cruz Angeles). Avoid claiming sole end-to-end authorship.
- **Root `api-spec.yaml` drifted from deployed routes** — advertises plural `/stores`,`/volts`, omits `/dc`; deployed routes are singular `/store`,`/dc`. Source of truth is `api-spec/schema/openapi.json`. If they open the spec expecting the DC contract, they'll find drift.
- **"30% faster" is an unmeasured critical-path-compression estimate**, not an instrumented A/B metric. Say so.
- **Endpoint returns HTTP 200 (a read), not 201**; EI call is an unusual **GET-with-body**; `.block()` on a reactive WebClient in MVC is a real thread-starvation risk; **no batch-size cap on DC `values`** (unlike store status capped at 100).

---

### Quick-reference: code anchors you can cite verbatim
- **Audit producer:** `audit-api-logs-srv`, SB 3.5.12/Java 17; `AuditLoggingController.saveApiLog` → 204; `ExecutorPoolService` = `Executors.newCachedThreadPool()`; key `AuditKafkaPayloadKey.getKafkaKey()` = `serviceName + "/" + endpoint`; topic `api_logs_audit_{env}`; Avro `log.avsc`, 19 fields, namespace `com.walmart.dv.audit.model.api_log_events.LogEvent`.
- **Audit sink:** Kafka Connect `kcaas-base-image:11-major`, Lenses `GCPStorageSinkConnector` 1.64; `kc_config.yaml` 3 connectors, `errors.tolerance=all`, DLQ, `RETRY max.retries=5`; `BaseAuditLogSinkFilter implements Transformation`; KCQL `PARQUET PARTITIONBY service_name,_header.date,endpoint_name` → `audit-api-logs-{us|ca|mx}-prod`.
- **Common JAR:** `com.walmart:dv-api-common-libraries`, parent `spring-boot-starter-parent 2.7.11`, Java 11; `AuditLogAsyncConfig` core6/max10/queue100; `LoggingFilter extends OncePerRequestFilter @Order(LOWEST_PRECEDENCE)`; `AuditHttpServiceImpl` WebClient `.block()`.
- **NRTI failover:** `cp-nrti-apis/.../NrtKafkaProducerServiceImpl.java`; `NrtKafkaProducerConfig` 4 templates (IAC + DSC, primary + secondary); IAC lines 67-92 `.exceptionally → handleFailure().join()`; DSC lines 104-151 no `.join()`; ccm.yml acks=all, retries=10, `enable.idempotence=false`, `request.timeout.ms=300000`.
- **Migration:** pom parent `3.5.14`, BOM `3.5.7`, Java 17; 149 `jakarta.*` / 2 `javax.*`; `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` in `ParentCompanyMapping`; Flagger in `kitt.yml` stepWeight 10 / maxWeight 50 / 5xx-rate gate threshold 1%.
- **DC inventory:** `DcInventoryController.getDcInventory`, `POST /dc/inventory/status` → 200 `DcInventoryStatusResponse`; EI `EI-PIT-BY-ITEM-INVENTORY-LOOKUP`, GET-with-body; `HttpServiceImpl` WebClient `.timeout(10s)` + `Retry.backoff(3,100ms,max2s)` + `.block()`; InventoryType enum = {PROMO, TURN}.
