# Q: Describe a time you eliminated redundant work.

> **LP**: Invent and Simplify
> **Primary story**: `W2 — Shared Library Adoption`
> **Backup story**: `G10 — Event-gRPC consolidation`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Early last year three services on our Walmart team were each building audit logging — `cp-nrti-apis`, `inventory-status-srv`, and the DSD notification service. Splunk was being decommissioned and suppliers wanted self-serve query access to their API logs. I was in three different design reviews where engineers were drawing the same diagram: servlet filter, async sender, Kafka. The naming was different. The class shape was the same.

### Task

Nobody asked me to centralise this. My own service was about to build its version. But the duplication was real and somebody had to call it out before three implementations diverged in production.

### Action

I went to each team lead one-on-one. Not as a pitch — as a question. "What endpoints do you audit, what headers do you need, do you want response bodies?" Three conversations, about an hour each.

About 80 percent was identical. The 20 percent that differed: endpoint filtering (one team had 10 endpoints, another had 40), response-body capture (large responses doubled storage cost), and custom header propagation. I made the 20 percent configurable via CCM — Walmart's runtime config — so teams didn't need a redeploy to tweak any of it.

I built `dv-api-common-libraries` as a Spring Boot starter. One Maven dependency, one CCM block, done. The library uses Spring's auto-configuration to register `LoggingFilter` as a `@Component` with `@Order(LOWEST_PRECEDENCE)` so it runs after security filters. `ContentCachingRequestWrapper` lets the controller still read the body — HTTP streams can only be read once. The audit send is `@Async` with a bounded thread pool (6 core, 10 max, 100 queue) so audit failures never block the API.

I personally helped each team integrate — paired on their PRs, ran a brown-bag demo, wrote the docs. When a senior engineer challenged the queue size (silent drops were a risk) I added a Prometheus metric for rejected tasks and a WARN log at 80 percent capacity. He was right; I shipped his fix.

### Result

Three teams adopted within a month. Integration time dropped from two weeks to one day. About 1,500 lines of duplicated code never got written. The library is on version 0.0.54 today, supporting both JDK 11 and 17. The 80 percent queue warning has fired once — caught a downstream slowdown before it became an outage. The pattern became the org default for any new supplier-facing service.

---

## Technical depth — if they probe

- **`@Order(LOWEST_PRECEDENCE)`**: runs after security filters so we capture the final state — including 401s.
- **`ContentCachingRequestWrapper` + `copyBodyToResponse()`**: HTTP body is a one-shot stream. Wrapper caches bytes. Missing the copy-back call = empty response to client. One-line bug, catastrophic.
- **Thread pool sizing**: 100 req/sec × ~50ms audit = ~5 threads. 6 core, 10 max for spikes, 100 queue for bursts. At 2KB/payload, 200KB memory ceiling.
- **CCM runtime config**: endpoint regex + response-body toggle. Teams flip endpoints without a redeploy.
- **Signature-auth headers**: every audit request signed with RSA from AKeyless (Walmart's secret manager). HMAC-SHA256, rotatable key version, replay protection via timestamp.

---

## Likely follow-ups

**Q: How did you get the first team to switch?**
> I started with my own team — that was easy. Then I showed up at team #2's design review with "you're about to build this; I have it built; here's the integration guide." Team #3 came to me without a pitch.

**Q: What was the hardest team to convince?**
> Team #2 had already started their version. They didn't want to throw away two weeks of work. I offered to help them migrate — paired on the PR for an afternoon — and used their feedback (they wanted response-body capture configurable) to improve the library. Their improvement became a flag everyone benefits from.

**Q: Why a library and not a sidecar?**
> Sidecars work at the network layer — they don't see application context like which supplier authenticated or which endpoint was hit semantically. We needed that context inside the application.

**Q: What if a fourth team wanted something different?**
> The 20 percent of differences taught me to default to "make it a config flag, not a fork." A fourth team came along and wanted a custom header — I added it as a CCM property. The library is now used by 4 services.

**Q: What would you do differently?**
> Skip the publisher service — publish directly to Kafka from the library. Removes a network hop. Original concern was every service taking a Kafka dependency, but the team is mature enough with Kafka now that the trade-off's flipped.

---

## What NOT to say

- Don't claim "I single-handedly stopped duplication" — the conversations with each team lead were the actual work.
- Don't pretend the queue size was obviously right — it wasn't. The senior engineer's challenge improved the library.
- Don't pitch this as "I deleted three teams' code." I prevented duplicated code from being written and migrated one team's already-started work.

---

## Backup story (if asked for another)

At GCC, Event-gRPC had grown 60+ event types — Branch, WebEngage, Vidooly, Shopify — each with its own HTTP endpoint, validator, and worker pool. I consolidated them onto one gRPC `EventService.dispatch()` with protobuf-typed events and pluggable per-type sinkers. Adding a new event source dropped from three days to about an hour. Three days of plumbing for a ten-line business change was the smell that drove this.
