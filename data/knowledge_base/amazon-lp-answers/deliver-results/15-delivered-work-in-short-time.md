# Q: When was a time you delivered a feature or work in a very short amount of time?

> **LP**: Deliver Results
> **Primary story**: `P2 — Disbursal TAT 3.2 min → 1.1 min`
> **Backup story**: `G2 — Beat Rate Limiting`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

PayU API Lending, early 2023. Our disbursal turnaround time — TAT — was sitting at 3.2 minutes per loan, end to end. That number was the time between a user hitting submit on the loan agreement and the money landing in their account. Mobile-first borrowers were dropping off mid-flow because the spinner ran too long. Our product manager came to me on a Monday and said the competitor had launched a sub-90-second disbursal flow. He needed something to talk about by end of next week. Two weeks.

### Task

Cut TAT meaningfully without breaking the disbursal contract with the partner banks. The bar he gave me was "under 2 minutes." I gave myself "under 1.5."

### Action

I started where I always start when something is slow — profiling. Not guessing. I instrumented the disbursal flow with timing logs at every external call boundary. Ran 200 disbursals through stage with the timing on. The profile told a clear story.

The 3.2 minutes broke down as roughly — KYC verification call to the partner (45 seconds), bank account validation (30 seconds), credit check (50 seconds), agreement generation (20 seconds), disbursal submission (35 seconds), confirmation poll (12 seconds). Plus a handful of small calls.

The thing that jumped out — KYC, bank validation, and credit check were running sequentially. They had been written that way three years ago because the original code returned `Future<T>` and the team had not migrated to `CompletableFuture`. But those three calls had no data dependencies on each other. They were sequential because nobody had thought to parallelize.

That was the lever.

I rewrote the orchestration with `CompletableFuture.allOf()`. Three independent calls fired in parallel, joined when all three returned. The longest of the three (credit check at 50 seconds) became the floor instead of the sum (125 seconds). I added a Resilience4j circuit breaker around each call so a slow partner did not drag the whole flow.

Second optimization — caching. KYC verification was being called fresh on every disbursal even for users who had been verified inside the last 24 hours. I added a Redis-backed cache with a 24-hour TTL keyed on the user's PAN (Indian tax ID). Cache hit rate after a week was 38% — those disbursals skipped the KYC call entirely.

Two days of profiling. Three days of code. Three days of integration testing and canary at 10%. Two days at 25%. Two days at 100%. Twelve days total, two before the deadline.

### Result

TAT from 3.2 minutes to 1.1 minutes — 66% reduction. Under product's bar of 2 minutes and under my personal bar of 1.5. Drop-off rate during the agreement-to-disbursal window dropped by roughly a third in the first month. Product had something to talk about for the partner pitch and the competitor narrative shifted. The thing I took away — when something is slow and the team has lived with it, the first question is "what is sequential that does not need to be." Two thirds of the time, the answer is something that just was not written with concurrency in mind. Profiling tells you. Guessing wastes the deadline.

---

## Technical depth — if they probe

- **`CompletableFuture.allOf`**: Three independent partner calls — KYC, bank validation, credit check — fired in parallel. Joined when all three returned. Floor became the slowest call (~50s) instead of the sum (~125s).
- **Why no data dependency**: KYC verifies identity, bank validation confirms the account exists, credit check pulls bureau score. Three independent reads. Sequential was just legacy.
- **KYC cache**: Redis, 24-hour TTL, key `kyc:{pan}`. Hit rate ~38% after a week of warming. Cache miss falls through to partner call, populates cache.
- **Resilience4j per-call**: Circuit breaker on each parallel call so one slow partner did not block the `allOf` join. 50% failure threshold over 30s window.

---

## Likely follow-ups

**Q: How did you know parallelization was safe?**
> Profiled the call graph. None of KYC, bank validation, or credit check consumed the others' output. All three independently fed the disbursal submission. Verified by looking at the downstream payloads.

**Q: What about cache freshness for KYC?**
> 24-hour TTL was the compliance-safe window — RBI guidance treats KYC as fresh inside 24 hours for repeat transactions on the same identity. Cache miss falls through cleanly.

**Q: What broke first?**
> One of the partner banks had a connection-pool ceiling we hit when three calls fired at once. Bumped the pool size, problem went away. Caught in stage, not prod.

**Q: How did you verify the TAT number?**
> P50 across 10,000 disbursals over the week after rollout. P95 was 1.4 minutes, P99 was 1.8 minutes. The headline 1.1 minutes is P50.

---

## What NOT to say

- Do not say "I rewrote the disbursal flow." I rewrote the orchestration of three calls. The flow itself stayed identical.
- Do not skip the profiling beat. That is what told me which lever to pull.
- Do not over-promise on cache freshness. The 24-hour TTL is compliance-driven, not arbitrary.

---

## Backup story (if asked for another)

G2 — Beat scraping rate limits at GCC. Instagram and YouTube rate limits kept tripping our 150-worker fleet, throttling the daily crawl. I built a token-bucket rate limiter per platform, exponential backoff on 429s, and a proxy IP rotation pool. Crawl throughput went from 200K profiles/day to 500K+ inside a week.
