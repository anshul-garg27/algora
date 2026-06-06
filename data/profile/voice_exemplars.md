> These are reference exemplars for VOICE/style calibration only — never serve them verbatim; always generate a fresh answer in this voice.

# Voice Exemplars

Six STAR answers selected as the strongest, most voice-representative samples of Anshul's spoken interview style. Each covers a different story and a different Amazon Leadership Principle. Use these to calibrate tone, cadence, level of technical specificity, and the habit of honest self-critique. Do not reproduce them verbatim in any generated answer.

---

## Exemplar 1 — Ownership (DC Inventory Search API, end-to-end)

> **Q**: Tell me about a time when you took complete ownership of a project and ensured its success.

### Situation

In August 2025, the product team came to us with a need. Suppliers like Pepsi and Coca-Cola wanted a way to query Walmart's distribution-centre inventory in bulk — "give me on-hand and in-transit counts for these 50 SKUs at DC 6012". No such API existed. The consumer team was already booked for January integration.

### Task

Build the DC Inventory Search API from spec to production. I was the only backend engineer on it. Eight PRs over five months, end-to-end.

### Action

I started with the spec, not the code. That was deliberate. Wrote 898 lines of OpenAPI in PR #260 — endpoints, request/response schemas, validation rules, error examples for every status code. Shared it with the consumer team day one so they could generate a client SDK and start mocking. They didn't have to wait for my implementation.

The implementation in PR #271 was about 3,000 lines. The shape that mattered was a 3-stage pipeline. Stage 1 converts WmItemNumbers to GTINs through UberKey. Stage 2 validates each GTIN against supplier authorization. Stage 3 fetches actual inventory from the Enterprise Inventory API. Each stage tracks its own errors. So a 100-item bulk request might come back as 80 successes and 20 errors from three different stages — and the consumer knows exactly what failed and why.

For multi-country support I used a factory pattern. `USConfig`, `CAConfig`, `MXConfig` all implement `SiteConfigProvider` and Spring auto-discovers them into a `Map<String, SiteConfigProvider>`. Adding Mexico was one class plus an `@Component("MX")`. Zero changes to the factory or controller.

About a month after launch, I realised the validation logic was duplicated between this API and the Search Items API. PR #322 — about 1,900 lines — centralised it into a `RequestProcessor` pipeline. Each stage takes current state, runs a function on valid items, tags failures with an error source.

Then I caught a bug in container tests that unit tests had missed. Some GTINs mapped to multiple WmItemNumbers, and my reverse-mapping picked one non-deterministically. PR #330 added null checks, duplicate logging, and deterministic selection. Then PR #338 — 1,724 lines of container tests with Docker, WireMock, and real PostgreSQL test data — so this category of bug couldn't slip again.

### Result

Live across US, Canada, and Mexico. Bulk requests up to 100 items per call. About 8,000 lines from spec to container tests across eight PRs. The design-first approach cut consumer integration time by roughly 30% — they started three weeks earlier than they would have with code-first. And the next country we'll add (Brazil) is one class.

The lesson for me: write container tests from the start, not as an afterthought. PR #338 caught the GTIN reverse-mapping bug; unit tests with mocks never could have.

---

## Exemplar 2 — Dive Deep (audit-data deep dive, unexpected access-review discovery)

> **Q**: Describe a situation where a deep dive into data led to an unexpected discovery.

### Situation

A Pepsi engineer pinged us in Slack: "Why is my IAC POST returning a 400 today? Worked yesterday." Standard supplier debug. Normally we'd grep Splunk, find the request, and reply in a day. But Splunk was being decommissioned across Walmart and we'd just stood up the new Hive-backed audit query path. I told him to give me an hour.

### Task

Find his request, find the failure cause, and figure out why the same request worked the day before. The supplier had real urgency — their pricing data wasn't flowing.

### Action

