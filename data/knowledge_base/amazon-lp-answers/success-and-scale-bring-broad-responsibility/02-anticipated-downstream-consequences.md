# Q: Describe a time you anticipated downstream consequences of a decision.

> **LP**: Success and Scale Bring Broad Responsibility
> **Primary story**: `W3 — DiscardPolicy Silent-Drops Catch`
> **Backup story**: `W7 — DSD 2-of-5 Events Decision`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

During the audit-logging library design, I was about to ship the thread pool config with `DiscardPolicy` as the rejection policy. The pool was 6 core, 10 max, queue of 100. `DiscardPolicy` meant if the queue filled up, the task silently dropped — no exception, no log.

My reasoning was straightforward. Audit is fire-and-forget. If the system is under load, dropping a few audit events is acceptable because the alternative — `AbortPolicy` throwing exceptions back into the request thread — would slow down the real API responses. Cleaner failure mode, I thought.

### Task

Decide between two failure shapes — silent loss under load vs. backpressure that slowed real traffic — and consider what it would mean at the scale the library would run.

### Action

I almost shipped it. The PR was approved, I had my finger on the merge button. Then a teammate on review left a comment: "What happens when 12 services using this library all hit a traffic spike at the same time?"

I sat with that. Did the math. Twelve services, each averaging 100 events/sec, peak 500/sec. If audit-service downstream had a single bad minute — a deploy, a GC pause, anything — every one of those 12 thread pools would back up. Queues fill in seconds. `DiscardPolicy` would silently drop tens of thousands of audit events across the org. Compliance would have a hole the size of the spike.

That was the broader consequence I hadn't thought through. At one service, `DiscardPolicy` is a reasonable trade. At twelve services moving as a fleet, it's a compliance incident waiting for a bad downstream minute.

I went home that night still defending the design. The next morning I changed my mind. I switched to `CallerRunsPolicy` — when the queue fills, the calling thread executes the task itself. The request takes a 10-50ms hit, and that natural slowdown is the backpressure the system needs. Slow requests generate fewer new events, the queue drains, equilibrium returns.

But I went further. I added a Prometheus gauge for queue depth and an alert at 80% capacity. If the system hits 80, I want an engineer to see it before it hits 100. And I added a counter for `CallerRunsPolicy` invocations — if we're in fallback mode, I want to know.

### Result

Two months later there was a real downstream incident — audit-service had a 90-second deploy hiccup. The queues filled across nine services. Every one of them fell into `CallerRunsPolicy` mode. Total API p95 latency rose by about 40ms for the duration. Zero audit events lost. The alert paged the audit-service on-call, they rolled back the deploy, and the pools drained inside 4 minutes.

If I'd shipped `DiscardPolicy`, we'd have lost an estimated 200,000 audit events across 9 services in that window — most of it inventory-status traffic where suppliers later debug failures. We'd have learned about it weeks later in a compliance review.

The teammate's review comment saved a future incident. The broader-consequences thinking only happened because somebody else asked the scaling question.

---

## Technical depth — if they probe

- **Why `CallerRunsPolicy` is the natural-backpressure choice**: It feeds slowness back to the caller, which slows the rate of new events. It's a self-regulating feedback loop. `AbortPolicy` throws, `DiscardPolicy` loses, `DiscardOldestPolicy` loses different work. CallerRuns is the only one that throttles the source.
- **The pool sizing math**: 6 core handles average load (~100 req/sec at our pool service). 10 max handles 1.5x spikes. Queue of 100 absorbs short bursts. Above that we want backpressure, not unbounded growth.
- **Why a gauge AND a counter**: Gauge tells me the current state (queue at 80%). Counter tells me the historical pattern (we fell into fallback 14 times this week). Both are needed.
- **Where this lives**: `AuditLogAsyncConfig.java` in the common library. `executor.setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy())`. One line, big consequence.

---

## Likely follow-ups

**Q: How did you change your mind overnight?**
> I ran the load math on a napkin. 12 services × 500 events/sec peak × 60 seconds of downstream slowness = 360,000 events. Even at 1% drop rate that's 3,600 events. At 100% drop because the queue was full, it was unbounded. Once I saw the number, I couldn't unsee it.

**Q: What if `CallerRunsPolicy` slows down a critical path too much?**
> The 40ms hit during the real incident was acceptable. If it ever became unacceptable, the right answer would be more thread-pool capacity, not silent drops. Capacity is a cost question; data loss is a compliance question.

**Q: Could you have just made the queue bigger?**
> A bigger queue delays the question, doesn't answer it. At some point you fill any queue and the rejection policy fires. The policy is what you're really choosing.

**Q: What's the broader lesson for shared infra?**
> Every default in a shared library is being chosen for every team that adopts it. The right question isn't "what's good for one service" — it's "what's the failure mode at fleet scale."

---

## What NOT to say

- Don't claim you got this right on the first try — the teammate's comment is what unlocked it. Credit them.
- Don't oversell — say "approximately 200K events would have been lost." It's an estimate, not a measured number.
- Don't make `CallerRunsPolicy` sound clever. It's a 30-year-old JDK pattern. The insight is the scaling question, not the mechanism.

---

## Backup story (if asked for another)

For W7, when I designed the DSD push-notification system, the team wanted to fire 5 different event types per shipment. I dug into the receiving-associate workflow and found that 3 of those events were redundant — associates only acted on 2. Firing all 5 would have flooded the notification subsystem at scale (8K stores × peak receiving windows) and dulled the signal. I anticipated the noise consequence and shipped only the 2 actionable events. The downstream win: notification open rates stayed at 97% instead of degrading to where stores started ignoring them.
