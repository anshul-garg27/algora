# Q: Tell me about a time you thought about how your work at scale would affect others.

> **LP**: Success and Scale Bring Broad Responsibility
> **Primary story**: `G2 — 3-Level Rate Limiting on Partner APIs`
> **Backup story**: `W4 — Active/Active Region Cutover Sequencing`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

At GCC I owned Beat, the scraping engine. At our scale — 150+ Python workers, each running 5 concurrency, hitting Instagram Graph API, RapidAPI, and a handful of other partners — we were not a small customer. We were big enough that if we behaved badly, the partner would notice. Instagram had already throttled us once for hammering an undocumented endpoint and our entire platform went dark for 24 hours.

### Task

Build a scraping engine that respected each partner's rate limits — including the limits they didn't publish — and treated being a good citizen as a hard requirement, not a nice-to-have.

### Action

I built three layers of rate limiting because no single layer was enough at our scale.

The first layer was a global token bucket per partner, Redis-backed, shared across all 150 workers. If Instagram's Graph API rate was 100/minute across our IP space, the bucket enforced that globally. Without it, 150 workers each thinking they had 100/minute would have produced 15,000/minute — a guaranteed ban.

The second was per-account throttling. We rotated across multiple Instagram accounts to spread load. Each account had its own hourly budget. If account A was cooked, traffic routed to account B. Round-robin with health tracking.

The third was per-endpoint adaptive limiting. Instagram doesn't publish per-endpoint rate limits — `/user/lookup` is generous, `/posts/recent` is strict, and they never say so. I tracked 429s per endpoint and dialled the cap down on a sliding window. When the 429 rate fell, the cap crept back up. The system discovered the hidden limits empirically.

Then I added circuit breakers. If an endpoint hit 50% error rate over 30 seconds, the breaker opened for 60 seconds. Workers skipped that endpoint and moved on. Half-open probe after the cool-down. The breaker meant one broken partner didn't cascade into worker-pool exhaustion.

The piece I cared about most was what happened when all four signals said "wait." The worker put the item back on the queue with delay and pulled the next one. Backpressure flowed naturally upstream to the Airflow DAG that scheduled the work. No deadlocks, no busy-waits.

### Result

Beat ran for 18 months without a single platform-wide ban. The 429 rate stayed under 2%. When Instagram changed an undocumented endpoint cap twice during that period, the adaptive layer caught the new limit inside 30 minutes and dialled back without anyone paging on-call.

The broader scale-responsibility win was that when RapidAPI had a real 4-hour outage, our circuit breaker isolated the damage. Beat kept running on Graph API alone, our analytics pipeline downstream never knew, and we didn't add to RapidAPI's load by hammering them during their incident.

Honestly, I think about it like this — at one developer scraping one account, you can be careless and nothing breaks. At 150 workers across many accounts, your behaviour is the partner's experience. The responsibility ratio is asymmetric. If we'd been bad citizens, Instagram could have shut us down for an entire industry use case. That risk was the design driver.

---

## Technical depth — if they probe

- **Why Redis-backed token bucket**: 150+ workers across multiple pods can't coordinate without shared state. Redis's atomic Lua-script bucket gives no-double-spend across workers. In-process buckets over-issue by factor N.
- **Why per-account AND per-endpoint**: Per-account protects the credential (account-level bans). Per-endpoint protects the relationship (cap-level bans). Different failure modes need different defences.
- **Why adaptive caps over static**: Static is either too cautious (wastes budget, slower scraping) or too aggressive (gets you banned). Adaptive finds the true limit via 429 signal. Some endpoints have time-of-day variance too — adaptive picks that up naturally.
- **Why the circuit breaker protected RapidAPI during their outage**: Half-open probing tested with one request per 60 seconds instead of full traffic. We weren't adding noise to their recovery while their infra was down.

---

## Likely follow-ups

**Q: What's the cost of being too cautious?**
> Slower scraping. Fresher data is the product. If we under-utilise the budget by 30%, our supplier dashboards lag by 30%. So I tuned the adaptive layer's recovery aggression — it creeps the cap back up faster after the 429 rate drops, to recover budget quickly.

**Q: How did you know you'd been "bad citizens" before this design?**
> The 24-hour Instagram ban was the wake-up call. Logs showed we'd hit `/posts/recent` at about 3x the (then unknown) limit for two hours straight. After that, I treated partner-API behaviour as a first-class design constraint.

**Q: Would you do this differently at 10x scale?**
> I'd add a dedicated control-plane service that the scrapers consult, instead of every worker carrying the rate-limit logic. At 1500 workers the in-process checks would add latency. Centralised decisioning amortises across the fleet.

**Q: What's the worst failure mode you designed against?**
> A coordinated retry storm after a transient partner outage. If all 150 workers hit "retry" on a stuck endpoint simultaneously, we'd DDoS the recovery. Exponential backoff with jitter on every retry path — borrowed straight from AWS's guidance — was the answer.

---

## What NOT to say

- Don't say "we never got banned." Say "no platform-wide ban after this design." There were earlier bans; that's why the design existed.
- Don't claim "perfect rate limiting." Say "under 2% 429 rate." Numbers are credible.
- Don't make the partners the villain. They're running their own infra; respecting their limits is our job.

---

## Backup story (if asked for another)

For W4, the multi-region Active/Active Kafka cutover at Walmart had the same scale-responsibility shape. The audit pipeline served 12+ services across the team. A botched cutover wouldn't have just broken my code — it would have broken every supplier-facing audit query across the org for hours. I sequenced the rollout: pilot in stage, 10% canary in prod EUS2 alone, then add SCUS as secondary, then validate failover with a deliberate broker kill. Five weeks of careful sequencing for what could have been a one-weekend "just do it" deploy. The responsibility was that twelve teams depended on me getting this right.
