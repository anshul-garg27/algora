# Q: Describe a time you advocated for a more responsible engineering approach.

> **LP**: Success and Scale Bring Broad Responsibility
> **Primary story**: `W9 — Cosmos → Postgres Migration for Cost Sustainability`
> **Backup story**: `G6 — Interpretable Heuristic Over Black-Box DL`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

The Transaction Event History service at Walmart was running on Azure Cosmos DB. It had been built two years earlier when the team wanted "infinite scale" and Cosmos's auto-scaling Request Unit model looked attractive. By the time I picked up ownership in 2025, the service was costing about $18K/month — and that was on a workload that didn't actually need Cosmos's distributed-write characteristics.

### Task

Decide whether to keep running on Cosmos (easy, no change risk, $18K/month) or migrate to Postgres (cheaper, but requires migration work and operational lift). The framing the team had been using was "Cosmos is what we know — let's keep it." I wasn't sure that was the responsible answer at our scale.

### Action

I pulled the actual usage data. Three things jumped out.

One — write volume was about 50 writes/sec average, peak 200. Cosmos can do millions. We were paying for headroom we'd never use.

Two — the query patterns were almost entirely point-reads by `transaction_id` plus range scans by `(supplier_id, timestamp)`. No global secondary indexes were ever queried in any non-trivial way. Postgres B-tree indexes would handle both patterns easily.

Three — Cosmos's distributed-write model was costing us indirectly. Every write fanned out to 4 regions for consistency. We didn't need 4-region writes; we had one writer, several readers.

I wrote up a proposal. Cosmos at $18K/month vs Postgres at about $3.5K/month for the same workload, including read replicas in the regions we actually served. Annual saving roughly $175K. But the responsibility argument wasn't only the dollars — it was that we were burning compute and electricity for capacity we'd never use. At Walmart's scale, "we use the expensive tool because it's familiar" multiplied by hundreds of services is real environmental and financial cost.

The pushback was real. "Migration risk" was the main concern. So I proposed a dual-write phase — write to Cosmos and Postgres in parallel for 4 weeks, validate row-count parity within 0.05%, then cut over reads, then cut writes. Rollback was always one config flag away.

I also wrote a non-functional case. Postgres is what our DBA team operates daily; on-call for Cosmos was outsourced to two engineers globally. Sustainability isn't only environmental — it's operational. The system that breaks on a Saturday should be one our actual team can fix.

### Result

The migration shipped in 6 weeks. Cosmos was decommissioned. Run-rate cost dropped from $18K/month to $3.4K/month — about $175K saved annually. P95 read latency improved slightly because Postgres with proper indexes was faster for our shape than Cosmos's RU-throttled reads. Zero data loss across the cutover.

The broader change was cultural. Our team now defaults to the simpler tool unless there's a real reason for the complex one. Three other services have done the same kind of "right-size your DB" exercise in the year since. Total savings across the team is over $400K/year.

Honestly, what I'm most pleased about is that nobody calls it a "downgrade." The framing went from "Cosmos is the prestigious option" to "Postgres is the right tool for this shape." That shift is the thing that compounds.

---

## Technical depth — if they probe

- **Why Cosmos was overkill**: We had one writer per region, no cross-region write conflicts, and our read consistency model was "eventual was fine, strong was nice-to-have." That's a Postgres workload, not a Cosmos workload.
- **Why dual-write for 4 weeks**: 30 days of full month-end batch cycles. Edge cases that only fire on month-end (reconciliation, statement generation) needed at least one full cycle on both sides before I trusted parity.
- **The Postgres index strategy**: One B-tree on `transaction_id` (primary). One composite on `(supplier_id, timestamp DESC)` for the range scans. One partial index on `status = 'PENDING'` for the open-transaction queries. Three indexes, full workload coverage.
- **Why I included operational sustainability in the case**: The cheapest dollar-cost can still be the wrong choice if your team can't operate it. Including operational lift in the responsibility argument made the trade explicit.

---

## Likely follow-ups

**Q: What if Cosmos had been the right tool?**
> Then we'd have stayed. I tested the assumption with real workload data before recommending the change. If write rate had been 10x higher or if we'd needed multi-region writes, Postgres would have been wrong.

**Q: How did you handle the "we already know Cosmos" pushback?**
> I named it as a sunk-cost argument. Past Cosmos investment doesn't justify future Cosmos cost. The right question is "if we were starting today, what would we pick?" Two engineers said "Postgres" without hesitation.

**Q: What was the riskiest moment of the cutover?**
> The 24 hours after we switched reads. If Postgres p95 had been worse than Cosmos's, we'd have rolled back. It was actually better — proper indexes plus no RU throttling. I slept that night.

**Q: How do you think about scale-driven responsibility more broadly?**
> Every "we'll just over-provision" decision at one service becomes a fleet-wide habit. At Walmart we run thousands of services. A 5x over-provisioning factor across the fleet is millions of dollars and megawatts. Right-sizing isn't penny-pinching — it's responsibility for the resources we use.

---

## What NOT to say

- Don't make this anti-Cosmos. Say "Cosmos is great for the right workload — ours wasn't it."
- Don't claim the migration was risk-free — say "rollback was one config flag away" because that's the truth.
- Don't oversell the $175K — say "approximately $175K annually." Estimates are credible; round numbers are not.

---

## Backup story (if asked for another)

For G6, building the fake-follower detection ML, my manager wanted a deep-learning model. I pushed back. The training cost was high, inference cost was high, and the model was a black box — when it flagged an account, we couldn't explain why. I proposed an interpretable heuristic ensemble — 7 features, a logistic regression on top, plus rule-based gates. Same precision/recall at 1/100th the inference cost and full explainability. The responsible argument was that suppliers were going to ask "why was this account flagged?" and a deep-learning model couldn't answer that. Heuristics could.
