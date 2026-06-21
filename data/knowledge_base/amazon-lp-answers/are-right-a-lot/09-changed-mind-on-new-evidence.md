# Q: Describe a time you changed your mind based on new evidence.

> **LP**: Are Right, A Lot
> **Primary story**: `W3 — Overnight reconsideration of DiscardPolicy`
> **Backup story**: `G4 — Single-DB plan flipped to dual-DB after benchmarks`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

While building the shared audit-logging library at Walmart, I sized the async thread pool — 6 core, 10 max, 100 queue — and picked `DiscardPolicy` for the rejection handler. `DiscardPolicy` silently drops the task when the queue is full. I deliberately chose it over `AbortPolicy` (which throws) because I didn't want audit failures to bubble exceptions into the API response path. My reasoning: audit is best-effort, the API contract with suppliers is what matters, dropping silently keeps the API clean.

### Task

A senior engineer reviewed the design and said: "you'll lose audit data and you won't know." I had to decide whether to defend my call or change it.

### Action

My first reaction was to defend. I had numbers. 100 requests per second per pod × 50ms per audit = 5 threads in flight steady state. Queue of 100 = 10 seconds of buffer at peak. The queue would basically never fill. I wrote up the math and sent it back to him. I was confident.

He didn't reply with a counter-math. He just said: "rare isn't the point. invisible is the point."

I went home that evening still thinking I was right. Then I sat with what he'd actually said.

He wasn't arguing the queue would fill often. He was arguing that when it does — once a quarter, once a year, doesn't matter — we'd have no way to know. At 2 million events a day, even 0.01 percent silent loss is 200 events I can't see. Audit data is the thing suppliers are about to start querying. If we silently drop events for one supplier during one outage, they'd see gaps in their dashboards and we'd have no way to tell them what happened.

I'd been arguing about frequency. He'd been arguing about observability. Those are different problems with the same root word — "silent."

The next morning I came in and told him in our 1:1: "You were right. The math says drops are rare; the problem is when they happen we'd never notice. Let me fix it."

I added three things. A Prometheus counter `audit_log_rejected_tasks_total` that increments on every drop. A WARN log at 80 percent queue capacity with pool stats. A custom `RejectedExecutionHandler` that records the dropped task's request ID so we can correlate with downstream slowdowns.

### Result

That WARN-at-80-percent alarm has fired exactly once in production. It caught a downstream slowdown on `audit-api-logs-srv` — a misconfigured Kafka producer was running slow, the audit thread pool was filling. We caught it before the queue actually overflowed. Without the instrumentation we'd have silently lost events and never investigated.

The change shipped in the next library release. The senior engineer reviewed it, approved.

The real result was the habit I took from it. When I'm certain and someone with more experience disagrees, I sit with the disagreement overnight before defending. Sometimes I still defend the next morning. Often I find they saw something I missed — usually because they were arguing about a slightly different problem than the one I'd convinced myself we were debating. The trick was separating his actual concern (no observability) from my version of it (will the queue fill often).

I also learned to say "you were right" plainly. Burying it in "yeah I see your point, here's a compromise" weakens the working relationship. Direct concession strengthens it.

---

## Technical depth — if they probe

- **`DiscardPolicy` vs `AbortPolicy`**: `AbortPolicy` throws `RejectedExecutionException`. `DiscardPolicy` silently drops. The right shape: silent drops + observability, not one or the other.
- **The math I cited**: 100 req/sec per pod × 50ms per audit = 5 threads steady state. Queue of 100 = ~10 seconds of buffer.
- **What I added after changing my mind**: `audit_log_rejected_tasks_total` Prometheus counter, WARN log at 80 percent (`queue.size() > queue.remainingCapacity() * 4`), custom handler logging request ID of every drop.
- **What the alarm caught**: a Kafka producer config issue on `audit-api-logs-srv` causing slow downstream HTTP responses. Audit thread pool started filling. WARN fired at 80 percent. Fixed before any drops.
- **The general rule**: silent failures are fine when monitored, fatal when invisible.

---

## Likely follow-ups

**Q: How long did it take you to change your mind?**
> About a day. I defended in the review, sat with it overnight, came back in the morning and conceded.

**Q: What was the trigger that flipped it?**
> Re-reading his actual sentence. I'd been arguing my version of his concern (queue fills often), not his version (we'd never know if it did). Separating "rare" from "invisible" was the unlock.

**Q: Did you tell him you'd been wrong, directly?**
> Yes. "You were right, I'm fixing it." Strengthened the relationship. He asks me to review his designs now.

**Q: Has this come up again?**
> Yes — that's why I made it a habit. Anytime someone senior disagrees and I'm confident, I sleep on it. About half the time I find I was missing something. The other half I defend with the new clarity.

**Q: What if the disagreement was about a guess, not a measurable thing?**
> Same process. Sit with it. The point isn't always "they were right" — it's "did I understand their actual concern." Sometimes you defend because you've now understood it and still disagree. That's a stronger defence.

---

## What NOT to say

- Don't soften it into "I refined the design" — I was wrong on a specific thing and changed my mind. The plain story is stronger.
- Don't pretend it was instant — I defended for a day. Real story.
- Don't oversell — the alarm catching one production incident is one data point. The general lesson is about observability for rare failures, not "I prevented a Sev-1."

---

## Backup story (if asked for another)

At GCC I originally planned single-Postgres for the Coffee API. Two weeks into design I ran a representative benchmark on our heaviest queries — leaderboard top-1000 (28 seconds on Postgres, 1.8 on ClickHouse) and 30-day creator time-series (31 seconds vs 1.2). 15x and 25x. The benchmark changed my mind. I pivoted the design to dual-DB — Postgres for OLTP, ClickHouse for OLAP — and went back to the CTO with the numbers. That benchmark-driven flip shipped and ran for years.
