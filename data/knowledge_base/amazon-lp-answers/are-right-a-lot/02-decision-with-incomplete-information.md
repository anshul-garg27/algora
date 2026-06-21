# Q: Tell me about a decision you made with incomplete information.

> **LP**: Are Right, A Lot
> **Primary story**: `W4 — Multi-Region Resilience`
> **Backup story**: `W8 — DC Inventory Search API`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Mid last year my Walmart tech lead dropped a one-sentence ticket on me: "make the audit-logging service resilient." That was the entire brief. No RTO target, no RPO definition, no traffic budget, no preference between active/active and active/passive. The previous owner had left. The CRQ for multi-region rollout was on the calendar in 5 weeks.

### Task

I had to convert "make it resilient" into a concrete architecture and ship it.

### Action

I gave myself two days to make the brief concrete before writing any code.

I started by reading the existing system. Kafka cluster in EUS2 (East US 2), GCS sinks already deployed there. SCUS (South Central US) was sitting there empty. The `audit-api-logs-srv` had one `kafkaTemplate` pointed at EUS2. No failover code, anywhere. I tested the failure mode in stage by killing the Kafka primary — the publisher returned the error to the caller and the API failed. Not resilient.

Then I made the numbers concrete. I went to the supplier-experience team and asked "if audit data is delayed by 30 minutes, do you care?" Answer: yes, BigQuery dashboards drive their daily check-ins. "What about 24 hours of total downtime?" Answer: no, audit is best-effort. So I wrote it down: RPO = 30 minutes, RTO = 24 hours formal but we target 15 minutes. I sent that doc back to my lead. He said "yes, that's what I meant."

I picked active/active because RPO of 30 minutes is hard to hit with active/passive (failover detection alone burns 10-20 minutes). I added a secondary `kafkaSecondaryTemplate` pointed at SCUS. The publisher chains `CompletableFuture` properly: primary first, `.exceptionally()` triggers `handleFailure()` which sends to secondary and `.join()`s.

The thing I almost missed: I added geographic routing via the `wm-site-id` header so US-origin events prefer EUS2, Mexico-origin prefer SCUS. Limits duplicate fan-out in the steady state.

I rolled it out with Flagger canary, 5 weeks of soak, dual-region in production by March.

### Result

We achieved 15-minute recovery on the next real outage — well under our 1-hour RTO target. The CompletableFuture change uncovered an existing bug in the publisher's old `ListenableFuture` failover logic — exceptions were being swallowed and secondary was never tried. Fixing that was a bonus from doing this properly. The RTO/RPO doc became the template for two other teams' resilience reviews.

---

## Technical depth — if they probe

- **RTO vs RPO**: RPO = max data loss tolerated (30min for us). RTO = max recovery time (24h formal, 15min achieved). The brief had neither — I derived them from supplier-experience interviews.
- **Active/active over active/passive**: active/passive has detection overhead (10-20 min) and "is the standby healthy" risk. Active/active fails over in seconds; cost is 2x infrastructure.
- **CompletableFuture failover chain**: `kafkaPrimaryTemplate.send().exceptionally(ex -> handleFailure().join()).join()`. The old code returned `null` in `.exceptionally()` and the secondary was never tried.
- **Geographic routing**: `wm-site-id` header on the producer side, SMT filter on the sink side routes to per-country GCS buckets. Limits cross-region duplicates.
- **Dedup at query**: Kafka idempotent producer prevents duplicates within a region; `request_id` (UUID) dedupes at the query layer for cross-region overlap. Worst case is dup, never loss.

---

## Likely follow-ups

**Q: What if you'd guessed wrong on RTO?**
> The doc was reviewable. I sent it to the lead and supplier-experience before building. If they'd said "actually 5 minutes RPO," I'd have re-designed — probably toward synchronous dual-write. Getting the numbers in writing was the cheap way to find out I was wrong before spending 5 weeks coding.

**Q: How did you handle the duplicate-publish risk?**
> Three layers. Geographic routing limits steady-state overlap. Kafka idempotent producer prevents intra-cluster duplicates. `request_id` UUID dedups at the BigQuery query layer with `SELECT DISTINCT request_id`. Worst case: a row is duplicated, never lost.

**Q: What didn't you know that you wish you had?**
> Real production traffic distribution between US, CA, MX. I assumed it was uniform; it wasn't — US dominates. If I'd known I'd have right-sized SCUS smaller initially and saved cost.

**Q: How did you decide it was time to ship instead of gathering more info?**
> The 5-week deadline was real. After two days of clarifying the brief I had 80 percent of what I needed. The remaining 20 percent (traffic distribution, actual outage frequency) would have been answered by shipping and watching, not by more meetings.

**Q: What would you do differently?**
> I'd have written the RTO/RPO doc on day one, not after reading the code. Anchoring the conversation to numbers up front would have saved a few back-and-forth threads.

---

## What NOT to say

- Don't claim "I just figured it out" — the gap was clarifying the brief with the right people. Pretending it was solo intuition is dishonest.
- Don't oversell active/active — it's 2x infrastructure cost; the choice was justified by RPO, not because it's universally better.
- Don't skip that the migration uncovered an existing bug — that's the strongest signal the work was needed.

---

## Backup story (if asked for another)

At Walmart I built the DC Inventory Search API with another one-paragraph brief — "let suppliers query DC inventory in bulk, US/CA/MX, design for Brazil later." No spec, no specific volume estimate, no error semantics defined. I started with design-first OpenAPI — 898 lines — and asked the consumer team to review it as a contract before I wrote any Java. The spec review surfaced the partial-success requirement (always-200, per-item status) that I would have missed and had to retrofit later.
