# Q: Tell me about a time you challenged conventional wisdom.

> **LP**: Invent and Simplify
> **Primary story**: `W5 — Spring Boot 3 Migration with .block()`
> **Backup story**: `G8 — RabbitMQ over Kafka`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

When I started planning the Spring Boot 3 migration for `cp-nrti-apis`, a senior engineer on the team pushed hard to go fully reactive. His argument was straightforward: "we're touching every HTTP call anyway, RestTemplate is deprecated, WebFlux is the modern path — why not modernise properly while we're in here?" Most of the room was nodding.

### Task

I owned the migration. I had to decide what we'd actually ship.

### Action

I didn't argue in the room. I scheduled a 1:1 with the lead and brought the numbers.

Fully reactive meant every service class returns `Mono` or `Flux`. Error handling fundamentally changes — exceptions become signals you have to `.onError` on every chain. The team would need reactive training. Realistic estimate: 3 months minimum, and every business-logic class touched.

Framework-only migration with WebClient + `.block()` meant calls behave like RestTemplate did. Business logic unchanged. Tests still synchronous (mocking is uglier but the shape is the same). 4 weeks.

The conventional wisdom said "if you have WebClient, never call `.block()` — it's an anti-pattern." I dug in. The anti-pattern is calling `.block()` on a reactive thread — the event-loop thread. We don't have a reactive thread. We're on Tomcat's worker pool. `.block()` on a Tomcat thread is just synchronous behaviour with the new client. Same as RestTemplate.

I framed it to the lead as scope control. "This is a framework upgrade driven by security — Snyk is flagging CVEs we can't patch otherwise, audit fails in 3 months. Full reactive is a separate architecture initiative. Ship safely first, modernise later."

He agreed. I deployed via Flagger canary — 10 percent traffic, auto-rollback if error rate crossed 1 percent. 158 files changed. javax → jakarta across 74 files. Hibernate 6 enum mapping. CompletableFuture instead of ListenableFuture (which actually fixed a real failover bug — exceptions used to be swallowed).

### Result

Shipped in 4 weeks instead of 3 months. Zero customer-impacting issues on rollout. The Hibernate enum issue surfaced in stage week — caught before prod. The CompletableFuture change uncovered that our multi-region Kafka failover had been silently broken — the `exceptionally()` callback returned null instead of chaining to the secondary cluster. Fixing that was a bonus.

The decision held up. Over the next 9 months we shipped 10 small follow-up PRs — WebClient timeouts, K8s probe config, heap tuning — but never had to revisit the reactive question.

---

## Technical depth — if they probe

- **`.block()` on non-reactive thread**: Tomcat worker thread. Synchronous behaviour. Same semantics as RestTemplate. The anti-pattern is `.block()` on Netty's event loop, which we don't have.
- **CompletableFuture vs ListenableFuture**: The migration revealed a real failover bug. Old code: `kafkaPrimaryTemplate.send(msg).exceptionally(ex -> { log.error(...); return null; })` — secondary was never tried. New code chains `handleFailure(...).join()` properly.
- **Flagger canary**: 10 percent → 25 → 50 → 100 over 24 hours. `request-success-rate > 99`, `P99 < 500ms`. Automatic rollback. We never needed it.
- **Hibernate 6 enum bug**: caught in stage. `column is of type status_enum but expression is of type character varying`. Fix: `@JdbcTypeCode(SqlTypes.NAMED_ENUM)`. H2 in-memory wouldn't have caught this — needed real Postgres in stage.
- **javax → jakarta**: 145 import changes across 74 files. Mostly mechanical but some classes had behavioural changes — filter signatures, security config.

---

## Likely follow-ups

**Q: When would you go fully reactive?**
> When we need many more concurrent requests per pod and the bottleneck is I/O wait, not CPU. At our load — about 100 req/sec per pod — Tomcat's 200-thread pool gives 10x headroom. If we hit 1,000+ req/sec, reactive becomes the right call.

**Q: Did the senior engineer push back after the decision?**
> A little. I asked him to own the reactive proposal as a separate Q3 initiative. That gave him a real path forward and stopped it from feeling like a "no." Last I heard, that initiative deprioritised once load testing showed sync was fine.

**Q: Was `.block()` ever a problem in production?**
> Six months in we did hit thread starvation when a downstream API got slow. WebClient doesn't have RestTemplate's implicit timeout. PR #1564 added explicit timeouts and retry with exponential backoff. That's the kind of follow-up that comes with the trade-off, and I documented it in the design doc.

**Q: How did you frame the disagreement to the team?**
> "Two real options, here's the timeline and risk for each, I picked one, here's why. Open to changing if I'm wrong." Came with the data, owned the call.

**Q: What was the cost of being wrong?**
> If `.block()` had caused thread starvation under load, Flagger would have auto-rolled back at 10 percent traffic. Worst case: a few hours of partial impact, instant rollback, redo the migration. I sized the blast radius before betting.

---

## What NOT to say

- Don't oversell this as "I was right and everyone else was wrong" — the reactive proposal was reasonable. The disagreement was about scope and timing.
- Don't claim `.block()` is universally fine — it's fine on a non-reactive thread. On the event loop it'd be a real bug.
- Don't skip the failover-bug bonus — discovering the broken `exceptionally()` chain is the proof that the migration paid for itself.

---

## Backup story (if asked for another)

At GCC the conventional choice for high-volume events was Kafka. I picked RabbitMQ for our 10M-events-per-day ClickHouse pipeline. The team already ran RabbitMQ for credential events; at 115 events/sec average it handled the load fine; and the operational expertise was already there. Kafka would have been right at 100x our volume — at our scale it was over-engineering. Stuck with RabbitMQ, shipped the buffered-sinker pattern on top, and it held for two years.
