# Q: Describe a situation where you failed at a task and what you learned.

> **LP**: Learn and Be Curious
> **Primary story**: `W3 — DiscardPolicy Feedback`
> **Backup story**: `P3 — Test Coverage Program`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Mid-2024. I was hardening our Kafka audit publisher at Walmart Data Ventures. Suppliers' API calls had to land in our audit pipeline reliably. Under load tests at 5K req/sec, our publisher thread pool started rejecting tasks. I had to pick a `RejectedExecutionHandler` fast.

### Task

Choose a rejection policy for the audit log executor. I owned this end-to-end. Code review was happening that afternoon.

### Action

I went with `DiscardPolicy`. My reasoning at the time: audit logs are best-effort, dropping a few under burst was better than blocking the request thread and slowing supplier-facing APIs. Shipped it. Felt clean.

A senior on the team — Rajesh — pinged me on Slack the next day. One line: "How will you know you dropped them?" I started to defend it. Then I sat with the question.

He was right. DiscardPolicy is silent. No logs, no metric, nothing. We had a compliance commitment that audit events should not vanish without a trace. I had optimised for the wrong thing — pure latency — and ignored observability. Worse, the dashboard would still look green while data was disappearing.

I rolled back the next morning. Switched to `CallerRunsPolicy` so the publisher thread itself handled overflow — adds backpressure, but nothing is silently lost. Then I added a Micrometer counter `audit.publisher.rejected` and a queue-depth gauge. Wired both into our Grafana board and added an alert at 80% queue utilisation.

The bigger fix was on me. I started writing down "what does failure look like and how will I see it?" as a real step in my design checklist, not a vague principle.

### Result

Zero silent drops after the switch. The new queue-depth metric caught a real spike during a Pepsi onboarding event two weeks later — alert fired, we scaled pods, no data loss. Honestly, the embarrassment of someone else asking the obvious question is what made it stick. I now treat "how will I detect this failing" as part of the change, not a follow-up ticket.

---

## Technical depth — if they probe

- **DiscardPolicy vs CallerRunsPolicy**: Discard silently drops; CallerRunsPolicy runs the task on the submitting thread, which slows the producer naturally. For audit data, backpressure beats data loss.
- **Why not AbortPolicy**: That throws `RejectedExecutionException` to the request thread. We didn't want supplier APIs to fail just because audit was busy.
- **Observability added**: `audit.publisher.rejected` counter, `audit.queue.depth` gauge, Grafana alert at 80% queue depth.
- **Tradeoff I missed first time**: A bounded queue with no rejection metric is worse than a slightly slower request path with full visibility.

---

## Likely follow-ups

**Q: Why did you pick DiscardPolicy in the first place?**
> I was anchored on supplier API latency. Audit is async, so dropping felt safe. I forgot that "safe" needed a way to verify.

**Q: How did you decide the 80% queue-depth alert threshold?**
> Empirical. I ran the same 5K req/sec load test and watched queue behaviour. At 80% we still had headroom; at 95% we were already rejecting. 80% gave the on-call about 5 minutes to react.

**Q: Could you have caught this in code review yourself?**
> I should have. My checklist now has "is there a metric for the failure mode of this code path." If the answer is no, I stop and add one.

**Q: What did Rajesh's feedback teach you about working with seniors?**
> One short question can save a week of pain. I now ask other people's juniors' code the same kind of question — not gotchas, just "how would you know."

---

## What NOT to say

- Don't say it was a "production incident." It was caught in load test plus design review — no customer impact.
- Don't blame the framework. The default executor behaviour is documented; I just didn't read it carefully enough.
- Don't oversell the fix as innovation. CallerRunsPolicy is textbook — the lesson was about observability, not the policy.

---

## Backup story (if asked for another)

At PayU, my first big task was a test coverage program for our loan disbursal service. I wrote 200+ tests in two weeks and hit our 80% target. Two months later, an integration bug slipped through because all my tests were unit-level — I'd never set up the disbursal flow against a real bank sandbox. Coverage looked great, real behaviour wasn't tested. Since then I write at least one integration test against a real dependency before declaring a feature done.
