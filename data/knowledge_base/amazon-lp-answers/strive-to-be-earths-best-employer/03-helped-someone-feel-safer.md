# Q: Tell me about a time you helped someone feel safer at work.

> **LP**: Strive to be Earth's Best Employer
> **Primary story**: `W11 — junior anxious about resolver failures, "private fail" branch+pairing pattern`
> **Backup story**: `W3 — created safe space for DiscardPolicy reversal`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Week three of pairing with the SDE-1 on the credential-mgmt subgraph. He'd shipped two resolvers cleanly. Then his third PR went up and he asked me to look at it before he marked it ready-for-review. I noticed he'd been doing that for every PR — getting my private blessing before opening to the wider team. The wider team's reviews were tougher; one senior had a reputation for blunt comments on early-career PRs.

### Task

The pattern wasn't sustainable. If he kept routing every PR through me first, he wasn't going to learn to defend his own work in public review. But just telling him to "be brave" wasn't going to fix it. The real issue was that public review didn't feel safe to fail in.

### Action

I asked him to walk me through what he was worried about. He said specifically: he was scared of getting a sharp comment in a public PR that made him look junior in front of the rest of the team. He'd already had one such comment in his first week and it had stuck with him.

I gave him a structure I called the "private fail" pattern, which is exactly what he was already doing — but I made it explicit and bounded. The deal: he could push to a `wip/` branch on the remote, ping me, I'd review it the same day. If the design was wrong, we'd fix it on the `wip/` branch privately. Once we agreed on the direction, *then* he'd open the public PR. The public PR would still get full team review, but it wouldn't have design-level mistakes in it.

The key rule I added: the `wip/` branch step had a sunset. Six weeks. After that he opened PRs directly to the public review channel. I gave him a date.

I also went and had a private conversation with the senior who'd been blunt. Same pattern as before — not a confrontation. I asked: when you leave a hard comment on an SDE-1's PR, can we frame it as "this is the bug + here's the canonical pattern", instead of just "this is wrong, read the docs." He took it well. Said he'd been on the receiving end of the same tone at his last company and hated it. He just hadn't noticed he was doing it.

Then I did the explicit safety part. I told my mentee: if you ever get a comment that feels harsh, screenshot it and send it to me. We'll talk through it in our 10 AM session. Not to escalate — just to make sure you're not carrying it home alone.

### Result

The `wip/` pattern ran for four weeks. He used it for the first two weeks, used it occasionally for week three, didn't use it at all by week four. The sunset date was self-enforcing — once his PRs were landing without rework on the `wip/` branch, opening them straight to public review felt fine.

He screenshotted exactly one comment in three months. We talked through it. The comment had actually been fine — he'd been pattern-matching to the earlier bad one. By month three he'd stopped flinching.

The senior who'd been blunt softened his code-review tone across the board. Two other SDE-1s told me later that the change was visible from the outside. So one conversation about one engineer ended up shifting the whole review surface a little.

The thing I notice with my mentee now: he runs the same `wip/` branch pattern with the newest SDE-1 on the team. He extended it to four weeks instead of six, because he thinks it should be shorter. Either way, the safety scaffolding got rebuilt for the next person.

---

## Technical depth — if they probe

- **Why `wip/` branches, not a feature flag**: Branches are a Git convention everyone understands. Feature flags would have been over-engineering for a process problem.
- **Why a sunset date**: Without one, the "safe" pattern becomes the default and you never learn to ship in public. The date makes it temporary scaffolding, not a permanent crutch.
- **The conversation with the senior reviewer**: Same technique as the wellbeing story — ask a question, don't make a statement. "Can we frame this differently?" lands better than "you were harsh."

---

## Likely follow-ups

**Q: Was the `wip/` pattern bypassing the team's review process?**
> No. Every PR still went through full public review before merge. The `wip/` step was a private design rehearsal, not a replacement for review.

**Q: How did you know when to remove the scaffolding?**
> When his `wip/` PRs stopped needing design changes. At that point, the public PR was going to look the same with or without the rehearsal — so the rehearsal had served its purpose.

**Q: What if the senior reviewer hadn't responded well?**
> I'd have gone to the team's tech lead. Not as a complaint — as a request to surface the pattern in our team's code-review norms. The conversation was the lower-cost first step.

**Q: How is "safety" different from "lowering standards"?**
> Safety means the consequence of being wrong is feedback, not embarrassment. Lower standards would have been merging his PRs without review. He still got every review comment — just in a form that didn't punish him for being new.

---

## What NOT to say

- Don't moralize about psychological safety — talk about the specific scaffolding I built
- Don't make the senior reviewer sound malicious — he wasn't, he was repeating a pattern from his own past
- Don't say "I made him feel safe" — say "I gave him a structure to fail in private until he could fail in public"
- Don't skip the sunset date — without it the story sounds like I was protecting him forever

---

## Backup story (if asked for another)

When I had to reverse my own DiscardPolicy decision after a senior caught silent event drops, I wrote the postmortem with my name on the wrong-call section first. The team had been uncomfortable disagreeing with my designs. After that postmortem, two engineers pushed back on my next design choice within a week. I think the explicit "I was wrong, here's why" made the room feel safer to disagree.
