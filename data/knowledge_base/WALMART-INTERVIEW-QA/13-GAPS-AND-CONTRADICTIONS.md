# 13 — Master Reconciliation Ledger: Gaps, Contradictions & Cross-Doc Consistency

> **Purpose & how to use this doc in the room.** This is the *consistency referee* for the whole prep set. When a panelist quotes a number back to you — from your résumé, or from a thing you said ten minutes ago — this is the single page that tells you (a) which version is **canonical** (= what the CODE actually says), (b) where your own résumé/older docs **disagree with the code or with each other**, and (c) the **one-sentence self-correction** to say out loud. The move is always identical: *state the precise code truth first, then the trade-off, then the fix.* Volunteering a gap reads as senior signal; getting caught on one reads as inflation.
>
> Every claim below is grounded in real source under `/Users/a0g11b6/Desktop/walmart`, with `file:line` you can cite verbatim. Where a number is **not in the repo** (provisioned by KaaS, or an ops/game-day figure), it is flagged explicitly — never invent one; answer those with a sizing **formula**.

**Severity legend (used throughout):**
- 🟥 **INSTANT-TELL** — a flat factual claim the code *contradicts*. If you assert it and they open the file, you are caught. Pre-empt these.
- 🟧 **REFRAME** — directionally true but the résumé wording over-promises; restate precisely.
- 🟨 **SOFT-ESTIMATE** — a real number that lives in ops/game-days/estimation, not in code; label it as such.

---

## A0. Cross-doc contradiction matrix — where TWO of your OWN sources disagree

> This is the highest-value section and the one the old version of this doc was missing entirely. These are not résumé-vs-code gaps; these are places where **two of your own documents (or the résumé and a doc) state different things**. If a panel cross-reads your notes, this is what would embarrass you. For each: the two conflicting sources, what the **code** says (CANONICAL), and the resolution.

