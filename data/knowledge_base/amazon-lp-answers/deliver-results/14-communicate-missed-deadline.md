# Q: Tell me about how you will communicate if you think you will miss a deadline.

> **LP**: Deliver Results
> **Primary story**: `W5 — Spring Boot 3 Migration`
> **Backup story**: `W4 — Multi-Region Rollout`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Spring Boot 2.7 to 3.2 migration on cp-nrti-apis, April 2025. I had told my manager I would have the main migration PR up in two weeks — that is what I committed in our planning meeting. End of week one I knew I was going to miss it by about a week. 158 files, 1,732 lines added, and the WebClient test-mock refactor was eating more time than I had budgeted. The audit deadline three months out was firm. The two-week PR date was not, but it was my commitment.

### Task

Tell my manager the same day I knew. Give him a useful update — not just "I'm behind." Show what changed, what the new date is, what mitigation looks like.

### Action

I did three things in order.

First, the message itself. I sent my manager a Slack message that same evening before I left the office. Three short paragraphs. Paragraph one — I'm a week behind on PR #1312. Paragraph two — here is what changed: WebClient test-mock refactor across 42 test files is roughly double the time I estimated, plus a Hibernate 6 enum edge case I want stage time to validate. Paragraph three — new date is end of next week (April 21), production canary still feasible by April 30, audit deadline still safe. I did not ask for permission. I gave him the new date with the reasoning.

Second, a daily progress doc. I built a one-page Confluence doc the next morning. Three numbers — files migrated (out of 158), tests passing (out of 487), lines remaining. Updated every evening. Anyone on the team could read it without asking me. The daily cadence took five minutes per day.

Third, a scope cut decision that protected the bigger commitment. A colleague had been pushing for full reactive WebClient — three-month rewrite. I picked `.block()` instead — sync behaviour, framework upgrade only, four-week scope. I wrote up the tradeoff and walked my tech lead through it 1:1 before the next design review. That single call cut three months out of the plan and is the reason the audit deadline survived.

What I deliberately did not do. I did not wait for the next standup to surface the slip. I did not bury it in a status report. I did not give a vague "still working on it" update. The communication has to be specific or it is not communication.

### Result

PR #1312 merged April 21 — one week late on my personal commitment, on track for the audit. Production release April 30 via Flagger canary, 10% → 25% → 50% → 100% over 24 hours, zero customer-impacting issues. The audit passed. My manager later told me in our 1:1 that the same-day Slack and the daily doc were the reason he could defend the new date to his director without needing to come back to me for context. The framework I keep — when you think you will miss a date, you have three jobs. Tell the right person the same day. Give them a new date with reasoning, not a vague extension. Give them a daily artifact so they do not have to ask.

---

## Technical depth — if they probe

- **The WebClient mock gap**: Each chained call (`get().uri().headers().retrieve().bodyToMono()`) needs its own mock. 42 test files. Roughly doubled test code complexity. The single biggest delta from my original estimate.
- **The `.block()` decision**: Sync behaviour with WebClient's API. Not an anti-pattern on non-reactive threads. Saved three months of architecture change.
- **Hibernate 6 enum catch**: Stage week caught `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` requirement on Postgres enum columns. Production-breaking bug avoided.
- **Flagger config**: `threshold: 5`, `maxWeight: 50`, `stepWeight: 10`, `interval: 1m`. Auto-rollback at 1% error rate or P99 over 500ms.

---

## Likely follow-ups

**Q: Why Slack and not in person or email?**
> Slack is timestamped, searchable, and forwardable to his director without me having to retell the story. The 1:1 channel preserved tone.

**Q: What was in the daily doc?**
> Three numbers — files migrated, tests passing, lines remaining. Two sentences on the day's blocker if any. Five minutes to update.

**Q: When would you use email instead?**
> When the original commitment was on an email thread with leadership. I used email for the multi-region slip because the director had committed the date by email — the slip note had to live on the same thread.

**Q: What if your manager pushes back on the new date?**
> Then we have a scope conversation, not a date conversation. The new date reflects the work. If the date has to hold, something has to come out of scope.

---

## What NOT to say

- Do not say "I keep my manager updated" — too vague. Be specific about the mechanism (Slack same-day, daily doc).
- Do not pretend you wait for standups. Standups are too slow for slip communication.
- Do not skip the scope-cut beat. The communication and the scope decision are two halves of the same job.

---

## Backup story (if asked for another)

W4 — Multi-region active/active. A 4-week date had been committed by a director before I scoped it. I came back at week 2 and committed to 5 weeks instead, with an assumptions doc that turned vague requirements into RTO < 30s and RPO = 0. The slip note went on email to match the original commitment thread. Shipped end of week 5.
