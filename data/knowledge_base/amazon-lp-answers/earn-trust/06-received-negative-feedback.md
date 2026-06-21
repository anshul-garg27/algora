# Q: Tell me about a time you received negative feedback.

> **LP**: Earn Trust
> **Primary story**: `W3 — DiscardPolicy Feedback (long-term trust dividend angle)`
> **Backup story**: `P3 — Test Coverage Program`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Audit common library PR, late 2024. A senior engineer reviewed it and called out my thread-pool queue size as arbitrary — said it would silently drop audit records when full. The comment was direct, public on the PR, and honestly it stung.

The interesting part isn't what I did that day. It's what the feedback became over the next year.

### Task

In the moment: respond well. Long-term: figure out whether this was a one-off or a pattern I should be designing against everywhere.

### Action

Short version of the immediate fix — I'd defended on the PR first, sat with it overnight, walked it back at standup the next morning, and added three things before merge: a Prometheus counter for rejected tasks, a WARN log at 80% queue depth, and a README section spelling out the trade-off. He'd flagged one more — thread-name prefix for heap-dump readability — and I added that too.

The longer story is what I did with it after.

A few months later when I owned the observability roll-out across the whole supplier API platform, his feedback was sitting in the back of my head. The bar I set: every async path, every queue, every batch buffer needs a metric for what it dropped or rejected. Not just what it processed. That principle came directly from his comment. "Is it running?" isn't monitoring — "is it processing correctly without losing data?" is.

I went back through three other services I owned. Found similar patterns. The DSD notification dispatcher had an unbounded `LinkedBlockingQueue` with no depth metric. The DC inventory service had a `CompletableFuture` fan-out where individual exceptions were swallowed in the join. Both got instrumented. Both eventually caught real production issues — the DSD queue depth warning fired during a partner outage and let us drain gracefully.

I also changed how I reviewed other people's PRs. Specifically when someone added an async path or a thread pool, I'd ask: "what's the metric when this drops something?" That phrase came out of his review. I've used it on dozens of PRs since.

### Result

The audit library shipped. Production has fired the 80% queue warning twice — both downstream slowdowns, both pre-empted. But the bigger result was the principle. Three other services got instrumented because of one PR comment. The observability work I led across the team for 99.9% SLA was built on that bar — alert on what's dropped, not just what's processed.

The senior engineer became one of the people whose reviews I now seek out. We've built genuine working trust — he reviews my hard PRs, I review his. The trust didn't come from agreeing with him in 2024. It came from him seeing the pattern repeat in my code over the next year — that the feedback had actually become part of how I work.

---

## Technical depth — if they probe

- **The principle, stated**: Every bounded queue needs a depth gauge and a rejection counter. Every async path needs a metric for what it dropped. Every batch buffer needs a flush failure counter.
- **DSD queue example**: The notification dispatcher was using `LinkedBlockingQueue` with no depth instrumentation. Added a sampler thread emitting `dsd_dispatch_queue_depth` and a WARN at 80%. The warning fired during a downstream outage and gave us 15 minutes to drain gracefully.
- **DC inventory example**: `CompletableFuture.allOf(...)` was being joined with `.exceptionally(...)` that returned null. Individual item failures were vanishing into the response. Added a counter for `inventory_item_fetch_failures` keyed by failure stage.

---

## Likely follow-ups

**Q: How do you make a single feedback persistent like that?**
> I keep a doc — "design principles I want to remember." His comment turned into one bullet: "instrument what you drop, not just what you process." Re-read it when I do new design work.

**Q: Did you tell the senior engineer the feedback had become a principle?**
> Yes, about six months later when I gave a brown-bag on observability. I credited the principle to his review on the audit library. He laughed and said he'd forgotten about that PR.

**Q: What if the feedback had been wrong?**
> Then it wouldn't have become a principle. The test was: does this pattern keep showing up in real bugs? It did, multiple times, in multiple services. That's how I knew the bar was right.

**Q: Has any feedback failed that test?**
> Yes. A different engineer once told me to use `Optional` everywhere — said null was unsafe. I tried it for a sprint. The code got noisier without catching new bugs. Dropped the pattern.

---

## What NOT to say

- Don't make the immediate-fix story the whole story. The trust dividend is what makes this an Earn Trust answer.
- Don't claim the principle was already in your head. The honest version is one PR comment shifted how I design now.
- Don't say "I've never received negative feedback that was wrong" — that signals you don't filter.

---

## Backup story (if asked for another)

At PayU as an intern my mentor reviewed my first 40 end-to-end tests and called them brittle — too coupled to implementation, broke on every refactor. I rewrote them against the public service interface only and switched from state to behaviour assertions. That feedback turned into a habit — write tests against contract, not against implementation. It's why coverage at PayU got from 30% to 83% without becoming a maintenance burden, and why the tests survived three years of refactoring after I left.
