# Q: Describe a situation where you saw an opportunity to improve a process and took action.

> **LP**: Unclassified (Invent and Simplify + Ownership)
> **Primary story**: W2 — Shared Library Adoption (audit library across 3 teams)
> **Backup story**: G10 — Event-gRPC consolidation
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Walmart, early 2025. The Splunk decommission was forcing every team in Data Ventures to roll their own audit-logging stack for compliance. My team had started ours. Then I walked past two whiteboards in one week — Inventory Status team sketching the same Kafka publisher pattern, Transaction Events team sketching the same async filter chain. Three different engineers, three slightly different implementations of the same architecture.

The process being broken was "every team builds audit logging on their own". The cost was real — three weeks per team, three different config formats, three different incident playbooks down the line. Multiply that by 15 services and you have a long-term tax.

### Task

Nothing in my assigned scope said "fix this org-wide". My job was just to ship audit logging for my team's service. But the duplication was visible enough that ignoring it felt like leaving money on the table.

### Action

I went looking for the cheapest version of the fix that would actually work.

**Step 1 — Validate the overlap before pitching anything.** I booked 30-minute calls with the lead engineers on both other teams. I didn't bring a solution. I brought questions. Endpoints, payload format, latency budgets, what was hard-required vs configurable. I documented the union of requirements on a single Confluence page. 80 percent of the spec was identical across all three.

**Step 2 — Make the 20 percent configurable, not code.** The differences were narrow — one team wanted response-body logging, another didn't. One had strict latency SLOs, another was flexible. Each of those became a config flag, not a code branch. The library — `dv-api-common-libraries` — auto-configured everything default-on and let each consumer override via CCM.

**Step 3 — Build for adoption, not just function.** This is where most internal libraries fail. The code was 30 percent of the work. The adoption stuff was the other 70 percent. I wrote a migration guide that included a copy-paste 5-line Maven dependency snippet, an example service PR showing the integration, and a "common errors" section based on what I'd hit while migrating my own team.

**Step 4 — Pair through the first integration.** I scheduled a half-afternoon with each adopting team and sat next to them through their integration PR. Caught a `ContentCachingWrapper` ordering issue with one team, a CCM-property naming collision with the other. Fixed both, cut a patch release the same day. That signal — "we shipped your patch in 4 hours" — is what built trust.

**Step 5 — Brown-bag and write it up.** Once two teams had adopted, I did a 45-minute brown-bag for the org. The recording became the canonical onboarding doc for new teams.

### Result

Three teams adopted in month one. Integration time dropped from "two weeks of custom dev" to "one day with the library". By end of quarter, the library was the de facto standard for any new service in Data Ventures.

The deeper thing I learned — the cheap version of process improvement is a shared library, not a process. Telling people to use the same architecture is a process. Giving them a Maven dependency that *is* the architecture is a tool. Tools win.

---

## Technical depth — if they probe

- **Why a Spring Boot Starter, not a plain JAR**: auto-configuration. Add the dependency, drop in `@EnableAuditLogging`, get the filter, the executor, and the CCM client wired automatically. Zero "did you remember to register the bean" failures.
- **The CCM config pattern**: each consumer team has a CCM namespace with their endpoint regex list and overrides. New endpoints added without code changes. Was the single biggest reason for fast adoption.
- **`OncePerRequestFilter` + `@Order(LOWEST_PRECEDENCE)`**: filter runs after Spring Security so we capture final state including auth failures. Run earlier in the chain and you miss the post-auth view of the response.

---

## Likely follow-ups

**Q: Why didn't your manager flag the duplication?**
> The duplication was visible at the engineer level — me, the two other leads — but invisible to managers because each team was reporting "audit logging on track". From the top it looked like progress. Process improvements where the cost is hidden one level above where the work happens are the most common kind to miss.

**Q: How did you avoid building something nobody used?**
> The 30-min discovery calls before any code. If both other leads had told me their requirements were genuinely different, I'd have built only for my team and let the others fork. The library was a function of the 80 percent overlap, not of my preference for sharing code.

**Q: What if the org had pushed back on you taking time for this?**
> They might have, honestly. I took the risk by not asking first — I started the discovery calls, got informal commit from two other leads, then walked into my manager's 1:1 with "I'm doing this, do you want a status doc?". He laughed and said yes. The risk paid off; if it hadn't, I'd have had to defend the time investment.

**Q: What's the maintenance story?**
> I still own the library, but versioning is the cost. v0.4 had a breaking payload-schema change and two teams stayed on v0.3 for a month. I now treat the schema as a public API — backward compatible by default, breaking changes coordinated across consumers ahead of time. The library has a `CODEOWNERS` file and a release-notes pattern.

**Q: Have you done this pattern since?**
> Yes — the Apollo Federation BFF pattern at Walmart. Same shape: three teams were each building their own GraphQL gateway. I proposed a federated approach, prototyped it, paired with the adopting teams. Different tech, same process-improvement loop.

---

## What NOT to say

- Don't claim this was a top-down initiative — it wasn't. The fact that you spotted it bottom-up is the whole point.
- Don't make the other teams sound incompetent for not seeing the duplication — they didn't know about each other either.
- Don't skip the pairing/migration-guide detail. That's the unglamorous adoption work, and interviewers look for it.
- Don't oversell. Three teams in month one is enough. Don't claim "org-wide standard in one quarter" if that came later.

---

## Backup story (G10 — Event-gRPC consolidation)

At GCC, every service was talking to every other service over a different protocol — some REST, some HTTP/JSON, some directly to RabbitMQ. The internal traffic looked like spaghetti. I noticed three services were all consuming the same Beat scraper output through three different transports. Consolidated them onto a single gRPC ingestion service. One Protobuf schema, one wire format, fewer failure modes. Removed roughly 800 lines of bespoke serialisation code across the org and made adding new consumers a 1-line change instead of a 1-week integration. Same pattern — see the duplication, build the shared tool, pair through the first adoption.
