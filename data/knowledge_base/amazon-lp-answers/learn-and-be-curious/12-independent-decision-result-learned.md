# Q: Tell me about a time you made an independent decision, what result you got, and what you learned from it.

> **LP**: Learn and Be Curious
> **Primary story**: `G4 — Dual-Database API Coffee`
> **Backup story**: `W4 — Multi-Region Rollout`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Mid-2023 at Good Creator Co. I was building Coffee — our main Go REST API serving 40+ endpoints across 12 modules. The product team wanted a single database for everything — simpler ops, one place to look for data. Postgres was the default choice. Discovery searches, leaderboard rankings, time-series engagement queries — all on Postgres. I'd inherited a draft plan from a senior who'd left.

### Task

Decide on the database layer for Coffee. I was the sole engineer on the service. The decision was effectively mine to make.

### Action

I started with the workload. The Discovery module needed aggregations over millions of profile records — "average engagement rate for fashion influencers last 30 days." Leaderboard ranking joined 12+ tables with window functions across multiple platforms. Postgres could do these, but slowly — I benchmarked them and saw 30-second query times at our data volume.

Coffee also needed transactional operations — profile collections, post collections, campaign-profile associations. Those wanted ACID, foreign keys, point lookups by ID. That's Postgres' strength.

I almost went with single-Postgres for two days. Then I ran a benchmark on ClickHouse for the same leaderboard query. 30 seconds dropped to 2 seconds. 5x compression on the same dataset because columnar storage compresses similar values well. The numbers were unambiguous.

So I flipped the plan — dual database. Postgres for OLTP (CRUD on profiles, collections, campaigns). ClickHouse for OLAP (aggregations, time-series, ranking). The middleware would manage both sessions per request — `RequestContext.Session` for Postgres, `RequestContext.CHSession` for ClickHouse. Commit or rollback both at the end of the request.

I had to defend this in a design review. The senior who'd drafted the original plan asked the obvious question — "two databases means twice the ops complexity, are you sure?" I showed the benchmarks. 30s to 2s on real queries. 5x storage cost reduction. The kicker — Postgres scans on the leaderboard query were also slowing down profile lookups because of shared buffer cache pressure. Splitting workloads protected both.

The team agreed. I wrote a small wrapper so the same Service interface worked against either DAO — Postgres or ClickHouse — based on which module the request hit.

### Result

API response times improved 25% across the board. Analytics queries went from 30 seconds to 2 seconds. Operational cost dropped about 30% — ClickHouse columnar storage was much cheaper for the same query volume. What I learned — when the default plan and the benchmark disagree, trust the benchmark. And — if you're going to disagree with a senior's draft plan, bring numbers. Opinions don't move the room. Numbers do.

---

## Technical depth — if they probe

- **Why Postgres for OLTP**: row storage, ACID transactions, foreign keys, fast point lookups by ID. CRUD on profiles, collections, campaign-profile junctions.
- **Why ClickHouse for OLAP**: columnar storage means reads only touch columns the query needs. 5x compression on our data. `argMax(value, timestamp)` for "latest value per group" without subqueries. Materialized aggregations via MergeTree.
- **Dual session management**: every request had two persistence sessions in its context. Middleware committed or rolled both back on completion. If one failed, the other rolled back.
- **What I lost**: cross-database joins. Mitigated by syncing aggregated marts from ClickHouse to Postgres via dbt + S3 staging — that's where Stir later came in.

---

## Likely follow-ups

**Q: How did you handle the operational complexity argument?**
> Two ways. First, the benchmark numbers were too big to ignore — 30s → 2s isn't a marginal win. Second, our infra team had a Click ouse cluster running for other services already, so we weren't introducing new infrastructure.

**Q: What was the riskiest part of dual database?**
> Eventual consistency between them. Profile data lived in Postgres; aggregations lived in ClickHouse. The lag between a profile update and the aggregated mart could be up to 15 minutes during heavy load. We mitigated with cache invalidation events via Watermill — when Postgres updated, we invalidated the Redis cache so the next read pulled fresh data.

**Q: When would single Postgres have been right?**
> If aggregations were small (thousands of rows, not millions). At our scale it wasn't right. At a smaller startup with 10K profiles it would be.

**Q: What did this decision teach you about disagreement?**
> Numbers move conversations. Showing the benchmark switched the room from "two databases is risky" to "we'd be crazy not to use ClickHouse." The decision wasn't really about my opinion versus the senior's — it was about benchmarks versus assumptions.

---

## What NOT to say

- Don't say I "overruled" the senior. I changed the plan with the team's agreement after showing data.
- Don't claim no downsides — dual database adds operational complexity and cross-system consistency questions. Acknowledge the tradeoff.
- Don't oversell the savings as financial. "30% cost reduction" was on the analytics query path, not the total infra bill.

---

## Backup story (if asked for another)

Multi-region Active/Active for the Walmart audit pipeline. Leadership said "make it resilient" with no spec. I picked Active/Active over Active/Passive because audit is write-heavy and a 30-minute failover would breach our compliance RPO. Argued for 2x infrastructure cost on the basis that compliance failure cost more than infrastructure. Shipped in 4 weeks. DR test: 15-minute recovery, zero data loss. Same lesson — when a decision is yours to make and the data points one way, name the tradeoff explicitly and ship.
