# Q: Tell me about a time when you transferred your responsibilities.

> **LP**: Unclassified (Hire and Develop the Best + Ownership)
> **Primary story**: W11 — Unified Onboarding / IAM (delegation arc with junior)
> **Backup story**: G7 — Handoff to incoming SE-II at GCC
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Walmart, mid-2025. I was the primary engineer on the Apollo Federation BFF for the unified onboarding / IAM work — the supplier-facing GraphQL layer that combined credential management with the audit and inventory subgraphs. The work was growing — there was talk of a credential-management subgraph being added, and I was the bottleneck for any new resolver.

A junior engineer joined our team — fresh from a different org, no Apollo Federation experience, no GraphQL background. The hiring manager wanted him on this work. The implicit ask was: make him the owner of the credential-management subgraph within a quarter.

### Task

My responsibility was to transfer ownership of a critical piece of the federation layer to someone who didn't yet have the context. Not "delegate a task" — actually hand over the responsibility, including the ability to make design decisions without checking with me.

### Action

I broke it into three phases.

**Phase 1 — Pair, don't dictate.** First two weeks, we paired daily — an hour each morning. He drove the keyboard. I narrated. We started with the existing onboarding subgraph — I walked him through the schema, the resolvers, the N+1 traps in Apollo Federation. The first resolver he wrote had a textbook N+1 — for each user, a separate DB call inside the field resolver. I caught myself about to just rewrite it. Instead I drew the schema on a whiteboard, asked him to trace the query plan, and let him find the N+1 himself. He shipped a `DataLoader` batching fix that afternoon. That was the moment the pattern clicked for him.

**Phase 2 — Lead with safety nets.** Weeks 3 and 4, I let him drive design for the credential-management subgraph. I stopped joining every standup. I set up two safety nets — a 30-min weekly design review where he walked me through his decisions, and a "ping me before merging anything that touches federation directives" rule. He hit some bumps — week 4 he nearly quit, frustrated by an Apollo gateway error that was actually a misconfigured `@key` directive. I coached him through it over coffee, didn't fix it for him.

**Phase 3 — Step back, sponsor up.** Weeks 5 and 6, I pulled out almost entirely. He owned the subgraph. I joined his PRs as a reviewer, not a co-author. I started telling our manager in 1:1s — "the credential-management subgraph is his now, route credit accordingly". When the promo cycle came around, I wrote the recommendation for his SDE-2 case.

### Result

The handover stuck. He owns the credential-management subgraph end-to-end. He's the on-call for it. He's reviewed PRs from other teams on federation work since. Three months after the handover, he found a federation directive bug that I would've missed — the schema-level fix made it into our internal Apollo guide.

The deeper thing — transferring responsibility isn't sending a Slack saying "you own this now". It's six weeks of resisting the urge to rewrite his code, plus the explicit sponsorship work upward. The first part teaches him. The second part makes the handover official with the people who matter for his career.

---

## Technical depth — if they probe

- **Apollo Federation N+1**: when a federated field resolver fetches per-entity data without batching, you get one DB call per parent entity. `DataLoader` batches them inside a single tick of the event loop. The junior's first resolver did `users.map(u => fetchCredsByUserId(u.id))` — classic N+1. The fix was `DataLoader<string, Cred>` keyed on user id with a batch resolver doing `WHERE user_id IN (?)`.
- **@key directive misconfig**: federated entities are joined across subgraphs on `@key` fields. He'd marked `email` as the key on credentials, but the upstream onboarding subgraph used `userId`. Gateway error was opaque — "cannot find type" — actual cause was a key mismatch. Five-line schema fix once you find it.
- **Why the whiteboard, not the IDE**: pulling a junior into the IDE risks them watching me type. Whiteboard forces them to articulate the design before code. Better learning, slower start, faster long-term.

---

## Likely follow-ups

**Q: What if he'd kept making N+1 mistakes?**
> Then we'd have paired longer. The timeline wasn't fixed at 6 weeks — that was my mental budget. If he'd needed 10, I'd have spent 10. The constraint was "real ownership", not "fast handover".

**Q: How did you handle him nearly quitting in week 4?**
> Coffee, not a 1:1. Out of the office. I asked what was actually frustrating him — turned out it wasn't the Apollo error, it was that he felt like he was making the team slower. I told him the truth — his ramp was on track, the error he was stuck on had stumped me too at his stage. The ramp from "I'm slow" to "I belong here" is the hardest curve in the first year of a new org. Naming it helped.

**Q: Why not just let him learn the N+1 the hard way in production?**
> Because federation N+1s scale badly — at our load, a 100-entity query becomes 100 DB calls, hits the connection pool, cascades. Letting him discover it in prod risks an incident. The whiteboard catch was learning without the blast radius.

**Q: Did your manager know you were spending an hour a day on this?**
> Yes — I told him upfront. His response was "do it, that's your job now". Mentoring a junior is leverage — one hour a day for six weeks gets me back 40 hours a week of his throughput forever.

**Q: Have you done this handover since?**
> Smaller version with the audit-logging library — a new team adopting it for the first time, I pair with one engineer on the integration PR. Different scale, same pattern: pair, safety nets, step back.

---

## What NOT to say

- Don't make yourself the hero. The junior did the work — you set the conditions for him to do it well.
- Don't claim the handover was clean — name the week-4 wobble. It makes the story believable.
- Don't say "I delegated" — delegation is a one-shot task assignment. Transfer of responsibility is six weeks of work.
- Don't skip the "sponsor up" part. That's the line most engineers miss in handover stories — telling the manager so the credit lands on the right person.

---

## Backup story (G7 — GCC handover to incoming SE-II)

When a SE-II joined the GCC backend team after I'd been the sole architect for 18 months, I had to hand over the architectural ownership of six services. Same pattern, longer timeline — pair walks through each service, a co-owned design doc for one project to set the model, then I stepped back as he started running design reviews. I made a point of sending the tech lead a Slack saying "X is owning Coffee now, route through him" so the sponsorship was explicit. When I left for Walmart three months later, the handoff was clean — no "ask Anshul" knowledge gaps.
