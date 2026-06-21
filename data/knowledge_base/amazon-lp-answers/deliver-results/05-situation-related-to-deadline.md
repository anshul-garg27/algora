# Q: Describe a situation related to a deadline (DDL).

> **LP**: Deliver Results
> **Primary story**: `P1 — Partner API Failure Rate`
> **Backup story**: `W7 — DSD Notification System`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

PayU API Lending, late 2022. I was an intern that had just turned full-time. We disbursed loans through partner banks via APIs — the partner integration was the path the money traveled on. Two weeks before the quarterly partner SLA review, our production failure rate on disbursal calls was sitting at 4.6%. The contract threshold was 2%. If we did not bring it down by review day, the partner had the right to throttle our volume to a fraction of normal. That meant real revenue loss and a credibility hit my team had been carrying for two quarters.

### Task

Get the failure rate under 2% in two weeks. I was the one who had the disbursal flow paged into my head — I had been debugging it since week three of the internship.

### Action

I started with the data. Pulled two weeks of failure logs, bucketed by HTTP status and error code from the partner.

The breakdown surprised me. Only about a third of the failures were genuine — KYC mismatch, account closed, validation failures. Two thirds were transient: 503s on the partner gateway, 504 timeouts, and a handful of cases where we double-submitted because of a network blip during the retry window. The bank was returning the same disbursal twice and one of them came back as a duplicate-key rejection.

That changed the plan. I did not need to fix every failure. I needed to make the retryable ones idempotent and to actually retry them properly.

First change — idempotency keys. I added a UUID per disbursal request, sent it in a custom header to the partner, and stored it in our local table with a unique constraint. If the same request came back twice, the second one short-circuited at our edge and returned the first response. That killed the double-submit class of failures inside three days.

Second change — retry with exponential backoff. Resilience4j retry on transient 5xx and timeouts. 3 attempts, base 200ms, multiplier 2.0, max 800ms. Anything that returned `IDEMPOTENCY_KEY_USED` was treated as success on retry and pulled the original response.

Third change — circuit breaker. Same Resilience4j config. 50% failure-rate threshold over a 30-second window, half-open after 60 seconds. The point was not to retry forever — when the partner was actually down, we needed to fail fast and route to the secondary partner instead.

I shipped in nine days. Two days of analysis, four days of code and integration tests, three days of canary at 10% of traffic before going to 100%. My mentor reviewed every PR. My manager checked in daily.

### Result

Failure rate from 4.6% to 0.3% — 93% reduction. Reviewed comfortably under the 2% threshold. Partner SLA review went the other direction — they offered us a higher volume tier. Year-over-year that opened roughly 40% more business volume on cross-lending integrations. The thing I took from it — when you have a deadline, do the bucketing first. Two thirds of those failures were not bugs, they were missing patterns. Idempotency and retry are cheap. Picking them off correctly is the leverage.

---

## Technical depth — if they probe

- **Idempotency key design**: UUID v4 per request, sent in `X-Idempotency-Key`, stored locally with a unique index. Replay returns the cached response from our side without re-hitting the partner.
- **Retry config**: Resilience4j `retry`, 3 attempts, exponential backoff base 200ms multiplier 2.0 max 800ms. Retry only on transient 5xx, timeouts, and connection errors. Not on 4xx — those are real business failures.
- **Circuit breaker**: 50% failure rate over 30-second sliding window, 60-second half-open delay, fail-fast to secondary partner integration during open state.
- **The double-submit class**: Network blip during partner's response → our retry → partner saw two disbursals → one succeeded, one came back as duplicate-key. Idempotency key short-circuited the second submit before it left our edge.

---

## Likely follow-ups

**Q: What if the deadline had been one week instead of two?**
> I would have shipped the idempotency keys alone — that was the biggest single lever. Retries and circuit breaker would have been the next week.

**Q: How did you de-risk the rollout?**
> 10% canary for three days with the idempotency table backed up hourly so I could prove every accepted key matched a real partner response. No anomalies, ramped to 100%.

**Q: What about the partner's side?**
> I spent a half-day on a call with their integration team confirming the idempotency-key header contract. They had supported it for a year — we just had not used it.

**Q: How did you keep your manager confident?**
> Daily Slack with the failure-rate number from the metrics dashboard. He could check progress without asking.

---

## What NOT to say

- Do not say "I rewrote the disbursal flow." I added idempotency, retry, and a breaker. Surgical, not heroic.
- Do not blame the partner. Two thirds of the failures were on us not handling transient errors right.
- Do not skip the bucketing step. That is what made the plan possible.

---

## Backup story (if asked for another)

W7 — DSD notifications. Six-week deadline before the holiday receiving window. Cut scope from 5 event types to 2 (ENROUTE + ARRIVED only). Two-week chunks, feature flag per market, pilot in one US store first. Shipped on time. 500,000+ notifications in six months, 35% replenishment improvement.