| # | Contested fact | Source A says | Source B says | CODE (CANONICAL) | Resolution (say this) | Sev |
|---|---|---|---|---|---|---|
| A0.1 | **Spring Boot version — but WHICH service?** | 00-INDEX B.1 diagram: audit-srv = "SB **3.5.12**"; résumé: "2.7→**3.2**" | doc 09 / 00-INDEX E: a shield report shows `spring-boot-starter-web` **3.2.8**; BULLET-4: cp-nrti = **3.5.14 / BOM 3.5.7** | **Two different services.** `cp-nrti-apis/pom.xml:8` parent **3.5.14**, `:36` `springboot.version` **3.5.7** (BOM), `:26` java 17. `audit-api-logs-srv/pom.xml:15` parent **3.5.12**, `:57` java 17. The 3.2.8 is a stale Snyk/shield snapshot of one transitive starter, not the effective version. | "Résumé '3.2' is stale shorthand — I led the 2.7→3.x jump and the service is current: **cp-nrti is on 3.5.14 parent / 3.5.7 BOM**, the audit service is on **3.5.12**. The 3.2.8 a scan shows is an old report, superseded by the BOM." Never carry one number across both services. | 🟥 |
| A0.2 | **NRTI HPA min/max pods** | 00-INDEX / earlier notes sometimes quote **4/8** | doc 09 itself flags 4/8 vs 6/12 | `cp-nrti-apis/kitt.yml`: **prod** stage `:60-62` `min: 6 / max: 12 / cpuPercent: 60` (cluster_id `eus2-prod-a30, scus-prod-a63`); **stage** `:157-159` `min: 4 / max: 8 / 60`; dev `:99-101` `2/4`; sandbox/iacstage `:308-310,:371-373` `1/2`. | "**NRTI prod is min 6 / max 12 at 60% CPU**; the 4/8 you may have seen is the **stage** profile. Audit-srv prod is separately min 4 / max 8 at 60%." Don't quote 4/8 as NRTI prod. | 🟥 |
| A0.3 | **IAC failure HTTP status** | 00-INDEX A.B.2 + several docs say IAC returns **503** on total failure | canonical-facts note says "HTTP **500/503**" | `NrtiUnavailableException` is annotated `@ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)` = **HTTP 500** (`cp-nrti-apis/.../exception/handlers/NrtiUnavailableException.java`). There is no 503 in code. | "In code the IAC dual-region failure surfaces as **HTTP 500** via `NrtiUnavailableException(@ResponseStatus(INTERNAL_SERVER_ERROR))`. I sometimes say 503 loosely meaning 'retryable unavailable' — but the literal status is 500. (Arguably it *should* be 503 + `Retry-After`; that's a fix I'd make.)" | 🟧 |
| A0.4 | **`api-spec.yaml` advertised routes vs deployed** | Root `cp-nrti-apis/api-spec.yaml` advertises **plural** `/stores/...`, `/volts/...` and **omits `/dc`** | Bullet 5 / deployed controllers use **singular** `/store`, and `POST /dc/inventory/status` exists | `api-spec.yaml:16,83,144,203,...` = `/stores/inventoryActions`, `/stores/inventories/statuses`, `/volts/...`; **no `/dc` path in that file.** Hand-written `DcInventoryController` serves `POST /dc/inventory/status`. Source of truth is `api-spec/schema/.../openapi.json`. | "The root `api-spec.yaml` is a drifted draft — it lists plural `/stores` and `/volts` and doesn't even contain `/dc`. The contract that's actually built/deployed lives under `api-spec/schema/`. If you open the root yaml expecting the DC contract, you'll find drift — that's a doc-hygiene gap I'd close." | 🟧 |
| A0.5 | **DSC secondary-region failover target** | Docs describe "DSC primary → DSC secondary template" (symmetric with IAC) | code review of `NrtKafkaProducerServiceImpl` | **BUG:** DSC's `handleFailure(...)` at `NrtKafkaProducerServiceImpl.java:137` re-sends via `kafkaSecondaryTemplate` — which is the field declared `:39-41` bound to `NRT_KAFKA_SECONDARY_TEMPLATE` (the **IAC** secondary), **not** `kafkaDscSecondaryTemplate` (`:48-50`, `DSC_KAFKA_SECONDARY_TEMPLATE`). | "There's a genuine bug: on a DSC primary-region failure the retry goes through the **IAC** secondary template, not the DSC secondary — wrong broker config object. I'd cite this as a real find from reading the failover path closely." (Only volunteer if asked about DSC failover internals — it's a strong senior signal.) | 🟥 |
| A0.6 | **"Events/day" volume** | Résumé summary "**2M+**"; 00-INDEX "millions" | a GCC README says "**10M+**" | Not in code (platform metric). doc 07:166-171 derives audit ≈ single-digit millions/day per service (~15 req/s × 86,400 ≈ 1.3M/day, cross-checked vs sink `flush.count=5000`). | "Walmart audit is **single-digit millions/day** in aggregate; the **10M+** is a *different* project (GCC), don't cross-wire them. I can derive the audit figure: ~15 req/s × 86.4k s ≈ 1.3M/day/service." | 🟨 |

---

## A. Number & claim mismatches (résumé vs code vs older docs) — the full ledger

> Columns: **what the résumé says | what older docs say | what the CODE says (CANONICAL, with file:line) | one-line reconciliation | severity.** Reordered so 🟥 instant-tells sit at the top.

