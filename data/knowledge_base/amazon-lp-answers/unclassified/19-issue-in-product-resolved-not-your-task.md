# Q: Tell me about a time when you found an issue in a product and resolved it (even though it wasn't your task).

> **LP**: Ownership (hybrid)
> **Primary story**: `W2 — Shared Library Adoption`
> **Backup story**: `W3 — DiscardPolicy Feedback`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

While building the audit publisher for my own service at Walmart, I was reading through other teams' design docs to make sure my Kafka topic naming didn't collide with theirs. That's when I caught it. Inventory Status and Transaction Events were each writing their own audit filter from scratch. Three teams, three filters, three different ways to read the HTTP body.

### Task

This wasn't my problem on paper. My ticket said "ship audit for cp-nrti-apis." But I could see two future bugs already — inconsistent schemas in BigQuery and three latency profiles to debug.

### Action

I scheduled a short call with the lead engineer on each team. Not to pitch a solution, just to ask what they were building. Both confirmed the same async-after-response pattern. One was reading the body before the filter chain finished, which would break Spring Security. The other was using `RestTemplate` synchronously on the request thread, which would tank P99.

I went back to my manager with numbers. If I spent two extra weeks building a shared starter, three teams save two weeks each. Net positive of four engineering-weeks plus consistent schema in BigQuery.

He agreed but wanted me to keep my original deadline. So I cut scope on my service's nice-to-haves — moved trace correlation to v2 — and used the saved time on the library.

The build was a Spring Boot starter, `dv-api-common-libraries`. `LoggingFilter` at `@Order(LOWEST_PRECEDENCE)` to capture the final response after security. `ContentCachingRequestWrapper` for safe body reads. `@Async` with a bounded thread pool to keep it off the request path. CCM-driven config so each team picks its own endpoints and body-capture rules.

I sat with each team for an afternoon on their integration PR. Caught a 100-thread executor config that would've blown a 2GB heap. Caught a missing exclusion for `spring-boot-starter-webflux` that would've broken Spring MVC autoconfig.

### Result

Three teams onboarded in three weeks. Their per-team integration cost dropped from two weeks to one day. BigQuery now has one schema across all of them, so suppliers can join audit data across services with one query. The library hit version 0.0.54 and five teams use it today. I still wasn't tasked with any of this when I started.

---

## Technical depth — if they probe

- **Why a Spring Boot starter, not a class library**: Auto-config. `@EnableAutoConfiguration` picks up our `LoggingFilterAutoConfiguration` from `META-INF/spring.factories`. Teams add the Maven dep and a YAML block — that's the entire integration.
- **The `LOWEST_PRECEDENCE` decision**: Spring's filter chain runs by `@Order`. Lowest precedence runs last, so we see the response after Spring Security has done its thing — auth failures included.
- **Async backpressure**: 6 core threads, 10 max, 100 queue. When the queue fills, `RejectedExecutionHandler` drops. I added a counter `audit.tasks.rejected` and a WARN log at 80 percent queue depth.
- **Schema discipline**: Avro with Schema Registry. Backward-compatible only. New fields default to nullable. No breaking changes shipped in 9 months.

---

## Likely follow-ups

**Q: Did the other teams resent you stepping in?**
> The lead on Inventory Status pushed back at first — felt like I was rewriting his design. I sent him the field-by-field schema diff and asked which fields he'd lose. He found three he didn't need. That conversation flipped him.

**Q: What if the library has a regression?**
> Versioned releases. Teams pin a version, upgrades are opt-in. I treat it as a public API now — semver, deprecation warnings before breaking changes, changelog with migration notes.

**Q: How did you split your time?**
> Roughly 60 percent on my own service, 40 percent on the library and reviews. The trick was cutting my own scope — I dropped trace correlation from v1 and shipped it later.

**Q: Have you reused this pattern?**
> Yes. When I saw the same drift starting on circuit-breaker config across services, I pushed for a shared Resilience4j base config. Same playbook — find the 80 percent, ship it as a starter, hold office hours.

---

## What NOT to say

- "I knew better than the other teams" — frame it as catching drift early, not correcting them.
- Don't make the manager sound like a villain — he agreed, he just held the deadline. That's reasonable.
- Avoid "I saved 480 hours" without showing the math.

---

## Backup story (if asked for another)

During the same audit work, I shipped a thread-pool with a DiscardPolicy and didn't add queue-depth instrumentation. A senior engineer flagged it on the PR — silent drops on overflow. I defended it for a day, then realised he was right and added a Prometheus counter, an 80-percent WARN log, and a Grafana panel. We caught the queue saturating once during a downstream slowdown, before any audits dropped. The issue wasn't mine to fix; the standard was mine to raise.
