# Q: Tell me about a time when you faced a roadblock.

> **LP**: Deliver Results / Dive Deep (hybrid)
> **Primary story**: `W1 — Silent Kafka Failure`
> **Backup story**: `W8 — DC Inventory Search API`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

May 2025. About six weeks after the Kafka audit logging system went live, I happened to glance at the GCS bucket count and noticed it had flatlined. No alerts. No errors in dashboards. The system looked healthy from every angle except the one that mattered — data was no longer landing.

### Task

Find the root cause, stop the data loss, and don't tell suppliers we lost their audit trail. Kafka was retaining everything, so I had a buffer. But the backlog was growing by the hour.

### Action

Day one, I checked the obvious. Connect workers running, topic full, consumers polling. The break was somewhere between consumption and the GCS write.

Day two, I turned on DEBUG logging. NullPointerException in the SMT filter. Legacy records didn't have the `wm-site-id` header we expected. One bad record per batch was killing the whole batch because `errors.tolerance` was `none`. I added a try-catch with permissive fallback — no header means US bucket — and shipped PR #35.

Day three, the buckets were still empty. New symptom: consumer poll timeouts. Default `max.poll.interval.ms` was five minutes, but our large GCS writes were running longer. Tuned the consumer configs and pushed again.

Day four, this is when I got stuck. The lag would shrink, then explode. I sat with the Kubernetes events for an hour and saw the pattern. KEDA was scaling on consumer lag. More lag, more pods, more rebalances, less throughput, more lag. A textbook feedback loop. I disabled KEDA in PR #42 and switched to CPU-based HPA.

Day five, JVM heap exhaustion on large Avro batches. Default 512MB couldn't handle our `flush.size` of 10M records. I jumped the heap to 7GB with G1GC tuning in PR #57.

### Result

Zero data loss because Kafka held everything. Backlog cleared in four hours once the fixes stacked. I wrote a runbook from the daily notes, and it's been used twice since by other teams. The bigger thing for me — I now treat "errors.tolerance: none" as the default and add a dropped-record counter on day one.

---

## Technical depth — if they probe

- **Why KEDA-on-lag is bad for Kafka consumers**: Scaling triggers a consumer group rebalance. During rebalance, no messages are consumed. Lag grows. KEDA scales more. Use CPU or message-rate-per-pod, never lag.
- **`errors.tolerance: all` vs `none`**: `none` stops the connector on first bad record — loud failure. `all` silently drops bad records — quiet failure. Pick `all` only with a dropped-record metric in place.
- **JVM tuning (PR #57)**: `-Xms5g -Xmx7g`, G1GC, MaxGCPauseMillis=200. Avro deserialization for 10M-record batches is allocation-heavy.
- **Why Kafka saved us**: 7-day retention on the topic. Even with no consumers, no message was lost.

---

## Likely follow-ups

**Q: Why didn't monitoring catch this?**
> We had "is it running" metrics, not "is it processing correctly." After this, I added a counter for filtered records, a counter for rejected SMT records, and consumer lag alerts at 100 and 500 messages. Silent failure is now my first thing to instrument on any new pipeline.

**Q: Were you the only one debugging?**
> I led it, but I pulled in my manager and a platform engineer for the KEDA piece because that touched infra config. I owned the timeline and the comms to the team — that part wasn't shared.

**Q: What was the moment you almost gave up?**
> Day four morning. I'd shipped two fixes and the dashboard was still wrong. I almost rolled back to Splunk for a week. Then I sat with the Kubernetes events and the pattern fell out in twenty minutes. Sometimes the breakthrough is just one less tab open.

**Q: How did you communicate this to your team?**
> Daily standup updates with the hypothesis, the test, and the result. I kept it boring — no panic. Slack thread with timestamps so leadership could read it without asking me.

---

## What NOT to say

- "We figured it out" — own it. I led the debugging.
- "Kafka's at fault" — Kafka was the only thing that worked. The roadblock was our config and our blind spots.
- Don't gloss over day four. The KEDA loop is the part interviewers love to probe.

---

## Backup story (if asked for another)

The DC Inventory Search API had a different kind of roadblock — the team that owned the inventory data, EI, had no public docs and no capacity to build for me. I reverse-engineered three of their endpoints with Charles Proxy and Postman, validated against production data, and built the three-stage pipeline myself. Shipped in four weeks instead of the twelve-week estimate.
