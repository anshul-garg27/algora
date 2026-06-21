# Q: Tell me about a time when you did something which was not you responsiblity.

> **LP**: Ownership (hybrid)
> **Primary story**: `W2 — Shared Library Adoption`
> **Backup story**: `G7 — Sole Architect (6 services)`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

This was early in the Kafka audit work at Walmart. I was building the publisher tier for my own service, `cp-nrti-apis`. In the same week, two other teams — Inventory Status and Transaction Events — were quietly starting their own audit pipelines. Nobody had asked me to look at their work.

### Task

My job was to ship audit for one service. But I could see three near-identical implementations heading into production, with three different schemas and three different bugs.

### Action

I spent a couple of evenings reading their design docs. They were 80 percent the same — request capture, async publish, Kafka. The 20 percent that differed was config: which endpoints to audit, whether to capture response bodies, latency budget.

I went to my manager and asked for two extra weeks. My pitch was simple. If I extracted the common 80 percent into a shared library, three teams would integrate in a day instead of two weeks each. That's roughly 480 engineering hours saved.

He pushed back at first — "scope creep, just ship yours." I came back with the resistance I'd hit. One team wanted body logging, another didn't. I showed how that becomes a config flag, not a code change. Response body capture, endpoint filtering — all CCM-driven, no Java.

Then I built it. `dv-api-common-libraries` as a Spring Boot starter. `LoggingFilter` with `@Order(LOWEST_PRECEDENCE)` so it runs after security. `ContentCachingRequestWrapper` to read the body without consuming it. `@Async` with a 6-core, 10-max, 100-queue thread pool. Two Maven coordinates and a YAML block, and you're done.

I held Friday office hours for a month and reviewed every adoption PR myself. Caught a `100-thread` config in one PR that would've blown the heap.

### Result

Three teams shipped in three weeks instead of six. Integration dropped from two weeks to one day. The library is now version 0.0.54 with five teams on it. Nobody asked me to do this; I just couldn't watch three teams build the same thing badly.

---

## Technical depth — if they probe

- **Why a Spring Boot starter**: Zero code changes for consumers. `@ComponentScan` picks up the filter, `@EnableAsync` registers the executor, CCM loads runtime config. Add the dependency, done.
- **ContentCachingRequestWrapper**: HTTP bodies are streams — read once. Without caching, my filter would steal the body and the controller would get empty input. Cache wraps the input and lets both read.
- **Async tradeoff**: Fire-and-forget. If the queue fills, `RejectedExecutionHandler` drops audits silently. I added a Prometheus counter for rejected tasks plus a WARN log at 80 percent capacity.
- **Config-driven differences**: Endpoint filtering uses regex from CCM, response body capture is a boolean flag, thread pool sizes are tunable per service.

---

## Likely follow-ups

**Q: What did your manager say after?**
> He stopped asking me to scope down. Two quarters later, the library was the default for new services in our org, and he started citing the 480-hour saving in his own roadmap reviews.

**Q: Did any team resist adoption?**
> Inventory Status was wary — their latency budget was tighter. I ran a JMeter test on their endpoints with the library in line and showed under 5ms P99 overhead. They were in within a week.

**Q: What if the library has a bug?**
> Versioned releases, semver, opt-in upgrades. Teams pin the version they want. I treat the library like a public API now — backward-compatible only, deprecation warnings before breaking changes.

**Q: How did you handle disagreement on response body capture?**
> Made it a config flag. One team's "no, that's sensitive" and another team's "yes, we need it for debugging" can both be true. Code shouldn't pick one.

---

## What NOT to say

- "I went rogue" — frame it as a deliberate ask, not unsanctioned work.
- "It was easy" — the harder part was getting buy-in and absorbing the extra weeks.
- "We" — own the call. The teams owned their integrations.

---

## Backup story (if asked for another)

At GCC, I was hired for one backend role and ended up owning six services because the team was tiny and gaps kept opening up. Beat scraping, Coffee API, the gRPC ingestion service — I picked them up because nobody else would. I didn't ask permission; I asked forgiveness when something broke. By the time I left, those six services moved ~500K profiles a day.
