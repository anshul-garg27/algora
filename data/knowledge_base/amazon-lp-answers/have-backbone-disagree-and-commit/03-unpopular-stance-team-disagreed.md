# Q: Tell me about a time when you took an unpopular stance, and your team members or manager disagreed.

> **LP**: Have Backbone; Disagree and Commit
> **Primary story**: `W9 — Cosmos → Postgres Migration`
> **Backup story**: `W4 — Multi-Region Active/Active`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

May 2025. I owned the Transaction Event History API on inventory-events-srv. It ran on Azure Cosmos DB. Our bill kept moving — Cosmos charges per RU and our query mix kept changing the spend. I had been tracking it for two months. The line was unpredictable and pointing up.

I brought it up in a team standup. My pitch was: move this service from Cosmos to Postgres on WCNP. Two senior engineers pushed back hard. Their reasons were not crazy. Cosmos was the team default. Moving it meant codegate work, schema design, partitioning, and a non-trivial deploy. "Why fix what is not broken?" The manager was leaning toward leaving it.

### Task

I was the smallest voice in the room. I either dropped it or did the homework to actually defend the move.

### Action

I did not push back in the meeting. I asked for a week to come back with a real proposal. Then I built the case.

I pulled three months of Azure cost data and broke it down per query. The RU-per-month was sitting at about 4x what a comparable Postgres workload would cost on WCNP, where we already had managed instances. I priced the migration — about three weeks of my time including codegate fixes. I drew the operational angle too: every other service on the team was Postgres. Two engineers had to context-switch every time they touched this one. The on-call runbook had a separate Cosmos section that almost nobody read.

I wrote it up as a one-page doc — cost trend, migration plan, risk list, rollback. Risk list mattered most. I called out the API contract guarantee: the migration would not change the public response. Cursor-based pagination would still work because I encoded the cursor as a timestamp bookmark, which works the same on Cosmos and Postgres.

I sent it to my manager 1:1 first. He read it, asked two questions, then said "you make the call, you own it." That was the green light. I shared it with the team and committed to delivering by end of the month.

### Action — execution

The migration PR was #80, around 530 lines. I kept the API surface identical. Then four codegate PRs over five days — Walmart's automated quality gates flagged minor stuff in stage and prod configs. I fixed each one. Zero-downtime cutover. Suppliers — Pepsi, Coca-Cola, the usual — saw no change.

### Result

The migration shipped end of May. Cosmos cost came off the bill. Predictable Postgres footprint going forward. A month later we layered the Canada launch (PR #96) on top of the new Postgres foundation — that would have been painful on Cosmos. The two engineers who pushed back? One of them later told me he was glad he lost that one. The thing I learned — when the data is on your side, do not argue in the meeting. Go quiet, build the doc, walk it through your manager first, then come back with a plan, not a complaint.

---

## Technical depth — if they probe

- **Cursor pagination across the migration**: Same `WHERE created_ts > last_seen LIMIT 10` shape. Cosmos uses continuation tokens, Postgres uses an indexed scan. Cursor token format stayed identical on the wire so consumers did not change.
- **Site-based partitioning**: Postgres tables partitioned by site_id (US=1, MX=2, CA=3). Partition pruning gives the same data-isolation property Cosmos had with partition keys.
- **Codegate**: Walmart-internal CI gate. PRs #83, #85, #86, #87 fixed config and SQL-injection lint warnings the migration triggered.
- **Why predictable beats cheap**: It was not just cheaper. RUs spike when query plans change. Postgres on WCNP gives us a flat cost line we can plan against.

---

## Likely follow-ups

**Q: What if your manager had said no?**
> I would have asked for a smaller pilot — migrate one of the smaller endpoints first to prove the cost case. If that came back clean, the larger move becomes a conversation about evidence, not opinion.

**Q: How did the team feel after?**
> The two engineers who pushed back ran the migration with me on review. They wanted to learn the Postgres-on-WCNP patterns. By the end, they were the ones answering questions for the next service migration.

**Q: Risk you missed?**
> Cosmos had implicit retries on transient failures. Postgres on WCNP needed me to add explicit retry with exponential backoff via Resilience4j. Caught it in stage, not prod.

**Q: How did you avoid breaking suppliers?**
> Kept the API contract identical and ran a 1-week dual-read in stage where every request hit both Cosmos and Postgres and I diffed the responses. Caught one ordering issue, fixed it before cutover.

---

## What NOT to say

- Do not say "the team was wrong." They were cautious, which is reasonable.
- Do not skip the manager 1:1 — that is the move.
- Do not oversell the cost number without the predictability angle.

---

## Backup story (if asked for another)

W4 — Multi-Region Active/Active. Leadership said "make audit resilient" with no RTO/RPO. Team wanted Active/Passive for cost. I pushed for Active/Active because compliance needed zero data loss. Wrote up the requirements doc myself, defended the spend, and ran a 5-week canary. 25-second failover in production, zero data loss across three failovers.
