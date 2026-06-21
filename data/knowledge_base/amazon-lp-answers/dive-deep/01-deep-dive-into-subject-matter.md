# Q: Tell me about a time when you had to deep dive into subject matter.

> **LP**: Dive Deep
> **Primary story**: `W1 — Silent Kafka Failure`
> **Backup story**: `G1 — ClickHouse Migration`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

About six weeks after our Kafka audit pipeline went live, I opened the GCS bucket on a Tuesday morning and the latest file was three hours old. No alerts had fired. Dashboards were green. We were quietly losing compliance-critical audit data for Pepsi, Coca-Cola, and the other suppliers.

### Task

I was the system owner. I had to find out why the pipeline looked healthy from the outside but was failing on the inside — and I had to do it without making things worse.

### Action

Day one I checked the obvious. Kafka Connect was up. Messages were piling up in the topic, millions of them. So the break was somewhere between the consumer and the GCS write.

Day two I turned DEBUG logging on. Found a NullPointerException in our SMT filter — legacy traffic didn't carry the `wm-site-id` header, and our code did `.toString()` on null. PR #35 added a try-catch and made the filter permissive. I thought I was done.

I wasn't. Day three the lag was still climbing. Consumer poll timeouts. The default `max.poll.interval.ms` of 5 minutes wasn't enough because GCS writes for large Avro batches were taking longer. I tuned the consumer configs.

Day four was the strange one. I correlated the lag chart with our Kubernetes events and saw the loop. KEDA was scaling on consumer lag. Scale up triggered a rebalance. Rebalance meant zero consumption. Lag climbed. KEDA scaled again. The dashboard wasn't lying — KEDA was loop-clicking itself. PR #42 removed the KEDA Kafka trigger and switched to CPU-based HPA.

Day five was JVM heap. `jmap -histo:live` showed Avro deserialization buffers eating the 512MB default. PR #57 went to 2GB. Still tight. PR #61 the next day went to `-Xms5g -Xmx7g` with G1GC tuned for low pause. The OOM kills stopped.

### Result

Zero data loss the whole time — Kafka retained everything. Backlog cleared in four hours after the last fix. I wrote a runbook from those five days, and two other teams used it within the next month. Honestly, the lesson was that one bug almost always hides three more.

---

## Technical depth — if they probe

- **Why DEBUG before metrics**: We didn't have Prometheus counters on filter exceptions. The error was being swallowed by Kafka Connect's `errors.tolerance` setting. DEBUG was the fastest path to seeing the NPE.
- **KEDA feedback loop**: Scaling Kafka consumers on lag is a known anti-pattern. Each new consumer triggers a group rebalance. During rebalance, nobody consumes, so lag climbs further. CPU-based HPA breaks the loop.
- **7GB heap math**: At `flush.size: 10000000` and 3KB Avro records, in-memory batch can exceed 1GB before serialization. Double for deserialization overhead, plus G1GC headroom — 7GB landed safely.
- **PR #35 fix pattern**: The filter now defaults to the US bucket if the header is missing. Permissive on read, strict on write — same pattern I'd seen in our Spring Security config.

---

## Likely follow-ups

**Q: Why didn't you have a dashboard catching this?**
> We had Kafka Connect health metrics, but `errors.tolerance` was set to "none" originally, meaning one bad message killed the whole task. After the fix I added a Prometheus counter on filter exceptions and an alert on GCS write age.

**Q: What if Day 4 fix made Day 5 worse?**
> It actually did — once consumption restarted, the heap pressure was real. That's why the runbook now says "after each fix, watch for the next bottleneck to surface." Distributed systems fail in compound ways.

**Q: How did you know to look at KEDA on Day 4?**
> I overlaid the Kubernetes pod count chart on the consumer lag chart. The scale-up events lined up exactly with the lag spikes. Once you see the pattern visually, it's obvious.

**Q: Would you do anything differently?**
> Add OpenTelemetry from day one. We were debugging blind because traces didn't span the Kafka boundary. Also — start with `errors.tolerance: all` plus an alerting counter, not `none`.

---

## What NOT to say

- Don't say "I solved it in one day" — the five-day arc is the point.
- Don't say "KEDA is bad" — it's fine for stateless services, just not for consumer groups.
- Don't skip the PR numbers (#35, #42, #57, #61). They're the receipts.

---

## Backup story (if asked for another)

At GCC, PostgreSQL was choking on 10M+ log writes per day. Write latency went from 5ms to 500ms. I dug into the access patterns and found 99% of writes were append-only time-series. I built a RabbitMQ → Go buffered sinker → ClickHouse pipeline with 1000-record batches. Query time dropped from 30s to 12s; storage shrank 5x. The deep dive was understanding why row-oriented MVCC was the wrong shape for the workload.
