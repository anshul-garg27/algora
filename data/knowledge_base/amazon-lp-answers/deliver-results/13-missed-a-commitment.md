# Q: Tell me about a time you missed a commitment.

> **LP**: Deliver Results
> **Primary story**: `P1 — Partner API Failure Rate`
> **Backup story**: `W4 — Multi-Region Rollout`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

PayU API Lending, late 2022. I had committed to my manager that I would get our disbursal failure rate from 4.6% to under 2% by a specific internal date — five business days before the quarterly partner SLA review, so we had buffer for canary and a potential rollback. The real review was the immovable date. My internal date was the discipline.

I missed my internal date by two days.

### Task

Be honest about the slip, explain why my estimate was wrong, hit the real review date with margin, and decide what I would change.

### Action

The plan was three pieces. Idempotency keys to kill duplicate submits. Exponential-backoff retry on transient 5xx and timeouts. A circuit breaker so we could fail fast to the secondary partner when the primary was down. I had estimated four days of coding, two days of canary, one day of cushion.

Where I underestimated. I had assumed the partner's idempotency-key header was a documented, working contract end-to-end. The doc was real. The end-to-end was not. Their gateway accepted the header cleanly. Two of their four downstream banks did not pass it through. We were retrying disbursals with the right idempotency key on our side, but on those two bank routes the partner was still seeing duplicate submits and rejecting them as `DUPLICATE_REQUEST`. I lost a day and a half on a call with their integration team mapping which bank routes preserved the header and which stripped it. We added a fallback path — if we got `IDEMPOTENCY_KEY_NOT_SUPPORTED` from a downstream bank, we treated the retry as a fresh request and leaned on the partner's own dedupe window.

The moment I knew — end of day three. I told my manager that evening on Slack. Did not wait for standup. Said the internal date would slip by two days but the real review date was still safe with cushion. He was fine with it.

I shipped on day seven. Canary at 10% for two days. Failure rate dropped fast on the canary slice. Ramped to 100% on day nine. Review day was day fourteen.

### Result

Failure rate from 4.6% to 0.3% — 93% reduction. The real review hit comfortably. The partner offered a higher volume tier on the back of the numbers. Year-over-year that opened roughly 40% more business volume on cross-lending. What I missed was a personal discipline date, not the customer-facing one — but the lesson is the same. I treated "documented" as "working" and lost a day and a half. My rule on third-party integrations is now to start with a 30-minute call with their integration team before I plan, not before I deploy. The cushion between my internal date and the real date is what made the slip survivable. I will not run a P0 fix without that gap again.

---

## Technical depth — if they probe

- **Idempotency key**: UUID v4 per request, `X-Idempotency-Key` header, local table with unique constraint. Replay returns cached response without re-hitting the partner.
- **The bank-passthrough gap**: 2 of 4 downstream banks stripped the header. Fallback path on `IDEMPOTENCY_KEY_NOT_SUPPORTED` treats retry as fresh request, partner's own dedupe handles the rest.
- **Retry config**: Resilience4j, 3 attempts, base 200ms, multiplier 2.0, max 800ms. Match on transient 5xx + timeout + connection errors. Not 4xx.
- **Circuit breaker**: 50% failure rate over 30s sliding window, half-open at 60s. On open, route to secondary partner.

---

## Likely follow-ups

**Q: Why set a personal date earlier than the real one?**
> Canary needed two days, ramp needed one, rollback would need a day. Five business days of cushion covered the worst case.

**Q: How did you tell your manager?**
> Slack the evening I knew, not at the next standup. Two sentences — what slipped, why, new date.

**Q: What's the new rule on third-party work?**
> A 30-minute call with the partner's integration team before I write any code. Saves days later.

**Q: Did you communicate to the partner about the slip?**
> No, because their date — the real review — was still safe. The internal date was my own discipline, not their commitment.

---

## What NOT to say

- Do not say "I never miss commitments." Be honest.
- Do not blame the partner. The bank-passthrough gap was something I should have asked about up front.
- Do not skip the cushion pattern. That is the actual lesson.

---

## Backup story (if asked for another)

W4 — Multi-region active/active. A senior director had committed a 4-week date to a peer team before talking to engineering. I came back at week 2 and committed to 5 weeks instead, with an assumptions doc (RTO < 30s, RPO = 0). Shipped end of week 5. Failover 25s in production, zero data loss across three failovers in the first six months.
