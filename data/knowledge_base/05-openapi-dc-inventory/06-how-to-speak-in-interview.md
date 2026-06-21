# How To Speak About OpenAPI & DC Inventory In Interview

> Practice OUT LOUD until natural.

---

## YOUR 60-SECOND PITCH

> "I designed and built the DC Inventory Search API end-to-end. I started design-first - wrote 898 lines of OpenAPI spec with schemas and examples before any code. This let the consumer team start integration immediately while I built the implementation.
>
> The API processes requests through a 3-stage pipeline: GTIN conversion via UberKey, supplier authorization validation, and Enterprise Inventory data fetch. Each stage tracks errors separately - so for bulk requests of 100 items, the consumer knows exactly which items failed at which stage.
>
> I used a factory pattern for multi-site support - US, Canada, Mexico. Adding a new country is one class. The error handling refactor alone was 1,903 lines. Total: over 8,000 lines from spec to container tests."

---

## WHEN TO USE THIS STORY

| They Ask About... | Use This |
|-------------------|----------|
| "End-to-end project" | Full story - spec to production |
| "API design" | Design-first approach, spec structure |
| "Design patterns" | Factory pattern, RequestProcessor pipeline |
| "Error handling" | 3-stage pipeline, partial success, error sources |
| "Testing strategy" | Container tests with WireMock + PostgreSQL |
| "Working with consumers" | Spec-first parallel development |
| "Refactoring" | RequestProcessor refactor (PR #322: 1,903 lines) |
| "Why X not Y?" | Use 04-technical-decisions file (10 decisions) |

---

## KEY DECISION STORIES

### "Why design-first?"
> "Consumer team was waiting for me to finish coding before they could start. Design-first meant I wrote the spec first - they started integration immediately. We saved about 30% by working in parallel."

### "Why factory pattern?"
> "Three countries with different backend configs. Factory with Spring's Map injection auto-discovers implementations. Adding Mexico was one class with @Component('MX'). Zero changes to factory or service."

### "Why always HTTP 200 for partial success?"
> "A 100-item request where 80 succeed is a SUCCESSFUL request. If we returned 400 or 207, consumers might discard the 80 good results. With 200, they always parse the body. Each item has its own status."

### "Why container tests?"
> "A GTIN-to-WmItemNumber conversion bug only showed up with real PostgreSQL. Unit tests with mocks passed perfectly. That's when I learned: if it touches a database, test with a real database."

### "Why reverse error conversion?"
> "Supplier validation works with GTINs internally, but consumers sent WmItemNumbers. If I return 'GTIN 00012345 not found,' they'd be confused. I convert errors back to their original WmItemNumbers. Small detail, big difference in API usability."

---

## THE DEBUGGING STORY FOR THIS PROJECT

**Use when they ask:** "Tell me about a production bug" or "Tell me about debugging"

> "After launching the DC Inventory API, we discovered a subtle bug in GTIN-to-WmItemNumber error conversion. The reverse mapping - converting GTIN-based errors back to consumer-friendly WmItemNumbers - worked fine in unit tests.
>
> But in production, some GTINs mapped to multiple WmItemNumbers. Our reverse map was non-deterministic - which WmItemNumber would it pick? Sometimes the consumer got the wrong identifier in their error message.
>
> I fixed it in PR #330 with three changes: null checks for empty mappings, duplicate GTIN logging for debugging, and deterministic selection (always pick the first mapping). Also added integration tests with real PostgreSQL data to catch this pattern.
>
> The lesson: reverse mappings in many-to-one relationships need special handling. Unit tests with controlled mock data won't surface duplicates that exist in production data."

---

## STAR STORY: ERROR HANDLING REFACTOR

**Use when they ask:** "Tell me about improving code quality" or "Tell me about refactoring"

> **Situation:** "After launching DC Inventory, the same validation logic was duplicated across services. Adding error handling for the Search Items API would mean more duplication."
>
> **Task:** "Centralize validation before building the next API."
>
> **Action:** "I built RequestProcessor - a pipeline pattern. Each stage takes current state (valid/invalid/errors), runs a function on valid items, separates new successes from failures, tags errors with source. 1,903 lines changed. Migrated all services to JUnit 5 in the same PR."
>
> **Result:** "DRY validation. Search Items API reused RequestProcessor with zero duplication. Error messages became consistent."
>
> **Learning:** "Build the abstraction in the first iteration, not as a refactor. Two similar implementations should trigger the reusability alarm."

---

## NUMBERS TO DROP

| Number | How to Say It |
|--------|---------------|
| 898 lines spec | "...wrote 898 lines of OpenAPI spec before any code..." |
| 3,059 lines implementation | "...the implementation was over 3,000 lines across 30 files..." |
| 1,903 lines error refactor | "...the error handling refactor was almost 2,000 lines..." |
| 1,724 lines container tests | "...built container tests with Docker, WireMock, SQL test data..." |
| 100 items/request | "...supports bulk queries up to 100 items..." |
| 30% integration reduction | "...reduced integration time by about 30%..." |
| 8,000+ total lines | "...over 8,000 lines from spec to tests..." |
| 3-stage pipeline | "...three-stage pipeline: GTIN conversion, supplier validation, EI fetch..." |
| 8 PRs over 5 months | "...eight PRs over five months, from spec to container tests..." |

---

## PIVOT TECHNIQUES

**From Kafka to this:**
> "The audit system was about data pipelines. DC Inventory was about API design and consumer experience. Different challenge, same ownership mindset."

**From Spring Boot 3 to this:**
> "The migration showed I can evolve existing systems. DC Inventory showed I can build new systems from scratch - design-first, spec to production."

**From this to behavioral:**
> "The design-first approach taught me about working with consumers. Want me to tell you about collaborating with the frontend team?"

**From this to technical decisions:**
> "There were interesting trade-offs in this API - like why we always return HTTP 200 even for partial failures, or why ConcurrentHashMap over HashMap. Want me to walk through any of those?"

---

## GOOGLEYNESS STORIES FROM THIS PROJECT

### Putting Users First
> "By writing the spec first, the consumer team started 3 weeks earlier. I was thinking about THEIR timeline, not just mine."

### Challenging Status Quo
> "Most APIs in our org were code-first. I proposed design-first and proved it worked with 30% faster integration."

### Doing the Right Thing
> "I converted errors back to WmItemNumbers even though it added complexity. The consumer shouldn't need to understand our internal GTIN mapping to debug their failures."

### Taking End-to-End Ownership
> "Eight PRs over five months - spec, implementation, error refactor, bug fixes, container tests. I didn't hand it off after the first PR."

---

*Practice the 60-second pitch and the debugging story OUT LOUD.*
