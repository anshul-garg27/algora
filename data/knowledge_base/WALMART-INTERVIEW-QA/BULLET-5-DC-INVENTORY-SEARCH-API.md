# Bullet 5 — DC Inventory Search API (OpenAPI design-first, 3-stage pipeline, multi-site)

> **Resume line (verbatim):**
> "Developed DC Inventory Search API end-to-end using OpenAPI design-first approach, enabling parallel consumer integration (30% faster) with 3-stage pipeline and factory pattern for multi-site support (US/CA/MX)."

> **Repo:** `cp-nrti-apis` (Channel Performance — Near-Real-Time Inventory APIs), org `dsi-dataventures-luminate`, WCNP namespace `data-ventures-luminate-cperf`. Spring Boot 3.5.x / Java 17 / Jakarta. The DC inventory endpoint is `POST /dc/inventory/status`.

> **READ THIS FIRST — the honesty header.** This bullet has THREE specific code-vs-resume gaps you MUST internalize before the interview, because if an interviewer opens the repo they will see them:
> 1. **"Factory pattern for multi-site (US/CA/MX)"** — there is **no class named `*Factory`** that selects a US/CA/MX implementation at runtime. `grep -rn "factory" src/main` returns only framework factories (`DefaultKafkaProducerFactory`, MapStruct `Mappers.getMapper`, `org.springframework.beans.factory.*` imports). Multi-site is achieved by **deploying the same codebase per region with different CCM config** (`wmSiteId`, `dcInventoryWmConsumerCountryCode` both default to `"US"` in this repo's `ccm.yml`). The closest thing to a runtime "factory" is (a) Spring's bean container injecting per-domain service beans and (b) **header-based controller dispatch** that picks prod vs sandbox controllers. Be ready to reframe this precisely (Section 6).
> 2. **"OpenAPI design-first … with codegen"** — the build does NOT generate the DC controllers from the spec. The `openapi-generator-maven-plugin` runs the **`spring`** generator **only** on `openapi_items_assortment.json` (the items-assortment endpoint). For `openapi.json` it runs the **`openapi`** generator, which just **resolves/bundles** the spec into `api-spec/openapi_consolidated.json` — **no Java is produced**. The DC controllers are **hand-written** to match a **hand-maintained** spec. Design-first is real as a *process* (spec agreed up front); it is not enforced by server-side codegen for DC.
> 3. **Authorship** — `git log` on `DcInventoryController.java` / `DcInventoryServiceImpl.java` shows the feature was largely authored by **Keshav Gatla** and **Ambiorix Cruz Angeles** (DC endpoint dev→stage→prod, error-response enhancement). Anshul has commits in the surrounding NRTI codebase (sandbox metrics, store-gtin removal, scaling, Snyk/logging fixes, Spring Boot 3 work) but is **not** the sole author of the DC files. Use "I" for the work you did and "the team / I contributed to" honestly — see Section 6 for the safe phrasing.

---

## 1. Plain-English: what this actually is (ELI5 then precise)

**ELI5.** Walmart suppliers (Coca-Cola, Pepsi, Frito-Lay, etc.) want to know *"how many units of my product are sitting in Walmart Distribution Center #45 right now?"* A Distribution Center (DC) is the big warehouse that feeds many stores. The **DC Inventory Search API** lets a supplier send a DC number plus a list of their item numbers and get back current inventory at that DC, broken down by inventory *type* (promo vs turn) and *state* (e.g., sellable, damaged, on-hold). We don't own that inventory data — it lives in Walmart's internal **Enterprise Inventory (EI)** system. Our API is a **secure, authorized gateway**: it checks the supplier is allowed to see those items, translates their item numbers into the GTINs EI understands, calls EI, and reshapes the answer into a clean supplier-facing JSON.

**Precise.** `POST /dc/inventory/status` is a **synchronous, blocking Spring MVC endpoint** (`DcInventoryController.getDcInventory`) returning **HTTP 200** with a `DcInventoryStatusResponse`. The request is `DcInventoryStatusRequest { Integer dcNbr; List<String> values }` plus an `itemIdentifier` query param (only `wmItemNbr` is supported). The flow:
1. **Validate** the request (`dcNbr` is `@NotNull @Positive`; `values` must be valid WM item numbers via `NrtBusinessValidatorService.validateDCInventoryStatusRequest`).
2. **Resolve the supplier** from the `WM_CONSUMER.ID` header → `ParentCompanyMapping` (Postgres `nrt_consumers`) to get `globalDuns` and the display `parentCmpnyName`.
3. **Translate** WM item numbers → GTINs via the **UberKeys** service (`getGtinsFromWmItemNbrs`).
4. **Authorize** those GTINs against the supplier's `globalDuns` (`StoreGtinValidatorServiceImpl.getMappedGtins`) — only items the supplier is permitted to see survive.
5. **Call EI** PIT-by-item inventory read over reactive **WebClient** (`EI-PIT-BY-ITEM-INVENTORY-LOOKUP`, host `ei-pit-by-item-inventory-read.walmart.com`, path `/api/v1/inventory/node/{nodeId}/itemnumber`).
6. **Map** the EI response (`EIDCInventoryResponse`) into the supplier-facing `DcInventoryItem` list (`EIServiceHelper.getDcInventories`).
7. Return the response. Each external hop is wrapped in a **Strati child transaction** for observability.

"DC Inventory Search" = a server-side **search/lookup** (point-in-time read) of warehouse inventory for items a supplier owns, fronted by an **OpenAPI contract** so consumers could integrate before the backend was finished.

---

## 2. The real architecture (grounded in code)

### 2.1 End-to-end flow (ASCII)

```
                         ┌───────────────────────────────────────────────┐
 Supplier client  ─────► │  Edge / API Gateway (Walmart)                  │
 POST /dc/inventory/status │  • verifies WM_SEC.* signature (NOT in this repo)│
 headers: WM_CONSUMER.ID,  │  • routes to data-ventures-luminate-cperf      │
   WM_SVC.NAME=channelperformance-nrti, WM_SVC.ENV, ...                    │
 body: {dcNbr:45, values:["000444444",...]}                               │
                         └───────────────────────────┬───────────────────┘
                                                      ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│  cp-nrti-apis  (Spring Boot 3.5 / Java 17, Tomcat MVC)                              │
│                                                                                    │
│  ── STAGE 1: INBOUND FILTER / VALIDATION ──────────────────────────────────────── │
│   filters/RequestFilter (OncePerRequestFilter, @Order LOWEST_PRECEDENCE-100)       │
│     • sanitize URI/URL, validate WM_CONSUMER.ID → 401 if missing                   │
│     • open Strati transaction (TransactionMarkingManager)                          │
│   interceptors/NrtiApiInterceptor (PSP / supplier-context checks)                  │
│   Header dispatch on @RequestMapping(headers="wm_svc.name=channelperformance-nrti")│
│     → DcInventoryController  (prod)                                                 │
│     → DcInventorySandboxController (headers="...-sandbox", mock data)              │
│   Bean Validation: DcInventoryStatusRequest @NotNull @Positive dcNbr               │
│   NrtBusinessValidatorService.validateDCInventoryStatusRequest(req, itemIdentifier)│
│                                                                                    │
│  ── STAGE 2: AUTHORIZE + FETCH FROM DOWNSTREAM (the heart) ─────────────────────── │
│   DcInventoryController.getDcInventory                                             │
│     → SupplierMappingServiceImpl.getSupplierMapping(WM_CONSUMER.ID)                │
│         → ParentCompanyMapping (Postgres nrt_consumers, Caffeine-cached 6h)        │
│     → DcInventoryServiceImpl.getDcInventoryStatus(dcNbr, wmItemNbrs, mapping, ...)  │
│         (a) UberKeyReadService.getGtinsFromWmItemNbrs   [Strati child txn]          │
│             WM item nbr → GTIN   (calls uber-keys-read-nsf via WebClient)           │
│         (b) StoreGtinValidatorServiceImpl.getMappedGtins(globalDuns, gtins)         │
│             authorization: only GTINs mapped to this supplier survive               │
│         (c) HttpServiceImpl.sendHttpListRequest(...)    [Strati child txn]          │
│             reactive WebClient GET EI PIT-by-item, 10s timeout,                     │
│             Retry.backoff(3,100ms,max2s) → NrtiUnavailableException                │
│             URI built by EIServicesRequestBuilder.createDcInventoryHttpRequestURI  │
│             headers built by getEIDcInventoryHttpRequestHeaders() (CCM-driven,      │
│             incl. WM_CONSUMER.COUNTRY_CODE = "US")                                  │
│                                                                                    │
│  ── STAGE 3: MAP / BUILD RESPONSE ─────────────────────────────────────────────── │
│   EIServiceHelper.handleEIDcInventoryResponse(resp)  (status → exceptions)         │
│   EIServiceHelper.getDcInventories(mappedWmItemNbrs, eiResponses)                  │
│     → DcInventoryItem.builder()...inventoryByInventoryType(...)                    │
│        (InventoryByInventoryType → InventoryByState: state, qty, qtyUom, lastUpd)  │
│   DcInventoryStatusResponse.builder().supplier(...).dcNbr(...).inventory(...).errors│
│   AppUtil.addResponseHeaderIds(...) → correlation id / txn id headers              │
│   return 200                                                                        │
└──────────────────────────────────────────────────────────────────────────────────┘
                                  │  reactive WebClient (HttpServiceImpl)
                                  ▼
        ┌───────────────────────────────────────────────────────────────┐
        │ EI PIT-by-item inventory read (system of record, HTTP)         │
        │ host ei-pit-by-item-inventory-read.walmart.com                 │
        │ /api/v1/inventory/node/{nodeId}/itemnumber                     │
        │ returns EIDCInventoryResponse[] (inventoryByInventoryType,     │
        │   itemIdentifier, nodeInfo, errors[])                          │
        └───────────────────────────────────────────────────────────────┘

  Cross-cutting: every request also flows through dv-api-common-libraries LoggingFilter
  → audit-api-logs-srv → Kafka api_logs_audit_* → GCS sink (the audit pipeline, Bullet 1/2/10).
```

### 2.2 Real file paths and classes (DC slice)

| Concern | Class / file |
|---|---|
| Prod controller | `controller/DcInventoryController.java` — `@RequestMapping(headers={NRT_PROD_APP_MANDATORY_HEADERS="wm_svc.name=channelperformance-nrti"}, value=NRTI_DC_APIS="/dc")`, `@PostMapping("/inventory/status", params={"!controller"})` |
| Sandbox controller | `controller/DcInventorySandboxController.java` — `headers={SANDBOX_MANDATORY_HEADERS="wm_svc.name=channelperformance-nrti-sandbox"}` |
| Business logic | `services/impl/DcInventoryServiceImpl.java` (`implements DcInventoryService`) |
| Sandbox logic | `services/impl/...` (`DcInventorySandboxService`) — returns mocked data |
| Supplier resolution | `services/impl/SupplierMappingServiceImpl.java` → `entity/ParentCompanyMapping` |
| WM item → GTIN | `services/UberKeyReadService` (`getGtinsFromWmItemNbrs`) |
| Authorization | `services/impl/StoreGtinValidatorServiceImpl.java` (`getMappedGtins`) |
| EI request build | `services/builders/EIServicesRequestBuilder.java` (`createDcInventoryHttpRequestURI`, `createDcInventoryHttpRequestBody`, `getEIDcInventoryHttpRequestHeaders`) |
| HTTP executor | `services/impl/HttpServiceImpl.java` (reactive WebClient + retry/timeout) |
| Response mapping | `services/helpers/EIServiceHelper.java` (`getDcInventories`, `handleEIDcInventoryResponse`, `getInventoryByInventoryType`) |
| Validation | `services/validators/NrtBusinessValidatorService.java` (`validateDCInventoryStatusRequest`) |
| EI DTOs | `models/ei/dcinventory/{EIDCInventoryResponse, EIDCInventory, EIDCInventoryByInventoryType, DCInventoryPayload}.java` |
| Response DTOs | `models/response/dc/{DcInventoryStatusResponse, DcInventoryItem, InventoryByInventoryType, InventoryByState}.java` |
| Request DTO | `requests/DcInventoryStatusRequest.java` (`@RequestScope`, `dcNbr` `@NotNull @Positive`, `values`) |
| Per-domain config | `configs/EiApiCCMConfig.java` (the `getEIDcInventory*` block — host, uri path, country code, svc name, originator id) |
| Site config | `configs/SiteIdCCMConfig.java` (`getWmSiteId()`), `configs/SiteIdFilterAspect.java`, `services/SiteIdFilterService` |
| WebClient bean | `configs/WebClientConfig.java` |
| Contract | `api-spec.yaml` (root, partial/legacy), `api-spec/schema/openapi.json` (source), `api-spec/openapi_consolidated.json` (generated bundle), `api-spec/examples/*` |
| Codegen | `pom.xml` `openapi-generator-maven-plugin` 7.0.1, springdoc-openapi 2.3.0 |

### 2.3 What the EI DC inventory payload looks like (real fields)

EI returns an array of `EIDCInventoryResponse`:
- `List<EIDCInventoryByInventoryType> inventoryByInventoryType` — each has `String inventoryType` and `List<EIDCInventory> inventory`.
- `EIDCInventory { String state; Double quantity; Long lastUpdatedTime; String qtyUom }`.
- `ItemIdentifier itemIdentifier` (carries the wmItemNbr value used to correlate back).
- `NodeInfo nodeInfo` (the DC/node).
- `List<ErrorsItem> errors` (per-item EI errors).

`InventoryType` enum (`models/enums/InventoryType.java`) = `{ PROMO, TURN }`. So a DC may report the same item under both PROMO and TURN inventory, each with multiple `state`/`quantity` rows.

---

## 3. Every design decision

| # | Decision | Why (real engineering reason) | Alternatives considered | Trade-off / what we gave up |
|---|---|---|---|---|
| 1 | **Design-first OpenAPI contract** (`api-spec/schema/openapi.json` agreed up front, bundled to `openapi_consolidated.json`) | Consumers (supplier-integration, internal UI, partner teams) could generate client SDKs + mock servers from the spec and start integrating **before** the backend was complete → the "30% faster / parallel integration" claim. Contract also feeds R2C contract tests and springdoc Swagger UI. | **Code-first** (write controllers, generate spec after). | Spec and code can drift (and they did — see #9, root `api-spec.yaml` advertises **plural** paths like `/stores/...` and lacks `/dc/...` entirely, while deployed routes are **singular** `/store`, `/dc`). Design-first needs discipline + contract tests to stay honest. |
| 2 | **Hand-written controllers (not full server codegen) for DC/store** | Walmart's NRTI surface uses **header-based multitenancy** (same path, different `wm_svc.name`), Strati child-transaction wrapping, `@RequestScope` DTOs, custom error contracts — patterns the stock Spring generator doesn't express cleanly. So only the newer **items-assortment** endpoint uses the `spring` generator (delegate pattern); the rest are hand-written against the agreed spec. | Generate all controllers via `openapi-generator` `spring` + delegate. | The DC controllers aren't *mechanically* tied to the spec; correctness relies on review + R2C tests, not the compiler. (This is exactly why I must phrase "design-first" as a *process*, not "codegen for DC".) |
| 3 | **3-stage request pipeline** (filter/validate → authorize+fetch → map/build) | Clean separation: security boundary at the edge (filter/interceptor), business + authorization + IO in the service, pure transformation in helpers/builders. Each stage is independently testable and observable (Strati child txns per external hop). | One fat controller method; or a heavyweight pipeline framework. | More classes / indirection; a reader must follow controller → service → builder/helper to see the whole story. |
| 4 | **Reactive WebClient (`HttpServiceImpl`) with `.block()`** for EI calls | WebClient is the modern, non-deprecated client; gives declarative `timeout(10s)` + `Retry.backoff(3,100ms,max2s)`. We `.block()` because the controllers are blocking Spring MVC (Tomcat servlet), so we expose a synchronous contract. | `RestTemplate` (deprecated); full end-to-end WebFlux. | We pay a thread-per-request cost (no true reactive backpressure); `.block()` on a WebFlux client inside MVC is a known smell that can starve the Tomcat pool under high concurrency. |
| 5 | **WM item nbr → GTIN translation via UberKeys before EI** | EI keys inventory by **GTIN**; suppliers think in **WM item numbers**. UberKeys is the canonical cross-reference. Doing it before authorization means we authorize on the *resolved* GTIN. | Make supplier send GTINs (worse UX); cache the mapping locally (staleness risk). | Extra network hop + failure mode (UberKey errors become per-item errors in the response). |
| 6 | **Authorization on `globalDuns` → GTIN mapping** (`StoreGtinValidatorServiceImpl.getMappedGtins`) | Suppliers must only see their own items. Postgres `supplier_gtin_items` maps `globalDuns + gtin`. Items not mapped to this supplier are dropped and surface as `WM_ITEM_NBR_NOT_MAPPED_TO_THE_SUPPLIER` errors. | Trust the gateway / no row-level checks. | A DB read on every request (mitigated by Caffeine cache on the parent-company mapping; the GTIN mapping itself is queried per request). |
| 7 | **CCM-driven per-environment config** (`EiApiCCMConfig.getEIDcInventory*`, `SiteIdCCMConfig.getWmSiteId`) | Hosts, URI paths, consumer IDs, `WM_CONSUMER.COUNTRY_CODE`, `wmSiteId` are all Strati `@ManagedConfiguration` properties → change EI endpoints or site id at runtime without redeploy; same artifact deployed per region with different CCM. | Hardcode per-env; Spring profiles only. | "Multi-site" is config + per-region deploy, **not** a runtime US/CA/MX switch in one process (the gap in #1 honesty header). |
| 8 | **Builder pattern for responses** (`DcInventoryStatusResponse.builder()`, `DcInventoryItem.builder()`, Lombok `@Builder`/`@Value` immutable) | Immutable, readable assembly; a **custom builder** on `DcInventoryStatusResponse` nulls `supplier`/`dcNbr` when both `inventory` and `errors` are empty (clean "no data" response). | Setters / public constructors. | The custom-builder null-trick is subtle; a maintainer could miss it. |
| 9 | **`@RequestScope` on `DcInventoryStatusRequest`** | One request DTO instance per HTTP request (safe with shared singletons). | Default singleton-ish binding. | Minor proxy overhead per request. |
| 10 | **`itemIdentifier` restricted to `wmItemNbr`** | DC search only supports WM item number lookups today; `validateDCInventoryStatusRequest` throws `InvalidNrtiRequestException` ("request must contain wmItemNbr") for anything else. | Support GTIN directly. | Less flexible; deliberate scope control. |

---

## 4. Deep-dive Q&A (fundamentals → internals → scenario → behavioral)

### FUNDAMENTALS

**Q1. What is the DC Inventory Search API and who uses it?**
"It's a supplier-facing REST endpoint, `POST /dc/inventory/status`, in our `cp-nrti-apis` gateway. External Walmart suppliers send a distribution-center number (`dcNbr`) and a list of their WM item numbers, and we return the current point-in-time inventory at that DC broken down by inventory type — PROMO vs TURN — and by state, with quantity and unit of measure. We don't own the inventory; it lives in Walmart's Enterprise Inventory system. Our job is to authorize the supplier, translate their item numbers into GTINs, call EI, and reshape the response into a clean, supplier-scoped JSON."

**Q2. What does "DC" mean and how is it different from store inventory?**
"DC = Distribution Center, Walmart's warehouses that replenish stores. Store inventory (`/store/...` endpoints) is on-hand at a specific store; DC inventory is warehouse stock at a node, which is upstream of stores. The data source differs too: store on-hand comes from `EI-onhand-inventory-read`, DC comes from `EI-PIT-BY-ITEM-INVENTORY-LOOKUP` (`ei-pit-by-item-inventory-read.walmart.com`). DC is keyed by `nodeId` (the dcNbr), store by store number + GTIN."

**Q3. What is a GTIN and why translate WM item numbers to it?**
"GTIN = Global Trade Item Number, the global barcode-level identifier. Suppliers know their products by Walmart item number; EI keys inventory by GTIN. So before calling EI I translate WM item nbr → GTIN through the **UberKeys** cross-reference service (`UberKeyReadService.getGtinsFromWmItemNbrs`). If an item number doesn't resolve, it becomes a per-item error (`INVALID_WM_ITEM_NBR_MESSAGE`) rather than failing the whole request."

**Q4. Walk me through the request from the wire to the response.**
"Three stages. **Stage 1** — `RequestFilter` (a `OncePerRequestFilter` at `Ordered.LOWEST_PRECEDENCE - 100`, so it runs before `StoreInboundRequestFilter`) sanitizes the URI, validates `WM_CONSUMER.ID` (401 if missing), and opens a Strati transaction; `NrtiApiInterceptor` does supplier-context checks; Spring routes to `DcInventoryController` by the `wm_svc.name=channelperformance-nrti` header; bean validation + `NrtBusinessValidatorService` validate the body. **Stage 2** — `DcInventoryServiceImpl.getDcInventoryStatus` resolves the supplier mapping (Postgres, cached), translates item numbers to GTINs via UberKeys, authorizes those GTINs against the supplier's globalDuns, then calls EI over reactive WebClient. **Stage 3** — `EIServiceHelper` validates the EI status and maps the EI payload into `DcInventoryItem`s grouped by inventory type and state; I build the immutable `DcInventoryStatusResponse` and return 200. Every external hop is its own Strati child transaction."

**Q5. What does "OpenAPI design-first" mean here?**
"Design-first means the API contract — paths, schemas, validation rules, examples — is authored and agreed **before** implementation. We keep the spec under `api-spec/`. Consumers take that spec, generate client SDKs and mock servers from it, and build against the mock while we build the real backend in parallel. That overlap is where the ~30% faster integration comes from: integration work isn't serialized behind backend completion. Honestly, for the DC/store endpoints the controllers are hand-written to match the spec, not generated — the codegen plugin only generates server code for the items-assortment endpoint and otherwise just bundles the spec. So design-first here is a discipline backed by contract tests, not compiler-enforced codegen."

### INTERMEDIATE

**Q6. How exactly is the EI DC call constructed?**
"`EIServicesRequestBuilder.createDcInventoryHttpRequestURI(dcNbr)` builds `https://{dcInventoryHost}/api/v1/inventory/node/{nodeId}/itemnumber` from `EiApiCCMConfig` (`getEIDcInventoryUriScheme/Host/UriPath`), expanding `nodeId` = dcNbr. The body is `createDcInventoryHttpRequestBody(mappedWmItemNbrs)` → `{ "wmItemNumbers": [...] }`. Headers come from `getEIDcInventoryHttpRequestHeaders()`: `WM_CONSUMER.ID`, `WM_CONSUMER.COUNTRY_CODE` (="US"), `WM_BUSINESS_UNIT` (="WMT"), `WM_SVC.ENV/NAME/VERSION` (`EI-PIT-BY-ITEM-INVENTORY-LOOKUP`/`1.0.0`), `WM_APP_NAME` (`LCP-DSD-CONSUMERS`), `WM_ORIGINATOR_ID` (=111), content-type JSON, accept `*/*`. Interesting wrinkle: the URI says `node/{id}/itemnumber` (GET-style) but item numbers go in the body — `HttpServiceImpl.sendHttpListRequest(uri, GET, entity, EIDCInventoryResponse[].class)` sends a **GET with a body**, which is unusual but what EI accepts."

**Q7. What's the response shape and how is it built?**
"`EIServiceHelper.getDcInventories` iterates the *mapped* WM item numbers, finds the matching `EIDCInventoryResponse` by `itemIdentifier.value`, and for each builds a `DcInventoryItem` with `inventoryByInventoryType`: for each EI `inventoryByInventoryType` it copies `inventoryType` and maps the `inventory` list into `InventoryByState{ state, quantity, lastUpdatedTime (formatted), qtyUom }`. The top-level `DcInventoryStatusResponse` carries `supplier` (parent company name), `dcNbr`, `inventory[]`, and `errors[]`. `@JsonInclude(NON_EMPTY)` plus the custom builder means an all-empty response cleanly omits supplier/dcNbr."

**Q8. How is authorization enforced?**
"After resolving GTINs I call `StoreGtinValidatorServiceImpl.getMappedGtins(globalDuns, null, () -> gtinValues)`. It queries Postgres `supplier_gtin_items` for rows matching the supplier's `globalDuns` and the candidate GTINs. Only mapped GTINs survive; `NrtBusinessValidatorService.getMappedWmItemNumbers` maps that back to which WM item numbers are allowed. Unauthorized items become `WM_ITEM_NBR_NOT_MAPPED_TO_THE_SUPPLIER` errors. If nothing is authorized, I short-circuit and return a no-inventory response with just supplier + dcNbr + errors — I never call EI for items the supplier can't see."

**Q9. Where does the "factory pattern for multi-site (US/CA/MX)" actually live in code?**
"I'll be precise because this is easy to over-claim. There's no `*Factory` class that, per request, returns a US/CA/MX implementation. Multi-site is achieved two ways. First, **per-region deployment of the same artifact** with different CCM: `SiteIdCCMConfig.getWmSiteId()`, `EiApiCCMConfig.getEIDcInventoryWmCountryCode()` etc. are all Strati-managed; in this repo they default to US (`wmSiteId=1704989259133687000`, country code `US`), and a CA/MX deployment overrides them — confirmed by the `*-INTL` companion app in `sr.yaml`. Second, within a single process the closest thing to a 'factory' is **Spring's bean container + header-based controller dispatch**: the same `/dc/inventory/status` path resolves to `DcInventoryController` or `DcInventorySandboxController` purely by the `wm_svc.name` header on `@RequestMapping(headers=...)`, and `DcInventoryService` vs `DcInventorySandboxService` beans are injected accordingly. So if I say 'factory' I mean *config/deploy-time site selection plus DI-based variant selection*, not a Gang-of-Four factory choosing US/CA/MX at runtime."

**Q10. How does the SiteId filter work and is it part of DC?**
"`SiteIdFilterAspect` is an AOP `@Around` on `execution(* com.walmart.cpnrti.repository..*(..))` that enables a Hibernate `siteIdFilter` before every repository call and disables it after (in a `finally`, so it cleans up even on exception). That auto-scopes JPA reads to the environment's `site_id` for tenant isolation. It's relevant to DC indirectly — the supplier/GTIN authorization reads go through repositories and are therefore site-scoped — but the DC inventory data itself comes from EI over HTTP, not from our DB, so the aspect doesn't touch the EI call."

**Q11. What are the timeouts, retries, and error handling on the EI call?**
"`HttpServiceImpl` sets a 10-second `timeout` and `Retry.backoff(3, 100ms, maxBackoff 2s)` with a `doBeforeRetry` log; on retry exhaustion it rethrows the original failure, and the surrounding `catch(Exception)` maps it to `NrtiUnavailableException` (→ 503). Before mapping, `EIServiceHelper.handleEIDcInventoryResponse` inspects status: 404 is logged (treated as no-data, not fatal), 400 throws `InvalidNrtiRequestException` (→ 400 with EI's body), anything not 200/206 throws `NrtiUnavailableException`."

### DEEP / INTERNALS

**Q12. Why GET with a request body for the EI call — isn't that against HTTP semantics?**
"It is unusual — RFC 7231 says GET bodies have no defined semantics and many intermediaries drop them. We do it because EI's PIT-by-item contract accepts the item-number list in the body on that route, and `HttpServiceImpl` passes the `HttpEntity` body regardless of method via WebClient's `.body(BodyInserters.fromValue(...))`. If I were designing the EI contract I'd make it a POST (or a query param for small lists). It works here because the call is server-to-server inside Walmart's mesh where the body survives. It's a latent portability risk worth calling out."

**Q13. `.block()` on a reactive WebClient inside Spring MVC — what's the risk and why is it there?**
"The controllers are blocking servlet endpoints, so I have to materialize a value — hence `.block()`. The risk is thread-pool starvation: each in-flight EI call holds a Tomcat worker thread blocked for up to 10s. Under a burst with a slow EI, the Tomcat pool can exhaust and we start queuing/rejecting requests. WebClient's own event-loop threads are fine; it's the servlet thread that's pinned. The clean fix is to go end-to-end reactive (return `Mono`/`Flux` from a WebFlux controller) so we never block a request thread, or to bound concurrency with a bulkhead/semaphore. We kept MVC because the rest of the gateway, the Strati txn model, and JPA are blocking, so a hybrid was the pragmatic choice."

**Q14. Is the retry safe? Could it duplicate side effects?**
"For DC inventory it's a **read** (idempotent), so retrying is safe — worst case we read twice. The `Retry.backoff` retries on *any* error including non-2xx that bubble as exceptions, which means a 400 could be retried before `handleEIDcInventoryResponse` runs — actually the status handling happens after `.block()` returns, so retried calls are network/5xx-class failures from WebClient. The thing I'd tighten is making the retry **predicate-based** (`.filter(isRetryable)`) so we don't waste backoff on deterministic 4xx. For write endpoints (IAC/DSC) retries would need idempotency keys — but DC is read-only."

**Q15. How does design-first actually produce parallel work, mechanically?**
"The spec (`openapi.json` → bundled `openapi_consolidated.json`) plus the `examples/` files (`inventory_status_*_request_200.json`, etc.) are a complete machine-readable contract. A consumer team runs `openapi-generator` on it to get a typed client in their language, and stands up Prism/WireMock from the same examples to get a mock server returning realistic payloads. They build and test their integration against the mock on day one. When our real endpoint ships, they flip the base URL. The serialization work — request/response shape, field names (snake_case via `@JsonProperty`), enums (PROMO/TURN), error envelope — is settled in the spec review, so there's almost no rework. That overlap (consumer build time hidden behind our backend build time) is the ~30%."

**Q16. The build runs openapi-generator twice — what does each execution do?**
"Execution `generate-server-code` runs the **`spring`** generator with `interfaceOnly=true`, `delegatePattern=true`, `useSpringBoot3=true`, `useJakartaEe=true`, Lombok on, against `openapi_items_assortment.json` only — that produces the `InventoryControllerApi` interface + models for the items-assortment endpoint, which `InventoryController` implements. The second execution uses generator name **`openapi`** against `openapi.json` and just emits a resolved/bundled `openapi_consolidated.json` (a doc artifact, no Java). So DC/store controllers are not generated; they're hand-written. springdoc-openapi 2.3.0 also serves live Swagger UI from the running app's annotations."

**Q17. What's `params={"!controller"}` on the `@PostMapping` and why?**
"It's a Spring request-mapping condition meaning 'match only when there is **no** `controller` query parameter'. It's a disambiguation guard so this handler doesn't accidentally collide with another mapping that uses a `controller` param. Combined with the `headers` condition on the class-level `@RequestMapping`, Spring's `RequestMappingHandlerMapping` picks the right method by header + path + absence of that param."

**Q18. How are inventory types (PROMO/TURN) and states represented end to end?**
"EI returns `inventoryByInventoryType[]` where `inventoryType` is a free string but maps to our `InventoryType` enum `{PROMO, TURN}`. Under each type is an `inventory[]` of `{state, quantity, lastUpdatedTime, qtyUom}`. We pass `inventoryType` through as-is and map each state row into `InventoryByState`. `ValidInventoryState` enum constrains the states we recognize. So the supplier sees, per item: a list of inventory types, each with a list of states and quantities — e.g., item X has TURN inventory with 1200 units sellable and 30 damaged, plus PROMO inventory with 200 units allocated."

**Q19. Where's caching and what's cached?**
"`CacheConfig` wires Caffeine caches. The one that matters for DC is `parentCompanyMappingCache` (key `consumerId+siteId`, ~6h TTL) used by `SupplierMappingServiceImpl` — so the supplier-resolution DB read is mostly served from memory. There's also a `storeNbrToStoreTimeZoneCache` warmed weekly, but that's store-side, not DC. The supplier→GTIN authorization read is **not** cached per request (it varies by the GTIN set), so that's a real DB hit each call."

**Q20. How is observability wired for this endpoint?**
"Strati `TransactionMarkingManager`. `RequestFilter` opens the root transaction; in `DcInventoryServiceImpl` each external call is a child transaction via try-with-resources — `UberKeySupportWmItemNbrToGtinCall` under `DcInventoryService`, `getMappedGtins` under `GtinValidatorService`, and `EIDcInventoryCall` under `DcInventoryService`. `.start()` and auto-close mark span boundaries. On the way out, `AppUtil.addResponseHeaderIds` echoes the correlation id and transaction id in response headers. Micrometer/Prometheus + OTLP/Dynatrace export the metrics/traces."

### SCENARIO / WHAT-IF

**Q21. EI is down or slow. What happens?**
"WebClient times out at 10s, retries up to 3 times with backoff (100ms→2s), and if still failing rethrows → `catch` → `NrtiUnavailableException` → 503 to the supplier (the controller advertises 503). The danger is the blocking thread held during those retries; under sustained EI slowness Tomcat threads can saturate. Mitigations I'd add: a circuit breaker (Resilience4j) so we fail fast when EI is unhealthy instead of holding threads, a bulkhead to cap concurrent EI calls, and ideally reactive controllers to stop pinning request threads."

**Q22. A supplier sends 10,000 item numbers in one request. What breaks?**
"Today there's no explicit cap on `values` for DC (unlike multi-GTIN store status which is capped at 100). The request would be `distinct()`-ed, all sent to UberKeys and then to EI in a single GET-with-body — large body, large EI response, and one blocked thread for the whole thing. At scale I'd (a) enforce a max batch size with `@Size`, (b) chunk into parallel EI calls with `CompletableFuture.supplyAsync` (the pattern already used for store UberKey fan-out, partitioned at 100), and (c) paginate the response. As-is, a huge request risks timeouts and memory pressure."

**Q23. Two suppliers share a GTIN — could supplier A see supplier B's data?**
"No, because authorization is on `globalDuns + gtin` in `supplier_gtin_items`, and DC inventory is per-node totals, not per-supplier ownership of physical units. We only return inventory for GTINs explicitly mapped to the requesting supplier's globalDuns. The risk would be a **misconfigured mapping** (a GTIN wrongly mapped to the wrong globalDuns) — that's a data-quality control, not a code path. The SiteId Hibernate filter also scopes the mapping reads to the right site."

**Q24. The `wm-site-id` / country code is missing or wrong. What happens to DC?**
"For DC the EI country code comes from CCM (`dcInventoryWmConsumerCountryCode`, default US), not from the inbound request, so a missing inbound site header doesn't change the EI call in this US deployment — it always sends US. The inbound `wm_svc.name` header *is* mandatory for routing (no `channelperformance-nrti` → no controller match → 404/401). Contrast with the audit GCS sink (Bullet 1/2/10) where a missing `wm-site-id` lands records in the US catch-all bucket; that's a different layer."

**Q25. How would you add a true multi-site factory if asked to support US/CA/MX in one process?**
"I'd introduce a `SiteContext` resolved per request from `wm-site-id`/country header, and a `Map<Site, DcInventoryClient>` (or a `DcInventoryClientFactory.forSite(site)`) that returns the per-country EI client configured with that country's host/consumer-id/country-code. CCM would hold a map keyed by site instead of single values. The controller would resolve the site, the factory would hand back the right strategy, and the SiteId Hibernate filter would scope DB reads to that site. I'd choose a **registry/strategy factory** over if/else because countries are open-ended (adding MX shouldn't touch existing branches) and over per-country subclasses because behavior is identical except config. The trade-off is more moving parts and the need for per-site secrets/observability in one pod."

**Q26. How do you handle partial failure — 3 of 5 items resolve, EI errors on 1?**
"It's designed for partial success. Unresolvable WM item numbers, unauthorized GTINs, and EI per-item errors all accumulate into the `errors[]` list (`NrtiApiErrorDetails{ fieldName, value, message }`) while the successful items populate `inventory[]`. EI errors are extracted in `getEIDCInventoryErrors` by flat-mapping each response's `errors`. The supplier gets one 200 response with both the good data and a clear, per-item error list — much better than all-or-nothing."

**Q27. What if UberKeys returns a GTIN but EI has no record for it at that DC?**
"`getDcInventories` finds the matching `EIDCInventoryResponse` by `itemIdentifier.value`; if EI returned an error for that item (non-empty `errors`), we skip building an `inventory` entry and add it to `errors` as `NO_DATA_FOUND`. If EI simply has zero inventory, you'd get an item with empty inventory states. So 'mapped but no stock' and 'mapped but EI error' are distinguishable in the response."

**Q28. Contract test fails because implementation returns a field the spec doesn't have. How do you resolve it design-first?**
"Design-first means the spec wins. I'd update the spec first (add the field with type/description/example), get consumer sign-off (especially if it's breaking), regenerate the bundled `openapi_consolidated.json`, then make the code match. I would not silently change the code and let the spec rot — that's how the root `api-spec.yaml` drifted to plural paths that don't match the deployed singular routes. The R2C gate exists precisely to catch this in CI."

### BEHAVIORAL

**Q29. What was your specific contribution to this feature?**
"I want to be accurate: the DC inventory endpoint itself was built across the team — colleagues drove the original dev→stage→prod rollout and the error-response enhancement. My contributions in this codebase were adjacent and substantial: I worked on the sandbox product-metrics path, the store-GTIN validation/removal flow, scaling/HPA tuning for prod and IAC, Snyk/security and logging fixes, and the Spring Boot 3 / Java 17 modernization that this endpoint runs on. On the contract side I championed keeping the OpenAPI spec as the source of truth so consumers could integrate in parallel. If they push, I'll own exactly what I did and credit the team for the rest — I'd rather be precise than overclaim."

**Q30. What's the thing you'd most want to fix here?**
"The blocking `.block()` on a reactive client under Tomcat with unbounded request batch size. It's the most likely thing to cause a production incident under load: a slow EI plus a large request can pin and exhaust the Tomcat pool. I'd add a circuit breaker + bulkhead, cap and chunk the item batch, and ideally move the hot read paths to reactive controllers. It's a clear, defensible scaling improvement."

**Q31. Tell me about a trade-off you consciously accepted.**
"Header-based multitenancy (same path, `wm_svc.name` disambiguates prod vs sandbox vs IAC) instead of versioned/separate paths. It keeps one clean public path and lets the gateway route by service identity, but it's non-obvious to newcomers and the published spec drifted from it. I accepted the operational simplicity in exchange for that discoverability cost, mitigated by Swagger UI and the spec."

---

## 5. Defending the numbers

**"30% faster parallel consumer integration."**
- **What it measures:** the reduction in calendar time for consumer teams to complete their integration, because they start against a spec-generated mock instead of waiting for the live backend.
- **How to derive it:** Integration normally serializes as `backend_build + consumer_build`. With design-first they overlap: `max(backend_build, consumer_build) + small_glue`. If consumer integration is ~10 days and previously sat entirely behind a ~2-3 week backend build, moving it in parallel removes roughly a third of the combined critical path. "~30%" is a directional estimate from that overlap, not a stopwatch metric.
- **If pushed:** "It's an estimate of critical-path compression from parallelizing consumer work, corroborated by the fact that consumers had a typed client and a mock from the spec on day one and didn't file 'where's the endpoint' blockers. I don't have a controlled A/B; I'd present it as 'roughly a third less wall-clock to first successful integration.'" Be honest that it's an estimate — do NOT claim instrumented measurement.

**"3-stage pipeline."**
- Map it concretely: Stage 1 = filter/interceptor/validation; Stage 2 = supplier-resolve + UberKey translate + authorize + EI fetch; Stage 3 = map/build/return. Grounded in `RequestFilter`/`NrtiApiInterceptor`, `DcInventoryServiceImpl`, `EIServiceHelper`. If they say "I count more than three steps," answer: "Three *stages* (boundary → fetch → transform); each has multiple steps, but the architectural seams are those three."

**"Multi-site (US/CA/MX)."**
- Truthful version: "The platform supports US/CA/MX by deploying the same artifact per region with region-specific CCM (`wmSiteId`, country code, EI hosts) and a `*-INTL` companion deployment; in the repo I'm showing, the config defaults to US. There isn't a single-process runtime factory across all three — I'd build that with a site-keyed client registry if we consolidated regions into one deployment."

**Latency / "near-real-time."**
- DC is a synchronous read; end-to-end latency ≈ UberKey hop + (optional DB authz read, often cached) + EI hop, each bounded by the 10s WebClient timeout, typically well under a second when EI is healthy. "Near-real-time" refers to reading EI's current point-in-time state, not a cached snapshot.

---

## 6. HONEST watch-outs (if they open the code)

1. **No `*Factory` class for US/CA/MX.** `grep -rn "factory" src/main` → only `DefaultKafkaProducerFactory`, MapStruct `Mappers`, and Spring `beans.factory` imports. **Pre-empt it:** "When I say 'factory pattern for multi-site,' I mean config/deploy-time site selection via CCM plus DI/header-based variant selection — not a GoF factory. Here's exactly how I'd build a real one if we ran US/CA/MX in one process." (Q9, Q25.) Saying this *before* they catch it converts a gotcha into a maturity signal.
2. **DC controllers are hand-written, not generated.** The `spring` generator runs only on `openapi_items_assortment.json`; the `openapi` generator only bundles `openapi.json` into a consolidated doc. **Pre-empt:** "Design-first for DC is a process + contract-test discipline, not server codegen. Only items-assortment is codegen'd."
3. **Spec drift in the root `api-spec.yaml`.** It advertises **plural** RESTful paths (`/stores/...`, `/volts/...`) and **does not contain `/dc/...` at all**; deployed routes are singular (`/store`, `/dc`). **Pre-empt:** "The published yaml drifted; the maintained source is `api-spec/schema/openapi.json` → `openapi_consolidated.json`, and R2C tests guard the real routes. That drift is itself the argument for stricter design-first enforcement."
4. **Authorship.** Anshul is one of several committers; DC feature commits are mostly others. Use "I contributed / the team built; my work was X." Never claim sole authorship of the DC endpoint.
5. **GET-with-body to EI** (Q12) — unusual HTTP; own it as an EI-contract constraint and say you'd prefer POST.
6. **`.block()` on reactive WebClient in MVC** (Q13) — thread-starvation risk; have the circuit-breaker/bulkhead/reactive answer ready.
7. **No batch-size cap on DC `values`** (Q22) — store multi-GTIN caps at 100, DC doesn't; name it as a gap.
8. **`@SneakyThrows` on the controller + broad `catch(Exception)→NrtiUnavailableException`** — hides root causes behind 503s; the real cause is only in logs. Acknowledge it's a smell.
9. **`request/response_size_bytes` in the audit payload** (cross-cutting, common jar) are computed from `toString().getBytes().length`, effectively meaningless — only relevant if they jump to the audit pipeline.

---

## 7. Follow-up rabbit holes (+ crisp answers)

- **"Why not just expose GTIN in the API and skip UberKeys?"** Suppliers operate on WM item numbers; forcing GTIN shifts cognitive load and breaks existing consumer mental models. UberKeys is the canonical mapping, so we resolve server-side. Trade-off is an extra hop, handled with per-item error degradation.
- **"How would you cache DC inventory?"** I wouldn't aggressively — it's near-real-time warehouse stock; staleness misleads replenishment decisions. I'd cache the *authorization* and *item→GTIN* mappings (slow-changing) and add a very short (seconds) TTL on EI reads only if EI became a bottleneck, with explicit "as of" timestamps in the response (`lastUpdatedTime` already carries that).
- **"What partitions/keys EI by?"** EI is keyed by `nodeId` (the DC) and GTIN; our request is `node/{nodeId}/itemnumber` with the item list in the body — one node per call, many items.
- **"How do you version the API?"** Today via header-based service identity (`wm_svc.name`) and the spec's `x-api-id: nrt-apis:1.0`, not URL versioning. Breaking changes would mean a new spec version + consumer migration; non-breaking additions go straight into the spec first.
- **"What if two inventory types report the same state?"** They're separate `InventoryByInventoryType` entries (PROMO vs TURN), each with its own state list — we don't merge them, so the supplier can distinguish promo vs turn stock in the same state.
- **"Idempotency of the read under retries?"** Safe — pure read; at most a duplicate EI fetch. The retry isn't predicate-filtered, so I'd add `.filter(isRetryable)` to skip deterministic 4xx.
- **"How are secrets/keys handled for the EI call?"** Consumer IDs and signing keys come from CCM/Akeyless (`/etc/secrets/...`), not source; outbound signing uses `cp-data-apis-common` AuthSign; Istio enforces mTLS on egress.
- **"Why MapStruct in some flows but hand-mapping for DC?"** `EIInboundInventoryMapper` (MapStruct) is used for store-inbound; DC mapping is hand-written in `EIServiceHelper` because it involves filtering/correlating by `itemIdentifier` and accumulating errors — logic beyond a field-by-field mapping. Trade-off: more code vs. full control over partial-failure semantics.

---

## 8. One-paragraph + 30-second pitch

**One paragraph.** The DC Inventory Search API (`POST /dc/inventory/status` in `cp-nrti-apis`, Spring Boot 3.5 / Java 17) lets Walmart suppliers query current distribution-center inventory for their items. It's a contract-first design: the OpenAPI spec under `api-spec/` was agreed before implementation so consumer teams could generate clients and mocks and integrate in parallel — roughly a third less wall-clock to first integration. The request flows through a clean three-stage pipeline — an inbound filter/validation boundary (`RequestFilter`, `NrtiApiInterceptor`, bean validation), a fetch-and-authorize stage (`DcInventoryServiceImpl`: resolve supplier from Postgres, translate WM item numbers to GTINs via UberKeys, authorize against the supplier's globalDuns, then read Enterprise Inventory over a reactive WebClient with a 10s timeout and exponential-backoff retry), and a mapping stage (`EIServiceHelper` reshapes EI's inventory-by-type/state payload into a supplier-scoped response with per-item partial-error handling). Multi-site (US/CA/MX) is handled by deploying the same artifact per region with region-specific CCM config rather than a single-process factory. Every external hop is a Strati child transaction for tracing.

**30-second verbal.** "I worked on `cp-nrti-apis`, the supplier-facing inventory gateway, including its DC inventory search endpoint. It's OpenAPI design-first — we locked the contract up front so consumer teams built against generated clients and mocks in parallel, cutting integration wall-clock by about a third. A request runs through three stages: validate at the edge, then resolve and authorize the supplier and translate their item numbers to GTINs before reading Walmart's Enterprise Inventory over a reactive WebClient with timeout and retry, then map EI's promo/turn inventory-by-state into a clean supplier response with per-item partial errors. Multi-site US/CA/MX is done by deploying the same code per region with different CCM config. If you want, I'll be precise about where 'factory' is config-and-DI versus a true runtime factory, because I think that distinction matters."
