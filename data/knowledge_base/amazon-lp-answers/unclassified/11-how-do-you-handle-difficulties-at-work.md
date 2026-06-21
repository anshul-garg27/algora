# Q: How do you handle difficulties at work?

> **LP**: Unclassified (multi-story framed answer)
> **Primary story**: W1 — Silent Kafka Failure (technical difficulty)
> **Backup story**: W3 — DiscardPolicy Feedback (interpersonal / feedback difficulty)
> **Time budget**: 90–120 seconds spoken — this is a framed multi-story answer

---

## How to read this question

This isn't a single-story question. It's a **framing** question — they want to know your default behaviour under difficulty, then they want one or two examples that prove it.

The right shape is: state the framework in 15 seconds, then run two short examples — one technical, one interpersonal. Keep each example under 30 seconds.

---

## The spoken answer

Three things, every time.

**One — separate the bug from the feeling about the bug.** When I hit a hard problem, the first thing I do is name what's making it hard. Is the technical surface big? Is the deadline real? Am I getting feedback that stings? Naming the source separates "I'm stuck because the problem is hard" from "I'm stuck because I'm reacting to it". Usually it's both, but they need different fixes.

**Two — break it down until something is shippable.** No matter how big the problem looks, there's almost always a 2-hour piece I can ship that moves the needle. Even if it's just a metric, a runbook, or a half-fix. The win there is psychological too — shipping anything breaks the stuck feeling.

**Three — surface, don't tunnel.** This is the one I've been working on most. My default used to be "go deep alone until I crack it". My current default is "post in the team channel, then go deep". Saves time and saves the team from wondering where I am.

Two quick examples.

**Technical example — Kafka silent failure.** 2 million events a day stopped landing in GCS. No alerts. Day one I narrowed the failure surface to consumption-or-write. Day two I shipped an SMT null-header fix — a real shippable piece, even though I knew there were probably more bugs underneath. Five days in, I'd found three independent root causes — null headers, KEDA feedback loop, JVM heap OOM. Zero data loss because Kafka retained everything. The difficulty was technical; the discipline was shipping a partial fix each day instead of waiting for a complete diagnosis.

**Interpersonal example — code review feedback.** A senior engineer publicly flagged my thread-pool design on a PR. My first reaction was defensive. I almost typed a defensive reply. Instead I walked away, ran the actual failure mode he was warning about, confirmed he was right, and shipped three concrete changes — a metric, a warn-log, a README section. Replied thanking him. The difficulty was ego, not engineering. The fix was naming it before responding.

Those are the two flavours I hit most — technical depth and ego-on-feedback. The three-step approach holds for both.

---

## Why this works

- **Frame first, examples second.** You signal that you have a default, not just stories.
- **Two examples in different flavours** — technical and interpersonal. Shows breadth.
- **Honest about the "surface, don't tunnel" gap.** You name the weakness you're actively working on — that builds trust.
- **Numbers in the right places.** "2 million events a day", "three independent root causes" — concrete without being a metric-dump.

---

## Technical depth — if they probe

### W1 (technical difficulty)

- **Day 2 SMT fix**: try-catch around the SMT filter, default to US bucket if `wm-site-id` header is null. Two-line change, shipped same day.
- **Day 4 KEDA feedback loop**: KEDA scaling consumer pool on lag → Kafka consumer-group rebalancing → more lag → more scaling. Disabled KEDA, switched to CPU-based HPA. Cross-correlated with Kubernetes events to find this — wasn't visible in app logs alone.
- **Day 5 JVM heap**: default 512MB OOMing on large Avro batches. Bumped to 2GB. Later profiled with `jmap -histo:live` and tuned to 7GB.

### W3 (interpersonal difficulty)

- **The thread-pool design**: 6 core, 10 max, queue capacity 100, default `AbortPolicy`. Inside `@Async` fire-and-forget, rejected tasks throw exceptions that disappear into Spring's async error handler. Silent data loss path.
- **The three changes**: Prometheus counter `audit_log_rejected_tasks_total`, WARN log at 80% queue depth, README section explaining the trade-off and the alert threshold.

---

## Likely follow-ups

**Q: What if your three-step approach didn't work?**
> Then I'd ask. The third step — surface, don't tunnel — is the escape hatch. Sometimes the difficulty is "I'm in over my head", and the fix is borrowing eyes from someone who's seen it. The W1 incident is exactly where I should've surfaced earlier — that's the gap I'm working on.

**Q: Tell me about a non-work difficulty you've handled.**
> The lockdown-era job switch. I left a stable internship at PayU during the pandemic-era hiring freeze, took a job at a small startup (GCC) without knowing if it would survive. Same shape — named the source (career stagnation vs uncertainty), broke it down (financial buffer for 6 months, talked to the team before joining), and surfaced (asked my mentor for honest read on the bet). It worked out — GCC was the biggest growth step of my career.

**Q: How do you handle disagreements with peers?**
> Same shape. Name what's actually being disagreed about. Most "disagreements" are actually missing context — one of us has data the other doesn't. Most of the time, sharing the data ends the disagreement. When it doesn't, we present both options to the lead and let them call it.

**Q: What about difficulty with your manager?**
> I've been lucky — my managers have been good. The closest I've had to friction was the early days of the silent-Kafka-failure incident when my manager wanted faster status updates and I was head-down. We talked about it in a 1:1, I started posting daily "going deep on X" updates, friction resolved in a week.

**Q: What's a difficulty you've failed to handle?**
> The early GCC compensation conversation. I was doing SE-II work as SE-I for over a year and didn't ask for the title or comp adjustment. The failure was avoidance — I knew I should ask, didn't, and lost a year of comp progression. Now I treat the comp conversation like any other engineering problem — surface it, frame it with data, ship it.

---

## What NOT to say

- Don't say "I keep calm and carry on" — every candidate says it, none of them mean it.
- Don't pick a single story for this question — it's a framing question, you need at least two flavours.
- Don't pretend you've never struggled. The interviewer is looking for self-awareness, not invulnerability.
- Don't make the manager or peer the villain in the interpersonal story.

---

## Backup story (W3 alone, if they want only one)

If they cut you off after the framework and ask for "just one example of interpersonal difficulty", the W3 thread-pool feedback story stands on its own. Senior engineer flagged a real silent-data-loss hole in my design. Public PR comment. My first reaction was defensive. I walked away, ran the failure mode, confirmed he was right, shipped a Prometheus counter + WARN log + README. The hard part was killing the defensive reply, not fixing the code. Four months later, the queue-depth alert fired at 82 percent during a downstream slowdown — pre-empted real data loss. That alert wouldn't have existed without the feedback.
