# Amazon LP Interview Prep — Anshul Garg
## Stories prepped for: Bias for Action · Learn & Be Curious

---

# ⚡ BIAS FOR ACTION

## Story 1 (Primary) — W5: Spring Boot 3 Migration

**Story: W5 — Spring Boot 3 Migration · Bias for Action · Amazon · ~4 min**

### Opener (say this first, start talking within 15 seconds)

Story: W5 — Spring Boot 3 + Java 17 migration · Bias for Action · Amazon lens · ~4 min
Situation: Production supplier API on EOL Spring Boot 2.7, 2 unpatched CVEs, Pepsi/Coca-Cola/Unilever data flowing through it.
Task + Action: Volunteered to lead — made the call to use `.block()` on WebClient instead of full reactive rewrite: 3 weeks not 3 months. 158 files changed, Flagger canary 10→25→50→100%.
Result: Zero customer impact. CVEs cleared. Live April 2025.

### Full STAR

**Situation:**
The main supplier API service `cp-nrti-apis` was running Spring Boot 2.7 and Java 11 — both end-of-life. There were 2 CVEs that couldn't be patched without upgrading the framework. This service was the data layer for Fortune 500 suppliers — Pepsi, Coca-Cola, Unilever — so security wasn't negotiable. No one had volunteered to own the migration.

**Task:**
Lead the migration to Spring Boot 3.2 + Java 17 with zero downtime and zero customer impact.

**Action:**
The most consequential call I made upfront: `.block()` on the new WebClient vs a full reactive rewrite. Full reactive would've been architecturally cleaner but 3 months of work. `.block()` kept it a framework upgrade — 3 to 4 weeks. CVEs couldn't wait 3 months. I load tested `.block()` in staging, verified P99 was acceptable, and committed.

158 files changed total. The `javax` → `jakarta` namespace rename touched 74 files alone. Hibernate 6 had stricter enum handling that would've silently broken prod — fixed it with `@JdbcTypeCode(SqlTypes.VARCHAR)`. Spent 2 days debugging a Mockito WebClient chain in tests where the mocking of request/response chains required `.exchangeFunction(...)` — unit tests had missed this entirely, only showed up in integration.

Rollout: Flagger canary, 10→25→50→100% over 5 days, auto-rollback wired to 1% error-rate threshold. I rehearsed the rollback in staging before touching prod.

**Result:**
Zero customer-impacting issues. CVEs cleared. Production April 2025.

### Likely Follow-ups

**Q: Why not wait for a scheduled maintenance window?**
> CVEs mean active security exposure. The cost of waiting was greater than the cost of moving fast with a rollback safety net. Canary meant if anything went wrong, rollback was automatic — no manual scramble at 2 AM.

**Q: What was the risk of `.block()` over reactive?**
> Thread contention under high load. We load tested in staging — P99 stayed acceptable at peak QPS. I acknowledged the long-term technical debt, documented it, and accepted the tradeoff explicitly. Speed to clear CVEs was the right call here.

**Q: How did you get buy-in to move fast?**
> CVEs were the forcing function — the conversation was simple. I wrote a one-page risk doc: cost of CVE exposure vs cost of a canary migration with auto-rollback. Leadership didn't need convincing once the risk was laid out.

**Q: What would you do differently?**
> Write container tests from the start. The Mockito WebClient chain bug cost 2 days because unit tests with mocks couldn't catch it. Container tests with WireMock + real DB would've caught it in CI. I added them after, but should've been day one.

**Q: What if the canary had caught a regression?**
> Auto-rollback on 1% error threshold. We rehearsed it in staging — the rollback path was already proven before we touched prod. I wouldn't have gone to prod without that rehearsal.

---

## Story 2 (Backup) — W7: DSD Notifications

**Story: W7 — DSD Real-time Notifications · Bias for Action · Amazon · ~3 min**

### Opener

