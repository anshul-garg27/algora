# Q: Describe a situation where you put in extra effort beyond your assigned work and achieved success.

> **LP**: Unclassified (Ownership + Customer Obsession + Invent and Simplify)
> **Primary story**: W2 — Shared Library Adoption
> **Backup story**: G7 — Sole Architect (6 services)
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Walmart, early 2025. Splunk was being decommissioned and three teams in our org — mine, Inventory Status, and Transaction Events — were all building their own audit-logging stack at the same time. My assigned scope was just my service. Build the audit pipe for our APIs, ship it, move on.

I noticed something walking past two whiteboards in the same week. Both other teams were sketching the same architecture I had. Same Kafka producer pattern, same async filter, slightly different config formats. Three engineers, three weeks of work each, three slightly inconsistent implementations.

### Task

My scope didn't include "build a shared library for the org". Nobody had asked. My manager would've been fine with me shipping just my piece. But shipping three near-duplicate systems felt like a tax on the next two years of engineering.

### Action

I scheduled 30-minute calls with the lead engineers from both other teams. Came in without a pitch — just questions. "What endpoints do you need to audit? What payload format? Latency budget? What can be config, what has to be code?"

I documented the union. About 80 percent of the requirements overlapped. The 20 percent that didn't — response-body logging, endpoint filtering, region tagging — could be flags.

Then I built the shared library on top of my own service's needs. `dv-api-common-libraries`. Spring Boot starter, `OncePerRequestFilter` with `@Order(LOWEST_PRECEDENCE)` so it runs after security filters, `ContentCachingWrapper` for the HTTP body, `@Async` thread pool sized 6 core / 10 max. Endpoint filtering pulled from CCM config. Response-body logging was a flag both teams could set per-service.

The extra work wasn't the code. The extra work was the adoption.

I did a 45-minute brown-bag for the org. Wrote a migration guide. Then I spent an afternoon pairing with each adopting team on their integration PRs — fixed issues they hit, cut a patch release the same day. That repetition is what made it stick.

### Result

Three teams adopted in the first month. Integration time went from "two weeks of custom code" to "one day with the library". By end of quarter it was the de-facto standard for new services. The senior engineer who initially pushed back on the thread-pool design — DiscardPolicy concern — became one of the loudest advocates and onboarded a fourth team himself.

What I took from it — extra effort isn't doing more of the same task. It's seeing the pattern your scope hides and naming it. My assigned scope was a service. The actual problem was a shared design. Those are different jobs.

---

## Technical depth — if they probe

- **Why a Spring Boot Starter, not a plain JAR**: starter auto-configures the filter, the executor, and the CCM client. Consumer teams just add the dependency and an `@EnableAuditLogging` annotation. Zero copy-paste, zero "did you remember to register the bean".
- **OncePerRequestFilter + LOWEST_PRECEDENCE**: runs after Spring Security, so we capture final response state including auth failures. AOP wouldn't see the HTTP body. A higher-precedence filter would miss the post-auth view.
- **ContentCachingWrapper**: HTTP request body is a single-use stream. Caching wraps it so the controller and our filter can both read. Without it, reading the body in the filter would break the controller's `@RequestBody` binding.
- **CCM endpoint filtering**: each consumer team adds their endpoint regex list to the CCM config. No code change to add or remove endpoints from audit coverage.

---

## Likely follow-ups

**Q: How did you get the other teams to give you 30 minutes when it wasn't on their roadmap?**
> I framed it as "I'm about to build this anyway — if I get your requirements upfront, you don't have to build it later." Engineers respond to "I'll do the work" pitches. Plus, both lead engineers had already started their own version, so they could see the duplication.

**Q: What if one team had refused?**
> Then I'd have built it for two teams and let the third copy or fork. The point wasn't org-wide standard adoption, it was reducing duplication where I could. Two of three was already a 60 percent win.

**Q: How did your manager react?**
> He was supportive once he saw the brown-bag deck. The honest part: I didn't ask before starting. I started, got the first two teams to commit informally, then walked into his 1:1 with "I'm doing this, do you want a status doc?" He laughed and said yes.

**Q: How did you decide which 20 percent to make configurable?**
> Anything where two teams disagreed. Response-body logging, sample rate, region tag — those went into flags. The 80 percent everyone agreed on — filter ordering, thread pool defaults, payload schema — those stayed hard-coded. A flag for every preference is just a config-shaped monster.

**Q: Was there any downside?**
> One. Versioning. When I shipped v0.4 with a breaking change to the payload schema, two teams stayed on v0.3 for a month. I learned to coordinate breaking releases ahead of time and to keep payload schemas backward-compatible by default. Now I treat the library like a public API even though it's internal.

---

## What NOT to say

- Don't claim this was assigned to you — it wasn't, and the "extra effort" framing breaks if you do.
- Don't trash the other teams for "duplicating work" — they didn't know about each other either. The story is collaboration, not blame.
- Don't skip the "spent an afternoon pairing with each team" detail — that's the unglamorous adoption work, and interviewers look for it.
- Don't end on "and now I'm a platform engineer" — let the result speak.

---

## Backup story (G7 — Sole architect at GCC)

At Good Creator Co, my actual scope was one Python scraper. The reality of being SE-I on a small team was that I ended up the sole architect across six services — Beat scraping engine, Coffee SaaS API, Stir data platform, Event-gRPC, the analytics dashboard, the dual-database gateway. Nobody assigned me that scope. The team just didn't have anyone else doing it, and the work needed someone. I picked it up, defended tech-stack decisions in design reviews where I was the most junior person in the room, and shipped all six to production. The extra effort there wasn't a single project — it was 18 months of saying yes to architectural ownership without the title.
