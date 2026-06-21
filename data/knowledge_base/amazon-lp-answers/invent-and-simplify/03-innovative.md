# Q: Tell me about a time when you did something innovative.

> **LP**: Invent and Simplify
> **Primary story**: `W8 — DC Inventory Search API`
> **Backup story**: `G10 — Event-gRPC`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Last August at Walmart, suppliers wanted a way to query distribution-centre inventory in bulk — up to 100 items per request, across US, Canada, and Mexico. The existing pattern in our org was a single `if (siteId == "US")` branch with country-specific code copy-pasted three times. Two countries was already ugly. Three was going to be a fire.

### Task

I owned the API end-to-end — spec, controller, services, tests. I wanted to design it so adding Brazil later would be one class, not a refactor.

### Action

Two things stand out.

First, the factory pattern with Spring DI. I made `SiteConfigProvider` an interface. `USConfig`, `CAConfig`, `MXConfig` each implement it with `@Component("US")`, `@Component("CA")`, `@Component("MX")`. Spring auto-injects all three into a `Map<String, SiteConfigProvider>`. The factory just does a map lookup — no if-else, no switch. Adding Brazil is literally one new file with `@Component("BR")`. Zero changes to the factory, service, or controller. Open-closed in practice.

Second, the 3-stage processing pipeline with error-source tagging. Bulk requests fail differently at different stages. Stage 1: GTIN conversion via UberKey — some items have invalid wmItemNbr. Stage 2: supplier authorization check — some items aren't mapped to that supplier. Stage 3: Enterprise Inventory fetch — some items just have no data. I built a `RequestProcessor` that takes current state (valid items + errors), runs a stage function, and accumulates failures with a source tag — `ERROR_SOURCE_UBERKEY`, `ERROR_SOURCE_SUPPLIER_MAPPING`, `ERROR_SOURCE_EI`. The consumer gets back per-item status — 80 succeeded, 20 failed with reasons. Always HTTP 200; status is per-item, not per-request.

The detail I'm proudest of — the reverse conversion. Stage 2 works in GTINs internally but the consumer sent us WmItemNumbers. So before returning errors, I convert error identifiers back to the consumer's original WmItemNumber. They see their own input, not our internal mapping.

### Result

API shipped end-to-end in 8 PRs over 5 months. The OpenAPI spec was 898 lines, implementation 3,059, error refactor 1,903. Mexico went live two months after the US launch — one new `MXConfig` class, zero core changes. The `RequestProcessor` got reused on the Search Items API the following quarter. The error-source tagging gave the Pepsi integration team enough detail to self-serve their 400-class failures.

---

## Technical depth — if they probe

- **Spring map injection**: `@Autowired Map<String, SiteConfigProvider>` — Spring discovers every `@Component` that implements the interface and keys them by bean name. Cleaner than registering them in a static map.
- **RequestProcessor signature**: `processWithBulkValidation(currentState, stageFunction, errorMessage, errorSource)`. Each stage takes the current state, returns updated state. Pure pipeline composition.
- **Always HTTP 200**: 207 Multi-Status is technically right per RFC 4918 but most HTTP clients don't handle it well. With 200 and a per-item `dataRetrievalStatus`, every client just parses the body.
- **ConcurrentHashMap for wmItemNbrGtinMap**: Populated in Stage 1, read in Stages 2 and 3. Even if we later parallelise the bulk processing, the map won't break. Defensive, not premature.
- **Constructor injection over @Autowired fields**: Final fields. Fails at startup if a dep is missing, not at runtime with a NullPointerException.

---

## Likely follow-ups

**Q: Why not Strategy pattern?**
> It IS the Strategy pattern, wired via Spring DI. The factory is the context that picks the strategy. The win over hand-rolled Strategy is that Spring auto-registers new strategies — I don't need a static map or switch to keep updated.

**Q: How did you handle the GTIN that maps to multiple WmItemNumbers?**
> Caught that one in production. The reverse mapping was non-deterministic — sometimes the wrong WmItemNumber came back in the error. Fixed it in PR #330: null checks, duplicate logging, deterministic selection (always pick the first mapping). Added integration tests with real Postgres to catch it.

**Q: What did design-first save you?**
> About 30 percent integration time. The consumer team started coding against the OpenAPI spec immediately. Generated their client SDK, mocked responses, built their UI in parallel. When my implementation went live they just flipped the URL.

**Q: Walk me through the pipeline.**
> Stage 1 calls UberKey to convert WmItemNumbers to GTINs. Stage 2 validates each GTIN against the supplier mapping table. Stage 3 calls Enterprise Inventory for actual DC quantities. Each stage tags its failures with a source. Final response merges all successes and all errors.

**Q: What would you do differently?**
> Three things. Container tests from day one instead of two months in. Rate limiting on the bulk endpoint to protect the downstream EI API. And response time SLAs declared in the OpenAPI spec, not just functional contracts.

---

## What NOT to say

- Don't claim CompletableFuture parallelism for the DC fetch — the actual code is synchronous. EI aggregates across DCs internally. CompletableFuture is in the Kafka publishing layer, not this API.
- Don't oversell "innovation" — the factory pattern is textbook. The interesting bit is wiring it through Spring map injection and using error-source tagging.

---

## Backup story (if asked for another)

At GCC the Event-gRPC service had grown to 60+ event types — Branch, WebEngage, Vidooly, Shopify each had their own HTTP endpoint. I consolidated them onto a single gRPC `EventService.dispatch()` with protobuf-typed payloads. Same wire protocol, one connection per worker pool, batched flushes to ClickHouse. Cut the HTTP boilerplate, made adding a new event source a `.proto` definition plus a sinker.
