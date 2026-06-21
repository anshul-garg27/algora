# OpenAPI Design-First & DC Inventory API -- Interview Prep

> **Resume Bullets:** 5 (OpenAPI Design-First), 6 (DC Inventory with bulk query), 8 (Supplier Authorization)
> **Repo:** `inventory-status-srv` (291 PRs total)
> **Your Key PRs:** #260, #271, #277, #312, #322, #330, #338, #197

---

## Your Pitch

### 60-Second Pitch

> "I designed and built the DC Inventory Search API end-to-end. I started design-first -- wrote 898 lines of OpenAPI spec with schemas and examples before any code. This let the consumer team start integration immediately while I built the implementation.
>
> The API processes requests through a 3-stage pipeline: GTIN conversion via UberKey, supplier authorization validation, and Enterprise Inventory data fetch. Each stage tracks errors separately -- so for bulk requests of 100 items, the consumer knows exactly which items failed at which stage.
>
> I used a factory pattern for multi-site support -- US, Canada, Mexico. Adding a new country is one class. The error handling refactor alone was 1,903 lines. Total: over 8,000 lines from spec to container tests."

### 30-Second Pitch

> "I designed and built the DC Inventory Search API from spec to production. I started with OpenAPI design-first -- writing the spec before any code, so consumer teams could start integration immediately. The API lets suppliers query inventory across multiple distribution centers with bulk support (up to 100 items per request). I used a factory pattern for multi-site support (US/CA/MX) and built comprehensive error handling with a centralized RequestProcessor for partial success scenarios. The spec-first approach reduced integration time by 30%."

---

## Key Numbers

| Metric | Value | Source |
|--------|-------|--------|
| API spec PR | **+898 lines** | PR #260 (gh verified) |
| Implementation PR | **+3,059 lines** | PR #271 (gh verified) |
| Error handling refactor | **+1,903 lines** | PR #322 (gh verified) |
| Container tests | **+1,724 lines** | PR #338 (gh verified) |
| Total your code | **~8,000+ lines** | PRs #260-338 combined |
| Integration time reduction | **30%** | Design-first approach |
| Bulk request limit | **100 items/request** | OpenAPI spec |
| 3-stage pipeline | GTIN conversion, Supplier validation, EI fetch | Service layer |
| 8 PRs over 5 months | Aug 2025 -- Jan 2026 | gh verified |

### How to Drop the Numbers

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

## Architecture

### Full System Diagram (5 Layers)

```
+---------------------------------------------------------------------------+
|                     DC INVENTORY SEARCH API                               |
|                                                                           |
|  LAYER 1: API SPEC (Design-First)                                        |
|  +-------------------------------------------------------------------+   |
|  |  api-spec/openapi_consolidated.json                                |   |
|  |  +-- /search-distribution-center-status endpoint                   |   |
|  |  +-- Request/Response schemas                                      |   |
|  |  +-- Error examples (400, 401, 404, 500)                          |   |
|  |  +-- openapi-generator -> Server stubs + Client SDKs              |   |
|  +-------------------------------------------------------------------+   |
|                                                                           |
|  LAYER 2: CONTROLLER                                                     |
|  +-------------------------------------------------------------------+   |
|  |  InventorySearchDistributionCenterController.java (Production)     |   |
|  |  InventorySearchDistributionCenterSandboxController.java (Sandbox) |   |
|  |  InventorySearchDistributionCenterSandboxIntlController.java (Intl)|   |
|  +-------------------------------------------------------------------+   |
|                                                                           |
|  LAYER 3: SERVICE + FACTORY                                              |
|  +-------------------------------------------------------------------+   |
|  |  InventorySearchDistributionCenterService.java                     |   |
|  |  +-- SiteConfigFactory -> USConfig / CAConfig / MXConfig           |   |
|  |  +-- EIServiceHelper (calls external EI DC Inventory API)          |   |
|  |  +-- UberKeyReadService (authorization key lookup)                 |   |
|  |  +-- ServiceRequestBuilder (builds downstream requests)            |   |
|  +-------------------------------------------------------------------+   |
|                                                                           |
|  LAYER 4: MODELS                                                         |
|  +-------------------------------------------------------------------+   |
|  |  DCInventoryPayload.java                                           |   |
|  |  EIDCInventory.java                                                |   |
|  |  EIDCInventoryByInventoryType.java                                 |   |
|  |  EIDCInventoryResponse.java                                        |   |
|  +-------------------------------------------------------------------+   |
|                                                                           |
|  LAYER 5: AUTHORIZATION (Bullet 8)                                       |
|  +-------------------------------------------------------------------+   |
|  |  NrtiMultiSiteGtinStoreMapping.java (Consumer->DUNS->GTIN->Store) |   |
|  |  StoreGtinValidatorService.java (4-level auth check)               |   |
|  +-------------------------------------------------------------------+   |
+---------------------------------------------------------------------------+
```

### Request Flow

```
Supplier Request
    |
    v
InventorySearchDistributionCenterController
    |
    v
InventorySearchDistributionCenterService
    |
    +-- SiteConfigFactory.getConfig(siteId)
    |   +-- USConfig (US-specific settings)
    |   +-- CAConfig (Canada-specific settings)
    |   +-- MXConfig (Mexico-specific settings)
    |
    +-- UberKeyReadService (Authorization key lookup)
    |
    +-- ServiceRequestBuilder (Build downstream request)
    |
    +-- EIServiceHelper -> External EI DC Inventory API
                           (Walmart's internal inventory system)
    |
    v
DCInventoryPayload -> EIDCInventoryResponse
    |
    v
Response to Supplier
```

### Key Files (from repo tree)

```
src/main/java/com/walmart/inventory/
+-- controller/
|   +-- InventorySearchDistributionCenterController.java
|   +-- InventorySearchDistributionCenterSandboxController.java
|   +-- InventorySearchDistributionCenterSandboxIntlController.java
+-- services/
|   +-- InventorySearchDistributionCenterService.java
|   +-- InventorySearchDistributionCenterSanboxService.java
|   +-- UberKeyReadService.java
|   +-- helpers/EIServiceHelper.java
|   +-- builders/ServiceRequestBuilder.java
+-- factory/
|   +-- SiteConfigFactory.java
|   +-- impl/
|       +-- USConfig.java
|       +-- CAConfig.java
|       +-- MXConfig.java
+-- models/ei/dcinventory/
|   +-- DCInventoryPayload.java
|   +-- EIDCInventory.java
|   +-- EIDCInventoryByInventoryType.java
|   +-- EIDCInventoryResponse.java
+-- enums/
    +-- InventoryType.java
```

---

## OpenAPI Design-First

### The Problem

Suppliers (Pepsi, Coca-Cola, Unilever) need to query inventory across Walmart's distribution centers (DCs). Before this API:

- No standardized way to check DC inventory
- Each supplier integration was custom
- No API contract for frontend/consumer teams to code against
- Suppliers couldn't see inventory breakdowns by type (on-hand, in-transit, etc.)

### What Is Design-First?

Design-first means **the API specification is the source of truth**, written BEFORE implementation code.

```
TRADITIONAL (Code-First):
  1. Write code
  2. Generate spec from code
  3. Share spec with consumers
  4. Consumers start integration
  Problem: Consumers WAIT for code to be done

DESIGN-FIRST (What I Did):
  1. Write OpenAPI spec FIRST (PR #260: +898 lines)
  2. Share spec with consumers immediately
  3. Consumers mock against spec and start integration
  4. I build implementation against the spec (PR #271: +3,059 lines)
  5. R2C contract testing validates spec matches implementation
  Result: Consumers start 2-3 weeks earlier! (~30% integration time reduction)
```

### Design-First Workflow (4 Steps)

```
Step 1: WRITE THE SPEC
  +-- Define endpoints, request/response schemas
  +-- Add validation rules (required fields, patterns, sizes)
  +-- Write examples for every scenario (success, errors)
  +-- Review spec with consumers (frontend, partner teams)

Step 2: SHARE SPEC IMMEDIATELY
  +-- Consumers generate client SDKs from spec
  +-- Consumers mock responses using examples
  +-- Frontend development starts IN PARALLEL
  +-- No waiting for backend code!

Step 3: BUILD IMPLEMENTATION
  +-- Generate server stubs from spec (openapi-generator-maven-plugin)
  +-- Implement business logic against generated interfaces
  +-- Implementation MUST match spec exactly

Step 4: VALIDATE WITH R2C
  +-- R2C (Request-to-Contract) tests run automatically
  +-- Compare actual API responses against spec
  +-- Fail build if implementation doesn't match contract
```

