# Q: Tell me about a time you had to coach someone through a tough situation.

> **LP**: Hire and Develop the Best
> **Primary story**: `W11 — junior nearly quit during week 4 frustration`
> **Backup story**: `W2 — team lead who resisted the shared library, talked through their forks`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Week four of pairing with the SDE-1 on the credential-mgmt subgraph. He'd been doing well — composite cursor was shipped, the resolver for principal-credentials was clean. Then he hit Apollo Federation entity references and got stuck for three days. By Friday of that week, he was distant in our pairing session. I asked if he was okay. He said he was thinking about whether engineering was right for him.

### Task

This wasn't a technical coaching moment. It was a confidence moment. If I said the wrong thing he'd either dig in worse, or actually walk. I had a junior engineer telling me he was considering quitting his first SDE role, three weeks before his probation review.

### Action

I closed the laptop. Didn't try to solve the Apollo Federation bug.

I asked him to tell me what was going on. Not "what's the bug" — what was actually going on. He said the work felt like it was getting harder every week, not easier. He'd assumed by week four he'd be writing code faster than week one. He was writing it slower. He took that as a signal he wasn't cut out for this.

I told him something specific. Week one, he was writing his first resolver — a simple list endpoint. Week four, he was doing federated entity resolution with caching and a fallback path. The complexity had gone up four times. His speed had gone down maybe 20%. Net, he was four times more productive than week one. He just couldn't see it from inside.

I pulled up his week-one PR and his week-four PR side by side. Showed him the difference in scope. He hadn't looked at his own progress that way.

Then I told him something he probably needed to hear and probably didn't want to. The feeling he was having — the dip at week four — happens to everyone. Including me. Including the staff engineers he was intimidated by. The difference isn't that they don't feel it. They've just felt it enough times to know it passes.

I didn't tell him to push through. I told him to take Monday off — actually off, no laptop. Come back Tuesday and we'd look at the Apollo Federation bug together. Fresh eyes.

He took Monday. Came back Tuesday. We fixed the bug in 90 minutes. Most of it he found himself once he wasn't burnt out.

### Result

He didn't quit. He passed probation. Six months later he was up for SDE-2 four months ahead of cohort. A year later he was mentoring the next SDE-1.

He told me eight months in that the Monday-off thing was the moment that mattered. Not the technical mentoring, not the design reviews, not the promotion sponsorship. The fact that I told him to stop instead of pushing through.

I think about that one a lot. The most useful thing I did as a mentor that whole year was tell him to take a day off. The rest was scaffolding.

---

## Technical depth — if they probe

- **Why I didn't try to solve the technical bug first**: When someone is questioning whether they belong in the field, fixing the immediate bug doesn't solve the underlying issue. It just delays it.
- **The week-one vs week-four artifact comparison**: Pulling up actual PRs gave him evidence against his own internal narrative. Stories don't fight stories — evidence fights stories.
- **Why I told him to take Monday off, not just rest**: A vague "rest more" doesn't change behavior. A specific instruction does.

---

## Likely follow-ups

**Q: Did you tell his manager?**
> No. He told me in confidence. Telling his manager would have broken trust and made the next conversation harder. I'd have escalated only if I thought he was in real distress beyond burnout.

**Q: What if he had quit?**
> Then he'd have quit. My job wasn't to keep him — it was to help him make a real decision instead of one made on three days of frustration. If he'd taken Monday off, come back, and still wanted to leave, that's a different answer.

**Q: How did you know to coach the confidence, not the code?**
> The signal wasn't the bug. He'd been stuck before and worked through it. The signal was the distance in pairing and the "is engineering for me" language. That's not a code problem.

**Q: Have you ever been on the receiving end of this?**
> Year one at GCC. I was sole architect across six services and I was drowning. My manager told me to take three days off and come back. I almost didn't go. That's where I learned the pattern.

---

## What NOT to say

- Don't make it sound like a pep talk — it wasn't, it was a structured conversation
- Don't claim I "saved him" — he made the choice, I just made the case
- Don't generalize ("this works with everyone") — it worked because he was specific kind of stuck
- Don't skip my own version of the same dip — it makes the answer human

---

## Backup story (if asked for another)

When the shared audit-logging library was rolling out, one team lead was openly hostile — he'd written his own audit framework and felt the library was a not-invented-here put-down. I asked for 45 minutes. Walked through his framework's three known bugs and showed how the library handled them. Didn't tell him his code was bad. Showed him where ours had more reps. He adopted the library a week later and became one of the loudest advocates for it.