| Topic | Résumé says | Older docs say | CODE says (CANONICAL) | Reconcile (say this) | Sev |
|---|---|---|---|---|---|
| **"Spring Boot starter JAR"** | "reusable **starter** JAR" | doc 12 proves library-not-starter | `dv-api-common-libraries` has **NO `src/main/resources`** at all → no `spring.factories`, no `META-INF/spring/...AutoConfiguration.imports`. `pom.xml:7` artifact `dv-api-common-libraries`, `:18` parent `2.7.11`, `:30` java 11. Consumers must `@ComponentScan com.walmart.dv.*` + supply their own `WebClient`. | "It's a shared **library**, not an auto-configured **starter** — there's no `src/main/resources`/`spring.factories`. I lead with that correction." | 🟥 |
| **"Spring Security migration"** (implied by "SB3 migration") | — | older prep claimed `WebSecurityConfigurerAdapter → SecurityFilterChain` | **No Spring Security anywhere** in `cp-nrti-apis` — no `spring-boot-starter-security`, no `SecurityFilterChain`/`WebSecurityConfigurerAdapter`. Auth = gateway `WM_SEC.*` headers + custom servlet filters (`RequestFilter`, `XssFilter`, `NrtCorsFilter`). | "There's **no Spring Security in the repo** — so there was no Security-config migration. Auth is gateway headers + servlet filters. Don't let me claim a Security migration." | 🟥 |
| **"RestTemplate → WebClient migration"** | — | older prep implied a client migration | **No `RestTemplate` in `cp-nrti-apis`** — WebClient was already the HTTP client (`HttpServiceImpl`). (Note: the common JAR has a *dead `RestTemplate` import* but uses `WebClient.block()`.) | "WebClient was already in place — there was no RestTemplate→WebClient migration to claim." | 🟥 |
| **"Factory pattern for multi-site"** | "**factory pattern** for US/CA/MX" | Bullet 5 / doc 10 confirm none | **No `*Factory` class** for multi-site. Only framework factories exist (`DefaultKafkaProducerFactory`, MapStruct `Mappers`). Multi-site = same artifact per region + CCM config (`SiteIdFilterAspect` AOP, `SiteIdCCMConfig`). Both `wmSiteId` and country default to `US` in-repo. | "There's **no GoF `*Factory`** — multi-site is per-region deploy + CCM config + DI/AOP. I'd build a real site-keyed strategy/registry if we needed runtime multi-tenancy." | 🟥 |
| **Spring Boot version** | "2.7 → **3.2**" | 3.5.12 (audit), 3.2.8 (shield), 3.5.14 (cp-nrti) — three strings! | cp-nrti `pom.xml:8`=**3.5.14** parent, `:36`=**3.5.7** BOM; audit `pom.xml:15`=**3.5.12**. | "'3.2' is stale; cp-nrti is 3.5.14/BOM 3.5.7, audit 3.5.12. See A0.1." | 🟧 |
| **"Active/Active … zero data loss"** | "active/active, **zero data loss**" | reframed in BULLET-3 | NRTI: `ccm.yml` `acks=all`, `retries=10`, **`enable.idempotence=false`** → **at-least-once** (dups/reorder possible, NOT exactly-once). Failover is producer dual-**write on failure**, not continuous mirroring. | "Active/active at the *service* layer; cross-region redundancy is **failover-triggered**. It's at-least-once → reframe to '**no observable loss of an acknowledged event under single-region failure**', dedup consumer-side." | 🟧 |
| **Audit durability (separate story!)** | (folded into "zero loss") | flagged in doc 10 | Audit producer `KafkaProducerConfig.populateConfigProperties:85-119` sets **only** bootstrap/serializers/schema-url/`auto.register=false`(+optional SSL). **No `acks`, no `enable.idempotence`, no `retries`** → client defaults → **effective acks=1** → leader-failure loss window. (A CCM yml may *declare* acks but `@ManagedConfiguration` never reads it.) | "The audit producer is a **different, weaker** durability story than NRTI: it sets no acks → effective **acks=1**. I'd propose acks=all + min.insync.replicas=2 + idempotence." **Never conflate with NRTI.** | 🟧 |
| **Canary "10% → 100%"** | "Flagger canary **10%→100%**" | doc 10 confirms | `kitt.yml:727` `stepWeight: 10`, `:728` `maxWeight: 50`, `:729` `interval: 2m`, `:735` gate `threshold: 1` (5xx-rate). | "True end-to-end, but precise: **10% steps to 50%, then promote to 100%**. Gate is **5xx-rate at 1%** — blind to wrong-200 and latency." | 🟧 |
| **"<5ms P99"** | "**sub-5ms** P99 latency impact" | 00-INDEX B.1 note | Overhead = two async hops: common-JAR `@Async` POST (off Tomcat thread) + audit-srv `AuditLoggingController.saveApiLog:58-60` returns **204** then `ExecutorPoolService:10` fires. Freshness ≠ overhead: sink `flush.interval=600s`. | "<5ms is the **overhead added to the audited API** via the async hops — **not** audit freshness, which is **minutes** (flush 600s). Two separate sentences, always." | 🟧 |
| **"15-min DR vs 1-hour RTO"** | "**15-min** DR" | doc 10 ⚠️, BULLET-3 | **Not in code.** Conflates RPO/RTO; code failover is sub-second/per-message/automatic. 15-min is operational (CCM region-pin flip / cluster-health-back) from DR game-days. | "Code failover is **sub-second**; the **15-minute** figure is an **operational** game-day number for full regional recovery, vs an old ~1-hour manual runbook. Not code-proven." | 🟨 |
| **"2 weeks → 1 day" adoption** | Bullet 2 | estimate | Not in code. | "An adoption estimate from CCM flag-on vs bespoke audit code — not an instrumented metric." | 🟨 |
| **"30% faster" parallel integration** | Bullet 5 | estimate | Not instrumented. | "Critical-path-compression estimate from design-first parallel client work, not an A/B." | 🟨 |
| **Partition count / RF / min.insync / retention** | — | 09 "sized by formula" | **Not in repo** — provisioned via KaaS. Broker list shows **3 brokers/region** ⇒ RF almost certainly 3. | "Those are **KaaS-provisioned**, not in the repo. RF≈3 from the 3-broker list; partitions I'd **size by formula** (peak throughput ÷ per-partition ceiling, headroom ×2-3), not invent." | 🟨 |

