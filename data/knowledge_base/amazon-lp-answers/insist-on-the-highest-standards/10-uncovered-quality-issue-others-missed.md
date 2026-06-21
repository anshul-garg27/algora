# Q: Tell me about a time you uncovered a quality issue others missed.

> **LP**: Insist on the Highest Standards
> **Primary story**: `W1 — 5-day Kafka silent-failure dig`
> **Backup story**: `W3 — DiscardPolicy silent drops via instrumentation`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

May 2025. Six weeks after we launched the GCS sink for our Kafka audit pipeline. I was looking at the dashboards on a Wednesday and the GCS bucket counts had flatlined. Not zero. Just not growing. The Kafka topic was healthy. Dashboards green. Connector pods reporting healthy.

We were losing compliance-critical audit data and nobody knew. Suppliers needed this data for API debugging — silent loss meant compliance gaps we couldn't reconstruct.

### Task

Find what was actually broken. Stop the loss. Then make sure this category of failure can never be silent again.

### Action

Five days, one hypothesis at a time.

Day one — checked the obvious. Kafka Connect running, yes. Messages in topic, yes, millions backing up. So the gap was between consumption and GCS write. Not the producer side.

Day two — enabled DEBUG logging on the connector. NullPointerException in our SMT filter. Some legacy records didn't carry the `wm-site-id` header we assumed was always there. `header.value().toString()` blew up on null. Added try-catch with graceful fallback to US bucket (PR #35). Deployed. Lag started clearing.

Day three — lag started growing again. Consumer poll timeouts in the logs. Default `max.poll.interval.ms` was 5 minutes; our GCS writes for large batches were taking longer. Tuned consumer configs.

Day four — still unstable. Correlated with K8s events and found KEDA was the trap. Lag goes up, KEDA scales up workers, scaling triggers consumer-group rebalance, rebalance stalls consumption, lag goes up more, KEDA scales more. Feedback loop. PR #42 — disabled KEDA, switched to CPU-based HPA.

Day five — workers OOM-killed every 30 to 60 minutes. JVM heap on default ~256MB, flush size was 10M records, Avro deserialization needs real memory. PR #57 → #61 raised heap to 7GB with G1GC tuned for low pause. The OOMs stopped.

Through all five days, Kafka itself retained every message. Nothing was permanently lost.

Then the deeper find. During validation against API Proxy request counts, I cross-checked Data Discovery (Hive) record counts and saw a 40,000–130,000 record per day delta. Default 1MB payload limit on the API Proxy was hitting 413 Payload Too Large for inventory responses with hundreds of items — *before* they reached the audit publisher. PRs #49–51 bumped it to 2MB. After the fix, the two counts matched exactly.

### Result

Zero data loss. Backlog cleared in 4 hours once the last fix landed. Wrote the runbook that two other teams have since pulled from for similar silent failures. The 413 discovery is the one I'm proudest of — it would've kept leaking forever without that cross-tier validation.

Afterwards I added Prometheus alerts for consumer lag (warning at 100, critical at 500) and per-tier record counts. The whole point: monitoring inputs doesn't guarantee outputs are correct. Validate at every tier boundary.

---

## Technical depth — if they probe

- **Why it was silent**: `errors.tolerance: all` plus no alerting on lag or dropped-record counts. Kafka Connect's error tolerance hides everything by design unless you instrument it.
- **The KEDA feedback loop**: Lag-based autoscaling triggers consumer rebalances. Rebalances pause consumption. Pause makes lag worse. Don't scale Kafka consumers on lag — use CPU.
- **The 413 cross-tier check**: API Proxy request count vs Hive record count vs Kafka topic count. The three should agree. They didn't, and the gap had a specific shape that pointed at payload size.
- **Heap tuning**: 7GB with `-Xms5g -Xmx7g`, G1GC with target pause 200ms. Large batches plus Avro deserialization is genuinely memory-hungry.

---

## Likely follow-ups

**Q: How did the team miss this for six weeks?**
> The pod-up dashboards stayed green. The metric we needed — consumer lag and per-tier record counts — wasn't there. Monitoring asked the wrong question.

**Q: Why cross-tier validation?**
> Each tier reports what it processed, not what it received. Comparing tier-to-tier counts is the only way to see records that vanished between them.

**Q: What did you change after?**
> Two-tier lag alerts (100 warning, 500 critical), per-tier record-count metrics with daily reconciliation, and a runbook for silent-failure debugging. The runbook has been used twice since.

**Q: What's the broader lesson?**
> "Is it running?" isn't monitoring. "Is it processing correctly, fast enough, without losing data?" is monitoring. I built that into every service after.

---

## What NOT to say

- Don't blame the original implementer — the silent-failure-friendly defaults are a Kafka Connect quirk.
- Don't claim heroic single-day debugging. It was five days of disciplined hypothesis-and-test.
- Don't downplay the 413 find. It's the one we would've kept missing without the cross-tier check.

---

## Backup story (if asked for another)

On the audit common library, my own design had a silent quality issue. The thread pool's default `AbortPolicy` plus our exception swallow meant rejected audit records vanished. A senior caught it on PR review. I added `audit_log_rejected_count` as a Prometheus metric and a WARN log at 80% queue depth. That instrumentation has caught two real downstream slowdowns since — both times we scaled the thread pool before a single record was actually rejected.
