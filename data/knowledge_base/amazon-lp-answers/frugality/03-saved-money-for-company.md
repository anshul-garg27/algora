# Q: Describe a time you saved money for the company.

> **LP**: Frugality
> **Primary story**: `W1/W2 — Splunk replacement (audit-logging $50K/mo → $500/mo)`
> **Backup story**: `G1 — 30% infra cost cut + 5× compression`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

At Walmart Luminate, two things landed in the same quarter. Walmart was decommissioning Splunk company-wide — enterprise licence wasn't being renewed, and the audit-logging part of that bill alone was around $50K/month for our slice. Separately, external suppliers like Pepsi and Coca-Cola were asking for visibility into their API interactions. The two problems had the same shape: durable, queryable log storage.

### Task

Replace Splunk for our internal debugging and unlock supplier self-serve. Without renewing the licence. Without impacting our sub-200ms API SLA.

### Action

The expensive answer was Datadog or another commercial log-aggregation tool. I sketched the cost — at our 2M events/day volume Datadog priced at roughly $30K/month for the same retention. Cheaper than Splunk, not cheap.

I built a custom three-tier pipeline instead. Tier 1 was a shared Spring Boot library — `dv-api-common-libraries` — that any service could pull in as a Maven dependency. It had a servlet filter, ContentCachingWrapper for the body, and an `@Async` audit-log call. Zero new application code for any consuming service. Tier 2 was a Kafka producer service (`audit-api-logs-srv`) that serialised to Avro (70% smaller than JSON) and published to multi-region Kafka. Tier 3 was a Kafka Connect sink with custom SMT filters writing Parquet to GCS, partitioned by service/date/endpoint.

On top of that I added BigQuery external tables on the GCS Parquet — no data movement, BigQuery just reads the files. With row-level security per `consumer_id`, suppliers self-serve queries.

The economics worked because each component was either cheap by design or already paid for. GCS at ~$0.02/GB is dirt cheap for Parquet. BigQuery only charges per query (~$5/TB scanned), and columnar Parquet makes those queries small. Kafka was already running. Zero per-event cost like Splunk had.

I ran it as a pilot on one service first — measured cost, measured latency impact (zero, async fire-and-forget), measured query speed. Then rolled it to 12 services over 8 weeks.

### Result

Audit logging cost went from ~$50K/month (Splunk slice) to about $500/month — $60 GCS + BigQuery query budget, the rest in Kafka and the producer service shared with other workloads. 99% reduction. Annual savings on the order of $600K for our scope. Suppliers self-serve in 30 seconds instead of waiting 2 days for support. 12 services adopted. Zero latency hit. The pattern got picked up by the Walmart Platform team as reference architecture.

The thing I'd flag: the savings number is real but the headline 99% is partly because Splunk's price was crazy for our use case. Even Datadog would have been a 60% cut. The win was not picking a category-leader tool for a problem that didn't need one.

---

## Technical depth — if they probe

- **Why GCS + Parquet, not raw JSON**: 90% compression vs JSON, columnar reads in BigQuery, native external-table support. Cheap and queryable.
- **Why Avro on Kafka, not JSON**: 70% smaller on the wire, schema enforcement, registry-backed evolution.
- **Why Kafka Connect, not a custom consumer**: Built-in offset management, retry, exactly-once semantics with idempotent sinks. I didn't want to maintain a consumer.
- **Shared library**: Servlet filter + `@Async` + `ContentCachingWrapper`. Zero application code change to integrate. Maven dependency + CCM config and you're done.
- **Async/fire-and-forget**: API latency stays zero-impact. Audit failure never blocks the customer request.

---

## Likely follow-ups

**Q: Did you compare against Datadog or ELK?**
> Yes. Datadog was ~$30K/month; ELK self-hosted would have been similar in infra + dedicated ops time. Custom on GCS + BigQuery was cheaper than both because we weren't paying per-event ingestion.

**Q: How did you avoid hidden costs?**
> BigQuery slot reservations vs on-demand was the big one. We stayed on-demand because supplier query patterns were bursty. Parquet partitioning kept scanned data small.

**Q: Latency impact?**
> Zero on the API path. Async fire-and-forget with `@Order(LOWEST_PRECEDENCE)` so the filter runs after the response is built.

**Q: Compliance / retention?**
> GCS bucket retention set to 7 years. Splunk had 30 days because storage was expensive; we got better retention for less money.

**Q: What's the catch?**
> Supplier-facing query UX is SQL, not a UI. We documented it; for our supplier audience that was fine. A UI would have been the next $50K of work we didn't do.

---

## What NOT to say

- Don't claim "I saved $600K" without context — Splunk's pricing was the comparison.
- Don't oversell custom-built tooling — for most companies, the right answer is to buy.
- Don't skip the supplier-self-serve angle. The cost story is half of it; the UX win is the other half.

---

## Backup story (if asked for another)

ClickHouse migration at GCC. 30% infrastructure cost cut and 5x compression on log data (500GB → 100GB). The frugality there was operational, not capex — I used the RabbitMQ already in production and added log consumers to event-grpc instead of standing up a new service. No new tooling for the 5-person team to operate.
