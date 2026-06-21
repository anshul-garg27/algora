# Q: Tell me about the most innovative thing you've built.

> **LP**: Invent and Simplify
> **Primary story**: `W8 — DC Inventory Search API`
> **Backup story**: `G6 — Fake-Follower ML`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Suppliers like Pepsi and Coca-Cola needed to query Walmart distribution-centre inventory in bulk — up to 100 items per request — across the US, Canada, and Mexico. The existing supplier APIs were single-country and single-item. The product team gave me a one-paragraph brief and said "make it work for three countries on day one and design it so Brazil is cheap to add."

### Task

I owned the whole thing — OpenAPI spec, controller, service, factory, tests. End-to-end.

### Action

Three pieces of design I'm proud of.

First, design-first. I wrote 898 lines of OpenAPI spec before any Java. Request and response schemas, error examples for every status code, validation rules. Shared it with the consumer team day one. They generated their client SDK and mocked responses while I built the implementation. R2C contract tests wired into CI — if my response shape drifts from the spec, the build fails.

Second, the country factory. `SiteConfigProvider` is an interface. `USConfig`, `CAConfig`, `MXConfig` each implement it with `@Component("US")`, `@Component("CA")`, `@Component("MX")`. Spring injects all of them into a `Map<String, SiteConfigProvider>`. The factory does a map lookup keyed off the request `siteId`. Adding Brazil is one new file. Zero changes to factory, service, or controller.

Third, the 3-stage pipeline with `RequestProcessor`. Bulk requests fail at different stages — invalid wmItemNbr (Stage 1: GTIN conversion), unauthorized for this supplier (Stage 2: mapping check), no inventory data (Stage 3: Enterprise Inventory fetch). I built `RequestProcessor` as a pipeline primitive. Each stage takes current state, runs a function on valid items, accumulates failures with a source tag, returns new state. Consumer gets per-item status — 80 succeeded, 20 failed, each error tagged with where it failed.

The small thing I keep telling people about: reverse error conversion. Stage 2 works in GTINs internally but the consumer sent us WmItemNumbers. So before returning errors I convert identifiers back to the consumer's original WmItemNumber. They see their input in the error, not our internal GTIN.

### Result

Shipped in 8 PRs over 5 months — spec to container tests. Design-first cut integration time about 30 percent because the consumer team started in parallel. Mexico went live two months later — one new class. The `RequestProcessor` got picked up for the Search Items API the next quarter. Pepsi's integration team stopped opening "why did this fail" tickets — the error-source tag gave them everything they needed.

---

## Technical depth — if they probe

- **898 lines of OpenAPI**: endpoints, schemas, validation regex, examples for every error combination. Generated server stubs via `openapi-generator-maven-plugin` so the controller `implements` the spec interface — compile fails if the controller drifts.
- **Spring map injection**: `Map<String, SiteConfigProvider>` auto-populated by Spring from `@Component` bean names. Cleaner than maintaining a registry.
- **Always HTTP 200**: 207 Multi-Status is technically correct per RFC 4918 but most clients trip on it. Per-item `dataRetrievalStatus` field makes consumption trivial.
- **`@JsonIgnoreProperties(ignoreUnknown = true)`** on Enterprise Inventory response models — we don't own that API; new upstream fields shouldn't break us.
- **Constructor injection, final fields**: dependencies are immutable, fail-fast at startup if any wiring is missing.

---

## Likely follow-ups

**Q: Why design-first when most teams in your org were code-first?**
> Two reasons. Consumers wait for you in code-first — they can't start until your endpoint exists. With design-first they generate a mock from the spec and start the same day. And the spec gets reviewed properly when it's the artifact, not an afterthought.

**Q: How did you handle the GTIN-multiple-WmItemNbr bug?**
> Caught it in prod. The reverse mapping was non-deterministic when one GTIN mapped to several WmItemNumbers. Fix in PR #330: null checks, duplicate logging, deterministic selection (first match wins), and integration tests with real Postgres.

**Q: What if Enterprise Inventory adds a new field?**
> `ignoreUnknown = true` on the deserialiser. New fields are silently ignored until we choose to add them. We don't break on upstream changes.

**Q: How is this different from a standard CRUD service?**
> Pipeline error tagging is the unusual bit. A standard service returns success or failure for the whole request. Bulk APIs need partial-success semantics that are still simple for the client to consume. `RequestProcessor` is the abstraction that made this clean.

**Q: What would you do differently?**
> Container tests from day one — we added them two months in. Rate limiting on the bulk endpoint to protect the EI downstream. And SLA fields on the OpenAPI spec, not just functional contracts.

---

## What NOT to say

- Don't say this is parallel/multi-threaded — the DC fetch is synchronous. EI aggregates across DCs internally. CompletableFuture is in the Kafka publishing layer, not this API.
- Don't oversell "innovation" — factory pattern is textbook; the design-first + error-source tagging is the actual novelty in this org.

---

## Backup story (if asked for another)

At GCC I built an ML pipeline to detect fake Instagram followers. The interesting bit: Indian users write names in 10 scripts — Devanagari, Bengali, Tamil, Urdu and more. You can't string-match "rahul_27" against "राहुल". I built a custom Hindi transliterator with 24 vowel and 42 consonant mappings, used HMM-based `indictrans` for the other 9 scripts, and a 5-feature ensemble (non-Indic regex, digit count, handle-name correlation, weighted RapidFuzz, 35,183-name Indian name DB). Runs on Lambda + SQS + Kinesis. 50 percent faster than the previous manual filter.
