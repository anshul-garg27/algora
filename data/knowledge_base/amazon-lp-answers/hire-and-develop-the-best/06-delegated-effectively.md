# Q: Tell me about a time you delegated effectively.

> **LP**: Hire and Develop the Best
> **Primary story**: `W11 — delegated credential-mgmt subgraph after 6 weeks of pairing`
> **Backup story**: `G7 — delegated Beat operations to ops team`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Six weeks into pairing with the SDE-1 on the credential-mgmt subgraph. He was writing review-ready PRs, the p95 was clean, and he'd just run his own design review for the credential-rotation flow. I was still on the on-call rotation for his subgraph. Still reviewing every PR. He was doing the work; I was doing the safety net.

### Task

The handoff. Move ownership of the subgraph — code, on-call, and design authority — from me to him. The risk: hand off too fast and he'd break production. Hand off too slow and I'd block his growth and waste my own week.

### Action

I made a written list of what "ownership" meant. Not a vague handoff — a checklist. Five things:

One, on-call pager — Spring Boot 3.5.5 service, Apollo Federation subgraph, Postgres. Two, design authority on the credential-mgmt schema — adding tables, changing the principal-product junction. Three, deploy approval — Flagger canary on WCNP, his name on the rollout. Four, PR review for everyone else's changes to the subgraph. Five, the supplier-facing escalation path.

We agreed on the order. On-call first, easiest to roll back if it went wrong. Design authority last, because design mistakes are slow to surface.

Week one of handoff: he took the pager. I stayed on as secondary for the first two weeks. We got two real pages — one MeghaCache connection pool exhaustion, one ServiceNow change-window rejection. He took the first call both times. Diagnosed both. I jumped in only when he asked.

Week three: I dropped off secondary. PR reviews moved to him as primary, me as optional. By week six, "optional" meant I was reviewing maybe one in five PRs, and only because I was curious about the design.

The one thing I kept: the supplier-facing escalation path. Suppliers are external — Pepsi, Coca-Cola, Unilever — and they expect a senior engineer if something breaks. I told him I'd hand that one off in another quarter. He understood.

### Result

Within two months he was fully owning the subgraph. p95 stayed at ~180ms. He shipped two features I didn't touch. The team grew by two more SDE-1s and he ran their pairing himself.

The clean part of the handoff: I got my Tuesdays back. I'd been spending one full day a week on his work — PR review, pairing, escalation. After the handoff, that day went into a new project on transaction event history.

Honestly, the part I almost screwed up was the checklist. My first instinct was to just say "you own it now." Without the explicit list, we'd both have kept doing pieces in parallel.

---

## Technical depth — if they probe

- **Why on-call first**: On-call problems are concrete and time-bounded. You either fix it or escalate. Design authority is slower and harder to claw back if you hand it off wrong.
- **Why I kept supplier escalation**: External-customer-facing problems carry contract risk. Pepsi has an SLA. The handoff there needs more reps before the customer sees a new face.
- **The Flagger canary detail**: Putting his name on the rollout meant he owned the rollback decision. Real authority, not symbolic.

---

## Likely follow-ups

**Q: What was the hardest part of the handoff?**
> Letting him make a design choice I disagreed with. He chose to skip an index on the principal-product junction because he didn't think the read pattern needed it. I thought it did. I let him ship without it. Six weeks later he added the index when the query pattern shifted. He had to feel that — me telling him wouldn't have stuck.

**Q: How did you know he was ready?**
> Three signals. He was catching his own bugs in PR. He was running design reviews. And he'd started asking "what would break" questions instead of "is this right" questions.

**Q: Did anything go wrong?**
> One incident — he got paged at 2 AM on a MeghaCache connection-pool issue. He woke me up, which was the right call. We worked it together for 30 minutes, he wrote the postmortem alone. The postmortem was better than mine would have been.

**Q: What if the handoff hadn't worked?**
> The checklist was reversible. I could have taken on-call back, or design authority back, individually. Nothing was load-bearing on him being perfect — only on him being good enough.

---

## What NOT to say

- Don't say "I delegated everything" — say "I delegated in stages with a written list"
- Don't make it sound like I dropped the work on him — the six-week pairing came first
- Don't claim he had no growing pains — mention the missing index, the 2 AM page
- Don't say "I trusted him completely" — say "I gave him real authority and a real safety net"

---

## Backup story (if asked for another)

At GCC, after I built the Beat scraping engine, I delegated daily operations — rate-limit tuning, source-onboarding, schedule changes — to the ops team. I wrote a runbook with the four common failure modes, paired with the ops lead for two weeks, then dropped off. Within a month they were onboarding new sources without engineering involvement.
