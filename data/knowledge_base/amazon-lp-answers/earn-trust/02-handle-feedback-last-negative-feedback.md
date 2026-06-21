# Q: How do you handle feedback, and when was the last time you received negative feedback?

> **LP**: Earn Trust
> **Primary story**: `W3 — DiscardPolicy Feedback (overnight thinking angle)`
> **Backup story**: `P3 — Test Coverage Program`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Most recent one was on the audit common library PR. Senior engineer left a review comment that my thread-pool queue size of 100 was arbitrary and would silently drop audit records when full. Public on the PR. Not phrased gently.

Honestly, I disagreed at first. I'd picked 100 for a reason — memory budget, throughput estimates. I left a one-line reply explaining the math and went back to my other work. I thought that was the end of it.

### Task

Walking home that evening I couldn't let it go. He had 8 years of seniority on me and a reputation for catching things. If he was wrong, my one-liner was enough. If he was right, my reply had just made it worse.

### Action

I sat with it overnight. Not in a beat-myself-up way — I traced his scenario through the actual code in my head.

Production load profile: about 100 audit calls per second per pod. Thread pool: 6 core, 10 max. Queue 100. Now imagine the downstream audit publisher slows to 50 calls per second. The pool fills, the queue fills, then `AbortPolicy` starts throwing `RejectedExecutionException` on every new task. My async method catches all exceptions and logs them. The catch was meant to protect the API path. It also makes every dropped audit record invisible.

By the time I got to my laptop the next morning I knew he was right. The math worked. There's a real path where we lose data and the system looks healthy.

At standup I said it out loud. "I pushed back on the queue-size comment yesterday. I sat with it last night. He's right — there's a silent-drop path I missed. I'm adding three things to the PR."

Then I did it. Prometheus counter for rejected tasks. WARN log at 80% queue depth. README section on the trade-off. I replied on the PR thread, walked through the failure path I'd traced, and asked if anything else was missing. He flagged thread-name prefix for heap dumps. Added that too.

### Result

The library shipped two days later. The 80% queue warning fired twice in production since — both during downstream slowdowns, both times we scaled before any record was actually dropped. The senior engineer later helped me get a fourth team onboarded.

The thing I keep coming back to: the overnight delay was the trust move, not the standup walk-back. If I'd just typed "you're right" within five minutes of his comment, it would have looked like I caved. The fact that I'd actually sat with it, traced the failure path myself, and came back with a real fix is what made the change credible.

---

## Technical depth — if they probe

- **The failure path I traced**: Queue full → `AbortPolicy` throws → my `try/catch` swallows → record never reaches the publisher → API returns 200 → nobody knows.
- **Why instrumentation, not larger queue**: A bigger queue just delays the problem. The instrumentation tells you when you're hitting the wall regardless of queue size.
- **80% chosen empirically**: 70% was too noisy in load tests; 90% was too late. 80% gave a real signal with time to act.

---

## Likely follow-ups

**Q: Do you always sit with feedback overnight?**
> Not always. If it's a typo or a code-style nit, I just fix it. The overnight pause is for the ones where my first reaction is defensive — that's usually the signal I should think harder.

**Q: How did the senior react when you walked it back?**
> He just said "ok cool" in standup and moved on. That's the right reaction — he wasn't keeping score, and neither was I.

**Q: What if you'd been right and he'd been wrong?**
> I'd have come back with the numbers showing why. The overnight pause works in both directions — sometimes you confirm you were right, you just confirm it with better evidence than the original reply.

**Q: Has this changed how you receive feedback now?**
> Yes. When my first reaction is defensive, I make myself wait. The defensive reaction is information — it usually means there's something I haven't fully thought through.

---

## What NOT to say

- Don't say "I just took the feedback gracefully." The honest version — defended first, then sat with it overnight — is the trust-building move.
- Don't make the senior into a villain. He was right. The story is what I did with it.
- Don't claim you came to the standup walk-back instantly. The overnight is the point.

---

## Backup story (if asked for another)

At PayU as an intern my mentor told me 40 of my end-to-end tests were brittle — too tightly coupled to implementation details. They all broke when I refactored. I rewrote them against the public service interface and switched from state to behaviour assertions. That feedback is why I think about test boundaries before writing the first test now — and why coverage at PayU got to 83% without becoming a maintenance burden.
