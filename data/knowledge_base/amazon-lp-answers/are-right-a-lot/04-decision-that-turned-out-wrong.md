# Q: Tell me about a decision you made that turned out to be wrong — and what you did.

> **LP**: Are Right, A Lot
> **Primary story**: `W3 — DiscardPolicy Feedback`
> **Backup story**: `G6 — Initial 5-feature pick that needed adjustment`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

In the shared audit-logging library at Walmart I'd sized the async thread pool at 6 core, 10 max, 100 queue. The default `RejectedExecutionHandler` in `ThreadPoolTaskExecutor` is `AbortPolicy` — it throws when the queue fills. I deliberately chose `DiscardPolicy` — silently drop the task when the queue is full — because I didn't want audit failures to bubble exceptions up into the API response path. My reasoning: audit is best-effort, the API contract with suppliers is what matters, dropping silently keeps the API clean.

### Task

A senior engineer reviewed the design and flagged it. He said "you'll lose audit data and you won't know." I disagreed in the review. I thought he was being academic — the queue would never fill in practice, audit was best-effort, the trade-off was correct.

### Action

I defended it for about a day. I had reasons — the math said the queue wouldn't fill (100 req/sec × 50ms per audit = 5 threads in flight; the queue would only fill during a real downstream slowdown, which would be rare and short). I wrote up the math, sent it back to him.

Then I sat with what he'd actually said. "You'll lose data and you won't know." That wasn't an academic objection — it was about observability. My math said the queue rarely fills. He was saying: when it does, you have no way to find out. Even if "rarely" was 0.01 percent of the time, at 2 million events a day that's 200 lost events I couldn't see.

The next morning I came in and conceded. Told him in our 1:1: "You were right. The math says it's rare; the problem is when it happens we'd never notice. Let me fix it."

I added three things. First, a Prometheus counter `audit_log_rejected_tasks_total` that increments on every drop. Second, a WARN log at 80 percent queue capacity with the current pool stats. Third, a custom `RejectedExecutionHandler` that records the dropped task's request ID so we can correlate with downstream slowdowns.

That WARN-at-80-percent alarm has fired exactly once in production. It caught a downstream slowdown — the audit publisher service was running slow, the queue was filling. We caught it before the queue actually overflowed. Without the instrumentation we'd have lost data and never known.

### Result

The change shipped in the next library release. The senior engineer reviewed it and approved. The alarm catching a real incident later was the proof he was right. I learned to separate "the math says this won't happen often" from "we need to know when it does." Rare doesn't mean invisible.

I also took a habit from that interaction: when I'm sure I'm right and someone with more experience disagrees, I sit with the disagreement overnight before defending. Sometimes I still defend. Often I find they saw something I missed.

---

## Technical depth — if they probe

- **`DiscardPolicy` vs `AbortPolicy`**: `AbortPolicy` throws `RejectedExecutionException`. `DiscardPolicy` silently drops. I picked Discard to keep audit failures out of the API response path.
- **The math I cited**: 100 req/sec per pod × 50ms per audit = 5 threads in flight steady state. Queue of 100 = ~10 seconds of buffer at peak. Should rarely fill.
- **What I added**: `audit_log_rejected_tasks_total` Prometheus counter, WARN log at 80 percent (`queue.size() > queue.remainingCapacity() * 4`), custom handler that logs the request ID of every drop.
- **Why the alarm fired**: downstream publisher (`audit-api-logs-srv`) was running slow due to a Kafka producer config issue. Audit thread pool started filling. Caught it at 80 percent — fixed the publisher config before any drops happened.
- **The right shape for this kind of trade-off**: silent drops are fine when monitored; they're a bug when invisible.

---

## Likely follow-ups

**Q: What made you change your mind?**
> Re-reading his actual sentence. "You'll lose data and you won't know." I'd been arguing with my own version of his concern (queue fills often vs rarely). His version was about observability, not frequency. Once I separated them, he was clearly right.

**Q: How long did you defend it before changing your mind?**
> About a day. I sent him my math, slept on it, came back in the morning and conceded in our 1:1.

**Q: Did you tell him you'd been wrong?**
> Yes, directly. "You were right, I'm fixing it." Easier than rationalising. Strengthened the working relationship — he asks me to review his designs now and gives sharp feedback in return.

**Q: What's the right way to handle this in general?**
> Two rules I picked up. When I'm certain and someone senior disagrees, sit with it overnight. And when I change my mind, say so plainly — don't bury it.

**Q: What did the instrumentation actually catch?**
> A downstream Kafka producer config issue on `audit-api-logs-srv`. The publisher was slower than expected, audit thread pool was filling. The 80 percent WARN fired and an on-call engineer noticed before the queue overflowed. Without the instrumentation we'd have lost data and never investigated.

---

## What NOT to say

- Don't soften this into "I almost made a mistake" — I made the call. He flagged it. I was wrong about which problem he was naming.
- Don't oversell the math as if I half-knew — I was confident at the time. The lesson is exactly about overconfidence in math vs missing the observability point.
- Don't pretend I instantly agreed — defended for a day. Real story.

---

## Backup story (if asked for another)

On the fake-follower ML system at GCC I picked 5 features for the ensemble. Early test runs showed one feature — handle-name special-char correlation — was misclassifying real users whose handles had underscores in their names ("rahul_kumar"). I'd weighted it 1.0 when it should have been a soft signal. I rebalanced: that feature now only fires as "fake" when combined with a low Indian-name DB score. False positives dropped meaningfully. The fix was admitting the original weighting was wrong and re-running on labeled samples.
