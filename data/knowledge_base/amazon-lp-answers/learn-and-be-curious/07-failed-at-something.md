# Q: Tell me about a time when you failed at something.

> **LP**: Learn and Be Curious
> **Primary story**: `W3 — DiscardPolicy Feedback`
> **Backup story**: `P4 — First Job Learning Curve`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Mid-2024 at Walmart Data Ventures. I was hardening our Kafka audit publisher. Under load tests at around 5K req/sec the executor queue would fill and the framework rejected tasks. I had to decide what to do when the queue overflowed. Pick a `RejectedExecutionHandler`, ship it, move on.

### Task

Choose the rejection policy for the audit log thread pool. I owned the design end-to-end.

### Action

I shipped `DiscardPolicy`. My logic at the time was — audit logs are best-effort, they shouldn't block the supplier-facing request thread, dropping a few during burst was fine. The PR went up. Tests passed. Looked clean.

Rajesh, a senior on the team, pinged me on Slack the next morning. One line: "How will you know you dropped them?" I tried to defend the choice for about a day. Then I went back to the dashboard.

He was right and I'd missed it. DiscardPolicy is completely silent — no log, no metric, no exception. We had a compliance commitment that audit events shouldn't vanish without a trace. The dashboard would stay green while data quietly disappeared during a burst. I'd optimised purely for latency and ignored "how would I detect this failing."

I rolled it back the next morning. Switched to `CallerRunsPolicy` so the calling thread handles overflow itself — adds backpressure on the producer but nothing is silently lost. Then I added a Micrometer counter `audit.publisher.rejected` and a queue-depth gauge. Both went into our Grafana board with an alert at 80% queue utilisation.

The bigger fix was the one inside my head. I added a checklist item to my design notes — "what does failure look like and how will I see it" — and made it a step I do before merging, not a wishlist for later.

### Result

Zero silent drops after the switch. Two weeks later, during a Pepsi onboarding spike, the new queue-depth alert fired. We scaled pods, the audit pipeline absorbed the burst, no data loss. That's the moment I realised the lesson wasn't really about CallerRunsPolicy — it was about treating observability as part of the change, not a follow-up ticket. Honestly, the embarrassment of getting a one-line question I couldn't answer is what made it stick.

---

## Technical depth — if they probe

- **DiscardPolicy**: silently drops the task. No log, no metric, no exception. Worst possible behaviour for compliance-sensitive data.
- **CallerRunsPolicy**: runs the rejected task on the submitting thread. Creates natural backpressure — request thread slows down, upstream notices.
- **Why not AbortPolicy**: throws `RejectedExecutionException`. Would have failed supplier-facing requests during burst, which is worse than slow.
- **What I added**: `audit.publisher.rejected` counter, `audit.queue.depth` gauge, Grafana alert at 80% depth.

---

## Likely follow-ups

**Q: Why didn't you catch this in your own review?**
> I anchored on latency and didn't ask the observability question. My checklist now has "is there a metric for the failure mode of this code path" — if no, I stop and add one.

**Q: Did Rajesh write the rollback PR or did you?**
> I did. He just asked the one question. The fix was mine.

**Q: What about backpressure on the supplier API thread?**
> CallerRunsPolicy does slow the request thread under burst — that's the tradeoff. For audit, that's correct. The supplier API SLA is generous enough to absorb a 50–100ms hit; losing audit data is not absorbable.

**Q: How do you raise this kind of thing for juniors now?**
> Same question Rajesh asked me. "How will you know if this fails." Doesn't shame anyone, doesn't dictate the fix. Just makes them go look.

---

## What NOT to say

- Don't say it was a production incident. It was caught in code review and load test, before any customer impact.
- Don't blame the framework. The default behaviour is documented.
- Don't oversell the fix as innovation. CallerRunsPolicy is textbook. The lesson was the habit, not the code.

---

## Backup story (if asked for another)

At PayU as a fresh hire on the loan disbursal team, I tried to refactor a payment-state-machine in my first month. I rewrote about 400 lines, opened a PR, and tagged my senior. He spent 90 minutes in code review showing me why every "improvement" I'd made would break under a corner case the existing code already handled. I learned to read production code patiently before deciding I knew better than it. That habit — read before refactor — has saved me from a lot of bad PRs since.
