# Q: Tell me about a difficult situation that required you to deep dive.

> **LP**: Dive Deep
> **Primary story**: `W1 — Silent Kafka Failure`
> **Backup story**: `G1 — ClickHouse Migration`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

It was a Tuesday morning in May 2025. The audit pipeline I'd shipped six weeks earlier had stopped writing to GCS overnight. My dashboards showed green across the board. Suppliers couldn't query data that didn't exist. The data was compliance-critical — Pepsi, Coca-Cola, Unilever were depending on it for their own debugging workflows.

### Task

Find out why the system looked fine and was broken. Stop the bleed before suppliers noticed. Make sure this shape of failure couldn't repeat.

### Action

I started at the end. GCS bucket files were three hours old. The Kafka topic had millions of unconsumed messages. That ruled out the producer side and narrowed me to the consumer-and-sink path.

DEBUG logs gave me the first cause — a NullPointerException in the SMT filter when legacy traffic arrived without a `wm-site-id` header. The filter called `.toString()` on null and the entire Kafka Connect task aborted because `errors.tolerance` was "none." PR #35 added a try-catch and made the filter permissive.

But lag kept climbing after the fix. Day three I tracked it to consumer poll timeouts — the default `max.poll.interval.ms` of 5 minutes was too short for our GCS write latency on large batches.

Day four was the one I almost missed. I overlaid the Kubernetes pod-count chart on the consumer lag chart and noticed they were in lockstep. Lag climbed, KEDA scaled the pod count, lag climbed more, KEDA scaled again. The feedback loop was that KEDA was scaling on consumer-group lag, which triggers a rebalance, which means zero consumption during the rebalance window. PR #42 removed the KEDA Kafka trigger and switched to CPU-based HPA.

Day five was heap exhaustion. `jmap -histo:live` showed Avro deserialization buffers chewing up the 512MB default. PRs #57 and #61 took the JVM to `-Xms5g -Xmx7g` with G1GC tuned for low pause.

After all that I added cross-tier record counters and an alert on tier-to-tier divergence over 0.1%. That alert has caught two real losses in the months since, both inside 15 minutes.

### Result

Zero data loss the whole arc — Kafka durability saved us. Backlog cleared in four hours. The runbook I wrote afterwards has been used by two other teams.

The thing I learned wasn't about Kafka specifically. It was that "looks green" is a property of what you chose to measure. If you don't measure tier-to-tier consistency, you won't see silent loss. I now build that in from day one on any pipeline.

---

## Technical depth — if they probe

- **Why DEBUG, not metrics**: We didn't have a filter-exception counter. Adding the metric would have been faster long-term but slower right now. DEBUG was the quickest path to "what's the actual exception."
- **Why "errors.tolerance: none" was wrong**: With it set to none, one bad message kills the whole task. Better default is "all" plus a counter that alerts when the count moves. Bad data shouldn't kill the system.
- **Why KEDA on lag is dangerous**: Scaling consumers triggers consumer-group rebalance. During rebalance, no one consumes. Lag climbs. KEDA scales more. The loop never converges. CPU-based HPA breaks the coupling between scaling and consumer-group membership.
- **Why I added the cross-tier counter**: Because each tier individually said "I'm healthy." The bug was in the seams. The only way to catch seam bugs is to invariant-check the seams.

---

## Likely follow-ups

**Q: At what point did you realise this wasn't a one-bug problem?**
> Day 3. I'd shipped the NPE fix and lag was still climbing. That's when I knew the system had multiple compounding causes, not one root cause. Distributed-system bugs almost always stack.

**Q: Did you consider rolling back?**
> Briefly on Day 1. But rollback meant losing six weeks of supplier onboarding work, and Kafka was retaining everything anyway. The cost of staying forward was a few more days of debugging; the cost of rollback was much larger. I chose forward.

**Q: What's the most uncomfortable part of a five-day debug?**
> Telling the manager on Day 3 that I had a theory but no fix yet. The instinct is to fake confidence. I learned to just say "this is the next thing I'm checking and here's what I'd expect to see."

**Q: How would OpenTelemetry have changed this?**
> Day 4 becomes Day 1. The KEDA loop would be obvious as overlapping rebalance spans during scale-up events. I'm building OTel into all new pipelines.

---

## What NOT to say

- Don't say "I solved this in a day." The five days are the story.
- Don't blame KEDA, Kafka Connect, or any specific tool. They're fine — the seams were not measured.
- Don't oversell the runbook. It's a paragraph per failure mode, not a thesis.

---

## Backup story (if asked for another)

The G1 ClickHouse migration was the same shape at a different scale — a slow-burning difficulty rather than an acute one. PostgreSQL write latency had been climbing for months, nobody owned the analytics workload, and three different teams blamed three different things. I dug into the query patterns, found that 99% of reads were time-range aggregations on metrics columns, and built three POCs side by side. ClickHouse won on query speed, compression, and cost. Dual-write phase for two weeks, less than 0.02% drift, then we cut over. 30s queries became 12s, storage shrank 5x.