### The Spec I Wrote (PR #260)

#### Endpoint Definition

```json
{
  "path": "/inventory/search-distribution-center-status",
  "method": "POST",
  "description": "Search inventory status across distribution centers",
  "request": {
    "body": {
      "items": ["array of GTINs"],
      "siteId": "US | CA | MX"
    }
  },
  "responses": {
    "200": "Inventory data by DC and type",
    "400": "Invalid request (bad GTIN format, too many items)",
    "401": "Unauthorized",
    "404": "No data found",
    "500": "Internal server error"
  }
}
```

#### Request/Response Schemas

```json
// inventory_search_distribution_center_status_request.json
{
  "items": [
    {
      "gtin": "00012345678905",
      "wmItemNbr": 12345
    }
  ],
  "siteId": "US"
}

// inventory_search_distribution_center_status_response_200.json
{
  "inventoryItems": [
    {
      "gtin": "00012345678905",
      "distributionCenters": [
        {
          "dcNumber": "6012",
          "inventoryByType": [
            {
              "inventoryType": "ON_HAND",
              "quantity": 1500
            },
            {
              "inventoryType": "IN_TRANSIT",
              "quantity": 300
            }
          ]
        }
      ]
    }
  ]
}
```

#### Error Examples

```json
// All error combination example
{
  "errors": [
    {
      "gtin": "00012345678905",
      "errorCode": "GTIN_NOT_FOUND",
      "message": "No inventory data found for this GTIN"
    },
    {
      "gtin": "INVALID_FORMAT",
      "errorCode": "INVALID_GTIN",
      "message": "GTIN must be 14 digits"
    }
  ]
}
```

#### API Spec File Structure

```
api-spec/
+-- openapi_consolidated.json                                    # Full OpenAPI 3.0 spec
+-- examples/
|   +-- inventory_search_distribution_center_status_request.json
|   +-- inventory_search_distribution_center_status_response_200.json
|   +-- ...response_all_error_combination.json
|   +-- ...response_success_error_combination.json
|   +-- notify_...invalid_length_error_400.json
|   +-- notify_...invalid_property_error_400.json
|   +-- notify_...malformed_error_400.json
+-- schema/
|   +-- common/
|   |   +-- inventory.json
|   |   +-- inventory_by_location_item.json
|   |   +-- inventory_by_state.json
|   |   +-- inventory_item.json
|   +-- (dc inventory specific schemas)
+-- doc/
    +-- userguide.md
```

### Why Design-First Matters (Interview Talking Points)

> **Parallel Development:** "While I was building the implementation, the consumer team was already coding their integration using the spec. They generated a client SDK and mocked responses. By the time my implementation was ready, they just pointed their client to the real endpoint and it worked."

> **Contract as Documentation:** "The spec IS the documentation. It defines every field, every validation rule, every error scenario. New team members read the spec instead of the code."

> **R2C Contract Testing:** "We integrated R2C (Request-to-Contract) testing into our CI pipeline. Every build validates that the actual API responses match the spec. If I change the response format without updating the spec, the build fails."

> **Consistent Error Handling:** "The spec defines error response schemas for every HTTP status code. This means consumers know exactly what error format to expect -- no surprises."

---

## DC Inventory Implementation

### What This API Does

```
POST /inventory/search-distribution-center-status

Input:
  - dcNumber: Distribution center number (e.g., 6012)
  - itemType: "wmItemNbr" or "gtin"
  - itemTypeValues: List of item identifiers (up to 100)

Output:
  - inventories: List of items with DC inventory by type
  - Each item has: wmItemNumber, inventoryByType (ON_HAND, IN_TRANSIT, etc.)
  - Partial success: some items return data, some return errors
```

### 3-Stage Processing Pipeline

```
+-------------------------------------------------------------------+
|                    3-STAGE PROCESSING PIPELINE                      |
|                                                                     |
|  STAGE 1: GTIN CONVERSION                                          |
|  +--------------------------------------------------------------+  |
|  |  Input: List of WmItemNumbers                                 |  |
|  |  Action: Call UberKey service to convert to GTINs             |  |
|  |  Output: Map<WmItemNbr, GTIN> + errors for invalid items     |  |
|  |  Error: "INVALID_WM_ITEM_NBR"                                |  |
|  +--------------------------------------------------------------+  |
|           | valid items pass to next stage                          |
|           v                                                         |
|  STAGE 2: SUPPLIER VALIDATION                                      |
|  +--------------------------------------------------------------+  |
|  |  Input: List of GTINs from Stage 1                            |  |
|  |  Action: Check supplier mapping (is this GTIN authorized?)    |  |
|  |  Output: Valid GTINs + errors for unauthorized items          |  |
|  |  Error: "WM_ITEM_NBR_NOT_MAPPED_TO_THE_SUPPLIER"             |  |
|  |  Special: Convert GTIN errors BACK to WmItemNbr for UX       |  |
|  +--------------------------------------------------------------+  |
|           | valid items pass to next stage                          |
|           v                                                         |
|  STAGE 3: EI DATA FETCH                                            |
|  +--------------------------------------------------------------+  |
|  |  Input: Valid WmItemNumbers from Stage 2                      |  |
|  |  Action: Call Enterprise Inventory (EI) API for DC data       |  |
|  |  Output: Inventory by type per item + errors for not found    |  |
|  |  Error: "NO_DATA_FOUND"                                       |  |
|  +--------------------------------------------------------------+  |
|           |                                                         |
|           v                                                         |
|  FINAL: BUILD RESPONSE                                             |
|  +--------------------------------------------------------------+  |
|  |  Merge ALL successful items + ALL errors from all stages      |  |
|  |  Return HTTP 200 always (partial success is valid)            |  |
|  +--------------------------------------------------------------+  |
+-------------------------------------------------------------------+
```

> "The API uses a 3-stage pipeline: GTIN conversion, supplier validation, and EI data fetch. Each stage accumulates errors. The final response merges successes and errors from ALL stages. This means a 100-item request might have 80 successes and 20 errors from different stages -- and the consumer knows exactly which items failed and why."

### Controller Code (Actual Production)

```java
@Slf4j
@RestController
public class InventorySearchDistributionCenterController
    implements InventorySearchDistributionCenterStatusApi {

    // Constructor injection (not @Autowired)
    private final TransactionMarkingManager transactionMarkingManager;
    private final SupplierMappingServiceImpl supplierMappingService;
    private final InventoryBusinessValidatorService inventoryBusinessValidatorService;
    private final InventorySearchDistributionCenterServiceImpl inventorySearchDistributionCenterService;

    @Override
    public ResponseEntity<InventorySearchDistributionCenterStatusResponse>
        getInventorySearchDistributionCenterStatus(
            InventorySearchDistributionCenterStatusRequest request) {

        var httpRequest = AppUtil.getCurrentRequest();
        String correlationId = httpRequest.getHeader(WM_QOS_CORRELATION_ID);

        // 1. Validate request
        inventoryBusinessValidatorService.validateDCInventoryStatusRequest(
                request.getItemTypeValues(), request.getItemType());

        // 2. Get supplier mapping (authorization)
        var parentCompanyMapping = supplierMappingService
                .getSupplierMapping(httpRequest.getHeader(WM_CONSUMER_ID));

        // 3. Validate request params against supplier mapping
        InventoryBusinessValidatorService.validateRequestParams(
                request.getDcNumber(), parentCompanyMapping, request.getItemType());

        // 4. Deduplicate items
        List<String> wmItemNumbers = request.getItemTypeValues()
                .stream().distinct()
                .collect(Collectors.toCollection(ArrayList::new));

        // 5. Call service (3-stage pipeline)
        var response = inventorySearchDistributionCenterService
                .getInventorySearchDistributionCenterStatus(
                    request.getDcNumber(), wmItemNumbers,
                    parentCompanyMapping, request.getItemType());

        // 6. Always return HTTP 200 (partial success is valid)
        return ResponseEntity.status(HttpStatus.OK)
                .headers(responseHeaders)
                .body(response);
    }
}
```

### Service Code -- 3-Stage Pipeline (Actual Production)

