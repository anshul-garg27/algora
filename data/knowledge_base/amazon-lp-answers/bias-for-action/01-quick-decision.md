# Q: Describe a situation where you had to make a quick decision.

> **LP**: Bias for Action
> **Primary story**: `P2 — Disbursal TAT 3.2 min → 1.1 min`
> **Backup story**: `G2 — Beat rate limiting`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

This was at PayU, on the API Lending team. The loan disbursal flow was taking 3.2 minutes end-to-end. Sales had a demo with a partner that week and the partner had said clearly — anything over 2 minutes and they walk. We had four days.

### Task

Cut disbursal time by at least 50% before the demo. My lead said pick whatever path I could actually finish, not what was technically nicest.

### Action

I pulled APM traces for the disbursal endpoint and laid out every downstream call on paper. There were seven calls in a chain — KYC verify, bank account validation, partner pre-check, credit bureau, internal scoring, partner final-call, and ledger write. Total wall time around 190 seconds.

I looked at which ones actually depended on each other. KYC verify, bank validation, and credit bureau didn't — they were three independent network calls all gated on the same user input. The team had written them sequentially because that's how the original spec was drafted.

That was the unlock. I wrapped the three independent calls in `CompletableFuture.supplyAsync` on a dedicated `ThreadPoolExecutor`, joined with `CompletableFuture.allOf`, and added a per-call timeout so a slow partner couldn't drag the whole flow down. Total latency for that block dropped from about 95 seconds to about 35 — the slowest single call.

The other big win was caching the KYC result. Users were retrying disbursals after small failures and we were re-running KYC every time. I added a Redis cache keyed by PAN with a 10-minute TTL. Hot retries became near-instant.

I shipped it on day 3 behind a feature flag, watched the metrics for a day, then enabled it for the demo cohort.

### Result

TAT went from 3.2 minutes to 1.1 minutes — 66% reduction. The partner demo went through. The same pattern was applied to two other journeys later. Honestly, the decision wasn't about the tech. It was about which slice to cut so I could ship in four days, not four weeks.

---

## Technical depth — if they probe

- **`CompletableFuture.allOf` vs reactive**: I picked CompletableFuture because the rest of the codebase was synchronous Java 11 with Spring MVC. Going reactive would mean rewriting the controller and every test. Not worth it for a 4-day window.
- **Dedicated thread pool**: I didn't use the common ForkJoinPool. Created a `ThreadPoolExecutor` with core 10, max 20, queue 100 — sized to our concurrency. Common pool is shared and one slow partner could choke unrelated work.
- **Timeout per future**: `orTimeout(2, SECONDS)` on each future. Without this, a hanging KYC partner would block the whole join.
- **Redis cache key**: PAN+amount-bucket. Not just PAN — different loan amounts trigger different KYC variants and I didn't want to cross them.
- **Feature flag**: Toggled per partner. Let me roll back instantly if one partner's flow misbehaved.

---

## Likely follow-ups

**Q: Why not full async / reactive?**
> Codebase was Spring MVC, team was synchronous-Java native. Reactive would've been a 3-week project. CompletableFuture on a sync controller gets you 80% of the win for a fifth of the work.

**Q: What if one of the three calls fails?**
> The future's `exceptionally` block converts it to a structured failure. The aggregator decides — KYC failure is a hard stop, bank validation failure can fall back to a manual review queue. Each downstream's failure mode was different.

**Q: Did you measure correctness, not just speed?**
> Yes. I diffed the response payload for 1,000 disbursals before and after on staging. Identical except for timing fields. That gave me the confidence to ship.

**Q: Cache invalidation?**
> 10-minute TTL was the cheap answer. If KYC data changed within 10 minutes, we'd serve stale — but the upstream KYC system itself had a 5-minute consistency window. I wasn't making things worse.

**Q: What would you do differently?**
> Pick the thread pool size from a load test, not a guess. We over-provisioned a little. And I'd have written the trace-diff script before the change, not after.

---

## What NOT to say

- Don't claim I "rewrote the system" — I rewrote one method.
- Don't say "I made a call without data" — I had APM traces. That was the data.
- Don't oversell Redis — it was a tactical cache, not a system.

---

## Backup story (if asked for another)

At GCC, Beat scraping hit Instagram's rate limit on a Friday evening and the whole crawl pipeline was 429-ing. I shipped a Redis-backed distributed token bucket the same night — checked in tokens per partner key, capped at the public quota, and gated all workers through it. Crawls came back online in about 4 hours.
