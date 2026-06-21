# Q: Describe a time you balanced speed and quality.

> **LP**: Insist on the Highest Standards
> **Primary story**: `W5 — .block() + Flagger canary + tech-debt write-up`
> **Backup story**: `G1 — Dual-write 2 weeks + buffered sinker`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Spring 2025. Spring Boot 2.7 end of life. Snyk flagging CVEs we couldn't patch. Three months to a failed security audit. The clock was external — pushed by compliance, not preference.

A colleague proposed going fully reactive while we were in the code. Three months of work. "Modernize once, properly."

### Task

Ship the Spring Boot 3 migration before the audit deadline. Don't ship something that breaks supplier APIs.

### Action

I made a deliberate trade. WebClient with `.block()` instead of full reactive. Four weeks instead of three months. The framework gets upgraded, the business logic doesn't change, the team doesn't have to learn reactive types under deadline pressure.

But I refused to trade quality on the rollout itself. Three things stayed non-negotiable.

One: a full week in stage with production-like traffic. That week caught the Hibernate 6 Postgres enum issue — a missing `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` annotation that would've 500'd every query on those entities. Worth every day.

Two: Flagger canary in production. 10% → 25% → 50% → 100% over 24 hours. Two-minute metric checks. Automatic rollback if success rate dropped below 99% or P99 went above 500ms. No 30-minute big-bang.

Three: the tech-debt write-up. Going fully reactive wasn't dead, it was deferred. I wrote a Q3 follow-up ticket with the reasoning, the throughput threshold at which we'd revisit (~1000 req/sec per pod), and the migration shape. Speed today, but the future self gets a paper trail.

### Result

158 files in PR #1312. 4 weeks from planning to 100% production. Zero customer-impacting issues during the rollout. Error rate 0.02%, P99 at 180ms.

The honest tail — the migration had a long post-rollout life. Heap OOM in October (PR #1528), correlation ID propagation (PR #1527), WebClient timeouts (PR #1564). Nine months before I'd call it truly done. That's the cost of "ship fast on a framework." But the audit deadline was hit, and the long tail was fixable without customer impact.

Looking back, the `.block()` decision is the one I'm proud of. Ship safely first, modernize later. Knowing what not to do was harder than knowing what to do.

---

## Technical depth — if they probe

- **`.block()` is the trade**: Reactive WebClient blocked back to synchronous. Same behavior as RestTemplate from the caller's view. Anti-pattern only on a reactive event loop, which we don't have.
- **Stage for a full week**: Functional tests pass on day one. Database-type bugs (Hibernate enum), filter-chain bugs (correlation ID), and memory bugs only show up under sustained traffic.
- **Flagger metrics**: `request-success-rate` and `request-duration` against the gateway. Step weight 10%, max canary 50% before promotion to primary.
- **The Q3 ticket**: Reactive only matters above ~1000 req/sec per pod. We're at ~100. Not free engineering — speculative engineering for capacity we don't need.

---

## Likely follow-ups

**Q: How do you know when to trade speed for quality?**
> The asymmetry. If the failure mode is "audit fails, contract penalties," speed matters more. If the failure mode is "supplier APIs throw 500s," quality matters more. We needed both — speed on the migration scope, quality on the rollout.

**Q: What did "long tail" cost?**
> Roughly 10 follow-up PRs over 9 months. Each caught by CI or by our observability, not by suppliers. Total customer-impacting incidents from the migration: zero. The tail is fine when it's invisible.

**Q: Would you trade speed differently today?**
> I'd set WebClient timeouts on day one — we added them 6 months later in PR #1564. Mechanical hardening should ship with the migration, not after.

**Q: When does the reactive ticket get picked up?**
> When throughput per pod doubles. Right now it's speculative engineering. We're saving the work for when it's real.

---

## What NOT to say

- Don't pretend reactive was a bad idea. It's the right architecture for different load. We just didn't have that load.
- Don't claim "no compromises were made." Speed is a compromise — you traded modernization for safety.
- Don't downplay the post-migration tail. Interviewers respect the honest version.

---

## Backup story (if asked for another)

At GCC the ClickHouse migration had the same shape. Postgres was choking on 10M events/day, finance was watching the bill, but a big-bang cutover would've taken the platform down. I built the dual-write — Beat to Postgres + RabbitMQ, Event-gRPC into ClickHouse via a buffered sinker batching 1000 events every 5 seconds. Two-week dual-write window with validation queries every day. Switched reads only after three clean days. Slower to ship the cutover, but zero downtime and zero lost rows.
