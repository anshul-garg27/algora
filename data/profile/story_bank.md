# Story Bank — Anshul Garg

> **Canonical, verified career narrative.** Every fact below is real and reusable. The coach must ground every answer in these cards and **never invent specifics** (numbers, tech, names, dates). If a detail is not in a card, do not assert it — speak in ranges or say it would need checking.
>
> **Persona:** First name **Anshul** is kept for the voice persona. All contact PII (phone, email, personal site, LinkedIn, GitHub) is redacted — the coach never needs contact info.
>
> **Career arc:** PayU (intern → SE, loan disbursal) → Good Creator Co. (SE-I, sole architect of 6 production services, Feb 2023–May 2024) → Walmart Data Ventures (SE-III, supplier-facing data APIs, June 2024–present).

---

## How to use this bank

- **Tag** = stable reference (W = Walmart, G = Good Creator Co., P = PayU). Use tags to pick primary + backup stories.
- Each card gives: **Situation**, **Action (Anshul's specific ownership slice)**, **Stack**, **Result (quantified)**.
- Numbers are conclusions, not labels. State them flat: "dropped from 30s to 12s." No TED-talk closers.
- "Sole architect" / "I led" / "I owned" claims are real for the stories so tagged — use them confidently.

### Story priority (pick in this order)

- **PRIMARY — pick from these FIRST** (most-practiced, deepest, most defensible): **W1, W2, W3, W5, W8, W9, G1, G2, G3, G5, G6.** Whenever a question maps to one of these, use it.
- **SECONDARY — coverage and backup** (use when no PRIMARY fits the principle, or as the second example for the same competency): **W7, W10, W12, G8, P1, P2, P3, P4.**
- **HONEST GAP RULE (critical):** if a question genuinely doesn't map to any card — e.g. a pure "tell me about formally mentoring someone to a promotion" ask — do **not** stretch a story into something it isn't, and do **not** invent specifics. Say it honestly and pivot to the closest real thing: _"I haven't done exactly that, but the closest is —"_ then use a real card. For "developing others / raising the bar," the honest real angle is **force-multiplier work**: W2 (a shared library three teams adopted, cutting their integration from 2 weeks to 1 day) and W8 (design-first spec that let other teams build in parallel) — frame it as team/org-level, not 1:1 mentoring. An honest near-match always beats a fabricated perfect-match: you can defend what's real, you can't defend what isn't.

---

# WALMART — Data Ventures / Luminate / NRT (SE-III · June 2024–present)

Supplier-facing data APIs for Pepsi, Coca-Cola, Unilever, P&G. Core stack across the org: Spring Boot 3, Java 17, Kafka 3.x, Kafka Connect, GCS, BigQuery, Cosmos DB, PostgreSQL, Apollo Federation GraphQL, Dynatrace, Prometheus, Grafana, Flagger, WCNP/Istio. Platform-wide SLA target 99.9%, P95 ≤ 200ms.

### W1 — The 5-day silent Kafka failure

**Company:** Walmart Data Ventures

**Situation.** The audit-logging pipeline (Kafka Connect → GCS sink) silently stopped writing data. No error surfaced — it took 5 days to root-cause because there was no consumer-lag monitoring.

**Action.** Anshul traced a five-link failure chain: null SMT headers caused a `SinkRecord` NPE → Connect silently retried → KEDA's poll-timeout autoscaler read the stall as load and scaled up → the extra workers drove JVM heap to OOM. He fixed it with an SMT null-guard plus bounded backoff, then added guardrails so it could never go silent again: a Micrometer null-header counter, a Grafana alert at 0.1%, and a CI chaos test. The lesson he tells is "'is it running?' is not monitoring — 'is it processing correctly without losing data?' is."

**Stack:** Kafka Connect, SMT, GCS sink, KEDA, JVM, Micrometer, Grafana, CI chaos testing.
**Result.** Zero data loss after replay. Two-tier consumer-lag alerting (warning at 100, critical at 500) added afterward has since caught two issues before they became incidents.

### W2 — Shared library `dv-api-common-libraries` (kills Splunk audit cost)

**Company:** Walmart Data Ventures

**Situation.** Three product teams were each duplicating audit-logging code, and audit logging ran through Splunk, which Walmart was decommissioning company-wide (expensive licensing). Suppliers also wanted self-service "why did my request fail?" visibility.

**Action.** Anshul built a reusable Spring Boot starter (auto-configured via `spring.factories`) so any service gets audit logging by adding one Maven dependency. A servlet filter intercepts the request, caches the body with `ContentCachingWrapper`, and fires the audit payload asynchronously (fire-and-forget, no latency hit). Internals: thread-pool sizing 6/10/100, idempotent Kafka producer, Avro serialization, three-tier pipeline (library → Kafka publisher → Kafka Connect GCS sink with US/CA/MX routing → BigQuery external tables suppliers query directly). Shipped design-to-prod in ~5 weeks.

**Stack:** Spring Boot starter, `spring.factories`, servlet filter, Kafka, Avro, Kafka Connect, GCS Parquet, BigQuery external tables.
**Result.** Integration time dropped from 2 weeks to 1 day per service. Replaced Splunk audit logging at ~$50K/mo with a custom pipeline at ~$500/mo (~99% cost cut). ~2M events/day, P99 under 5ms, suppliers self-serve debugging.

### W3 — DiscardPolicy feedback (slept on it, then fixed it)

**Company:** Walmart Data Ventures

**Situation.** In design review, a senior flagged that Anshul's `ThreadPoolExecutor` config (`RejectedExecutionHandler.DiscardPolicy` + bounded queue of 100) would silently drop audit records under load.

**Action.** Anshul initially defended the choice, then slept on it and realized the senior was right — silent drops on a customer-facing audit trail were unacceptable. He added a Micrometer queue-depth gauge, an 80%-full warning alert, and switched to `CallerRunsPolicy` so backpressure slows the producer instead of dropping data.

**Stack:** `ThreadPoolExecutor`, `CallerRunsPolicy`, Micrometer.
**Result.** Zero customer-facing drops over the following 90 days. (Good "disagree, then commit / take feedback" story.)

### W5 — Spring Boot 2.7→3.2 and Java 11→17 migration (`cp-nrti-apis`)

**Company:** Walmart Data Ventures

**Situation.** The main supplier API service (`cp-nrti-apis`) was on EOL Spring Boot 2.7 / Java 11 with CVEs that couldn't be patched without upgrading. Anshul volunteered to lead the migration.

**Action.** 158 files changed. He drove the `javax`→`jakarta` rename (74 files), and made the key call: use `.block()` on the new WebClient rather than a full reactive rewrite — that kept it a framework upgrade (~3–4 weeks) instead of an architecture rewrite (~3 months). Handled Hibernate 6's stricter enum mapping with `@JdbcTypeCode(SqlTypes.VARCHAR)`, spent 2 days debugging a Mockito WebClient chain in tests, and rolled out via Flagger canary (10→25→50→100% over ~5 days).

**Stack:** Spring Boot 3.2, Java 17, jakarta namespace, WebClient `.block()`, Hibernate 6, Mockito, Flagger/Istio canary.
**Result.** Zero customer-impacting issues. Production release end of April 2025.

### W7 — DSD real-time delivery notifications

**Company:** Walmart Data Ventures

**Situation.** Direct Store Delivery: suppliers (e.g. Pepsi) drop goods at store docks, but associates only discovered deliveries during periodic 2–4 hour checks, so goods sat unshelved and shelves looked empty. 1,200+ associates across 300+ stores.

**Action.** Anshul actually talked to associates and found only 2 of the 5 DSD lifecycle states are actionable — ENROUTE and ARRIVED — so he notified only on those (skipping PLANNED/STARTED/COMPLETED) to avoid notification fatigue. He wired the cp-nrti-apis events into Walmart's SUMO V3 Mobile Push API, targeting by domain + siteId + role so only the right store's receiving team is paged. Commodity-type mapping (vendor → "Beverage"/"Snacks") is CCM-configurable, no redeploy to onboard a new supplier.

**Stack:** SUMO V3 Mobile Push API, Kafka, cp-nrti-apis, CCM config.
**Result.** ~35% improvement in replenishment timing (gap between ARRIVED event and first inventory scan), tracked via the business team's operational dashboard.

### W8 — DC Inventory Search API (design-first + performance)

**Company:** Walmart Data Ventures

**Situation.** Suppliers had no standardized way to query inventory across Walmart's 30+ distribution centers; every integration was custom and consumers had no contract to build against.

**Action.** Anshul wrote the OpenAPI spec first (an 898-line consolidated spec with examples for success, partial-error, and full-error cases) so consumers could mock and start integrating weeks before the implementation landed (~8K LOC). He used a factory pattern for multi-site config (US/CA/MX, 30+ DCs) and parallelized downstream EI calls with `CompletableFuture`. He reverse-engineered the undocumented internal EI inventory API using Charles Proxy.

**Stack:** OpenAPI design-first, R2C contract testing, factory pattern, CompletableFuture, Charles Proxy.
**Result.** P99 dropped from ~3s to ~800ms via parallel downstream calls. Design-first cut consumer integration time ~30%.

### W9 — Cosmos DB → PostgreSQL migration (Transaction Event History)

**Company:** Walmart Data Ventures

**Situation.** The Transaction Event History API ran on Cosmos DB, whose RU-based pricing was unpredictable; the team had stronger PostgreSQL expertise and other services already ran Postgres on WCNP.

**Action.** Anshul led the persistence-layer migration to PostgreSQL with site-based partitioning (US/CA/MX) and cursor pagination using a base64-encoded composite key, keeping the API contract identical for zero consumer impact. Under design-review pushback he defended cursor pagination over offset, because offset gets progressively slower as you page into millions of rows. He cleared 4 follow-up codegate fixes to ship.

**Stack:** Cosmos DB → PostgreSQL, WCNP, cursor pagination (base64 composite key), site partitioning. (PRs #8 +11.6K LOC, #38 +11.9K CRQ.)
**Result.** Zero-downtime migration, predictable costs, constant-time pagination regardless of page depth. Became the foundation for the later Canada launch.

### W10 — Observability across the platform

**Company:** Walmart Data Ventures

**Situation.** The supplier API platform needed end-to-end observability, and (post-silent-failure) needed alerting that catches "processing-incorrectly," not just "is it up."

**Action.** Anshul built the four-layer setup: Dynatrace distributed tracing with a custom `TransactionMarkingManager` creating child spans per downstream call (via the `traceparent` header), Prometheus alert rules (latency >100ms sustained 12 min, any 5xx in 30s, Kafka consumer lag warning/critical at 100/500, cache latency >50ms), Grafana dashboards, and Flagger canary with metric-based auto-rollback.

**Stack:** Dynatrace, Prometheus, Grafana, Flagger/Istio, Spring Boot Actuator/Micrometer, custom child-span transaction marking.
**Result.** 99.9% uptime SLA upheld. This monitoring is what caught the Spring Boot 3 post-migration behavior and surfaced the heap-OOM trend during the silent-failure incident.

### W12 — Why leaving Walmart (framing only)

**Company:** Walmart Data Ventures

**Situation.** Comes up in intro/closing rounds.

**Action / framing.** Positive only: Anshul wants platform/infrastructure impact at higher scale and the ownership level of an Amazon SDE-3. **Never bad-mouth Walmart.** Phrase as moving toward bigger scope, not away from problems. Avoid the banned "where my instincts break" closers — just say he wants to operate a couple orders of magnitude up.

**Result.** N/A — this is a framing card, not an achievement.

---

# GOOD CREATOR CO. — influencer-marketing analytics SaaS (SE-I · Feb 2023–May 2024)

~5-person backend team. Anshul was sole architect of 6 production services, ~60K+ LOC across Go and Python. Note: say "Good Creator Co.", not "GCC," to interviewers.

### G1 — ClickHouse migration (HERO STORY)

**Company:** Good Creator Co.

**Situation.** The analytics workload was on PostgreSQL taking 10M+ writes/day, and write latency had degraded from ~5ms to ~500ms. Analytics queries were slow and storage/cost were climbing.

**Action.** Anshul moved analytics to ClickHouse behind a RabbitMQ-buffered sinker: a Go channel buffer (cap 10K) flushes in batches of 1000 OR every 5 seconds on a ticker, so ClickHouse gets the large batch inserts its columnar engine wants. Tables use MergeTree partitioned by `toYYYYMM(timestamp)`. He ran a 2-week dual-write window to guarantee zero data loss before cutover.

**Stack:** ClickHouse (MergeTree), RabbitMQ buffered sinker, Go channels + ticker, GORM, dual-write migration.
**Result.** ~99% I/O cut, ~33× throughput, analytics queries 30s → 12s (and elsewhere ~2.5× faster retrieval), storage 500GB → 100GB (~5× compression), ~30% infra cost cut, zero data loss.

### G2 — Beat: distributed social scraping engine

**Company:** Good Creator Co.

**Situation.** GCC needed to aggregate data from 15+ social APIs (8 Instagram, 4 YouTube providers, plus Shopify, GPT, etc.); the prior system was single-threaded, constantly rate-limited, and managed only a few thousand profiles/day.

**Action.** Anshul built Beat: 73 scraping flows, 150+ concurrent workers using multiprocessing for CPU isolation + asyncio/uvloop for I/O. Task coordination uses a SQL queue with PostgreSQL `FOR UPDATE SKIP LOCKED` (atomic pickup, queryable, priority-ordered — no Redis/RabbitMQ needed for tasks). Reliability came from 3-level stacked rate limiting (20K/day, 60/min, 1/sec per handle) and credential rotation with TTL backoff and a Strategy-pattern provider fallback chain.

**Stack:** Python 3.11, FastAPI, asyncio + uvloop, aio-pika, asyncpg, PostgreSQL `FOR UPDATE SKIP LOCKED`, Redis, RabbitMQ.
**Result.** ~10K events/sec, 10M+ data points/day. API costs down ~30% (credential rotation + rate limiting), response times up ~25% (asyncpg connection pooling). Provider outages (previously 2–3 visible/month) became invisible to the business.

### G3 — Stir: data platform (ClickHouse → Postgres sync)

**Company:** Good Creator Co.

**Situation.** Analytics lived in ClickHouse but the SaaS web app read from PostgreSQL, and the old monolithic daily batch meant a profile update could take ~24 hours to appear in the app.

**Action.** Anshul built a 3-layer ELT pipeline: 112 dbt models transform data in ClickHouse → `INSERT INTO FUNCTION s3()` exports JSON to S3 staging (decoupled, retry-able) → an `SSHOperator` downloads and `COPY`s into PostgreSQL with an atomic table swap (RENAME inside a transaction) for zero-downtime, consistent snapshots. 76 Airflow DAGs schedule by business need across 7 tiers — scrape monitoring every 5 min, core metrics every 15 min, leaderboards daily.

**Stack:** Airflow 2.6.3, dbt-core 1.3.1, ClickHouse, S3, PostgreSQL, SSHOperator, atomic table swap.
**Result.** Data freshness 24h → under 1h overall (core metrics under 15 min). His framing: scheduling is a product decision — match freshness to business need rather than making everything real-time.

### G5 — S3 assets pipeline + discovery

**Company:** Good Creator Co.

**Situation.** The platform needed to ingest and serve millions of social media images per day reliably.

**Action.** Anshul built a dedicated 50-worker pool at 100 concurrency each (≈5,000 parallel S3 uploads), fed by the same `FOR UPDATE SKIP LOCKED` SQL task queue, with CloudFront CDN delivery.

**Stack:** Python asyncio, aioboto3, AWS S3, CloudFront, PostgreSQL `FOR UPDATE SKIP LOCKED`.
**Result.** 8M images/day processed; ~10% engagement growth attributed to faster/complete asset availability.

### G6 — Fake-follower detection (ML without labeled data)

**Company:** Good Creator Co.

**Situation.** Brands needed reliable follower-quality metrics, but content filtering was manual and there was no labeled dataset of fake-vs-real accounts.

**Action.** Anshul chose an interpretable 5-feature heuristic ensemble over deep learning precisely because there were no labels and explainability mattered (each flag is explainable). Features include weighted RapidFuzz name similarity and a match against a 35,183-name Indian-name database. For multilingual names he ran HMM transliteration via `indictrans` (Viterbi decoder compiled in Cython) across 10 Indic scripts, with custom rule-based handling for Hindi's complex diacritics. Output is a 3-level score (0.0 real / 0.33 review / 1.0 fake). Deployed as an AWS Lambda ECR container (libraries exceed the 250MB layer limit) with SQS in and Kinesis out.

**Stack:** Python, RapidFuzz, `indictrans` HMM/Viterbi (Cython), AWS Lambda + ECR, SQS, Kinesis, ClickHouse source.
**Result.** ~50% throughput gain over the prior single-threaded approach, with consistent explainable scoring.

### G8 — Tech-stack defence (right-sizing decisions)

**Company:** Good Creator Co.

**Situation.** Interviewers probe why the GCC stack diverged from "default big-company" choices.

**Action / reasoning to reuse.** RabbitMQ over Kafka — a 5-person team, simpler ops, ~100K events/day didn't need Kafka's throughput or replay. Dual-DB (Postgres OLTP + ClickHouse OLAP) — different workloads. Go + Python — Go for high-throughput services, Python for scraping/ML ergonomics. Self-hosted over k8s — at that team size, ops cost outweighed savings. Lambda for the ML job — bursty batch workload, pay-per-invocation beats idle EC2.

**Stack:** decision-rationale card (no single stack).
**Result.** N/A — this is a "are right a lot / frugality" reasoning card.

---

# PAYU — loan disbursal (intern → SE · earliest role)

First professional role. First Spring Boot, first 24/7 on-call, real customer money moving.

### P1 — Partner API failure rate 4.6% → 0.3%

**Company:** PayU

**Situation.** Loan-disbursal partner API calls (to NPCI / NBFC partners) were failing at ~4.6%, blocking disbursals.

**Action.** Anshul added idempotency keys (safe retries without double-disbursing), a Resilience4j circuit breaker, and exponential backoff with jitter (3 retries).

**Stack:** Spring Boot, Resilience4j (circuit breaker), idempotency keys, exponential backoff + jitter.
**Result.** Failure rate dropped 4.6% → 0.3%; business operations scaled ~40%.

### P2 — Disbursal TAT 3.2 min → 1.1 min

**Company:** PayU

**Situation.** End-to-end loan disbursal turnaround time was ~3.2 minutes because KYC, bank-verification, and risk checks ran sequentially.

**Action.** Anshul parallelized the independent checks with `CompletableFuture.allOf(kyc, bank, risk)` so they run concurrently and the slowest one bounds the total.

**Stack:** Spring Boot, `CompletableFuture.allOf`.
**Result.** TAT 3.2 min → 1.1 min; disbursal funnel conversion up ~18%.

### P3 — Test coverage 30% → 83% (as an intern)

**Company:** PayU

**Situation.** The loan-disbursal codebase had ~30% test coverage and deploy errors were frequent.

**Action.** As an intern Anshul wrote 200+ tests in 8 weeks, wired SonarQube into GitHub Actions as a PR-blocking quality gate, and introduced Flyway for versioned DB migrations.

**Stack:** JUnit/Mockito, SonarQube, GitHub Actions, Flyway.
**Result.** Coverage 30% → 83%; deploy errors down ~90%.

### P4 — First-job learning curve (framing)

**Company:** PayU

**Situation.** PayU was Anshul's first real engineering job — first Spring Boot, first time on 24/7 on-call, first time code moved real customer money.

**Action / framing.** Use this to show humility and growth at the start of the career arc, then pivot to P1/P2/P3 for concrete wins. Keep it short.

**Result.** N/A — framing card for the intro/career-arc narrative.

---

## Pairing guide (primary → backup)

- **Ownership / scope:** W8 (DC Inventory Search, design-to-prod solo) → W2 or G1.
- **Dive deep / debugging:** W1 (silent Kafka failure) → G1 or W8.
- **Invent and simplify:** W2 or W8 (design-first) → G2 (`FOR UPDATE SKIP LOCKED`).
- **Are right a lot / good judgment:** W5 (`.block()` call) → W9 (cursor vs offset), G8 (stack defence).
- **Have backbone / disagree & commit:** W3 (DiscardPolicy) → W9 (cursor vs offset).
- **Hire and develop / develop others:** no 1:1 mentoring card by design — use the honest _force-multiplier_ angle: W2 (shared library three teams adopted, 2 weeks → 1 day) → W8 (design-first spec other teams built against in parallel). State plainly it's team/org-level, not formal mentoring; do not fabricate a mentoring story.
- **Learn and be curious:** G6 (chose interpretable ML, learned `indictrans`/HMM transliteration) or G2/G3 (new Go/ClickHouse/Airflow/dbt stack) → P3.
- **Deliver results / frugality:** W2 (Splunk ~$50K→$500/mo), G1 (ClickHouse cost + 5× compression) → P1/P2.
- **Customer obsession:** W7 (DSD associates, talked to them first) → W2 (suppliers self-serve their own audit data).

<!-- PII redaction: phone, email, personal site, LinkedIn handle, and GitHub handle all removed/never included. First name "Anshul" intentionally kept for the voice persona. No source code, credentials, or .certs included — curated narrative only. -->
