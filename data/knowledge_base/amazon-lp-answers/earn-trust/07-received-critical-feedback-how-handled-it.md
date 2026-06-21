# Q: Tell me about a time when you received a critical feedback and how did you handle it.

> **LP**: Earn Trust
> **Primary story**: `W3 — DiscardPolicy Feedback (handling-the-public-disagreement angle)`
> **Backup story**: `P3 — Test Coverage Program`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

PR review on the audit common library, late 2024. A senior engineer left a comment on the thread-pool config: "Your queue size of 100 is arbitrary. When it fills, you'll lose audit records silently and never know." Public on the PR thread. Direct, not gentle.

The library was about to go to three teams. I'd already pitched it to their leads. The PR review was the last gate.

### Task

Handle this publicly without making it worse. Specifically: don't defend out of ego, don't capitulate without doing the math, don't make him look bad, don't make me look bad.

### Action

I held back the first reply. The instinct was a quick "I considered this — here's why 100" and move on. That would've ended the conversation in a way I'd regret if he was right.

Instead I left it for the day. Went back to other work. Around 6 PM I pulled the code up and traced his scenario through it specifically.

Each audit payload is around 2KB. Queue of 100 fills if downstream slows by half — well within normal operating range. When `AbortPolicy` throws, my async method's catch-all logs the exception and moves on. There's no metric. There's no dashboard panel. The API keeps serving like nothing happened.

He was right. I'd defended in my head for half a day; the trace took 10 minutes.

The next morning at standup I said it out loud — pushed back yesterday, sat with it overnight, he's right, here's what I'm adding. Then I went and built it. Prometheus counter for rejected tasks. WARN log at 80% queue depth. README section explaining the trade-off.

Replied on the PR thread. I didn't just write "fixed." I wrote out the failure path I'd traced, listed the three additions, and asked what else I'd missed. He flagged thread-name prefix for heap dumps. Added that too. Asked one more time if anything was missing. He approved.

The public part of handling it well was specifically the PR reply. Not a one-liner. Walked through what I'd learned, what I'd changed, asked for more. That signal — "I'm taking your feedback seriously enough to write three paragraphs about it" — was what closed the loop publicly.

### Result

Library shipped two days after the original feedback. Three teams adopted within a month. The 80% queue warning fired twice in production since, both during downstream slowdowns — both times we scaled the pool before a single audit record was actually dropped. The senior engineer who'd flagged it later helped onboard a fourth team.

The handling was the win. If I'd shipped a one-line "you're right" within five minutes, he wouldn't have trusted that I'd actually thought about it. If I'd defended hard, we'd have argued and one of us would've escalated. The half-day wait plus the worked-through reply is what made it land.

---

## Technical depth — if they probe

- **The trace I did**: At 100 req/s, downstream slows to 50, pool fills in ~2 seconds, queue fills in ~4 seconds, then every new audit task throws `RejectedExecutionException`, caught and swallowed. Zero visibility.
- **Why instrumentation over a bigger queue**: Bigger queue just delays the same failure. The metric tells you the system is at the boundary regardless of the queue size you chose.
- **80% empirical threshold**: 70% was noisy during load tests with normal GC; 90% gave less than 30 seconds of warning. 80% gives 1–2 minutes — enough to scale the pool or accept some loss intentionally.

---

## Likely follow-ups

**Q: Why didn't you reply immediately?**
> Immediate replies are reactive. I wanted to know whether he was right before I answered. Half a day is short — long enough to actually trace the scenario, short enough not to look like I was avoiding it.

**Q: How did the rest of the team see this?**
> The standup walk-back made it visible. Two other engineers reviewed their own thread-pool configs in adjacent services after that — turned up similar patterns and instrumented them. The feedback became a team-level lesson, not just mine.

**Q: What if he had been wrong?**
> Then my PR reply would've been the same shape — "here's the failure path I traced, here's why your scenario doesn't materialise, what am I missing?" The structure works either way. The content depends on what tracing actually shows.

**Q: Has this changed how you give critical feedback now?**
> Yes. I always include the specific failure path in my own review comments now — not "this looks wrong" but "here's the scenario I'm worried about." Gives the author something to verify, not just an opinion to react to.

---

## What NOT to say

- Don't say "I always take feedback gracefully." The half-day defensive period is the honest part.
- Don't say "I handled it perfectly" — the perfect version is the one with the public walk-back, which is hard.
- Don't make the senior into either a villain or a saint. He was direct, he was right, and we both moved on.

---

## Backup story (if asked for another)

At PayU my mentor flagged 40 of my tests as brittle — too coupled to implementation, broke on every refactor. I rewrote them in two passes — against the service interface only, with behaviour assertions instead of state assertions. That feedback became a habit. Test coverage at PayU went from 30% to 83% during my internship, and the tests survived three years of post-internship refactoring because they were testing contract, not implementation.
