# Q: Tell me about a time when you had to make a decision between long-term value or short-term results.

> **LP**: Think Big / Are Right A Lot (hybrid)
> **Primary story**: `W5 — Spring Boot 3 Migration`
> **Backup story**: `G1 — ClickHouse Migration`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Mid-Spring-Boot-3 migration at Walmart, March 2025. I was four weeks out from a hard deadline. `cp-nrti-apis` runs 100 requests per second per pod and supports Pepsi, Coca-Cola, Unilever. A teammate proposed going fully reactive — switch `RestTemplate` to `WebClient` and rewrite every service to return `Mono` or `Flux`. His argument was solid: we're already in the code, why ship halfway?

### Task

Pick one of two paths and live with the consequences. Either the long-term clean architecture (full reactive) or the framework-only migration with `.block()` calls that ships on time.

### Action

I sat down with both options and tried to be honest about them.

Reactive end-to-end meant rewriting business logic. Every service method becomes a chain of `flatMap` and `onErrorResume`. Exceptions stop being exceptions — they become error signals on a stream. Tests fundamentally change. The team has never written reactive code in anger. My honest estimate was three months, plus a few weeks of bugs while everyone learned the new patterns.

Framework-only with `.block()` meant `WebClient` everywhere but the threading model stays the same. Business logic untouched. Tests get harder because `WebClient` mocking is verbose, but the runtime behavior matches `RestTemplate`. Four weeks.

The honest argument against `.block()` is that it looks like an anti-pattern. The honest counter is that `.block()` on a plain MVC thread is fine — it's only dangerous on the Netty event loop, which we don't have.

I didn't argue in the meeting. I wrote a one-pager with both options, the risks, the team-readiness cost, and the customer impact. I scheduled a 1:1 with my lead and walked through it. My recommendation: ship framework-only now, propose reactive as a separate Q3 initiative once we have monitoring in place to prove the load justifies it.

He agreed. I committed to writing up the reactive proposal in Q2 so the long-term value didn't get lost.

### Result

`cp-nrti-apis` shipped in four weeks, zero customer-impacting issues, automated canary rollback never tripped. The reactive proposal landed two quarters later as its own initiative — same team, more time, no production pressure. Honestly, the part I'm proud of is that I didn't pretend the short-term call was the best call forever. I picked the safer ship and committed to revisit it.

---

## Technical depth — if they probe

- **Why `.block()` is safe here**: Plain MVC servlet threads, not Netty. `.block()` parks the thread, no event-loop starvation. Effectively `RestTemplate` behaviour with `WebClient`'s newer API.
- **What we'd gain from reactive**: Better thread efficiency under high concurrency. At 100 req/sec/pod we don't need it. At 1000+ req/sec/pod, we would.
- **Flagger canary**: Istio traffic split, 10/25/50/100 over 24 hours, auto-rollback at 1 percent 5xx.
- **Test mocking cost**: WebClient mocks doubled test-file size. 42 files updated. Not free, but bounded.

---

## Likely follow-ups

**Q: Did the teammate who pushed for reactive stay bought-in?**
> He led the Q3 reactive proposal. The way I handled the disagreement — write it up, take it offline, present in 1:1 — built trust. He told me later he'd have been more annoyed if I'd shot him down in the meeting.

**Q: When does `.block()` actually become a problem?**
> When you've got reactive code calling reactive code on Netty's event loop. Block there and you starve every other request sharing that loop. Easy to introduce by accident if half your stack is reactive and half isn't.

**Q: What would have made you pick reactive?**
> If our load was already past 500 req/sec/pod and we were adding pods just to handle bursts. We weren't. We were nowhere near saturated.

**Q: Was the reactive proposal actually adopted?**
> Partially. They picked three high-throughput endpoints and reactive-ified those. The rest stayed `.block()`. Pragmatic outcome.

---

## What NOT to say

- "Reactive was wrong" — it wasn't wrong, it was wrong-for-now.
- "I was right" — I was right enough to ship; the long-term call still lives.
- Don't make the teammate sound difficult. He pushed in good faith.

---

## Backup story (if asked for another)

At GCC, Postgres was choking on 10M+ log writes a day. Quick fix: more Postgres replicas. Long-term fix: rebuild the pipeline through RabbitMQ into ClickHouse. I chose the long-term — two weeks of dual-write, then cutover, then decommission. Got 5x compression, 99 percent write-latency reduction, 30 percent infra cost drop. More short-term pain, better long-term shape.
