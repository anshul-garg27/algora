# Q: Have you ever missed a deadline.

> **LP**: Deliver Results
> **Primary story**: `P1 — Partner API Failure Rate`
> **Backup story**: `W5 — Spring Boot 3 Migration`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

PayU API Lending, late 2022. Two weeks before the quarterly partner SLA review, our disbursal failure rate was 4.6%. Contract threshold was 2%. I had committed to my manager that I would get it under threshold by review day. I gave myself a personal hard date — five business days before the review, so I had buffer for canary and a possible rollback.

I missed the personal hard date by two days. The real review I hit comfortably.

### Task

Be honest about the slip, hit the actual review deadline, and figure out where my estimate was wrong.

### Action

The work itself was a three-part change. Idempotency keys per disbursal request to kill double-submits. Exponential-backoff retry on transient 5xx and timeouts via Resilience4j. A circuit breaker so we could fail fast to the secondary partner when the primary was down. I had estimated four days of coding plus two days of canary plus a day of cushion.

Where I underestimated. The partner-side integration on the idempotency-key header. I had assumed it was a documented header on their gateway. It was, but two of their four upstream banks did not pass it through cleanly. I lost a day and a half on the call with their integration team mapping which bank routes preserved the header and which stripped it. We had to add a fallback path — if the partner returned `IDEMPOTENCY_KEY_NOT_SUPPORTED` from a downstream bank, we treated the retry as a fresh request and relied on the partner's own dedupe window.

The moment I knew I was slipping — end of day three. The header-passthrough call had run long. I told my manager that evening in Slack. Did not wait for standup. I gave him a revised timeline — two days late on my personal hard date, but four days of cushion still left before the real review. He was fine with it.

I shipped on day seven. Canary at 10% for two days. Failure rate dropped fast on the canary slice. Ramped to 100% on day nine. Review day was day fourteen.

### Result

Failure rate from 4.6% to 0.3% — 93% reduction. Review went the other way — the partner offered us a higher volume tier on the back of the numbers. Year-over-year that opened roughly 40% more business volume on cross-lending. My takeaway — I missed my personal date because I treated a "documented header" as a working header without verifying with the partner first. Now my rule on third-party integrations is to start with a 30-minute call before I plan, not before I deploy. The protective cushion between my personal date and the real review was the saving grace. I would not run a P0 fix without that buffer again.

---

## Technical depth — if they probe

- **Idempotency key**: UUID v4 per request, sent in `X-Idempotency-Key`, stored locally with a unique index. Replay returns the cached response without re-hitting the partner.
- **Partner-side surprise**: Two of four downstream banks did not preserve the header. Added a fallback that treated `IDEMPOTENCY_KEY_NOT_SUPPORTED` as a soft signal and let the partner's own dedupe handle it.
- **Resilience4j config**: 3 retries, base 200ms, multiplier 2.0, max 800ms. Circuit breaker 50% failure rate over 30s, half-open at 60s.
- **Buffer pattern**: Personal hard date set 5 business days before the real review. That gap saved the rollout.

---

## Likely follow-ups

**Q: Why did you set a personal date earlier than the real one?**
> Canary needed two days, ramp needed one, rollback would need a day if anything went wrong. Five business days of cushion was the buffer that covered the worst case.

**Q: When did you tell your manager?**
> The same evening I knew. End of day three. Did not wait for standup the next morning.

**Q: What did you learn about third-party integrations?**
> Documented does not mean working. A 30-minute call with the partner's integration team before I write any code is now the rule. Saves days later.

**Q: Did the partner notice the slip?**
> No — the real review date was the only one they cared about. The personal date was my own discipline.

---

## What NOT to say

- Do not say "I never miss deadlines." Be honest.
- Do not blame the partner. The bank-passthrough gap was something I should have asked about.
- Do not skip the buffer pattern. That is the lesson that has stayed with me.

---

## Backup story (if asked for another)

W5 — Spring Boot 3 migration. Committed to a 2-week PR. Shipped in 3. The WebClient test-mock refactor was the gap — 42 test files, each chained call needed its own mock, complexity roughly doubled. Told my manager same day, daily progress doc, audit deadline still hit because of the `.block()` scope cut.
