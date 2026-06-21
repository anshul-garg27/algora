# Interview Q&A - OpenAPI & DC Inventory (Complete)

---

## Opening Questions

### Q1: "Tell me about the DC Inventory API."

**Level 1 Answer:**
> "I designed and built a DC Inventory Search API for our supplier platform. Suppliers like Pepsi send a list of product identifiers, and the API returns inventory across distribution centers broken down by type - on-hand, in-transit, reserved."

**Follow-up:** "Walk me through the architecture."
> "It's a 3-stage pipeline. Stage 1: Convert WmItemNumbers to GTINs via UberKey service. Stage 2: Validate each GTIN against supplier authorization mapping - does this supplier have access to this product? Stage 3: Call Enterprise Inventory API for actual DC inventory data. Each stage accumulates errors separately. The final response merges all successes and all errors with error-source tracking."

**Follow-up:** "Why a pipeline pattern?"
> "Because bulk requests - up to 100 items - can fail at different stages for different reasons. One item might have an invalid identifier (Stage 1), another might not be authorized for this supplier (Stage 2), another might have no inventory data (Stage 3). The pipeline pattern with RequestProcessor tracks errors by source so the consumer knows exactly what failed and why."

**Follow-up:** "What would you do differently?"
> "Three things. Write container tests from the start - not 2 months later. Add request rate limiting for bulk endpoints to protect the downstream EI API. And add response time SLAs to the OpenAPI spec, not just functional contracts."

---

### Q2: "What does design-first mean?"

> "Design-first means the OpenAPI spec is written BEFORE code. I wrote 898 lines of spec - endpoint definitions, request/response schemas, validation rules, error examples for every scenario. We shared this with consumers immediately. They generated client SDKs and mocked responses while I built the implementation. R2C contract testing validates spec matches implementation. This reduced integration time by about 30%."

---

### Q3: "How did you handle multi-site (US/CA/MX)?"

> "Factory pattern with Spring's Map injection. Each site has its own Config class - USConfig, CAConfig, MXConfig - each registered as a Spring @Component. The factory auto-discovers all implementations via `Map<String, SiteConfigProvider>` injection. Looking up a site is just a map get. Adding a new country means adding one class with @Component annotation - zero changes to factory, service, or controller. Open-Closed Principle."

**Follow-up:** "How is this different from Strategy pattern?"
> "It IS Strategy pattern, implemented via Spring DI. The factory is the context that selects which strategy to use. The advantage over hand-rolled Strategy is Spring handles registration automatically - no static map or switch statement."

---

### Q4: "What was the hardest part?"

> "Error handling for partial success in bulk requests. When 50 out of 100 items fail across different stages, you need to: track which items failed at which stage, tag errors with source (UberKey, Supplier, EI), convert GTIN-based errors back to WmItemNumbers for consumer-friendly messages, and merge everything into one response. The RequestProcessor refactor was 1,903 lines."

---

### Q5: "Tell me about the testing approach."

> "Four layers:
>
> 1. **Unit tests**: JUnit 5 + Mockito for all services and controllers
> 2. **R2C contract tests**: Validate API responses match OpenAPI spec automatically
> 3. **Container tests**: Docker containers with real PostgreSQL + WireMock for downstream APIs. 1,724 lines of test infrastructure. Caught a GTIN-to-WmItemNumber conversion bug that unit tests missed.
> 4. **Stage deployment**: Production-like traffic for 1 week"

**Follow-up:** "What did container tests catch that unit tests didn't?"
> "A GTIN-to-WmItemNumber conversion error. The reverse mapping logic worked fine with mock data, but with real PostgreSQL queries returning actual WmItemNbr-to-GTIN mappings, duplicate GTIN entries caused incorrect reverse lookups. PR #330 fixed this with null checks and duplicate handling."

---

## Technical Deep Dive Questions

### Q6: "Explain the authorization framework."

> "Four-level hierarchy: Consumer → DUNS → GTIN → Store. When a supplier requests inventory, we check: Does this consumer have access? For this legal entity (DUNS)? For this product (GTIN)? At this store? Any 'no' returns 403.
>
> The authorization data is in PostgreSQL with the NrtiMultiSiteGtinStoreMapping entity. Walmart's internal megha-cache handles caching for frequently accessed mappings - this data changes rarely but is queried on every request."

**Follow-up:** "Why megha-cache instead of Caffeine?"
> "megha-cache is Walmart's managed distributed cache service. Caffeine is in-process only - if we have 5 pods, each maintains its own cache. With megha-cache, the cache is shared across pods so invalidation is consistent. For authorization data that must be consistent across all instances, distributed cache is the right choice."

---

### Q7: "Why always return HTTP 200?"

> "A 100-item bulk request where 80 succeed and 20 fail is a successful request - we have useful data. If we returned 400 or 207, the consumer's error handling might discard the 80 successful results. With 200, consumers always parse the body. Each item has a `dataRetrievalStatus` field - SUCCESS or ERROR with reason and errorSource."

**Follow-up:** "But 207 Multi-Status is the RFC standard."
> "207 is from the WebDAV spec. Our consumers are external suppliers with varying technical sophistication. 200 with per-item status is simpler - every HTTP client handles 200. We document the partial success pattern clearly in our OpenAPI spec."

