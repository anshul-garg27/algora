# Q: A walkthrough of my career journey and work experience.

> **LP**: Unclassified (Intro / Universal)
> **Primary story**: Career arc — PayU → GCC → Walmart
> **Backup story**: G1 — ClickHouse Migration as the single most-cited example
> **Time budget**: 90 seconds — this is THE intro, don't ramble

---

## STAR — how to actually tell it

### Situation

Interviewer is opening. They want a quick pitch — where I've been, what I owned, why I'm here.

### Task

Walk through three jobs in roughly 90 seconds. One hookable detail per job. Hand them clean follow-up handles.

### Action

So I'm a backend engineer, roughly three and a half years in. Started at PayU, then Good Creator Co, now Walmart Data Ventures.

PayU was my first real job — joined as a Java intern on the loan disbursal team. They put me on partner-API failures, which were running around 4.6% — and that's a customer not getting their loan, not a stat on a dashboard. I worked through the retry logic, fixed idempotency on partner calls, tightened the timeout handling. Got it down to about 0.3%. After that I rewrote the disbursal pipeline — three sequential API calls running 95 seconds total — parallelised them with `CompletableFuture.allOf`. Brought it to about a minute.

Then I jumped to Good Creator Co, an influencer-analytics startup. SE-I on paper, but the backend was a five-person team and I ended up owning six production services solo — Python scraper, Go gRPC ingestion, ClickHouse data platform, the SaaS gateway, a couple more. The biggest single thing I did there was migrate event logging off Postgres. We were doing about 10 million writes a day and the database was choking. I built a RabbitMQ buffered sinker — events batch into thousand-record chunks before flushing to ClickHouse. Dual-write for two weeks to make sure I wasn't losing anything, then cut over behind a feature flag. Got us 5x storage compression and roughly 30% off the infra bill.

I've been at Walmart since June 2024. Two things to flag. First, the audit-logging platform I built — three-tier pipeline through Kafka and GCS into BigQuery, around 2 million events a day, under 5 ms P99 impact on the source APIs. Pepsi and Coca-Cola can query their own audit logs directly now instead of filing tickets. The shared library got picked up by three other teams in the first month. Second — I led the Spring Boot 2.7 to 3.2 plus Java 11 to 17 migration on our main supplier API. 158 files, kept WebClient on `.block()` rather than going fully reactive, shipped through Flagger canary 10→25→50→100. Zero customer impact.

And I'm here because the scale I work with at Walmart is where Amazon starts. That's the next stretch I want.

### Result

Three jobs, four hookable details (PayU disbursal, GCC ClickHouse, Walmart audit, Walmart SB3 migration). They almost always grab one of those for the next question. Lands in ~90 seconds if I don't over-explain any single piece.

---

## Technical depth — if they probe by job

- **PayU (P1/P2)**: 4.6%→0.3% via idempotency keys on partner-bank calls + Resilience4j circuit breaker on the credit-score API + exponential backoff with jitter. TAT 3.2→1.1 min via `CompletableFuture.allOf` parallelising three serial API calls — KYC, bank validation, credit check — that were averaging 50 seconds each.
- **GCC (G1/G7)**: ClickHouse MergeTree partitioned by `toYYYYMM(timestamp)`, sorted by `(platform, profile_id, event_timestamp)`. RabbitMQ buffered sinker pattern in Go: `chan` buffer 10K, batch 1000 records or 5-sec ticker. Dual-write parity check at 0.02% drift. Sole architect across six services for 18 months — owned design + impl + on-call.
- **Walmart W1 (audit)**: Spring Boot starter library `dv-api-common-libraries` v0.0.54. `OncePerRequestFilter` + `ContentCachingWrapper` + `@Async` fire-and-forget. Avro-serialised onto Kafka, Kafka Connect sink to GCS as Parquet with geographic SMT routing on `wm-site-id`. BigQuery external tables on top, row-level security per supplier.
- **Walmart W5 (SB3 migration)**: 158 files. 74 javax → jakarta. `RestTemplate` → `WebClient` with `.block()` — Tomcat thread pool so `.block()` doesn't break the event loop. Hibernate 6 `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` for Postgres enums. Flagger canary at 1% error threshold for auto-rollback.

---

## Likely follow-ups

**Q: Why the jumps — PayU to GCC to Walmart?**
> PayU was an intern conversion. GCC came up when I wanted to own services end-to-end, not just features — five-person backend meant I'd actually get to make architectural calls. Walmart was for scope and stability — enterprise scale, supplier-facing infra, real production stakes.

**Q: Which jump was the biggest growth?**
> GCC. Going from "implement someone else's design" at PayU to "you pick the design across six services" was the real shift. Walmart was more refinement — same shape of work, bigger numbers.

**Q: What's your strongest single project?**
> The Walmart audit platform. It pulled together everything I'd learned — distributed systems from GCC, debugging discipline from the PayU disbursal work, and platform thinking from the shared-library design. The fact that it survived the 5-day silent-failure incident without losing data is what I'm proudest of.

**Q: What are you not great at yet?**
> Cross-org influence at enterprise scale. At GCC, the whole org was 30 engineers — convincing two of them was the whole game. At Walmart, the audit library reached three teams in my immediate org but I haven't driven adoption org-wide. That's the gap I want to close at Amazon.

---

## What NOT to say

- Don't recite the resume — story, not timeline.
- Don't say "Chapter one / Chapter two / Chapter three" aloud. Use "I started at", "then I went to", "now I'm at". Sounds spoken, not rehearsed.
- Don't run more than 90 seconds. If you hit 110, one of the jobs got over-explained.
- Don't end on a weakness or open question. End on "the scale I'm working with at Walmart is where Amazon starts" or equivalent — gives a clean handoff.

---

## Backup story (if asked for one)

If they want to drill deeper, default to the Kafka audit work at Walmart — that's the cleanest single arc. "I built the audit pipeline that replaced Splunk for our team. Three-tier: shared Spring Boot library, Kafka publisher with Avro, Kafka Connect sink to GCS as Parquet. 2M events daily, under 5 ms P99 impact, three teams adopted the library in the first month." Then let them pick which tier to dig into.

<!-- lpSlug: unclassified -->