```java
@Slf4j
@Service
public class InventorySearchDistributionCenterServiceImpl
    implements InventorySearchDistributionCenterService {

    @Override
    public InventorySearchDistributionCenterStatusResponse
        getInventorySearchDistributionCenterStatus(
            Integer dcNumber, List<String> wmItemNumbers,
            ParentCompanyMapping parentCompanyMapping, String inventoryType) {

        List<InventorySearchDistributionCenterStatusInventoryItem> successfulResponses
            = new ArrayList<>();
        Map<String, String> wmItemNbrGtinMap = new ConcurrentHashMap<>();

        // STAGE 1: WmItemNbr -> GTIN conversion via UberKey
        RequestProcessingResult wmItemNbrToGtinResult =
            performGtinConversion(wmItemNumbers, wmItemNbrGtinMap);

        if (wmItemNbrToGtinResult.getValidIdentifiers().isEmpty()) {
            return buildDCResponse(dcNumber, parentCompanyMapping,
                wmItemNbrToGtinResult, successfulResponses);
        }

        // STAGE 2: Supplier validation (is this supplier authorized for these GTINs?)
        RequestProcessingResult supplierMappingResult = requestProcessor
            .validateSupplierMapping(
                new ArrayList<>(wmItemNbrGtinMap.values()),
                parentCompanyMapping, null,
                WM_ITEM_NBR_NOT_MAPPED_TO_THE_SUPPLIER);

        // CRITICAL: Convert GTIN-based errors back to WmItemNumber for UX
        RequestProcessingResult normalizedResult =
            convertGtinErrorsToWmItemNumbers(supplierMappingResult, wmItemNbrGtinMap);

        if (normalizedResult.getValidIdentifiers().isEmpty()) {
            return buildDCResponse(dcNumber, parentCompanyMapping,
                normalizedResult, successfulResponses);
        }

        // Get mapped WmItemNbrs for EI call
        List<String> mappedWmItemNbrs = getMappedWmItemNbrs(
            wmItemNbrGtinMap, normalizedResult);

        // STAGE 3: EI data fetch
        RequestProcessingResult eiDataResult = fetchAndProcessEIData(
            dcNumber, mappedWmItemNbrs, normalizedResult,
            wmItemNbrGtinMap, successfulResponses);

        // Build final response merging ALL successes + ALL errors
        return buildDCResponse(dcNumber, parentCompanyMapping,
            eiDataResult, successfulResponses);
    }
}
```

### GTIN Error Reverse-Conversion (Key Detail)

```java
private RequestProcessingResult convertGtinErrorsToWmItemNumbers(
        RequestProcessingResult supplierMappingResult,
        Map<String, String> wmItemNbrGtinMap) {

    // Build reverse map: GTIN -> WmItemNbr
    Map<String, String> gtinToWmItemNbrMap = new HashMap<>();
    for (Map.Entry<String, String> entry : wmItemNbrGtinMap.entrySet()) {
        if (gtinsToConvert.contains(entry.getValue())) {
            gtinToWmItemNbrMap.put(entry.getValue(), entry.getKey());
        }
    }

    // Convert error identifiers from GTIN to WmItemNumber
    List<RequestValidationErrors> updatedErrors = supplierMappingResult.getErrors()
        .stream()
        .map(error -> RequestValidationErrors.builder()
            .identifier(gtinToWmItemNbrMap
                .getOrDefault(error.getIdentifier(), error.getIdentifier()))
            .errorReason(error.getErrorReason())
            .errorSource(error.getErrorSource())
            .build())
        .collect(Collectors.toList());

    return RequestProcessingResult.builder()
        .validIdentifiers(supplierMappingResult.getValidIdentifiers())
        .invalidIdentifiers(invalidWmItemNbrs)
        .errors(updatedErrors)
        .build();
}
```

> "A subtle but important detail: the supplier validation stage works with GTINs internally, but the consumer sent WmItemNumbers. So I convert error identifiers BACK to WmItemNumbers before returning. The consumer sees their original input in error messages, not our internal GTIN identifiers. This is user-centric error design."

### Transaction Marking (Observability)

```java
try (var uberKeyTxn = transactionMarkingManager
        .getTransactionMarkingService()
        .currentTransaction()
        .addChildTransaction(INVENTORY_SEARCH_DC_SERVICE, UBER_KEY_WM_ITEM_NBR_TO_GTIN)) {
    uberKeyTxn.start();
    // ... UberKey call
}
```

Each stage is wrapped in transaction marking for Dynatrace observability, creating a trace tree:
```
InventorySearchDCService
+-- UberKeySupportWmItemNbrToGtinCall
+-- EIInventorySearchDCCall
```

### RequestProcessor Pattern (Centralized Bulk Validation)

```java
RequestProcessingResult processedResult = requestProcessor.processWithBulkValidation(
    wmItemNbrToGtinResult,           // Current state (valid + invalid + errors)
    identifiers -> fetchGtinsFromUberKey(identifiers, wmItemNbrGtinMap),  // Stage function
    INVALID_WM_ITEM_NBR_MESSAGE,     // Error message for failures
    ERROR_SOURCE_UBERKEY);           // Error source tracking
```

**RequestProcessor** is a reusable pattern:
- Takes current state (valid/invalid/errors)
- Runs a stage function on valid items
- Separates new successes from new failures
- Accumulates errors with source tracking
- Returns updated state

> "RequestProcessor is like a pipeline processor. Each stage takes the current state, processes valid items, catches failures, tags them with an error source (UberKey, Supplier, EI), and passes updated state to the next stage. By the end, we have a complete picture of which items succeeded and which failed at which stage."

### Data Models (Java 17 Records)

```java
public record DCInventoryPayload(
    List<EIDCInventoryByInventoryType> inventoryByInventoryType,
    ItemIdentifier itemIdentifier,
    NodeInfo nodeInfo
) {}

public record EIDCInventoryResponse(
    List<EIDCInventoryByInventoryType> inventoryByInventoryType,
    ItemIdentifier itemIdentifier,
    NodeInfo nodeInfo,
    List<ErrorsItem> errors
) {}

public record EIDCInventory(
    String state,       // e.g., "ON_HAND", "IN_TRANSIT"
    Double quantity,    // e.g., 1500.0
    Long lastUpdatedTime,
    String qtyUom       // Unit of measure
) {}

public record EIDCInventoryByInventoryType(
    String inventoryType,      // e.g., "REGULAR", "SEASONAL"
    List<EIDCInventory> inventory
) {}
```

> "I used Java records for the DC inventory models -- they're immutable by default, auto-generate equals/hashCode/toString, and clearly communicate that these are data carriers, not business logic classes. This is a Java 17 best practice."

### Factory Pattern for Multi-Site (Actual Code)

```java
@Component
public class SiteConfigFactory {

    private final Map<String, SiteConfigProvider> factory;  // Spring injects all implementations

    @ManagedConfiguration
    SiteIdConfig siteIdConfig;

    @Autowired
    public SiteConfigFactory(Map<String, SiteConfigProvider> factory) {
        this.factory = factory;  // Spring auto-discovers USConfig, CAConfig, MXConfig
    }

    public SiteConfigProvider getConfigurations(Long siteId) {
        Map<String, String> siteIdData = siteIdConfig.getSiteIdConfigs()
            .getOrDefault(String.valueOf(siteId), AppUtil.getDefaultSiteValues());
        return factory.get(siteIdData.get(NAME));
    }
}

@Component(US)  // Registered as "US" in Spring context
public class USConfig implements SiteConfigProvider {
    @ManagedConfiguration USEiApiCCMConfig usEiApiCCMConfig;
    @ManagedConfiguration USUberKeyReadApiCCMConfig usUberKeyReadApiCCMConfig;

    @Override
    public SiteConfigMapper getEIConfigs() {
        SiteConfigMapper mapper = new SiteConfigMapper();
        mapper.setHost(usEiApiCCMConfig.getHost());
        mapper.setUriPath(usEiApiCCMConfig.getMultiGtinOnHandInventoryUriPath());
        mapper.setConsumerId(usEiApiCCMConfig.getWmConsumerId());
        // ... more config
        return mapper;
    }

    @Override
    public SiteConfigMapper getUberKeys() {
        // US-specific UberKey configuration
        return mapper;
    }
}
```

How Spring discovers implementations:
- `USConfig` is `@Component("US")`
- `CAConfig` is `@Component("CA")`
- `MXConfig` is `@Component("MX")`
- Spring auto-injects all into `Map<String, SiteConfigProvider>`
- Factory looks up by name from CCM siteId mapping

> "Spring's `Map<String, SiteConfigProvider>` injection automatically discovers all implementations. The factory just does a map lookup. Adding Brazil means adding one `BRConfig` class with `@Component("BR")` -- zero changes to factory or service."

### Response Building (Always HTTP 200)

