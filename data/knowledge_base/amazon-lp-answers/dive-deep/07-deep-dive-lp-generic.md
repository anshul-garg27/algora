# Q: Questions based on the 'Deep Dive' leadership principle.

> **LP**: Dive Deep
> **Primary story**: `W1 — Silent Kafka Failure`
> **Backup story**: `G1 — ClickHouse Migration`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Six weeks after launch, the audit pipeline I owned was failing without saying so. GCS bucket files were three hours stale. Kafka had millions of unconsumed messages. None of the dashboards I'd built were alarming. The audit data was compliance-critical and suppliers couldn't query what wasn't there.

### Task

Find the actual cause, not the surface symptom. And do it without breaking the parts that were still working.

### Action

The first thing I did was resist the urge to redeploy. The instinct was "bounce the connector and see if it recovers" — but if I lost the in-memory state I'd lose the breadcrumbs. So I left it running and read the logs.

The trail led me through four layers before I hit the bottom.

Layer one: a NullPointerException in the SMT filter on records without a `wm-site-id` header. One bad message had stalled the connector because `errors.tolerance` was set to "none." PR #35 added a try-catch and made the filter default to the US bucket.

Layer two: consumer poll timeouts. `max.poll.interval.ms` defaulted to 5 minutes but our GCS batch writes were taking longer. Tuned to 10 minutes.

Layer three was the one that took me longest. I overlaid the pod-count chart on the lag chart and saw KEDA was loop-clicking itself — scale up triggered rebalance, rebalance halted consumption, lag climbed, KEDA scaled again. The loop never broke. PR #42 removed KEDA's Kafka trigger and moved to CPU-based HPA.

Layer four: heap exhaustion. `jmap -histo:live` showed Avro deserialization buffers eating 512MB. PR #57 went to 2GB. Still tight under flush.size of 10M records. PR #61 went to `-Xms5g -Xmx7g` with G1GC tuned for low pause. That held.

### Result

Five days. Four root causes. Zero data loss the whole time because Kafka retained everything. Backlog cleared in four hours after the last fix. I wrote up the debug arc into a runbook that two other teams used over the next month.

The lesson that stuck with me wasn't about Kafka. It was that distributed systems fail in compound ways — fix one cause and the next one underneath reveals itself. If I'd shipped the NPE fix on Day 2 and walked away, the KEDA loop would have eaten us alive a week later.

---

## Technical depth — if they probe

- **Why I left the connector running**: To preserve the in-memory state for DEBUG-level introspection. Kafka offsets were durable on disk, so I wasn't risking re-processing. A redeploy would have given me a clean log with no symptoms.
- **Why KEDA's Kafka trigger is dangerous**: It scales on consumer-group lag. Each new consumer joins a rebalance. During rebalance, nothing consumes. Lag climbs, KEDA scales more, more rebalances. CPU-based HPA breaks the loop because CPU is independent of consumer-group membership.
- **Why 7GB heap**: At `flush.size: 10000000` and 3KB Avro records, the in-memory batch can exceed 1GB before serialization. Double for deserialization. Plus G1GC needs headroom. 7GB landed safely.
- **What I added afterwards**: A Prometheus counter for filter exceptions, an alert on GCS-write-age over 30 minutes, and a runbook section per failure mode. The next silent failure has a documented playbook.

---

## Likely follow-ups

**Q: How did you not get tunnel vision after the NPE fix?**
> The lag chart kept rising even after PR #35 went live. The data told me the fix was incomplete. I'd rather trust the metric than trust my code.

**Q: What if you'd had OpenTelemetry from day one?**
> Day 4 would have been Day 1. The KEDA loop would have been obvious in a span graph — rebalance events as spans, lag climbing during each one. I'm adding OTel to all new pipelines now.

**Q: Why "DEBUG logs first" instead of metrics first?**
> Because the metric we needed didn't exist yet — filter exceptions weren't counted. DEBUG was the fastest path to "see what's actually happening." Then I added the metric so next time I wouldn't need DEBUG.

**Q: What's the hardest part of a multi-layer debug?**
> Honestly, knowing when you're done. Each fix moves the bottleneck. You have to keep watching for the next one to surface and resist the urge to declare victory after the first green graph.

---

## What NOT to say

- Don't say "I fixed it in one day." The five-day arc is the substance.
- Don't say "the dashboards were lying" — say "the dashboards weren't measuring the right thing."
- Don't gloss over the runbook. The artifact that survived the debug is the leadership signal.

---

## Backup story (if asked for another)

For G1, the ClickHouse migration, the deep dive was understanding why PostgreSQL was wrong for the workload. Write latency had climbed from 5ms to 500ms at 10M+ logs/day. The temptation was to add indexes or partitioning. Instead I dug into the access pattern: 99% of queries were time-range aggregations on metrics columns. That's a columnar shape, not a row shape. I built three POCs — partitioned PG, TimescaleDB, ClickHouse — benchmarked them with real query plans, and ClickHouse won on every axis. 2.5x query speedup, 5x compression, 30% cost cut. The dive was choosing the right tool, not tuning the wrong one.
