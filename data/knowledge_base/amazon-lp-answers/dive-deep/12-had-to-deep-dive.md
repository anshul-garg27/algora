# Q: Tell me about a time you had to deep dive.

> **LP**: Dive Deep
> **Primary story**: `W1 — Silent Kafka Failure`
> **Backup story**: `G1 — ClickHouse Migration`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Late Tuesday evening, around 11pm, I was about to log off when the lag chart on the Kafka audit pipeline caught my eye — climbing steadily, no alerts firing. The pipeline had been live six weeks, ingesting around 2M events/day for supplier audit logs. Compliance-critical data. I opened the GCS bucket and the latest file was three hours stale. Something was eating records and nothing was screaming about it.

### Task

Find out what was breaking the pipeline between consumer and sink, without losing more data and without taking the rest of the system down.

### Action

I worked it from the back. GCS bucket files were stale, Kafka topic counts were healthy. So the break was inside Kafka Connect or its sink.

DEBUG logs the first night showed a NullPointerException on the SMT filter for messages missing the `wm-site-id` header. Legacy upstream traffic didn't carry that header. PR #35 added a try-catch and defaulted unknown messages to the US bucket. I ran it through Flagger canary at 10% — looked good — promoted to 100%.

The next morning, the lag was still climbing. Same flavour. I went to consumer poll settings and found that `max.poll.interval.ms` defaulted to 5 minutes. Our GCS writes for big Avro batches were taking longer. Tuned it to 10 minutes.

Day three I overlaid the pod-count chart on the lag chart and the picture made me close my laptop and pace. KEDA was scaling on consumer-group lag. Each scale-up triggered a rebalance. During rebalance, nothing consumed. Lag climbed. KEDA scaled again. The dashboard wasn't lying — KEDA was the bug. PR #42 removed the KEDA Kafka trigger and switched to CPU-based HPA.

Day four-and-five was JVM heap. `jmap -histo:live` on the running connector showed Avro deserialization buffers occupying close to the 512MB heap limit. PR #57 went to 2GB. Still tight under flush.size of 10M records. PR #61 the next day took us to `-Xms5g -Xmx7g` with G1GC tuned for short pauses. The OOM kills stopped.

### Result

Five days, four root causes, zero data loss. Kafka durability meant every message was retained on disk while I was debugging — the four-hour backlog flushed in four hours after the last fix went live.

I wrote up the debug arc as a runbook with one paragraph per failure mode and the metric you'd check first. Two other teams used it inside a month. And I added a Prometheus counter on filter exceptions plus an alert on GCS-write-age over 30 minutes, so the next silent failure of this shape would page someone in 15 minutes.

The thing that stuck — when a distributed system fails, one root cause usually hides two more underneath. Each fix moves the bottleneck. The dive isn't done until the lag chart goes flat AND stays flat for a day.

---

## Technical depth — if they probe

- **Why DEBUG before metrics**: We didn't have a counter on filter exceptions yet — the metric didn't exist. DEBUG was the fastest way to see the actual exception. I added the counter afterwards.
- **Why `errors.tolerance: none` was wrong**: One bad message kills the whole connector task. Better default is "all" plus an alert on the exception counter. Bad data shouldn't take down the system.
- **Why KEDA on lag is a known anti-pattern**: Scaling consumers triggers consumer-group rebalance. Rebalance halts consumption. Lag climbs. KEDA scales more. The loop doesn't converge.
- **Why 7GB heap, not just 2GB**: At `flush.size: 10000000` and 3KB Avro records, in-memory batch can hit 1GB before serialization. Double for deserialization overhead. G1GC needs headroom. 7GB held steady.

---

## Likely follow-ups

**Q: How did you decide to keep digging after Day 2?**
> The lag chart told me. After the NPE fix went live, lag stayed elevated. If my fix had been complete, the chart would have turned. The data was honest even though the dashboard was misleading.

**Q: What if you'd been wrong about KEDA on Day 4?**
> The PR was reversible. KEDA configs are YAML — re-enable in two minutes. I'd already convinced myself with the pod-count-vs-lag overlay, but I kept the rollback path open until 24 hours of clean data confirmed it.

**Q: Did you sleep?**
> Not well. But the discipline that kept me sane was writing down what I'd checked and what I'd ruled out, so I wasn't re-litigating yesterday's questions at 2am.

**Q: What does this look like with OTel?**
> Day 4 becomes Day 1. The KEDA loop shows up as overlapping rebalance spans during scale events. The NPE shows up as a span exception. We had logs and metrics but no traces; that gap cost us four days.

---

## What NOT to say

- Don't say "I should have caught this earlier." Six weeks of production with no signal isn't your fault — it's the system's fault, and you fixed the system.
- Don't blame KEDA or Kafka Connect. They're fine for other use cases. Blame the missing tier-to-tier invariant.
- Don't oversell — say "I wrote a runbook," not "I built a new debugging methodology."

---

## Backup story (if asked for another)

The G1 ClickHouse migration was a longer, less acute dive. PostgreSQL write latency had been climbing for months and the analytics queries were unusable. I dug into the query patterns and found 99% of reads were time-range aggregations on metrics columns — wrong shape for row storage. Three POCs, benchmarked side by side, ClickHouse won. Dual-write phase, less than 0.02% drift, then we cut over. 30s queries became 12s, storage shrank 5x, infrastructure cost dropped 30%. The dive was choosing the right tool, not tuning the wrong one.
