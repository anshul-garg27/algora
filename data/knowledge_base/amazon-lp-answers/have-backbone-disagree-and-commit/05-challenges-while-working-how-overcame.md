# Q: Tell me about a time you faced challenges while working on something and how you overcame them.

> **LP**: Have Backbone; Disagree and Commit
> **Primary story**: `W1 — Silent Kafka Failure`
> **Backup story**: `G2 — Beat Rate Limiting`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

About six weeks after we launched the GCS sink in production — this was the Kafka audit pipeline that feeds BigQuery — I opened the team dashboard on a Wednesday morning and saw something off. GCS buckets had stopped receiving data. No alerts had fired. No errors in the dashboards. Kafka was healthy. Suppliers were still hitting our APIs. The audit pipeline was just silently dropping compliance data.

### Task

I owned the system. I had to find root cause and stop the bleed before we lost data we could not recover. The challenge was that nothing was visibly broken — every tier said it was fine.

### Action

The first day, I worked the obvious. Was Kafka Connect running? Yes. Were messages in the topic? Yes — millions, backing up. Conclusion: the problem sat between consumption and the GCS write.

Day two I turned on DEBUG logging on Kafka Connect. Found a `NullPointerException` in our SMT filter. Some legacy records had no `wm-site-id` header, and the filter blew up trying to read it. I shipped PR #35 with a try-catch that defaulted to the US bucket on null headers. Backlog started flowing again. I thought it was over.

It was not. Day three, GCS write rate dropped again. Found consumer poll timeouts in the logs. Default `max.poll.interval.ms` was 5 minutes. GCS writes for large batches were taking longer than that. Bumped the interval, tuned batch sizes.

Day four was the painful one. I traced the events and noticed KEDA autoscaling was firing every few minutes. Lag goes up → KEDA scales the consumer pool → consumer group rebalances → during the rebalance, zero messages are consumed → lag goes higher → KEDA scales again. A feedback loop. KEDA was the bug. PR #42 removed it entirely and we switched to CPU-based HPA. Heartbeat and session timeouts went from 10s to 600s. The rebalance storm stopped.

Day five, JVM heap exhaustion. Avro deserialization on large batches was OOM-killing workers every 30-60 minutes. Default heap was 256MB. PR #57 bumped to 2GB, then PR #61 raised it again to 7GB with G1GC tuning. OOM kills stopped.

The bit I am most proud of: a couple of weeks later during validation, I cross-referenced API Proxy request counts against Data Discovery row counts. We were short 40,000 to 130,000 records a day. Root cause was the API Proxy default 1MB payload limit — large responses were hitting 413 before they even reached the audit publisher. PRs #49-51 bumped it to 2MB. After that, the two counts matched exactly. Zero data loss.

### Result

Five days, five distinct production issues — SMT NPE, poll timeout, KEDA rebalance storm, OOM kills, and the upstream 413. Kafka retained everything during debugging so we lost no compliance data. The backlog cleared in four hours after the last fix. I wrote a troubleshooting runbook that two other teams used inside the next quarter. The thing that stuck with me — Kafka Connect's error tolerance can mask real bugs. Monitoring inputs does not guarantee outputs. Now I always validate at every tier boundary, not just the entry point.

---

## Technical depth — if they probe

- **SMT filter NPE (PR #35)**: SMT = Single Message Transform. With `errors.tolerance=none`, one bad record stops the whole connector. Try-catch with permissive default to US bucket.
- **KEDA rebalance storm (PR #42)**: KEDA on consumer-lag metrics triggered scaling, scaling triggered consumer-group rebalance, rebalance halted consumption, lag grew. Removed KEDA, used CPU-based HPA. `heartbeat.interval.ms` and `session.timeout.ms` went to 10 minutes.
- **JVM heap (PRs #57, #61)**: `-Xms4g -Xmx7g` with G1GC for low-pause behavior under Avro deserialization load.
- **413 Payload Too Large**: API Proxy default 1MB. `APIPROXY_QOS_REQUEST_PAYLOAD_SIZE: 2097152`. Upstream gateway dropping the payload before our publisher ever saw it.
- **Validation method**: API Proxy request count vs Hive row count, daily cross-check. Caught the 413 gap that no per-tier metric would have surfaced.

---

## Likely follow-ups

**Q: What was the hardest moment?**
> Day three. I had shipped a fix on day two and the data started flowing again. Then it stopped. I had to accept the SMT fix was real but not the only bug. There were more layers.

**Q: How did you not panic?**
> Kafka has retention. Messages were not lost — they were backed up. That bought me time. I worked one layer at a time and resisted shipping speculative fixes.

**Q: Why did the alerts not fire?**
> We were alerting on "is Kafka Connect running" and "are messages in the topic." Both were true. The failure was downstream and silent. The fix was tier-boundary validation — every output should match every input.

**Q: What did the runbook contain?**
> The five failure modes, the symptom for each, the metric to check, and the rollback path. Two teams used it for unrelated Connect issues that quarter.

---

## What NOT to say

- Do not say "we lost data." Kafka retention saved us.
- Do not collapse all five issues into one. They were genuinely separate root causes.
- Do not make it sound clean. It was a five-day grind with several false fixes.

---

## Backup story (if asked for another)

G2 — Beat scraping at GCC. Instagram and YouTube rate limits kept tripping our 150 workers. I built a token-bucket rate limiter per platform, added exponential backoff on 429s, and routed proxy IPs in a round-robin pool. Crawl throughput went from 200K profiles/day to 500K+.
