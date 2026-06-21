# Q: Describe a time you took action despite ambiguity.

> **LP**: Bias for Action
> **Primary story**: `W4 — "Make it resilient" multi-region work`
> **Backup story**: `W8 — Charles Proxy reverse-engineering`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Early 2025 at Walmart. The audit logging system was live and stable in EUS2. My skip-level dropped one sentence in a planning doc — "we need this to be resilient" — and tagged me as the owner. No RTO, no RPO, no budget, no timeline. The compliance and DR conversation was happening somewhere above me but hadn't reached the doc.

### Task

Figure out what "resilient" meant, design for it, and start moving. I had a quarterly OKR slot for it and I'd already burned a week waiting for clarity that wasn't coming.

### Action

I stopped waiting. I wrote down what I thought "resilient" meant — survives a regional Azure outage, recovers under an hour, loses less than a few hours of data — and went and got those numbers confirmed. Not in one big meeting. I scheduled three 20-minute 1:1s.

With our team lead: "If EUS2 goes dark for 6 hours, how long can the audit pipeline be down before suppliers complain?" His answer: "An hour is fine. A day is not."

With the compliance owner: "If we lose audit events for a window, what's the max acceptable gap before we fail an audit?" Her answer: "Four hours, documented."

With the platform team: "What does our Kafka multi-region setup actually support today?" Their answer: cross-region replication wasn't ready; if I wanted active/active I'd be running two independent clusters and reconciling at the sink.

That gave me RTO = 1 hour, RPO = 4 hours, and the constraint that I owned reconciliation. Not a spec from above — a spec I assembled from three conversations and wrote up in a one-pager.

Then I sketched three topologies — active/passive, active/active, hybrid — listed the cost, failover time, complexity for each, and recommended active/active. Sent the one-pager to the same three people. They approved by Friday.

The execution was 4 phases over 4 weeks — publisher to second region, sink to second region, validation week, cutover. Geographic routing using a `wm-site-id` header so each region only wrote records tagged with its own region.

### Result

15-minute RTO in the first failover drill — well under the 1-hour target. Zero data loss. The one-pager itself became the de facto requirements doc that two later projects copied. The thing that mattered most was the move on day 8 when I stopped waiting for a spec and went and built one.

---

## Technical depth — if they probe

- **Why active/active**: 30-minute active/passive failover broke the RTO. Active/active gives sub-second cutover via Azure Front Door.
- **Header-based routing**: `wm-site-id` is on every message. SMT filters in each region's Kafka Connect drop foreign-region records before GCS write.
- **Idempotent producer + dedup**: During dual-write windows, both regions could publish the same record. Producer-level idempotency, SMT dedup by `request_id`, and BigQuery `DISTINCT` at query time.
- **Parity validation**: Hourly row-count diffs for a full week before I trusted the cutover. Caught an 18-record gap that turned out to be 2MB gateway-limit drops — fixed before go-live.

---

## Likely follow-ups

**Q: Why didn't you just escalate and wait for a real spec?**
> I tried. The conversation was stuck two levels above me. Waiting was a choice and I made the other choice — go build the spec, get it sanity-checked, move.

**Q: What if the team lead had disagreed with your numbers?**
> The one-pager was a starting point for the conversation, not a fait accompli. If he'd said "no, RTO is 15 minutes" I'd have re-scoped to a different topology.

**Q: What was the riskiest assumption?**
> That compliance's "4-hour RPO" would survive a real audit. I asked for it in writing, got an email back. That email was my cover.

**Q: How did you know when "enough data" was enough?**
> When the cost of more investigation was bigger than the cost of a wrong decision. I had three stakeholder confirmations and a documented topology comparison. Going further was paralysis.

**Q: What would you do differently?**
> Write the one-pager on day 1, not day 8. I burned a week being polite about waiting for the spec.

---

## What NOT to say

- Don't pretend I had clean requirements — I built them.
- Don't say "I just figured it out alone" — three 1:1s. That's the work.
- Don't oversell — 15-min RTO is great, but it came from a concrete topology choice, not magic.

---

## Backup story (if asked for another)

Building the DC Inventory Search API, the upstream Enterprise Inventory team had no formal spec for their endpoints. Rather than block, I ran their staging APIs through Charles Proxy, captured request/response samples, reverse-engineered the contract, and wrote my own OpenAPI spec from it. Got the team to confirm the spec was right after I'd already started building.
