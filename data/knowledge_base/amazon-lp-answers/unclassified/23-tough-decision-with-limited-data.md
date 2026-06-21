# Q: Tell me about a time when you made a tough decision with limited data.

> **LP**: Bias for Action / Are Right A Lot (hybrid)
> **Primary story**: `G2 — Beat Rate Limiting`
> **Backup story**: `W4 — Multi-Region Rollout`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

At GCC in late 2023, Beat — our Instagram scraping engine — started hitting rate limits more often. We were on RapidAPI's GraphAPI provider. The rate-limit responses weren't well-documented; sometimes 429, sometimes 200 with an empty body. I had a few hours of logs and a Slack message from the provider that said, roughly, "you're hitting too fast."

### Task

Drop our throughput enough to stop getting throttled without dropping it so much that we'd miss the daily 500K profile target. No clean signal on the right number.

### Action

I pulled the last 48 hours of request logs and counted by minute. Throughput peaked at 800 requests per minute per worker. Errors started climbing past 600. That gave me a noisy ceiling — somewhere between 400 and 600 was probably safe.

I had two options. Build a proper sliding-window rate limiter with provider-side calibration, which would take a week and would still be wrong if the provider changed its policy. Or pick a conservative number now and tune it from production data.

I went with conservative-now. Set the worker concurrency so the per-minute rate landed around 450, well under the noisy ceiling. Added a circuit breaker on the worker — if the last 20 calls saw more than 10 percent 429s, pause for 30 seconds. Logged every 429 with timestamp, endpoint, and worker ID so I'd have clean data after a week to actually tune.

The honest part is I had no proof 450 was right. It was a guess from a graph.

A week later, the logs told a clearer story. We held 450 RPM steady, 429s dropped to under 2 percent, daily target was hit. I bumped to 500 RPM and watched. Held. Pushed to 550 and saw 429s climb to 5 percent — backed off to 500 and left it there.

### Result

Daily scrape target stayed at 500K profiles. 429 rate dropped from ~15 percent at peak to under 2 percent. No more emergency Slack messages from the provider. The bigger thing — I stopped trying to design for unknown limits and started shipping to learn them.

---

## Technical depth — if they probe

- **Why a circuit breaker, not a fixed delay**: Provider rate limits aren't constant. A circuit breaker reacts to actual signal — if 429s spike, pause. If they don't, full speed. Fixed delays leave throughput on the table.
- **Worker concurrency math**: 150 workers, 5 concurrency each = 750 in-flight. Tuned the concurrency down to land at 450 RPM aggregate.
- **Logging strategy**: Every 429 logged with `endpoint`, `worker_id`, `ts`, `retry_after_header` if present. Aggregated nightly into a small SQLite for tuning.
- **What I'd do with more data**: Implement a token-bucket per provider with per-endpoint quotas. The provider eventually published their actual limits, and the bucket maps to those.

---

## Likely follow-ups

**Q: How did you know 450 was safe and not 300?**
> I didn't. I picked 450 because the noisy data said 600 was definitely too high, and 300 would've missed the daily target. Conservative-but-shipping beat perfect-but-late.

**Q: What if 450 had been too high?**
> The circuit breaker would've caught it within minutes — 10 percent 429 rate in a 20-call window means a 30-second pause. I'd have stepped down to 350 the same day.

**Q: Did you ever go back and build the proper rate limiter?**
> Once we had two months of production data, yes. Token bucket per endpoint, dynamic refill rate based on the provider's published headers. The provider eventually started sending `X-RateLimit-Remaining`, which made it almost trivial.

**Q: How did you communicate the uncertainty to the team?**
> I wrote up the decision as "best-guess 450 RPM, will re-tune from logs in 7 days." Posted the dashboard link in the team channel. The team knew the number was provisional, so when I bumped it to 500 a week later, nobody was surprised.

---

## What NOT to say

- "I just picked a number" — you picked a number based on visible signal and built monitoring to refine it. Tell that.
- Don't pretend you had a model. The honest version is "noisy graph, conservative guess, instrumentation to fix it later."
- Skip rate-limiting theory unless asked. Keep it concrete.

---

## Backup story (if asked for another)

At Walmart, when we needed multi-region resilience for audit logging, leadership said "make it resilient" without specifying RPO or RTO. I had no formal requirements doc. I wrote an assumptions document — RPO of 4 hours, RTO of 1 hour — and shipped Active/Active across East US 2 and South Central US in five weeks. The assumptions doc became the de facto spec after stakeholders reviewed it.
