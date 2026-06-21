# Q: Describe a time your judgment was challenged and you stood by it.

> **LP**: Are Right, A Lot
> **Primary story**: `W5 — SB3 .block() defended in design review`
> **Backup story**: `G8 — RabbitMQ over Kafka tech-stack defence`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Last March I was kicking off the Spring Boot 3 migration for `cp-nrti-apis`. A senior engineer with more reactive-programming experience than me pushed hard in the kickoff meeting: "we're touching every HTTP call, RestTemplate is deprecated, this is the moment to go fully reactive with WebFlux." Most of the room was nodding. The framing was that `.block()` is an anti-pattern. He had two production wins on his record from past reactive migrations.

### Task

I'd been planning a framework-only migration with `WebClient.block()`. I had to decide if I should pivot to his proposal or stand my ground — and if I stood, I'd need to defend it to him and the lead.

### Action

I didn't argue in the meeting. I scheduled a 1:1 with the lead the next day and brought numbers.

Three points.

One — scope. Framework-only means business-logic classes don't change. Reactive means every service returns `Mono` or `Flux`, every exception becomes a signal. Estimate based on the file count: framework-only is 4 weeks, full reactive is 3 months minimum. We have a security deadline — Snyk-flagged CVEs we can't patch without upgrading, audit fails in 3 months.

Two — the anti-pattern claim. `.block()` is an anti-pattern on a reactive thread (Netty's event loop). We don't have a reactive thread. We're on Tomcat's worker pool. `.block()` on a Tomcat thread is just synchronous behaviour with the new client. Same semantics as RestTemplate. I went and read the WebFlux docs and pulled the relevant lines.

Three — the test for "am I wrong." If I shipped framework-only and we hit thread starvation in production, Flagger's auto-rollback at 10 percent traffic would catch it. Worst case: hours of partial impact, instant rollback, redo. Sized the blast radius.

I told the lead clearly: "I'm going to recommend framework-only. If it fails, that's on me. I want the senior engineer to own the reactive proposal as a separate Q3 initiative — full architecture work, training plan, the works." That gave him a real path forward.

The senior engineer pushed back again in writing — long Slack thread. I read it carefully, addressed each point with specifics (Tomcat threadpool size, our actual request rate of ~100/sec per pod, downstream latency profiles). Held the line. Didn't make it personal.

Lead approved. Engineer accepted it (not enthusiastically).

### Result

Shipped in 4 weeks. Zero customer-impacting issues on rollout. Flagger canary, gradual 10 → 100 percent over 24 hours. The CompletableFuture migration actually uncovered an existing failover bug — `exceptionally()` was returning null instead of chaining to the secondary Kafka cluster. Fixing that was a bonus from doing the migration correctly.

Six months later we hit a real WebClient issue under load — explicit timeouts were missing because RestTemplate had implicit ones. Added them in PR #1564 with exponential backoff. That's the kind of follow-up that comes with the trade-off, and I'd documented it as known tech debt up front.

Reactive as a Q3 initiative quietly got descoped — load testing showed sync was fine at our request rate. The engineer ended up agreeing the framework-only call was correct. Holding the line wasn't being stubborn; it was protecting scope on a security-deadline-driven migration.

---

## Technical depth — if they probe

- **`.block()` on Tomcat thread**: synchronous semantics on the request-processing thread. The anti-pattern is `.block()` on Netty's event loop. We're on Tomcat — different threadpool, different rules.
- **Flagger auto-rollback**: 5 failed checks × 2-minute interval × 1 percent error threshold. Bound on blast radius.
- **CompletableFuture failover fix**: old `.exceptionally(ex -> { log.error(...); return null; })` swallowed errors; new code chains `handleFailure(...).join()` properly.
- **Tomcat threadpool math**: 200 threads × ~200ms avg response = 1000 req/sec ceiling per pod. We're at 100. 10x headroom for `.block()` to be safe.
- **PR #1564 WebClient timeouts**: 2-second `responseTimeout`, Resilience4j retry with exponential backoff, `NrtiUnavailableException` on exhaustion.

---

## Likely follow-ups

**Q: How did you handle the senior engineer's Slack pushback?**
> Read every point carefully, replied with specifics (Tomcat threadpool size, our request rate, downstream profile). Didn't engage with rhetoric — engaged with facts. Held the line without making it personal.

**Q: What if you'd been wrong?**
> Flagger auto-rollback at 10 percent traffic. Hours of partial impact, instant rollback, redo. The blast-radius sizing was the actual defence — even if my judgment was off, the cost was bounded.

**Q: Did the engineer trust you afterwards?**
> Took a quarter or so. The fact that I gave him a real path forward (Q3 reactive proposal) and never made the disagreement personal helped. We work fine together now.

**Q: When would you have switched to his proposal?**
> If the request rate had been 1000+ per pod, or if downstream calls had been so I/O-bound that synchronous threads were going to drain Tomcat. At our actual load, reactive was over-engineering.

**Q: What did you learn from holding the line?**
> Disagreement is easier when you bring numbers and own the call. "If this fails, that's on me" gives the other side an out — they're not the one defending it. And give them a real path forward, not just a "no."

---

## What NOT to say

- Don't claim I was right because I was right — I was right because the load profile fit. Wrong load, different call.
- Don't disparage the senior engineer — his reasoning was sound; the disagreement was scope and constraints.
- Don't oversell — the WebClient timeout follow-up six months later was a known cost of the trade-off; not hiding it is the honest version.

---

## Backup story (if asked for another)

At GCC the conventional choice for the 10M-events/day ClickHouse pipeline would have been Kafka. I picked RabbitMQ. The team already ran it for credentials, identity events, WebEngage. The CTO challenged it — "Kafka is the standard for event streaming at scale." I held the line with the volume math (115 events/sec average is well within RabbitMQ's range), the operational expertise the team already had, and the buffered-sinker pattern that gave us the batching benefit anyway. RabbitMQ held for two years; we never needed Kafka.
