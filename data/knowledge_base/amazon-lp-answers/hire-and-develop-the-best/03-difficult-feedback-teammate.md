# Q: Describe a time you gave difficult feedback to a teammate.

> **LP**: Hire and Develop the Best
> **Primary story**: `W11 — junior's first resolver design with N+1 issues`
> **Backup story**: `G7 — peer Go onboarding feedback`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Three weeks into pairing with the new SDE-1 on the credential-mgmt subgraph, he shipped a resolver to staging that I'd seen twice already in PR review. Both times I'd left comments. Both times he'd marked them resolved without changing the code. The resolver was doing nested REST calls inside a GraphQL loop — classic N+1, and he knew the pattern by then.

### Task

I had to give him hard feedback without breaking the relationship I'd been building for three weeks. The temptation was to just fix it. The right move was to call out the actual issue — he was marking review comments resolved without actually addressing them.

### Action

I didn't do it in Slack and I didn't do it in the PR. Wednesday's 10 AM session, I closed my laptop. I said, "I want to talk about how we're doing code review."

I told him directly: I'd left the same comment in two PRs about N+1 queries. Both times he marked it resolved. The resolver still had N+1. That wasn't a knowledge gap anymore — we'd done DataLoader together. It was a process gap.

I didn't make it about him as a person. I made it about the artifact. "When you mark a comment resolved, the reviewer assumes the code changed. If it didn't, you're spending my trust." I used the word trust on purpose.

He got defensive at first. Said he thought he'd addressed it differently. I pulled up the diff. The lines were identical. He went quiet for about ten seconds.

Then I gave him the path forward. From now on: when you mark a comment resolved, paste the commit SHA where you addressed it. Takes ten seconds. Forces you to actually look at what you changed.

I also told him this was the only hard feedback I had for him that week. The rest of his work was good, and I told him specifically what — the schema he'd drawn for principal-product junction was cleaner than mine would have been.

### Result

He started pasting commit SHAs. Within a week, his PR review cycles dropped from three rounds to one. Two months later he told me that conversation was the one that made the biggest difference for him — not the technical lessons. He said it was the first time anyone had told him directly what he was doing wrong without dressing it up.

---

## Technical depth — if they probe

- **Why face-to-face, not Slack**: Hard feedback in text reads harsher than spoken. The same words at a whiteboard land differently than in a thread.
- **The SHA-paste trick**: Forces the author to re-read the diff before marking resolved. It's a forcing function, not a punishment.
- **Why I led with the ratio**: One piece of hard feedback per week, plenty of specific positive feedback. Otherwise the hard feedback becomes the whole relationship.

---

## Likely follow-ups

**Q: Did you escalate to his manager?**
> No. The first hard piece of feedback should be from the person who saw the issue. If it had repeated I would have. It didn't.

**Q: What if he'd rejected the feedback?**
> I'd have said okay, given it another week, then escalated. The escalation point is when behavior doesn't change after explicit feedback, not when someone bristles in the moment.

**Q: How did you keep it from feeling like an attack?**
> I described the artifact, not the person. "This PR has the same bug as last week's PR" is a fact. "You're sloppy" is an attack. Same content, different consequence.

**Q: Have you ever been on the receiving end of feedback like this?**
> Yes — a senior architect once told me my CompletableFutures were using the common ForkJoinPool and would exhaust it under load. He was right. I rewrote with a dedicated pool and propagated the fix to four other services. That feedback shaped how I give feedback now.

---

## What NOT to say

- Don't make it sound rehearsed — natural pauses are better than a script
- Don't claim he had no flaws after this — keep at least one ongoing growth area in the answer
- Don't say "I had to fix his code" — the point is he fixed it after feedback
- Don't drop into a HR-speak tone ("performance gap", "developmental opportunity") — talk like an engineer

---

## Backup story (if asked for another)

At GCC, a peer was new to Go. His first three PRs all had race conditions — unprotected map access in goroutines. I told him directly that `go test -race` would have caught all three. He pushed back on the friction. I showed him the panic stack from production. He started running `-race` locally and the issues stopped.
