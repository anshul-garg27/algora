# Q: Describe a situation where you prioritized customer feedback over other priorities and the result.

> **LP**: Customer Obsession
> **Primary story**: `W6 — Supplier Self-Service (Pepsi debug-log finding)`
> **Backup story**: `W7 — DSD Notifications`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Last year at Walmart Luminate I was building the Kafka audit logging replacement for Splunk. The original ticket was internal-only — engineers needed somewhere to grep logs. Then a Pepsi engineer pinged my manager on Teams. He had been debugging a failing `/iac/v1/inv` call for two days. We finally pulled the audit row in 30 seconds and saw a stale OAuth token. Two days of his life for one line of data.

### Task

I was already mid-build. The internal team wanted the system done. But that 2-day debug pattern wasn't a one-off — Coca-Cola and Unilever had filed similar support tickets. I decided to expand scope so suppliers could self-serve before we shipped, not after.

### Action

I went back to my design doc and changed two things. First, the sink format. I had been planning JSONL on GCS because it was simpler. I switched to Parquet, because BigQuery can query Parquet external tables directly with no extra ETL.

Then the harder piece — row-level security. I sat with our data team for a morning. We added a BigQuery RLS policy keyed on `consumer_id`, so each supplier sees only their rows. The audit schema already had request body, response body, status code, error message. I kept it all in.

I wrote five sample queries — "show me my failed calls in the last week", "what's my P95 by endpoint", "why did this `request_id` fail". Sent them in the supplier onboarding email along with the BigQuery project link.

The cost was about a week of extra work. I told my manager I'd absorb it without slipping the Splunk cutoff date. He agreed.

### Result

Suppliers now debug their own API failures in about 30 seconds. The Pepsi engineer who started this loop told me it was the first time he'd had query access to his own data with any vendor. Internal support tickets for "why did my request fail" dropped sharply. I don't have the exact percentage — the support team owns that dashboard — but it's the kind of thing where if you'd shown me the Pepsi ticket six months earlier, the whole design would've started from there.

---

## Technical depth — if they probe

- **BigQuery external tables on Parquet**: GCS holds the Parquet partitions, BigQuery reads them in place. No ingest step, no duplicate storage. About 90% cheaper than loading into native BQ for our access pattern.
- **Row-level security on `consumer_id`**: The RLS policy is a `FILTER USING consumer_id = SESSION_USER()` pattern. Suppliers authenticate via Walmart's SSO, the session user maps to their `consumer_id`. No way for Pepsi to see Coke's rows.
- **Schema choice**: I included `request_body` and `response_body` as strings, not just status codes. That was the call that made self-service actually useful — most "why did it fail" answers live in the response body.
- **Why not let support handle it**: Support was already 1-2 day SLA on these tickets. Adding more suppliers would have made it worse. Self-serve scales.

---

## Likely follow-ups

**Q: How did you know suppliers actually wanted this and weren't going to ignore the BigQuery link?**
> The Pepsi engineer asked for it directly. Coca-Cola and Unilever had support tickets that all read the same way — "we need to see our own API logs." Three suppliers asking unprompted is a signal. I also socialised the sample queries in the onboarding email — if no one used them I'd know in a week.

**Q: What if a supplier wrote a query that scanned everything?**
> BigQuery slot quotas per project capped that. We also partitioned the Parquet by date, so the cheap queries hit one partition. Bad queries get expensive for them, not for us.

**Q: Did the extra week put anything else at risk?**
> The Splunk cutover date was the hard deadline. I rebudgeted by cutting a "nice-to-have" admin dashboard I was going to build for our team. We used BigQuery for our own queries too, so the dashboard became unnecessary anyway.

**Q: How did you measure success?**
> Support ticket count for "why did my request fail" and the time to first query by each supplier after onboarding. The first metric dropped, the second was usually same-day.

---

## What NOT to say

- Don't claim a specific support-ticket-drop percentage — the support team owns that dashboard, I have the qualitative signal not the number.
- Don't say "I built BigQuery" — I configured external tables and RLS, the data team owns the platform.
- Don't oversell the time saved per supplier — "2 days to 30 seconds" is the Pepsi case, not the universal number.

---

## Backup story (if asked for another)

DSD push notifications. Store associates at 300+ stores were discovering supplier deliveries during periodic dock checks — hours of lag. I built a real-time SUMO push pipeline triggered only on ENROUTE and ARRIVED, not all five DSD events, because notification fatigue would kill it. 1,200+ associates now get sub-5-second alerts. The operations team measured a 35% improvement in replenishment timing.
