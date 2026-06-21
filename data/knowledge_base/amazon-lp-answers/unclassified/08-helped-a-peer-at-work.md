# Q: Have you ever helped a peer at work?

> **LP**: Unclassified (Hire and Develop the Best + Earn Trust)
> **Primary story**: W11 — Unified Onboarding / IAM (junior engineer mentoring arc)
> **Backup story**: W2 — Helping the audit-library adopters
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Mid-2025 at Walmart. A junior engineer joined our team — fresh from a different org, no Apollo Federation experience, no GraphQL background. The hiring manager paired him with me on the unified onboarding work because I owned the Apollo Federation BFF.

His first month was rough. He'd shipped Spring Boot services before, but federation is a different mental model — schemas across subgraphs, `@key` directives, gateway query plans. He was hitting his head on N+1 issues and opaque federation errors. Week four, over coffee, he told me he was thinking about asking to switch teams. He felt like he was making everyone slower.

### Task

The "help" here wasn't a one-shot fix. He needed enough grounding in Federation that he could own a piece of it himself. Otherwise I'd be paired-on-him forever, and he'd never recover the confidence.

### Action

I made three calls about how I'd actually spend my time on this.

**One — pair on the keyboard, not at it.** First two weeks we paired daily, an hour each morning. He drove. I narrated. The first resolver he wrote had a textbook N+1 — for each user, a separate DB call inside a field resolver. I caught myself about to type the `DataLoader` fix. Stopped. Drew the schema on a whiteboard, asked him to trace the query plan, let him find the N+1 himself. He shipped a `DataLoader` batching fix that afternoon. The pattern clicked because *he* discovered it.

**Two — coach the wobble, not the technical issue.** Week four, the near-quit conversation. We went for coffee, out of the office. I didn't argue technically. I asked what was actually frustrating him. He said he felt slow. I told him the truth — his ramp was on track, the Apollo error he was stuck on had stumped me too at his stage, and the "I'm slow" feeling is the hardest curve in the first year of a new org. Naming it helped more than fixing it.

**Three — sponsor up.** I started telling our manager in 1:1s that this engineer owned the credential-management subgraph now. When the promo cycle came around, I wrote a strong recommendation for his SDE-2 case. The help wasn't just at the keyboard — it was making sure credit landed on him with the people who matter for his career.

### Result

He owns the credential-management subgraph end-to-end now. He's the on-call for it. He's reviewed federation PRs from other teams. Three months after the handover he found a federation directive bug that I would've missed — the schema-level fix made it into our internal Apollo guide. He got the SDE-2 promo on the cycle.

The deeper thing I took from it — helping a peer well is mostly resisting the urge to do the work for them. Plus the unglamorous part of telling other people the help happened, so the credit lands right.

---

## Technical depth — if they probe

- **Apollo Federation N+1**: federated field resolvers fetch per-entity data. Without batching, one DB call per parent entity. `DataLoader<string, Cred>` batches them inside a single tick of the event loop. Fix: `WHERE user_id IN (?)` in the batch loader.
- **The `@key` misconfig that nearly broke him**: federated entities join across subgraphs on `@key` fields. He'd marked `email` as the key on credentials; upstream onboarding subgraph used `userId`. Gateway error was opaque — "cannot find type". Actual cause was a key mismatch. Five-line schema fix once you find it.
- **Why whiteboard before IDE**: pulling a junior into the IDE risks them watching me type. Whiteboard forces them to articulate the design first. Slower start, faster long-term.

---

## Likely follow-ups

**Q: How did you know he was near-quitting before he said it?**
> Body language at standup, mostly. Quieter on calls. Two PRs in a row with apology messages in the description. The conversation didn't come out of nowhere — I'd asked him for the coffee specifically because something was off.

**Q: Were you ever tempted to just write the resolver yourself?**
> Constantly. Especially when he was stuck on the N+1 for almost a day. The pull was real. The discipline was reminding myself — if I write it, he learns nothing, and the next federation feature lands back on my plate. The hour I save today costs me weeks later.

**Q: What if your manager hadn't been supportive of you spending time mentoring?**
> I'd have done it on my own time, honestly, but my manager was supportive — he saw the leverage. One hour a day for six weeks gets me back 40 hours a week of his throughput forever.

**Q: Have you helped other peers since?**
> Yes — at smaller scale. A senior on a different team integrating the audit-logging library hit a `ContentCachingWrapper` ordering issue. I paired with him for an afternoon, fixed it, cut a patch release the same day. Different scope, same instinct.

**Q: Did you ever get frustrated with the slow ramp?**
> Once. Around week 5, I caught myself thinking "this should be faster by now". I checked the timeline I'd set for myself at the start — I'd budgeted six weeks. He was on track. The frustration was on me, not him. I let it go.

---

## What NOT to say

- Don't make yourself the hero. He did the work — you set the conditions.
- Don't claim the help was easy. The week-4 wobble is the realistic detail.
- Don't say "I delegated" — delegation is one-shot; helping a peer through a ramp is sustained.
- Don't skip the sponsor-up part. That's the line most engineers miss in mentoring stories — making sure the manager sees the work.

---

## Backup story (W2 — Helping audit-library adopters)

When I shipped the `dv-api-common-libraries` shared library, I spent half-afternoons pairing with each adopting team on their first integration PR. The Inventory Status team hit a `ContentCachingWrapper` ordering issue with their existing security filter — I caught it, fixed it, cut a 0.4.1 patch release the same day. The Transaction Events team hit a CCM property-naming collision — same pattern, same-day patch. The help wasn't a one-shot favour — it was the cost of making the library actually adopted instead of just published. Different shape from the W11 mentoring story but the same instinct: meet the peer where they are, then fix the friction so they don't bounce off.
