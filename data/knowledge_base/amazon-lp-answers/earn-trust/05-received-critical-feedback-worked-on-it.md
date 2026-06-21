# Q: Tell me about a time you received critical feedback. How did you work on it?

> **LP**: Earn Trust
> **Primary story**: `W3 — DiscardPolicy Feedback (next-standup walk-back angle)`
> **Backup story**: `W12 — Why-Leaving Framing`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Audit common library, late 2024. Senior engineer reviewed the PR and flagged my thread-pool queue size as arbitrary and risky — said it would silently drop audit records when full. I'd defended it on the PR thread the first day. By that evening I knew he was right but hadn't said anything publicly.

### Task

The standup the next morning was the right place to walk it back. Sending another PR comment would have been quiet. Saying it in front of the team was the part I was avoiding.

### Action

Standup that morning, when the round-robin got to me, I changed plans. Instead of giving my normal update I said: "I want to flag the audit library PR. I pushed back on the queue-size comment yesterday. I sat with it last night. The senior engineer is right — there's a silent-drop path I missed. I'm adding three things to the PR before merging." Then I listed them out loud — Prometheus counter for rejected tasks, WARN log at 80% queue depth, README section explaining the trade-off.

Maybe 30 seconds of dead air. Felt longer. Standup moved on.

After standup I did the work. Added `audit_log_rejected_count` as a counter — straightforward. The 80% queue-depth WARN was trickier — needed a periodic sampler thread because `ThreadPoolTaskExecutor` doesn't expose queue depth as a gauge by default. Wired that up. Updated the README. Pushed the new commits.

Then I replied on the PR. Not just "fixed" — I walked through the failure path I'd traced overnight, listed the three changes specifically, and asked the senior engineer if anything else was missing. He flagged thread-name prefix on the pool for heap-dump readability. Added that too.

### Result

Library merged two days after the original feedback. Production has fired the 80% queue warning twice since — both during downstream slowdowns, both times we scaled the pool before a single record was actually dropped. The senior engineer who'd flagged it later became one of the strongest advocates for the library and helped onboard a fourth team I never had to talk to directly.

The part I keep coming back to: the standup walk-back was the hardest sentence I'd said all year. Saying "he's right and I was wrong" in front of the team didn't cost me anything. The opposite — it bought credibility that "I'll defend a design and change it when the evidence demands it." That credibility is the asset.

---

## Technical depth — if they probe

- **The three changes**: `audit_log_rejected_count` counter, queue-depth WARN at 80%, README documenting the bound. Plus thread-name prefix per the senior's follow-up.
- **Why a periodic sampler for queue depth**: `ThreadPoolTaskExecutor.getQueue().size()` is `O(1)` but you don't want to call it on every task. Sampler thread runs every 10 seconds and emits a gauge.
- **Why a counter for rejected, not a gauge**: Rejections are events, not state. Counter + `rate()` in Prometheus is the right shape.
- **README placement**: Right under "Configuration" — first thing a new team reading the doc sees. Trade-off needs to be visible, not hidden in an appendix.

---

## Likely follow-ups

**Q: Why standup instead of a Slack DM?**
> Slack DM would've felt private — like I was hiding it. Standup made it the team's information. Other engineers should see what happens when feedback lands.

**Q: How did the senior engineer react?**
> He said "ok cool" and moved on. No drama. That's exactly the right reaction — he wasn't keeping score, and treating it like a normal engineering exchange is what kept the relationship working.

**Q: Did anyone else on the team flag similar issues afterwards?**
> Yes. Once I'd made the failure path visible in standup, two other engineers reviewed their own thread-pool configs in adjacent services. Found two similar patterns. Both got instrumented.

**Q: What if the senior had been wrong?**
> Then my standup wouldn't have been a walk-back — it would have been "here's the math, let me know what I'm missing." The structure of saying it out loud is the same. The content depends on what overnight thinking actually produced.

---

## What NOT to say

- Don't say "I have no ego" — that's a thing only people with ego say.
- Don't dramatise the standup. It was 30 seconds and the team moved on.
- Don't claim the lesson is "always agree with seniors." The lesson is verify, then act publicly.

---

## Backup story (if asked for another)

When my Walmart manager asked why I wanted to leave the team, I gave him the honest version — I wanted to work on larger-scale systems and the org's roadmap had me on small features for the next year. He didn't take it personally. We spent the next month finishing the audit library cleanly and writing handoff docs for the IAM platform. Both projects shipped without disruption because I'd been honest about the trajectory three months in advance instead of dropping it as a surprise.
