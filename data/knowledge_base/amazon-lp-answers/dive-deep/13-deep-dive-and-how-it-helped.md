# Q: Tell me about a time when you took a deep dive and how it helped you.

> **LP**: Dive Deep
> **Primary story**: `W1 — Silent Kafka Failure`
> **Backup story**: `G1 — ClickHouse Migration`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

The Kafka audit pipeline I owned at Walmart was failing silently in May 2025. Dashboards were green. The GCS bucket was three hours stale. About 2M events/day of compliance audit data was at risk and suppliers couldn't query what wasn't there. I'd shipped the pipeline six weeks earlier and was the only person with end-to-end context.

### Task

Find the actual cause. Stop the loss. Make sure I'd recognise the same shape next time in 15 minutes, not 5 days.

### Action

I treated the debug like a tree, not a list. Each suspected cause got a quick verification before I committed to it.

The NullPointerException in the SMT filter was the first answer DEBUG logs gave me. Easy fix — PR #35 added a try-catch and made the filter permissive when headers were missing. But I didn't declare victory; I watched the lag chart. The chart didn't budge.

That refusal to declare victory is what helped me later. I dug into consumer poll timeouts on Day 3 and found `max.poll.interval.ms` was too tight for GCS batch write times. Day 4 I overlaid the pod count on the lag chart and saw KEDA was loop-clicking itself — scaling on consumer-group lag triggers rebalances, rebalances halt consumption, lag climbs, KEDA scales again. PR #42 removed KEDA's Kafka trigger.

Day 5 was JVM heap. `jmap -histo:live` told me Avro deserialization was eating the 512MB default. PRs #57 and #61 took it to `-Xms5g -Xmx7g` with G1GC tuned for low pause.

The dive helped me beyond fixing the one outage. I noticed all four root causes had one shape in common — each tier had a healthy-looking metric, but nobody was measuring tier-to-tier consistency. I added cross-tier record counters to our common library: a Prometheus counter at the filter, the publisher, the Kafka send, and the GCS commit. Plus an alert on tier-to-tier divergence over 0.1%.

### Result

Zero data loss through the original outage — Kafka retained everything. Backlog cleared in four hours. The runbook I wrote got used twice by other teams.

But the part that helped most was the cross-tier counter. It's caught two real silent-loss incidents since, both in under 15 minutes. One was a Kafka topic misconfiguration after a platform upgrade. The other was a 413 regression on the API Proxy after a gateway version bump. Without those counters, both would have been week-long spreadsheet debugs like the original.

Honestly, the dive helped me as much as it helped the team. I now build cross-tier invariants into every pipeline I touch, by default. The pattern came from one bad week.

---

## Technical depth — if they probe

- **Why DEBUG first, then metrics**: We didn't have a filter-exception counter at the time. DEBUG was the fastest path to "what's the actual error." I added the metric afterwards so future debugs start with the counter.
- **Why KEDA on lag is a known anti-pattern**: Lag-based scaling triggers consumer-group rebalances, which halt consumption, which climbs lag, which triggers more scaling. CPU-based HPA breaks the coupling.
- **Why I added cross-tier counters to the common library**: Because every service consuming the library gets them for free. Local fixes don't scale. Library fixes do.
- **Why 0.1% divergence threshold**: We had ~0.02% baseline drift from in-flight messages and retry boundaries. 0.1% catches real loss without false positives.

---

## Likely follow-ups

**Q: What did you almost get wrong?**
> Declaring victory on Day 2 after the NPE fix. If I'd walked away then, KEDA would have eaten us alive a week later when the next traffic spike hit.

**Q: How did this change how you ship pipelines?**
> Cross-tier counters in the PR template checklist. Day-one alerting, not bolt-on. Runbook per known failure mode. The cost is 30 minutes per service; the saving is 5 days of debugging when the next silent failure happens.

**Q: What's the easiest mistake to make in this kind of debug?**
> Trusting the dashboard. If you only look at metrics that exist, you only see the failures you anticipated. The Day 4 KEDA loop only became visible when I overlaid two charts that weren't designed to overlay.

**Q: Has anyone else benefited from the runbook?**
> Two teams. One had a similar OOM pattern and the heap-tuning section saved them an afternoon. Another caught a consumer-poll-timeout issue using the metric I'd added.

---

## What NOT to say

- Don't say "I solved it in a day." The five-day arc is the substance and the credibility.
- Don't oversell zero failures since. Say "zero of the original shape." There will always be new shapes.
- Don't blame any specific tool — the bug was in the seams between tools, not in the tools themselves.

---

## Backup story (if asked for another)

The G1 ClickHouse migration was a longer dive — months of slowly-degrading PostgreSQL performance that the team had been treating as inevitable. I dug into the query patterns and realised it was a column-oriented workload running on row-oriented storage. Three POCs, real benchmarks, ClickHouse won. Two weeks of dual-write at less than 0.02% drift, then we cut over. Query time 30s → 12s, storage 5x compression, infrastructure cost 30% down. The deep dive helped because the team had been arguing about which Postgres indexes to add; the answer was that no Postgres index would solve a column-oriented problem.
