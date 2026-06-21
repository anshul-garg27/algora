# Q: Tell me about a challenging implementation you handled.

> **LP**: Dive Deep
> **Primary story**: `G2 — Beat Scraping Engine`
> **Backup story**: `W11 — Unified Onboarding / IAM`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

At GCC I owned Beat, the scraping engine that pulled influencer data from Instagram, YouTube, and a handful of other platforms. The challenge wasn't writing scrapers — it was being a good citizen of the partner APIs. Instagram's Graph API would throttle us. RapidAPI would shadow-ban tokens. And if we hit rate limits hard, we'd get IP-banned and the whole platform would go dark for 24 hours.

### Task

Build a scraping engine that ran 150+ Python workers, hit five different upstream APIs, respected each one's rate limit, and didn't take the whole platform down if one provider hiccuped.

### Action

I built three layers of rate limiting because no single one solved the problem.

The first layer was a global token bucket per upstream provider — Redis-backed, distributed across all workers. If Instagram's Graph API was rated at 100 calls/minute across our IPs, the bucket enforced that globally. Workers acquired tokens or backed off.

The second layer was per-account throttling. Each Instagram account we used to scrape had its own request budget. If account A had burned through its hourly limit, requests for that account routed to account B. Round-robin with health tracking.

The third layer was per-endpoint adaptive rate limiting. Different endpoints had different soft limits Instagram never documented — `/user/lookup` was generous, `/posts/recent` was strict. I tracked 429s per endpoint and dialled the per-endpoint cap down on a sliding window. When the 429 rate dropped, we crept back up.

Then I added circuit breakers. Resilience4j-style — if an endpoint hit 50% error rate over 30 seconds, the breaker opened for 60 seconds. During the open window, workers skipped that endpoint and pulled the next item from the queue. Half-open probe afterward. The breaker meant one broken endpoint didn't drag the whole worker pool down.

The hard part was the interaction between layers. Token bucket said "go," per-account said "wait, you're cooked," per-endpoint said "go but slow," and the breaker said "this endpoint is sick — skip." I wrote a decision matrix and a single `acquire()` function that consulted all four. Worker code stayed clean: `if rate_limiter.acquire(provider, account, endpoint): scrape()`.

### Result

Beat ran for 18 months without a single platform-wide ban. 500K+ profiles a day across 150+ workers with 5x concurrency. The 429 rate stayed under 2%. When Instagram changed an endpoint's limit silently — which happened twice — the adaptive layer caught it within 30 minutes and dialled back without anyone paging on-call.

The other piece that came out of this: when partner APIs went down for real, our circuit breakers protected the rest of the platform. One time RapidAPI was out for 4 hours; Beat kept running on Graph API alone and our analytics pipeline never knew.

---

## Technical depth — if they probe

- **Why Redis-backed token bucket**: 150+ workers across multiple pods can't coordinate without shared state. Redis's atomic `EVAL` script on a Lua bucket guarantees no double-spend across workers. In-process buckets would have over-issued by a factor of N.
- **Why per-account and per-endpoint, both**: Per-account protects the credential. Per-endpoint protects the relationship. Different failure modes need different defences.
- **Resilience4j-style breaker, not literal Resilience4j**: I was in Python. I wrote a small breaker class with the same semantics — closed, open, half-open with probe. Borrowed the math, not the library.
- **Why adaptive caps**: Instagram doesn't publish per-endpoint limits. The only signal is 429s. A static cap is either too cautious (wastes budget) or too aggressive (gets you banned). Adaptive lets the system find the true limit empirically.

---

## Likely follow-ups

**Q: What happened when all three layers said "wait"?**
> The worker put the item back on the queue with a delay and pulled the next one. Backpressure flowed naturally to the producer side — if every consumer was waiting, the queue grew, and Airflow noticed lag and slowed the upstream DAG. No deadlocks.

**Q: How did you debug an adaptive-limit miscalibration?**
> Every `acquire()` decision was logged with the four signals — bucket state, account budget, endpoint cap, breaker state. When the 429 rate spiked, I could replay the last 5 minutes and see which signal misled the decision. Two miscalibrations in 18 months, both endpoint-cap calculations.

**Q: Would Kafka have been better than RabbitMQ for this?**
> RabbitMQ was the existing backbone. For 115 events/sec average, it was fine. The rate-limiting layer wasn't the bottleneck — the scraping work itself was. Kafka would have been overkill.

**Q: What did you regret not building?**
> A dead-letter consumer that persists failed items to S3 for offline replay. We logged failures but didn't have a replay path. For a couple of nasty provider outages, we lost work we could have recovered.

---

## What NOT to say

- Don't oversell "I solved rate limiting." Plenty of teams have. Be specific about the four-signal decision.
- Don't claim "zero 429s." Say "under 2%." 2% is real and acceptable; zero is a lie.
- Don't skip the adaptive part. The fact that the system discovered Instagram's hidden caps is the deep-dive signal.

---

## Backup story (if asked for another)

For W11, building unified onboarding with Apollo Federation, the implementation challenge was getting the supergraph to route correctly across five subgraphs while maintaining sub-200ms p95. The Apollo router's planner makes non-obvious decisions about resolver fan-out, and N+1 issues are invisible at the schema level. I built a DataLoader layer per subgraph, traced every resolver in OpenTelemetry, and walked a junior engineer through the planner output for his credentials subgraph until he could spot the fan-out patterns himself. The deep dive was understanding the planner well enough to teach it.
