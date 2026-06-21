# Q: Describe a time when you solved a complex problem with a simple solution.

> **LP**: Insist on the Highest Standards
> **Primary story**: `W5 — Spring Boot 2.7 → 3.2 + Java 11 → 17 Migration`
> **Backup story**: `G1 — ClickHouse Migration`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Early 2025. Spring Boot 2.7 was hitting end of life. Snyk was flagging CVEs in our dependency tree that couldn't be patched without upgrading the framework. Security audit was three months out and we'd fail.

The service was `cp-nrti-apis` — our main supplier-facing API. Pepsi, Coca-Cola, Unilever depend on it daily. About 100 requests per second per pod. Downtime equals supplier impact.

### Task

I volunteered to lead the migration. Spring Boot 2.7 to 3.2, Java 11 to 17. The hard call would be how far to take "while we're in there."

### Action

A colleague proposed going fully reactive — RestTemplate to WebClient, all the way to `Mono` and `Flux` end-to-end. His logic was fair: we were touching the code anyway. Three months of work, every service class returning reactive types, error handling fundamentally changed, the team learning a new mental model.

I picked the simpler path. WebClient with `.block()`.

The `.block()` call converts the reactive chain back to synchronous inside the filter context. Same behaviour as RestTemplate. The framework gets upgraded, the business logic doesn't change, the team doesn't have to learn reactive on a deadline.

I scheduled a 1:1 with our lead. Brought the data — 3 months versus 4 weeks, the risk profile of each, what we'd carry forward. The proposal: framework migration now, reactive as a separate Q3 initiative if we ever needed the throughput.

Then I executed. 158 files in PR #1312, +1,732 / -1,858. The mechanical bits — `javax` to `jakarta` across 74 files, `ListenableFuture` to `CompletableFuture` in 23 places, Hibernate 6's `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` for our Postgres enums. One week in stage caught a real bug — Hibernate 6 stopped letting us pass enums as VARCHAR to a Postgres custom enum type. Glad we found that there, not in prod.

Production rollout was Flagger canary. 10% to 25% to 50% to 100% over 24 hours, automatic rollback if error rate crossed 1%.

### Result

Four weeks from planning to 100% production. Zero customer-impacting issues during the rollout. P99 latency 180ms (target was under 500ms). Error rate 0.02%. The pattern became the template for two other team migrations.

The `.block()` decision is the one I'm proud of — knowing what not to do was harder than knowing what to do.

---

## Technical depth — if they probe

- **`.block()` on a non-reactive thread**: The anti-pattern is `.block()` on a reactive event loop. We don't have an event loop. Tomcat thread pool calling `.block()` is effectively the RestTemplate model with WebClient's API.
- **When I'd go fully reactive**: When throughput per pod exceeds ~1000 req/sec or downstream calls dominate latency. At 100 req/sec, synchronous code is fine.
- **Hibernate `@JdbcTypeCode(SqlTypes.NAMED_ENUM)`**: Hibernate 6 stopped doing implicit enum-to-text coercion. Without the annotation, the JDBC driver sends VARCHAR and Postgres rejects with "column is of type status_enum but expression is of type character varying."
- **Flagger config**: `stepWeight: 10, maxWeight: 50, interval: 2m`. Two thresholds: `request-success-rate > 99` and `request-duration P99 < 500ms`. Five failed checks triggers automatic rollback.

---

## Likely follow-ups

**Q: Isn't `.block()` an anti-pattern?**
> In a fully reactive stack, yes — it stalls the event loop. In a synchronous stack like ours, no — it's just RestTemplate behavior with WebClient's API.

**Q: What was the hardest gotcha?**
> WebClient test mocking. RestTemplate is one `when(...).thenReturn(...)`. WebClient needs five mock setups for the builder chain. Test files roughly doubled in complexity for 42 of them.

**Q: Did anything break post-migration?**
> Yes, in waves over 9 months. Heap OOM in October (PR #1528) from resource management changes — fixed with try-with-resources. Correlation ID stopped propagating (PR #1527). WebClient needed explicit timeout and retry logic that RestTemplate had implicit (PR #1564). Framework migrations have a long tail.

**Q: Would you do anything differently?**
> Set WebClient timeouts from day one — we added them in PR #1564, six months late. And run OpenRewrite for the `javax`-to-`jakarta` change next time. Mechanical edits should be automated.

---

## What NOT to say

- Don't pretend reactive was a bad idea. It's the right architecture for different load profiles. We just didn't need it.
- Don't skip the post-migration tail. Interviewers love honesty here.
- Don't claim "zero issues" — say "zero customer-impacting issues during rollout."

---

## Backup story (if asked for another)

At GCC, the complex problem was Postgres choking on 10M events/day. The complex solution would have been Postgres sharding. The simple solution was ClickHouse for analytics, Postgres for CRUD, RabbitMQ between them with a buffered sinker batching 1000 events every 5 seconds. Two databases each doing what they're good at — analytics went from 30s to 2s, infra cost dropped 30%, no downtime.
