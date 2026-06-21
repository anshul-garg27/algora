# Q: Tell me about a time when you had to understand a customer's needs deeply.

> **LP**: Customer Obsession
> **Primary story**: `W7 — DSD Notification System`
> **Backup story**: `W6 — Supplier Self-Service`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

The DSD project had a written PRD — "send notifications when DSD trucks arrive." Simple sentence. But the actual customer here was the store receiving associate, not the supplier, not my product manager. And I had no idea what their day actually looked like.

### Task

Before writing any code, I needed to figure out what notifications would help versus what would get muted within a week. The five DSD event types — Planned, Started, Enroute, Arrived, Completed — were all in the spec. The PRD was silent on which to push.

### Action

I asked the project owner to set up two calls with store receiving leads. Not interview-style — just "walk me through your morning." That ran about an hour each.

Two things I didn't know going in. First, associates already get push notifications from a stack of other Walmart apps — labor scheduling, pricing changes, recall alerts. Their handhelds buzz roughly every few minutes during a morning shift. Adding five DSD pushes per truck would have been the straw that broke notification trust. They told me directly: "If you push too much, we turn them off in settings."

Second, the receiving lead said the most useful information wasn't "the truck is here." It was "the truck is 30 minutes out." That's prep time — clear the dock, assign a person, get the pallet jack. The arrival notification matters too, but the ETA is what changes the workflow.

I went back and shipped a hard filter: ENROUTE and ARRIVED only. PLANNED and STARTED stay silent — they're informational, no associate action needed. COMPLETED is too late to matter. Defined as a constant: `SUMO_NOTIFICATION_ENABLER = List.of(ENROUTE, ARRIVED)`.

Then I dug into the message body. The receiving lead asked for two things — commodity type (so they know if it's frozen, needs immediate handling) and the trailer number (so they know which dock to walk to). UTC timestamps don't work for an associate on the floor. I wired up `SumoHelper.getAmPmFromTimeZone` against a store-to-timezone map so the ENROUTE push reads "ETA between 2:00 PM and 3:00 PM" in their local time.

One more thing they mentioned — receiving teams change. Roles get renamed. So I pulled the role targeting out of code and into CCM. Ops can change "receiving_team" to "receiving_team_v2" without a deploy.

### Result

1,200-plus associates across 300+ stores use it. 35% improvement in replenishment timing, measured by the operations team. The receiving lead I talked to during discovery has stayed in touch — he's the one who flagged the COMPLETED event for removal too. The thing I'm proudest of isn't the metric. It's that I didn't ship the obvious 5-event version of this.

---

## Technical depth — if they probe

- **The two-event filter as a constant**: `SUMO_NOTIFICATION_ENABLER` lives in `DscEventType.java`. Adding a new triggering event is one line — no switch-statement edits, no controller changes. Restraint baked into the structure.
- **Per-destination loop**: One shipment goes to multiple stores with different ETAs. I loop per destination so Store A gets its ETA in Pacific time and Store B gets its ETA in Central. Batching would have given everyone the same ETA — wrong for everyone except one store.
- **CCM role targeting**: Roles come from `SumoApiCCMConfig.getStoreRoles()`. Stores reorganise. Role names change. Code doesn't need to.
- **Commodity mapping in CCM, not code**: `PEPSI-001` → "Beverage", default → "DSD". Ops adds a new supplier without engineering involvement.

---

## Likely follow-ups

**Q: What did you do when you got conflicting feedback from different stores?**
> Two of the four leads I talked to wanted COMPLETED notifications. The other two said they'd ignore it. I went with the "no" because the cost of fatigue is global — if you train associates to ignore notifications at one store, that habit travels. We added COMPLETED to Kafka for audit, just not to SUMO.

**Q: How would you have validated this if you couldn't talk to associates?**
> Pull six months of receiving scan timestamps and look at the delay distribution between supplier ARRIVED events and the inventory scan. The data tells you where the lag is. Talking to people is faster.

**Q: How long did the discovery actually take?**
> Two calls, an hour each. Maybe three hours of synthesis after. Total under a day. The build was three weeks. Spending 5% of total project time on talking to the user changed at least two design decisions.

**Q: Were there competing priorities you had to push back on?**
> The original PRD said "send notifications on all events." My PM was fine with the filter once I explained the fatigue argument. The harder no was to the supplier side — Pepsi wanted a COMPLETED notification so they could close their books. I told them they can query Kafka or BigQuery for that, but it's not going to an associate's handheld.

---

## What NOT to say

- Don't say "I shadowed an associate's shift" — I joined two calls. Be honest about depth.
- Don't claim the 35% as my measurement — operations measured it.
- Don't make the discovery sound formal. It was two calls and one synthesis doc, not a research program.

---

## Backup story (if asked for another)

The supplier audit log work. The customer there is the external engineer at Pepsi or Coke debugging a failed API call. I learned what they actually needed by looking at the support ticket queue — every "why did my request fail" ticket needed status code, error message, request body, response body. I designed the Parquet schema with those four fields prominent and put it behind a BigQuery RLS policy on `consumer_id` so they could query their own rows. Two-day debug became 30 seconds.
