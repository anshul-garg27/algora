# Q: Deadline-related: Tell me about a time you handled tasks with a strict deadline.

> **LP**: Deliver Results
> **Primary story**: `W7 — DSD Notification System`
> **Backup story**: `P1 — Partner API Failure Rate`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Late 2024 at Walmart. DSD — Direct Store Delivery — is when suppliers like Pepsi or Coca-Cola deliver straight to a store dock instead of through a DC. Before our system, goods would sit on the dock until an associate happened to check, sometimes 2-4 hours after arrival. Customers would see empty shelves while inventory was 30 feet away. Product gave us a six-week window to ship real-time notifications to store associates ahead of the holiday receiving window. Miss it and we wait three months for the next major release train.

### Task

Build push notifications to 1,200+ associates across 300+ stores in six weeks. Integrate with the existing DSC API, plug into Kafka for event distribution, and push through Walmart's internal SUMO mobile push platform.

### Action

I broke the work into two-week chunks instead of one big plan.

Weeks 1-2 — wire the event pipeline. I added the Kafka publish path inside the existing `NrtiStoreControllerV1` for the `/nrt/v1/directShipmentCapture` endpoint. The DSD lifecycle has five event types — PLANNED, STARTED, ENROUTE, ARRIVED, COMPLETED. I made a deliberate scope cut early: only ENROUTE and ARRIVED trigger notifications. The other three are noise. PLANNED is "we exist," STARTED is "truck is loading," COMPLETED is "done, doesn't help anyone." If we notified on all five, the associate gets four alerts per delivery and stops trusting the system. I confirmed that read with two associate interviews — one in a US store, one through a manager in the Mexico market — before locking it in.

Weeks 3-4 — SUMO integration. The push API needs an audience object — countryCode, domain (STORE/DC/HO), siteId, roles. I built `SumoServiceImpl` to extract the store number from the shipment payload, set domain to STORE so DC associates do not get the page, and pull the receiving-team role list from CCM config. CCM let me change the role list without a deploy.

Week 5 — pilot in one market. We rolled US-only first behind a feature flag. I sat next to two store associates for a half-day shift to watch the notifications land on their devices. One thing that came out — the body text I had was too long. Phones truncated it. Cut it to "{vendor} {trailer} has arrived at store" for ARRIVED and "{vendor} {trailer} is enroute with ETA {start}-{end}" for ENROUTE.

Week 6 — Mexico and Canada launch behind the same flag. Site IDs were the only config change. Multi-market support came from the same factory pattern the rest of the team already used.

We shipped on the date.

### Result

500,000+ notifications across six months. Push delivery rate at 97%. Average delivery latency 3.2 seconds from API call to device. 35% improvement in stock replenishment timing — that is the bullet. 1,200+ associates, 300+ stores. Zero supplier-spam complaints because email volume stayed targeted. The scope-cut decision early — only 2 of 5 event types — is the one that mattered. If I had tried to notify on all five, we would have missed the date and built a system associates would have muted inside a week.

---

## Technical depth — if they probe

- **Event filtering**: Hard guard at the top of `sendSumoNotification` — feature flag check, then event-type check. Only ENROUTE and ARRIVED pass. Logged the rejected types for audit, did not publish.
- **SUMO audience targeting**: `Site { countryCode, domain=STORE, siteId=4236, roles=["receiving"] }`. CCM-driven role list, no deploy to change the targeting.
- **Multi-market**: Site IDs US=1, MX=2, CA=3. Factory pattern picks the right CCM config block. Code reuse 95%, config-only delta per market.
- **Kafka decoupling**: Notifications are a downstream consumer of the same shipment event. Adding SMS later (week 8) and photo-upload (week 10) needed zero changes to DSC API.

---

## Likely follow-ups

**Q: How did you decide which 2 events to notify on?**
> Two associate interviews and one manager interview. PLANNED/STARTED have no associate action. COMPLETED is after the fact. ENROUTE prepares the dock, ARRIVED is "go now." Those are the two that change behaviour.

**Q: What did you cut to hit the date?**
> SMS support, photo-upload events, and analytics consumers. All shipped weeks 8-12 as additional Kafka consumers. Zero changes to DSC API because of the event-driven design.

**Q: How did you de-risk the rollout?**
> Feature flag per market, pilot in one US store, then one supplier in each new market, then full rollout. SUMO has its own deduplication and Redis-backed dedupe in our consumer.

**Q: What was the closest call?**
> Week 5 — the truncated message text I caught in the store. If I had not done the shift-along, we would have shipped a useless notification.

---

## What NOT to say

- Do not say "we worked nights and weekends." We did not. The plan was tight, the scope cut was the lever.
- Do not call SUMO the heroes. Walmart owns SUMO internally and our integration was specific.
- Do not skip the in-store visit. That is the customer-obsession beat that makes the story land.

---

## Backup story (if asked for another)

P1 — PayU partner API failure rate. Production failures sitting at 4.6% on disbursal, deadline two weeks before a partner SLA review. Added idempotency keys, exponential-backoff retries on transient 5xx, and a circuit breaker. Failure rate dropped to 0.3% — 93% reduction. Shipped in nine days.