Story: W7 — DSD Notifications · Bias for Action · Amazon lens · ~3 min
Situation: 1,200+ store associates discovering supplier deliveries only during 2-4 hour periodic checks — goods sitting unshelved.
Task + Action: Talked to associates directly, found only 2 of 5 lifecycle states are actionable, wired those to Walmart's mobile push API.
Result: ~35% improvement in replenishment timing.

### Full STAR

**Situation:**
Direct Store Delivery suppliers like Pepsi drop goods at store docks, but associates only found out during periodic checks every 2 to 4 hours. Shelves looked empty even when stock was sitting in the back. 1,200+ associates across 300+ stores.

**Task:**
Build real-time notifications so associates act on deliveries the moment they arrive.

**Action:**
Before writing a line of code, I went and talked to actual associates. Found out fast: there are 5 DSD lifecycle states (PLANNED, STARTED, ENROUTE, ARRIVED, COMPLETED) but associates only need to act on 2 — ENROUTE and ARRIVED. Notifying on all 5 would cause notification fatigue and get ignored. I notified only on those 2.

Wired cp-nrti-apis Kafka events into Walmart's SUMO V3 Mobile Push API, targeted by domain + siteId + role so only the right store's receiving team gets paged. Commodity-type mapping (vendor → "Beverage", "Snacks") is CCM-configurable — no redeploy needed to onboard a new supplier.

**Result:**
~35% improvement in replenishment timing — gap between ARRIVED event and first inventory scan, tracked via the business team's operational dashboard.

### Likely Follow-ups

**Q: How did you decide which states to notify on?**
> Talked to associates directly before designing. They told me PLANNED and STARTED don't change their work — they can't do anything yet. ENROUTE means "get the dock ready" and ARRIVED means "go receive." The other states are noise.

**Q: Why CCM-configurable vendor mapping?**
> Bias for Action means also thinking about future action. If onboarding a new supplier requires a redeploy and a release cycle, that's a bottleneck. Config-driven means the business team can onboard a supplier themselves.

---

---

# 🧠 LEARN & BE CURIOUS

## Story 1 (Primary) — G1: ClickHouse Migration

**Story: G1 — ClickHouse Migration · Learn & Be Curious · Amazon · ~4 min**

### Opener (say this first)

Story: G1 — ClickHouse migration at Good Creator Co. · Learn & Be Curious · Amazon lens · ~4 min
Situation: PostgreSQL write latency degraded from 5ms to 500ms at 10M+ writes/day. System breaking at scale.
Task + Action: Learned ClickHouse from scratch, wrote Go sinkers (new language), 2-week dual-write for zero data loss.
Result: 33× throughput, 30s → 12s queries, 5× compression, 30% infra cost cut.

### Full STAR

**Situation:**
At Good Creator Co., our analytics pipeline was writing 10 million-plus data points a day into PostgreSQL. Write latency had degraded from around 5ms to 500ms. Analytics queries were timing out. The system was breaking at scale and we needed a real fix, not a patch.

**Task:**
Re-architect the analytics data layer. I had never used ClickHouse before — or Go.

**Action:**
First, I actually researched the options instead of defaulting to what I knew. Compared TimescaleDB (PostgreSQL extension, limited columnar benefit), InfluxDB (time-series focused, less flexible for our relational queries), and ClickHouse. ClickHouse's MergeTree + columnar model matched our append-only write pattern exactly.

Then I went deep on WHY ClickHouse works the way it does. The fundamental insight: columnar stores hate single-row inserts. Inserting 1 row at a time vs batching 1000 rows is a 100× performance difference. This completely changed the architecture I had to build — you can't just swap the DB, you need a buffering layer.

I built that in Go — which I didn't know. Go's goroutine model and channel semantics were the right fit for high-throughput buffered batch writes; Python asyncio wasn't. Two weeks to get comfortable enough to write production code. The sinker: Go channel buffer (cap 10K), flushes at 1000 rows OR every 5 seconds on a ticker, so ClickHouse always gets large batch inserts.

Tables: MergeTree partitioned by `toYYYYMM(timestamp)` — learned that partition strategy from reading ClickHouse internals on how it scans columns.

