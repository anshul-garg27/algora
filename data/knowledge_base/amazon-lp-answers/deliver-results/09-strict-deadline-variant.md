# Q: Same question again: Tell me about a time you handled tasks with a strict deadline.

> **LP**: Deliver Results
> **Primary story**: `W7 — DSD Notification System`
> **Backup story**: `P1 — Partner API Failure Rate`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Holiday receiving window approaching, late 2024. Direct Store Delivery — DSD — is when a supplier delivers to a store dock instead of a DC. Before our notification system, goods would sit on the dock for 2-4 hours until an associate happened to check. Customers walked past empty shelves while the inventory was 30 feet away. Product had asked for store-associate push notifications by a six-week deadline, ahead of the holiday rush. Miss it and we wait for the next major release train, which was three months out — past the holidays.

### Task

Ship real-time push notifications to 1,200+ associates across 300+ stores in six weeks. Plug into the existing DSC API, distribute via Kafka, push through Walmart's internal SUMO mobile platform.

### Action

I planned in two-week chunks instead of one big plan. Three chunks, six weeks. Each chunk had to ship something visible.

Chunk one — event pipeline. I added the Kafka publish path inside `NrtiStoreControllerV1` on the `/nrt/v1/directShipmentCapture` endpoint. The DSD lifecycle has five event types — PLANNED, STARTED, ENROUTE, ARRIVED, COMPLETED. The biggest call of the project happened here. I decided notifications would only fire on ENROUTE and ARRIVED. The other three were noise. PLANNED is "we exist." STARTED is "truck is loading." COMPLETED is "delivery is done, you already saw it." If I notified on all five, the associate gets four alerts per delivery and silences the app inside a week. I validated that with two store-associate interviews and one Mexico-market manager call before locking it in.

Chunk two — SUMO integration. `SumoServiceImpl` builds the SUMO V3 Mobile Push payload. The audience object needed `countryCode`, `domain=STORE` (so DC and HO associates do not get paged), `siteId` (the specific store), and `roles` (the receiving team list, pulled from CCM config so I could change it without a deploy). The notification body — short, declarative. "{vendor} {trailer} has arrived at store" for ARRIVED. "{vendor} {trailer} is enroute with ETA {start}-{end}" for ENROUTE.

Chunk three — pilot and rollout. Week 5, US-only pilot behind a feature flag. I went to a store for a half-day shift to watch the notifications land in real life. One thing came out — my original message text was too long, the phones truncated it. Cut the format down to what shipped. Week 6, Mexico and Canada launch behind the same flag. Multi-market support was a config change, not code — site IDs and CCM blocks per market.

### Result

Shipped on the date. 500,000+ notifications across the next six months. Push delivery rate at 97%. Average latency 3.2 seconds from supplier API call to associate device. 35% improvement in stock replenishment timing — that is the resume bullet. 1,200+ associates, 300+ stores. Zero supplier-spam complaints because the email channel stayed targeted. Three additional Kafka consumers added in weeks 8, 10, and 12 — SMS, photo-upload, analytics — with zero changes to the DSC API. The decision that earned the date was the scope cut on event types. Notifying on 2 of 5 instead of all 5 is the lever that made six weeks possible.

---

## Technical depth — if they probe

- **Event filter**: Hard guard at the top of `sendSumoNotification` — feature flag check, then event-type check. Only ENROUTE and ARRIVED pass through. Rejected types logged for audit, never published.
- **SUMO audience**: `Site { countryCode, domain=STORE, siteId, roles=["receiving"] }`. CCM-driven role list, no deploy to change targeting.
- **Multi-market**: US=1, MX=2, CA=3. Factory pattern picks the right CCM config per market. Config delta only, 95% code reuse.
- **Event-driven extensibility**: SMS consumer added week 8, photo-upload week 10, analytics week 12. All consumed the same shipment events. Zero changes to DSC API.

---

## Likely follow-ups

**Q: What was the riskiest part of the timeline?**
> Week 5 pilot. The truncated message text I caught only because I went to a store. If we had shipped the wider rollout off the dev sandbox, associates would have got useless notifications.

**Q: Why a feature flag per market?**
> Compliance and rollback. Each market has its own legal review. If MX or CA flagged anything, US would not be impacted. We could disable any single market in CCM in seconds.

**Q: How did you decide which 2 events to notify on?**
> Two associate interviews and one manager call. PLANNED/STARTED have no associate action. COMPLETED is after the fact. ENROUTE prepares the dock, ARRIVED is "go now."

**Q: What did you defer to make the date?**
> SMS, photo-upload events, analytics consumers. All shipped in weeks 8-12. The event-driven design meant zero changes to DSC API for any of them.

---

## What NOT to say

- Do not say "we burned weekends." We did not. The scope cut was the lever.
- Do not skip the store visit. That is the customer-obsession beat that matters.
- Do not over-credit SUMO. It is Walmart-internal infra. Our integration was specific.

---

## Backup story (if asked for another)

P1 — PayU partner failure rate. Two weeks before partner SLA review, 4.6% failure rate vs 2% threshold. Bucketed the failures — two thirds were transient. Added idempotency keys, exponential-backoff retry, circuit breaker. Shipped in nine days. Failure rate dropped to 0.3% — 93% reduction. Partner offered a higher volume tier.
