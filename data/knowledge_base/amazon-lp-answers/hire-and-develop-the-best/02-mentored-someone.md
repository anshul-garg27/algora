# Q: Tell me about a time you mentored someone.

> **LP**: Hire and Develop the Best
> **Primary story**: `W11 — IAM mentoring arc (1 hr/day for 6 weeks)`
> **Backup story**: `W2 — Shared Library Adoption (mentoring across 12 teams)`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Summer of 2024, an SDE-1 joined our team. Non-CS background — mechanical engineering degree, learned to code at a bootcamp, six months of Node.js experience. We were mid-build on the unified onboarding platform: Apollo Federation BFF, two Spring Boot 3.5.5 services, Postgres with `ext_identity_auth_policies` schema, multi-tenant via Hibernate filters and ThreadLocal context. A lot of moving parts for someone whose first real job this was.

### Task

His tech lead asked me to take him on. The ask: get him owning the credential-mgmt subgraph in two months. Specifically, the GraphQL resolvers, the DataSharing API integration, and the principal-product junction logic.

### Action

I blocked 10 to 11 AM every weekday, six weeks straight. Not a recurring meeting on his calendar — actual time on mine.

Week one we didn't write any code. I had him draw the request flow on paper. Supplier clicks "Create Credential" — what happens? He missed the ServiceNow ticket step. We walked through it together. By Friday he could draw the full flow including ThreadLocal tenant context propagation.

Week two and three, I gave him the simplest resolver — list credentials by principal. He wrote it. It worked. Then we made it harder: add cursor pagination. He hit the same bug everyone hits, single-field cursor on `created_at` with duplicate timestamps. I didn't tell him. I asked, "what happens if two credentials get created in the same millisecond?" He went and reproduced it himself. Then he wrote the composite cursor — `(created_at, id)` tiebreaker. That fix is still in production.

Week four he hit a wall. Apollo Federation entity references, `@key` directives, why his `__resolveReference` wasn't getting called. He was frustrated. I told him: take the afternoon, read the Federation spec section on entities, come back tomorrow. He came back with the right mental model.

Week five he wrote the credential-rotation flow himself, including the compensating transaction for ServiceNow ticket cleanup. Week six he ran the design review for it. I sat in the back and said almost nothing.

### Result

He owns the subgraph now. His p95 on resolver latency is 180ms. He's already mentored the next SDE-1 who joined. His promotion case for SDE-2 went up four months ahead of cohort. I'd say the real win is that the team picked up his "ask a question before answering" review style — that spread.

---

## Technical depth — if they probe

- **Why pairing not just code review**: PR comments teach the fix. Pairing teaches the way you think. He needed the second one.
- **Why I didn't skip GraphQL fundamentals**: Apollo Federation has sharp edges — entity resolution, reference resolvers, schema stitching. If you don't get the model, you cargo-cult and break things at scale.
- **The composite cursor moment**: That was the turning point. He found a real production bug on his own. After that he stopped waiting for permission.
- **Books I gave him**: Designing Data-Intensive Applications, just the chapters on consistency and indexes. Not the whole thing — overload kills momentum.

---

## Likely follow-ups

**Q: Did pairing one hour a day actually cost you that much?**
> The first two weeks, yes. After that, no — his PRs needed less review and I had a real second pair of hands on the subgraph.

**Q: What if he hadn't been a quick learner?**
> Same routine, longer arc. The structure works regardless of speed. What you don't do is rescue them — they have to write the code themselves.

**Q: How did you measure progress?**
> Three things: time-to-merge on his PRs, number of review rounds, and whether he started catching his own bugs before I pointed them out. All three trended right by week three.

**Q: Did you give him hard feedback?**
> Yes. Week three I told him his commit messages were one-liners and that wouldn't scale. He pushed back, said it didn't matter for a small PR. I showed him a git blame from six months ago where I couldn't tell what a one-liner change did. He took it.

---

## What NOT to say

- Don't say "I taught him everything" — frame it as "he did the work, I cleared the path"
- Don't overstate the hours — one hour a day is what I actually spent
- Don't claim credit for his promotion — say "his promotion case went up early"
- Don't make him sound junior in tone — he's a peer now, talk about him that way

---

## Backup story (if asked for another)

For the shared audit-logging library, twelve teams needed to adopt it. I ran Friday office hours for a quarter — show your screen, bring your error. One team had `isAuditLogEnabled=false` because of a typo in CCM. We fixed it together in five minutes. Eleven similar issues got caught in those office hours instead of becoming support tickets.