2-week dual-write window before cutover. During that window I found a critical bug: the consumer was acking RabbitMQ messages before the Go sinker confirmed the batch flush. If the service crashed between ack and flush, those messages were gone. Fixed: ack only after batch write confirmed. Would've been silent data loss in prod.

**Result:**
33× throughput. Queries 30s → 12s. Storage 500GB → 100GB (5× compression). 30% infra cost cut. Zero data loss.

### Likely Follow-ups

**Q: How did you choose ClickHouse over other options?**
> Benchmarked locally before committing. TimescaleDB is a PostgreSQL extension — easier migration but columnar benefits are limited. InfluxDB is optimized for time-series but our queries had relational joins. ClickHouse's MergeTree handles append-only writes + columnar analytics both. The local benchmark confirmed the throughput difference was real.

**Q: You learned Go for this — had you used it before?**
> No. Picked it up specifically because Python asyncio wasn't the right model for high-throughput buffered batch writes. Go's goroutine + channel semantics are cleaner for this pattern. Took about 2 weeks of deliberate learning — read "The Go Programming Language" and built small experiments before writing the sinker. Deliberate choice, not convenience.

**Q: What was the single biggest learning?**
> Columnar databases have a completely different performance model than OLTP. It's not "just a faster Postgres." The architecture changes: you need a buffer layer, batch sizes matter more than indexes, and schema design has to account for the fact that ClickHouse reads entire columns. Once I understood that, everything else fell into place.

**Q: What went wrong during the dual-write window?**
> Consumer was acking RabbitMQ before the Go sinker flushed the batch. On a service crash between ack and flush, acknowledged messages would've been lost — no way to recover. Found it during dual-write comparison (ClickHouse had slightly fewer records than PostgreSQL). Fix: ack only after batch write confirmed. Without the dual-write window, this would've been silent data loss in prod.

**Q: What else did you explore while doing this?**
> Dove into ClickHouse MergeTree internals — how it merges parts in the background, why `toYYYYMM()` partitioning helps time-range queries avoid full scans. Also studied why ClickHouse reads entire columns: it changed how I thought about which columns to include vs which to derive at query time. Schema design for columnar is a different discipline.

---

## Story 2 (Backup) — G2: Beat Scraping Engine

**Story: G2 — Beat Scraping Engine · Learn & Be Curious · Amazon · ~3 min**

### Opener

Story: G2 — Beat distributed scraper at Good Creator Co. · Learn & Be Curious · Amazon lens · ~3 min
Situation: Prior system single-threaded, rate-limited constantly, handling a few thousand profiles/day.
Task + Action: Rebuilt from scratch — learned Python asyncio/uvloop deeply, discovered PostgreSQL FOR UPDATE SKIP LOCKED for task coordination (no Redis needed).
Result: 10M+ data points/day, provider outages invisible to the business.

### Full STAR

**Situation:**
Good Creator Co. needed to scrape data from 15+ social APIs — Instagram, YouTube, Shopify, and more. The existing system was single-threaded, got rate-limited constantly, and could handle a few thousand profiles a day. We needed an order-of-magnitude scale jump.

**Task:**
Redesign the scraping infrastructure. I had never built a distributed worker system at this scale.

**Action:**
The most interesting learning was around task coordination. My first instinct was Redis or RabbitMQ for a task queue. But I dug into PostgreSQL's `FOR UPDATE SKIP LOCKED` — a pattern where multiple workers can pick tasks from a shared queue atomically, each one locking only the row it's taking. No Redis, no separate broker, no additional infra to maintain. Queryable, priority-ordered, and transactional. For a 5-person team, one less system to run is a real win. I learned this from the PostgreSQL docs and implemented it — it became the backbone for both Beat and the S3 pipeline.

For I/O concurrency I went deep on Python asyncio + uvloop. Learned the difference between multiprocessing (CPU isolation for each flow) and asyncio (I/O concurrency within a flow) — used both together: multiprocessing for the 73 scraping flows, asyncio within each flow for concurrent API calls.

