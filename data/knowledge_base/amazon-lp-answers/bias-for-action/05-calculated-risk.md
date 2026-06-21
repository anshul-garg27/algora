# Q: Tell me about a calculated risk.

> **LP**: Bias for Action
> **Primary story**: `W5 — Spring Boot 3 .block() decision`
> **Backup story**: `G1 — RabbitMQ-buffered ClickHouse ingestion`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

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

## Technical depth — if they probe

- **`.block()` on a sync thread**: Not an anti-pattern in a non-reactive stack. The anti-pattern is `.block()` on a Netty event loop, which we don't have. Tomcat's 200-thread pool handles it.
- **Thread starvation math**: ~100 req/sec/pod × 200ms avg downstream = ~20 active threads. Tomcat default pool is 200, so 10x headroom. The risk model was concrete.
- **`CompletableFuture` migration fixed a bug**: Old `ListenableFuture.addCallback` swallowed primary-region Kafka failures so secondary never got tried. `CompletableFuture.exceptionally()` chained correctly.
- **Stage soak caught Hibernate 6 enum**: Without the 1-week stage, the `column is of type status_enum but expression is of type character varying` would have hit canary. Stage saved us a rollback.
- **Flagger config**: 10% step, 1m interval, 1% error threshold, 99% success-rate metric. Auto-rollback configured before traffic ever hit.

---

## Likely follow-ups

**Q: Isn't `.block()` always wrong?**
> In a reactive stack, yes. We're synchronous. `.block()` is functionally identical to RestTemplate. The interview answer is "context matters."

**Q: When would you revisit?**
> When we hit ~1000 req/sec per pod. Reactive shines for I/O-heavy concurrency. At 100 req/sec we don't need it.

**Q: How did you handle the disagreement?**
> Not in the meeting. I prepared data and took it 1:1. He pushed back, I had answers. We agreed in 20 minutes.

**Q: What was the biggest post-migration surprise?**
> Heap OOM at month 5 — try-with-resources wasn't applied everywhere. WebClient also needed explicit timeout + retry config that RestTemplate had implicitly. Both fixed in follow-up PRs.

**Q: What would you do differently?**
> Add WebClient timeout and Resilience4j circuit breaker on day one. We added them 6 months later when we needed them.

---

## What NOT to say

- Don't pitch this as "I was right" — pitch it as "I picked the lower-risk path with a written escape hatch."
- Don't ignore the post-migration tail — the calculated risk paid because the tail was manageable, not because there was no tail.
- Don't trash reactive — it's the right answer at a different scale.

---

## Backup story (if asked for another)

At GCC, ClickHouse hated single-row inserts but we had 10M log events/day from Beat. I bet on a buffered sinker pattern — batches of 1,000 with a dual trigger (size or 1-minute ticker, whichever first). Risk: if ClickHouse hiccupped mid-flush, the buffered events were already ACKed in RabbitMQ and would be lost. I accepted that for log data and wrote the trade-off in the doc. Ingestion went from 10k INSERTs/sec to 10 batch INSERTs/sec.