I ran the BigQuery external table on the audit logs partition for the last 48 hours, filtered to his consumer ID. The 400 was real. Error reason: "store_id 6018 not authorized." I looked at the prior day's logs — the same store_id was accepted. Same supplier, same endpoint, same store.

That was the unexpected bit. The authorization shouldn't be flaky. I pulled the consumer-to-DUNS-to-GTIN-to-store mapping table and noticed his entry had been touched 11 hours ago. Someone had reduced his store list as part of a quarterly access review and store 6018 had dropped off.

Then I looked sideways. I queried for any supplier hitting a 4xx on stores they used to access, in the last 30 days. The query took 1.2 seconds against the Parquet files in GCS. The number came back as 47 distinct suppliers, with a long tail of similar "I used to be able to do this" failures that never got reported because most teams shrugged it off as "must be wrong on their end."

The unexpected discovery: the access-review process was silently breaking integrations and we had no signal because Splunk wasn't queryable by suppliers. The new audit path made the pattern visible in one query.

### Result

I sent the data to our compliance team — 47 suppliers, named, with timestamps. They flipped the review process from "remove access by default" to "remove access with 30-day supplier notification." Two days later they shipped that change. Pepsi got their store back the same afternoon I dug in.

The deeper result was operational. Our supplier-facing 4xx rate had been creeping up 2% per quarter and nobody connected it to the access reviews. Once we had it on a dashboard, the trend reversed.

---

## Exemplar 3 — Earn Trust (critical PR feedback on a silent-drop failure path)

> **Q**: Tell me about a time when you had received critical feedback and how you worked upon it.

### Situation

It was a Friday afternoon code review on the audit common library — the Spring Boot starter JAR I'd built for three teams to log API calls. PR was up. A senior engineer — someone whose reviews everyone respected — left a comment on the thread-pool config.

The pool was 6 core, 10 max, 100 queue, default `AbortPolicy`. My async method had a catch-all that logged and swallowed exceptions to protect the API path. His comment: "Your queue size of 100 is arbitrary. When it fills up, you'll lose audit records silently and you won't know."

The comment was public. My first reaction was honestly defensive. I'd thought about queue sizing. I had numbers in my head.

### Task

Respond well. Either justify the design with evidence or change it. The wrong move was the angry-junior-engineer reply.

### Action

I waited before I typed anything. Then I ran his scenario through the actual code path.

Each audit payload is around 2KB. Queue of 100 is 200KB total — fine on memory. But when the queue fills, `AbortPolicy` throws `RejectedExecutionException`. My async method catches all exceptions and logs them. So the record is dropped, the WARN goes into log noise that no dashboard reads, and the API keeps serving like nothing happened. He was right. There's a path where we silently lose audit data and the system reports healthy.

I replied on the PR. Not "you're right, I'll fix it" — that's cheap. I wrote out the failure path I'd just traced, said his concern was legitimate, and listed three changes I'd add before merging.

One: a Prometheus counter — `audit_log_rejected_count` — so dropped tasks show up on the dashboard.

Two: a WARN log at 80% queue depth — `audit_log_queue_depth` — so we see pressure before tasks start failing.

Three: documentation in the README spelling out the trade-off — audit is best-effort by design, but "best-effort" doesn't mean silent.

I asked if there was anything else I'd missed. He flagged the thread-name prefix — said rejected tasks should be findable in a heap dump. I added that too.

### Result

The library shipped a couple of days later. The 80% queue warning has fired twice in production — both during downstream slowdowns. Both times we scaled the pool before any record was actually dropped. The senior engineer later became one of the loudest advocates for the library and helped onboard a fourth team.

What I took away: defending first is human, but trust comes from showing the work — running the numbers, naming the failure path, listing the changes. "You were right" is one sentence. The trust is in the second paragraph.

---

## Exemplar 4 — Deliver Results (ClickHouse migration, project most proud of)

> **Q**: Describe a project you are most proud of.

### Situation

