# Q: Tell me about a difficult decision you made recently.

> **LP**: Are Right, A Lot
> **Primary story**: `W5 — Spring Boot 3 .block() vs Webflux`
> **Backup story**: `W4 — Active/Active vs Active/Passive`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

In March I was kicking off the Spring Boot 3 migration for `cp-nrti-apis`, our main supplier-facing API. Snyk was flagging CVEs we couldn't patch without upgrading; the security audit deadline was 3 months out. In the kickoff a senior engineer proposed going fully reactive with WebFlux — "we're touching every HTTP call anyway, RestTemplate is deprecated, this is the moment." The room was leaning his way.

### Task

I owned the migration. Pick the scope. Live with it.

### Action

I bought a day to think. Two real options.

Full reactive. Every service returns `Mono` or `Flux`. Exceptions become signals. Team needs reactive training. Estimate based on the file count and how deep the refactor would go: 3 months minimum. Within the security deadline only if everything goes right.

Framework-only with WebClient `.block()`. Behaviour matches RestTemplate. Business logic unchanged. Tests stay synchronous (mocking is uglier but the shape is the same). 4 weeks.

The `.block()` anti-pattern objection was the hard part. He framed `.block()` as universally bad. I went to the WebFlux docs. `.block()` is an anti-pattern on a reactive thread — Netty's event loop. We don't have a reactive thread. We're on Tomcat's worker pool. `.block()` there is just synchronous behaviour. Same semantics as RestTemplate. The anti-pattern label didn't apply to our deployment shape.

I made my recommendation to the lead in 1:1 the next day. Framework-only with `.block()`. Reactive proposed as a separate Q3 initiative — full architecture work, training plan. Sized the blast radius too: if I was wrong about thread starvation, Flagger's auto-rollback at 10 percent canary traffic would catch it. Hours of partial impact, instant rollback, redo. Bounded downside.

I told the senior engineer 1:1 before the team meeting, not in it. "I'm recommending framework-only because of the security deadline. I want you to own the Q3 reactive proposal." Gave him a real path forward.

Lead approved. Engineer accepted (not enthusiastically). I shipped.

### Result

4 weeks. Zero customer-impacting issues on rollout. Flagger canary, gradual 10 → 25 → 50 → 100 percent over 24 hours. The CompletableFuture migration uncovered an existing failover bug — `exceptionally()` was returning null instead of chaining to the secondary Kafka cluster. Free fix.

Six months later we hit a real WebClient issue under load — explicit timeouts were missing because RestTemplate had implicit ones. Fixed in PR #1564 with exponential backoff. That's the known follow-up cost of `.block()` and I'd documented it as tech debt up front.

Reactive as a Q3 initiative quietly got descoped — load testing showed sync was fine. The senior engineer eventually agreed the framework-only call was right.

Difficult decisions are the ones where you can argue either side honestly. This one was hard because his argument wasn't wrong — it was just wrong for our timeline and traffic shape.

---

## Technical depth — if they probe

- **`.block()` on Tomcat thread**: synchronous semantics on request thread. The anti-pattern is `.block()` on Netty's event loop. Different threadpool, different rules.
- **Flagger canary**: 10 percent step weight, 1-minute check interval, `request-success-rate > 99`, `P99 < 500ms`. Five failed checks → automatic rollback.
- **Tomcat threadpool math**: 200 threads × ~200ms avg response = 1000 req/sec ceiling per pod. We're at 100. 10x headroom for `.block()` to be safe.
- **CompletableFuture failover fix**: old code `kafkaPrimaryTemplate.send().exceptionally(ex -> { log.error(...); return null; })` swallowed errors. New code chains `handleFailure(...).join()`.
- **PR #1564 WebClient timeouts (6 months later)**: 2-second `responseTimeout`, Resilience4j retry with exponential backoff, `NrtiUnavailableException` on exhaustion. Known follow-up cost.

---

## Likely follow-ups

**Q: What made it difficult?**
> The senior engineer wasn't wrong on principle — full reactive is the modern path. The difficulty was that I had to recommend the less-ambitious option without sounding like I was dodging hard work. Owning the call ("if it fails that's on me") was how I made the recommendation defensible.

**Q: How did you size the blast radius?**
> Flagger auto-rollback at 10 percent canary traffic with 1 percent error threshold. Worst case: a few hours of partial impact for 10 percent of suppliers, instant rollback. Bounded. The bound was the actual case for accepting the risk.

**Q: Have you used .block() in production before this?**
> Yes — the audit-library's WebClient call uses `.block()` for the same reason. Synchronous context, non-reactive thread, behaviour matches RestTemplate. Two production systems on the same pattern.

**Q: When would you regret this decision?**
> If request rate per pod tripled and downstream latency stayed where it is, Tomcat's thread pool would start filling. We'd need explicit timeouts (already added), circuit breaker (mostly added), and eventually reactive for the I/O-heavy endpoints. The decision was right for the load profile of the time.

**Q: What's the broader pattern in how you make these calls?**
> Pick the scope that fits the deadline and the team's current skills. Bound the downside. Give the disagreeing party a real path forward — not just a "no." Own the call.

---

## What NOT to say

- Don't oversell — `.block()` isn't a victory lap. It's a deliberate trade-off with a known follow-up cost (the timeout PR six months later).
- Don't pretend reactive is universally wrong — wrong tool for our scale, right tool for many systems.
- Don't disparage the senior engineer's proposal — it was reasonable. The disagreement was scope and constraint.

---

## Backup story (if asked for another)

The other recent hard call: active/active vs active/passive for the audit-logging multi-region work. Active/passive is simpler — one cluster runs, the other warms. Active/active is 2x infrastructure but 15-minute recovery instead of 30-plus. I picked active/active because compliance couldn't tolerate the 30-minute window. Cost was justified by RPO. We hit 15-minute recovery on the next real outage, under our formal 1-hour RTO target.
