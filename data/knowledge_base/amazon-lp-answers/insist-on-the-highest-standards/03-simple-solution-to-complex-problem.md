# Q: Describe a time when you found a simple solution to a complex problem.

> **LP**: Insist on the Highest Standards
> **Primary story**: `W8 — DC Inventory Search API`
> **Backup story**: `G1 — ClickHouse Migration`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Pepsi, Coca-Cola and Unilever were each asking for the same thing — give me inventory across Walmart's distribution centers, in bulk, so I can plan replenishment. Before this API, each supplier had a custom integration. Three suppliers, three contracts, three subtly different shapes.

When I started designing the new API, the obvious instinct was to make one endpoint that branched internally on country and supplier type. The proposed flow had four `if (siteId == "US")` blocks and a 600-line service class.

### Task

Build one API that handles US, Canada and Mexico, supports bulk requests up to 100 items, and gives the supplier a clear breakdown of which items failed at which stage — without the implementation becoming a maze of country-specific branches.

### Action

I went design-first. Wrote the OpenAPI spec before any Java — 898 lines covering schemas, error examples, the 100-item bulk limit. PR #260. The consumer team started their integration off the spec while I built the backend. That alone shaved about three weeks off the joint timeline.

Then for the country branching, I used a factory pattern instead of conditionals. `SiteConfigFactory.getConfig(siteId)` returns `USConfig`, `CAConfig` or `MXConfig`. Each config is one class that owns its endpoint, headers, and downstream identifiers. Adding Mexico later was one new class — no edits to the service layer.

For partial-success on bulk requests, I broke the work into three explicit stages — GTIN conversion via UberKey, supplier authorization, then the EI inventory fetch. Each stage tracks its own errors. If item 47 fails authorization, the response tells the supplier exactly that — not a generic 500.

The error handling refactor was a separate PR (#322, +1,903 lines) so the code review could focus only on that.

### Result

Total ~8,000 lines across 8 PRs from spec to container tests, but the surface area suppliers see is one endpoint. Integration time across consumers dropped about 30%. When Canada launched, the change was one class — `CAConfig`. When Mexico went live a few weeks later, same story.

The simple part wasn't the line count. It was that adding a country didn't require touching the service.

---

## Technical depth — if they probe

- **Why factory over Spring profiles**: Profiles run at JVM start. We need to switch per-request based on `siteId` in the payload. Factory keeps the routing in code, not in config.
- **Why design-first**: Consumers can't start until the contract is fixed. Writing the spec first turns the contract from "what the code does" into "what we promised."
- **3-stage error tracking**: Each item carries a `stageFailed` field. UberKey conversion failures, auth denials and EI failures look different to the supplier — different fixes on their side.
- **100-item bulk limit**: Comes from downstream EI API's payload limit. We surface it in the spec rather than letting the request fail at the boundary.

---

## Likely follow-ups

**Q: Why not microservices per country?**
> Three services for three countries with 95% shared code would've been worse. Same OpenAPI surface, same auth model, same monitoring. The factory pattern gives you the isolation benefit inside one service.

**Q: How did you keep the spec and code in sync?**
> R2C contract tests. Every PR runs the spec against the actual API responses. If they diverge, the build breaks.

**Q: Did the factory pattern ever bite you?**
> Once. We added a country that needed a different auth path. I almost added an `if` in the service. Instead I extended `SiteConfig` interface with `getAuthStrategy()` so the country owns its auth too. The discipline was worth keeping.

**Q: What was the hardest part?**
> Convincing the team to write the OpenAPI spec first. People wanted to "just start coding." I had to show that consumers integrate against the spec, not the code.

---

## What NOT to say

- Don't say "I made it simple" without explaining the structural choice (factory, design-first).
- Don't claim 8,000 lines is small. Make it about adding a country being one class.
- Don't oversell OpenAPI as a silver bullet — it requires discipline to keep in sync.

---

## Backup story (if asked for another)

At GCC, our Postgres was breaking under 10M events/day. The complex move would've been sharding Postgres. The simple move was ClickHouse for analytics, Postgres for CRUD, RabbitMQ in between with a buffered sinker that batched 1000 events every 5 seconds. Two databases doing what each is good at. Analytics queries went from 30s to 2s, infra cost dropped about 30%, no downtime during the cutover.
