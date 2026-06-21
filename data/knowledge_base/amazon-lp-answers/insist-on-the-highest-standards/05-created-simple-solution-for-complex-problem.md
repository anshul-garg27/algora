# Q: Describe a time you created a simple solution for a complex problem.

> **LP**: Insist on the Highest Standards
> **Primary story**: `W8 — DC Inventory Search API`
> **Backup story**: `G10 — Event-gRPC consolidation`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Walmart suppliers needed to query distribution-center inventory. They send a list of items, sometimes 100 at a time, and they need the breakdown — on-hand, in-transit, by inventory type. The data is owned by a downstream Walmart system called EI (Enterprise Inventory).

The first design draft tried to do everything in one big service method. Country branching, GTIN translation, authorization, downstream call, response assembly. About 600 lines, four `if (siteId.equals("US"))` blocks. It worked. It would also become unmaintainable the second we added Canada.

### Task

Design an API that handles US, Canada and Mexico, bulk-supports up to 100 items, surfaces stage-level errors, and stays maintainable as we add countries.

### Action

I went design-first. The OpenAPI spec went up first — 898 lines, request and response schemas, error examples, the 100-item limit baked in. PR #260. The consumer team started integrating off the spec while I built the implementation. That overlap saved about three weeks of joint timeline.

For the country problem, I replaced the conditional branches with a factory pattern. `SiteConfigFactory.getConfig(siteId)` returns the right `SiteConfig` — `USConfig`, `CAConfig`, `MXConfig`. Each config is one class that owns its endpoint URL, headers and identifiers. The service layer never asks "which country" — it just asks the config.

For bulk partial success, I split the work into three explicit stages — UberKey GTIN conversion, supplier authorization via the Consumer → DUNS → GTIN → Store hierarchy, then the EI fetch. Each item carries which stage it failed at, if any. A supplier with 100 items and 3 auth failures gets 97 results plus 3 clearly-labelled "you don't have access to these stores" errors. Not one generic 500.

The error-handling rewrite was its own PR — #322, +1,903 lines — so the diff stayed reviewable. Container tests came next (PR #338, +1,724 lines) running against real Docker, WireMock and SQL fixtures.

### Result

8 PRs over 5 months, around 8,000 lines total. When Canada launched, the change was one new `CAConfig` class. When Mexico went live, same. Integration time for new suppliers dropped about 30% because the OpenAPI spec was the contract.

What I'm proud of: from a supplier's view, the API is one endpoint. From a developer's view, adding a country is one class. The complexity is still there — it's just been moved to the right place.

---

## Technical depth — if they probe

- **Factory over `if` blocks**: With three countries it was annoying. With six it would be a bug farm. Factory keeps country knowledge isolated and lets us unit-test each `SiteConfig` independently.
- **Spec-first contract**: OpenAPI spec + R2C contract tests means the consumer team integrates against guarantees, not promises. Every PR validates that the actual response shape still matches the spec.
- **Stage-tagged errors**: `stageFailed` enum — `GTIN_CONVERSION`, `AUTHORIZATION`, `EI_FETCH`. Three different failure modes that need three different fixes on the supplier's side.
- **Why 100 items**: Downstream EI API hard-limit on payload. We surface it in the spec so callers don't hit a wall mid-batch.

---

## Likely follow-ups

**Q: Why a factory instead of strategy pattern?**
> The two are close. I used factory because the config object is a plain data container — endpoint URL, headers, identifiers. There's no behavior to vary, just data. Strategy fits better when you have varied algorithms.

**Q: What if a country needed completely different auth?**
> That happened once. I extended `SiteConfig` to include `getAuthStrategy()` so the country owns its auth too. The service stays neutral.

**Q: How do you keep the OpenAPI spec from rotting?**
> R2C contract tests in CI. The spec is checked against real API responses on every PR. Drift breaks the build.

**Q: 8,000 lines doesn't sound simple.**
> Lines don't measure simplicity. Adding a country measures it. Mexico was one class.

---

## What NOT to say

- Don't equate "simple solution" with "small diff." It's about complexity locality.
- Don't downplay the error-handling refactor — it's the part that lets bulk-mode partial-success actually work.
- Don't claim OpenAPI design-first is universally better. It's better when consumer teams exist and need to parallelize.

---

## Backup story (if asked for another)

At GCC, Event-gRPC consolidated about 60 protobuf event types behind a single ingestion service. Before, each upstream service had its own ad-hoc HTTP endpoint for emitting events — different schemas, no validation, hard to onboard new producers. I built one gRPC service with strict protobuf contracts, a buffered sinker that batched 1000 events every 5 seconds into ClickHouse, and a clean way to add new event types — drop a `.proto` file, regenerate, done. Write I/O dropped about 99%, onboarding a new event type went from days to hours.
