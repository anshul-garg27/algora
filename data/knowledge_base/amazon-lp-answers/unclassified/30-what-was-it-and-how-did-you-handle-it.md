# Q: What was it, and how did you handle it.

> **LP**: Generic follow-up placeholder
> **Primary story**: `W1 — Silent Kafka Failure`
> **Backup story**: `G1 — ClickHouse Migration`
> **Time budget**: 60–90 seconds spoken (this is usually a follow-up, not the opener)

---

## Context

This is a generic follow-up prompt — "what was it, and how did you handle it" — that usually lands after the interviewer has already heard your situation. Treat it as a chance to go one level deeper without re-narrating. I default to expanding the Day-4 KEDA piece of W1 (the most technical beat) or the cutover mechanics of G1 (the riskiest step).

---

## STAR — how to actually tell it

### Situation

I'd already told them about the May 2025 silent failure — GCS buckets stopped filling, no errors, no alerts. Three fixes shipped over four days hadn't fully resolved it. The dashboard would show lag shrinking, then exploding back up.

### Task

Find the last layer of the problem. Not just patch a symptom.

### Action

Day four morning. I'd already added a null-guard for the SMT filter, tuned the consumer poll timeouts, and the lag was still pulsing. I sat with the Kubernetes events tab open in one window and Grafana in the other for about an hour and just watched.

The pattern showed up. Every time consumer lag climbed past about 100 messages, KEDA fired a scale-up. Pods went from 1 to 3. That triggered a consumer group rebalance — during rebalance, no messages are consumed. Lag grew further. KEDA scaled to 5. Another rebalance. And so on. A feedback loop where the autoscaler was making the problem worse.

The fix was uncomfortable because it argued against what looked like a sensible config — autoscale on consumer lag. But for Kafka consumers specifically, lag is the wrong signal. Scaling triggers rebalances; rebalances stop processing.

I disabled KEDA on the consumer group in PR #42 and replaced it with CPU-based HPA. Increased `heartbeat.interval.ms` and `session.timeout.ms` from 10 seconds to 10 minutes to make any future rebalances tolerable. Bumped `flush.size` from 10M to 100M to reduce write churn.

### Result

Lag stabilized within an hour of the deploy. The fifth fix — JVM heap — came the next day and was the last piece. Zero data loss across the whole incident because Kafka retained everything. The "don't autoscale Kafka consumers on lag" rule is now in our team's runbook with this incident as the reference.

---

## Technical depth — if they probe

- **Why rebalance kills throughput**: During a consumer group rebalance, partition assignments are revoked and reassigned. No consumer is processing during this window. For our config, rebalance took 30-60 seconds at a time.
- **Why CPU is a safer signal**: CPU reflects actual processing work. It rises when consumers are slow, not when partitions are unbalanced. No feedback loop.
- **Heartbeat tuning**: `heartbeat.interval.ms: 600000` and `session.timeout.ms: 600000` give a much wider window before the broker declares a consumer dead. Counterintuitive but right when your processing batches take minutes.
- **PR #42 diff**: -29 lines (KEDA YAML removed), heartbeat/session bumped 10s → 10min, `flush.size` 10M → 100M.

---

## Likely follow-ups

**Q: Why didn't this show up in staging?**
> Staging didn't have production-scale traffic. KEDA never triggered because lag never grew past the threshold. The lesson — load-test autoscalers, not just steady-state throughput.

**Q: What did you replace KEDA with?**
> CPU-based HPA. Two replicas minimum, scale to four at 70 percent CPU. Stable since deploy.

**Q: How did you avoid blaming KEDA?**
> KEDA wasn't wrong. The config was wrong for Kafka consumers. KEDA works fine on HTTP services where scaling adds capacity without rebalance cost. Distinction matters.

**Q: Generic version — describe a debugging approach for any prompt?**
> Hypothesis, test, result. Log each round. Don't skip the boring obvious checks. When stuck, take a window of time to just watch the system without doing anything — patterns show up when you stop poking.

---

## What NOT to say

- "KEDA was bad" — wrong tool for this job, not a bad tool.
- Don't make this a hero story. The honest version is "four days of failed fixes, then I sat still and saw the pattern."
- Avoid restating the whole situation. This is a follow-up — answer the specific "what was it."

---

## Backup story (if asked for another)

For the ClickHouse cutover at GCC, the riskiest step was the read flip. I'd run dual-write for two weeks with nightly row-count parity and sampled deep-compare. Three consecutive clean nights, then flipped reads to ClickHouse via a dbt-layer feature flag on a Tuesday morning. Kept Postgres writes alive for one more week as a safety net. Zero data loss across the migration.
