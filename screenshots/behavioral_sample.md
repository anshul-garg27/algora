## Took on something outside your defined role — Amazon (Ownership)
Story: W6 — Pepsi supplier self-service debugging · Amazon Ownership · ~100s. Backup if they want another: W5 (volunteering to lead the Spring Boot 3 migration).

### Situation
Early on at Walmart, my job was building and maintaining the supplier-facing data APIs. Nobody asked me to look at the support side. But I kept seeing the same thing in our logs — one big account, Pepsi, hammering us with re-queries every time they debugged a failed request.

### Task
This wasn't on my sprint board. But it was clearly broken, so I made it mine. I wanted to kill the round-trip — let suppliers debug their own data without going through Walmart support.

### Action
First I actually counted it. One debugging session from Pepsi was 50-plus repeated re-queries, because they had zero visibility into their own request history. Every round-trip went through our support team.

So I built BigQuery external tables over the audit data we were already dropping into GCS as Parquet. That meant suppliers could run plain SQL against their own data — no new pipeline, I reused what was already there.

The catch was security. Pepsi can't see Coca-Cola's rows. So I put row-level security on it with a policy tag on `supplier_id` — each supplier only sees their own data, enforced at the table.

> 💬 "Layman version: I gave suppliers a read-only window into their own request history, and locked it so each one can only see their own stuff."

I drove it end to end — noticed it, built it, secured it, handed it to the supplier.

### Result
A debug that used to take two days now takes about 30 seconds. And it freed up roughly 12 hours a week of our support time. None of it was assigned — I just saw the pattern and owned the fix.

**Technical depth — if they probe:**
- External tables = BigQuery queries the Parquet files sitting in GCS directly; no copy, no separate ETL to maintain.
- Row-level security via a policy tag on `supplier_id` — the filter is enforced at the data layer, not in app code, so it can't be bypassed.
- I reused the existing audit pipeline (the same one feeding our audit logging), so the marginal cost was basically zero.
- Suppliers write their own SQL against a stable schema — self-service, no support ticket.

**Likely follow-ups:**
- "How did you notice it?" → I watch our own logs/metrics; the re-query pattern from one consumer ID stood out.
- "Did you get buy-in first?" → I validated the pain with numbers, then looped in my lead and the support team before shipping.
- "Security risk of giving suppliers SQL?" → Row-level security plus they only touch external tables over their own partition; no access to raw infra.
- "Why not a dashboard?" → SQL was faster to ship and more flexible for their engineers; reused existing data.

**What NOT to say:**
- Don't make it sound like I went rogue — I validated and looped people in.
- Don't undersell the security piece; that's what made it safe to ship.
- Don't claim it was a huge team effort — this one was genuinely me.

🎙️ **Say-it script:**
"So this wasn't on my plate. My role was building the supplier-facing data APIs, not the support side. But I kept seeing one account, Pepsi, hammering us with re-queries every time they hit a failed request. I dug in and counted it — one debugging session was fifty-plus repeated queries, because they had no visibility into their own request history. Every round-trip went through Walmart support. So I made it mine. We were already dropping audit data into GCS as Parquet, so I built BigQuery external tables on top of it — suppliers could run plain SQL against their own data, no new pipeline. The tricky part was security: Pepsi can't see Coca-Cola's rows. I put row-level security on it with a policy tag on supplier_id, so each supplier only sees their own data, enforced at the table. End result — a debug that took two days now takes about thirty seconds, and it saved our support team roughly twelve hours a week. Nobody assigned it. I just saw the pattern and owned it."

💬 **60-second version:**
"My role was the data APIs, not support. But I noticed Pepsi was running fifty-plus re-queries per debug because they couldn't see their own request history. So I built BigQuery external tables over the audit data we were already storing, with row-level security so each supplier only sees their own rows. Two-day debugs dropped to thirty seconds and saved support about twelve hours a week — and none of it was assigned to me."