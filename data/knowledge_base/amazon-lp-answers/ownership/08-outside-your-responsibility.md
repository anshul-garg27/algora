# Q: Tell me about a time you did something outside your responsibility.

> **LP**: Ownership
> **Primary story**: `W2 — Shared Library Adoption`
> **Backup story**: `G7 — Sole Architect for 6 Services`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

I'd been at Walmart for about five months. My slice was adding audit logging to `cp-nrti-apis`, the supplier-facing service I owned. While I was writing my filter and async config, a slack thread in the broader Data Ventures channel caught my eye. Another team was wrestling with exactly the same problem — capturing HTTP request and response bodies without breaking the controller. A third team chimed in: "we just built ours yesterday."

### Task

My job ended at "audit logging works for my service." But that meant three teams writing 500 nearly identical lines of Spring filter code. So I made it my problem.

### Action

I went to my manager with a one-page proposal. One week to extract the audit logging into a shared Spring Boot starter JAR. Three teams pre-committed to evaluate it. He said yes but warned me — "adoption is on you."

First thing I did was talk to the other two teams. Not announce — listen. Sat with their engineers for about an afternoon each. About 80% of what they needed was identical to my code. The 20% that differed was real, not cosmetic — one team needed response body capture turned off because some endpoints returned PII, another wanted custom endpoint filtering with regex. I made those bits configurable through CCM, not hardcoded.

The library was about 500 lines. A `LoggingFilter` extending `OncePerRequestFilter` with `@Order(LOWEST_PRECEDENCE)` so it ran after security filters. `ContentCachingRequestWrapper` so reading the body didn't consume the stream. An `@Async` audit service with a bounded thread pool — 6 core, 10 max, queue 100 — so audit failures never blocked the API path.

The bigger work was getting people to use it. I wrote a copy-paste README, not "read the JavaDoc". Recorded a 5-minute screen-recorded walkthrough. Held a 1-hour office hour every Friday for the first month. Reviewed every integration PR personally — not just to approve, to teach. One team set `maxPoolSize=100` which would have blown up JVM memory. I showed them the sizing formula `(requests/sec × latency) × 2` and they reduced it to 20.

The one design choice I almost got wrong: queue capacity. I picked 100. A senior engineer pushed back — said silent drops could happen under load. He was right. I added a metric for rejected tasks and a Grafana alert at 80% queue depth. That alert has fired twice in production for legit slowdowns we needed to know about.

### Result

Three teams adopted in the first month. Integration time dropped from about two weeks of custom work to one day. The library is now on version 0.0.54 supporting JDK 11 and JDK 17. Five more teams picked it up across the next quarter. One was outside Data Ventures entirely.

Honestly, the thing that surprised me was how much the office hours mattered. Half the adoption value came from sitting with engineers for 15 minutes on a Friday, not from the library itself.

---

## Technical depth — if they probe

- **`@Order(LOWEST_PRECEDENCE)`**: Filter runs last, after all Spring security filters. So we capture the final state — including failed auth attempts and their error responses. Higher priority would miss them.
- **`ContentCachingRequestWrapper` / `ContentCachingResponseWrapper`**: HTTP body streams can only be read once. Without wrapping, the controller would receive an empty body after the filter consumed it. The wrapper buffers the bytes.
- **`@Async` with bounded pool**: 6 core handles ~100 req/sec steady, 10 max for bursts, queue 100 absorbs short spikes. `AbortPolicy` on overflow — we catch the rejection and log a warning, never throw to the caller. Audit is best-effort, never blocks the API.
- **CCM-driven config**: Endpoints to audit, response-body capture toggle, audit-service URL, signature key version — all in CCM. Teams flip behaviour at runtime, no redeploy.
- **WebClient + `.block()`**: Used Spring WebFlux's `WebClient` because `RestTemplate` is deprecated in Spring 6. Wrapped in `.block()` to fit the synchronous filter context.

---

## Likely follow-ups

**Q: Did your manager want you working on someone else's problem?**
> Not initially. I framed it: one week, three teams benefit immediately, more later. He said yes with the caveat that adoption was on me. If I'd just disappeared into a side project, that's a different conversation.

**Q: What if no one adopted it?**
> Then I'd have wasted a week and learned to scope-down. I de-risked by pre-committing the two other teams before I started. They'd already said "if you build this, we'll try it."

**Q: How did you handle differing requirements between teams?**
> Took the 80% that was common and made the rest configurable through CCM. Response body capture, endpoint filters, thread pool sizes. The library shipped opinionated defaults; teams override what they need.

**Q: Why a library and not a sidecar?**
> Sidecars work at the network layer. They can't see "which supplier called which endpoint semantically." That context only lives in the application. Library cost is one Maven dep; sidecar cost is operational forever.

**Q: What's the hardest part of building cross-team libraries?**
> Versioning. We're on 0.0.54 now. Every breaking change is a coordination cost. I learned to add new things as optional fields with sensible defaults, never break existing callers.

---

## What NOT to say

- Don't say "I built it alone" — the 20% configurable bits came from the other teams' real needs.
- Don't claim it solved audit logging end-to-end — this was the library; the publisher service was separate.
- Don't oversell adoption — three teams month one, eight teams total over a quarter, not "every team at Walmart".
- Avoid the word "stakeholders" — say "the other two teams" or "their engineers".

---

## Backup story (if asked for another)

At Good Creator Co. I was an SE-I but quietly took on the scope of six backend services — Beat, Event-gRPC, Stir, Coffee, the API gateway, and a fake-follower ML pipeline. Nobody assigned that scope. The four-person team didn't have anyone else covering it. About 60K lines of Go and Python over 15 months, 10K events/sec at peak. Outside my title, inside my responsibility once I picked it up.
