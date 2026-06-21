# Scenario-Based "What If?" Questions - DC Inventory API

> Use framework: DETECT → IMPACT → MITIGATE → RECOVER → PREVENT

---

## Q1: "What if the EI (Enterprise Inventory) API is slow?"

> **DETECT:** "Latency alert fires (>100ms for 12 min). Dynatrace child span `EIInventorySearchDCCall` shows high duration."
>
> **IMPACT:** "All DC Inventory requests are slow. But the 3-stage pipeline returns partial results - items that completed before timeout succeed, remaining items get `errorSource: EI_SERVICE` errors."
>
> **MITIGATE:** "PR #1564 added WebClient timeout + retry with exponential backoff. After 3 retries, returns error for remaining items."
>
> **RECOVER:** "When EI recovers, new requests work normally. No state to clean up."
>
> **PREVENT:** "I'd add Resilience4j circuit breaker: after 5 consecutive failures, stop calling EI for 30 seconds. Return 'service temporarily unavailable' immediately instead of waiting for timeout."

---

## Q2: "What if UberKey service is down?"

> "UberKey converts WmItemNumbers to GTINs in Stage 1 of the pipeline.
>
> **Impact:** ALL items fail at Stage 1. Response: HTTP 200 with every item showing `errorSource: UBERKEY, errorReason: INVALID_WM_ITEM_NBR`.
>
> **Why HTTP 200?** Because the API processed correctly - it just couldn't convert identifiers. The error is per-item, not a system failure.
>
> **What I'd add:** Cache WmItemNbr-to-GTIN mappings locally. These don't change often. If UberKey is down, serve from cache for known items. Unknown items still fail gracefully."

---

## Q3: "What if a supplier sends 100 items and ALL are unauthorized?"

> "Stage 2 (supplier validation) rejects all.
>
> **Flow:**
> 1. Stage 1: UberKey converts all 100 → success (100 GTINs)
> 2. Stage 2: Supplier mapping check → ALL 100 unauthorized
> 3. Stage 3: Never reached (no valid items)
>
> **Response:** HTTP 200 with 100 error items, each with `errorSource: SUPPLIER_MAPPING, errorReason: WM_ITEM_NBR_NOT_MAPPED_TO_THE_SUPPLIER`.
>
> **Key design:** Error identifiers are converted BACK to WmItemNumbers. Supplier sees their original input, not our internal GTINs."

---

## Q4: "What if the factory returns null for an unknown siteId?"

> "SiteConfigFactory does `getOrDefault` with default US values as fallback.
>
> ```java
> Map<String, String> siteIdData = siteIdConfig.getSiteIdConfigs()
>     .getOrDefault(String.valueOf(siteId), AppUtil.getDefaultSiteValues());
> ```
>
> **If siteId is completely unknown:** Falls back to US configuration. US is the default market.
>
> **If you want strict validation:** Check if siteId exists BEFORE calling factory. Return 400 for unknown sites. Currently, unknown sites silently use US config - which could be wrong for a Brazil request.
>
> **What I'd improve:** Add explicit siteId validation before the factory call. Return `400: Invalid siteId` for unknown sites."

---

## Q5: "What if ConcurrentHashMap causes a race condition?"

> "ConcurrentHashMap is thread-safe by design - lock striping ensures concurrent reads and writes don't corrupt data.
>
> **But:** If `processWithBulkValidation` splits items into batches and processes them in parallel, two batches could try to put the same key. ConcurrentHashMap handles this safely - last write wins. For our use case (WmItemNbr-to-GTIN mapping), the same key always maps to the same value, so 'last write wins' is correct.
>
> **Where it COULD be an issue:** If two different GTINs map to the same WmItemNbr (reverse mapping). We handle this with duplicate detection logging:
>
> ```java
> if (!gtinToWmItemNbrMap.containsKey(gtin)) {
>     gtinToWmItemNbrMap.put(gtin, wmItemNbr);
> } else {
>     log.warn(\"Duplicate GTIN found: {} maps to both {} and {}\", ...);
> }
> ```"

---

## Q6: "What if a container test passes but production fails?"

> "This is the GTIN-to-WmItemNumber conversion bug we found (PR #330).
>
> **What happened:** Unit tests passed. Container tests passed. But production had duplicate GTIN entries that test data didn't have.
>
> **Root cause:** Test data was clean - each GTIN mapped to exactly one WmItemNumber. Production data had many-to-one relationships (multiple WmItemNumbers → same GTIN).
>
> **Lesson:** Container tests are only as good as their test data. I added more diverse test data after this bug - including duplicates, nulls, and edge cases.
>
> **What I'd add:** Property-based testing that generates random mappings including duplicates. Or use a production data snapshot (anonymized) for container tests."

---

## Q7: "What if the response is too large for the client to handle?"

> "100 items × full inventory breakdown per item = potentially large JSON response.
>
> **Current:** We return the full response in one JSON body. For 100 items with multiple DCs each, this could be several MB.
>
> **Mitigations:**
> 1. Bulk limit is 100 items - prevents unbounded responses
> 2. Each item only returns the requested inventory types
> 3. Response compression (gzip) via Spring Boot
>
> **If response size becomes a problem:**
> - Add pagination within the response
> - Stream JSON response instead of buffering
> - Allow field selection (only return specific inventory types)"

---

## Q8: "What if you need to add a 4th stage to the pipeline?"

> "RequestProcessor makes this easy. Each stage is a function passed to `processWithBulkValidation`:
>
> ```java
> // Adding Stage 4: Price validation
> RequestProcessingResult priceResult = requestProcessor.processWithBulkValidation(
>     eiDataResult,
>     identifiers -> validatePrices(identifiers),
>     \"PRICE_NOT_AVAILABLE\",
>     ERROR_SOURCE_PRICING);
> ```
>
> **What changes:**
> - Add one more stage call in the service
> - Write the stage function
> - Define error message and source
>
> **What DOESN'T change:** RequestProcessor, controller, response builder - all reusable."

---

## Q9: "What if R2C contract test and implementation drift apart?"

> "R2C catches this automatically.
>
> **Scenario:** Developer changes response field from `inventoryType` to `type` without updating spec.
>
> **What happens:**
> 1. Code compiles (Java doesn't know about spec)
> 2. Unit tests pass (testing code, not contract)
> 3. R2C test FAILS: 'Expected field inventoryType not found'
> 4. CI pipeline blocks deployment
>
> **The other direction:** Developer updates spec but not code. Generated interface changes → code won't compile. Caught at build time.
>
> **Why both directions matter:** Spec-to-code is caught by generated interfaces (compile-time). Code-to-spec is caught by R2C (CI time). Together, they guarantee spec and implementation stay in sync."

---

## Q10: "What if authorization data in megha-cache is stale?"

> "Cache TTL-based. If authorization is revoked:
>
> **Scenario:** Supplier 'PepsiCo' loses access to GTIN '00012345' at 2:00 PM. Cache TTL is 24 hours. Cache was refreshed at 1:00 PM.
>
> **Impact:** Pepsi can still query that GTIN until 1:00 PM next day (25 hours of stale access).
>
> **Is this acceptable?** For inventory queries - probably yes. It's read-only data. No financial transaction.
>
> **If not acceptable:**
> 1. Reduce TTL to 1 hour (more DB load but fresher data)
> 2. Add cache invalidation endpoint (revoke triggers cache clear)
> 3. Event-driven invalidation (authorization change publishes event → cache evicts)
>
> **Trade-off:** Shorter TTL = more DB load. Longer TTL = staler data. Current balance works for our use case."

---

*Connect every answer to real code or real incidents from your PRs.*
