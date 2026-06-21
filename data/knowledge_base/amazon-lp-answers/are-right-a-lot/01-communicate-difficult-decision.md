# Q: Tell me about a time when you had to communicate a difficult decision or change in timeline/direction.

> **LP**: Are Right, A Lot
> **Primary story**: `W5 — Spring Boot 3 Migration`
> **Backup story**: `G4 — Dual-Database API`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Last March I was kicking off the Spring Boot 3 migration for `cp-nrti-apis`, our main supplier-facing API. A senior engineer on the team had built the case for going fully reactive — "we're touching every HTTP call anyway, RestTemplate is deprecated, this is the moment." His timeline estimate was 6 weeks. Mine, after looking at the actual code, was 3 months. Most of the room was nodding along to his 6 weeks. The migration was driven by a security deadline — Snyk had flagged CVEs we couldn't patch without upgrading; audit failed in 3 months.

### Task

I owned the migration. I had to decide the scope and then tell the team and the lead that I was going to do something less ambitious than what was on the whiteboard.

### Action

I didn't push back in the room. I scheduled a 1:1 with the lead the next day and brought numbers.

For full reactive: every service class returns `Mono` or `Flux`, exceptions become signals, the team needs reactive training, every business-logic class touched. Realistic estimate based on the file count: 3 months minimum.

For framework-only with `.block()`: behaviour matches RestTemplate, business logic unchanged, tests stay synchronous (mocking is uglier but the shape is the same). 4 weeks.

I told him I wanted to ship framework-only and propose reactive as a separate Q3 initiative. The "anti-pattern" objection to `.block()` is real when you're on a reactive thread; we're on Tomcat's worker pool, so `.block()` is just synchronous behaviour with the new client.

Then I had the harder conversation — with the engineer who'd been championing reactive. I went to him before the team meeting, not in it. "I'm going to recommend framework-only because of the security deadline. I want you to own the reactive proposal as a Q3 initiative — full architecture, training plan, the works. That's the way to get it done right." He wasn't thrilled, but he understood. Reactive wasn't going to ship in 6 weeks alongside a forced framework upgrade.

In the team meeting I laid out both options with numbers, the recommendation, and the rationale. I said clearly: "If full reactive fails, that's on the team. If framework migration fails, that's on me." Owning the call made it easier to defend.

### Result

Shipped in 4 weeks. Zero customer-impacting issues on rollout. Flagger canary, 10 percent → 100 percent over 24 hours. The Hibernate enum issue caught in stage week would have been a Sev-2. The CompletableFuture migration actually uncovered that our multi-region Kafka failover was silently broken — `exceptionally()` returning null instead of chaining to secondary. Fixing that was a free bonus.

Reactive as a Q3 initiative quietly got descoped — load testing showed sync was fine at our request rate. The engineer who'd championed it ended up agreeing the framework-only call was correct.

---

## Technical depth — if they probe

- **`.block()` on non-reactive thread**: Tomcat worker thread. Synchronous semantics. The anti-pattern is `.block()` on Netty's event-loop thread — we don't have one.
- **Flagger canary config**: `stepWeight: 10`, `interval: 1m`, `request-success-rate > 99`, `P99 < 500ms`. Five failed checks → automatic rollback.
- **Hibernate 6 enum fix**: `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` on every Postgres enum field. Without it, Hibernate sends VARCHAR and Postgres rejects it.
- **CompletableFuture failover fix**: old code `.exceptionally(ex -> { log.error(...); return null; })` — secondary never tried. New code chains `handleFailure(...).join()` properly. Migration uncovered an existing bug.
- **WebClient timeout follow-up (6 months later)**: PR #1564 added explicit timeout + retry with exponential backoff. RestTemplate had implicit timeouts; WebClient does not.

---

## Likely follow-ups

**Q: How did the senior engineer take it?**
> Not thrilled at first. I went to him 1:1 before the team meeting, gave him a real path forward (own the Q3 reactive proposal), and committed to backing him on it. Going to him first, not in the meeting, was the move.

**Q: What if you'd been wrong about `.block()`?**
> Flagger would have auto-rolled back at 10 percent traffic. Worst case: a few hours of partial impact, instant rollback. I sized the blast radius before betting.

**Q: How did you communicate the timeline change to suppliers?**
> Suppliers didn't see a change. Migration was internal; the API contract didn't move. The change was internal — what I had to communicate was the scope decision to the team and the security audit owner.

**Q: When does .block() become a real problem?**
> When downstream is slow and request rate is high enough to drain Tomcat's 200-thread pool. We hit a softer version 6 months in — WebClient default timeout was effectively unbounded. Fixed with explicit 2s timeouts + Resilience4j circuit breaker.

**Q: What did you learn about communicating disagreement?**
> Bring numbers, not opinions. Own the decision in the meeting. Don't ambush the person you're disagreeing with. Give them a real path forward — "Q3 initiative" was a real offer, not a brush-off.

---

## What NOT to say

- Don't say "I was right and he was wrong" — his proposal was reasonable; the disagreement was scope and timing.
- Don't oversell — `.block()` isn't a victory lap; it's a deliberate trade-off with known follow-up cost.
- Don't pretend reactive will never make sense — at 1000+ req/sec per pod, it would.

---

## Backup story (if asked for another)

At GCC I'd planned single-Postgres for the Coffee API. Mid-design I benchmarked an analytics-heavy query — 30+ seconds. Postgres was the wrong tool for OLAP at our profile counts. I pivoted to dual-DB: Postgres for OLTP, ClickHouse for OLAP, both managed through the same session middleware so commits and rollbacks are atomic across them. Had to communicate the scope expansion to the lead — I framed it as "two weeks more now or six months of slow dashboards later" and brought the benchmark numbers. Got the green light.