---

## B. Internal contradictions to reconcile (with code anchors)

> Reordered: 🟥 instant-tells first.

1. 🟥 **"Spring Boot starter JAR" (Bullet 2) → it is a plain library.** No `src/main/resources`, no `spring.factories`, no `AutoConfiguration.imports`; `pom.xml` parent 2.7.11 / java 11 (`dv-api-common-libraries/pom.xml:18,30`). Async pool is a hand-wired `ThreadPoolTaskExecutor` (`AuditLogAsyncConfig.java:19-22`, core 6 / max 10 / queue 100), **not** auto-config. **Always self-correct to "library" up front.**

2. 🟥 **"Factory pattern for multi-site" (Bullet 5) → no `*Factory` class.** Site behavior is `SiteIdFilterAspect` (AOP `@Around`) + CCM (`SiteIdCCMConfig`). **Reframe as "config + DI/AOP; I'd build a real site-keyed strategy/registry for runtime multi-tenancy."**

3. 🟥 **Failover lives in `cp-nrti-apis`, NOT audit-srv.** Audit-srv's `kafkaSecondaryTemplate` bean **exists but is DEAD CODE**: declared `KafkaProducerConfig.java:60-63`, autowired into `KafkaProducerService`, but the send path only ever calls `kafkaPrimaryTemplate.send(...)` in a **log-only try/catch** — the secondary is never `.send()`-ed. **Never attribute in-code Kafka failover to the audit producer.**

4. 🟧 **"Active/Active" (Bullet 3) → failover-triggered, with an IAC/DSC asymmetry that is the real sharp edge.** Happy-path messages live in **one** region; the other is written **only on the send-future's `.exceptionally`** (`NrtKafkaProducerServiceImpl.java:69` primary send → `:84-89` IAC `.exceptionally(...).join()` → `:159-175` `handleFailure` re-sends to secondary). The asymmetry:
   - **IAC** (`:84-92`): `.exceptionally` re-sends to secondary, then the **outer `.join()` blocks the Tomcat thread**; total failure throws `CompletionException` → `NrtiUnavailableException` → **HTTP 500** (`:90-92`). Caller learns it failed.
   - **DSC** (`:113-126`): `.thenAccept(...).exceptionally(...)` with **NO terminal `.join()` and NO rethrow** → fire-and-forget → controller returns **201 even when both regions fail**. (And `:137` retries via the *IAC* secondary — see A0.5.)
   → "Active/active at the service layer; cross-region is failover-triggered. IAC is blocking + surfaces failure as 500; DSC is best-effort + returns 201 regardless — a real asymmetry I'd flag and fix with a DSC failure metric + DLQ."

5. 🟧 **"<5ms P99" placement (Bullet 1).** Keep two latencies in **separate sentences**: the <5ms is **added overhead** on the audited API (the `@Async` hop in the JAR + the 204-then-publish in audit-srv); **freshness is minutes** (`flush.interval=600s` in the Connect sink). Quote the right one.

6. 🟧 **"Three-tier system" ownership (Bullets 1/2/5).** Common-JAR pom developer is **Nayana.BG**; DC inventory files largely authored by **Keshav Gatla** and **Ambiorix Cruz Angeles**. **Say the identical slice every round: "I designed/owned ___ (capture lib design + reusability/adoption, the SB3 migration, HPA/Snyk/logging hardening), partnered with the team on ___."**

---

## C. Genuine gaps the prep must own (each with the honest answer + where it's resolved)

> Self-contained: each gap gives the one-line answer AND the precise sibling anchor, so you don't have to leave the page.

