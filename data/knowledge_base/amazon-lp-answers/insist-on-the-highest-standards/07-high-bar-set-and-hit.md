# Q: Describe a high bar you set and hit.

> **LP**: Insist on the Highest Standards
> **Primary story**: `W10 — Observability Stack + 99.9% SLA upheld`
> **Backup story**: `W5 — Zero customer impact across 5-day canary`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Mid-2025, after the Kafka silent-failure incident. Our SLA promise to suppliers was 99.9% uptime. We didn't have the instrumentation to prove it. We had pod-up alerts. We didn't have "is it actually processing" alerts. Our 99.9% number was hope, not measurement.

### Task

Set a real bar: every service must answer three questions at any moment — is it running, is it processing correctly, and how close are we to breaching SLA. And then hold the 99.9% across the year.

### Action

I started with Prometheus alert rules. For HTTP latency: `rate(http_server_requests_seconds_sum) / rate(http_server_requests_seconds_count) > 0.1` for 700 seconds — sustained above 100ms for about 12 minutes pages on-call. Short spikes don't.

For 5xx, opposite logic. Any single 5xx for 30 seconds pages immediately. Our consumers are external suppliers — a 500 hits their dashboards.

For Kafka consumer lag — what bit us in May — two tiers. Warning at 100 messages for 5 minutes. Critical at 500. The warning gives time to investigate. The critical is "drop everything."

For the audit library specifically, I added a metric for thread-pool rejections and a WARN log when queue depth crossed 80%. The catch-and-log we had before was lying to us. That instrumentation came directly out of W3 feedback — a senior had told me queue size of 100 could silently drop data, and he was right.

Then Dynatrace transaction marking. Every downstream call gets its own child span — UberKey, EI inventory, the auth lookup. The trace tree tells you which leg of a 400ms request was slow.

Finally Flagger canary on every deploy. 10% step, 2-minute checks, automatic rollback below 99% success or above 500ms P99.

I wrote the alert YAMLs as a template. Two other teams cloned them in the first quarter.

### Result

99.9% SLA held across the full year. Specifically: the 80% queue warning fired twice and we scaled the thread pool before a single audit record was dropped. The consumer-lag alert caught two silent stalls. Flagger auto-rolled back a downstream service one time when error rate crossed during canary — saved us from a 30-minute outage that would've burned a chunk of the SLA budget.

The bar that mattered: every alert that fires has to require human action. Quarterly review prunes anything that doesn't.

---

## Technical depth — if they probe

- **700s for latency, 30s for 5xx**: Latency has GC noise; 5xx is binary. Different signal-to-noise ratios, different windows.
- **Two-tier Kafka lag**: Came out of the silent-failure post-mortem. Single-threshold alerting pages too late or too often.
- **Why custom metrics on the audit library**: Standard JVM metrics tell you the pool is healthy. They don't tell you tasks are being rejected. Different observable.
- **Dynatrace child spans**: `transactionMarkingManager.currentTransaction().addChildTransaction(...)` per downstream call. Without it, the parent span is one opaque blob.

---

## Likely follow-ups

**Q: How did you know 99.9% was the right target?**
> It was the existing supplier-facing commitment, just unmeasured. I didn't set the SLA — I built the system that could actually defend it.

**Q: Has the bar ever been wrong?**
> Yes. Initial latency alert was 50ms / 5 minutes — fired constantly on harmless GC spikes. I tuned it to 100ms / 12 minutes. Alert quality is measurable: alerts-acted-on divided by alerts-fired.

**Q: What's the single most important alert?**
> The Kafka consumer-lag warning at 100. It's the alert we didn't have during the May silent failure. Adding it was the direct fix for "monitoring inputs doesn't guarantee outputs are correct."

**Q: How did you get other teams to adopt the template?**
> The alert YAMLs lived in the team's shared telemetry repo. After our service's MTTR dropped, two other teams asked for the config. No mandate.

---

## What NOT to say

- Don't take credit for the 99.9% target itself — you built the system that proves it.
- Don't list every metric you collect. The bar is meaningful alerts, not metric volume.
- Don't claim observability is "set up." It's quarterly maintenance.

---

## Backup story (if asked for another)

The Spring Boot 3 migration target was zero customer-impacting issues during the 24-hour Flagger rollout. 158 files, three framework boundaries, one cross-region failover path. I held the bar with stage testing for a full week, Flagger with 10% → 100% steps and 2-minute checks, and 48 hours of old-pod retention for instant rollback. Error rate stayed at 0.02%, P99 at 180ms. No rollback triggered. The pattern became the team's default for framework upgrades.
