# Q: Tell me about a time you helped create a more inclusive environment.

> **LP**: Strive to be Earth's Best Employer
> **Primary story**: `W11 — inclusive code-review norms when onboarding non-CS-degree junior`
> **Backup story**: `W2 — shared library adoption pair-programming sessions`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Summer 2024, the SDE-1 who joined our unified-onboarding team had a mechanical engineering degree, a coding bootcamp behind him, and six months of Node.js work. Everyone else on the team had a CS degree from a top engineering college. In his first three weeks, I noticed two things. He didn't speak in design reviews. And his PR comments from other reviewers used a lot of acronyms — CAP, BASE, ACID, two-phase commit — without explaining them. He'd nod, mark resolved, and move on.

### Task

Nobody was being unkind. The culture had just calibrated to people who already knew the vocabulary. The result was the same — he was learning slower and contributing quieter than he should have been. I wanted to change the room's habits, not just help him personally.

### Action

I started with one rule for myself. In any code-review comment, I'd spell out the concept the first time and link to the canonical doc. "This is an N+1 query (each row triggers a separate downstream call — see Apollo Federation DataLoader docs)." Took me an extra 30 seconds per comment. I did it for two weeks straight.

Then in our team's PR-review channel, I called out one specific pattern. A reviewer had commented "watch CAP here" with no other context. I replied in-thread, not as a callout, with a quick explanation of what CAP meant for that specific code path. The reviewer thanked me. He hadn't realized the comment was opaque to someone without that background.

Within a month, two other senior engineers started doing the same thing. We didn't make a rule. It became a habit because the comments were higher signal — even for senior reviewers, explaining the *why* surfaced things we'd been hand-waving.

For design reviews, I changed our default. The room had been "explain the design, take questions." I switched the rooms I ran to "explain the design, then everyone shares one assumption they want validated." That last bit gave the quieter engineers — not just my mentee — a structured turn to speak. He spoke in his second design review. By month four he was running them.

The last thing I did was the one I almost skipped. I told him directly: this room's vocabulary defaults to a specific background. That's not your gap to close alone. Some of it is mine and the rest of the team's gap to spell out. That conversation reframed the imposter feeling he was carrying.

### Result

He started contributing in design reviews by month two instead of month six. The "spell out the concept" code-review norm spread to about half the team within a quarter. The "share one assumption" structure stuck — three other team leads use it now. Three more SDE-1s have joined since, two from non-CS backgrounds, and the ramp time has dropped noticeably.

The thing I'm proudest of: my mentee now runs his own pairing sessions for the newer SDE-1s. The norm went one more layer down without me being involved.

---

## Technical depth — if they probe

- **The "spell out the concept" norm**: 30 extra seconds per PR comment. Trade-off: senior reviewer time vs. junior comprehension. The trade is heavily on the side of comprehension.
- **The "one assumption" structure**: Forces every attendee to have a position. Quieter engineers get a turn. Skeptical engineers can challenge assumptions instead of conclusions.
- **Why I didn't make it a rule**: Rules get followed grudgingly. Habits spread because they're better. I demonstrated, then waited.

---

## Likely follow-ups

**Q: How did you frame it to senior engineers without it sounding like criticism?**
> I didn't frame it. I just did it in my own comments and waited. When two seniors picked it up themselves, it was their choice, not my mandate.

**Q: What if his background really had been a gap?**
> Vocabulary isn't a gap — it's exposure. He had the thinking. He'd just never been in rooms that used the words. Two months of being in those rooms fixed it.

**Q: Did anyone push back?**
> One senior thought the explanations made code review slower. I pointed out the second-order benefit — explaining "why" caught two real design bugs that month that "watch CAP" comments hadn't. He stopped pushing back.

**Q: How do you separate inclusion from lowering the bar?**
> Inclusion is removing the unrelated friction so the actual bar applies to everyone. Spelling out an acronym doesn't lower the bar — it makes the bar legible.

---

## What NOT to say

- Don't make this about diversity rhetoric — talk about specific behaviors that changed
- Don't paint the team as exclusionary — they weren't, they just had unexamined habits
- Don't claim I solved inclusion — claim I shifted two specific norms
- Don't skip the part where my mentee now runs pairing for newer joiners — that's the proof

---

## Backup story (if asked for another)

For the shared audit-logging library rollout, twelve teams had to integrate, and the team leads had different experience levels with Spring Boot internals. I ran Friday office hours as a screen-share, no-judgment forum — "show your error, we'll figure it out together." Three integration leads later told me it was the first time they'd been able to ask a "stupid question" without feeling stupid. Eleven small bugs got caught in those sessions instead of becoming late-night incidents.
