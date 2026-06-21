# Q: Tell me about a time you had a conflict with your manager or senior.

> **LP**: Have Backbone; Disagree and Commit
> **Primary story**: `W3 — DiscardPolicy Feedback`
> **Backup story**: `W9 — Cosmos → Postgres Migration`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

It was a Thursday afternoon when the comment landed. I had just finished the audit common library — dv-api-common-libraries, 696 lines, going into 12 services. My PR was approved by my own team. A senior engineer from the platform org, two levels above me, dropped a public comment: my thread pool was wrong. He called out the queue size of 100 as arbitrary, and `DiscardPolicy` as a silent-loss bug waiting to happen. He was not on my team but he had a strong reputation across the org.

### Task

I had to figure out — defend it, or do the work to actually know if he was right. And do it without burning the relationship with someone whose opinion would shape adoption.

### Action

First reaction was bruised ego. I had thought about that queue size. I had run the math — each audit payload is 2KB, queue of 100 is 200KB, plenty of headroom. I started drafting a reply.

I made myself stop. Stepped away from the laptop and went for coffee. While walking, I let the word "silent" sit in my head. He was not arguing memory. He was arguing visibility. `DiscardPolicy` drops tasks with no exception. Our async wrapper catches all exceptions. So if the queue ever filled, we would lose audit events with no log, no metric, no signal. For a compliance pipeline that feeds BigQuery and downstream regulatory reporting, that is not a small thing.

He was right.

Next morning I replied on the PR. Did not pretend I had considered it. Thanked him for the catch. Then I made three changes. Swapped `DiscardPolicy` for `CallerRunsPolicy` — calling thread runs the task under saturation, which gives natural backpressure to the request that triggered it. Added a Prometheus counter `audit_pool_rejected_total` so nothing would ever be invisible. Added a WARN log at 80% queue depth as an early warning.

Then I asked him for 15 minutes on a call. Not on the PR thread. In the call I walked him through the new design, asked if I had missed anything. He had one more catch — I had not added the metric to the team SLA dashboard. Fixed that too.

### Result

Library shipped with the new policy. Four months in, during a downstream slowdown, the queue-depth warning triggered on cp-nrti-apis. We caught it before any audit got lost and scaled the pool from 10 to 20 threads in 10 minutes. Twelve services integrated the library — eight teams. He became one of its loudest internal advocates and brought two more teams to me. The harder lesson was that defending a design publicly before you have sat with the feedback is a great way to lose trust. The 1:1 call after the fix did more for the working relationship than the fix itself.

---

## Technical depth — if they probe

- **CallerRunsPolicy reasoning**: Under queue saturation, the producing thread (the request thread) runs the task itself. Adds 10-50ms to that request but eliminates silent drops. The request slows, the producer slows, the queue drains. Self-regulating.
- **Why DiscardPolicy was wrong here**: Compliance data. Silent loss is the worst failure mode. Audit logs feed downstream regulatory pipelines. We have to be able to prove what was logged.
- **Instrumentation**: `audit_pool_rejected_total` (counter), `audit_pool_queue_depth` (gauge), WARN log at 80% capacity. Dashboard panel on team SLA board.
- **Why the 1:1 over the PR thread**: PR threads are public and short. A call lets the other person see you changed your mind, ask follow-ups, and re-engage as a collaborator.

---

## Likely follow-ups

**Q: How long did the defensive feeling last?**
> Maybe an evening. The walk helped. By the next morning I had read his comment three times and the silent-loss point had landed.

**Q: How did you keep the relationship intact?**
> Three moves. Thanked him on the PR without ego. Pinged him for a 15-min call. Asked him to review my next two PRs before anyone else. That last one was the real signal — I trust your eye.

**Q: What if he had been wrong?**
> I would still have added the rejection metric and the queue-depth log. Visibility is cheap and independently valuable. Then I would have written up the math in the reply.

**Q: Did it slow you down?**
> The change was about a day of work — swap the policy, add the metric, add the log, update tests, update the dashboard. Cheap insurance.

---

## What NOT to say

- Do not say "we had a clash" or "it got tense." It was a code review disagreement.
- Do not skip the initial defensiveness. Interviewers want to see honesty about the reaction.
- Do not say he was wrong. He saved the library.

---

## Backup story (if asked for another)

W9 — Cosmos → Postgres. Two senior engineers on my own team pushed back on migrating the Transaction Event History API off Cosmos. I asked for a week, built a cost-trend doc, walked my manager through it 1:1 before the team meeting, and got the green light. Migration shipped in May with zero supplier impact and Postgres became the foundation for the Canada launch a month later.