Reliability: 3-level rate limiting (20K/day, 60/min, 1/sec per handle) with credential rotation and a Strategy-pattern provider fallback chain — when one provider fails, transparently fall back to another.

**Result:**
73 scraping flows, 150+ concurrent workers, 10M+ data points/day, ~10K events/sec. Provider outages — previously 2-3 visible per month — became invisible to the business.

### Likely Follow-ups

**Q: Why PostgreSQL FOR UPDATE SKIP LOCKED instead of Redis/RabbitMQ?**
> For our scale (~10M events/day) and team size (5 engineers), adding Redis or RabbitMQ meant another system to operate, monitor, and debug. `FOR UPDATE SKIP LOCKED` gives atomicity, queryability, and priority ordering — all from the DB we already had. The tradeoff is it doesn't scale to millions of tasks/second, but we weren't there. Right tool for the actual scale.

**Q: What's the difference between multiprocessing and asyncio here?**
> Multiprocessing gives CPU isolation — each of the 73 flows runs in its own process, so one flow's CPU-bound work doesn't block others. asyncio within each flow handles the I/O concurrency — while one API call is waiting for a response, the event loop is making 50 others. It's the combination that gets you to 150+ concurrent workers without the overhead of 150+ threads.

---

---

# 🔍 AUDIT LOG KAFKA — W1 + W2 (Detailed)

---

## W2 — Building the Kafka Audit Library (Ownership / Invent & Simplify / Bias for Action)

**Story: W2 — Kafka Audit Library · Invent & Simplify / Ownership · Amazon · ~4 min**

### Opener

Story: W2 — `dv-api-common-libraries` Kafka audit library at Walmart · Invent & Simplify · Amazon lens · ~4 min
Situation: 3 teams duplicating audit-logging code; Splunk being decommissioned ($50K/mo); suppliers had no self-serve debug visibility.
Task + Action: Built a Spring Boot starter JAR — one Maven dependency, zero config, audit logging just works. Asynchronous fire-and-forget, Kafka pipeline to BigQuery.
Result: Integration time 2 weeks → 1 day. Splunk replaced: $50K/mo → $500/mo. 12+ teams now on it. 2M events/day, P99 < 5ms.

### Full STAR

**Situation:**
Three product teams at Walmart Data Ventures were each writing their own audit-logging code — duplicated, inconsistent, and hard to maintain. On top of that, Splunk (which was handling audit data) was being decommissioned company-wide due to expensive licensing — around $50K a month just for audit. And separately, suppliers like Pepsi and Unilever had no way to debug their own API failures: "why did my request return a 400?" — they had to file a ticket and wait.

Three problems, one root cause: no shared audit infrastructure.

**Task:**
Build something reusable. Not just for our team — for any Walmart Data Ventures service.

**Action:**
I designed a Spring Boot starter — auto-configured via `spring.factories` so any service gets audit logging by adding exactly one Maven dependency to their POM. Zero config, zero boilerplate. That was the design goal: integration should take a day, not two weeks.

Internals: a servlet filter intercepts every inbound request, caches the body with `ContentCachingWrapper` (so it can be read twice — once by the business logic, once by audit), and fires the audit payload asynchronously in a fire-and-forget thread pool. No latency hit on the request path. Thread pool: 6 core, 10 max, queue of 100 with `CallerRunsPolicy` — under extreme load, the calling thread handles the task instead of dropping it. Idempotent Kafka producer with Avro serialization.

Pipeline: library → Kafka topic → Kafka Connect → GCS Parquet (partitioned by US/CA/MX, by date) → BigQuery external tables. Suppliers can now query their own audit data directly in BigQuery. Self-serve debug with no ticket filing.

Shipped design-to-prod in ~5 weeks.

**Result:**
Integration time per service: 2 weeks → 1 day. Splunk audit logging replaced: $50K/mo → $500/mo (99% cost reduction). 12+ teams now on it. 2M events/day in production. P99 under 5ms. Suppliers self-serve their own debugging.

