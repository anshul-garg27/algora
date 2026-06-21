# Q: Describe a complex technical problem you solved in your past experience.

> **LP**: Dive Deep
> **Primary story**: `W1 — Silent Kafka Failure`
> **Backup story**: `W8 — DC Inventory Search API`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

The audit pipeline I'd shipped six weeks earlier looked perfect on dashboards. Sub-200ms API latency. No alerts. But on a routine cross-check I ran in April 2025, the API Proxy request count and the Hive record count were off by 40,000 to 130,000 records per day. We were silently losing audit data — the kind suppliers like Pepsi were supposed to query for their own debugging.

### Task

Figure out where in the three-tier pipeline records were vanishing. Cp-nrti-apis → audit-api-logs-srv → Kafka → GCS sink → Hive. Five hops, no alarms.

### Action

I walked the data backwards. Hive missing records — were they in GCS? Some yes, some no. GCS Parquet files were short. Were they in Kafka? Topic counts matched the API Proxy upstream side. So the loss was between the API Proxy gateway and the audit publisher.

I added a request-count metric at each hop and ran a load test. The diff showed up between the gateway and the publisher controller — the request never made it to my service.

I pulled the API Proxy access logs. The pattern was clear: every dropped request was on the inventory-status endpoint with response payloads bigger than 1MB. 413 Payload Too Large. The gateway had a default 1MB cap. Large inventory responses — hundreds of items — were being chopped before they ever reached the audit publisher. The audit was supposed to capture the full response. It was capturing nothing.

The fix was a two-line config: `APIPROXY_QOS_REQUEST_PAYLOAD_SIZE: 2097152` — 2MB. PRs #49, #50, #51 across the three impacted services. I deployed it the same day through Flagger canary at 10% → 50% → 100%.

But the real fix was structural. I added a request-count metric at every tier boundary and an alert on cross-tier divergence over 0.1%. So if the same shape ever showed up again, we'd know in minutes, not in an April spreadsheet.

### Result

After the 2MB rollout the API Proxy count matched the Data Discovery count exactly. Zero data loss going forward. The cross-tier divergence alert has fired once since — caught an unrelated networking issue in 15 minutes. The learning that stuck: monitoring inputs doesn't tell you outputs are correct. You have to validate at every tier boundary.

---

## Technical depth — if they probe

- **Why I cross-checked counts in April**: My PR description discipline. Whenever I deploy something with downstream consumers, I add a "post-launch verification" todo for two weeks out. This was the second one of those.
- **Why API Proxy had a 1MB default**: It's a Walmart platform-wide gateway shared by hundreds of services. Default is conservative. Each service can override but most don't think about it.
- **The metric I added**: A simple Prometheus counter per service: `audit_pipeline_records_total{stage="gateway|publisher|kafka|gcs|hive"}`. The alert is on ratio drift between adjacent stages.
- **Why three PRs, not one**: Three services each owned their own gateway config. Same fix, but each had its own canary, its own CRQ ticket, and its own owner approval.

---

## Likely follow-ups

**Q: Why didn't unit tests catch the 413?**
> Unit tests stubbed the gateway. The gateway's 1MB cap was a runtime config, not a code path. The only thing that would have caught it was a load test with realistic large payloads — which I now run on any audit-emitting service.

**Q: Did anyone notice the loss before you did?**
> No. That's what made it bad. Suppliers querying their own data wouldn't know they were missing 5-7% of inventory-status records. Internal teams treated the dashboards as ground truth.

**Q: How do you handle a similar situation now?**
> Cross-tier metrics by default. Any pipeline I ship has counters at each hop and an alert on divergence. It's in our common library now — teams get the metrics for free.

**Q: What was hardest about the debug?**
> Resisting the urge to instrument my own service first. The loss wasn't there. I had to back up one hop at a time. The discipline was "follow the data, don't follow the code I wrote."

---

## What NOT to say

- Don't frame this as a heroic debug — frame it as a discipline that caught a real bug.
- Don't say "we lost X records" without naming the range (40K-130K/day). Specifics make it credible.
- Don't blame the gateway team — the default was reasonable; we should have known our payload sizes.

---

## Backup story (if asked for another)

For W8, the DC Inventory Search API, the complex part wasn't the happy path — it was the bulk-error UX. A 100-item request can fail at three different stages: GTIN conversion, supplier auth, EI fetch. I built a RequestProcessor pipeline where each stage tags errors with a source (`UBERKEY`, `SUPPLIER_MAPPING`, `EI`), then reverse-converts GTIN errors back to the WmItemNumber the supplier sent. The consumer sees "12345 not mapped to supplier," not "00012345678905 not mapped." 1,903 lines of error-handling refactor, all so the API made sense from the supplier's seat.
