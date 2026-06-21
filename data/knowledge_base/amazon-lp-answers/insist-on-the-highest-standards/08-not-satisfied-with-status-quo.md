# Q: Tell me about a time you weren't satisfied with the status quo.

> **LP**: Insist on the Highest Standards
> **Primary story**: `W3 — DiscardPolicy + queue-depth instrumentation`
> **Backup story**: `W6 — Pepsi 2-day debug accepted as normal`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Mid-2025, the audit library was live. Three teams using it. The thread pool config was 6 core, 10 max, 100 queue, with the default `AbortPolicy` and a catch-all in the async method that swallowed exceptions to "keep the API path safe."

The team's view: it works, ship it.

A senior engineer left a comment on my PR. "Your queue size of 100 is arbitrary. When it fills, you'll lose audit records silently and never know." The team's view on the comment: nice-to-have. We've already shipped through dozens of these.

### Task

The library was the audit path for supplier APIs. Records being silently dropped meant compliance gaps nobody could see. Status quo said move on. I didn't want to.

### Action

I ran the math first. Each audit payload is around 2KB. Queue of 100 is 200KB — not a memory problem. The real problem is `AbortPolicy` throws `RejectedExecutionException`, our catch-all logs and swallows, and the API keeps serving like nothing happened.

He was right. I'd defended my design for a day. Then I sat with it overnight and walked into standup the next morning saying he was right.

Three changes went in before merge:

First, a Prometheus counter for rejected tasks — `audit_log_rejected_count`. Now dropped records show up on the dashboard.

Second, a WARN log at 80% queue depth — `audit_log_queue_depth`. Early signal before the pool starts rejecting.

Third, documentation — the trade-off was spelled out in the library README. Audit is best-effort by design, but "best-effort" doesn't mean "silent."

I replied on the PR thanking him, listed the three changes, asked what else I'd missed. He flagged one more — the thread-name prefix for the pool so rejected tasks show up under a clear name in heap dumps. Added that too.

### Result

The library shipped. The 80% queue warning has fired twice in production — both times during downstream slowdowns. Both times we scaled the thread pool up before a single audit record was actually rejected. The senior engineer later became one of the loudest internal advocates for the library and helped onboard a fourth team.

The lesson I keep going back to: "it works" isn't a high bar. "It works and tells me when it doesn't" is.

---

## Technical depth — if they probe

- **`AbortPolicy` vs `CallerRunsPolicy`**: `CallerRunsPolicy` would block the calling thread (API request thread) when the queue is full — that's worse, it makes API latency depend on audit-pool health. `AbortPolicy` + instrumentation gives us "drop with visibility" instead of "drop silently."
- **Why 100 queue and not unbounded**: Unbounded queue = OOM under sustained downstream slowness. Bounded queue gives backpressure. The right answer is bounded + observable.
- **80% threshold**: From the post-mortem playbook. 80% is "early enough to act, late enough not to be noise." We tested 70% — noisy. 90% — too late.
- **The metric name choice**: `audit_log_rejected_count` follows the team Prometheus naming convention so it shows up in the standard Grafana dashboards without anyone wiring a panel.

---

## Likely follow-ups

**Q: How did you decide to push back on "ship it"?**
> The cost of being wrong was asymmetric. If I added the instrumentation and it wasn't needed, we wasted half a day. If I shipped without it and the queue silently filled, suppliers' audit trails had gaps we couldn't detect or fix.

**Q: Was the senior's comment public or private?**
> Public on the PR. First instinct was defensive. Second instinct was to run the numbers.

**Q: Did you go look for similar patterns elsewhere?**
> Yes. Two other internal libraries had the same `AbortPolicy` + swallow-catch combo. I raised them with their owners and shared the metric pattern. One team adopted it.

**Q: What's the broader lesson?**
> "Is it running?" isn't monitoring. "Is it processing correctly, fast enough, without losing data?" is monitoring.

---

## What NOT to say

- Don't paint the team as careless — most teams ship with default thread-pool config.
- Don't claim the queue is "now perfect." It's bounded and observable; both matter.
- Don't generalise "always question status quo." Sometimes status quo is right; the discipline is which battles to pick.

---

## Backup story (if asked for another)

At Walmart in 2025, Pepsi's onboarding had a 2-day average debug cycle whenever they couldn't see a store's data — because every request was a manual ticket to my team to check authorization tables. The team treated it as the cost of doing business. I built BigQuery row-level security with `@policy_tag` so suppliers could self-serve. The 2-day debug became 30 seconds. The status quo was an accepted cost; the fix was a one-time policy-tag config.
