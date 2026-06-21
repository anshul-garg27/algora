# Q: Share an experience when you had to act quickly without having all the necessary data.

> **LP**: Unclassified (Bias for Action + Are Right A Lot)
> **Primary story**: G2 — Beat Scraping Engine rate-limiting incident
> **Backup story**: P2 — Disbursal TAT 3.2 min → 1.1 min
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

GCC, mid-2023. The Beat scraping engine pulled influencer profile data from Instagram, YouTube, and Shopify on a continuous schedule — about 8 million images and 10 million profile updates a day. One evening, the Instagram side started returning 429 rate-limit errors at scale. Within an hour, almost all our scraper workers were on the rate-limit floor and the data freshness our customers depended on was dropping fast.

I didn't know the new rate-limit threshold. Instagram doesn't publish them. I didn't know if it was a global change, a per-IP change, or our usage pattern hitting a new heuristic. What I knew was — every hour we sat on this, customer dashboards went more stale.

### Task

I was the SE-I owning the scraping engine. I had to act fast — reduce the rate-limit hit while keeping enough throughput to not bleed customer freshness — without waiting for Instagram to clarify what the new limit was.

### Action

I went with the cheapest reversible action first.

**Step one — cut the request rate by 50 percent across the board.** Took 5 minutes — the worker pool size was a config value, dropped from 150 to 75 async workers, redeployed. That bought breathing room and made the next 30 minutes' data usable instead of throwing 429s.

**Step two — add jitter and exponential backoff on the retry path.** The existing retry was a fixed 1-second sleep, which made our retries land in the same window and bunch up. I shipped a jitter patch with 1–5 second random backoff on the first retry, doubling thereafter. 20-minute change, deployed.

**Step three — adapt the request rate to the observed signal.** I added a simple feedback loop — track 429s per minute, and if it spiked above a threshold, halve the worker pool; if it stayed clean for 10 minutes, increase by 25 percent. Crude, but it self-corrected without me sitting on the keyboard. Wrote it on Friday evening, deployed by midnight.

**Step four — instrument and wait for data.** I added Prometheus metrics for 429-rate by endpoint, retry-success-rate, and effective-throughput. Over the weekend the system found its own floor — about 95 workers, roughly 60 percent of original throughput, sustainable without 429s.

**Step five — once the data came in, fix it properly.** On Monday I had two days of metrics. The pattern showed Instagram was rate-limiting on a sliding 1-hour window of distinct user-agent fingerprints. I rotated user-agent strings across the worker pool — recovered to about 90 percent of original throughput by the end of the week.

### Result

Customer-visible data freshness dipped about 30 percent during the worst hour, recovered to baseline by Monday morning, and was above baseline by Friday. No customer escalations. The feedback-loop pattern I'd written on Friday evening became permanent — three other scrapers in the system got the same self-tuning loop within a month.

The deeper thing I took from it — when you don't have data, you act in *reversible* steps. Cut rate, add jitter, instrument, wait. Each step was easy to undo. The mistake would've been making a permanent architectural change in hour one based on a hunch.

---

## Technical depth — if they probe

- **Why halve the workers first**: cheapest reversible move. Single config value, redeploy in 2 minutes, undoable in 2 minutes. Lets me get to "data flowing again" while I think about a real fix.
- **Jitter with exponential backoff**: fixed-interval retries bunch up — 100 workers all retrying at exactly T+1s creates a thundering herd. Random 1–5s on first retry, then `2^n * base` with jitter, breaks the herd.
- **The feedback loop**: Prometheus scrape of `429_total` rate, threshold check every 60s, AMQP message to the scheduler to adjust worker pool size. Crude PID-ish behaviour without the math — proportional response, no derivative or integral term. Worked because the response surface was monotonic.
- **User-agent rotation**: kept a pool of about 200 plausible UA strings and rotated per request. Instagram's rate-limiting was per-(IP + UA) hashed. Rotation distributed the load across UA buckets within the IP we owned.

---

## Likely follow-ups

**Q: How did you decide which steps were reversible?**
> Test: can I undo it in less than 5 minutes with no customer impact? Worker pool size — yes. Retry policy — yes. Feedback loop — yes (just disable the controller). User-agent rotation came later because it touched the user-facing request shape and needed more thought.

**Q: What would you have done differently with more time?**
> Same first three steps, in the same order. Step five — the user-agent rotation — I'd have wanted a partner conversation with Instagram first, but we didn't have a contact. In hindsight I'd have escalated for the partner relationship earlier; we eventually got it but it took months.

**Q: What if the 50-percent cut hadn't worked?**
> I'd have cut to 25 percent. Same shape, more conservative. The principle was "buy breathing room first, optimise after". Going from 150 to 75 to 38 is just continued application of the same rule.

**Q: How do you balance speed and correctness in something like this?**
> The speed is in *acting*. The correctness comes from *reversibility*. As long as the action is undoable, speed wins. I'd never have pushed an architectural change in hour one — that's a one-way door. Cutting a worker count and adding jitter are two-way doors.

**Q: When have you done this since?**
> The audit-logging incident at Walmart (W1) — same pattern. Day 1, I shipped an SMT null-header fix without yet knowing how many other bugs were underneath. The shape was the same: reversible step, deploy, observe, iterate. The W1 incident took five days; this Beat one took a long weekend.

---

## What NOT to say

- Don't claim you had perfect information — the whole question is about acting *without* it.
- Don't make the steps sound planned in advance. The "five steps" framing emerged from the experience — narrate it that way.
- Don't skip the reversibility point. That's the senior-engineer signal in this story.
- Don't end on "and I learned to gather more data" — that's the wrong lesson. The lesson is "I learned to act in reversible steps when data is incomplete".

---

## Backup story (P2 — Disbursal TAT cut at PayU)

When I was an intern at PayU, the loan-disbursal TAT was averaging 3.2 minutes — too slow for the conversion funnel. I didn't have detailed timing data per stage. I knew the high-level flow: credit check, KYC, partner-bank pre-check, disbursal. Without per-stage telemetry, I made a quick call — parallelise the three pre-checks using `CompletableFuture.allOf`, because none of them depended on each other's output. Deployed, watched the TAT drop to about 1.8 minutes. Then I added per-stage metrics and found the next bottleneck — partner-bank rate-limit windows. Added a Redis cache, dropped TAT to 1.1 minutes. Same pattern as the Beat story — act on the cheap reversible move first, instrument as you go, refine once you have data.
