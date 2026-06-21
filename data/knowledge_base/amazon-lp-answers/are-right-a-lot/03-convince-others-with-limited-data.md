# Q: Describe a time you had to convince others with limited data.

> **LP**: Are Right, A Lot
> **Primary story**: `G8 — Tech-Stack Defence (dual-DB design review)`
> **Backup story**: `W5 — SB3 .block() calibration defended`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

At Good Creator Co. I was the sole architect on the Coffee API — the multi-tenant Go backend for the SaaS dashboard. In a design review I proposed running two databases side by side: Postgres for OLTP (collections, profiles, partners) and ClickHouse for OLAP (leaderboard aggregations, time-series engagement). The CTO and the tech lead both leaned toward "one Postgres, scale it up if needed." Their case: less operational overhead, one ORM, one backup story. Reasonable defaults.

I had limited production data — Coffee wasn't live yet. No real query latency numbers from our actual workload. I had to convince them based on benchmarks and architectural reasoning, not data.

### Task

Build the case for dual-DB without being able to point to "look, here's what's broken." I had to make them confident in a more complex architecture before we had any pain.

### Action

I did three things.

First, I ran a representative benchmark. Took our two heaviest query shapes — leaderboard top-1000 by engagement, 30-day time-series for a creator — and ran them against Postgres with realistic data volumes (10M profile rows, 50M post rows). Leaderboard: 28 seconds. Time-series: 31 seconds. I ran the same queries against ClickHouse with the same data: 1.8 seconds and 1.2 seconds. 15x and 25x. The numbers were the conversation-changer.

Second, I sketched the alternative explicitly. "If we go Postgres-only, here's what we'll need: read replicas, materialised views refreshed every N minutes, eventual lag tolerance. None of that is free. The total ops cost is higher than a second database with the right shape." I named the cost of the conservative option, not just the cost of mine.

Third, I addressed the operational overhead head-on. "I'll wire both into one session middleware. The `RequestContext` has both `Session` (Postgres) and `CHSession` (ClickHouse). Middleware commits or rolls back both atomically. ORMs are different (GORM for Postgres, native client for ClickHouse) but the abstraction is unified. Adding a new module looks the same."

The CTO pushed back: "two databases means two operational on-calls." Fair. I countered with the buffered-sinker pattern from Event-gRPC — ClickHouse writes are bulk + async, so a brief ClickHouse outage doesn't break user-facing requests; reads degrade gracefully to "data not available right now."

They approved.

### Result

The dual-DB design shipped and stayed in production for years. Analytics queries that would have taken 30+ seconds on Postgres returned in 1-2 seconds. Operational cost dropped about 30 percent because ClickHouse's columnar compression cut storage 5x versus Postgres row-oriented for the same data. The pattern got copied for two later projects.

The lesson: limited data isn't no data. A focused benchmark on the right query shape is worth more than vague handwaving about scale.

---

## Technical depth — if they probe

- **Benchmark methodology**: 10M profile rows, 50M post rows generated from production-shape distributions. Same queries on both stacks. Same hardware tier.
- **Single session middleware, two DBs**: `RequestContext.Session` (Postgres) and `RequestContext.CHSession` (ClickHouse). Both commit or roll back together on request completion via `defer rollbackSessions(ctx)`.
- **ClickHouse MergeTree for OLAP**: `PARTITION BY toYYYYMM(event_timestamp)`, `ORDER BY (platform, profile_id, event_timestamp)`. Partition pruning + columnar scan.
- **Graceful degradation on ClickHouse outage**: analytics endpoints return a "data temporarily unavailable" response; transactional endpoints (collections, profiles) unaffected.
- **Cost math**: 5x compression × 30 percent infrastructure savings = the resume bullet. Cheaper storage, fewer I/O ops, smaller instance types for the analytics path.

---

## Likely follow-ups

**Q: How did you choose what to benchmark?**
> The two queries most likely to be slow: leaderboards (large aggregation across many rows) and time-series (range scans). If those two were OK on Postgres, dual-DB wouldn't have been worth it. They weren't.

**Q: What if the benchmark had said Postgres was fine?**
> I'd have shipped Postgres-only. The benchmark was the gating decision, not a validation of a pre-made choice.

**Q: How did you handle the operational concern?**
> Named it explicitly in the review. Two DBs means two backups, two monitors, two on-call paths. My answer: ClickHouse failure doesn't break user-facing requests (async sinker pattern); operational overhead is real but bounded. Showed the gateway-level degradation flow so they could see the failure mode.

**Q: What if ClickHouse goes down?**
> Reads to analytics endpoints return a friendly "data unavailable" response. Transactional flows (collection CRUD, profile updates) are Postgres-only and unaffected. Writes to ClickHouse are buffered and queued in RabbitMQ — they drain when ClickHouse comes back.

**Q: How did you build trust with the CTO?**
> Brought numbers, named the cost of my proposal, named the cost of the conservative alternative, and offered to own the operational complexity. "I'll wire it; if it's a mess, that's on me" gave them an off-ramp.

---

## What NOT to say

- Don't oversell — "ClickHouse is just better than Postgres" is false. ClickHouse is wrong for OLTP. The win is matching workload to engine.
- Don't dismiss the operational pushback — two DBs IS more complex. Acknowledge it, then quantify the offsetting benefit.
- Don't pretend I had production data — I didn't. Be honest that I made the case on benchmarks.

---

## Backup story (if asked for another)

I made the same kind of case in reverse during the Spring Boot 3 migration at Walmart. A senior engineer wanted to go fully reactive. I had limited data — no production load test of WebFlux under our traffic shape. I made the case for framework-only + `.block()` based on: file count (158 files changed for framework-only vs every business class touched for reactive), team reactive familiarity (low), and the security-deadline constraint. Lead agreed. Shipped in 4 weeks, zero customer impact.
