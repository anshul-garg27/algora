# Q: Tell me about a time when you handled an urgent requirement or made a trade-off decision.

> **LP**: Bias for Action
> **Primary story**: `G2 — Beat rate limiting`
> **Backup story**: `P2 — Disbursal TAT`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

This was at Good Creator Co. — small influencer-analytics shop, 5-person eng team. Beat was our scraping engine, 150-odd async workers crawling Instagram and YouTube. On a Friday evening Instagram started returning 429s across the board. Our public-API quota was getting blown by Beat's own concurrency.

By midnight roughly 40% of the day's scrape jobs had failed. Monday morning the customer dashboard would show flat lines for two days of data. Brands would notice.

### Task

Get scraping back inside quota by the time the Saturday crawl batch kicked off — about 8 hours away. I had to pick between a clean fix and a fix I could actually ship.

### Action

The clean fix was per-flow concurrency tuning across every worker config. That meant load-testing each Instagram endpoint separately. Probably a week of work.

I had a faster option. The actual cause was simple: we had no shared view of how many requests were in-flight to Instagram. Each worker thought it was alone. So I built a Redis-backed token bucket — one key per partner endpoint, refilled by a script every second at the published quota rate. Every worker did a `DECRBY` before making a call. If the result was negative, it slept with jitter and retried.

The whole thing was about 60 lines of Python. I tested it locally with three workers hammering a stub, then deployed it to one Instagram flow first. Watched the 429 rate drop from 30% to under 1%. Rolled it out to the other flows by 4 AM.

The trade-off I made was clear and I wrote it in the deploy notes: the token bucket was approximate, not exact. If Redis briefly disconnected, workers would default to "allowed" and we could spike. I added a circuit breaker for that case — three consecutive 429s and the worker pauses for 60 seconds.

### Result

Saturday's batch ran clean. 429 rate stayed under 1% for the next two weeks. The "proper" fix — per-flow tuning — became a follow-up I scoped but never had to ship. The token bucket held. The right call wasn't the perfect rate limiter, it was the one that ran on Saturday morning.

---

## Technical depth — if they probe

- **Why Redis, not in-process**: 150 workers across multiple pods. In-process limiters would have given each pod its own quota — useless.
- **`DECRBY` instead of Lua**: Atomic, single-round-trip. Lua scripts are nicer but I didn't need read-modify-write — just decrement-and-check.
- **Sleep with jitter**: Without jitter, every blocked worker wakes at the same instant and re-thunders the limiter. Exponential backoff with random jitter spread the retries.
- **Circuit breaker fallback**: For when Redis itself misbehaves. The token bucket is the optimistic path; the breaker is the pessimistic backstop.
- **Per-partner keys**: Instagram and YouTube had different quotas. Separate buckets so a busy IG day didn't starve YouTube.

---

## Likely follow-ups

**Q: Why not just lower the worker count?**
> That throws away throughput evenly across all endpoints. Some endpoints had room. The token bucket lets fast endpoints stay fast and only throttles where the quota is actually hit.

**Q: What if Redis goes down?**
> Workers default to "allowed" so we don't take a hard outage from a soft dependency. The 3-consecutive-429 breaker catches the case where Redis is up but we've started overshooting.

**Q: How did you tune the refill rate?**
> Instagram publishes their quota — I set the bucket to 80% of that. The 20% headroom was for retries and for upstream rate-limit accounting being a bit fuzzy.

**Q: Did you ever do the "proper" fix?**
> No. The token bucket held for the rest of my time at GCC. The proper fix would have been work for the sake of work.

---

## What NOT to say

- Don't pretend this was a fancy system — it was 60 lines of Python and Redis.
- Don't claim "100% reliability" — it was 99%+, and I told the team about the failure mode.
- Don't skip the trade-off — interviewers want to hear what you knowingly accepted.

---

## Backup story (if asked for another)

At PayU, four days before a partner demo, I cut loan disbursal TAT from 3.2 to 1.1 minutes by wrapping three independent downstream calls in `CompletableFuture.allOf` with per-call timeouts. Same pattern: pick the slice you can ship, not the one that looks best on the design doc.
