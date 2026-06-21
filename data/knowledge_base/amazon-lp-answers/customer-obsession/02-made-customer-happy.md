# Q: Tell me a time when you made customer happy.

> **LP**: Customer Obsession
> **Primary story**: `W7 — DSD Notification System`
> **Backup story**: `W6 — Supplier Self-Service`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Walmart has this thing called Direct Store Delivery — suppliers like Pepsi and Frito-Lay drive trucks straight to a store dock, skipping the distribution center. Before my work, no one at the store knew the truck was coming. The receiving associate would walk past the dock during a periodic check, see boxes sitting there, and start scanning. Goods would sit for hours. Customers walked past empty shelves while the product was 50 feet away in the back.

### Task

The asks from the receiving team was simple — "tell us when the truck is enroute and when it lands." Mine was to design the notification flow without spamming associates, because they already have a noisy device.

### Action

I built the notifier inside `cp-nrti-apis`. The DSD API already had five event types — Planned, Started, Enroute, Arrived, Completed. The naive answer is to push on all five. I went and watched a receiving associate's handheld for an hour. They were already getting alerts every few minutes from other systems. Five DSD pushes per truck would be ignored within a week.

So I shipped a hard filter: only ENROUTE and ARRIVED trigger a SUMO push. The other three persist to Kafka for audit but stay silent. Defined that as a constant in the enum — `SUMO_NOTIFICATION_ENABLER = List.of(ENROUTE, ARRIVED)` — so adding or removing a trigger is one line.

Then I made the message actually useful. ENROUTE shows the commodity type, trailer number, and the ETA window converted to store-local time. ARRIVED says "Beverage TRL-4521 has arrived at store" — short enough to read while walking.

I added a CCM feature flag — `isSumoEnabled` — so if SUMO has an outage we kill notifications instantly without redeploying anything. The DSD event still flows to Kafka, only the push is skipped.

### Result

1,200-plus associates across 300-plus stores now get sub-5-second alerts when a DSD truck is on the way and when it lands. The operations team measured a 35% improvement in replenishment timing — that's the gap between the ARRIVED event and the inventory scan. The receiving team lead pinged my manager directly. Something like "we used to find out about deliveries from the smell of the dairy truck." That message stuck with me more than the percentage did.

---

## Technical depth — if they probe

- **SUMO targeting**: Audience model is hierarchical — `countryCode` → `Domain (STORE)` → `siteId` → `roles`. Only the receiving team at the exact store gets the push. Store 4236 in Texas doesn't get a Store 4811 ETA.
- **Why two events not five**: Notification fatigue. PLANNED and STARTED need no action. COMPLETED is too late. ENROUTE = prep, ARRIVED = act. That's it.
- **Timezone conversion**: Suppliers POST timestamps in UTC. Associates need "2:00 PM" in their local time. `SumoHelper.getAmPmFromTimeZone()` does the conversion against a store-to-timezone map.
- **Kafka + SUMO dual write**: SUMO is fire-and-forget. Kafka persists the event regardless. If SUMO fails I still have the event for replay and audit. `SignatureHandleException` is logged but never propagated.
- **CCM commodity mapping**: `PEPSI-001` → "Beverage", `FRITO-LAY` → "Snacks", default → "DSD". Ops can add a new supplier without a deploy.

---

## Likely follow-ups

**Q: How do you know associates aren't ignoring these notifications?**
> Honestly, we don't have open-rate tracking on SUMO yet. The 35% replenishment metric is our proxy — if they were ignoring pushes, the gap between arrival and scan wouldn't have moved. Open-rate is the thing I'd add next.

**Q: What if SUMO goes down?**
> Two safety nets. The push call is wrapped in try-catch for `SignatureHandleException` — fails silently, logs, never affects the supplier's API response. And `isSumoEnabled` is a CCM flag, so I can kill all push traffic in under a minute without a deploy.

**Q: Why SUMO and not SMS?**
> SUMO is Walmart's internal push platform — free, sub-5-second, targets by role. SMS would cost per message, can't filter by role, and associates don't carry personal phones on the floor.

**Q: What did you wish you'd built differently?**
> A delivery confirmation button in the push. Right now I notify on ARRIVED but don't track when the associate actually starts scanning. Closing that loop would let us measure the full chain.

---

## What NOT to say

- Don't say I measured the 35% myself — the business ops team owns that dashboard. I built the pipeline, they measured the outcome.
- Don't claim "real-time" without the latency number. Sub-5-second is the honest answer.
- Don't oversell the visit to the dock — I watched the handheld for an hour, I didn't shadow a full shift.

---

## Backup story (if asked for another)

The supplier audit logs work. Pepsi's engineer spent two days debugging a failed API call. After I added Parquet + BigQuery external tables with row-level security on `consumer_id`, the same kind of failure takes 30 seconds to find. Suppliers like Pepsi and Unilever query their own data now — first time they've had that with a vendor.