1. **Consumer side of the topics.** NRTI is **producer-only** (no `@KafkaListener` in `cp-nrti-apis`); audit-srv is producer-only too. Consumption/dedup/offset-DR live downstream. → "I own the produce side; consumer failover/dedup is a downstream/topology concern, not my code." (Resolved: 00-INDEX E Bullet-3; doc 11 consumer Q&A.)

2. **Schema Registry ops (audit only).** `auto.register.schemas=false` (`KafkaProducerConfig.java:92`) → schemas are pre-registered out-of-band; compatibility mode is **BACKWARD**; producer fails fast on an unregistered schema. → "Avro + Confluent SR, `auto.register=false`, BACKWARD compat, schema changes gated in CI." (Resolved: doc 17 Avro wire-format + compat section; doc 06 basics.)

3. **Cost reframe ("replaced Splunk").** No dollar figure exists; give it qualitatively: **Splunk license + ingest** vs **GCS storage** (buckets `audit-api-logs-{us|ca|mx}-prod`, project `wmt-dv-luminate-prod`) **+ BigQuery query** over external tables on the Parquet. → "Trade per-GB Splunk ingest for cheap object storage + pay-per-query BigQuery, plus supplier self-service. Qualitative — I don't have an audited dollar number." (Resolved: 00-INDEX B.1; doc 07 cost section.)

4. **Test strategy depth.** Stage gate runs (kitt.yml `:234` `R2C` contract, `:249` `automaton` perf, `:269` Resiliency/RaaS) + the 5xx Flagger gate. → "Unit (JUnit/Mockito), R2C contract, Automaton perf, RaaS resiliency in stage; the Flagger prod gate is **5xx-only**, so semantic regressions rely on the stage contract tests." (Resolved: BULLET-4 rollout; doc 09 test Q&A.)

5. **Bad-data recovery.** Sink has `errors.tolerance=all` + DLQ + `RETRY max.retries=5`; producer-side has **no DLQ**. → "If bad Parquet lands in GCS: replay from the sink DLQ + reprocess the affected BigQuery partition. Producer-side has no DLQ today — a gap I'd add (observe the future + app DLQ)." (Resolved: 00-INDEX quick-ref sink anchors.)

6. **HPA prod vs stage (don't quote the wrong profile).** NRTI **prod min6/max12@60%** (`kitt.yml:60-62`), **stage min4/max8@60%** (`:157-159`); audit-srv prod min4/max8@60%. → See A0.2. (Resolved: doc 09 HPA/Little's-Law.)

7. **`api-spec.yaml` route drift.** Root yaml advertises plural `/stores`,`/volts`, omits `/dc`; deployed routes singular `/store`,`/dc`; truth in `api-spec/schema/`. → See A0.4. (Resolved: 00-INDEX E Bullet-5.)

8. **The DSC-uses-IAC-secondary bug + DSC 201-on-failure.** `NrtKafkaProducerServiceImpl.java:137`. → See A0.5 / B.4. A strong "I read the failover path closely" signal.

9. **3x read amplification justification.** Audit sink runs **3 connector instances** (US catch-all + `-ca` + `-mx`), each `tasks.max=1` ⇒ 3 effective consumer groups ⇒ the whole topic is read **3×**. → "Deliberate isolation/residency trade-off; at ~10× volume it flips toward one branching connector." (Resolved: 00-INDEX B.1; doc 07.)

---

## D. Tape-to-monitor: the 12 things to never get wrong

