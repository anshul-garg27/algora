# Q: Tell me about a time when you had to make a decision that was best for the team but initially met with resistance.

> **LP**: Have Backbone; Disagree and Commit (hybrid)
> **Primary story**: `W2 — Shared Library Adoption`
> **Backup story**: `W9 — Transaction Event History Cosmos → Postgres`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

When I started the audit logging work at Walmart, two other teams were already writing their own audit filters. I proposed pulling the common 80 percent into a shared Spring Boot starter so everyone could integrate with two lines of Maven config. The resistance was immediate.

### Task

Convince three teams — with three different latency budgets and three different feature lists — to adopt one library. Or watch three almost-identical implementations ship and diverge.

### Action

The first pushback came from Inventory Status. Their lead said his needs were different — they wanted response body logging on a strict allowlist of endpoints. My library defaulted to capturing both bodies.

I didn't argue. I asked him to send me his endpoint list. Then I built endpoint filtering as a CCM-driven regex and shipped response-body capture as a boolean flag. His "different needs" became two lines of YAML in his service.

Second pushback came from Transaction Events. Their concern was latency. They had a 200ms supplier SLA, and the engineer was worried any filter overhead would eat into it. I built a JMeter test against their staging endpoints with the library inline and showed P99 overhead under 5ms — `ContentCachingRequestWrapper` plus an `@Async` dispatch. He read the JMeter output, asked one clarifying question about the queue size, and signed off.

The third resistance was from my own manager. He wanted me to ship `cp-nrti-apis` first and "consider" the shared library later. I came back with the math — three teams times two weeks each times 40 hours equals 240 engineering hours saved this quarter, and a single schema in BigQuery for cross-service queries. He pushed me to keep my own deadline, so I cut trace correlation from v1 and put the saved time into the library.

I committed to two things: I'd review every adoption PR personally, and I'd hold Friday office hours for a month. Both happened.

### Result

Three teams onboarded in three weeks. Integration time per team dropped from two weeks to one day. Five teams use the library today, version 0.0.54. The Inventory Status lead and the Transaction Events engineer both ended up advocating for it inside their own teams. Resistance, then commit, then promotion.

---

## Technical depth — if they probe

- **Endpoint filter design**: Regex from CCM, evaluated once per service start, cached. Lookup is O(1) per request after the regex compile.
- **Response body capture**: Off by default. `ContentCachingResponseWrapper` is non-zero overhead — for high-throughput endpoints, leaving it off matters.
- **Latency overhead**: 5ms P99 measured on their endpoints. `ContentCachingRequestWrapper` is allocation, plus the `@Async` dispatch which is cheap.
- **Why a starter, not a library**: Auto-config. Teams add the Maven dep and a YAML block. No `@Import`, no `@Configuration` class to write.

---

## Likely follow-ups

**Q: What if a team had said no?**
> They could've. I designed for opt-in, not opt-out. If Inventory Status had stuck with custom, my library still shipped for the other two and `cp-nrti-apis`. The cost of one holdout was bounded.

**Q: How did you handle the disagreement with your manager?**
> Two conversations. First one, I made the case. He said no. Second one, I came back with the engineering-hours math and offered to cut v1 scope. He said yes. The honest move was offering the tradeoff up front rather than pretending the extra work was free.

**Q: Did the office hours actually work?**
> Yes. I caught a 100-thread executor in one PR that would've blown the heap, and a missing `spring-boot-starter-webflux` exclusion that would've broken Spring MVC. Eleven separate issues over the month, all caught before deploy.

**Q: Has any team left the library?**
> No, but one team forked it for an edge case — they needed Kinesis instead of Kafka. I merged the abstraction into upstream so the next team won't have to fork.

---

## What NOT to say

- "I convinced them" — they convinced themselves once the data was on the table.
- Don't make my manager sound obstructionist. He was reasonable — he just held the deadline.
- "It was easy" — it wasn't. The work was building trust per team.

---

## Backup story (if asked for another)

When we hit Cosmos cost issues with the transaction event history service, my proposal was a Cosmos-to-Postgres migration with dual-write. The team pushed back — Cosmos has no schema, Postgres does, the migration would be painful. I built a JSONB-based schema for the flexible fields and ran a two-week dual-write before cutover. Cost dropped, query latency improved, zero data loss. The team that pushed back hardest helped me write the migration playbook for other services.
