# Q: Where do you see yourself in 5 years?

> **LP**: Intro & Closers
> **Primary story**: W2 — Shared Library Adoption (the platform-thinker arc)
> **Backup story**: None — this is a forward-looking answer
> **Time budget**: 45–60 seconds spoken

---

## The spoken answer

Five years out, I want to be a senior engineer whose work shows up in other teams' commits, not just my own.

The pattern I've been chasing is platform work — the kind where you build something once and ten other teams use it. At Walmart, the closest thing was the shared audit-logging library. I built it for one team, but three teams picked it up in the first month, and integration dropped from two weeks to one day. That was the most satisfying outcome of the year — not because the code was hard, but because the leverage was real.

So five years out, the shape of my work is:

- Designing platform pieces that multiple teams build on — APIs, SDKs, frameworks
- Leading the technical direction on cross-team initiatives at Amazon scale
- Mentoring two or three engineers seriously, the way I'm doing with the junior on my team now
- Still writing code. I don't want to stop. The day I stop writing code is the day I stop being credible in design reviews.

At Amazon, that's somewhere between a senior SDE and a principal-track engineer — depending on what fits. The title matters less than the scope.

What I'm explicitly **not** chasing is people-management. I want technical leadership without losing my hands on the keyboard.

---

## Why this works

- **Concrete shape**, not vague aspiration. "Platform work where ten teams build on it" is something they can imagine you doing.
- **Grounded in evidence** — the W2 shared library story makes this real, not hypothetical.
- **Honest** about the IC track vs management. Most interviewers respect that clarity.
- **Open to Amazon's path** — you don't lock yourself into one title, you describe the work.

---

## Technical depth — if they probe

- **The shared-library evidence**: built `dv-api-common-libraries` as a Spring Boot Starter — `OncePerRequestFilter`, `@Order(LOWEST_PRECEDENCE)`, `ContentCachingWrapper`, `@Async` thread pool. Three teams pulled it in within four weeks. Integration: 2 weeks → 1 day.
- **What "platform piece" means to me**: not just shared code. It's a contract — versioned, documented, with a roll-out plan. The library shipped with a migration guide, a brown-bag session, and pairing time with each adopting team. That's what made it stick.
- **Why I keep coding**: the audit-system architecture worked because I'd just spent six months in the GCC ClickHouse migration. Senior engineers who stop writing code start designing for last year's problems.

---

## Likely follow-ups

**Q: Why not management?**
> I've coached a junior at Walmart for the last few months — mentoring through pairing, code reviews, design walkthroughs. I love that part. What I don't want is the calendar life of a manager — 1:1s, status, performance cycles. The IC track at Amazon, especially SDE-3 and above, lets me do the mentoring without the management overhead.

**Q: What kind of platform work specifically?**
> Backend infra — anything where multiple teams are solving the same problem differently. At Walmart it was audit logging. At Amazon it could be auth, observability, event delivery, internal SDKs. The specific domain matters less than the leverage shape.

**Q: How does Amazon fit into that?**
> Amazon's whole structure rewards platform work — two-pizza teams owning services that other teams consume. The bar for principal-track engineers is real cross-team impact, not just code volume. That's exactly the trajectory I'm chasing.

**Q: What if you change your mind in 2 years and want to manage?**
> Then I'll manage. I'm not religious about it. But I want to make IC-track the default, not the fallback, and I'm being upfront about that now so we're aligned.

---

## What NOT to say

- Don't say "VP" or "director" — at SDE-3 entry, that reads as either arrogance or lack of self-awareness.
- Don't say "I want to start my own company" — kills the conversation instantly.
- Don't say "I'm not sure" — five years is the standard question, you should have thought about this.
- Don't promise loyalty ("I'll be at Amazon for 5 years for sure") — interviewers know that's not how careers work. Talk about the work, not the badge.
- Don't pretend you want management if you don't. The fit will be wrong and you'll regret it.

---

## Spoken-vs-written delivery note

- Open conversationally: "Five years out..." — not "In five years I envision myself...".
- The W2 library example should feel like an aside, not a pitch. "The closest thing was..." is the right framing.
- Pause before "What I'm explicitly **not** chasing". That's the line that separates a generic answer from a real one — let it land.
- 45–60 seconds. If you go past 75, you're rambling.