Mid-2023 at Good Creator Co. Beat was our Python scraping engine — 150+ workers crawling Instagram and YouTube, generating profile-log, post-log, sentiment-log entries that the SaaS app reads for influencer analytics. Volume was crossing 10 million log events a day. Postgres was choking. Write latency had drifted from 5ms per INSERT to 500ms. Profile-log and post-log tables had billions of rows and the autovacuum was running constantly. Time-series queries — "show me this influencer's follower growth over 30 days" — were taking 30 seconds because Postgres was scanning row-oriented storage for a metric workload.

### Task

Redesign the write pipeline so Postgres stopped saturating, time-series analytics ran in seconds, and we did not lose data during the migration.

### Action

I designed a three-tier pipeline spanning three services.

Beat (Python) stopped doing `session.add()` on log objects. Instead it called `make_scrape_log_event("profile_log", profile)` to publish to RabbitMQ. The old code is literally still commented in `processing.py` so you can see the before/after on the same lines. Fire-and-forget from the scraper's perspective.

Event-gRPC (Go) was the new consumer. I wrote it from scratch. Each topic — `profile_log_events`, `post_log_events`, `sentiment_log_events`, `scrape_request_events` — has its own sinker. The sinker buffers up to 1000 records in a Go channel, then either flushes when the channel fills or when a ticker fires every 1-5 minutes (configurable per topic). The flush is a batch INSERT into ClickHouse via GORM. That single change is the heart of the throughput jump — Postgres saw 10,000 INSERTs per second before, ClickHouse sees 10 batched INSERTs per second now.

ClickHouse table design mattered. `MergeTree` engine, `PARTITION BY toYYYYMM(event_timestamp)`, `ORDER BY (platform, profile_id, event_timestamp)`. That ordering means a "30-day follower growth for profile X on Instagram" query hits an indexed range scan on the same disk block.

Stir (Airflow + dbt) was the third tier. dbt models in ClickHouse compute the analytics — 29 staging models, 83 marts. Then a nightly job exports the materialized analytics back to Postgres as a JSON staging file on S3, and an atomic table swap loads them into the operational DB so the SaaS app keeps reading from Postgres.

Migration plan was two weeks of dual-write — Beat writing to both Postgres and RabbitMQ in parallel — so I could diff the row counts and prove no events were lost. After two clean weeks, I dropped the Postgres write path in `processing.py` and cleaned up the unused tables.

### Result

Write latency 500ms per event → 5ms per 1000 events. 99% reduction. Query time for a 30-day range on a profile 30 seconds → 12 seconds — 2.5x faster. Storage 5x compression because ClickHouse is columnar (1B logs went from 500GB to 100GB). Infrastructure cost 30% lower because the analytics shifted off the same Postgres cluster the SaaS app needed for OLTP. DB calls per second dropped from 10,000 to 10. Zero data loss in the cutover. I am proud of this one because it was real architecture, not a refactor — three services, three databases, a migration plan with proof, and numbers that actually moved.

---

## Exemplar 5 — Bias for Action (calculated risk, Spring Boot 3 `.block()` decision)

> **Q**: Tell me about a calculated risk.

### Situation

Spring Boot 2.7 was hitting end-of-life and Snyk was already flagging CVEs we couldn't patch without upgrading. Our security audit was three months out. `cp-nrti-apis` — the main supplier-facing API used by Pepsi, Coca-Cola, Unilever — had to move to Spring Boot 3.2 and Java 17.

In planning, a colleague proposed we go fully reactive while we were already in the code. WebClient is reactive by default, so why use it the old way?

### Task

I was leading the migration. The decision was mine to make and defend — go reactive, or migrate the framework and keep the code synchronous.

### Action

I sat with the two paths for an evening. Fully reactive meant every service method returns `Mono` or `Flux`. Error handling fundamentally changes — exceptions become signals you compose. The team had near-zero reactive experience. Estimated work: 3 months including the learning curve.

`.block()` meant we use WebClient's API but block on the result, so the rest of the code stays synchronous. Same behaviour as RestTemplate. Estimated work: 4 weeks.