```java
private InventorySearchDistributionCenterStatusResponse buildDCResponse(
        Integer dcNbr, ParentCompanyMapping parentCompanyMapping,
        RequestProcessingResult finalResult,
        List<InventorySearchDistributionCenterStatusInventoryItem> successfulResponses) {

    return ResponseBuilder.buildResponse(
        finalResult,
        successfulResponses,
        // Error item mapper
        error -> InventorySearchDistributionCenterStatusInventoryItem.builder()
            .wmItemNumber(error.getIdentifier())
            .dataRetrievalStatus(ERROR)
            .reason(error.getErrorReason())
            .build(),
        // Response builder
        items -> InventorySearchDistributionCenterStatusResponse.builder()
            .dcNumber(dcNbr)
            .supplierName(parentCompanyMapping.getParentCmpnyName())
            .inventories(new ArrayList<>(items))
            .build()
    );
}
```

Uses a generic ResponseBuilder with functional interfaces -- reusable across APIs.

### Supplier Authorization Framework (Bullet 8)

```
Consumer -> DUNS -> GTIN -> Store

1. Consumer: API consumer (e.g., "PepsiCo Inc")
2. DUNS: Data Universal Numbering System - legal entity
3. GTIN: Global Trade Item Number - product identifier
4. Store: Individual store locations

Authorization check: Does this consumer -> have this DUNS -> for this GTIN -> at this store?
Any "no" returns 403.
```

Key files:
```
src/main/java/com/walmart/inventory/
+-- entity/
|   +-- NrtiMultiSiteGtinStoreMapping.java
|   +-- NrtiMultiSiteGtinStoreMappingKey.java
+-- repository/
|   +-- NrtiMultiSiteGtinStoreMappingRepository.java
+-- services/
    +-- StoreGtinValidatorService.java
    +-- impl/StoreGtinValidatorServiceImpl.java
```

### CompletableFuture Note

