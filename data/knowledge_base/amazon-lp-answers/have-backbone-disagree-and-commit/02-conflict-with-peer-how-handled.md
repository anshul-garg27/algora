# Q: Tell me a time when you have conflict with your peer and how did you handle this.

> **LP**: Have Backbone; Disagree and Commit
> **Primary story**: `W3 — DiscardPolicy Feedback`
> **Backup story**: `G8 — Tech Stack Defence`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Early 2025, code review for the dv-api-common-libraries audit module. I had picked `DiscardPolicy` as the rejection handler on the thread pool — 6 core threads, 10 max, queue of 100. A senior engineer on the platform team dropped a public comment on my PR. He said the queue size was arbitrary and `DiscardPolicy` would silently lose audit events under load. His tone was sharp. The PR was already approved by my own team.

### Task

I had two routes. Defend it on the thread and ship. Or actually sit with his point and see if he was right.

### Action

My first reflex was defensive. I had thought about this — every audit payload is about 2KB, queue of 100 is 200KB, that is not a memory issue. I started drafting a reply explaining the math.

Then I stopped. I closed the laptop and went for a walk. The part that nagged me was the word "silent." Even if memory was fine, what happens when the queue overflows? `DiscardPolicy` drops the task with no exception, no log. We catch all exceptions inside the async wrapper. So if the queue ever filled, audit events would just vanish. We are a compliance system. Silent loss is the worst failure mode.

He was right.

Next morning I replied on the PR. Thanked him for the catch, did not pretend I had thought of it. Then I made three changes. First, swapped `DiscardPolicy` for `CallerRunsPolicy` so the calling thread runs the task instead — natural backpressure on the producer. Second, added a Prometheus counter for rejected tasks so it would never be silent again. Third, added a WARN log at 80% queue depth as an early signal.

I also pinged him on chat and asked if he had time for a 15-minute call. We walked through the new design. He had one more catch — I was not exporting the metric to our SLA dashboard. Added that too.

### Result

The library went out with `CallerRunsPolicy` and full instrumentation. About four months in, the queue-depth warning triggered during a downstream slowdown. We caught it before any audit got lost and scaled the pool. He later became the loudest internal advocate for the library and helped me onboard two other teams. Twelve services adopted it. The thing I took away — defending a design publicly when you have not actually sat with the feedback is the fastest way to lose trust.

---

## Technical depth — if they probe

- **CallerRunsPolicy vs DiscardPolicy**: Caller-runs makes the request thread itself run the audit publish under saturation. Adds maybe 10-50ms to that request but never loses an event. Natural backpressure.
- **Why DiscardPolicy was wrong**: Async wrapper swallows rejections. No exception bubbles up. Combined with no metric, the loss is invisible. For compliance data that is unacceptable.
- **Instrumentation added**: `audit_pool_rejected_total` counter, queue-depth gauge, WARN log at 80% capacity, dashboard panel on the team SLA board.
- **The 1:1 move**: Public PR thread is a bad place to argue. Real disagreement happens in a call where the other person can see you actually changed your mind.

---

## Likely follow-ups

**Q: How long did it take you to switch from defensive to "he's right"?**
> About an evening. The walk helped. I had to separate the ego — I picked DiscardPolicy — from the design question.

**Q: What if he had been wrong?**
> I would have replied with the math, the rate calculations, and the rejection-metric proposal so even if the policy was fine the visibility would be there. The instrumentation point was independently valuable.

**Q: Why CallerRunsPolicy and not just a bigger queue?**
> Bigger queue just delays the problem. Caller-runs gives genuine backpressure to the upstream caller — they slow down, queue drains, system self-regulates.

**Q: How did you rebuild the working relationship?**
> The 1:1 was the main thing. After that I asked him to review my next two PRs first. That signal — I trust your eye — did more than any apology.

---

## What NOT to say

- Do not say "we had a fight." It was a code review disagreement, not a fight.
- Do not paint him as the bad guy. He saved the library.
- Do not skip the part where you were initially defensive. The interviewer wants to see you can be wrong and recover.

---

## Backup story (if asked for another)

G8 — Tech Stack Defence. Senior lead pushed for Kafka + microservices + k8s on Coffee. I was the only engineer with three months to ship 12 modules. I built a one-pager with real numbers, walked him through it in a 1:1 before the design review, kept Watermill on RabbitMQ and a modular monolith. Shipped on time.
