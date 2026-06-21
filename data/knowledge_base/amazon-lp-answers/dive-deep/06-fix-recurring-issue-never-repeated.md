# Q: How did you fix a recurring issue and ensure it never repeated?

> **LP**: Dive Deep
> **Primary story**: `W1 — Silent Kafka Failure`
> **Backup story**: `W3 — DiscardPolicy Feedback`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

The audit pipeline I owned had a habit of failing silently. The first silent failure was the May 2025 outage — five days of debugging, four root causes stacked on top of each other. Two weeks after I shipped the fixes, a similar shape of failure popped up again on a different SMT filter. Different code path, same flavor: looked healthy, was broken.

### Task

Stop treating each silent failure as a one-off. Find the class of bug and remove it.

### Action

I sat down and listed every silent-failure incident from the previous six months. There were four. I wrote them out side by side:

1. SMT NPE on missing `wm-site-id` header (PR #35). `errors.tolerance: none` plus no metric on filter exceptions equalled silent drop.
2. KEDA rebalance storm (PR #42). Scaling on lag triggered rebalances, lag climbed, more scaling. No alert because individual instances looked fine.
3. JVM OOM kills every 30-60 minutes (PRs #57, #61). The pod restarted, Kafka offsets were preserved, dashboards stayed green.
4. API Proxy 413 cap on large payloads (PRs #49-51). Records dropped at the gateway before they ever reached us. Our metrics started downstream of the loss.

The pattern was clear. Every one of them broke between tiers. Each tier had its own health check that said "I'm fine," but nobody was measuring tier-to-tier consistency.

The fix was structural, not local. I added three things to our common library so every service got them for free:

First, per-tier record counters. `audit_pipeline_records_total{stage}` published at the LoggingFilter, the publisher controller, the Kafka send confirmation, and the GCS sink commit.

Second, a Prometheus alert on cross-tier divergence: if `stage_a` and `stage_b` counters drift more than 0.1% over a rolling 5 minutes, page on-call.

Third, a quarterly cross-tier reconciliation job. BigQuery counts API Proxy requests, audit publisher events, and Hive records, then emails any service whose tiers don't reconcile.

I also rewrote the runbook for "silent failure debugging." Five sections, one per known failure shape, with the metric you'd check first. Two other teams used it inside a month.

### Result

Eight months in, the cross-tier alert has fired three times. Two were real — a Kafka topic misconfiguration and a 413 regression after a gateway upgrade. Both caught in under 15 minutes instead of hours or days. One was a false positive that I tightened the threshold for. Zero silent failures of the old "discover by spreadsheet" variety.

The deeper change was cultural. Anyone in the team shipping a new pipeline now adds tier counters by default — it's in the PR template checklist. Honestly, that's the part I'm proudest of. The metric I shipped fades; the habit doesn't.

---

## Technical depth — if they probe

- **Why 0.1% threshold**: We had ~0.02% baseline drift from in-flight messages and retry boundaries. 0.1% catches real loss without tripping on normal jitter.
- **Why per-tier counters, not traces**: Traces are sampled; counters aren't. For "did we drop records?" you need the unsampled count, not a representative sample.
- **Why a quarterly reconciliation job in addition to the alert**: Real-time alerts catch fast loss. Slow leaks — like a 0.05% drift that compounds over weeks — only show up in batch reconciliation. Belt and suspenders.
- **Why I rewrote the runbook**: A bug pattern with no documented playbook is a bug that will recur. The runbook gives the next on-call engineer a 30-minute path to root cause instead of a 5-day path.

---

## Likely follow-ups

**Q: Couldn't you have caught all of this with end-to-end tests?**
> Some, not all. The KEDA storm only manifested under real production load. The 413 only happened on real supplier payloads. E2E tests are necessary but not sufficient — you also need running-system invariants like cross-tier counters.

**Q: How did you convince the team to adopt the PR template?**
> Showed them the time-cost data. The five-day debug in May plus the two-day debug for the 413 plus the half-day for the KEDA loop — that was 8 person-days of debugging in two months. The 30 minutes to add counters per service was an obvious trade.

**Q: What's the next class of bug you're chasing?**
> Schema-evolution silent failures. We're on Avro, and a new optional field added on the producer side without consumer rebuilds can silently default to null. I'm proposing a schema-registry compatibility gate in CI.

**Q: How do you know the fix really worked?**
> Eight months of zero "spreadsheet discoveries." The alert has fired correctly when real loss happened. And the runbook has been linked from on-call rotation handoffs without me prompting.

---

## What NOT to say

- Don't pitch this as "I solved it once" — say "I solved the class of bug."
- Don't blame Kafka Connect or KEDA. Blame the absence of cross-tier invariants.
- Don't oversell zero failures. Say "zero of the old shape." There will always be new shapes.

---

## Backup story (if asked for another)

For W3, the DiscardPolicy story is the same idea at a smaller scale. I'd defaulted the audit thread pool to `DiscardPolicy` — fire-and-forget, no exception thrown when the queue filled. A teammate pointed out this would silently drop audit events under load. I went to bed defending it. I came back the next morning, ran the math on peak load, and realised he was right — at 120 events/sec with a 100-deep queue, even a 1-second hiccup would drop a hundred events. I switched to `CallerRunsPolicy` (natural backpressure) and added a queue-depth gauge with an alert at 80% capacity. Recurring class of bug killed.
