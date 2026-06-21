# Q: Describe a situation where a deep dive into data led to an unexpected discovery.

> **LP**: Dive Deep
> **Primary story**: `W6 — Supplier Self-Service`
> **Backup story**: `G4 — Dual-Database API`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

A Pepsi engineer pinged us in Slack: "Why is my IAC POST returning a 400 today? Worked yesterday." Standard supplier debug. Normally we'd grep Splunk, find the request, and reply in a day. But Splunk was being decommissioned across Walmart and we'd just stood up the new Hive-backed audit query path. I told him to give me an hour.

### Task

Find his request, find the failure cause, and figure out why the same request worked the day before. The supplier had real urgency — their pricing data wasn't flowing.

### Action

I ran the BigQuery external table on the audit logs partition for the last 48 hours, filtered to his consumer ID. The 400 was real. Error reason: "store_id 6018 not authorized." I looked at the prior day's logs — the same store_id was accepted. Same supplier, same endpoint, same store.

That was the unexpected bit. The authorization shouldn't be flaky. I pulled the consumer-to-DUNS-to-GTIN-to-store mapping table and noticed his entry had been touched 11 hours ago. Someone had reduced his store list as part of a quarterly access review and store 6018 had dropped off.

Then I looked sideways. I queried for any supplier hitting a 4xx on stores they used to access, in the last 30 days. The query took 1.2 seconds against the Parquet files in GCS. The number came back as 47 distinct suppliers, with a long tail of similar "I used to be able to do this" failures that never got reported because most teams shrugged it off as "must be wrong on their end."

The unexpected discovery: the access-review process was silently breaking integrations and we had no signal because Splunk wasn't queryable by suppliers. The new audit path made the pattern visible in one query.

### Result

I sent the data to our compliance team — 47 suppliers, named, with timestamps. They flipped the review process from "remove access by default" to "remove access with 30-day supplier notification." Two days later they shipped that change. Pepsi got their store back the same afternoon I dug in.

The deeper result was operational. Our supplier-facing 4xx rate had been creeping up 2% per quarter and nobody connected it to the access reviews. Once we had it on a dashboard, the trend reversed.

---

## Technical depth — if they probe

- **Why BigQuery external tables, not native**: We were already writing Parquet to GCS for the audit pipeline. External tables sit on top, no copy needed. Query cost is by data scanned, and Parquet column projection plus `wm-site-id` partition pruning kept a 30-day scan under 2GB.
- **The access pattern that exposed it**: `WHERE consumer_id = ? AND response_code BETWEEN 400 AND 499 AND error_reason LIKE '%not authorized%'`. Then a window function for "was this consumer-store combo successful in the prior 14 days?"
- **Why nobody saw this in Splunk**: Splunk SPL is hard for suppliers and even harder for cross-supplier pattern queries. SQL on Hive made the "47 suppliers" answer obvious.
- **Row-level security via BigQuery policy tags**: Each supplier sees only their own rows via `@policy_tag` on `consumer_id`. That's how we let them self-serve without exposing other suppliers' data.

---

## Likely follow-ups

**Q: How did you know to look at "stores that used to work"?**
> Pattern-matching from my Walmart Luminate context. Once one supplier reports "worked yesterday, broken today," I want to know if it's a one-off or a class. Cohort queries always tell you more than instance queries.

**Q: Was this a one-time finding or a recurring check?**
> It's now a scheduled BigQuery job that emails compliance weekly: "These suppliers lost access this week and have made attempts on the removed resources." Recurring deep dives are how you keep the dashboard honest.

**Q: What if you'd been wrong about the access review?**
> The data was unambiguous — store 6018 was in his mapping at T-12h and out at T-10h, with the audit-log proof. I sent the compliance team the row IDs and the change-history reference number. They confirmed in 30 minutes.

**Q: How long did the original supplier query take in Splunk?**
> Two days, typically. The SQL query took 1.2 seconds. The 99% cost reduction was the headline, but the speed unlocked the cross-cohort analysis nobody was running.

---

## What NOT to say

- Don't say "Splunk was bad" — it was fine for its era; we outgrew it.
- Don't take credit for the policy change — name compliance as the team that fixed it.
- Don't oversell "I found this in 5 minutes." The hour I asked for was real.

---

## Backup story (if asked for another)

For G4, building the Coffee SaaS API, I was sure a single Postgres database would handle both OLTP and analytics. After benchmarking the genre-insights queries, the data told me different: full-table scans on the time-series data took 8-12 seconds on PG even with partial indexes. Pulled the same data into ClickHouse — 800ms. The unexpected discovery was that the "premature optimization" instinct was wrong for analytics-heavy workloads. I flipped the design to dual-DB (PG for OLTP, ClickHouse for OLAP via `RequestContext.CHSession`) and the p95 came down 5x.
