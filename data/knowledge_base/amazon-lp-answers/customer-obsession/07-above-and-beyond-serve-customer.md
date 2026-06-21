# Q: Tell me about a time when you went above and beyond to serve customer.

> **LP**: Customer Obsession
> **Primary story**: `W6 — Supplier Self-Service (going beyond Splunk scope)`
> **Backup story**: `G6 — Fake-Follower ML`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

In early 2025 at Walmart Luminate, Splunk was being decommissioned company-wide. My team was asked to replace it for our supplier-facing APIs — internal engineers needed somewhere to grep request and response logs. The scope was strictly internal. Build the replacement, point our engineers at it, move on.

### Task

I owned the design. The expected output was "another internal log search tool." I could have shipped exactly that in a few weeks.

### Action

Before designing, I spent half a day in the supplier-success ticket queue. The pattern across Pepsi, Coca-Cola, and Unilever tickets was identical — "request X failed yesterday, can you tell me why?" Each ticket took 1-2 days to close. Our engineer would `grep` Splunk, paste back the response body and status code. Same exact data, every time.

That was the moment I decided the project wasn't just an internal log tool. The same data could go to the suppliers themselves. The internal scope was the floor, not the ceiling.

I redesigned around three additions on top of the internal spec.

First, output format. The original plan was JSONL on GCS — simple, internal-friendly. I switched to Parquet partitioned by date and country. Parquet is columnar, BigQuery can query it as an external table with no ingest step. That choice cost me about three extra days of work on the Kafka Connect SMT side, because the GCS sink needed proper schema management.

Second, supplier access. I worked with our data team to set up BigQuery external tables on the Parquet, with a row-level security policy on `consumer_id`. Each supplier sees only their own rows. The policy uses a mapping table — `supplier_id` to `consumer_id` — so a supplier with multiple business units sees them all.

Third, onboarding. I wrote five copy-paste BigQuery queries — "show me my failed calls last week", "P95 latency by endpoint", "trace this `request_id`". Bundled them in the supplier onboarding email along with the BigQuery project link. Without those queries, even with access, a busy supplier engineer might never use it.

I told my manager I was expanding the scope and would absorb the cost without slipping the Splunk cutoff. He agreed. The internal piece shipped on time. The supplier-facing piece shipped a week later.

### Result

Suppliers now debug their own failures in about 30 seconds instead of opening a ticket and waiting two days. The Pepsi engineer who'd been on the worst of those tickets pinged my manager directly — first time he'd had query access to his own API data with any vendor. Three other Walmart teams asked for the same supplier-access pattern after we shared it, and the BigQuery RLS approach got promoted as a reference architecture inside Walmart Platform.

The internal scope was the safe answer. The supplier-facing version is the one that actually changed the customer experience.

---

## Technical depth — if they probe

- **Parquet over JSONL**: Columnar storage with snappy compression. About 80% smaller on disk and BigQuery only scans the columns the query touches. Roughly $50/month BQ query cost vs. several hundred for JSONL.
- **BigQuery external tables**: GCS holds the data, BQ reads it in place. No duplicate storage, no ingest pipeline, suppliers query through the same SQL surface as internal teams.
- **Row-level security on `consumer_id`**: `FILTER USING consumer_id IN (SELECT consumer_id FROM supplier_consumer_map WHERE supplier_id = SESSION_USER_SUPPLIER())`. The mapping table is the lever — onboarding team owns it, no engineering needed when M&A or business-unit changes happen.
- **The five canonical queries**: Without these, even with access, the feature is dead. Most supplier engineers don't have the schema in their head and won't go hunting.

---

## Likely follow-ups

**Q: Wasn't expanding scope risky against the Splunk deadline?**
> The internal piece was the hard deadline. I sequenced it so the internal version was shippable first, then layered the supplier piece on. If I'd run out of time, the internal version still goes out and the supplier piece slips a week. I never put the deadline at risk.

**Q: Did you check with security before exposing supplier data?**
> Yes. The audit data is already supplier-owned data — it's their requests and responses. The legal question was about row isolation, which is what RLS solves. Security signed off on the policy design before I rolled it out.

**Q: How did you know suppliers would actually use it?**
> The Pepsi engineer asked for it in a ticket two months earlier. Coke and Unilever tickets had the same shape. Three suppliers asking is enough signal. I also tracked first-query-time per supplier after onboarding — most queried within a day.

**Q: What if a supplier wrote a query that scanned years of data?**
> BigQuery slot quotas per project capped that. The Parquet is partitioned by date so well-written queries hit one day. Bad queries get expensive for the supplier, not for us.

---

## What NOT to say

- Don't say I "rebuilt Splunk" — Splunk's replacement was the table stakes. The supplier piece is what makes this story.
- Don't oversell the support-ticket drop with a fake percentage. The qualitative signal — Pepsi engineer's reaction, three teams asking for the pattern — is honest.
- Don't claim I designed BigQuery RLS from scratch. I configured the policy against the platform.

---

## Backup story (if asked for another)

Fake-follower ML at GCC. Off my official backlog, on evenings and weekends. Brand customers were getting burned by inflated creators with bot followers. I built a 5-feature ensemble — Indic transliteration via HMM, custom Hindi mapping with 66 vowel and consonant rules, RapidFuzz fuzzy match against a 35,000-name Indian name database, digit count heuristics, non-Indic script detection. Runs on Lambda from SQS. Brands now see a real-vs-fake score before signing.
