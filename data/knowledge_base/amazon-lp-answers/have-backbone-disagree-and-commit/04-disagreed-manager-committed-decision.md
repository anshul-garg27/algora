# Q: Tell me about a time you disagreed with your manager but eventually committed to their decision.

> **LP**: Have Backbone; Disagree and Commit
> **Primary story**: `W3 — DiscardPolicy Feedback`
> **Backup story**: `W5 — Spring Boot 3 Migration`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Spring 2025. I had just shipped the dv-api-common-libraries audit module to internal Maven. My manager wanted to roll it to all 12 team services in the next sprint. I had it on a 6-week phased plan — pilot on cp-nrti-apis, observe in production for two weeks, then roll to the next three, then the rest. He wanted it compressed to three weeks. "We have momentum, let's not waste it."

### Task

I thought he was wrong on the timeline. But he was the one who would carry the heat if anything broke. I had to argue the case once, listen, and then decide.

### Action

In our 1:1 I laid out the concern. The library uses a thread pool with `CallerRunsPolicy`. Under saturation, the calling thread does the audit publish — which means slow audit logging can slow down real requests. We had not run it at peak load on any of the 12 services yet. cp-nrti-apis was the pilot for a reason — it sees suppliers like Pepsi and Coca-Cola hitting our APIs all day. Two weeks at full traffic was the only way to know if the queue depth ever crossed 80%.

I made a counter-proposal. Pilot for two weeks on cp-nrti-apis. If queue-rejection metric stays at zero and P95 latency stays under 200ms, compress the rollout to four weeks for the remaining 11 services. That gives us safety on the unknown and pace on the known. He pushed back. His read was that the library was small (696 lines), well-tested (97% coverage), and the team needed the win. The instrumentation we had would catch problems either way.

I made my point one more time. Then I committed. I told him "I disagree on the speed, but I'll run it. Here's what I need." I asked for two things — a daily 10-minute sync during the rollout, and authority to pause if any service crossed 50% queue depth in the first 48 hours. He agreed to both.

Then I went and ran his plan, not mine. I did not slow-walk it. I built a runbook for each service team, did the integration myself for the first four (one-line Maven dependency + CCM config), and stood up a Grafana dashboard that showed queue depth across every service on one screen.

### Result

12 services integrated in three weeks. Zero outages. The queue-rejection counter stayed at zero. One service hit 60% queue depth during a Black Friday traffic spike four months later — the dashboard caught it, we bumped the pool size on that service in 10 minutes. He was right on the pace. I was right on the instrumentation being worth the time. We both made the library better.

Honestly, the part I had to learn was that disagree-and-commit is not theatre. Once I committed, I had to actually run his plan with the same energy I would have run mine. If I had executed at 80% to prove I was right, I would have just damaged the relationship and made the slower path look slower than it was.

---

## Technical depth — if they probe

- **The pool config**: 6 core, 10 max, queue 100, `CallerRunsPolicy`. The risk in fast rollout was caller-runs adding 10-50ms to request threads if downstream Kafka slowed.
- **Instrumentation I leaned on**: `audit_pool_queue_depth` gauge, `audit_pool_rejected_total` counter, WARN log at 80%. All exported to the team SLA dashboard.
- **The Pepsi-scale concern**: cp-nrti-apis sees ~100 req/s per pod with bursty supplier traffic. Pilot there meant the riskiest service got the longest validation window.
- **What the pause clause bought me**: Authority to stop the rollout if any service crossed 50% queue depth in the first 48 hours. Never used it.

---

## Likely follow-ups

**Q: How did you commit without sulking?**
> Built the runbook, did the first four integrations myself, ran the daily sync. The daily sync was the real tell — it kept us honest both ways.

**Q: What if it had broken?**
> The pause clause was the failsafe. We could halt the rollout in any service that crossed the threshold. The blast radius was contained to the next service in the queue.

**Q: Were you right or wrong in hindsight?**
> Wrong on the timeline. Right on the instrumentation being worth the time. He gave me air cover to over-invest in the dashboard, and that paid back four months later.

**Q: How did your manager react after?**
> He brought it up in our skip-level review as an example of how the team handles disagreement. That meant more than being right.

---

## What NOT to say

- Do not say "I was right" anywhere. The result said he was right on speed.
- Do not pretend you had no disagreement. The interviewer wants real disagreement, then real commitment.
- Do not skip the pause-clause negotiation — that is what made the commit honest.

---

## Backup story (if asked for another)

W5 — Spring Boot 3. A colleague wanted full reactive with WebClient. I argued for `.block()` so it stayed a framework migration, not an architecture rewrite. Tech lead leaned toward reactive. I prepared a side-by-side doc — 4 weeks vs 3 months — and we landed on `.block()` for now, reactive as a separate initiative if load demanded.
