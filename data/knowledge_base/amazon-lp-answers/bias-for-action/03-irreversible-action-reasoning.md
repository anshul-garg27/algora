# Q: Tell me about an irreversible action you took — what was the reasoning?

> **LP**: Bias for Action
> **Primary story**: `W4 — Multi-Region Active/Active Cutover`
> **Backup story**: `G1 — ClickHouse Dual-Write Cutover`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

At Walmart, our supplier-facing audit logging system had been running single-region in EUS2 for about six months. Leadership wanted multi-region for DR — the brief from above was vague, just "make it resilient." A regional Azure outage on a Monday morning would mean Pepsi, Coca-Cola and Unilever couldn't query their API logs. The compliance team had also flagged it.

### Task

Cut over from single-region Kafka to active/active across EUS2 and SCUS without breaking the existing flow. The hard part: once you've published a record to two clusters and started consuming from both, you can't quietly "rollback" — the order topology has changed, downstream offsets have moved, the GCS sink buckets have new partition keys. That last 1% step was the irreversible one.

### Task

My slice was the whole rollout. Define what "resilient" actually meant, pick the topology, and own the cutover.

### Action

I started by nailing the numbers. Pulled the team lead and the compliance owner into a 30-minute call: "How much data loss is OK? How long can we be down?" Got RPO = 4 hours, RTO = 1 hour written into a doc. That doc became the spec.

Three topologies on the table — active/passive, active/active, hybrid. Active/passive was cheap but failover took 30 minutes which broke RTO. Active/active doubled the infra cost but gave us automatic failover. Compliance couldn't tolerate a 30-minute window, so active/active was the call.

Now the cutover. I designed it in 4 phases over 4 weeks. Week 1, publisher writes to both clusters with primary EUS2 as the authoritative source. Week 2, GCS sink deployed to SCUS, both regions writing to bucket. Week 3, validate parity — I ran row-count diffs hourly between regions, spot-checked specific suppliers' records. Week 4, flip the consumer routing.

The actual irreversible moment was Week 4. Once both Kafka Connect workers were live and writing to the same GCS buckets, the data shape on disk changed — partition prefixes now included region. You can't "undo" written Parquet files. If something was wrong I'd be cleaning up GCS by hand for hours.

Before pulling the trigger I did two things. One, I ran one full week of parity checks — every Parquet file had a region tag and the union always matched the source Kafka topic. Two, I scripted the rollback — if I had to roll back, the script paused SCUS publishers, set SMT filters to drop SCUS records, and re-cut the routing. Not a real undo, but a "stop the bleeding" path.

Then I cut over on a Wednesday morning, not Friday evening — if it broke, I had four working days to fix it.

### Result

15-minute RTO measured in three subsequent failover drills, against a 1-hour target. Zero data loss. The pattern became the reference architecture for two other Walmart teams.

---

## Technical depth — if they probe

- **`wm-site-id` header routing**: Each message carries the originating region. SMT filters in each region's Kafka Connect drop foreign-region records before they hit GCS. Geographic routing without separate topics.
- **Idempotent producer + consumer dedup**: Both regions could publish the same record during the dual-write window. Idempotent producer on the Kafka side, dedup by `request_id` in the SMT, and BigQuery `DISTINCT` on the query layer. Three lines of defence.
- **Why Wednesday morning, not Friday**: Bias for action doesn't mean bias for stupid timing. Friday-evening cutover means weekend pager duty for a 4-week project.
- **Parity validation**: Hourly cron diffed `count(*) where wm-site-id='US'` between the two regions for a full week before I trusted the data path.

---

## Likely follow-ups

**Q: Why active/active and not active/passive?**
> Compliance set RTO at 1 hour. Active/passive failover was clocking 30 minutes — too close. Active/active is automatic — Azure Front Door just routes around the dead region.

**Q: What was the cost?**
> About 2x infra for the audit pipeline specifically. Justified against the cost of a compliance failure, which would have been an order of magnitude bigger.

**Q: How did you handle split-brain?**
> Each region only writes records tagged with its own `wm-site-id`. SMT filters drop anything foreign. Worst case is duplicates in BigQuery — not split-brain in the consistency sense.

**Q: What was the closest call?**
> Week 3 parity check showed an 18-record gap one hour. Turned out to be the publisher dropping records that exceeded the 2MB gateway limit. I caught it because I was watching the diff. Without that hourly check, the cutover would have flipped on a silently-broken pipeline.

**Q: If you'd had to roll back, what would have happened?**
> Run the rollback script — pause SCUS publishers, drop SCUS records in SMT, route consumers back to EUS2 only. GCS files from the SCUS window would have been orphaned; I'd have cleaned them up by hand. Painful but bounded.

---

## What NOT to say

- Don't claim this was zero risk — irreversible means irreversible.
- Don't skip the rollback plan. Even an irreversible cutover has a "stop the bleeding" path.
- Don't pretend I had complete data — I had RPO/RTO numbers and chose to commit.

---

## Backup story (if asked for another)

At GCC, after a 2-week dual-write window between PostgreSQL and ClickHouse, I commented out the PostgreSQL `session.add()` calls in Beat. Once dbt models switched their reads, going back would have meant re-running 14 days of historical ingestion. I cut over because the parity checks and the spot-checks on top influencers had matched within 0.02% for a week.
