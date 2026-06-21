# Q: Tell me about a time you had to manage up.

> **LP**: Intro & Closers
> **Primary story**: W4 — Multi-Region Active/Active rollout (vague exec ask)
> **Backup story**: W5 — Spring Boot 3 .block() decision defended to lead
> **Time budget**: 75–90 seconds spoken

---

## STAR — how to actually tell it

### Situation

Early 2025. Leadership came back from a compliance review saying our audit-logging system had to be "resilient". That was the whole brief. No RTO. No RPO. No budget number. My skip-level wanted it done "soon".

### Task

I owned the audit platform. I had to translate "make it resilient" into a real spec, get sign-off, and ship it — without bouncing the ask back as "give me requirements" and looking like I couldn't operate without hand-holding.

### Action

I didn't push back in the meeting. I went away for two days and did the homework first.

I wrote a one-page doc — three options. Active-Passive with ~30-minute failover, Active-Active with immediate failover, and a hybrid. For each one I put down a rough cost, a rough timeline, and the risk profile. Then I drafted what I thought the right RTO/RPO numbers were for an audit-log workload — 1-hour RTO, 4-hour RPO — and marked them as **assumptions**, not facts.

Then I booked a 30-minute slot with my lead, walked through the doc, and asked one question: "If these assumptions are wrong, tell me where." That flipped the conversation. Instead of him giving me a vague target, he was now reacting to specifics. He pushed back on the RPO — said compliance actually needs 4 hours max gap — confirmed. Pushed the RTO down to 30 minutes if we could afford it. We landed on Active-Active.

I sent a 4-line summary to my skip-level after — "here's what we decided, here's the timeline, here's what I need from you" — so he didn't have to chase. He approved in two hours.

Then I executed. Phased rollout, Week 1 publisher in second region, Week 2 GCS sink, Week 3 data parity check, Week 4 routing + failover drill. Geography-based routing on the `wm-site-id` header. I intentionally failed over a region in week 5 — 15-minute recovery, well inside the 1-hour budget.

### Result

Active-Active live in five weeks. Zero downtime, zero data loss. The skip-level later told me it was the cleanest scoping he'd seen on a "make it resilient" ask. The pattern — assumption-doc + 30-min sync — I've used three times since.

The reflection I took from it: when leadership gives you a vague ask, "I need more requirements" is the wrong reply. The right move is to make the spec yourself, mark the guesses, and let them correct you. They're usually faster at correction than at specification.

---

## Technical depth — if they probe

- **Why Active-Active over Active-Passive**: audit logging is write-heavy. Passive means 30+ min cold-start of consumers and a real chance of data gap. Active-Active doubles infra cost but failover is instant.
- **Geography-based routing**: every Walmart audit event has a `wm-site-id` header — US, CA, MX. Routing on that header keeps cross-region traffic minimal and makes the failover blast-radius obvious. Round-robin would've been cheaper to implement but harder to reason about during an incident.
- **The 4-line summary to the skip-level**: this is the actual lever. Skip-levels don't read 1-pagers. They read 4 lines and trust your judgment. Writing the 1-pager is for you and your lead, not for the exec.

---

## Likely follow-ups

**Q: What if your lead had disagreed with all three options?**
> I would've added option four right there in the meeting — that's the point of the doc. The options were a starting point for the conversation, not a contract. Disagreement was the goal.

**Q: How long did the doc take?**
> About four hours over two days. The cost numbers I pulled from the platform team's Kafka quota sheet. The RTO/RPO numbers I cross-checked against our compliance team's old incident reports.

**Q: Was your manager surprised you pushed back?**
> He wasn't surprised — he expected the doc, he just didn't say so explicitly. That's part of the read — senior managers often assume you'll convert "make it resilient" into a spec yourself. They don't say so because they don't realise junior engineers don't know that.

**Q: When have you done this since?**
> Most recently on the supplier self-service work — exec said "give Pepsi access to their data". I wrote up the BigQuery row-level-security pattern, marked the data-retention assumption, sent it up. Same shape, same outcome.

---

## What NOT to say

- Don't frame managing up as "managing my manager's emotions" — that's not what they're asking.
- Don't say "I told my manager he was wrong" — managing up isn't disagreement, it's filling the spec gap.
- Don't make the manager sound incompetent. "Vague ask" is normal at scale — name it without judgment.
- Don't skip the 4-line summary detail — that's the most concrete "managed up" move in the story and it's the one most engineers don't do.

---

## Backup story (W5 — .block() defended in design review)

When I pitched the Spring Boot 3 migration plan, a colleague wanted to go fully reactive — rewrite the whole codebase to non-blocking. I disagreed but didn't argue in the meeting. I went away, ran rough numbers — 3 months reactive vs 4 weeks `.block()` — listed the risks, scheduled a 1:1 with the lead. Walked him through scope vs benefit, proposed reactive as a follow-up Q3 project. He agreed. Shipped in 4 weeks, zero customer impact. Same shape as the W4 story — assume the spec, present the data, let the leader correct or confirm.
