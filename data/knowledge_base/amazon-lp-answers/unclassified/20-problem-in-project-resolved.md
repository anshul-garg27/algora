# Q: Tell me about a time when you had a problem in the project and how you resolved it.

> **LP**: Deliver Results (hybrid)
> **Primary story**: `W5 — Spring Boot 3 Migration`
> **Backup story**: `G1 — ClickHouse Migration`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Walmart mandated Spring Boot 2.7 to 3.2 across the org because 2.7 hit end-of-life and Snyk was flagging CVEs we couldn't patch. My team owned six services. I picked up `cp-nrti-apis` — the main supplier-facing API, about 100 requests per second per pod, integrated with Pepsi, Coca-Cola, Unilever.

### Task

Migrate without breaking suppliers. Volunteered to lead. My estimate was four weeks for `cp-nrti-apis` alone; other teams were planning 8–12 weeks per service.

### Action

I started by walking the diff and pulling out the breaking changes into three buckets.

Bucket one was the `javax` to `jakarta` namespace shift. 74 files, mechanical but unforgiving — miss one and the build fails late. I wrote a sed-based pre-flight script for the imports and ran it per-package so the diff stayed reviewable.

Bucket two was `RestTemplate` to `WebClient`. A teammate pushed me hard to go fully reactive — `Mono`/`Flux` end to end. I almost agreed. Then I sat with the numbers. Reactive would touch every service class, every test, every error handler. Three months. Framework-only with `.block()` on `WebClient` was four weeks and behaved like `RestTemplate`. I picked `.block()` and wrote the rationale up so the team could push back in writing if they disagreed. Two people did; I addressed their points in a 1:1 with my lead. We landed on `.block()` now, reactive as a separate Q3 initiative.

Bucket three was Hibernate 6. PostgreSQL enums broke — Hibernate 5 was implicit, 6 needed `@JdbcTypeCode(SqlTypes.NAMED_ENUM)`. I added them explicitly and updated the integration tests against a real Postgres container.

The deployment was Flagger canary on WCNP — 10 percent for an hour, 25, 50, 100 across 24 hours, automatic rollback if 5xx exceeded one percent.

### Result

158 files changed, 1,732 lines added, 1,858 removed. 203 test failures in `cp-nrti-apis` fixed down to zero. Zero customer-impacting issues across the 24-hour canary. Three minor follow-ups over nine months — a Snyk transitive, a mutable-collection issue, a logging tweak — all caught in monitoring, not by users. The runbook I wrote was picked up by five teams outside Data Ventures.

---

## Technical depth — if they probe

- **Why `.block()` is fine here**: Anti-pattern only on a reactive thread (event loop). Our threads are plain MVC request threads, so `.block()` is equivalent to `RestTemplate.exchange()` behavior. The real anti-pattern is mixing reactive and blocking on the same Netty event loop.
- **Hibernate 6 enum fix**: `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` plus `columnDefinition = "status_enum"`. Without it, Hibernate sends VARCHAR and Postgres rejects with type mismatch.
- **Flagger canary**: Istio-backed traffic split, automated promotion on success metrics, automated rollback on 5xx threshold. We set the threshold at 1 percent.
- **WebClient mocking pain**: Mock chain — `webClient.get()`, `.uri()`, `.headers()`, `.retrieve()`, `.bodyToMono()`. Each step needs its own mock. Test files doubled in size; 42 test files updated.

---

## Likely follow-ups

**Q: Why volunteer to lead?**
> Two reasons. One, the runbook would only get written once; I wanted to own it so other teams could use it. Two, it touched the riskiest service in our org — if I let someone less familiar lead, I'd be the first one paged when it broke.

**Q: How did you handle the disagreement on reactive?**
> I didn't argue in the meeting. I prepared the cost-benefit, scheduled a 1:1 with my lead, and presented `.block()` as the safer ship-then-modernize path. He agreed. The two engineers who wanted reactive are leading the SB3-to-reactive proposal for Q3 now.

**Q: What broke first in production?**
> A mutable collection initializer in a unit test that worked in 2.7 and threw `UnsupportedOperationException` in 3.2 because of changed default. Caught at 10 percent canary, fixed in 30 minutes.

**Q: Would you migrate the same way again?**
> I'd run OpenRewrite on the `javax → jakarta` change. The mechanical work was the boring part. Everything else needed human judgement.

---

## What NOT to say

- "Migration was straightforward" — it wasn't. Lead with the three buckets.
- "I just picked `.block()`" — the disagreement is the interesting part. Tell it.
- Don't dump every CVE; pick one if asked.

---

## Backup story (if asked for another)

At GCC, the Beat scraper was writing 10M+ log rows a day directly to Postgres. Write latency went from 5ms to 500ms; analytics queries took 30 seconds. I designed a RabbitMQ-buffered pipeline into ClickHouse with batches of 1000 records per flush. Got 99 percent write-latency reduction, 5x compression, 30 percent infra cost drop, and 2.5x faster queries.
