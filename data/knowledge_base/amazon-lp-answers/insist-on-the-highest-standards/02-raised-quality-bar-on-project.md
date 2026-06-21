# Q: Describe a situation where you helped raise the quality bar on a project or task.

> **LP**: Insist on the Highest Standards
> **Primary story**: `W10 — Observability Stack`
> **Backup story**: `P3 — Test Coverage 30% → 83%`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

After the Kafka silent failure in May 2025, our monitoring story was honest but ugly. We had "is the pod up" alerts. We didn't have "is it actually processing." The runbook said to grep logs.

Our SLA promise to suppliers was 99.9%. We had no real way to prove we were keeping it.

### Task

I owned the observability gap. The bar I wanted to set: every service should answer three questions at any moment — is it running, is it processing correctly, and how close are we to breaching SLA?

### Action

I started with Prometheus alert rules in `service-latency-alerts.yaml`. The rule that mattered most: `rate(http_server_requests_seconds_sum) / rate(http_server_requests_seconds_count) > 0.1` for 700 seconds. Translation — average latency above 100ms sustained for about 12 minutes pages on-call. Short spikes don't wake anyone.

For 5xx, I went the other way. Any single 5xx for 30 seconds pages immediately. Our consumers are external suppliers — Pepsi, Coca-Cola, Unilever. A 500 to them shows up in their dashboards before ours.

For Kafka consumer lag — the thing that bit us silently — I added two tiers. Warning at 100 messages for 5 minutes, critical at 500. The warning gives the on-call time to investigate. The critical says drop everything.

Then Dynatrace transaction marking. Every downstream call — UberKey lookup, EI inventory call — became a child span. So when latency spikes, the trace tree tells you which leg is slow, not just that the request was slow.

Finally Flagger canary on every deploy. 10% traffic step, 2-minute checks, automatic rollback if success rate dropped below 99% or P99 went above 500ms. No human in the loop for the rollback.

I wrote the alert YAMLs and the runbook together. Other teams pulled them as the template.

### Result

99.9% SLA held across the year. The 80% queue warning I added in the audit library caught a downstream slowdown twice — we scaled the thread pool before any data was dropped. The consumer-lag alert caught two more silent stalls before customers noticed. The whole stack — alert YAMLs, Flagger config, Dynatrace marking — became the SLA template for new services.

The thing I'm proud of: the bar wasn't "more dashboards." It was "every alert must mean something on-call has to do."

---

## Technical depth — if they probe

- **Why 700s for latency, 30s for 5xx**: Latency has natural noise — GC pauses, network blips. 5xx is binary signal. Different alert windows match different signal-to-noise ratios.
- **Two-tier Kafka lag (100 / 500)**: Comes directly from the silent-failure post-mortem. Single-threshold alerting either pages too late or too often.
- **Flagger over manual canary**: A human watching graphs for 24 hours is unreliable. Flagger checks every 2 minutes deterministically and rolls back without paging anyone.
- **Dynatrace child spans**: We use `TransactionMarkingManager.addChildTransaction(...)` per downstream call. Without it, the parent span is one opaque 400ms blob.

---

## Likely follow-ups

**Q: How do you keep alerts from going stale?**
> Quarterly review. If an alert fired in 90 days but nobody took action, it's noise — either fix the threshold or delete it. If a real incident happened with no alert, we add one.

**Q: What's the difference between Prometheus and Dynatrace for you?**
> Prometheus is for SLO alerting on aggregated metrics. Dynatrace is for tracing a specific slow request. I use Prometheus to know something is wrong, Dynatrace to know what is wrong.

**Q: How did you sell this to leadership?**
> Framed in terms of the May incident. "We lost 6 hours of audit data and didn't know. If we hit 0.5% more downtime this quarter, we miss SLA." Numbers from the post-mortem, not a wish list.

**Q: Did other teams actually adopt it?**
> Two teams cloned the alert YAMLs in the first quarter. The on-call channels are noisier now, but in a useful way — alerts fire when something actually needs attention.

---

## What NOT to say

- Don't list every metric you collect. The bar is meaningful alerts, not metric volume.
- Don't say "we now have 99.9% uptime" as if monitoring caused it. Monitoring revealed it.
- Don't claim Dynatrace is universally better than open-source — it's the tool the org pays for.

---

## Backup story (if asked for another)

As a PayU intern I inherited a Loan Origination System with 30% test coverage. Business logic was mixed into controllers, database calls sat next to validation. I extracted services, added interfaces for DI, wrote JUnit tests across the disbursal flow. Coverage went from 30% to 83%. I also wired SonarQube into GitHub Actions and Flyway for migrations — deployment-related errors dropped about 90% because schema changes were tracked and reversible.