1. **Two Kafka worlds, never mixed.** Audit = **Avro + Confluent Schema Registry**, key = `serviceName + "/" + endpoint` (`AuditKafkaPayloadKey.getKafkaKey`). NRTI = **Spring `JsonSerializer`, NO registry**.
2. **NRTI partition keys (the trap):** **IAC has a NULL partition key** — `messageId` is set as a **header only** (`IacServiceHelper.java:189` `.setHeader(AppConstants.MESSAGE_ID, ...)`, no `KafkaHeaders.KEY`) ⇒ **no broker-level ordering**. **DSC is keyed on `tripId`** — the *only* place `KafkaHeaders.KEY` is set (`DscServiceHelper.java:264`). Never say "key messageId/tripId" as if both are keys.
3. **Failover lives in `cp-nrti-apis`, NOT audit-srv** (audit's secondary template is **dead code**, `KafkaProducerConfig.java:60-63`).
4. **Two durability stories:** audit = **effective acks=1** (no acks set, `KafkaProducerConfig:85-119`); NRTI = **acks=all + retries=10 + idempotence=false** = at-least-once. Reframe accordingly; don't merge them.
5. **IAC blocks → HTTP 500; DSC fire-and-forget → 201 even on dual failure.** (`NrtKafkaProducerServiceImpl.java:84-92` vs `:113-126`.) Code status is **500** (`@ResponseStatus(INTERNAL_SERVER_ERROR)`), not 503.
6. **<5ms = added overhead on the audited API; freshness = minutes** (`flush.interval=600s`). Separate sentences.
7. **Common JAR is a LIBRARY, not a starter** (no `src/main/resources`); SB **2.7.11 / Java 11** — the lone outlier; in-repo `0.0.45`, consumed `0.0.61`.
8. **Pool bounded vs unbounded:** common-JAR `@Async` = bounded core6/max10/queue100 + default **AbortPolicy** (silently drops audits on saturation, `AuditLogAsyncConfig.java:20-22`); audit-srv = **unbounded** `Executors.newCachedThreadPool()` (`ExecutorPoolService.java:10`, OOM-under-burst).
9. **No Spring Security, no RestTemplate, no `*Factory`** in `cp-nrti-apis`. Don't claim migrations/patterns that don't exist.
10. **Canary:** stepWeight 10 → maxWeight 50 → promote 100; gate = **5xx-rate @ 1%** (blind to semantic + latency).
11. **HPA:** NRTI prod **6/12**, NRTI stage **4/8**, audit prod **4/8** — all @60% CPU. Quote the right profile.
12. **Soft numbers get a label** (15-min DR, 2wk→1d, 30% faster, events/day, partitions/RF/retention): "operational / estimate / KaaS-provisioned — not in code." Attribution: "I designed/owned ___, partnered on ___" — same slice every round.

---

### Quick-reference code anchors for THIS doc (cite verbatim under cross-examination)
- **NRTI failover:** `cp-nrti-apis/.../services/impl/NrtKafkaProducerServiceImpl.java` — `:69` IAC primary send, `:84-89` IAC `.exceptionally(...).join()`, `:90-92` `CompletionException → NrtiUnavailableException`, `:112` DSC primary send, `:121-126` DSC `.exceptionally` (no `.join()`), `:137` DSC `handleFailure` re-sends via **IAC** `kafkaSecondaryTemplate` (bug, A0.5), `:159-175` IAC `handleFailure`.
- **NRTI keys:** IAC null key — `IacServiceHelper.java:189` `MESSAGE_ID` as header; DSC keyed — `DscServiceHelper.java:264` `KafkaHeaders.KEY, buildTripId(...)`.
- **NRTI status:** `NrtiUnavailableException` `@ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)` = **500**.
- **NRTI tuning:** `ccm.yml` acks=all / retries=10 / `enable.idempotence=false` / lz4 / linger 20 / batch 8192 / `request.timeout.ms=300000` / max.request.size 10,000,000.
- **NRTI HPA + canary:** `kitt.yml:60-62` prod 6/12@60, `:157-159` stage 4/8@60, `:727` stepWeight 10, `:728` maxWeight 50, `:729` interval 2m, `:735` 5xx threshold 1.
- **Audit producer:** `audit-api-logs-srv` SB **3.5.12** (`pom.xml:15`), java 17 (`:57`); `AuditLoggingController.saveApiLog:58-60` → 204; `ExecutorPoolService.java:10` `newCachedThreadPool()`; `KafkaProducerConfig.populateConfigProperties:85-119` sets only bootstrap/serializers/SR-url/`auto.register=false`(+SSL) — **no acks/idempotence/retries**; `:60-63` dead `kafkaSecondaryTemplate`.
- **Common JAR:** `dv-api-common-libraries/pom.xml:7` artifact, `:18` parent **2.7.11**, `:30` java 11, `:7` version **0.0.45** (consumed **0.0.61** at `cp-nrti-apis/pom.xml:471`); `AuditLogAsyncConfig.java:20-22` core6/max10/queue100; **no `src/main/resources`**.
- **cp-nrti migration:** `pom.xml:8` parent **3.5.14**, `:36` BOM **3.5.7**, `:26` java 17.
- **api-spec drift:** `api-spec.yaml:16,83,144,203` plural `/stores`,`/volts`, no `/dc`.
