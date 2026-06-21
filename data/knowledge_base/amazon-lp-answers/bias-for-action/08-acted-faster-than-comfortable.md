# Q: Describe a time you acted faster than was comfortable.

> **LP**: Bias for Action
> **Primary story**: `W6 — Paused migration mid-sprint to ship BigQuery RLS`
> **Backup story**: `W3 — Overnight reversal on DiscardPolicy feedback`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

I was halfway through the Spring Boot 3 migration sprint when our customer success lead pinged me. Pepsi had been chasing us for two days asking "why did our last 50 IAC requests fail?" The pattern was old and tired — supplier emails support, support tickets us, I or someone else greps the audit logs, screenshots the rows, sends them back. Two days of debug cycle. Pepsi was a top-3 supplier and the customer success lead was about to escalate.

### Task

Stop the bleeding. The migration could wait one sprint; a two-day debug loop on a top supplier could not.

### Action

I'll be honest — pausing a high-visibility migration mid-sprint felt wrong. The PR was open, the team was watching. But the math wasn't complicated: if I shipped a self-serve path for suppliers, this class of ticket went to zero. I told my lead in a 5-minute Slack thread — "pausing SB3 work, two-day spike on supplier self-serve, I'll resume Monday." He said go.

The audit data was already in GCS as Parquet — that was the kafka-audit pipeline I'd built earlier. The piece missing was supplier access. I set up BigQuery external tables pointing at the existing GCS buckets — no data movement, no new ETL. Added `@policy_tag` columns on `consumer_id` so each row was tagged with the owning supplier.

Then row-level security. I wrote a BigQuery RLS policy: `filter using (consumer_id = SESSION_USER_CONSUMER_ID())`. Each supplier sees only their rows. Tested with two test consumer IDs. Wrote one sample query — "show me my last 7 days of failures" — and documented it.

The uncomfortable part was that I bypassed our normal week-long internal review for new supplier-facing surface. I shipped to one supplier on a Thursday afternoon. Watched their session for two hours — they ran six queries, all clean, no leakage to other consumers in the result set.

Monday morning, after watching one supplier's weekend usage, I rolled out to two more.

### Result

Pepsi self-served their first debug query in about 30 seconds — replacing the 2-day support cycle. Within a month, three suppliers were self-serving and the support queue dropped noticeably. The Spring Boot 3 migration resumed the following Monday and shipped on its original date. The spike cost me a sprint week; the math said the supplier hours saved would cover that in less than a month.

What was uncomfortable wasn't the work — it was choosing to make my own roadmap call mid-sprint with one Slack thread of cover. I'd do it again the same way.

---

## Technical depth — if they probe

- **No new infra**: BigQuery external tables on existing GCS Parquet. The audit pipeline was already feeding GCS — RLS was the missing piece.
- **`@policy_tag` on consumer_id**: Column-level access tags. Combined with row-level security policy that filters on the requesting user's consumer mapping.
- **Why GCS + BigQuery, not a custom UI**: A SQL surface was cheap. A UI would have been a 2-month project.
- **Audit trail**: BigQuery query history captures who-ran-what. Compliance got that for free.
- **One-week internal review skipped**: Not a great practice — but the scope was bounded (read-only, one supplier, behind an RLS policy I could yank). I wrote the review doc retroactively.

---

## Likely follow-ups

**Q: Why pause a high-visibility migration?**
> The migration had a 3-month deadline. The supplier debug loop was a daily pain point on a top customer. Cost-of-delay said pause.

**Q: Was the RLS policy actually safe?**
> Tested with two consumer IDs simultaneously. No leakage. BigQuery enforces the policy at the storage layer — not application-level. Compliance verified after launch.

**Q: What was the team's reaction?**
> My lead was supportive in the Slack thread. The skip-level asked why I hadn't escalated to her — fair point, I should have looped her in.

**Q: Could you have done this without skipping review?**
> Yes, but it would have added a week. The trade was that week against another week of Pepsi's debug pain. I made the call; in hindsight I'd have looped the skip-level in 24 hours, not Monday.

**Q: What would you do differently?**
> Loop the skip-level on day 1. The shortcut on review was defensible; the lack of an early heads-up wasn't.

---

## What NOT to say

- Don't pretend pausing a migration was an obvious call — it wasn't.
- Don't skip the discomfort — interviewers want to hear the friction.
- Don't oversell the RLS — it was a known BigQuery feature, not an invention.

---

## Backup story (if asked for another)

After our DiscardPolicy queue change went live in the audit pipeline, my lead flagged in a review that we had no instrumentation — we'd be silently dropping events. I'd been confident in the change. Overnight I added queue-depth metrics and Discard-count counters, then re-shipped within 24 hours. Two days later the metrics caught a real drop spike during a Kafka rebalance. The discomfort was admitting I'd shipped half-blind; the speed of reversal made it OK.