### Likely Follow-ups

**Q: Why a starter JAR vs just sharing code / documentation?**
> Shared documentation gets outdated. Copy-pasted code diverges. A starter JAR means there's one implementation — if there's a bug, you fix it in one place and teams upgrade a dependency version. It's the same reason Spring Boot itself uses starters. Auto-configuration via `spring.factories` means teams don't even have to write config — it just works.

**Q: Why asynchronous / fire-and-forget for audit?**
> Audit logging should never slow down the request that's being audited. If the Kafka producer has a hiccup, the supplier's API call shouldn't time out. Fire-and-forget with `CallerRunsPolicy` means: under normal load, it's async; under extreme load, the caller slows down instead of dropping data. No silent drops.

**Q: How did you handle the fire-and-forget reliability concern?**
> Three layers. First, `CallerRunsPolicy` — backpressure instead of drops. Second, idempotent Kafka producer — safe to retry on transient failures without duplicating records. Third, Micrometer gauge on queue depth with an alert at 80% — so we see pressure building before it becomes a problem. I also added a CI chaos test that force-kills the Kafka broker mid-load to verify no records are lost.

**Q: How did you get 12+ teams to adopt it?**
> First two were easy — they had the same Splunk cost pain we did. For the rest, the integration story was the pitch: one Maven dependency, one day of work, and you get self-serve supplier debugging for free. Once 3-4 teams were on it, it became the de facto standard and teams adopted it on new services without being asked.

**Q: What did you learn about thread pool sizing?**
> Lot. Initial config used `DiscardPolicy` — a senior engineer in design review caught that silent drops on an audit trail are unacceptable. I initially defended my choice, slept on it, realized he was right. Switched to `CallerRunsPolicy` and added a queue-depth gauge. The lesson: "it's unlikely to fill up" is not a monitoring strategy for customer-facing data.

---

## W1 — The Silent Kafka Failure (Dive Deep / Investigate)

**Story: W1 — 5-day silent Kafka failure · Dive Deep · Amazon · ~4 min**

*Note: W1 maps better to Dive Deep than Bias for Action. Use it if asked "tell me about a time you investigated a complex problem" or "when did you go below the surface to find a root cause."*

### Opener

Story: W1 — Silent Kafka pipeline failure at Walmart · Dive Deep · Amazon lens · ~4 min
Situation: Kafka Connect audit pipeline stopped writing data. No alert fired. 5 days to detect.
Task + Action: Traced a 5-link failure chain: null SMT headers → NPE → silent retry → KEDA misread stall as load → scaled up → OOM.
Result: Zero data loss after replay. Two-tier alerting added — has caught 2 issues before they became incidents since.

### Full STAR

**Situation:**
The audit logging pipeline — Kafka Connect to GCS sink — silently stopped writing data. No alert fired. No error surfaced anywhere obvious. It took 5 days to even notice something was wrong, and only because a supplier asked why their recent requests weren't showing up in BigQuery.

**Task:**
Root cause the failure, recover without data loss, and make sure it could never go silent again.

**Action:**
I started with what I had: Kafka Connect logs, GCS object count, BigQuery record timestamps. The GCS writes had stopped at a specific timestamp. Connect logs showed nothing — just successful poll cycles. That was the first clue: if the consumer is polling but nothing is being written, the records are being consumed and dropped somewhere in between.

I traced it step by step:

Step 1 — found null SMT (Single Message Transform) headers on a specific subset of messages. Step 2 — those null headers caused a `SinkRecord` NullPointerException inside the connector. Step 3 — Kafka Connect's default behavior on connector errors is silent retry with exponential backoff. It kept retrying, kept failing, never surfaced an error alert. Step 4 — KEDA (our autoscaler) monitors consumer lag. It saw the consumer group stalled and interpreted it as high load — so it scaled up Connect workers. Step 5 — more Connect workers × the same failing batch × retry storms → JVM heap OOM. That's when the pipeline fully died.

Five links in the chain. Any one of them could have been caught earlier with the right monitoring.

