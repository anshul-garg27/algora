# Q: Why do you choose Amazon?

> **LP**: Intro / Why-Company
> **Primary story**: `W12 — Why-Leaving Framing`
> **Backup story**: `W6 — Supplier Self-Service`
> **Time budget**: 60–90 seconds spoken

---

## The honest answer

Three things, in order of how much they actually drive the choice.

**One — the technical surface area.** I've spent the last three and a half years on systems that look small next to Amazon's. The Kafka audit pipeline I run at Walmart processes 2M+ events a day across two regions; Amazon's Kafka clusters do that in seconds. The DC inventory API serves 30K queries a day; Amazon's catalog serves orders of magnitude more. I want to work on problems where my current bottleneck assumptions stop being true. The scale forces different design tradeoffs — I'm curious what those look like from the inside.

**Two — the LPs aren't just posters.** I've read enough writeups and talked to enough Amazonians to know the LPs actually show up in design reviews and promo discussions. "Dive deep" and "insist on the highest standards" describe what I already try to do — I caught the silent Kafka failure by reading metrics at 11 PM on a Tuesday, not because anyone asked. "Customer obsession" maps to why I pushed for supplier self-service in the audit system instead of just internal logging. The framework matches how I want to keep working.

**Three — the ownership culture.** At Walmart Data Ventures I owned six services across the Spring Boot 3 migration and three teams adopted my shared library. At GCC I was the sole architect for six services as an SE-I. Both places gave me trust. Amazon's "single-threaded ownership" model is the natural next step — one person, one mission, no shared accountability dilution.

What I'm specifically *not* saying: I'm not coming for prestige or to escape Walmart. Walmart's been good to me. I'm coming because the next two years of my growth are about operating at a scale and pace I can't get where I am.

---

## If they push harder

**Q: Why not Google or Meta?**
> I considered both. Google's interview process is in flight too. Honest version: Amazon's LP system maps closer to how I actually work — written documents, six-pagers, working-backwards. I'm a writer-thinker. PRFAQs would suit my brain. Google leans more meeting-driven from what I've seen.

**Q: What team or org are you most interested in?**
> Anything supplier- or seller-facing — Selling Partner APIs, Marketplace integrations. My current work is supplier-facing APIs at Walmart; the domain transfer is direct. Beyond that, AWS data services because the ClickHouse work at GCC scratched that itch.

**Q: What if you don't get this role?**
> I keep growing the same way at Walmart for a while. The reason to switch isn't desperation — it's reach.

---

## What NOT to say

- "Amazon is the best company in the world." Don't.
- Don't bash Walmart. "Time for a new challenge" is fine; the rest is unkind and unnecessary.
- Avoid quoting Bezos memos verbatim. The interviewer has read them.
- Don't say "the LPs really resonate with me" without an example. That phrase is on every other candidate's deck.

---

## Backup angle (W6 — Supplier Self-Service)

If they want a project-led answer rather than a values-led one: the audit work at Walmart let me push beyond "replace Splunk" to giving suppliers self-service SQL access to their own API logs. Suppliers like Pepsi could debug their failed requests in 30 seconds instead of opening a 2-day support ticket. That instinct — solve the user's actual problem, not the internal ticket's framing — is what I read in Amazon's customer-obsession LP. It's not a new instinct for me; it's already how I work. I want to do more of it.