The risk on `.block()` is real — in a reactive thread pool it's an anti-pattern. But we weren't in a reactive thread pool. Tomcat thread per request, sync controllers, no event loop. `.block()` on a sync thread is just a method call.

I prepared the data — timeline, risk, team-readiness — and took it in a 1:1 with our lead instead of arguing in the planning meeting. My pitch: ship the framework upgrade safely now, scope reactive as a separate initiative if we ever hit the concurrency wall. He agreed.

I wrote up the trade-off in the design doc with the line "if we ever hit 1000+ req/sec per pod, revisit." That sentence was important. It made the decision a calculated bet, not a forever decision.

The migration touched 158 files. 145 `javax → jakarta` import changes. 23 `ListenableFuture → CompletableFuture` rewrites. The Hibernate 6 enum issue — `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` — got caught in the 1-week stage soak, not in prod. Flagger canary at 10% → 50% → 100% over 24 hours with auto-rollback wired to the 1% error threshold.

### Result

Shipped in 4 weeks. Zero customer-impacting issues during canary. The 9-month tail of post-migration fixes — heap OOM, correlation ID, WebClient timeout — were all manageable because the architecture hadn't changed. Reactive would have hidden those issues under a much bigger change. The calculated risk paid: the team kept moving, the audit was clean, the reactive option stayed on the table for later.

---

## Exemplar 6 — Frugality (ran six services solo, no extra headcount)

> **Q**: Tell me about a time you accomplished something without hiring more people.

### Situation

At Good Creator Co. I was the sole platform engineer. Five-person eng team total, three on product, one on infra, me on platform. The platform side had six services that needed to keep running and keep evolving: Beat (Python scraping), Event-gRPC (Go ingestion), Stir (Airflow + dbt), Coffee (Go REST), SaaS Gateway (Go API gateway), and a fake-follower ML service on Lambda. I asked for a DevOps hire twice in my first two months. Both times the answer was no — runway didn't allow it.

### Task

Run all six services. Ship the new features the product team needed for the roadmap — Genre Insights, Keyword Analytics, fake-follower detection, a ClickHouse migration. Without additional headcount for at least a year.

### Action

The win condition was "don't try to be a 3-person team in one body." Three deliberate moves:

One — standardise so all six services felt like one codebase. Coffee already had a 4-layer pattern (API → Service → Manager → DAO) with Go generics. I extended the same pattern to the gateway and to event-grpc. Every new module — Genre Insights, Keyword Analytics, Campaign Profiles — was the same four files with one converter pair. Adding endpoints stopped costing brain cycles.

Two — say no to ops complexity. No Kubernetes, no service mesh, no fancy observability stack. systemd unit files, bash deploy scripts checked into each repo, Sentry for errors, Slack for alerts, RabbitMQ management UI for messaging health. The whole platform was operable by one person at 2 AM because none of the components were complicated.

Three — push work out, not in. When the ClickHouse migration came up, I picked self-hosted ClickHouse on existing VMs instead of Snowflake or BigQuery — neither would have cost less in money but both would have cost more in operational learning. For the fake-follower ML I built a heuristic ensemble running on Lambda + SQS + Kinesis instead of a model-training pipeline. Each choice traded "best in class" for "ops-free for the team I actually had."

I also wrote a one-page runbook per service in my first month — what it does, top failure modes, how to restart, where the logs are. Cost 15 days; saved hours every month for the rest of my time there.

### Result

18 months. Six services kept running. Two cost-impacting projects shipped — the ClickHouse migration cut infra ~30%, the fake-follower detection unlocked sales conversations we'd been losing. Two product modules — Genre Insights, Keyword Analytics — shipped in Coffee. No new platform headcount during my tenure.

The honest part: this had real costs. Code quality varied. Some of my early bash deploy scripts make me wince now. But not hiring forced choices that turned out to be better than the textbook answers — standardise patterns, refuse ops complexity, push work onto managed services we already paid for.
