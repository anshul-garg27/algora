# Q: tell me about a time where you made some data recomendations and it was accepted by the team.

> **LP**: Dive Deep / Are Right A Lot (hybrid)
> **Primary story**: `W9 — Transaction Event History Cosmos → Postgres`
> **Backup story**: `G4 — Dual-Database API Coffee`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

At Walmart Data Ventures we had a Transaction Event History service backed by Azure Cosmos DB. The monthly Cosmos bill was creeping up — we were billed on RU/s, and our read pattern was slamming the high-RU end. The team's instinct was "throw more RUs at it." I wasn't sure.

### Task

Either accept the bill and tune Cosmos, or propose a migration. Make the call from data, not vibes.

### Action

I spent a week pulling numbers. Three things mattered.

First, our access pattern. Most reads were by `transaction_id` plus a `supplier_id` filter, with a date range. That's a primary-key lookup plus a secondary index. Cosmos handles that with cross-partition queries, which is where the RU spike happens.

Second, the actual data shape. Cosmos was sold to us as schemaless, but the docs we wrote in were 95 percent the same structure. Only two fields varied between supplier types. We weren't using the schema-less property.

Third, the cost numbers. Cosmos at our read rate was costing about $4K/month and trending up. A WCNP-managed Postgres of the same size would land around $800/month with consistent latency, plus JSONB for the variable fields.

I wrote a one-pager. Read pattern, cost, latency table, JSONB schema sketch, migration plan with a two-week dual-write window. Took it to the team in a design review.

The pushback was real — "Cosmos is multi-region, what about DR?" Fair. I added a Postgres read replica in the secondary region with a sync delay budget of 5 seconds. The compliance team signed off because our actual RPO requirement was 4 hours.

"What about the schema-less fields?" Mapped them to a `JSONB metadata` column with a partial GIN index on the keys we filter by.

"What about the rollback path?" Dual-write for two weeks; old writes still hit Cosmos, reads stay on Cosmos until we declare parity. If anything goes wrong, flip the read flag back.

The team agreed.

### Result

Migration shipped over four weeks. Monthly cost dropped from ~$4K to ~$800. Read P95 latency improved from 80ms to 35ms because we stopped doing cross-partition queries. Zero data loss. The dual-write pattern became the template for the next two database migrations in our team.

---

## Technical depth — if they probe

- **Why Postgres won on this workload**: PK-plus-filter is what a B-tree was built for. Cosmos partitions on a hash; PK-plus-secondary-filter forces cross-partition fan-out.
- **JSONB schema strategy**: Two `JSONB` columns — `metadata` for known-flexible fields, `attributes` for fully arbitrary. Partial GIN indexes only on the keys we query by, not the whole document.
- **Dual-write window**: New writes go to both. Reads stay on Cosmos until parity check (row counts plus a sampled deep-equal) passes for three consecutive days.
- **Read replica in secondary region**: Postgres streaming replication, lag monitored on Grafana, alert at 10 seconds lag.

---

## Likely follow-ups

**Q: What if Cosmos had been the right tool?**
> If our reads were genuinely cross-partition and the schema was actually irregular, Cosmos would've stayed. The data said otherwise — 95 percent of our docs had the same shape and our reads were PK-driven.

**Q: How did you handle the compliance pushback on DR?**
> Asked compliance for the actual RPO/RTO numbers in writing. They came back with 4 hours / 1 hour. Postgres streaming replication with sub-10-second lag is well inside both.

**Q: What did the migration weekend look like?**
> Boring, on purpose. Two-week dual-write window, parity checks running daily, read flag flipped on a Tuesday at 11 AM. We watched dashboards for an hour, didn't see anything, went to lunch.

**Q: What's one thing you'd do differently?**
> I'd have added a feature flag at the repository layer from day one, not the application layer. Made the cutover cleaner.

---

## What NOT to say

- "Cosmos is bad" — it's a tool. Wrong tool for this workload.
- Don't overstate savings — $4K to $800 is real; don't multiply by 12 and call it "annual savings of X."
- Avoid bragging about the team accepting it. The proposal accepted itself once the data was on the page.

---

## Backup story (if asked for another)

At GCC, the Coffee SaaS API was supposed to use a single Postgres for everything. I benchmarked the actual analytics queries — 30-second response times on follower-growth lookups. Pitched a dual-database design: Postgres for transactional reads, ClickHouse for analytics, with dbt syncing materialized views. Took it to my CTO with the benchmark numbers; he signed off the same meeting. Analytics queries dropped to under 12 seconds.
