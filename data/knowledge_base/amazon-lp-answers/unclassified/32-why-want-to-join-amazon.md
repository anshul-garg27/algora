# Q: Why do you want to join Amazon?

> **LP**: Intro / Why-Company
> **Primary story**: `W12 — Why-Leaving Framing`
> **Backup story**: `G1 — ClickHouse Migration`
> **Time budget**: 60–90 seconds spoken

---

## The honest answer

This question shows up twice in the bank (see also `31-why-choose-amazon`). Same instinct, slightly different angle here — this one I lead with the work, not the values.

The simplest answer: I want to keep doing what I'm doing, at a scale that forces me to think differently.

At Walmart I built an audit pipeline doing 2M+ events a day with under 5ms P99 overhead. At GCC I rebuilt a 10M-events-a-day log pipeline from Postgres into RabbitMQ-and-ClickHouse — 5x compression, about 30% cost reduction. Both taught me that scale changes which design rules apply. Amazon is another two or three orders of magnitude up, and I want to be in the room where those calls actually get made.

The work shape also matters. Amazon's six-pager and working-backwards culture suits how I actually think. When I disagreed with a teammate over reactive-vs-`.block()` during the Spring Boot 3 migration, I didn't argue in the room — I wrote a one-pager, scheduled a 1:1, and presented both options with tradeoffs. He agreed to `.block()`-now-reactive-later. That's a six-pager motion. I read the Bezos memo on memos years ago and it described what I was already doing without a name for it.

And the ownership model — single-threaded leadership, one person owning one mission — matches the trust I've had at GCC (sole architect across six services) and at Walmart (led the SB3 migration across six services for our team). Amazon's L5/L6 ladders are the natural next two rungs of that path.

If I'm being specific about *which* parts of Amazon — supplier-facing surfaces (Selling Partner, Marketplace) because my Walmart experience is direct domain transfer. Or AWS data services because of the ClickHouse work. Both fit the shape I'd take next.

---

## If they push harder

**Q: What about Amazon's reputation for high stress?**
> I've heard both sides. I work hard at Walmart already — multi-week migrations, multi-day incidents, the audit silent-failure took me five days of dig. I'd rather be on a team where everyone matches that intensity than be the only one. The stress story I worry about is bad teams, not high bars.

**Q: How does this fit your three-year plan?**
> Get to L6 (SDE-III), own a piece of a supplier-facing or data surface end-to-end, and write a six-pager I'd be proud of. Concrete, not aspirational.

**Q: What would make you turn down the offer?**
> A team that doesn't write things down, or a manager who treats LPs as ceremony. Both would be unusual at Amazon but I'd ask in the team-match round.

**Q: How are you preparing?**
> I've gone through the LPs against my actual stories — 200+ behavioral prompts mapped against W1 through W12 and G1 through G11. Mock-interviewed twice this week. Reading "Working Backwards" properly, not just the famous excerpts.

---

## What NOT to say

- "I want to learn from the best engineers" — vague flattery.
- "Amazon is on my bucket list" — Amazon isn't a bucket-list company; it's an employer with a culture.
- Don't promise "I'll stay for 10 years." Be honest — two to three years before re-evaluating is fine.
- Don't lead with comp or relocation perks. They're real; they shouldn't be the answer.

---

## Backup angle (G1 — ClickHouse Migration)

If they want a project-led answer rather than a values-led one: the ClickHouse migration at GCC is the cleanest example of what I want to keep doing. I was the sole architect — designed the RabbitMQ buffer, the buffered sinker in Go with 1000-record batches, the MergeTree schema partitioned by month and sorted by `(platform, profile_id, event_timestamp)`. Ran dual-write for two weeks, parity-checked nightly, flipped reads on a feature flag. Zero data loss, 5x compression, 30 percent infra cost drop. That kind of end-to-end ownership is what Amazon calls single-threaded leadership. I've done it at GCC scale; I want to do it at Amazon scale.