Fix: SMT null-guard (skip or log null headers instead of NPE). Bounded backoff with a max retry count so failures surface instead of retrying forever. Then I added what should have been there from the start: a Micrometer counter for null-header events with a Grafana alert at 0.1%, and a CI chaos test that injects null headers under load to verify the guard works. Two-tier consumer-lag alerting: warning at 100, critical at 500 — catching "processing incorrectly" not just "is it up."

Data recovery: replayed from Kafka's committed offset. Zero data loss.

**Result:**
Zero data loss after replay. Null-header guard shipped. Two-tier consumer-lag alerting added — has caught 2 separate issues before they became incidents since.

The framing I use: "'Is it running?' is not monitoring. 'Is it processing correctly without losing data?' is."

### Likely Follow-ups

**Q: How did you know where to start the investigation?**
> Started with the symptom (no BigQuery records) and worked backwards: GCS objects, Connect logs, consumer group lag, then the individual message level. The key was the GCS timestamp — I knew exactly when it stopped, which narrowed the search to what changed in that window.

**Q: Why didn't Kafka Connect surface an error?**
> Default behavior in Kafka Connect is to retry on errors with exponential backoff. It's designed to handle transient failures gracefully — but it makes persistent failures invisible. The connector was "healthy" from Connect's perspective because it was running, polling, and retrying. It just wasn't writing anything.

**Q: How did KEDA make it worse?**
> KEDA saw consumer lag growing (connector stalled = lag accumulates) and interpreted that as "high throughput demand" — so it scaled up workers. More workers hitting the same failing batch with the same NPE → more retry pressure → OOM. It was autoscaling into the failure instead of surfacing it.

**Q: What monitoring would have caught this on day 1?**
> Consumer lag alert with a threshold, not just "is consumer running." We had lag monitoring off by default to avoid noise. The lesson: lag alert at 100 is noise, lag alert at 500 sustained for 5 minutes is a real problem. Also: the null-header Micrometer counter would have shown the anomaly immediately. Monitoring should track "is data moving correctly" not just "is the service up."

**Q: How did you recover without data loss?**
> Kafka retains messages for a configurable period (our cluster was 7 days). The consumer group offset was committed up to the point just before the null-header batch. I fixed the null-guard, deployed, and let Connect resume from that offset — it replayed the failed messages cleanly this time. Verified record count in GCS matched what should have been written.

---

---

# QUICK REFERENCE

| LP | Primary Story | Backup Story |
|----|--------------|--------------|
| Bias for Action | W5 — Spring Boot 3 migration | W7 — DSD notifications |
| Learn & Be Curious | G1 — ClickHouse migration | G2 — Beat scraping engine |
| Ownership | W2 — Kafka audit library | W1 — Silent failure fix |
| Invent & Simplify | W2 — Kafka audit library | W8 — DC Inventory design-first |
| Dive Deep | W1 — Silent Kafka failure | G1 — ClickHouse deep dive |
| Deliver Results | W2 ($50K → $500/mo) | G1 (33× throughput) |

---

# NUMBERS CHEAT SHEET (never guess these)

| Story | Key Numbers |
|-------|------------|
| W5 (SB3) | 158 files, canary 10→25→50→100%, zero customer issues, April 2025 |
| W7 (DSD) | 1,200+ associates, 300+ stores, 35% replenishment improvement, 5 states → notify on 2 |
| W2 (library) | $50K/mo → $500/mo, 2 weeks → 1 day integration, 12+ teams, 2M events/day, P99 <5ms, ~5 weeks build |
| W1 (failure) | 5 days to detect, 5-link chain, lag alert warning@100 / critical@500, 2 issues caught since |
| G1 (ClickHouse) | 10M+ writes/day, 5ms → 500ms degraded, 30s → 12s queries, 33× throughput, 500GB → 100GB, 30% cost cut |
| G2 (Beat) | 73 flows, 150+ workers, 10K events/sec, 10M+ data points/day, 15+ social APIs |
