# Q: Tell me about a time you worked to improve team culture.

> **LP**: Strive to be Earth's Best Employer
> **Primary story**: `W2 — pair-programming sessions for shared library adoption became team norm`
> **Backup story**: `W11 — explanation-first code-review style spread`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Early 2025 at Walmart Data Ventures. I was rolling out the shared audit-logging library to twelve teams. The org's default for cross-team library rollouts had been: ship the library, write a README, post in Slack, hope teams figure it out. The pattern that resulted was predictable. Three teams adopted, nine got stuck, eventually four of those gave up and forked their own version. Knowledge silos, duplicated bugs, no shared muscle.

### Task

I didn't want this rollout to follow that pattern. The library was the easy artifact. The harder thing to change was the team's expectations for how cross-team work was supposed to feel. I wanted "ask for help" to be the default, not the exception. The technical adoption was a vehicle for the culture change.

### Action

Three moves. None of them were technical.

First, I ran Friday office hours. Open Zoom, one hour, every Friday for a quarter. Anyone from the twelve adopting teams could join, share their screen, walk through their integration. No agenda. No slides. Just bring your error.

The first session had two attendees. Second had four. By week six, twelve regular attendees plus drop-ins. The format spread sideways — two other library owners on adjacent teams started their own office hours within a month.

Second, I changed how I reviewed integration PRs. Instead of one-line approvals, I left detailed comments explaining the *why* — even on PRs that were technically fine. "This works, but here's a subtle gotcha you might hit in production: the audit executor pool defaults to the common ForkJoinPool, which..." Took me 10 extra minutes per PR. The integration leads started doing the same on each other's PRs. By the end of the quarter, the team's PR comments were noticeably more substantive across the codebase, not just on the audit library.

Third, I did the unglamorous one. When a senior architect found a CompletableFuture bug in my own code, I wrote up the lesson — root cause, the math for pool sizing, the four other services where I'd found the same bug — and shared it in our engineering channel with my name on the original mistake. Not as a humblebrag. As a "I made this mistake, here's what I learned, here are the four PRs I sent to fix it elsewhere."

That post got more replies than anything I'd written that year. Three other engineers wrote up their own "I was wrong about X" follow-ups in the next month. That was the cultural shift I actually wanted — being publicly wrong became something you got credit for, not penalized for.

### Result

The library went from one team to twelve in three weeks. Integration time per team dropped from a worst-case 40 hours to under one hour. But the actual cultural metric was different: a quarter later, three more cross-team libraries shipped using the same office-hours + teaching-PR-review pattern. The "ship and pray" default had quietly shifted.

The "I was wrong about X" pattern persisted longer. Two years later I still see those posts in the engineering channel.

The thing I'd say if pushed: a library is just an artifact. The artifact reaches twelve teams. The culture change reaches the whole org. I didn't set out to change the culture — I just set out to make the rollout not feel terrible. Culture changes are usually accidents downstream of trying to do something concrete well.

---

## Technical depth — if they probe

- **Why office hours, not 1:1 support**: 1:1 doesn't scale and creates knowledge silos. Group format means every fix gets seen by eleven other teams.
- **The teaching code review style**: 10 extra minutes per PR. Worth it because the comment educates the reviewer's reviewers too — it scales N-ways.
- **The CompletableFuture postmortem**: Common ForkJoinPool is 8 threads JVM-wide. Blocking I/O exhausts it. The lesson generalized because the pattern was everywhere.

---

## Likely follow-ups

**Q: How did you measure cultural change?**
> Three signals. Office hours format spreading to other library owners. Detailed PR comments becoming the team default. "I was wrong about X" posts going up. None of those are direct metrics, but together they pointed the same direction.

**Q: Did anyone push back on the office hours?**
> One manager thought it was a time sink. I showed him the numbers — eleven bugs caught in office hours that would have been late-night incidents. He stopped pushing back.

**Q: What if the "I was wrong" post hadn't landed well?**
> Then it would have just been a lesson with my name on it. The downside was small — I'd already shipped the fixes. The upside was the cultural permission, which is what actually happened.

**Q: How is this different from "tech talks" or "lunch and learns"?**
> Office hours are reactive — bring your real problem, get help. Tech talks are presentational — listen to someone else's polished narrative. Reactive is higher-signal for adoption work.

---

## What NOT to say

- Don't make this sound like a culture program — it wasn't, it was a rollout that happened to shift culture
- Don't say "I changed the company's culture" — say "three patterns I started spread further than the library did"
- Don't claim I planned the cultural change — it was a side effect of doing the rollout well
- Don't skip the "I was wrong" post — that's the part that lands

---

## Backup story (if asked for another)

The explanation-first code-review style I used with the SDE-1 I mentored — spelling out the concept, linking the canonical doc — got picked up by two senior engineers within a month. They started doing the same on their own PRs without me asking. A year later it was the team default. Culture is mostly demonstration plus patience.
