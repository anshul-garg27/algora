# Q: Describe a time you helped a struggling team member.

> **LP**: Hire and Develop the Best
> **Primary story**: `W11 — junior stuck on Apollo Federation N+1 debugging`
> **Backup story**: `G7 — peer Go onboarding`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Week four of pairing with the new SDE-1 on the credential-mgmt subgraph. He'd been doing fine for three weeks. Then he hit Apollo Federation's `__resolveReference` and couldn't get past it. His resolver was returning data, but the federated query downstream was returning nulls. He'd been on it for three days when I noticed his standup updates getting shorter.

### Task

He hadn't asked for help. That was the tell. Three days on the same bug without escalating meant he was either close, or stuck and embarrassed. I needed to figure out which without making him feel watched.

### Action

I didn't ask "are you stuck?" That question rarely gets an honest answer. I asked, "show me where you are." We pulled up his branch.

He had the resolver wired. The `@key` directive was on the `Principal` type. But his `__resolveReference` was reading from a stale cache instead of the database. I could see the bug in about two minutes. He'd been staring at it for three days.

I didn't fix it. I asked him to run the resolver with a debugger attached and step through line by line. He hit the cache lookup. The cache returned null. The fallback path wasn't wired. He saw it himself.

Then I did the thing that actually helped. I told him directly: three days on a bug is a signal. Not that you're bad — that you're stuck in your own head. The rule going forward: if you're 90 minutes into a bug without a working hypothesis, you ping me. I won't fix it for you. I'll ask one question that gets you unstuck.

We added that to our pairing notes as a written rule. Ninety minutes. Ping. One question.

I also told him something he probably needed to hear. Senior engineers get stuck too. The difference is they call it out earlier. Asking for help isn't a junior trait — it's a calibrated trait.

### Result

He shipped the fix that afternoon. Took him 20 minutes once he had the debugger pattern. More importantly, the 90-minute rule stuck. Over the next two months he pinged me maybe eight times. Each ping was a real stuck moment, and each one cleared in under 15 minutes of conversation. Two of those would have been multi-day rabbit holes if he'd kept going alone.

The pattern spread. He uses the same 90-minute rule with the next SDE-1 who joined the team after him.

---

## Technical depth — if they probe

- **What `__resolveReference` does**: When another federated subgraph references your entity by key, Apollo calls your `__resolveReference` to hydrate it. If it returns null, the federated query silently returns null for that field — no error, no log. Easy to miss.
- **Why the debugger helped**: Print statements get drowned in a federated request. Stepping through forces you to see the actual path taken.
- **The 90-minute number**: Loose rule of thumb. Long enough to do real work. Short enough that you haven't burned a day.

---

## Likely follow-ups

**Q: How did you spot he was stuck if he didn't ask?**
> His standup updates got shorter. Three days of "still working on the resolver" without a hypothesis is a tell.

**Q: Why didn't you just tell him the answer?**
> If I'd said "your cache is returning null", he'd have learned that one bug. By making him find it with a debugger, he learned the technique for the next ten bugs.

**Q: Did you ever break the 90-minute rule yourself?**
> Yes — I sat on a Kafka silent-failure bug for five days because I was convinced I was close. I should have pulled in a Kafka engineer on day two. That experience is why I gave him the rule.

**Q: What's the line between helping and rescuing?**
> Help means you stay on the keyboard. Rescue means I take the keyboard. The rescue version teaches nothing.

---

## What NOT to say

- Don't frame him as a charity case — say "he was stuck on a hard Apollo Federation problem"
- Don't make the 90-minute rule sound rigid — it's a guideline
- Don't take credit for his fix — he wrote it
- Don't say "I made him better" — say "he built habits that stuck"

---

## Backup story (if asked for another)

At GCC, a peer joined who'd never written Go before. His first three PRs had race conditions on map access in goroutines. I paired with him for one hour to run `go test -race` together, watched the panic, walked through the fix. After that he ran `-race` in pre-commit hooks himself. Same idea — give the tool, not the answer.
