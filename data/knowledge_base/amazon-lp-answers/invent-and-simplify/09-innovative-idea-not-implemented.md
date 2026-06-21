# Q: What's the most innovative idea you've had that wasn't implemented?

> **LP**: Invent and Simplify
> **Primary story**: Idempotency-key middleware (scoped during W2)
> **Backup story**: Platform-level supplier-data service from W6 BigQuery RLS pattern
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

While building the shared audit library at Walmart I kept seeing the same bug class in supplier integrations. Suppliers retry on timeout. Network blips, gateway hiccups, their own client libs auto-retrying — pick your reason. We'd get the same POST twice within seconds. Some endpoints were idempotent by nature (read-only), some weren't (creating a notification record, queuing a DSD push). I noticed two team chats where someone said "we got a duplicate inventory event" and the answer was "your client retried, that's normal." It wasn't normal — we were eating the double-write silently.

### Task

I wasn't on the team that owned write endpoints. But I had the audit library context and could see this was a cross-cutting problem.

### Action

I drafted a one-pager. An idempotency-key middleware as a sibling library to `dv-api-common-libraries`. The shape:

Clients send `Idempotency-Key: <UUID>` header on POST/PUT. A servlet filter — same `@Order(LOWEST_PRECEDENCE)` pattern as the audit filter — checks Redis: if the key was seen in the last 24 hours, return the cached response with the original status code. If new, proceed and cache the response on the way out. TTL of 24h aligns with Stripe's default. Bounded Redis use — a few hundred bytes per key.

I sketched the trade-offs. Redis dependency for every consuming service (mitigated: we already have shared Redis). Race condition between "check Redis" and "cache response" handled with a Redis `SET NX` lease pattern. Failure mode: Redis down means we lose idempotency but the API still works — same trust model as the audit library.

I took it to my manager and to the platform team. Both saw the value. But the timing was wrong. The platform team was mid-way through the GTP BOM rollout — their plate was full. My team was about to start the Spring Boot 3 migration. Nobody could own a new shared library responsibly.

The proposal got parked. I wrote it up properly in our team's design doc folder and tagged it as "deferred — revisit Q3."

### Result

It hasn't shipped. Two services have since rolled their own per-endpoint idempotency — duplicated work the library would have prevented. I still think it was the right idea. I'm honest about why it didn't happen: I picked the wrong moment to propose a new shared library and didn't push hard enough to find an owner. If I had to do it again I'd write the first version myself as a 200-line spike before pitching — would have been easier to hand off than a design doc.

---

## Technical depth — if they probe

- **Servlet filter pattern**: same `OncePerRequestFilter` + `@Order(LOWEST_PRECEDENCE)` we used for audit. Reads `Idempotency-Key` header, hashes with the endpoint path, looks up Redis.
- **Redis SET NX lease**: `SET key:lease NX EX 60`. If the lease is held by another request, we wait briefly and re-read the cached response. Avoids two requests both treating each other as "new."
- **24h TTL**: matches Stripe. Long enough for retry storms (most retries are within minutes), short enough that Redis pressure is bounded.
- **Per-method scope**: only POST/PUT. GET/DELETE are already idempotent by HTTP semantics.
- **Response caching**: full HTTP envelope — status, headers, body — keyed on `<consumer_id>:<endpoint>:<idempotency_key>`. About 5-10KB per cached entry.

---

## Likely follow-ups

**Q: Why didn't you just build it anyway?**
> Two reasons. I already owned the audit library, and a second shared library without proper ownership becomes everyone's tech debt. And I didn't want to overrule the platform team during a BOM rollout — bad time politically. I underestimated how much "wait for the right moment" turned into "never."

**Q: How would you do it differently?**
> Ship a 200-line proof-of-concept first, show it working on one endpoint, then pitch. Design docs are easy to defer; running code is harder to ignore.

**Q: What's wrong with per-endpoint idempotency?**
> Each team rolls their own. Some use DB unique constraints, some use a hash on the body, some use the request ID. Different semantics, different failure modes. Suppliers calling four endpoints get four different idempotency contracts.

**Q: What about gRPC streaming or async writes?**
> Idempotency keys cover the synchronous POST/PUT case. For async (Kafka publish) we already have message-ID dedup at the consumer. This middleware fills the HTTP gap.

**Q: Would you propose it again now?**
> Yes — and I'd ship the spike first. My team's a few months past the SB3 migration, the platform team is between major BOM updates, and we now have a known cost of NOT having it (two duplicated implementations). The case is stronger.

---

## What NOT to say

- Don't blame the platform team or "leadership didn't care" — the timing call was on me.
- Don't oversell the idea — Stripe and a few open-source libs already have this. The novelty was applying our existing shared-library pattern.
- Don't pretend this would have stopped every duplicate — it covers retry storms, not all duplication categories.

---

## Backup story (if asked for another)

I sketched a platform-level supplier-data service inspired by the W6 BigQuery row-level security pattern. Instead of every supplier-facing API querying inventory directly, route all reads through a single service that enforces "this consumer can only see their own data" via BigQuery `@policy_tag` RLS. Would have replaced bespoke auth checks across four services. Reached prototype stage; got descoped when the team prioritised the SB3 migration.
