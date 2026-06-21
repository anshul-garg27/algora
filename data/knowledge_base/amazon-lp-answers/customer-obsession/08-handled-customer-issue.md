# Q: Tell me about a time you handled a customer issue.

> **LP**: Customer Obsession
> **Primary story**: `P2 — Disbursal TAT 3.2 min → 1.1 min`
> **Backup story**: `W1 — Silent Kafka Failure`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

At PayU's API Lending team, I was three months into my first job. Customer success forwarded a thread — a borrower had taken a personal loan, the app showed "disbursal in progress" for over four minutes, he assumed it failed and re-applied through a different partner. We ended up with two loans against the same person, both disbursed. Operations had to reverse one and refund the partner. The borrower's exact words in the support chat: "Your app is broken, just send the money."

He wasn't wrong. Our median TAT was 3.2 minutes. The drop-off curve in our funnel was steepest at 90 seconds — the point where a user starts assuming the app froze.

### Task

My manager asked who wanted to take on TAT reduction. I picked it up. No specific target, just "make it faster."

### Action

I pulled traces for 500 disbursal journeys, top to bottom. The whole flow was a chain of synchronous API calls. KYC verification (8 seconds). Bank account validation (12 seconds). Partner-side eligibility (15 seconds). E-mandate (20 seconds). Disbursal (45 seconds). All in series, each waiting on the previous response.

The first thing I noticed — three of those calls didn't depend on each other. KYC needs the borrower's PAN. Bank validation needs the bank account. Partner eligibility needs the loan amount. None of these blocked each other. They were just sequential because that's how the code was written.

I rewrote that block with `CompletableFuture.allOf` on a dedicated thread pool. Three independent calls fire in parallel, the next stage waits for all three. I used a custom executor sized to `(RPS × latency × 2)` threads rather than `ForkJoinPool.commonPool()` — these are blocking I/O calls, and the common pool is shared across the JVM. Putting blocking work on it would have starved other parts of the service.

Next was caching. KYC verification was the slowest non-parallelisable call at 8 seconds. About 60% of users retried within 24 hours — same PAN, same Aadhaar. I added a Redis cache on KYC response keyed on the PAN hash with a 24-hour TTL. The TTL matched the regulatory window for KYC validity.

Last piece — the partner bank API would flake about 4% of the time with 5xx errors. We were retrying without idempotency, which is what created the original double-disbursal incident. I wrapped the partner call in Resilience4j with exponential backoff and a UUID idempotency key. Retries with the same key returned the cached partner response instead of disbursing twice.

I shipped it behind a feature flag, ran it on 10% of traffic for a week, watched the dashboards, then rolled to 100%.

### Result

Median TAT moved from 3.2 minutes to 1.1 minutes. Drop-off at the 90-second mark dropped meaningfully. The original borrower complaint pattern — "I thought it failed, I re-applied" — became rare in support tickets after the rollout. The failure rate from partner-side retries went from about 4.6% to under 0.3% because the idempotency key meant we could safely retry without doubling up.

I didn't get to talk to that specific borrower. But I saw his thread on the customer success channel and it stuck with me through the whole project. The architecture is hidden from him. He just got his loan in one minute instead of three, and didn't have to call support to undo a duplicate.

---

## Technical depth — if they probe

- **`CompletableFuture.allOf` with dedicated executor**: The common `ForkJoinPool` is shared across the JVM and is sized for CPU-bound work — typically `nCPUs - 1` threads. Blocking I/O on it starves other parts of the app. A bounded executor with `(RPS × latency × 2)` threads keeps I/O isolated.
- **Idempotency key on partner calls**: A UUID per disbursal in the request header. Partner deduplicates server-side. This is non-negotiable in payments — a double disbursal is a real loss. We had one before the fix.
- **Resilience4j circuit breaker**: 50% failure rate over a 30-second window opens the circuit. Exponential backoff with jitter prevents thundering herd on partner recovery.
- **Redis KYC cache**: PAN hash as key, 24-hour TTL aligned with the regulatory rule. Eviction on bank-side KYC update events.

---

## Likely follow-ups

**Q: How did you know the three calls were actually independent?**
> Read the partner API contracts and traced the request payloads. KYC takes PAN. Bank validation takes account number. Partner eligibility takes loan amount and partner ID. No call's request depended on another's response. I confirmed with our integration lead before parallelising.

**Q: What did you do about the 40% who weren't cached?**
> First-time borrowers. They take the full KYC hit — there's no avoiding it because we genuinely don't know them. The 60% who retried got the cache benefit, which is where the median moves.

**Q: Was the original double-disbursal incident actually caused by no idempotency?**
> Partially. The bigger cause was the user re-applying through a different partner because he assumed the first attempt failed. The idempotency fix protects against retry-driven duplicates inside one partner flow. The cross-partner case is a separate detection layer.

**Q: How did you validate the 1.1-minute number?**
> Pulled disbursal completion timestamps before and after the change, segmented by partner. 3.2 → 1.1 is the median. P95 also dropped from about 6 minutes to 2.5. I lead with the median because that's what most borrowers experience.

---

## What NOT to say

- Don't claim I personally talked to the borrower. I saw his thread, that's it.
- Don't pretend the double-disbursal incident was entirely my fault to fix — the idempotency gap was pre-existing, I closed it.
- Don't say I "rebuilt the disbursal flow." I parallelised three independent calls, cached KYC, and added idempotency.

---

## Backup story (if asked for another)

The silent Kafka failure at Walmart. Two weeks post-launch, GCS sinks stopped writing audit logs. No alarms — `errors.tolerance: all` was silently dropping records. I dug through DEBUG logs over five days. Found a null-header NPE in our SMT filter, a KEDA-driven rebalancing feedback loop, and JVM heap exhaustion. Fixed all three. The suppliers querying that data never knew anything broke — Kafka retained the messages, backlog cleared in 4 hours after the fix.
