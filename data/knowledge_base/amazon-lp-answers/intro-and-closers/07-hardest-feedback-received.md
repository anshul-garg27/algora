# Q: What's the hardest feedback you've ever received?

> **LP**: Intro & Closers
> **Primary story**: W3 — DiscardPolicy code-review feedback from senior engineer
> **Backup story**: P4 — first job learning curve (if they want a softer one)
> **Time budget**: 75–90 seconds spoken

---

## STAR — how to actually tell it

### Situation

Code review for the audit-logging shared library at Walmart. I'd configured the async thread pool — 6 core threads, 10 max, queue size 100. A senior engineer named the colleague — I'll call him R — left a public comment on the PR. Direct quote: "queue size 100 is arbitrary and the DiscardPolicy will silently drop audit logs. This is a compliance system."

My first reaction was defensive. I had thought about the thread pool. I'd run the math on memory. So I started typing a reply explaining my reasoning.

### Task

I needed to either defend the design with data, or accept the feedback. The harder part was that the comment was public — every other engineer on the team would read whatever I wrote.

### Action

I didn't send the reply. I closed the tab and walked.

When I came back, I actually ran the failure mode. Each audit payload is around 2KB. Queue of 100 is 200KB — that's not a memory issue, I had that right. But the default `ThreadPoolExecutor` discard policy when the queue fills up *throws* a `RejectedExecutionException` — and because the audit method was `@Async` with a fire-and-forget handler, that exception goes to the void. We'd lose audit data with zero indication it happened.

R was right. I'd designed for the happy path.

I spent the rest of the afternoon adding three things. A Prometheus counter for rejected tasks, exported through Micrometer. A WARN-level log when queue depth hit 80 percent — early signal before the drops start. And a section in the README explaining the trade-off, the metric to watch, and the alert threshold.

Then I replied on the PR — not defending, just listing what I'd added — and asked "anything else I missed?".

### Result

The library shipped with that monitoring. About four months later, during a downstream Kafka slowdown, the queue-depth alert fired at 82 percent — we scaled the consumer pool before any audit logs were dropped. That alert wouldn't have existed if I'd sent the defensive reply.

The deeper thing I took from it — defending good design is fine, but defending **your** design before checking the failure mode is just ego. R wasn't questioning my intent; he was questioning my testing. Big difference.

R later became one of the strongest advocates for the library across the org. I think part of why was that I responded to his catch instead of around it.

---

## Technical depth — if they probe

- **The exact thread pool config**: `ThreadPoolTaskExecutor`, core 6, max 10, queue capacity 100, `RejectedExecutionHandler` default which is `AbortPolicy`. Inside `@Async` fire-and-forget, the abort exception is swallowed by Spring's async error handler.
- **The monitoring added**: `Counter` for `audit_log_rejected_tasks_total`, `Gauge` for `audit_log_queue_depth`, alert rule at 80 percent capacity for 5 minutes. The threshold was deliberately conservative — better one false-positive a quarter than one missed compliance gap.
- **Why I didn't move to `CallerRunsPolicy`**: that would've back-pressured the source API thread, which violates the "zero latency impact" promise. The right answer was visibility, not back-pressure.

---

## Likely follow-ups

**Q: How long did it take you to accept he was right?**
> Honestly, about 20 minutes. The walk helped. I came back, ran the actual rejection path, and saw the silent-drop hole. The hard part wasn't accepting it intellectually — it was killing the half-typed defensive reply.

**Q: What did the senior engineer say after?**
> He thanked me on the PR thread for the metric. We've worked together since on the multi-region rollout — he's the person I now ping when I want a brutal review of a design.

**Q: Did this change how you write code reviews now?**
> Yes. When I review someone's PR and I think they're wrong, I try to ask "what happens when the queue is full?" instead of saying "this is wrong". Same content, different door. People accept questions more easily than verdicts.

**Q: Have you received harder feedback than this?**
> Not on a technical decision, no. The personal-style feedback in my W3 1:1 — "you go too deep without coming up for air" — that's harder to act on because the fix is a behaviour, not a metric. The DiscardPolicy one was actually easier because I could ship the fix the same day.

**Q: Why was this hard if it was a fast fix?**
> Because it was public, in front of the whole team, on a system I'd argued for. The fix took an afternoon. The ego-management took longer.

---

## What NOT to say

- Don't pick a feedback piece you didn't actually act on — interviewers can tell.
- Don't pick something trivial ("they told me to put more comments in my code") — that's not hard, that's correctable in 5 minutes.
- Don't blame the messenger ("the way he said it was rude") — even if true, it makes you sound thin-skinned.
- Don't make yourself the hero too fast. The first 10 seconds of the story should sound uncomfortable, not triumphant.
- Don't end with "and that's why I'm great at feedback now" — the reflection should be specific to this one moment, not a personality claim.

---

## Backup story (P4 — PayU first job learning curve)

In my first weeks at PayU as an intern, my mentor told me my code was technically correct but unreviewable — no commit messages, monster PRs, no tests. He said it kindly but it stung because I thought I was being fast. I asked him to do a sit-down review of one of my PRs, slot-by-slot. He spent 40 minutes walking through what a good commit message looks like, why a 200-line PR is faster than a 2000-line PR over the full cycle, and why tests are a gift to the next person. That changed how I shipped code from then on. Looking back, the loan-disbursal failure-rate work and the TAT improvement at PayU happened *because* the code was reviewable enough to ship in small slices.

---

## Spoken-vs-written delivery note

- The pause matters. "My first reaction was defensive." Beat. Then continue.
- "R was right." — say it flatly. Not apologetically. Owning the wrong-ness without grovelling is the move.
- Don't rush the "alert fired at 82 percent" payoff. That's the line that says the feedback compounded into real impact.
- End on the R-as-advocate line. Quiet, not boastful.
