# Q: Tell me about a time when you worked under strict deadlines.

> **LP**: Deliver Results
> **Primary story**: `P1 — Partner API Failure Rate`
> **Backup story**: `W7 — DSD Notification System`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

PayU API Lending, late 2022. Two weeks before the quarterly partner SLA review. Disbursal failure rate was sitting at 4.6%. Contract threshold was 2%. Above the threshold and the partner had contractual rights to throttle our volume to a small fraction of normal. Revenue impact would have been real and lasting. The team had been carrying this number for two quarters and treating it as "the partner is flaky." I had been on the disbursal flow since week three of my internship — six months of context paged in.

### Task

Drop the failure rate under 2% in two weeks, with enough margin to survive the review unambiguously.

### Action

Two weeks is tight enough that you do not have time to be wrong about where to start. I gave myself two days to find out what was actually failing before writing any code.

Pulled two weeks of failure logs out of our APM stack. Bucketed by HTTP status, partner error code, and stage in the disbursal flow. The pattern was clean.

About a third of failures were real — KYC mismatch, account closed, validation. We could not fix those. The other two thirds split into two buckets. One bucket was transient — partner gateway 503s and 504 timeouts, especially during peak hours. The other bucket was our own retry logic. We had a naive retry on partner timeout that did not carry an idempotency key, so when the network blip happened mid-response, our retry created a duplicate submit. The partner saw two disbursals, processed one, returned `DUPLICATE_REQUEST` on the second, and we counted that as a failure.

That changed the plan completely. Idempotency was the lever, not better error messages.

Three changes, shipped in order.

Idempotency keys first. UUID v4 per disbursal, sent in `X-Idempotency-Key` to the partner, stored locally with a unique index. If the same request hit twice, we short-circuited at our edge and returned the cached response. Killed the duplicate-submit class in three days.

Retry with exponential backoff second. Resilience4j retry — 3 attempts, base 200ms, multiplier 2.0, max 800ms. Retried only on transient 5xx, timeouts, and connection errors. Not on 4xx. The retry path used the same idempotency key from the original attempt so partner-side dedupe held.

Circuit breaker third. 50% failure-rate threshold over a 30-second sliding window, 60-second half-open. The goal was fail-fast to a secondary partner when the primary was actually down, not to retry into a brick wall.

Daily Slack update to my manager with the dashboard failure-rate number. Canary at 10% of traffic for three days. Ramped to 100% on day nine.

### Result

Failure rate from 4.6% to 0.3% — 93% reduction. Reviewed under the threshold by a wide margin. The partner offered a higher volume tier on the back of the numbers, which opened roughly 40% more business across the next year on cross-lending integrations. Two takeaways. First, the day-one bucketing is the thing that makes a tight deadline survivable — half the time, the "complex bug" is actually three simple patterns sitting next to each other. Second, idempotency keys cost almost nothing and save you in places you did not realise you were exposed.

---

## Technical depth — if they probe

- **Idempotency key**: UUID v4, `X-Idempotency-Key` header, local table with unique index. Cached response on replay. Worked with partner-side dedupe window.
- **Retry config**: Resilience4j retry, 3 attempts, base 200ms, multiplier 2.0, max 800ms. Predicate matched on `is5xx() OR isTimeout() OR isConnectionError()`. 4xx excluded.
- **Circuit breaker**: 50% failure rate over 30s sliding window, 60s half-open delay. On open, route to secondary partner integration.
- **The duplicate-submit class**: Network blip mid-response → naive retry → partner sees 2 submits → returns `DUPLICATE_REQUEST` on second → we counted it as failure. Roughly 30% of total failures.

---

## Likely follow-ups

**Q: Why was day-one bucketing the lever?**
> Two weeks is not enough to fix every failure. Bucketing made it obvious that two thirds were transient or self-inflicted. That is a totally different fix from "retry harder."

**Q: How did you de-risk the rollout?**
> Three-day canary at 10%. Daily reconciliation of the idempotency-key table against partner responses. No anomalies, ramped to 100%.

**Q: What did the partner do?**
> Engineering call to confirm the idempotency-key header contract. They had supported it for a year — we just had not used it. That call was a half-day, saved days later.

**Q: What was the closest call?**
> The discovery that two of four downstream banks did not preserve the idempotency header. Had to add a fallback path. Cost a day. Worth knowing about before deploy.

---

## What NOT to say

- Do not say "I rewrote the disbursal flow." I added three patterns. Surgical.
- Do not blame the partner. Two thirds of failures were us.
- Do not skip the bucketing day — that is the move.

---

## Backup story (if asked for another)

W7 — DSD notifications. Six weeks to ship push notifications to 1,200+ associates ahead of holiday receiving. Cut scope from 5 event types to 2. Per-market feature flag. Pilot in one US store before broader rollout. Shipped on time. 500,000+ notifications in six months, 35% replenishment improvement.
