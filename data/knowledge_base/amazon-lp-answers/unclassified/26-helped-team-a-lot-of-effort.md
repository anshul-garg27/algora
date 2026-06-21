# Q: tell me about a time where you did something that helped the team a lot of effort.

> **LP**: Invent and Simplify (hybrid)
> **Primary story**: `W2 — Shared Library Adoption`
> **Backup story**: `G10 — Event-gRPC`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

When Splunk got decommissioned at Walmart, every team needed an audit-logging replacement. Three teams in my org were already starting their own — Inventory Status, Transaction Events, and mine, `cp-nrti-apis`. Three filters, three Kafka pipelines, three different schemas in BigQuery.

### Task

Stop the divergence before it shipped. Save the team from rebuilding the same thing three times and from a year of debugging schema mismatches.

### Action

I spent two evenings reading the other two teams' design docs. The 80 percent overlap was clear — filter intercepts HTTP, captures body, fires async to Kafka. The 20 percent that differed was config: which endpoints, whether to capture response body, latency budget per service.

I pitched a shared Spring Boot starter to my manager. He pushed back on scope — "ship yours first, share later." I came back with the math. Three teams times two weeks each times 40 hours equals 240 engineering hours. Plus one shared schema in BigQuery so suppliers could join audit data across services in a single query. He agreed, on condition I kept my deadline.

I cut trace correlation from my v1 to buy back the time and started building.

`dv-api-common-libraries` as a Spring Boot starter. Two Maven coordinates and a YAML block to integrate. `LoggingFilter` with `@Order(LOWEST_PRECEDENCE)` so it runs after Spring Security and captures auth-failure responses. `ContentCachingRequestWrapper` to handle the HTTP-body-is-a-stream problem. `@Async` with a bounded thread pool — 6 core, 10 max, 100 queue — so the API response returns immediately. CCM-driven endpoint filtering and response-body toggle.

I held Friday office hours for a month and reviewed every adoption PR personally. Caught a 100-thread executor that would've blown the heap. Caught a missing `spring-boot-starter-webflux` exclusion. Eleven separate issues, none of them shipped.

### Result

Three teams onboarded in three weeks. Integration cost per team dropped from two weeks to one day. BigQuery now has one schema across all of them. The library is at version 0.0.54, five teams use it today, and it's the default for new services in our org. Roughly 480 engineering hours saved across adoption — math we revisited at the end of the quarter.

---

## Technical depth — if they probe

- **Auto-config trick**: `META-INF/spring.factories` registers `LoggingFilterAutoConfiguration`. Teams add the Maven dep, Spring picks it up, no `@Import` or `@Configuration` needed in their code.
- **`@Order(LOWEST_PRECEDENCE)`**: Spring's filter chain runs by `@Order`. Lowest precedence runs last, so we see the response after Spring Security. Auth failures get audited too.
- **`ContentCachingRequestWrapper`**: HTTP bodies are streams — read once. Without this, the filter reads the body and the controller gets empty input. Wrapper caches the bytes so both can read.
- **Backpressure**: Queue full = `RejectedExecutionHandler` drops. Counter `audit.tasks.rejected` plus WARN log at 80 percent capacity. Caught one near-miss in production.

---

## Likely follow-ups

**Q: How did you sell it to a skeptical team?**
> Inventory Status thought their needs were unique. I asked for their endpoint list and built endpoint filtering as a CCM regex. Transaction Events worried about latency — I ran JMeter against their staging and showed P99 overhead under 5ms. Data did the convincing.

**Q: What did you cut from your own service to make room?**
> Trace correlation. Shipped without `traceId` propagation in audit headers in v1. Added it in v2 three weeks later. Honest tradeoff — my service was slightly less debuggable for three weeks so three teams could ship.

**Q: How do you handle library upgrades?**
> Semver. Teams pin versions. Breaking changes get a deprecation cycle. I've shipped 47 minor versions in 9 months with zero breaking changes — discipline matters more than the version number.

**Q: What if someone else had built it instead?**
> Fine by me. The work was the bottleneck, not the credit. I'd have used theirs and contributed back.

---

## What NOT to say

- "I single-handedly saved 480 hours" — frame as enabling, not heroics.
- Don't oversell the manager pushback. He was reasonable, just guarding the deadline.
- "It was simple" — it wasn't. Getting three teams to agree on anything is the hard part.

---

## Backup story (if asked for another)

At GCC, the Event-gRPC service was doing per-row INSERTs into ClickHouse for 10M+ events a day. I built a buffered sinker — batches of 1000 records flushed by size or by a 5-minute ticker, whichever hit first. Single one-week effort, 99 percent reduction in DB calls per second, 5x storage compression, 30 percent infra cost drop. One pattern across all eight event types — no team had to figure out batching themselves.
