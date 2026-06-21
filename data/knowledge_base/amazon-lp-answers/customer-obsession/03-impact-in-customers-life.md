# Q: Tell me about a time when you created an impact in a customer's life.

> **LP**: Customer Obsession
> **Primary story**: `P2 — Disbursal TAT 3.2 min → 1.1 min`
> **Backup story**: `G6 — Fake-Follower ML`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

This was at PayU's API Lending division. We were the layer between a borrower's app and a partner bank that actually disburses the loan. End-to-end, a small-ticket personal loan was taking 3.2 minutes from "accept terms" to "money in account." Doesn't sound bad on a slide, but watch a real user — they refresh the screen, they think the app froze, some of them just leave. Drop-offs were highest at the 90-second mark.

### Task

My manager asked me to look at TAT. No specific target. I picked it up because the drop-off curve was right there in the funnel report.

### Action

I pulled traces for 500 disbursal journeys. The flow was a chain of synchronous calls — KYC verification, bank account validation, partner-side eligibility, e-mandate setup, then the disbursal call itself. Each one ran in sequence. Most were 5-20 seconds. The total was the sum.

I categorised them. KYC verification and bank account validation didn't depend on each other — both just needed the user's PAN and bank details. Partner eligibility also didn't depend on either. Three independent calls running in series, each waiting on the previous, no real reason.

I rewrote that block with `CompletableFuture.allOf` on a dedicated executor. Three calls fire in parallel, the chain waits for all three to complete, then continues. Used a custom thread pool sized to (RPS × latency × 2) — not the common ForkJoinPool, because these were blocking I/O calls and the common pool is shared across the JVM.

KYC was also the slowest. Same user often retried within 24 hours — same PAN, same Aadhaar, same result. I added a Redis cache on the KYC response with a 24-hour TTL and the PAN hash as key. Hit rate climbed to about 60% after a week. Cache hits skipped the 8-second KYC call entirely.

Last piece — retries. The partner bank API would flake about 4% of the time with 5xx. I wrapped the partner call in Resilience4j with exponential backoff and an idempotency key, so a retry didn't trigger a duplicate disbursal.

### Result

Average TAT moved from 3.2 minutes to 1.1 minutes — a 66% drop. Drop-off at the 90-second mark fell substantially. The product team got back to me a few weeks later — the loan completion rate had improved enough that they raised their monthly disbursal forecast. The borrower never sees the architecture, but they see their money 2 minutes sooner. That's the kind of impact you can't undo for them — once you've waited 1 minute for a loan, 3 minutes feels broken.

---

## Technical depth — if they probe

- **`CompletableFuture.allOf` with a dedicated executor**: The default `ForkJoinPool.commonPool()` is shared across the JVM and sized for CPU-bound work. Blocking I/O on it starves other parts of the app. A dedicated bounded executor with `(RPS × latency × 2)` threads keeps the pool healthy.
- **Idempotency key on partner retries**: We generated a UUID per disbursal request, sent it in the partner API header, and they keyed deduplication on it. Retries with the same key returned the original response, not a second disbursal. This is non-negotiable in payments — a double disbursal is a real loss.
- **Redis KYC cache**: PAN was the key. TTL of 24 hours matched the regulatory rule we were using (KYC valid for that window). On invalidation, we evicted on bank-side update events.
- **Resilience4j circuit breaker + backoff**: 50% failure rate over a 30-second window opens the circuit. Exponential backoff with jitter prevents thundering herd on partner recovery.

---

## Likely follow-ups

**Q: What if the parallel KYC and bank validation both fail in different ways?**
> `CompletableFuture.allOf` waits for all three to complete, success or failure. I aggregated the error responses into a single user-facing message — "KYC failed, retry with correct PAN" or "bank account couldn't be verified." We didn't want to fire three error toasts.

**Q: 60% cache hit rate — what about the other 40%?**
> First-time borrowers. No prior KYC in cache. They take the full hit. That's fine — they're not the retry cohort anyway.

**Q: Was there a risk in parallelising the partner eligibility check?**
> Mild. The partner could see three near-simultaneous reads against the same user. Their rate limit was per-PAN per minute, well above three. We checked with their team before shipping.

**Q: How did you validate the 66% number?**
> Pulled disbursal completion timestamps from the loan service DB before and after the change, segmented by partner. The 3.2 → 1.1 number is the median. P95 also dropped but I lead with the median because that's what most users experience.

---

## What NOT to say

- Don't claim I redesigned KYC — KYC was a vendor API, I cached it and parallelised it.
- Don't say "I worked on payments" generically. Be specific: API Lending, personal loan disbursal, partner bank flow.
- Don't oversell the borrower impact in money saved — the impact is time and completion rate. The money is the same loan amount.

---

## Backup story (if asked for another)

The fake-follower ML at GCC. Brands paying for influencer campaigns were getting burned — the influencer's follower count was inflated with bots. I built a 5-feature ensemble — Indic transliteration via HMM models, RapidFuzz scoring against a 35,000-name Indian name DB, digit-count heuristics, non-Indic script detection. It runs on AWS Lambda from SQS, 50% faster than the sequential approach. Brands now see a confidence score before signing a creator — they spend their budget on real reach.
