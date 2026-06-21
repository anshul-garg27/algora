# Q: Tell me about a time you re-purposed existing tools instead of building new.

> **LP**: Frugality
> **Primary story**: `W6 — BigQuery external tables on existing GCS Parquet`
> **Backup story**: `W2 — Shared starter on existing Spring Boot + Maven`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

At Walmart, external suppliers like Pepsi, Coca-Cola and Unilever were asking for visibility into their API interactions with us. "Why did my request fail? Show me my history." The current path was painful — supplier emails support, support files a ticket, I or someone else greps the audit logs, screenshots the rows, replies. Two days of round-trips. The customer success team had been pushing for a real solution for months.

The obvious answer was a custom supplier portal — a frontend, an API, auth, query builder, the works. That's a 2-3 month project minimum.

### Task

Give suppliers self-serve access to their audit data. Without a 3-month build. Without standing up new infrastructure.

### Action

I looked at what we already had. The audit pipeline I'd built earlier — Walmart was decommissioning Splunk, so I'd already moved logs into GCS as Parquet. Multi-region, partitioned by service/date/endpoint, 7-year retention, columnar compression. That was sitting there doing nothing for suppliers because it was internal-only.

The unlock was BigQuery external tables. BigQuery can read Parquet directly from GCS — no data movement, no ETL, no second copy. I added external table definitions over the existing buckets in about an afternoon.

Then row-level security. Each row in the audit data already had a `consumer_id` column — the supplier's tagged identifier. I added a BigQuery `@policy_tag` on that column and wrote a row-level security policy: `FILTER USING (consumer_id = SESSION_USER_CONSUMER_ID())`. Each supplier sees only their rows. Tested with two test consumer IDs — no leakage.

The supplier interface ended up being BigQuery's console itself plus a one-page document with three sample queries: "show me my last 7 days of failures", "show me my P95 latency by endpoint", "show me requests for a specific trace ID." I documented the schema in a Confluence page. Total new code: zero. Total new infra: zero.

Then I piloted with one supplier on a Thursday, watched their query history for two hours (six queries, all clean, no permission errors), and rolled to two more suppliers the following week.

### Result

Pepsi self-served their first debug query in 30 seconds. The 2-day debug cycle went to near-zero for the three suppliers on the platform. Within a month, three suppliers were self-serving and the support team's ticket queue dropped noticeably. Total elapsed engineering time: one week. Total new infrastructure cost: zero (BigQuery on-demand pricing, supplier query volume negligible).

The thing that worked: I refused the "build a portal" framing. The data was already in a format BigQuery could query. The auth model was already in the data. The pieces existed. The work was wiring them.

---

## Technical depth — if they probe

- **External tables, not BigQuery-native**: External tables read Parquet directly from GCS. No data duplication. We already had the data right there.
- **`@policy_tag` + row-level security**: Column-level tag plus a row-level filter policy. Enforced at the BigQuery storage layer, not application-level. Supplier can't bypass it.
- **`consumer_id` was already in the data**: The audit library captured it from `WM_CONSUMER.ID` header. The piece I added was the policy that filtered on it.
- **No portal**: BigQuery console was the UX. For a SQL-literate supplier audience that was fine. A portal would have been the next $50K of work I didn't do.
- **Audit trail for free**: BigQuery query history captures who ran what. Compliance got that without me building it.

---

## Likely follow-ups

**Q: What if a supplier wasn't SQL-literate?**
> Most of our suppliers had analytics teams. For the few that didn't, the three sample queries plus a Confluence page covered 80% of needs. A portal would have been the right answer if the audience were less technical.

**Q: How did you make sure RLS actually held?**
> Tested with two consumer test accounts simultaneously. Each could only see their own rows. Pulled compliance in for a review before broad rollout.

**Q: What about cost runaway from supplier queries?**
> BigQuery on-demand at $5/TB scanned. Parquet partitioning keeps per-query scan small — a supplier's last-7-days query reads <1GB. Total monthly cost stayed under $100 across all suppliers.

**Q: Could you have used GCP-native authentication?**
> Walmart suppliers don't have GCP accounts. We provisioned service accounts per supplier and rotated keys via our existing IAM process. Existing tool, existing process.

**Q: What would you have built differently with budget?**
> A frontend with query builder UI. The SQL interface is functional but unfriendly. We had a plan to build it; we never had to.

---

## What NOT to say

- Don't oversell — the RLS work was BigQuery's feature, not my invention.
- Don't skip the existing-tools angle. The story is "I refused the new-build framing." That's the frugality.
- Don't pretend SQL is the right UI for every audience.

---

## Backup story (if asked for another)

When I built the shared audit library `dv-api-common-libraries` at Walmart, I didn't introduce a new build tool, framework, or auto-config system. I built it as a regular Spring Boot starter — `META-INF/spring.factories`, `@ComponentScan`, `@ConfigurationProperties` — using exactly the patterns every team already knew. Integration was one Maven dependency and 10-15 lines of CCM config. Three teams adopted in a month because there was nothing new for them to learn.
