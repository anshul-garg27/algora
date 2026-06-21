# Q: Tell me about a time when you broke a production system or handled a high-severity incident while on-call. What steps did you take to resolve it?

> **LP**: Ownership
> **Primary story**: `W1 — Silent Kafka Failure`
> **Backup story**: `W3 — DiscardPolicy Feedback`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

About six weeks after we launched the GCS sink in production, I was checking dashboards on a Wednesday morning and something was off. The Kafka topic had millions of messages backing up. But the dashboards were green. Zero alerts. Our compliance audit data — the stuff regulators ask for — was quietly disappearing.

### Task

I owned the Kafka audit logging pipeline. Find why it had gone silent, fix it, make sure we didn't lose more data, and figure out why the alerting itself had failed.

### Action

Day 1 was the obvious checks. Kafka Connect running? Yes. Messages in topic? Yes, piling up. So the problem was between consumption and the GCS write. That narrowed it.

Day 2 I turned on DEBUG logging. Found a `NullPointerException` in the SMT filter — our Single Message Transform that checked the `wm-site-id` header. Legacy producers weren't sending it. `errors.tolerance` was set to `none`, so one bad message killed the whole connector. I shipped PR #35 the same day — try-catch with a permissive fallback (no header defaults to US bucket).

Day 3 the backlog kept building. Poll timeouts. The default `max.poll.interval.ms` was 5 minutes; our GCS writes for large batches were slower. Tuned the consumer configs.

Day 4 was the worst. KEDA was autoscaling on consumer lag. More lag → scale up → rebalance → no consumption during rebalance → more lag → scale up again. Feedback loop. PR #42 ripped out KEDA and moved to CPU-based HPA.

Day 5 we hit JVM heap exhaustion on large batch Avro deserialization. Bumped heap from 512MB to 2GB initially, then to 7GB with G1GC after I ran `jmap -histo:live` and saw the real footprint.

The whole time I refused to declare it fixed after each individual patch. Kafka was retaining the messages, so we hadn't lost anything yet. I'd rather take five days and find every cause than declare victory on day two.

### Result

Zero data loss across the entire week — Kafka's retention saved us. Backlog cleared in 4 hours after the last fix. I wrote up the whole thing as a runbook, and two other teams used it later for their own connector failures. Honest takeaway: Kafka Connect's error tolerance can hide problems for weeks. Now every connector I touch ships with queue-depth and processing-lag metrics in the same PR.

---

## Technical depth — if they probe

- **SMT NullPointerException (PR #35)**: `header.value().toString()` blew up when the header was missing. Added explicit null guards and a try-catch with default-US behaviour. Also added Prometheus counters for filter exceptions so silent drops would show up next time.
- **KEDA rebalance storm (PR #42)**: Scaling Kafka consumers on lag triggers consumer-group rebalances. During a rebalance no messages are consumed, which increases lag, which triggers more scaling. The fix was structural — never autoscale Kafka consumers on lag. CPU-based HPA only. Also raised `heartbeat.interval.ms` and `session.timeout.ms` to 10 minutes.
- **JVM heap and G1GC (PRs #57, #61)**: Default 512MB couldn't hold our `flush.size` batch of 10M records during Avro deserialization. Settled on `-Xms5g -Xmx7g` with G1GC tuned for low pause times.
- **The 413 cross-check**: Separately, when I cross-referenced API Proxy request counts against Hive record counts during validation, the numbers didn't match — losing 40-130K records a day to a 1MB gateway payload limit. Bumped `APIPROXY_QOS_REQUEST_PAYLOAD_SIZE` to 2MB. Numbers matched after that.

---

## Likely follow-ups

**Q: Why didn't the alerts fire?**
> Two reasons. The connector wasn't crashing — it was failing on one message and silently dropping. And our alerting watched the Kafka publisher side, not the consumer/GCS side. Inputs were fine, outputs weren't. Now I alert on every tier boundary.

**Q: Why five days? Couldn't you find it all on day one?**
> Each fix unmasked the next problem. The NPE was hiding the poll timeout. The poll timeout was hiding KEDA. KEDA was hiding the heap issue. Distributed systems fail in combinations, not in a single visible spot.

**Q: What did you do post-mortem?**
> Wrote the runbook. Added queue-depth alerts. Added a synthetic check that compares input count to output count every hour. And I made the SMT permissive by default — fail-open on missing headers, never fail-closed.

**Q: Was there pressure to rush a fix on day one?**
> Yes. My manager asked on day two if a quick patch would do. I said the NPE patch was already in but I wasn't confident it was the only cause. I'd rather take more days and not have to do this again.

**Q: Have you used this learning since?**
> Yes — every Kafka-related PR now includes input/output count parity in the test plan. We caught the 413 gateway issue exactly that way.

---

## What NOT to say

- Don't blame the previous developer — the NPE was inherited code but the silent-failure design was a team gap.
- Don't claim zero data loss without explaining WHY (Kafka retention). The interviewer knows it could have gone the other way.
- Don't make it sound clean — it was a five-day grind with multiple wrong hypotheses on the way.
- Don't say "I added monitoring everywhere" — be specific: queue depth, filter exceptions, tier-boundary count parity.

---

## Backup story (if asked for another)

W3 — the DiscardPolicy story. I'd built a thread pool with `DiscardPolicy` to handle backpressure. A senior engineer pushed back that I was silently dropping audit events. I defended it for a day, then sat with the queue-depth numbers and realised he was right. Shipped instrumentation first, then switched to `CallerRunsPolicy` so producers feel the slowdown instead of losing data.
