# Q: Tell me about a time when you did something which was not your responsibility.

> **LP**: Ownership
> **Primary story**: `W2 — Shared Library Adoption`
> **Backup story**: `G7 — Sole Architect for 6 Services`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Six months into my Walmart role, I was building audit logging for my own service — `cp-nrti-apis`. I noticed two other teams in slack threads asking similar questions. One was wiring up a servlet filter to capture HTTP bodies. Another was wrestling with thread pool config for `@Async` audit calls. I was about to ship the same code as them for the third time.

### Task

Strictly, my task was: add audit logging to my service. Not my job to think about anyone else's. But three teams writing the same 500 lines of code didn't feel right.

### Action

I asked my manager for a week to extract it into a shared library. He said okay but warned me — "if adoption fails, that's on you." Fine.

I went to the two other teams first, not last. Sat with their engineers for an afternoon each. Asked what they actually needed. Turns out about 80% of the code was identical, and the 20% that differed was real — one team needed response body logging off, another wanted different endpoint filters. So I made those bits configurable through CCM (our config management), not hardcoded.

The library itself was small — about 500 lines. A `LoggingFilter` extending `OncePerRequestFilter` with `@Order(LOWEST_PRECEDENCE)` so it ran after security filters. `ContentCachingRequestWrapper` and `ContentCachingResponseWrapper` so we could read the body without consuming the stream. An `@Async` service with a bounded thread pool — 6 core, 10 max, queue capacity 100 — so audit failures never blocked the API.

The harder part was getting people to use it. I wrote a README with copy-paste examples, not "read the docs". Made a 5-minute screen-recorded walkthrough. Ran a weekly office hour for a month. Reviewed every integration PR personally — not to approve, to teach. One team set `maxPoolSize=100` which would've blown up JVM memory; I showed them the sizing formula `(requests/sec × latency) × 2`.

Looking back, the spec change I'm most proud of was making it boring. No magic. Add the Maven dependency, set `audit.logging.enabled: true`, done.

### Result

Three teams adopted in the first month. Integration time dropped from about two weeks of custom work to one day. The library is now on version 0.0.54 and supports both JDK 11 and JDK 17. Five more teams picked it up over the next quarter. One of them was outside Data Ventures — not my org at all.

What I learned: nobody assigns you the cross-team work. You see it and pick it up, or it doesn't happen.

---

## Technical depth — if they probe

- **`@Order(Ordered.LOWEST_PRECEDENCE)`**: Filter runs last, after all security filters. We capture the final state of request and response, including failed auth attempts. Higher priority would miss auth failures.
- **`ContentCachingRequestWrapper`**: HTTP input streams can only be read once. Without wrapping, the controller would get an empty body after the filter read it. The wrapper caches bytes for re-reading.
- **`@Async` thread pool sizing**: 6 core handles steady traffic (~100 req/sec), 10 max for bursts, queue capacity 100 absorbs short spikes. Default `AbortPolicy` rejects when queue is full — we catch the rejection and log, never propagate. Audit is best-effort, not critical path.
- **CCM-driven config**: Endpoints to audit, response body capture on/off, audit service URL — all in CCM, not in code. Teams flip behaviour at runtime without a redeploy.
- **WebClient with `.block()`**: The HTTP service uses Spring WebFlux's `WebClient` instead of `RestTemplate` (deprecated in Spring 6). The `.block()` call converts the reactive chain back to synchronous inside the filter context.

---

## Likely follow-ups

**Q: Why a library and not a sidecar like Envoy?**
> Sidecars work at the network layer. They can't see "which endpoint was called semantically" or "which supplier made this request". That context only exists inside the app. A library gives us that for the cost of a Maven dependency.

**Q: What if the audit service is down?**
> The API keeps working. We catch all exceptions in `AuditLogService` and log them but don't propagate. The thread pool queue absorbs brief outages. Extended outages lose audit data, but the user-facing path is untouched.

**Q: How did you get teams to adopt it?**
> Three things, in order. Made it cheap to try — one Maven dep, one config flag. Made it cheap to integrate — copy-paste README, video, office hours. Made it cheap to debug — every PR I reviewed myself for the first month.

**Q: What was the hardest design call?**
> Queue size. I picked 100. A senior engineer challenged it — said it could cause silent drops. He was right. I added a metric for rejected tasks and a warning when the queue hit 80%. That alert caught downstream slowdowns twice in production.

**Q: Was your manager happy you spent a week on this?**
> Yes, but only because I framed it before starting. "One week, three teams benefit, I own adoption." If I'd just disappeared into a side project, that's a different conversation.

---

## What NOT to say

- Don't say "I built it alone" — the 20% configurable bits came from the other two teams' input.
- Don't claim it solved everything — it was a library, not a platform. The audit publisher service was a separate concern.
- Don't oversell the adoption — three teams in month one, not twelve.
- Avoid "stakeholders" — just say "the other two teams" or "their engineers".

---

## Backup story (if asked for another)

At GCC, I was a SE-I owning six backend services that ran the whole influencer analytics platform. Nobody assigned me that scope. The founders quietly stopped putting other engineers on those services and I picked up the gap — Beat, Event-gRPC, Stir, Coffee, the gateway, and the fake-follower ML pipeline. About 60K lines of Go and Python over 15 months. End-to-end ownership at 10K events/sec.
