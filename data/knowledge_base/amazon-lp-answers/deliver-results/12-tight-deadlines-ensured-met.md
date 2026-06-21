# Q: Tell me about a time you faced tight deadlines and how you ensured they were met.

> **LP**: Deliver Results
> **Primary story**: `W7 — DSD Notification System`
> **Backup story**: `P1 — Partner API Failure Rate`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Late 2024 at Walmart Data Ventures. Product came in with a six-week ask — real-time push notifications to store associates when DSD shipments are inbound or on dock. DSD is when suppliers like Pepsi deliver directly to a store dock instead of a DC. The window was tight on purpose — they wanted it live before the holiday receiving spike. Miss the window and we wait for the next major release train, which was past the holidays. The audience was 1,200+ associates across 300+ stores in three markets — US, Canada, Mexico.

### Task

Build the notification system end-to-end inside six weeks. Integrate with the existing DSC API, distribute via Kafka, push through Walmart's internal SUMO mobile platform.

### Action

Three mechanisms made the date.

First mechanism — scope cut before scope creep. The DSD lifecycle has five event types: PLANNED, STARTED, ENROUTE, ARRIVED, COMPLETED. The natural ask was "notify on all of them." I pushed back hard. PLANNED is "shipment exists." STARTED is "truck is loading." COMPLETED is "you already saw this." None of those change associate behaviour. Only ENROUTE (prepare the dock, ETA window incoming) and ARRIVED (go to dock now) trigger an action. I went to two stores, sat next to associates for half a shift each, and confirmed that read. Then I locked the scope at 2 of 5 event types and told the team that was the boundary.

Second mechanism — two-week visible chunks. I broke the six weeks into three chunks. Each one had to ship something demoable on Friday.

Chunk one (weeks 1-2): event pipeline working. I added the Kafka publish path inside `NrtiStoreControllerV1` for the `/nrt/v1/directShipmentCapture` endpoint. By end of week 2, supplier events were flowing through Kafka and the consumer was logging them.

Chunk two (weeks 3-4): SUMO integration. `SumoServiceImpl` built the push payload. Audience targeting via `Site { countryCode, domain=STORE, siteId, roles }`. Role list pulled from CCM config so I could change targeting without a deploy. By end of week 4, US-only flag on, push notifications were landing on test devices.

Chunk three (weeks 5-6): pilot and rollout. Week 5, US pilot in one store. I went there for a half-day to watch notifications actually land. Caught a message-truncation bug — the body was too long, phones cut it off. Trimmed it to "{vendor} {trailer} has arrived at store." Week 6, Mexico and Canada launches behind the same feature flag, factory pattern handling the per-market config.

Third mechanism — feature flag everywhere. Every market, every event type, the whole consumer behind a CCM flag. If anything went wrong in MX or CA, US stayed clean. I could disable any combination in seconds without a deploy.

I did a Friday demo to product every week. Two slides, five minutes, working device showing real notifications. They could course-correct early instead of at week 6.

### Result

Shipped on the date. 500,000+ notifications in the first six months. Push delivery rate 97%. Average latency 3.2 seconds from supplier API call to associate device. 35% improvement in stock replenishment timing. Zero supplier-spam complaints because the targeting stayed tight. Three more Kafka consumers added in weeks 8, 10, 12 — SMS, photo-upload, analytics — with zero changes to DSC API. The lever that made the date was the scope cut on event types in week one. If I had tried to ship five event types, we would have missed both the date and the associate's trust in the app.

---

## Technical depth — if they probe

- **Event filter**: Hard guard at top of `sendSumoNotification` — feature flag check, then event-type check. Only ENROUTE and ARRIVED proceed. Rejected types audit-logged.
- **SUMO audience**: `Site { countryCode, domain=STORE, siteId, roles=["receiving"] }`. CCM-driven roles, no deploy to change.
- **Multi-market factory**: US=1, MX=2, CA=3. `SiteConfigFactory` picks the right CCM block. 95% code reuse, config-only delta per market.
- **Event-driven extensibility**: Adding SMS in week 8, photo-upload week 10, analytics week 12 — all new Kafka consumers. Zero changes to DSC API source code.

---

## Likely follow-ups

**Q: What was the riskiest part of the timeline?**
> Week 5. The truncated message text I caught only by being in a store. Sandbox test devices would have shown it but I had assumed the format would render fine. Real device, real shift, real catch.

**Q: How did you communicate progress to product?**
> Friday demo, every week, two slides max. Working device showing actual notifications. They never had to ask for status.

**Q: What did you defer to make the date?**
> SMS, photo-upload events, analytics consumers. All shipped weeks 8-12 as additional Kafka consumers. Event-driven design meant no source changes to DSC API.

**Q: Why is feature-flag-everywhere worth the overhead?**
> Surgical rollback. One bad market or one bad event type does not blow up the whole feature. CCM flip is seconds, not minutes.

---

## What NOT to say

- Do not say "we worked nights." We did not. The plan was tight, the scope cut was the lever.
- Do not skip the in-store visit. That is the customer-obsession beat.
- Do not over-credit Kafka. Kafka was the transport, the scope discipline was the work.

---

## Backup story (if asked for another)

P1 — PayU partner failure rate. Two weeks before partner SLA review, 4.6% failures vs 2% threshold. Bucketed the failures — two thirds were transient or self-inflicted. Added idempotency keys, exponential-backoff retry, circuit breaker. Shipped in nine days. Failure rate dropped to 0.3% — 93% reduction. Partner offered a higher volume tier.
