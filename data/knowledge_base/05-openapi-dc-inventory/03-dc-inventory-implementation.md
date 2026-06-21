# DC Inventory API - Deep Implementation Guide (Bullet 6)

> **Resume Bullet:** "Built DC Inventory Search API with bulk query support"
> **Main PR:** #271 (+3,059/-540, 30 files)
> **All code below is ACTUAL production code from the repo (gh verified)**

---

## What This API Does

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

---

## Architecture (3-Stage Pipeline)

The service implements a **3-stage processing pipeline** where each stage can produce errors that get accumulated:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    3-STAGE PROCESSING PIPELINE                       │
│                                                                      │
│  STAGE 1: GTIN CONVERSION                                           │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  Input: List of WmItemNumbers                             │       │
│  │  Action: Call UberKey service to convert to GTINs         │       │
│  │  Output: Map<WmItemNbr, GTIN> + errors for invalid items │       │
│  │  Error: "INVALID_WM_ITEM_NBR"                             │       │
│  └──────────────────────────────────────────────────────────┘       │
│           │ valid items pass to next stage                           │
│           ▼                                                          │
│  STAGE 2: SUPPLIER VALIDATION                                       │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  Input: List of GTINs from Stage 1                        │       │
│  │  Action: Check supplier mapping (is this GTIN authorized?)│       │
│  │  Output: Valid GTINs + errors for unauthorized items      │       │
│  │  Error: "WM_ITEM_NBR_NOT_MAPPED_TO_THE_SUPPLIER"         │       │
│  │  Special: Convert GTIN errors BACK to WmItemNbr for UX   │       │
│  └──────────────────────────────────────────────────────────┘       │
│           │ valid items pass to next stage                           │
│           ▼                                                          │
│  STAGE 3: EI DATA FETCH                                             │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  Input: Valid WmItemNumbers from Stage 2                  │       │
│  │  Action: Call Enterprise Inventory (EI) API for DC data   │       │
│  │  Output: Inventory by type per item + errors for not found│       │
│  │  Error: "NO_DATA_FOUND"                                   │       │
│  └──────────────────────────────────────────────────────────┘       │
│           │                                                          │
│           ▼                                                          │
│  FINAL: BUILD RESPONSE                                              │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  Merge ALL successful items + ALL errors from all stages  │       │
│  │  Return HTTP 200 always (partial success is valid)        │       │
│  └──────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────┘
```

### Interview Point
> "The API uses a 3-stage pipeline: GTIN conversion, supplier validation, and EI data fetch. Each stage accumulates errors. The final response merges successes and errors from ALL stages. This means a 100-item request might have 80 successes and 20 errors from different stages - and the consumer knows exactly which items failed and why."

---

## ACTUAL Controller Code (from repo)

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

### Key Design Decision: Always HTTP 200
> "We return HTTP 200 even when some items fail. The response body contains both `inventories` (successful items) and error details per failed item. This is because a bulk request with partial success IS a valid response. Returning 400 or 500 for partial failures would force consumers to treat partial success as a failure."

---

## ACTUAL Service Code - 3-Stage Pipeline (from repo)

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

        // STAGE 1: WmItemNbr → GTIN conversion via UberKey
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

---

## Key Technical Details

### 1. ConcurrentHashMap for GTIN Mapping
```java
Map<String, String> wmItemNbrGtinMap = new ConcurrentHashMap<>();
```
**Why ConcurrentHashMap?** The map is populated during UberKey calls and read during subsequent stages. If bulk validation processes items in parallel (via `processWithBulkValidation`), thread-safe map is needed.

### 2. Error Conversion: GTIN → WmItemNumber
The supplier validation works with GTINs, but consumers sent WmItemNumbers. Errors need to be converted back:

```java
private RequestProcessingResult convertGtinErrorsToWmItemNumbers(
        RequestProcessingResult supplierMappingResult,
        Map<String, String> wmItemNbrGtinMap) {

    // Build reverse map: GTIN → WmItemNbr
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

**Interview Point:**
> "A subtle but important detail: the supplier validation stage works with GTINs internally, but the consumer sent WmItemNumbers. So I convert error identifiers BACK to WmItemNumbers before returning. The consumer sees their original input in error messages, not our internal GTIN identifiers. This is user-centric error design."

### 3. Transaction Marking (Observability)

```java
try (var uberKeyTxn = transactionMarkingManager
        .getTransactionMarkingService()
        .currentTransaction()
        .addChildTransaction(INVENTORY_SEARCH_DC_SERVICE, UBER_KEY_WM_ITEM_NBR_TO_GTIN)) {
    uberKeyTxn.start();
    // ... UberKey call
}
```

Each stage is wrapped in transaction marking for Dynatrace observability. This creates a trace tree:
```
InventorySearchDCService
├── UberKeySupportWmItemNbrToGtinCall
└── EIInventorySearchDCCall
```

### 4. RequestProcessor Pattern (Centralized Bulk Validation)

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

**Interview Point:**
> "RequestProcessor is like a pipeline processor. Each stage takes the current state, processes valid items, catches failures, tags them with an error source (UberKey, Supplier, EI), and passes updated state to the next stage. By the end, we have a complete picture of which items succeeded and which failed at which stage."

---

## Data Models (Java Records - Java 17!)

```java
// Uses Java records (immutable, auto-generated equals/hashCode/toString)
public record DCInventoryPayload(
    List<EIDCInventoryByInventoryType> inventoryByInventoryType,
    ItemIdentifier itemIdentifier,
    NodeInfo nodeInfo
) {}

public record EIDCInventoryResponse(
    List<EIDCInventoryByInventoryType> inventoryByInventoryType,
    ItemIdentifier itemIdentifier,
    NodeInfo nodeInfo,
    List<ErrorsItem> errors  // EI may return errors for specific items
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

**Interview Point:**
> "I used Java records for the DC inventory models - they're immutable by default, auto-generate equals/hashCode/toString, and clearly communicate that these are data carriers, not business logic classes. This is a Java 17 best practice."

---

## Factory Pattern for Multi-Site (ACTUAL Code)

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

**How Spring discovers implementations:**
- `USConfig` is `@Component("US")`
- `CAConfig` is `@Component("CA")`
- `MXConfig` is `@Component("MX")`
- Spring auto-injects all into `Map<String, SiteConfigProvider>`
- Factory looks up by name from CCM siteId mapping

**Interview Point:**
> "Spring's `Map<String, SiteConfigProvider>` injection automatically discovers all implementations. The factory just does a map lookup. Adding Brazil means adding one `BRConfig` class with `@Component(\"BR\")` - zero changes to factory or service."

---

## Response Building (Always HTTP 200)

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

Uses a **generic ResponseBuilder** with functional interfaces - reusable across APIs.

---

## Interview Questions

### Q: "Walk me through the DC Inventory request flow."
> "Three stages. First, convert WmItemNumbers to GTINs via UberKey service. Second, validate each GTIN against supplier authorization mapping. Third, call Enterprise Inventory API for actual DC inventory data. Each stage accumulates errors separately. The response merges all successes and all errors with error source tracking - so the consumer knows if an item failed at GTIN conversion, authorization, or data lookup."

### Q: "Why ConcurrentHashMap for the GTIN map?"
> "Thread safety. The GTIN map is populated during UberKey calls via `processWithBulkValidation`, which may process items in batches. The map is then read by subsequent stages. ConcurrentHashMap ensures safe concurrent access without explicit synchronization."

### Q: "Why convert GTIN errors back to WmItemNumbers?"
> "User experience. The consumer sent WmItemNumbers. If we return errors with GTIN identifiers, they'd have to reverse-map themselves. By converting errors back to WmItemNumbers, the consumer sees their original input in error messages. This is a small detail that makes a big difference in API usability."

### Q: "What's the hardest part of this implementation?"
> "The error accumulation across stages. Each stage can produce valid items and errors. The RequestProcessor pattern handles this by tracking errors with sources. But the tricky part was the GTIN-to-WmItemNumber reverse conversion in Stage 2 - building the reverse map, handling duplicates, and ensuring errors from all stages use consistent identifiers."

---

## IMPORTANT: CompletableFuture Note

> **Resume mentions CompletableFuture for DC Inventory but the actual code (PR #271) is synchronous.**
> CompletableFuture IS used in `audit-api-logs-srv` (PR #65) for dual-region Kafka failover.
>
> **Safe answer:** "We use CompletableFuture in the Kafka publishing layer. For DC Inventory, the EI backend aggregates across DCs internally. The bulk support here is about processing multiple items in one request, not parallel DC queries."

---

*Next: [05-interview-qa.md](./05-interview-qa.md)*
