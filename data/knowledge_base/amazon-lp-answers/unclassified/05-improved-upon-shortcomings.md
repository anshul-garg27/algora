# Q: Tell me about a time when you improved upon your shortcomings.

> **LP**: Unclassified (Learn and Be Curious + Are Right A Lot)
> **Primary story**: W3 — DiscardPolicy feedback → systematic instrumentation habit
> **Backup story**: P3 — Test coverage discipline at PayU
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Code review on the audit-logging shared library at Walmart, late 2024. I'd designed the async thread pool — 6 core, 10 max, queue capacity 100. A senior engineer left a comment on the PR: queue size 100 is arbitrary, and the default `DiscardPolicy` will silently drop audit logs. He was right. The fix was a fast afternoon.

But the harder thing he flagged in our follow-up 1:1 was the pattern. He'd seen me ship two systems where the happy path was solid but the failure modes were untested. The DiscardPolicy was the third instance. He said it directly: "you design well, but you don't think about what happens when your system fails until production tells you."

That landed. It was true.

### Task

The shortcoming wasn't "I forgot to add a metric". It was "my default is to design for the happy path". I needed to change that default — not on one PR, but on every PR going forward.

### Action

I made three concrete changes to how I write code.

**One — Failure-mode checklist before every PR.** Before I send a PR for review, I now run through five questions in order. What happens when the queue fills up? What happens when the downstream is slow? What happens when the input is null or malformed? What metric will alert me to this failing? What's the rollback path? I wrote them on a sticky note that's been on my monitor for over a year.

**Two — Every async path gets a counter.** No exceptions. Rejected tasks, dropped messages, timeouts. Even when I think it'll never fire. The Prometheus counter for `audit_log_rejected_tasks_total` was a direct output of the W3 feedback.

**Three — Pre-launch chaos drill.** Before any new service goes to prod, I deliberately break one thing — kill the downstream, OOM the JVM, flood the input — and watch which alerts fire. If the alert doesn't fire, the launch waits.

The proof these stuck: a few months after the W3 fix, during a real downstream Kafka slowdown, my queue-depth alert fired at 82 percent — pre-empted any actual data loss. We scaled the consumer pool, no audit logs dropped. That alert wouldn't have existed if I hadn't internalised the feedback.

The W1 silent-failure incident a few months after that was the bigger validation. Five days of debugging across null SMT headers, KEDA feedback loops, JVM heap exhaustion — zero data loss, because the failure-mode instrumentation I'd added since W3 caught the lag long before any drops happened.

### Result

The pattern is now a habit. My last design review at Walmart, the same senior engineer who'd given me the original feedback said — "you've inverted on this one. You're thinking about failure first now." That was the moment I knew it had taken.

The honest reflection — improvement on a shortcoming isn't a single PR. It's changing the default behaviour, with a forcing function (the sticky note, the chaos drill) that you can't skip. The fix isn't willpower, it's the system around the willpower.

---

## Technical depth — if they probe

- **The DiscardPolicy specifically**: `ThreadPoolTaskExecutor` with default `AbortPolicy` throws `RejectedExecutionException` when the queue fills up. Inside `@Async` fire-and-forget, that exception goes to Spring's async error handler — which logs but doesn't surface as a metric. Three lines of Micrometer instrumentation fixed it.
- **The chaos drill**: not a full chaos-engineering setup, just a manual checklist in stage. Kill the downstream Kafka cluster, watch alerts. OOM the JVM with a forced large batch, watch alerts. Send a null-header record, watch alerts. Each one either fires or files a new alert as a follow-up before prod.
- **What changed structurally**: my PR template at Walmart now has a "failure modes considered" section as a required check. Borrowed and adapted from a Google SRE template. Has caught two issues across our team in the last six months.

---

## Likely follow-ups

**Q: What if the chaos drill catches a problem the day before launch?**
> Then launch slips. That's the deal. The whole point of the drill is to find issues before customers do. I'd rather slip a day than write a post-mortem.

**Q: Has the failure-mode checklist ever caused you to delay something unnecessarily?**
> Once. I held a non-critical analytics endpoint for three days because I wanted a slow-downstream alert that turned out to add no real value — downstream was already monitored upstream. I'd rather over-instrument once than under-instrument once.

**Q: How do you teach this to others?**
> The junior on my team got the checklist on day one. We pair-reviewed his first PR using it. He now runs it on his own work — he caught a null-pointer-on-empty-list case last month before I would've seen it in review.

**Q: Was the original feedback the hardest you've received?**
> Yes — partly because it wasn't a single fix, it was a pattern. Fixing a thread pool is easy. Changing how you think about systems is slower.

**Q: Have you developed any other shortcomings since?**
> The depth-first habit — going deep before surfacing to the team. That's the current one I'm working on, with the 2-hour timebox and lateral check-ins. Different shape from the W3 one, same approach — forcing function plus repetition.

---

## What NOT to say

- Don't pick a fake shortcoming. "I work too hard" or "I'm a perfectionist" — interviewers tune out.
- Don't claim the shortcoming is fully fixed. "Inverted on this one" is the honest version; "completely solved" is the fake version.
- Don't make it about being told once and learning forever — improvement on a real shortcoming takes months of repetition.
- Don't trash the colleague who gave the feedback. "He was right" is the right tone.

---

## Backup story (P3 — Test coverage at PayU)

When I was an intern at PayU on the loan-disbursal flow, I shipped fast but with minimal tests. My mentor told me — kindly, but directly — "your code works but it's not safe to change". The shortcoming was that my speed depended on me being the only person who'd touch the code. The fix was a discipline I built over a quarter — every new feature came with at least one happy-path integration test and one failure-mode test. By the time I finished the disbursal-TAT work (3.2 min → 1.1 min), the test coverage on that path was 78 percent. Different shortcoming, same pattern — forcing function (mandatory test in every PR), repeated over months, until the default flipped.
