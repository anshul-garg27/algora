# Q: Describe a time you sponsored someone for growth.

> **LP**: Hire and Develop the Best
> **Primary story**: `W11 — recommended junior for SDE-2 promotion`
> **Backup story**: `W2 — advocated for the integration leads' work on the shared library`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Early 2025. The SDE-1 I'd mentored on the credential-mgmt subgraph had been on the team for about ten months. Standard SDE-1 to SDE-2 timeline at Walmart is 18 to 24 months. His tech lead was reviewing the next promotion cycle and asked me a direct question: is he ready, or is it too early.

### Task

I had to make the call honestly. Telling his tech lead "yes" if he wasn't ready would set him up to fail in the panel. Telling him "no" if he was ready would cost the team a year of his growth. I'd been close to his work for ten months. I owed both of them a real answer.

### Action

I went and looked at his work over the last quarter before answering. Not a vague impression — actual artifacts.

Three things I checked. One, was he making design decisions, not just implementing them. Two, was he catching mistakes in others' code, not just his own. Three, was anyone else relying on him for technical judgment.

I pulled three specific examples for each. For design, his composite-cursor fix for principal pagination, the compensating-transaction pattern he wrote for orphaned ServiceNow tickets, and the index decision he'd made (and later reversed — which counts). For catching mistakes, three PR reviews where he'd caught a race condition I'd missed in someone else's code. For judgment, the next SDE-1 who'd joined was now coming to him for advice, not to me.

I told the tech lead: yes, with one note. He doesn't run room-level conversations yet — he's still quiet in larger design reviews. That's a growth area, not a blocker.

Then I did the sponsoring part. I offered to write the technical recommendation for his promo packet. The standard recommendation is two paragraphs. I wrote a full page with three specific design artifacts, links to the PRs, and a sentence on the orphaned-ticket fix being still in production six months later.

I also briefed him on what to expect. Promotion panel will ask for system-design ownership. He'd done it but never had to defend it under pressure. We did one mock panel — I played the skeptical reviewer, he walked through the credential-rotation design. I poked at the compensating-transaction pattern. He defended it cleanly.

### Result

His packet went through with one round of feedback — the panel agreed but asked for one more cycle of cross-team design ownership. He delivered that within a quarter. He cleared on the next review. Four months ahead of cohort.

I think the thing that mattered most wasn't the recommendation letter. It was the mock panel. He told me later that the question I'd asked him about the compensating transaction was almost word-for-word what the panel asked.

The honest part: a year before, I wouldn't have been confident sponsoring anyone for promotion. I didn't trust my own read. After this one, I started actively sponsoring two other engineers on the team — both have moved up since.

---

## Technical depth — if they probe

- **Why I waited to look at artifacts before answering**: Impressions are biased by recent events. Artifacts force you to see the whole quarter.
- **The three signals I used**: design decisions, catching others' mistakes, becoming a go-to. Those generalize beyond him.
- **The mock panel detail**: Cheap. One hour. Single biggest swing on his actual panel.

---

## Likely follow-ups

**Q: What if you'd thought he wasn't ready?**
> I'd have told the tech lead and him directly. Then made a six-month plan with two concrete growth areas. Sponsoring isn't a yes-or-no — it's "ready now," "ready in six months with X and Y," or "deeper concern."

**Q: How did you write the recommendation?**
> Three sections: design artifacts (with PR links and the specific decision), cross-team impact (the SDE-1 he was now mentoring), and a candid growth area (room-level facilitation). Honest balance reads stronger than pure praise.

**Q: Did anyone disagree with the sponsorship?**
> Yes — one staff engineer thought 10 months was too early. I gave him the three artifacts. He read the orphaned-ticket fix code, came back, said okay. Specifics over arguments.

**Q: What did you learn about sponsoring?**
> Two things. Mock panels are the cheapest high-leverage thing. And the written recommendation is read more carefully than people think — vague adjectives get filtered out, specific artifacts don't.

---

## What NOT to say

- Don't say "I got him promoted" — say "I sponsored, the panel decided"
- Don't skip the growth area — having one in the answer makes it credible
- Don't oversell — say "four months ahead of cohort", not "stunning rise"
- Don't make it about me as the kingmaker — the artifacts did the heavy lifting

---

## Backup story (if asked for another)

When the shared audit-logging library shipped, the integration leads on the twelve adopting teams had done real work — adapting CCM configs, sizing thread pools, integrating circuit breakers. I made sure their names were in the tech-talk slides and the Confluence page. Two of them got that visibility cited in their next promo cases.
