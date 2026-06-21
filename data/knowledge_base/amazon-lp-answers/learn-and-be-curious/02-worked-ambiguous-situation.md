# Q: Describe a time you worked in an ambiguous situation.

> **LP**: Learn and Be Curious
> **Primary story**: `W4 — Multi-Region Rollout`
> **Backup story**: `W8 — DC Inventory Search API`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Early 2025. Leadership said: "Make audit logging resilient. We can't lose data if a region goes down." That was the entire ask. No RTO, no RPO, no budget, no preferred topology. Our audit pipeline ran in a single Azure region — EUS2. If EUS2 had a bad day, Pepsi and Coca-Cola supplier API audit trails would just stop.

### Task

Turn "make it resilient" into something I could actually design, defend, and ship.

### Action

I didn't start with code. I started with three questions for the compliance team and our SRE lead.

First — how much data can we lose in a disaster. They said zero on paper, but when pushed, accepted "less than 4 hours" because that's what their audit attestation could absorb. That gave me an RPO target.

Second — how fast must we recover. The number that came back was one hour. So RTO of 60 minutes.

Third — is the budget for 2x infrastructure approved. Yes, if compliance signs off.

I wrote those three assumptions into a one-page doc and circulated it. "I'm assuming RPO 4 hours, RTO 1 hour, 2x infra budget approved. Tell me where I'm wrong." Nobody pushed back. That doc became the de facto requirements spec.

Then I put three options on the table: Active/Passive, Active/Active, and a hybrid. I laid out failover time, cost, and complexity for each. Active/Passive was cheaper but had a 30-minute manual failover — that would blow RTO. Active/Active was 2x cost but had near-instant failover. I recommended Active/Active and explained why: audit is write-heavy, and a 30-minute gap during an outage was unacceptable for compliance.

The team agreed. I phased the rollout over four weeks — publisher to SCUS week one, GCS sink to SCUS week two, data parity validation week three, traffic split week four. Built `wm-site-id` header routing in the GCS sink connectors so each region wrote to its own bucket using a Single Message Transform.

### Result

Active/Active was live in four weeks. DR test gave us 15-minute recovery against a one-hour target. Zero data loss in production. Three other teams later copied the pattern for their own services. The lesson stayed with me — when requirements are vague, write down your assumptions and ask people to disagree. That's faster than waiting for a perfect spec.

---

## Technical depth — if they probe

- **wm-site-id routing**: Single Message Transform on Kafka Connect filters by header. EUS2 connector keeps `US`/null messages, SCUS keeps `CA`/`MX`. No duplicate writes between regions.
- **Dual Kafka publish**: `kafkaPrimaryTemplate.send().exceptionally(ex -> kafkaSecondaryTemplate.send())`. With `CompletableFuture` chaining, secondary fires automatically on primary failure. Old `ListenableFuture` code swallowed the exception — migration to `CompletableFuture` during the SB3 work actually fixed that bug.
- **RPO 4h / RTO 1h**: Picked from compliance, not engineering. RPO drives Kafka retention. RTO drives failover automation.
- **Why not Kafka MirrorMaker**: Active/Passive replication adds 1–5 minute lag. That alone blows the RPO target if we lose primary mid-replication.

---

## Likely follow-ups

**Q: What if compliance had said RPO zero, no excuses?**
> Then Active/Active dual-write is the only honest answer. Active/Passive can't give you zero RPO without synchronous replication, which is expensive and slow.

**Q: How did you get sign-off on the assumptions doc?**
> I shared it on Slack with compliance, SRE lead, and my manager. Asked for explicit "yes" or "tell me what's wrong." Two people came back with edits, the rest stayed quiet — that became the agreement.

**Q: What was the riskiest week?**
> Week three — data parity. We had both regions writing for a week, and I was comparing record counts daily. That's when I found the 413 Payload Too Large drops — 5–7% of audit events silently dropping. Fixed with a 2MB gateway limit before going to full traffic split.

**Q: Would you do anything differently now?**
> I'd add the gateway 2MB limit fix into week one, not discover it in week three. I now check payload size limits as part of any new Kafka pipeline design.

---

## What NOT to say

- Don't claim I owned the entire DR strategy alone. Compliance set the RPO/RTO, SRE owned Kafka cluster operations. I owned the publisher and sink design.
- Don't sell "make it resilient" as a heroic ambiguity. Many engineering tasks start vague. The point is the move from vague to specific.
- Don't recite cost numbers as if I controlled them — 2x infra was approved by leadership, not negotiated by me.

---

## Backup story (if asked for another)

DC Inventory Search API. Suppliers wanted a way to query DC inventory by GTIN, and there was no public API. The Enterprise Inventory team had no capacity to build one. No spec, no PM. I used Charles Proxy to reverse-engineer their internal endpoints, designed a 3-stage flow — GTIN to CID lookup, supplier authorisation check, then the EI call — and shipped in 4 weeks. 30K queries a day within two months. The ambiguity here was the same shape: you don't wait for a spec, you go discover what's actually there.