> **Resume mentions CompletableFuture for DC Inventory but the actual code (PR #271) is synchronous.** CompletableFuture IS used in `audit-api-logs-srv` (PR #65) for dual-region Kafka failover.
>
> **Safe answer:** "We use CompletableFuture in the Kafka publishing layer. For DC Inventory, the EI backend aggregates across DCs internally. The bulk support here is about processing multiple items in one request, not parallel DC queries."

---

## Error Handling (RequestProcessor)

### Pipeline Pattern

RequestProcessor is a reusable pipeline pattern that:
- Takes current state (valid/invalid/errors)
- Runs a stage function on valid items
- Separates new successes from new failures
- Accumulates errors with source tracking
- Returns updated state

```java
RequestProcessingResult processedResult = requestProcessor.processWithBulkValidation(
    currentResult,                    // State: valid + invalid + errors
    identifiers -> fetchGtins(...),   // Stage function
    INVALID_WM_ITEM_NBR_MESSAGE,      // Error message
    ERROR_SOURCE_UBERKEY);            // Error source tag
```

### Partial Success (Always HTTP 200)

> "A 100-item bulk request where 80 succeed and 20 fail is a SUCCESSFUL request -- we have useful data to return. If we returned 400 or 207, the consumer's HTTP error handling might discard the 80 successful results. With 200, the consumer always parses the body. Each item has a `dataRetrievalStatus` field -- 'SUCCESS' or 'ERROR' with a `reason`. The consumer can process successful items and handle errors individually."

### Error Source Tagging

Each error carries its source so consumers know WHERE in the pipeline the failure occurred:
- `ERROR_SOURCE_UBERKEY` -- GTIN conversion failed
- `ERROR_SOURCE_SUPPLIER_MAPPING` -- Authorization check failed
- `ERROR_SOURCE_EI` -- Enterprise Inventory API returned no data

### Reverse Error Conversion (GTIN to WmItemNumber)

```
SUPPLIER SENDS:  wmItemNbr = "12345"
STAGE 1 MAPS:   "12345" -> GTIN "00012345678905"
STAGE 2 ERROR:  "GTIN 00012345678905 not mapped to supplier"

WITHOUT CONVERSION:
  Error: "00012345678905 not found"  <-- Supplier says "What is this number?!"

WITH CONVERSION:
  Error: "12345 not mapped to supplier"  <-- Supplier says "Oh, I see the issue"
```

---

## Technical Decisions

### Quick Reference Table

| # | Decision | Chose | Over | Why |
|---|----------|-------|------|-----|
| 1 | ConcurrentHashMap | Thread-safe map | HashMap | Shared across pipeline stages |
| 2 | Java Records | Immutable models | @Data POJOs | EI responses are read-only |
| 3 | Factory + Spring DI | Auto-discovery | If-else/Switch | Open-Closed, zero changes to add country |
| 4 | Always HTTP 200 | Partial success in body | 207/400 | Consumers always parse body |
| 5 | RequestProcessor | Centralized pipeline | Inline validation | Reusable, error-source tracking |
| 6 | Constructor injection | Explicit, immutable | @Autowired fields | Fails fast, testable |
| 7 | Error reverse-conversion | WmItemNbr in errors | GTIN in errors | Consumer sees their input |
| 8 | ignoreUnknown=true | Resilient to upstream | Strict deserialization | Don't control EI API |
| 9 | Generated interface | Compile-time contract | Manual controller | Spec-implementation sync |
| 10 | try-with-resources | Auto-cleanup | Manual start/stop | Exception-safe observability |

### Decision 1: ConcurrentHashMap vs HashMap

```java
Map<String, String> wmItemNbrGtinMap = new ConcurrentHashMap<>();
```

| Aspect | HashMap | ConcurrentHashMap | Why We Chose |
|--------|---------|-------------------|-------------|
| Thread safety | NOT safe | Thread-safe (lock striping) | **Populated in Stage 1, read in Stage 2 & 3** |
| Performance | Faster (no locking) | Slightly slower but safe | Acceptable for our use case |
| Null keys | Allows null | Does NOT allow null | Protects against NPE |
| When to use | Single-threaded only | Multi-threaded or shared state | Our map is shared across pipeline stages |

> "I used ConcurrentHashMap because the GTIN map is populated during UberKey calls in Stage 1 via `processWithBulkValidation` which may process items in batches. The same map is then read by Stage 2 (supplier validation) and Stage 3 (EI fetch). Even though our current code is mostly sequential, ConcurrentHashMap is defensive -- if someone later makes the bulk processing parallel, it won't break. Plus, ConcurrentHashMap doesn't allow null keys, which prevents subtle NPE bugs."

**Follow-up -- "Why not just synchronize HashMap?"**
> "Synchronized HashMap locks the entire map for every operation. ConcurrentHashMap uses lock striping -- it divides the map into segments and locks only the segment being modified. For read-heavy operations like ours (one write phase, multiple read phases), ConcurrentHashMap is significantly better."

**Follow-up -- "Isn't this premature optimization?"**
> "It's defensive coding, not optimization. The performance difference is negligible for our data size. But the thread-safety guarantee and null-key prevention are worth it. I'd rather be safe by default than debug a race condition later."

### Decision 2: Java Records vs Regular POJOs

```java
public record DCInventoryPayload(
    List<EIDCInventoryByInventoryType> inventoryByInventoryType,
    ItemIdentifier itemIdentifier,
    NodeInfo nodeInfo
) {}
```

| Aspect | @Data (Lombok) | Record (Java 17) | Why We Chose |
|--------|----------------|-------------------|-------------|
| Mutability | Mutable (setters) | **Immutable** (no setters) | Data from EI API shouldn't change |
| Boilerplate | Needs Lombok annotation | Built into language | No dependency on Lombok |
| equals/hashCode | Generated by Lombok | Built-in, field-based | Guaranteed correct |
| Serialization | Works with Jackson | Works with Jackson + `@JsonIgnoreProperties` | Same |
| When to use | When you need mutability | When data is read-only | Our EI responses are read-only |

> "I used Java records for the EI response models because they're data carriers -- we receive them from the Enterprise Inventory API and pass them through the pipeline without modification. Records guarantee immutability by design -- no setter exists to accidentally modify them. They also auto-generate equals/hashCode which is important for our map lookups and deduplication."

**Follow-up -- "Why not records for everything?"**
> "The response DTOs like `InventorySearchDistributionCenterStatusInventoryItem` use @Builder and @Data because we build them incrementally -- setting fields across multiple stages. Records don't support that pattern because they're immutable. So: records for incoming data, builders for outgoing responses."

### Decision 3: Factory Pattern vs If-Else vs Strategy

```java
@Component
public class SiteConfigFactory {
    private final Map<String, SiteConfigProvider> factory;  // Spring injects all

    public SiteConfigProvider getConfigurations(Long siteId) {
        return factory.get(siteIdData.get(NAME));
    }
}

@Component("US")
public class USConfig implements SiteConfigProvider { ... }

@Component("CA")
public class CAConfig implements SiteConfigProvider { ... }
```

| Approach | Adding New Country | Modifying Existing | Testability | Our Choice |
|----------|-------------------|-------------------|-------------|------------|
| **If-else** | Modify existing code | Risky, touches everything | Hard to mock | No |
| **Switch** | Modify existing code | Same risk | Same issue | No |
| **Strategy** | New class | Isolated | Each strategy testable | Close, but... |
| **Factory + Spring DI** | New class + `@Component` | Isolated, zero changes to factory | Each config independently testable | **Yes** |

> "I chose the Factory pattern with Spring's Map injection. Spring auto-discovers all `@Component` classes that implement `SiteConfigProvider` and injects them as a map. The factory just does a lookup. This means adding Mexico was literally: create MXConfig class, add `@Component('MX')`, done. No changes to the factory, service, or controller. This follows the Open-Closed Principle."

**Follow-up -- "How is this different from Strategy pattern?"**
> "It IS the Strategy pattern, implemented via Spring DI. The factory is the context that selects which strategy to use based on siteId. The key advantage over a hand-rolled Strategy is that Spring handles the registration automatically. I don't need a static map or switch statement to register new implementations."

**Follow-up -- "What if the config is wrong/missing?"**
> "The `getOrDefault` call provides a default US configuration as fallback. And the CCM-based `SiteIdConfig` can be updated at runtime without redeployment -- so fixing a site mapping doesn't require a code change."

### Decision 4: Always HTTP 200 vs Status-Based Responses

```java
return ResponseEntity.status(HttpStatus.OK)
    .headers(responseHeaders)
    .body(response);
```

| Approach | When Partial Success | Consumer Handling | Our Choice |
|----------|---------------------|-------------------|------------|
| **200 always** | Body has success + errors | Parse body, handle per-item | **Yes** |
| **207 Multi-Status** | RFC standard for partial | More complex parsing | Considered |
| **200 for success, 400 for any error** | Treats partial success as failure | Lose the successful items! | No |
| **200 for success, 207 for partial** | Two response formats | Consumer needs two parsers | No |

> "A 100-item bulk request where 80 succeed and 20 fail is a SUCCESSFUL request -- we have useful data to return. If we returned 400 or 207, the consumer's HTTP error handling might discard the 80 successful results. With 200, the consumer always parses the body. Each item has a `dataRetrievalStatus` field -- 'SUCCESS' or 'ERROR' with a `reason`. The consumer can process successful items and handle errors individually."

**Follow-up -- "But isn't 207 the right status for partial success?"**
> "207 Multi-Status is technically correct per RFC 4918, but it's from the WebDAV spec and not widely understood by API consumers. Our suppliers are external companies with varying technical sophistication. 200 with per-item status is simpler to consume -- every HTTP client handles 200. We document the partial success pattern in our OpenAPI spec."

### Decision 5: RequestProcessor Pattern vs Inline Validation

```java
RequestProcessingResult processedResult = requestProcessor.processWithBulkValidation(
    currentResult,                    // State: valid + invalid + errors
    identifiers -> fetchGtins(...),   // Stage function
    INVALID_WM_ITEM_NBR_MESSAGE,      // Error message
    ERROR_SOURCE_UBERKEY);            // Error source tag
```

| Approach | Error Tracking | Reusability | Testability | Our Choice |
|----------|---------------|-------------|-------------|------------|
| **Inline in service** | Manual, error-prone | Not reusable | Hard | No |
| **RequestProcessor** | Automatic with source tags | Reusable across APIs | Mock processor in tests | **Yes** |
| **Functional pipeline** | Complex for team | Very reusable | Easy | Over-engineered for now |

> "RequestProcessor is a pipeline pattern. Each stage function receives a list of valid identifiers, processes them, and returns a map of successes. RequestProcessor automatically separates successes from failures, tags failures with an error source (UberKey, Supplier, EI), and accumulates errors. This means the service code focuses on WHAT each stage does, not the plumbing of error tracking. The same RequestProcessor is reused across the DC Inventory API and the Search Items API."

**Follow-up -- "Isn't this over-engineering?"**
> "It paid off when we built the second API. The Search Items API uses the same RequestProcessor with different stage functions. Without it, we'd have duplicated the error accumulation logic. The refactor in PR #322 (+1,903 lines) was largely about centralizing this pattern."

### Decision 6: Constructor Injection vs @Autowired

```java
public InventorySearchDistributionCenterServiceImpl(
        TransactionMarkingManager transactionMarkingManager,
        HttpServiceImpl httpService,
        UberKeyReadService uberKeyReadService,
        ServiceRequestBuilder requestBuilder,
        RequestProcessor requestProcessor) {
    this.transactionMarkingManager = transactionMarkingManager;
    this.httpService = httpService;
    // ...
}
```

| Approach | Immutability | Testability | Required Dependencies | Our Choice |
|----------|-------------|-------------|----------------------|------------|
| **@Autowired fields** | Mutable | Needs reflection in tests | Silently null if missing | No |
| **@Autowired setters** | Mutable | Can set in tests | Optional by default | No |
| **Constructor injection** | **Immutable (final fields)** | Just pass in constructor | Fails at startup if missing | **Yes** |

> "Constructor injection makes dependencies explicit and immutable. If a required service is missing, the application fails at startup -- not at runtime with a NullPointerException. In tests, I just pass mock objects directly to the constructor, no reflection needed. Spring recommends constructor injection since Spring 4.3 -- it's the modern best practice."

### Decision 7: GTIN Error Reverse-Conversion

> "This is a UX decision at the API level. Internally, we work with GTINs because that's what the supplier mapping database uses. But the consumer sent WmItemNumbers. If we return 'GTIN 00012345678905 is not authorized,' they'd have to reverse-map that themselves. By converting errors back to WmItemNumbers, the error message makes sense in the consumer's context. It's a small detail but shows we think about the API from the consumer's perspective."

**Follow-up -- "What about performance of the reverse map?"**
> "The reverse map is built once per request from the existing wmItemNbrGtinMap. For up to 100 items, it's negligible -- microseconds. The benefit of clear error messages far outweighs the cost."

### Decision 8: @JsonIgnoreProperties(ignoreUnknown = true) on Models

```java
@JsonIgnoreProperties(ignoreUnknown = true)
public record DCInventoryPayload(...) {}
```

| Without | With | Our Choice |
|---------|------|------------|
| If EI API adds a new field, our deserialization BREAKS | New fields silently ignored | **With** |
| Strict contract validation | Loose coupling | Loose -- we control our spec, not EI's |

> "The EI (Enterprise Inventory) API is an internal Walmart service that we consume but don't control. If they add a new field to their response, our deserialization shouldn't break. `@JsonIgnoreProperties(ignoreUnknown = true)` makes us resilient to upstream changes. We explicitly define the fields we NEED and ignore the rest."

### Decision 9: OpenAPI Generated Interface vs Manual Controller

```java
@RestController
public class InventorySearchDistributionCenterController
    implements InventorySearchDistributionCenterStatusApi {  // GENERATED interface
```

| Approach | Spec-Implementation Sync | Compile-Time Check | Our Choice |
|----------|-------------------------|-------------------|------------|
| **Manual controller** | Can drift from spec | No | No |
| **Generated interface** | Method signatures match spec | Yes -- won't compile if wrong | **Yes** |
| **Generated controller** | Full implementation generated | Too much generated code | No |

> "We generate Java interfaces from the OpenAPI spec using `openapi-generator-maven-plugin`. The controller IMPLEMENTS this interface. If the spec says the endpoint returns `InventorySearchDistributionCenterStatusResponse`, the controller must return that type -- enforced at compile time. If someone changes the spec, the controller won't compile until it's updated. This is the strongest form of spec-implementation contract."

### Decision 10: try-with-resources for Transaction Marking

```java
try (var uberKeyTxn = transactionMarkingManager
        .getTransactionMarkingService()
        .currentTransaction()
        .addChildTransaction(SERVICE, OPERATION)) {
    uberKeyTxn.start();
    // ... stage logic
}  // auto-closed -> transaction marked as complete
```

| Approach | Transaction Cleanup | Exception Handling | Our Choice |
|----------|--------------------|--------------------|------------|
| **Manual start/stop** | Must remember to stop | If exception, transaction hangs | No |
| **try-finally** | Stop in finally block | Verbose, error-prone | No |
| **try-with-resources** | Auto-closed when block exits | Even on exceptions | **Yes** |

> "Transaction marking creates child spans in Dynatrace for observability. If a stage throws an exception and we forget to close the transaction, Dynatrace shows it as still running -- confusing for debugging. try-with-resources guarantees the transaction is closed regardless of success or failure. It's the same reason we use it for streams and connections."

### The Meta-Answer Framework

When they ask "Why did you choose X?", always answer with this structure:

1. "We considered [alternatives]..."
2. "We chose [X] because [specific reason related to our context]..."
3. "The trade-off is [downside]..."
4. "We mitigated that by [action]..."

**Example:**
> "We considered HashMap, synchronized HashMap, and ConcurrentHashMap. We chose ConcurrentHashMap because the GTIN map is shared across three pipeline stages and populated during bulk processing. The trade-off is slightly lower performance than HashMap, but for up to 100 items per request, the difference is negligible. The thread-safety and null-key prevention are worth it."

---

## The Debugging Story

### GTIN-to-WmItemNumber Reverse Mapping Bug

> "After launching the DC Inventory API, we discovered a subtle bug in GTIN-to-WmItemNumber error conversion. The reverse mapping -- converting GTIN-based errors back to consumer-friendly WmItemNumbers -- worked fine in unit tests.
>
> But in production, some GTINs mapped to multiple WmItemNumbers. Our reverse map was non-deterministic -- which WmItemNumber would it pick? Sometimes the consumer got the wrong identifier in their error message.
>
> I fixed it in PR #330 with three changes: null checks for empty mappings, duplicate GTIN logging for debugging, and deterministic selection (always pick the first mapping). Also added integration tests with real PostgreSQL data to catch this pattern.
>
> The lesson: reverse mappings in many-to-one relationships need special handling. Unit tests with controlled mock data won't surface duplicates that exist in production data."

### What Container Tests Caught

> "A GTIN-to-WmItemNumber conversion error. The reverse mapping logic worked fine with mock data, but with real PostgreSQL queries returning actual WmItemNbr-to-GTIN mappings, duplicate GTIN entries caused incorrect reverse lookups. PR #330 fixed this with null checks and duplicate handling."

---

## Behavioral Stories

### End-to-End Ownership (8 PRs over 5 months)

> **Situation:** "Team needed a new API for suppliers to query DC inventory. No existing endpoint."
>
> **Task:** "I was responsible for everything -- from API design to production deployment."
>
> **Action:** "Started design-first: wrote OpenAPI spec (PR #260: 898 lines). Shared with consumers immediately. Built full implementation (PR #271: 3,059 lines) -- controllers, services, factory pattern. Then refactored error handling (PR #322: 1,903 lines) when we realized bulk validation needed centralization. Finally built container tests (PR #338: 1,724 lines)."
>
> **Result:** "API serving US, CA, MX suppliers. Design-first reduced integration time by ~30%. Factory pattern made Mexico trivial to add."
>
> **Learning:** "Write container tests from the start, not as an afterthought. And think about consumers first -- the spec isn't documentation, it's a development tool."

### Challenging Status Quo (Design-First)

> "Most APIs in our org were code-first. I proposed design-first and proved it worked with 30% faster integration. By writing the spec first, the consumer team started 3 weeks earlier. I was thinking about THEIR timeline, not just mine."

### Putting Users First (Spec-First Parallel Dev)

> "By writing the spec first, the consumer team started 3 weeks earlier. I was thinking about THEIR timeline, not just mine. And the error reverse-conversion -- converting errors back to WmItemNumbers even though it added complexity -- shows we think about the API from the consumer's perspective."

### Refactoring (RequestProcessor)

> **Situation:** "After launching DC Inventory, the same validation logic was duplicated across services. Adding error handling for the Search Items API would mean more duplication."
>
> **Task:** "Centralize validation before building the next API."
>
> **Action:** "I built RequestProcessor -- a pipeline pattern. Each stage takes current state (valid/invalid/errors), runs a function on valid items, separates new successes from failures, tags errors with source. 1,903 lines changed. Migrated all services to JUnit 5 in the same PR."
>
> **Result:** "DRY validation. Search Items API reused RequestProcessor with zero duplication. Error messages became consistent."
>
> **Learning:** "Build the abstraction in the first iteration, not as a refactor. Two similar implementations should trigger the reusability alarm."

### Doing the Right Thing

> "I converted errors back to WmItemNumbers even though it added complexity. The consumer shouldn't need to understand our internal GTIN mapping to debug their failures."

---

## Interview Q&A

### Q: "Tell me about the DC Inventory API."

**Level 1 Answer:**
> "I designed and built a DC Inventory Search API for our supplier platform. Suppliers like Pepsi send a list of product identifiers, and the API returns inventory across distribution centers broken down by type -- on-hand, in-transit, reserved."

**Follow-up -- "Walk me through the architecture."**
> "It's a 3-stage pipeline. Stage 1: Convert WmItemNumbers to GTINs via UberKey service. Stage 2: Validate each GTIN against supplier authorization mapping -- does this supplier have access to this product? Stage 3: Call Enterprise Inventory API for actual DC inventory data. Each stage accumulates errors separately. The final response merges all successes and all errors with error-source tracking."

**Follow-up -- "Why a pipeline pattern?"**
> "Because bulk requests -- up to 100 items -- can fail at different stages for different reasons. One item might have an invalid identifier (Stage 1), another might not be authorized for this supplier (Stage 2), another might have no inventory data (Stage 3). The pipeline pattern with RequestProcessor tracks errors by source so the consumer knows exactly what failed and why."

**Follow-up -- "What would you do differently?"**
> "Three things. Write container tests from the start -- not 2 months later. Add request rate limiting for bulk endpoints to protect the downstream EI API. And add response time SLAs to the OpenAPI spec, not just functional contracts."

### Q: "What does design-first mean?"

> "Design-first means the OpenAPI spec is written BEFORE code. I wrote 898 lines of spec -- endpoint definitions, request/response schemas, validation rules, error examples for every scenario. We shared this with consumers immediately. They generated client SDKs and mocked responses while I built the implementation. R2C contract testing validates spec matches implementation. This reduced integration time by about 30%."

### Q: "How does this differ from code-first?"

> "In code-first, you write the controller, then generate the spec from annotations. The problem: consumers wait for your code, and the spec is an afterthought -- it may not capture all edge cases. In design-first, the spec is reviewed and agreed upon before coding starts. It's the contract."

### Q: "How did this reduce integration time by 30%?"

> "Without design-first, the consumer team would wait 3-4 weeks for my implementation before starting integration. With the spec available from day one, they started in parallel -- generating client SDKs, mocking responses, building their UI. When my implementation was ready, integration was mostly done. We saved about 30% of the total end-to-end delivery time."

### Q: "What is R2C testing?"

> "R2C stands for Request-to-Contract. It's automated testing that sends requests to your API and validates the responses against the OpenAPI spec. It checks response schemas, status codes, header formats. If you change the API without updating the spec, R2C fails. It's our guarantee that spec and implementation stay in sync."

### Q: "How did you handle multi-site (US/CA/MX)?"

> "Factory pattern with Spring's Map injection. Each site has its own Config class -- USConfig, CAConfig, MXConfig -- each registered as a Spring @Component. The factory auto-discovers all implementations via `Map<String, SiteConfigProvider>` injection. Looking up a site is just a map get. Adding a new country means adding one class with @Component annotation -- zero changes to factory, service, or controller. Open-Closed Principle."

**Follow-up -- "How is this different from Strategy pattern?"**
> "It IS Strategy pattern, implemented via Spring DI. The factory is the context that selects which strategy to use. The advantage over hand-rolled Strategy is Spring handles registration automatically -- no static map or switch statement."

### Q: "What was the hardest part?"

> "Error handling for partial success in bulk requests. When 50 out of 100 items fail across different stages, you need to: track which items failed at which stage, tag errors with source (UberKey, Supplier, EI), convert GTIN-based errors back to WmItemNumbers for consumer-friendly messages, and merge everything into one response. The RequestProcessor refactor was 1,903 lines."

### Q: "Tell me about the testing approach."

> "Four layers:
>
> 1. **Unit tests**: JUnit 5 + Mockito for all services and controllers
> 2. **R2C contract tests**: Validate API responses match OpenAPI spec automatically
> 3. **Container tests**: Docker containers with real PostgreSQL + WireMock for downstream APIs. 1,724 lines of test infrastructure. Caught a GTIN-to-WmItemNumber conversion bug that unit tests missed.
> 4. **Stage deployment**: Production-like traffic for 1 week"

**Follow-up -- "What did container tests catch that unit tests didn't?"**
> "A GTIN-to-WmItemNumber conversion error. The reverse mapping logic worked fine with mock data, but with real PostgreSQL queries returning actual WmItemNbr-to-GTIN mappings, duplicate GTIN entries caused incorrect reverse lookups. PR #330 fixed this with null checks and duplicate handling."

### Q: "Explain the authorization framework."

> "Four-level hierarchy: Consumer -> DUNS -> GTIN -> Store. When a supplier requests inventory, we check: Does this consumer have access? For this legal entity (DUNS)? For this product (GTIN)? At this store? Any 'no' returns 403.
>
> The authorization data is in PostgreSQL with the NrtiMultiSiteGtinStoreMapping entity. Walmart's internal megha-cache handles caching for frequently accessed mappings -- this data changes rarely but is queried on every request."

**Follow-up -- "Why megha-cache instead of Caffeine?"**
> "megha-cache is Walmart's managed distributed cache service. Caffeine is in-process only -- if we have 5 pods, each maintains its own cache. With megha-cache, the cache is shared across pods so invalidation is consistent. For authorization data that must be consistent across all instances, distributed cache is the right choice."

### Q: "Why always return HTTP 200?"

> "A 100-item bulk request where 80 succeed and 20 fail is a successful request -- we have useful data. If we returned 400 or 207, the consumer's error handling might discard the 80 successful results. With 200, consumers always parse the body. Each item has a `dataRetrievalStatus` field -- SUCCESS or ERROR with reason and errorSource."

**Follow-up -- "But 207 Multi-Status is the RFC standard."**
> "207 is from the WebDAV spec. Our consumers are external suppliers with varying technical sophistication. 200 with per-item status is simpler -- every HTTP client handles 200. We document the partial success pattern clearly in our OpenAPI spec."

### Q: "Why ConcurrentHashMap instead of HashMap?"

> "The GTIN map is populated in Stage 1 via processWithBulkValidation and read in Stage 2 and 3. Even though current code is mostly sequential, ConcurrentHashMap is defensive -- if someone makes bulk processing parallel later, it won't break. Plus it doesn't allow null keys, preventing subtle NPE bugs. The performance difference for up to 100 items is negligible."

### Q: "Why Java records for the models?"

> "EI response data is read-only -- we receive it and pass it through without modification. Records guarantee immutability by design, auto-generate equals/hashCode, and clearly communicate these are data carriers. For the response DTOs we build incrementally, we use @Builder and @Data because we set fields across multiple stages. Records for incoming, builders for outgoing."

### Q: "How does R2C contract testing work?"

> "R2C sends predefined requests to our API and compares responses against the OpenAPI spec. Checks: required fields present? Types match? Status codes correct? If I change the response format without updating the spec, R2C fails and blocks deployment. It's the strongest guarantee that spec and implementation stay in sync."

### Q: "Walk me through the DC Inventory request flow."

> "Three stages. First, convert WmItemNumbers to GTINs via UberKey service. Second, validate each GTIN against supplier authorization mapping. Third, call Enterprise Inventory API for actual DC inventory data. Each stage accumulates errors separately. The response merges all successes and all errors with error source tracking -- so the consumer knows if an item failed at GTIN conversion, authorization, or data lookup."

### Q: "Why convert GTIN errors back to WmItemNumbers?"

> "User experience. The consumer sent WmItemNumbers. If we return errors with GTIN identifiers, they'd have to reverse-map themselves. By converting errors back to WmItemNumbers, the consumer sees their original input in error messages. This is a small detail that makes a big difference in API usability."

### Q: "What's the hardest part of this implementation?"

> "The error accumulation across stages. Each stage can produce valid items and errors. The RequestProcessor pattern handles this by tracking errors with sources. But the tricky part was the GTIN-to-WmItemNumber reverse conversion in Stage 2 -- building the reverse map, handling duplicates, and ensuring errors from all stages use consistent identifiers."

### Quick Answers

**"Why OpenAPI over GraphQL?"**
> "External suppliers with varying technical sophistication. REST with OpenAPI is universally understood."

**"How do you handle 100 items in one request?"**
> "Process all items through 3-stage pipeline. Collect successes and errors separately. Return both in same response."

**"What's the latency?"**
> "Bottleneck is downstream EI API call. Typical: under 800ms for 100 items."

**"Why constructor injection?"**
> "Dependencies explicit, immutable, fails at startup if missing. Modern Spring best practice."

**"Why @JsonIgnoreProperties(ignoreUnknown)?"**
> "EI API is internal Walmart -- we don't control it. If they add fields, our deserialization shouldn't break."

---

## What-If Scenarios

> Use framework: DETECT -> IMPACT -> MITIGATE -> RECOVER -> PREVENT

### What if the EI (Enterprise Inventory) API is slow?

> **DETECT:** "Latency alert fires (>100ms for 12 min). Dynatrace child span `EIInventorySearchDCCall` shows high duration."
>
> **IMPACT:** "All DC Inventory requests are slow. But the 3-stage pipeline returns partial results -- items that completed before timeout succeed, remaining items get `errorSource: EI_SERVICE` errors."
>
> **MITIGATE:** "PR #1564 added WebClient timeout + retry with exponential backoff. After 3 retries, returns error for remaining items."
>
> **RECOVER:** "When EI recovers, new requests work normally. No state to clean up."
>
> **PREVENT:** "I'd add Resilience4j circuit breaker: after 5 consecutive failures, stop calling EI for 30 seconds. Return 'service temporarily unavailable' immediately instead of waiting for timeout."

### What if UberKey service is down?

> "UberKey converts WmItemNumbers to GTINs in Stage 1 of the pipeline.
>
> **Impact:** ALL items fail at Stage 1. Response: HTTP 200 with every item showing `errorSource: UBERKEY, errorReason: INVALID_WM_ITEM_NBR`.
>
> **Why HTTP 200?** Because the API processed correctly -- it just couldn't convert identifiers. The error is per-item, not a system failure.
>
> **What I'd add:** Cache WmItemNbr-to-GTIN mappings locally. These don't change often. If UberKey is down, serve from cache for known items. Unknown items still fail gracefully."

### What if a supplier sends 100 items and ALL are unauthorized?

> "Stage 2 (supplier validation) rejects all.
>
> **Flow:**
> 1. Stage 1: UberKey converts all 100 -> success (100 GTINs)
> 2. Stage 2: Supplier mapping check -> ALL 100 unauthorized
> 3. Stage 3: Never reached (no valid items)
>
> **Response:** HTTP 200 with 100 error items, each with `errorSource: SUPPLIER_MAPPING, errorReason: WM_ITEM_NBR_NOT_MAPPED_TO_THE_SUPPLIER`.
>
> **Key design:** Error identifiers are converted BACK to WmItemNumbers. Supplier sees their original input, not our internal GTINs."

### What if the factory returns null for an unknown siteId?

> "SiteConfigFactory does `getOrDefault` with default US values as fallback.
>
> ```java
> Map<String, String> siteIdData = siteIdConfig.getSiteIdConfigs()
>     .getOrDefault(String.valueOf(siteId), AppUtil.getDefaultSiteValues());
> ```
>
> **If siteId is completely unknown:** Falls back to US configuration. US is the default market.
>
> **If you want strict validation:** Check if siteId exists BEFORE calling factory. Return 400 for unknown sites. Currently, unknown sites silently use US config -- which could be wrong for a Brazil request.
>
> **What I'd improve:** Add explicit siteId validation before the factory call. Return `400: Invalid siteId` for unknown sites."

### What if ConcurrentHashMap causes a race condition?

> "ConcurrentHashMap is thread-safe by design -- lock striping ensures concurrent reads and writes don't corrupt data.
>
> **But:** If `processWithBulkValidation` splits items into batches and processes them in parallel, two batches could try to put the same key. ConcurrentHashMap handles this safely -- last write wins. For our use case (WmItemNbr-to-GTIN mapping), the same key always maps to the same value, so 'last write wins' is correct.
>
> **Where it COULD be an issue:** If two different GTINs map to the same WmItemNbr (reverse mapping). We handle this with duplicate detection logging:
>
> ```java
> if (!gtinToWmItemNbrMap.containsKey(gtin)) {
>     gtinToWmItemNbrMap.put(gtin, wmItemNbr);
> } else {
>     log.warn("Duplicate GTIN found: {} maps to both {} and {}", ...);
> }
> ```"

### What if a container test passes but production fails?

> "This is the GTIN-to-WmItemNumber conversion bug we found (PR #330).
>
> **What happened:** Unit tests passed. Container tests passed. But production had duplicate GTIN entries that test data didn't have.
>
> **Root cause:** Test data was clean -- each GTIN mapped to exactly one WmItemNumber. Production data had many-to-one relationships (multiple WmItemNumbers -> same GTIN).
>
> **Lesson:** Container tests are only as good as their test data. I added more diverse test data after this bug -- including duplicates, nulls, and edge cases.
>
> **What I'd add:** Property-based testing that generates random mappings including duplicates. Or use a production data snapshot (anonymized) for container tests."

### What if the response is too large for the client to handle?

> "100 items x full inventory breakdown per item = potentially large JSON response.
>
> **Current:** We return the full response in one JSON body. For 100 items with multiple DCs each, this could be several MB.
>
> **Mitigations:**
> 1. Bulk limit is 100 items -- prevents unbounded responses
> 2. Each item only returns the requested inventory types
> 3. Response compression (gzip) via Spring Boot
>
> **If response size becomes a problem:**
> - Add pagination within the response
> - Stream JSON response instead of buffering
> - Allow field selection (only return specific inventory types)"

### What if you need to add a 4th stage to the pipeline?

> "RequestProcessor makes this easy. Each stage is a function passed to `processWithBulkValidation`:
>
> ```java
> // Adding Stage 4: Price validation
> RequestProcessingResult priceResult = requestProcessor.processWithBulkValidation(
>     eiDataResult,
>     identifiers -> validatePrices(identifiers),
>     "PRICE_NOT_AVAILABLE",
>     ERROR_SOURCE_PRICING);
> ```
>
> **What changes:**
> - Add one more stage call in the service
> - Write the stage function
> - Define error message and source
>
> **What DOESN'T change:** RequestProcessor, controller, response builder -- all reusable."

### What if R2C contract test and implementation drift apart?

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
> **The other direction:** Developer updates spec but not code. Generated interface changes -> code won't compile. Caught at build time.
>
> **Why both directions matter:** Spec-to-code is caught by generated interfaces (compile-time). Code-to-spec is caught by R2C (CI time). Together, they guarantee spec and implementation stay in sync."

### What if authorization data in megha-cache is stale?

> "Cache TTL-based. If authorization is revoked:
>
> **Scenario:** Supplier 'PepsiCo' loses access to GTIN '00012345' at 2:00 PM. Cache TTL is 24 hours. Cache was refreshed at 1:00 PM.
>
> **Impact:** Pepsi can still query that GTIN until 1:00 PM next day (25 hours of stale access).
>
> **Is this acceptable?** For inventory queries -- probably yes. It's read-only data. No financial transaction.
>
> **If not acceptable:**
> 1. Reduce TTL to 1 hour (more DB load but fresher data)
> 2. Add cache invalidation endpoint (revoke triggers cache clear)
> 3. Event-driven invalidation (authorization change publishes event -> cache evicts)
>
> **Trade-off:** Shorter TTL = more DB load. Longer TTL = staler data. Current balance works for our use case."

### What if you needed to support 10,000 items per request?

> "Current limit is 100. For 10,000:
> - **Batch processing**: Split into chunks of 100, process in parallel with CompletableFuture.allOf()
> - **EI API**: Needs to support larger bulk queries or we batch calls
> - **Response streaming**: For very large responses, consider streaming JSON instead of buffering entire response in memory
> - **Timeout**: 10,000 items would take much longer -- need async processing with webhook callback
>
> At that scale, I'd consider changing from synchronous request-response to async: accept the request, return a job ID, process in background, notify via webhook."

### What if the EI API is slow or down?

> "Currently we have basic error handling. If I rebuilt this:
> - **Circuit breaker**: Resilience4j circuit breaker to fail fast when EI is down
> - **Timeout**: Explicit timeout per request (currently uses Spring Boot default)
> - **Retry with backoff**: 2-3 retries with exponential backoff for transient failures
> - **Fallback**: Return cached data if available, or partial response with 'data unavailable' status"

### How would you add a new country (e.g., Brazil)?

> "Three changes:
> 1. Create `BRConfig` class implementing `SiteConfigProvider` with `@Component('BR')`
> 2. Add Brazil CCM configuration (EI URL, auth tokens, timeouts)
> 3. Add Brazil site ID mapping in CCM
>
> Zero changes to SiteConfigFactory, service, or controller. That's the beauty of the factory pattern."

---

## How to Speak

### When to Use This Story

| They Ask About... | Use This |
|-------------------|----------|
| "End-to-end project" | Full story -- spec to production |
| "API design" | Design-first approach, spec structure |
| "Design patterns" | Factory pattern, RequestProcessor pipeline |
| "Error handling" | 3-stage pipeline, partial success, error sources |
| "Testing strategy" | Container tests with WireMock + PostgreSQL |
| "Working with consumers" | Spec-first parallel development |
| "Refactoring" | RequestProcessor refactor (PR #322: 1,903 lines) |
| "Why X not Y?" | Technical decisions (10 decisions above) |

### Pivot Techniques

**From Kafka to this:**
> "The audit system was about data pipelines. DC Inventory was about API design and consumer experience. Different challenge, same ownership mindset."

**From Spring Boot 3 to this:**
> "The migration showed I can evolve existing systems. DC Inventory showed I can build new systems from scratch -- design-first, spec to production."

**From this to behavioral:**
> "The design-first approach taught me about working with consumers. Want me to tell you about collaborating with the frontend team?"

**From this to technical decisions:**
> "There were interesting trade-offs in this API -- like why we always return HTTP 200 even for partial failures, or why ConcurrentHashMap over HashMap. Want me to walk through any of those?"

### What I Would Do Differently

1. **Write container tests EARLIER** -- PR #338 came 2 months after implementation. Should've been part of PR #271.
2. **Include performance benchmarks in spec** -- The spec defines functional behavior but not performance SLAs.
3. **Add request rate limiting** -- Bulk endpoint with 100 items/request needs rate limiting to protect downstream EI API.

---

## PR Reference

### All 8 PRs (gh Verified, All MERGED)

| PR# | Title | +/- Lines | Merged | What You Did |
|-----|-------|-----------|--------|-------------|
| **#197** | Cosmos to Postgres | - | Apr 22, 2025 | Database migration foundation |
| **#260** | DC inventory API spec | +898/-9 | Aug 19, 2025 | **DESIGN-FIRST: Wrote OpenAPI spec** |
| **#271** | DC inventory development | +3,059/-540 | Nov 21, 2025 | **MAIN PR: Full implementation** |
| **#277** | wm_item_nbr fix | minor | Nov 11, 2025 | Variable name bug fix |
| **#312** | Fix DC inventory api spec | -26 | Nov 20, 2025 | Removed gtin from response |
| **#322** | Error handling DC inv | +1,903/-376 | Nov 25, 2025 | **RequestProcessor refactor** |
| **#330** | DC inv error fix | +171/-10 | Jan 12, 2026 | GTIN-to-WmItemNumber conversion fix |
| **#338** | Container test for DC inv | +1,724/-16 | Jan 13, 2026 | **WireMock + Docker tests** |

### Timeline

```
Apr 2025  | PR #197: Cosmos to Postgres migration (database foundation)
          |
Aug 2025  | PR #260: OpenAPI spec (+898 lines) <-- DESIGN FIRST
          |
Nov 2025  | PR #277: Bug fix (wm_item_nbr variable name)
          | PR #312: Fix DC inventory API spec (remove gtin from response)
          | PR #271: Full implementation (+3,059 lines) <-- MAIN PR
          | PR #322: Error handling refactor (+1,903 lines) <-- MAJOR REFACTOR
          |
Jan 2026  | PR #330: GTIN-to-WmItemNumber conversion error fix
          | PR #338: Container tests (+1,724 lines) <-- TESTING
```

**Note:** PR #260 (spec) was written in August, but PR #271 (implementation) came in November. The 3-month gap is when consumers were working with the spec and I was building other features. This IS design-first in action.

### Top 5 PRs to Memorize

| # | PR# | One-Line Summary |
|---|-----|------------------|
| 1 | #260 | Wrote the OpenAPI spec before code (898 lines) |
| 2 | #271 | Full DC Inventory implementation (3,059 lines, 30 files) |
| 3 | #322 | RequestProcessor refactor (1,903 lines, JUnit 5) |
| 4 | #338 | Container tests with WireMock + PostgreSQL (1,724 lines) |
| 5 | #330 | GTIN reverse-mapping bug fix (discovered by container tests) |

### PR Statistics

| Stat | Value |
|------|-------|
| Your PRs in inventory-status-srv | 8 |
| Total additions | ~7,800+ |
| Total deletions | ~980+ |
| Repo total PRs | 291 |
| Time span | Apr 2025 -> Jan 2026 (10 months) |