---

### Q8: "Why ConcurrentHashMap instead of HashMap?"

> "The GTIN map is populated in Stage 1 via processWithBulkValidation and read in Stage 2 and 3. Even though current code is mostly sequential, ConcurrentHashMap is defensive - if someone makes bulk processing parallel later, it won't break. Plus it doesn't allow null keys, preventing subtle NPE bugs. The performance difference for up to 100 items is negligible."

---

### Q9: "Why Java records for the models?"

> "EI response data is read-only - we receive it and pass it through without modification. Records guarantee immutability by design, auto-generate equals/hashCode, and clearly communicate these are data carriers. For the response DTOs we build incrementally, we use @Builder and @Data because we set fields across multiple stages. Records for incoming, builders for outgoing."

---

### Q10: "How does R2C contract testing work?"

> "R2C sends predefined requests to our API and compares responses against the OpenAPI spec. Checks: required fields present? Types match? Status codes correct? If I change the response format without updating the spec, R2C fails and blocks deployment. It's the strongest guarantee that spec and implementation stay in sync."

---

## "What If?" Questions

### Q11: "What if you needed to support 10,000 items per request?"

> "Current limit is 100. For 10,000:
> - **Batch processing**: Split into chunks of 100, process in parallel with CompletableFuture.allOf()
> - **EI API**: Needs to support larger bulk queries or we batch calls
> - **Response streaming**: For very large responses, consider streaming JSON instead of buffering entire response in memory
> - **Timeout**: 10,000 items would take much longer - need async processing with webhook callback
>
> At that scale, I'd consider changing from synchronous request-response to async: accept the request, return a job ID, process in background, notify via webhook."

---

### Q12: "What if the EI API is slow or down?"

> "Currently we have basic error handling. If I rebuilt this:
> - **Circuit breaker**: Resilience4j circuit breaker to fail fast when EI is down
> - **Timeout**: Explicit timeout per request (currently uses Spring Boot default)
> - **Retry with backoff**: 2-3 retries with exponential backoff for transient failures
> - **Fallback**: Return cached data if available, or partial response with 'data unavailable' status
>
> This is similar to what we had to add post-migration for cp-nrti-apis WebClient calls (PR #1564)."

---

### Q13: "How would you add a new country (e.g., Brazil)?"

> "Three changes:
> 1. Create `BRConfig` class implementing `SiteConfigProvider` with `@Component('BR')`
> 2. Add Brazil CCM configuration (EI URL, auth tokens, timeouts)
> 3. Add Brazil site ID mapping in CCM
>
> Zero changes to SiteConfigFactory, service, or controller. That's the beauty of the factory pattern."

---

## Behavioral Questions

### Q14: "Tell me about building something end-to-end."

> **Situation:** "Team needed a new API for suppliers to query DC inventory. No existing endpoint."
>
> **Task:** "I was responsible for everything - from API design to production deployment."
>
> **Action:** "Started design-first: wrote OpenAPI spec (PR #260: 898 lines). Shared with consumers immediately. Built full implementation (PR #271: 3,059 lines) - controllers, services, factory pattern. Then refactored error handling (PR #322: 1,903 lines) when we realized bulk validation needed centralization. Finally built container tests (PR #338: 1,724 lines)."
>
> **Result:** "API serving US, CA, MX suppliers. Design-first reduced integration time by ~30%. Factory pattern made Mexico trivial to add."
>
> **Learning:** "Write container tests from the start, not as an afterthought. And think about consumers first - the spec isn't documentation, it's a development tool."

---

### Q15: "Tell me about refactoring code."

> **Situation:** "After the initial DC Inventory launch, error handling was scattered. Same validation logic duplicated across services."
>
> **Task:** "Centralize validation and error handling before adding the next API."
>
> **Action:** "Built RequestProcessor - a pipeline pattern that tracks valid items, invalid items, and errors with sources across stages. Migrated all services to use it. Converted tests to JUnit 5. Added errorSource tracking so consumers know WHERE an error happened. 1,903 lines changed across the codebase."
>
> **Result:** "DRY validation. When we built the next API (Search Items), it reused RequestProcessor with zero duplication. Error messages became consistent across all endpoints."
>
> **Learning:** "Refactoring should be proactive, not reactive. I should have built RequestProcessor in the first iteration."

---

## Quick Answers

### "Why OpenAPI over GraphQL?"
> "External suppliers with varying technical sophistication. REST with OpenAPI is universally understood."

### "How do you handle 100 items in one request?"
> "Process all items through 3-stage pipeline. Collect successes and errors separately. Return both in same response."

### "What's the latency?"
> "Bottleneck is downstream EI API call. Typical: under 800ms for 100 items."

### "Why constructor injection?"
> "Dependencies explicit, immutable, fails at startup if missing. Modern Spring best practice."

### "Why @JsonIgnoreProperties(ignoreUnknown)?"
> "EI API is internal Walmart - we don't control it. If they add fields, our deserialization shouldn't break."

---

*Practice out loud until natural!*
