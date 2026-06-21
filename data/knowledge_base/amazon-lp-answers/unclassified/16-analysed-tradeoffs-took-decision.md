# Q: Tell me a time when you analysed tradeoffs and took a decision.

> **LP**: Unclassified (Are Right A Lot + Dive Deep)
> **Primary story**: G4 — Dual-Database API for Coffee SaaS
> **Backup story**: W4 — Multi-Region Active/Active vs Active/Passive
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

GCC, late 2023. We were building the Coffee SaaS API — a customer-facing analytics service that combined transactional queries (customer accounts, subscriptions, recent activity) with analytical queries (multi-month aggregations, dashboard rollups, time-series). The product team wanted both behind a single API.

The initial proposal from a senior engineer was Postgres-only — keep it simple, one database, replicate to a read-replica for analytics queries. Standard pattern at small scale. I'd been leaning toward a dual-database approach: Postgres for transactional, ClickHouse for analytical. I was the most junior person in the room. The senior engineer's plan was the default.

### Task

I had to either commit to the single-DB plan, or make a defensible case for the dual-DB plan. The decision would shape the next two years of how that API scaled.

### Action

I took a week to benchmark before committing to either side.

**Step one — name the tradeoffs explicitly.** I wrote them down on one page.

| Dimension | Postgres-only | Postgres + ClickHouse dual-DB |
|---|---|---|
| Operational complexity | Low (one DB) | Higher (two DBs + sync layer) |
| Query latency on aggregations | Mediocre (Postgres reads on 10M+ rows) | Strong (ClickHouse columnar) |
| Storage cost | Lower | ~30% lower at scale (columnar compression) |
| Write throughput | Single OLTP path | Need to dual-write or stream-sync |
| Recovery from a bad analytic query | Risk of read-replica lag spike | Isolated — ClickHouse can be hammered without OLTP impact |
| Team familiarity | High | Mixed (I knew CH, others didn't) |

**Step two — benchmark on real query patterns.** I pulled six of the most common analytics queries from the product team's mocks. Ran each against a sample 10M-row dataset on a tuned Postgres instance and a vanilla ClickHouse instance. The results were dramatic — the cheapest Postgres query was 1.8 seconds; the equivalent ClickHouse query was 280 ms. Aggregations over a year of data: Postgres 12 seconds, ClickHouse 600 ms.

**Step three — face the cost of the tradeoff I was proposing.** Operational complexity was real. Two databases meant two backup paths, two monitoring stacks, a sync layer I'd have to build. I sketched the sync — RabbitMQ buffered sinker, batched writes, eventual consistency with a 1–2 minute lag. Acceptable for analytical queries, not acceptable for transactional ones. The dual-DB design needed strict query-routing rules.

**Step four — propose, with the explicit limits.** I brought the page to the senior engineer for a 30-minute sync. I didn't argue. I showed the benchmark numbers, named the operational cost honestly, proposed the dual-DB design with the routing rules in writing. I explicitly listed when the single-DB choice would be the right one — if the read pattern was 90 percent transactional, we should stick with Postgres-only.

He pushed on the sync-layer cost. I'd already prototyped a half-day version of the buffered sinker — showed him it was about 200 lines of Go. He pushed on the team-familiarity gap — fair, I committed to writing an internal ClickHouse onboarding doc as part of the project scope.

We went with the dual-DB design.

### Result

The API shipped on Postgres + ClickHouse. Analytics dashboard p95 latency was around 700 ms — Postgres-only it would've been somewhere around 8 seconds based on the benchmarks. Two years in, the dual-DB pattern was still the right call. The sync layer cost about a week of engineering total. The onboarding doc I wrote got two engineers ramped on ClickHouse within a month.

The honest reflection — the tradeoff analysis was the easy part. The hard part was pushing back as the junior person and being willing to be wrong publicly if the benchmark numbers hadn't supported my hunch. Tradeoff analysis is only useful if you commit to the numbers, including the ones that go against you.

---

## Technical depth — if they probe

- **Why ClickHouse for analytical**: columnar storage, vectorised query execution, `MergeTree` engine partitioned `toYYYYMM(timestamp)`. Aggregations over time ranges are the dominant query shape — ClickHouse is purpose-built for this. Postgres can do it with materialised views but the maintenance cost compounds.
- **Why Postgres for transactional**: ACID, mature ecosystem, the team already knew it. ClickHouse's strict-consistency story for OLTP is weak — point lookups are not its strength.
- **The sync layer**: RabbitMQ buffered sinker — every transactional write emits a domain event to RabbitMQ, a sinker process batches 1000 events and writes to ClickHouse. Eventual consistency, 1–2 min lag, fine for analytics. Same buffered-sinker pattern I later used in G1 for the org-wide ClickHouse migration.
- **Query routing**: a thin layer in the API service inspects the query intent — anything with `GROUP BY` over a date range goes to ClickHouse, point lookups go to Postgres. About 40 lines of routing logic. We considered a query optimiser approach (parse SQL, choose route) — overkill for our query patterns.

---

## Likely follow-ups

**Q: What if the benchmark had shown Postgres was good enough?**
> I'd have gone Postgres-only. That was the actual deal I made with myself — if the numbers don't justify the operational cost, the senior engineer's plan wins. The benchmark was the decision-maker, not my preference.

**Q: How did you decide what "good enough" was?**
> The product team's latency SLO was sub-2-second on dashboard load. Postgres-only at 8 seconds wasn't close. If it had been 2.2 seconds, the dual-DB cost wouldn't have been justified. The gap was so large that the decision was clear once the benchmark ran.

**Q: How long did the benchmark take?**
> About a day to set up the sample dataset, a day to run the six queries on both DBs and document. So two days of focused work in a one-week window. Most of the time I'm doing tradeoff analysis, the bottleneck isn't the math — it's having the courage to actually run the benchmark instead of arguing from intuition.

**Q: Has the dual-DB pattern paid off?**
> Yes. Customer-visible: dashboard loads stayed sub-second through 2x growth in data volume. Internal: when one ClickHouse query went rogue during a customer's bulk export, it didn't touch the OLTP path. Postgres customer-facing reads stayed clean. That isolation was a benefit I hadn't fully priced in upfront.

**Q: Would you make the same call today?**
> At GCC's scale and query pattern, yes. At Walmart's scale, no — we use BigQuery instead of ClickHouse because we already have the GCS data lake. Different stack, same instinct: separate OLTP from OLAP when the read patterns diverge.

---

## What NOT to say

- Don't make the senior engineer the villain — his plan was the safe default and that's a legitimate choice.
- Don't claim you knew dual-DB was right from the start. The benchmark is what made it right.
- Don't skip the "I committed to the onboarding doc" detail. That's the line that signals you understand tradeoffs include team-cost, not just tech-cost.
- Don't list every dimension in the spoken answer. The table is for the written doc; spoken, you pick the 3 sharpest.

---

## Backup story (W4 — Multi-Region Active/Active vs Active/Passive)

Walmart, early 2025. The audit-logging platform needed multi-region for compliance. Tradeoff was Active/Passive (cheaper, ~30-min failover) vs Active/Active (2x infra, instant failover) vs hybrid. I wrote up a one-pager with cost, complexity, failure modes, and "what does the 3 AM on-call see" for each option. Booked 30 min with my lead, asked where my assumptions were wrong. He pulled RTO down to 30 minutes — which broke Active/Passive's case. We landed on Active/Active. Shipped in 5 weeks, 15-minute failover drill, zero data loss. Same shape as the G4 story — list dimensions, get the limits from the person who can correct them, commit on numbers.
