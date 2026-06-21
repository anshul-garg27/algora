# Q: Tell me about yourself / walk me through your background.

> **LP**: Intro & Closers
> **Primary story**: Career arc — PayU → GCC → Walmart
> **Backup story**: Lead with the Kafka audit system if they want depth
> **Time budget**: 90 seconds spoken — 30s PayU + 30s GCC + 30s Walmart + 15s why-here

---

## STAR — how to actually tell it

### Situation

Interviewer is opening the loop. They want a quick spoken pitch — where I've been, what I owned, why I'm sitting here.

### Task

Walk through three jobs in roughly 90 seconds. One hookable detail per job. Land it conversational, not rehearsed.

### Action

So I'm a backend engineer, roughly three and a half years in. SE-III at Walmart Data Ventures right now.

Started at PayU as a Java intern on the consumer-lending team. They put me on the loan-disbursal flow. Failure rate was running around 4.6% — which is bad, because each failure is a customer who didn't get their loan. I worked through the retry logic, fixed idempotency on the partner-bank calls, tightened up the timeouts. Got it down to about 0.3%. After that I rewrote the disbursal pipeline — three serial API calls that were averaging 95 seconds — parallelised them with `CompletableFuture.allOf`. Brought it to about a minute.

Then I went to Good Creator Co, an influencer-analytics startup. SE-I on paper, but the backend was a five-person team and I ended up owning six production services solo — Python scrapers, a Go gRPC ingestion service, ClickHouse data platform, the SaaS gateway. The biggest thing I did there was migrate event logging off Postgres. We were doing about 10 million writes a day and the database was choking. I built a RabbitMQ buffered sinker — events batch into thousand-record chunks before flushing to ClickHouse. Dual-write for two weeks to make sure nothing was lost, then cut over behind a feature flag. Got us 5x compression and roughly 30% off the infra bill.

Now I'm at Walmart, joined June 2024. Two things I'd flag. First, the audit-logging platform I built — three-tier through Kafka and GCS into BigQuery, around 2 million events a day, under 5 ms P99 impact on the source APIs. Suppliers like Pepsi can query their own audit logs directly instead of filing tickets. The shared library got picked up by three other teams in the first month. Second — I led the Spring Boot 2.7 to 3.2 plus Java 11 to 17 migration on our main supplier API. 158 files, kept WebClient on `.block()` rather than going fully reactive, shipped through Flagger canary. Zero customer impact.

And I'm here because the scale I work with at Walmart is where Amazon starts. That's the next stretch I want.

### Result

Three jobs covered. Four good hooks dropped (PayU disbursal, GCC ClickHouse, Walmart audit, Walmart SB3 migration). Lands in about 90 seconds if I don't over-explain any one piece. They almost always grab one of those for the next question.

---

## Technical depth — if they probe

- **PayU (P1/P2)**: 4.6%→0.3% via idempotency keys on partner-bank calls + Resilience4j circuit breaker on the credit-score API + exponential backoff with jitter. TAT 3.2→1.1 min via `CompletableFuture.allOf` parallelising three serial 50-second calls — KYC, bank validation, credit check.
- **GCC (G1/G7)**: ClickHouse MergeTree partitioned by `toYYYYMM(timestamp)`, sorted by `(platform, profile_id, event_timestamp)`. RabbitMQ buffered sinker in Go: `chan` buffer 10K, batch 1000 or 5-sec ticker. Dual-write parity check at 0.02% drift. Sole architect across six services for 18 months.
- **Walmart W1 (audit)**: Spring Boot starter library `dv-api-common-libraries`. `OncePerRequestFilter` + `ContentCachingWrapper` + `@Async` fire-and-forget. Avro-serialised onto Kafka, Kafka Connect sink to GCS as Parquet. BigQuery external tables with row-level security per supplier.
- **Walmart W5 (SB3 migration)**: 158 files. 74 javax → jakarta. `RestTemplate` → `WebClient` with `.block()` on the Tomcat thread pool. Hibernate 6 `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` for Postgres enums. Flagger canary 10→25→50→100% over 5 days.

---

## Likely follow-ups

**Q: Why the jumps — PayU to GCC to Walmart?**
> PayU was an intern conversion. GCC came up when I wanted to own services end-to-end, not just features — five-person backend meant I'd actually get to make architectural calls. Walmart was for scope and stability — enterprise scale, supplier-facing infra, real production stakes.

**Q: What are you most proud of?**
> Probably the audit logging system at Walmart. The architecture worked at 2 million a day, the shared library got picked up by three teams in the first month, and it survived a 5-day silent-failure incident in production without losing data.

**Q: What's your strongest technical area?**
> Backend distributed systems on the JVM — Kafka, Postgres, async pipelines, Spring Boot. I'm also comfortable in Go and Python, shipped production code in both at GCC.

**Q: Why Amazon over staying at Walmart?**
> I've been ramping inside one team for about 18 months and I'm ready for a broader platform problem. Amazon SDE-3 means influencing design across teams from day one, not asking permission. That fit matters to me right now.

---

## What NOT to say

- Don't list job titles and dates — that's a resume read, not an intro. Tell a story.
- Don't mention layoffs, manager issues, or anything negative. Frame is "what I've built", not "what went wrong".
- Don't say "I'm passionate about coding" or any version of that. Show it through what you built.
- Don't run past 100 seconds. If you've gone deep on Walmart and skipped GCC, you've blown the structure.

---

## Backup framing — if they want it shorter (60s version)

> Backend engineer, three and a half years. Started at PayU on consumer lending — fixed the loan-disbursal flow, failure rate 4.6 to 0.3 percent. Then GCC, sole architect across six services — migrated 10M-events-a-day off Postgres to ClickHouse, 5x compression, 30% infra cost cut. Now at Walmart SE-III — built the Kafka audit platform at 2 million events a day, led the Spring Boot 3 migration with zero customer impact. Looking at Amazon because SDE-3 here is the platform-scope step I'm ready for.

<!-- lpSlug: intro-and-closers -->
