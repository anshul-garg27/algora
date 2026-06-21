# Q: Tell me about a time when you saw a peer struggling and how you helped them.

> **LP**: Hire and Develop the Best (hybrid)
> **Primary story**: `W11 — Unified Onboarding / IAM`
> **Backup story**: `W2 — Shared Library Adoption`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

About four months into the Unified Onboarding work at Walmart, a junior engineer joined our team. He came in on the Identity Auth Policies service, which uses Apollo Federation, Spring Boot 3.5, and a multi-tenant Postgres schema. He'd never worked with GraphQL Federation before.

### Task

Get him productive on something real, not just code-reading, without writing his code for him.

### Action

His first ticket was the `credentials` field on the `Principal` type — a subgraph resolver that pulls a supplier's credentials with their products and roles. He took the first cut on his own. The PR worked, but the resolver fired one database query per credential and one more per product. Classic N+1.

I sat with him on a Tuesday afternoon. Resisted the urge to just write the fix. Instead, I drew the request flow on a whiteboard — GraphQL request, parent resolver, child resolver, database call per credential. Then I asked him what he thought would happen with a principal that has 50 credentials. He worked it out — 50 plus 50 round-trips. That was the moment.

We talked about DataLoader. Batches all child resolves into one DB call. I sketched the pattern in pseudocode. He went away to implement it. Came back two days later with a working `DataLoader<Long, List<Credential>>` keyed by `principalId`. Reduced the queries from N+1 to two total.

Over the next six weeks, I did about an hour a day with him — pair on his first design, code review with explanations not just approvals, walk through one production incident together so he could see how we debug. After week four he hit a wall — he was frustrated, said he felt slow, almost asked for a transfer. I shared my own first-job story. He laughed and stuck around.

By week six, I delegated the entire credential-management subgraph to him. He owned the design review and the rollout.

### Result

His subgraph shipped in week seven. Onboarding for a new supplier dropped from "3-5 days manual ticket" to under 10 minutes self-service. I recommended him for SDE-2 at the next cycle. The bigger thing — I had to keep reminding myself not to grab the keyboard. Helping someone learn means sitting with their slower path.

---

## Technical depth — if they probe

- **Why DataLoader, not a JPA fetch-join**: Federation resolves children across subgraphs, so a JPA join doesn't help. DataLoader batches the resolve at the GraphQL layer — works across any data source.
- **The N+1 he had**: `principal.credentials` resolver called `credentialRepo.findById(id)` per credential. For a 50-credential principal, 51 round trips.
- **DataLoader signature**: `DataLoader<Long, List<Credential>>` keyed by `principalId`, batch function does one `findByPrincipalIdIn(ids)` query.
- **Multi-tenancy gotcha**: His first DataLoader version forgot to apply the tenant filter. We caught it in code review — a row from tenant A leaking into tenant B's resolve. Fixed with a `ThreadLocal<TenantContext>` propagation through the batch function.

---

## Likely follow-ups

**Q: How did you know not to just write it for him?**
> Honest answer — I tried to grab the keyboard once and stopped myself. The point of the pairing wasn't to ship the fix faster; it was to teach him what to look for. If I'd written it, he'd never have caught the next N+1.

**Q: What did you do when he wanted to quit?**
> Listened, mostly. I told him about a 3 AM bug I caused in my first job when I dropped a Postgres index by mistake. He felt less alone. We re-scoped his ticket so he could ship a smaller win that week and rebuild momentum.

**Q: How is he doing now?**
> Owns two subgraphs and reviews my PRs sometimes. Got promoted to SDE-2 in his first cycle. He still pings me when he hits a federation edge case, and that's the relationship I wanted.

**Q: What would you do differently?**
> I'd have introduced DataLoader on day one as a team standard, not on his first PR as a fix. Pattern-first teaching is faster than bug-first teaching.

---

## What NOT to say

- "I taught him" — frame it as pairing. He did the work.
- Don't share his name. "Junior engineer" is enough.
- Avoid "I saved him" — he wasn't drowning, he was struggling. Different word.

---

## Backup story (if asked for another)

When three teams were building near-identical audit filters at Walmart, two of them had engineers stuck on the same body-stream-consumed bug. I didn't take over their tickets; I held Friday office hours, reviewed every adoption PR myself, and caught a 100-thread executor config that would've blown the heap. Eleven separate issues caught over a month, all before deploy. The shared library hit version 0.0.54 across five teams.
