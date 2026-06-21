# Q: Describe a situation where you prioritized competing tasks and still delivered successful results.

> **LP**: Deliver Results
> **Primary story**: `W4 — Multi-Region Rollout`
> **Backup story**: `G7 — Sole Architect`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Mid-2025. I had three things on my plate at the same time. The multi-region active/active rollout for the Kafka audit pipeline — that was leadership's "make it resilient" ask with no defined RTO or RPO. The Spring Boot 3 post-migration fix waves were still landing — heap OOMs in PR #1528, correlation-ID propagation in PR #1527, then WebClient timeout/retry in PR #1564. And cp-nrti-apis had a P0 supplier-facing incident every other week from the Hibernate enum tail.

All three had leadership eyes on them. All three had different deadlines. My manager asked me to pick.

### Task

Decide what gets my time this week, what gets a backlog item, and what I delegate. Without dropping any of the three.

### Action

I sat down on a Sunday evening and wrote each task on a card with three things — blast radius if it slips, who else can do it, and the next concrete action it needs from me.

The multi-region work had the biggest blast radius. Zero data loss on audit data is a regulatory requirement. Nobody else on the team had the Kafka multi-region context. The next action was a 1-pager to leadership defining RTO under 30 seconds and RPO at zero, because they had not given me numbers. I had to do this one myself.

The Spring Boot fix waves were medium blast radius. Each PR was small, the patterns were documented in my runbook, and a teammate had paired with me on the original migration. The next action on each was a code-review pass, not a rewrite. I could delegate the implementation and review the PRs.

The cp-nrti-apis P0s were urgent but bounded. Each one was a runbook problem — a known Hibernate enum issue that needed a `@JdbcTypeCode` annotation. I trained the on-call to grep the stack trace for the column type mismatch and add the annotation. That class of P0 came off my list inside a week.

I went to my manager Monday morning with this plan. Active/active stays with me. SB3 fix waves go to my teammate with me on review. P0 tail goes to on-call with a runbook. He signed off.

For the multi-region work, I phased it across four weeks. Week 1, define requirements and write the assumptions doc. Week 2, dual-write to two Kafka clusters in stage. Week 3, deploy GCS sinks in the second region. Week 4, route both regions and run a deliberate failover test. I shared the weekly target with leadership every Friday — short bullets, no slides.

### Result

Multi-region active/active shipped in four weeks. Failover at 25 seconds in production, zero data loss across three actual failovers in the first six months. SB3 fix waves landed clean — my teammate became the SB3 SME on the team. cp-nrti-apis P0 rate dropped to roughly zero because on-call could resolve the enum class without paging me. The lesson — when three things compete, the cost is not doing all three at 80%. It is picking the one with the biggest blast radius and giving the others a clean handoff with a runbook. The 1-pager and the weekly Friday note were the cheap mechanisms that kept leadership off my back.

---

## Technical depth — if they probe

- **Multi-region active/active**: Two Kafka clusters (EUS2, SCUS), replication factor 3, 12 partitions each. Dual-write from publisher, geography-based routing on `wm-site-id`. Failover 25s in production.
- **Hibernate enum runbook**: `column is of type X but expression is of type character varying` → add `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` on the field. One-line fix, repeatable.
- **The 1-pager for leadership**: RTO < 30s, RPO = 0, budget $3,200/month, alternatives priced (Active/Passive $2K/month, no-DR $1.2K/month). Turned vague ask into an approved spec.
- **Friday status note**: 5 bullets max — what shipped, what's next, blockers, risk, ask. Replaced three different ad-hoc status requests.

---

## Likely follow-ups

**Q: How did you pick the dimension you would own yourself?**
> Blast radius and uniqueness of context. Multi-region had the biggest blast and the smallest pool of people who could do it. Easy decision once I wrote it down.

**Q: What did the runbook give the on-call?**
> Stack-trace pattern → exact annotation to add → which file → which test to run. Three-step recipe for the most common P0 class.

**Q: What if leadership had pushed back?**
> Then I would have asked for one of the three to move out of the quarter. You cannot do three high-blast items at full quality with one person.

**Q: How did your teammate take over the SB3 waves?**
> Two-day pairing on the first PR, code review on the next three, then full ownership. By the fourth PR I was just reading the diff.

---

## What NOT to say

- Do not say "I worked nights to do all three." That is a sign of failed prioritization, not success.
- Do not skip the runbook handoff. That is what kept the lower-priority work moving without me.
- Do not pretend the prioritization was easy. It was a Sunday evening with three cards.

---

## Backup story (if asked for another)

G7 — Sole architect on 6 services at GCC. Beat, Coffee, SaaS Gateway, Stir, Event-gRPC, Fake-Follower Lambda. I prioritized by which service unblocked the SaaS app — Coffee + Gateway first, then Beat for data, then Stir for analytics, then Event-gRPC as the optimization, then the Lambda. Shipped all 6 in 15 months.
