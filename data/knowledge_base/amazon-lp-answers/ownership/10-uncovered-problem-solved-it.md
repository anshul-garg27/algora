# Q: When was a time you uncovered a problem in your team and solved it?

> **LP**: Ownership
> **Primary story**: `W3 — DiscardPolicy Feedback`
> **Backup story**: `W2 — Shared Library Adoption`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

About three months into the Walmart audit-logging work, I shipped a thread pool config for the `@Async` audit service. Six core threads, ten max, queue capacity 100, and `DiscardPolicy` as the rejection handler. The reasoning: audit failures should never block API responses. If the queue fills, drop the audit event quietly. It went into production. No alerts. Looked clean.

A week later, a senior engineer caught me in the office and said "you're losing audit events." Not "might be." "Are."

### Task

I'd shipped something I thought was safe. He thought it was lossy. Figure out which of us was right, then fix it if it was me. Don't dig in for ego.

### Action

Day one, I defended the choice. `DiscardPolicy` was textbook — it's literally in the Java docs as the way to handle a full queue without back-pressuring the producer. I argued that the queue was bounded so memory was safe, and audit was best-effort anyway.

That night I sat with the queue-depth metrics. I'd added them to the library a week earlier almost as an afterthought. What I saw was not what I expected. During traffic peaks, the queue stayed above 80% for stretches of 5-10 minutes. `DiscardPolicy` was silently dropping events the whole time. No exceptions, no logs, just gone. The senior was right.

So I did three things, not one.

First, I added explicit instrumentation. A Prometheus counter for rejected tasks. A Grafana alert at 80% queue depth. So even if my next decision was wrong, at least we'd see the loss.

Second, I switched the rejection handler from `DiscardPolicy` to `CallerRunsPolicy`. That makes the calling thread — the API thread — run the audit task itself when the queue is full. It slows down API responses under load instead of silently dropping. That's the right backpressure. Audit is best-effort against the network, not best-effort against truth.

Third, I rolled the change as a library version bump and emailed the three teams already using the library with a one-page write-up. "Here's what I shipped, here's why it was lossy, here's what to look for in your metrics." One of the teams found they'd had 0.3% silent drops over the past two weeks.

The harder part was admitting I'd defended it for a full day before checking the numbers. I told my manager that in the next 1:1. He said "good — that's the part that matters."

### Result

Zero silent drops after the deploy. The 80% queue-depth alert has fired twice since for legitimate downstream slowdowns we needed to know about. Three teams updated. The library is now on version 0.0.54 with `CallerRunsPolicy` as the default. I also added a "decision log" section to the library README explaining why we use `CallerRunsPolicy`, so the next engineer doesn't make my mistake.

The thing I'd say I learned: instrumentation isn't optional — it's the difference between a design call and a guess.

---

## Technical depth — if they probe

- **`DiscardPolicy` vs `CallerRunsPolicy`**: Both are `RejectedExecutionHandler` implementations. `DiscardPolicy` silently drops the task. `CallerRunsPolicy` runs it on the submitting thread, which back-pressures the producer. For audit, back-pressure is correct — if the audit service is slow, we'd rather slow API responses than lose compliance data.
- **`AbortPolicy`**: The default. Throws `RejectedExecutionException`. I considered it but rejected — propagating an exception to the API caller for an audit failure is the wrong blast radius. Audit is supporting, not primary.
- **Queue depth metric**: `Gauge` on `ThreadPoolTaskExecutor.getQueueSize() / getQueueCapacity()`. Sampled every 15 seconds. Alert at 80% sustained for 2 minutes.
- **`@Async` thread pool config**: 6 core, 10 max, 100 queue, 60s keep-alive. Sizing came from `(requests/sec × audit latency) × 2`. Roughly 100 req/sec × 0.5s × 2 = 100, but I kept core at 6 because most traffic was well below peak.
- **Why I caught my own bug late**: I'd added the queue-depth metric "for future debugging" and never set an alert threshold. The alert came later in the same PR set, before the rollout to the other two teams. So they never saw silent drops in production — they got the safer default from day one.

---

## Likely follow-ups

**Q: Why did you defend it before checking?**
> Habit, not logic. `DiscardPolicy` was in the Java textbook examples I'd learned from. I treated "this is what the docs show" as evidence. It's a bias I've watched for since.

**Q: How did you tell the three teams using the library?**
> Email with a one-page write-up. Title was honest — "Audit library was losing events under load. Here's the fix and the metrics to watch." Two teams said thanks. The third audited their dashboards and found 0.3% silent drops over two weeks.

**Q: Could you have just tested it before shipping?**
> A load test would have caught it. I'd done functional tests but not load tests on the queue overflow path. After this, every async config I ship gets a load test that explicitly hits queue overflow.

**Q: Was your manager upset?**
> No. He told me "the part that matters is that you changed your mind in 24 hours, not who was right." That stuck with me.

**Q: How is this different from the silent Kafka failure story?**
> The Kafka one was a multi-day debug of someone else's system failing in unexpected combinations. This was me shipping a wrong design and being told within a week. Different shapes. Same root cause — alerting was downstream of the actual failure mode.

---

## What NOT to say

- Don't claim I caught it myself — the senior engineer caught me. Be honest about that.
- Don't say "I was right but I deferred" — I was wrong. Own it.
- Don't blame the Java docs — they're not wrong about what `DiscardPolicy` does; I picked the wrong policy for our context.
- Don't say "I added monitoring everywhere" — be specific: queue depth gauge, rejection counter, 80% alert.

---

## Backup story (if asked for another)

The shared audit library at Walmart. I noticed three teams writing the same 500 lines of audit-logging Spring filter code. Took a week to extract it into a Spring Boot starter JAR. Integration time dropped from two weeks per team to one day. Three teams adopted in month one, eight teams over a quarter. Held weekly office hours and reviewed every integration PR personally.
