# Q: When your team encounters challenges, how do you motivate them and help come up with solutions?

> **LP**: Have Backbone; Disagree and Commit
> **Primary story**: `W11 — Unified Onboarding / IAM`
> **Backup story**: `W2 — Shared Library Adoption`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Mid 2025 at Walmart Data Ventures. We were building the unified onboarding and IAM platform — React micro-frontend, NestJS Apollo Federation BFF, two Spring Boot 3.5 services for auth policies and OAuth2 login. Suppliers like Pepsi were burning 3 to 5 days waiting for credentials through ServiceNow tickets. Our goal was sub-10-minute self-service.

Week four of the project, the team was stuck. We had three people. The junior was four weeks in and his first Apollo resolver had N+1 query patterns that made every page load take 3 seconds. He was frustrated to the point of telling me on a call that he was thinking about asking for a transfer. The mid-level was siloed on the OAuth2 login side and feeling like the work was disconnected from the rest. I had the BFF and the multi-tenant Hibernate filters and was running ahead but the team velocity was dropping.

### Task

I had to keep the team moving and not let the junior leave. That was a real risk that week.

### Action

I changed how we worked.

First, the junior. I stopped reviewing his code asynchronously and started pairing one hour a day. Not whiteboard lectures — I sat with him on the resolver and we drew the schema together. He had been treating GraphQL like REST with extra steps. We walked through DataLoader and batched resolvers on a single page. I resisted writing his code. He wrote it. I asked questions. By day three he had rewritten his resolver and the page dropped from 3s to 200ms. That was the moment I saw him come back online.

Second, the mid-level. The OAuth2 work was fine but isolated. I rewired our standups so every standup ended with a 5-minute architecture moment — one person walked through a piece of their work end-to-end. He kicked off the first one with the JWT + MeghaCache session flow. Two days later he was asking me how it connected to the BFF auth headers. He started owning the integration points instead of just his service.

Third, the work itself. I split the backlog into 2-day chunks instead of 1-week chunks. Every Friday we shipped something visible — a working credential rotation flow, a working multi-tenant filter, a working audit log. The wins compounded. The team started feeling like we were moving.

The hardest disagreement: my manager wanted me to take the junior off Apollo and put him on simpler CRUD work. He thought I was carrying the junior. I pushed back. I told him the junior was high potential and what looked like struggle was learning a new pattern. I asked for two more weeks. He gave me one. The junior shipped his second resolver clean inside that week. After six weeks of pairing, I delegated the entire credential-mgmt subgraph to him.

### Result

Platform shipped on schedule. Onboarding time went from 3-5 days to under 10 minutes — that is the bullet. The junior owns credential-mgmt now and I recommended him for SDE-2 promotion six months later. The mid-level became the OAuth2 + BFF integration owner. The team stayed together. What I learned — when the team is stuck, the answer is almost never more pressure. It is smaller wins, more pairing, and the right level of stretch for each person.

---

## Technical depth — if they probe

- **Apollo Federation BFF**: NestJS 10 + Apollo Federation 2 aggregating 10+ microservices. Resolvers use DataLoader for batch + cache. Per-request DataLoader prevents N+1 across resolver chains.
- **Junior's first fix**: Replaced per-row queries with `DataLoader<string, Credential>` batched by principal_id. Page render time 3s → 200ms.
- **Multi-tenancy**: Hibernate `@Filter("tenant_filter")` with ThreadLocal context. Every query auto-filters by tenant_id. Spring Boot 3.5 + Java 17 records.
- **The standup architecture moment**: Five minutes, no slides. One person walks through their piece end-to-end. Forces ownership, surfaces integration gaps.

---

## Likely follow-ups

**Q: How did you know the junior was high-potential and not over his head?**
> The first whiteboard session. I asked him to sketch how a credential rotation should flow. He drew the right boxes without prompting — he just did not know the GraphQL patterns yet. The instincts were there.

**Q: What did the 2-day chunk discipline change?**
> It gave the team something to ship by Friday every week. Morale follows shipping. Shipping follows scope size.

**Q: How did you handle the manager pushback?**
> I asked for one more week and committed that if the junior was not unblocked by Friday I would move him. The week worked. He stayed.

**Q: Did the mentoring slow your own delivery?**
> One hour a day for six weeks is 30 hours. Way cheaper than rehiring. And the BFF work he eventually took off my plate gave back a lot more time.

---

## What NOT to say

- Do not say "I motivated them with a speech." Speeches do not move stuck teams. Pairing, scope, and small wins do.
- Do not skip the disagreement with the manager. That is the backbone moment.
- Do not take credit for the junior's growth. Credit him.

---

## Backup story (if asked for another)

W2 — Shared library adoption. Twelve services across 8 teams resisted adopting the audit common library because integration meant touching every service. I made it a one-line Maven dependency plus 10-15 lines of CCM config, wrote a runbook, did the first three integrations myself, and got the team a visible win. 12 services in 8 weeks.
