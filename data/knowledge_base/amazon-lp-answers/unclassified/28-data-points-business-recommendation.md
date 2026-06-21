# Q: tell me about a time where you used some data points to make a business recomendation.

> **LP**: Customer Obsession / Are Right A Lot (hybrid)
> **Primary story**: `W7 — DSD Notification System`
> **Backup story**: `G1 — ClickHouse Migration`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

At Walmart Data Ventures, we were building the DSD (Direct Store Delivery) notification system. Suppliers send shipment events to our API in five states — PLANNED, STARTED, ENROUTE, ARRIVED, COMPLETED. The product spec said "push notifications to store associates for shipment events." That was vague.

### Task

Decide which of the five event types should actually trigger a push notification to associates. Too many notifications and they ignore all of them. Too few and we miss the operational point.

### Action

I started with what we had. Pulled six months of historical DSD event data from Hive — roughly 4.2 million shipment events across 300+ stores. Grouped by event type to see how often each fired per store per day.

The numbers were stark. PLANNED averaged 14 per store per day. STARTED averaged 12. ENROUTE was 11. ARRIVED was 11. COMPLETED was 11. If we pushed all five, that's ~60 notifications per associate per day — pure noise.

Then I went out to two stores in the Bay Area and asked associates what they actually needed to know. Two consistent answers. "When the truck is on its way so I can clear the dock." And "when it lands so I can go receive it." PLANNED and STARTED were back-office concerns. COMPLETED was after-the-fact.

So the data said ENROUTE plus ARRIVED, two events out of five. Cut from ~60 notifications down to ~22 per associate per day. Still high but actionable.

I wrote it up — historical event counts, the store visit notes, the proposed filter, and the math on associate fatigue. Took it to product and the store-operations lead. Product pushed back at first — "why not all five, more info is better?" I showed the per-store rate. He saw 60 notifications and got it.

For the message body I pulled supplier-name and trailer-number patterns from the same six months — those two fields were populated 99.4 percent of the time. ETA window was 87 percent. So the body became "Pepsi TRL-4521 is enroute with ETA 2:00 PM - 3:00 PM" with a fallback if ETA was missing.

### Result

Shipped with two of five events triggering pushes. Across 300+ stores and 1,200+ associates, replenishment timing improved by 35 percent in the first quarter — measured against the prior six months. Associates told the store-ops lead the notifications were useful, not noisy. The filter logic — only ENROUTE and ARRIVED — is now in production via `SumoServiceImpl`.

---

## Technical depth — if they probe

- **The filter**: `if (eventType == ENROUTE || eventType == ARRIVED) sendSumoPush(...)`. Lives in `SumoServiceImpl#sendSumoNotification`, gated by a CCM feature flag.
- **Audience targeting**: SUMO push goes to `Site(countryCode=US, domain=STORE, siteId=<store_nbr>, roles=[from CCM])`. Roles filter to the receiving team only.
- **Why not full ML personalization**: 4.2M events isn't enough variance for per-associate models, and the operational signal was clear from raw counts. Right tool, right time.
- **Fallback for missing ETA**: Template renders `"Pepsi TRL-4521 is enroute"` without the ETA clause when the field is absent. Tested with both populated and missing.

---

## Likely follow-ups

**Q: How did you measure the 35 percent improvement?**
> Compared average dock-to-shelf time in the six months after launch against the six months before. Same stores, same supplier mix. Walmart's internal ops dashboard provided the time-to-shelf metric.

**Q: Why did you visit stores instead of just looking at data?**
> Data told me ENROUTE and ARRIVED stood out structurally — those are the action-required transitions. The store visit confirmed associates agreed with that read. Data without the qualitative check is just numbers.

**Q: What if a supplier wanted PLANNED notifications too?**
> The filter is CCM-configurable per market. If a supplier in a specific store profile genuinely needed PLANNED, we could turn it on for that audience. Nobody asked.

**Q: How did you sell two-out-of-five to product?**
> Showed the 60-per-day number. He went from "more is better" to "this is noise we'd regret" in about 30 seconds. The numbers did the work.

---

## What NOT to say

- "Product was wrong" — product wanted more data per associate. The data showed it would backfire. Frame it as collaborative.
- Don't claim 35 percent improvement is solely from the notification. Acknowledge it's part of a broader change.
- "I made the call alone" — store-ops lead signed off; that's the right framing.

---

## Backup story (if asked for another)

At GCC, my recommendation to migrate from Postgres to ClickHouse was driven by data points — Postgres write latency had gone from 5ms to 500ms per row at 10M+ events/day, query times were 30 seconds for follower-growth lookups, and storage was 5x what it needed to be. I pitched the migration with a benchmark on 1 billion rows; got 5x compression, 2.5x query speedup, 30 percent infra cost drop.
