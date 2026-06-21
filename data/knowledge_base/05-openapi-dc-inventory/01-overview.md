# Overview - OpenAPI Design-First & DC Inventory API

> **Resume Bullets:** 5 (OpenAPI), 6 (DC Inventory), 8 (Authorization)
> **Repo:** `inventory-status-srv`

---

## The Problem

### Business Context

Suppliers (Pepsi, Coca-Cola, Unilever) need to query inventory across Walmart's **distribution centers (DCs)**. Before this API:

- No standardized way to check DC inventory
- Each supplier integration was custom
- No API contract for frontend/consumer teams to code against
- Suppliers couldn't see inventory breakdowns by type (on-hand, in-transit, etc.)

### What I Built

A **design-first REST API** for searching distribution center inventory status:

```
POST /inventory/search-distribution-center-status

Request: List of GTINs (product identifiers)
Response: Inventory at each DC broken down by type (on-hand, in-transit, reserved)
```

---

## Design-First Approach (Bullet 5)

### What Is Design-First?

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

### The Spec I Wrote (PR #260)

```
api-spec/
├── openapi_consolidated.json          # Full spec with all endpoints
├── examples/
│   ├── inventory_search_distribution_center_status_request.json
│   ├── inventory_search_distribution_center_status_response_200.json
│   ├── inventory_search_distribution_center_status_response_all_error_combination.json
│   └── inventory_search_distribution_center_status_response_success_error_combination.json
├── schema/
│   ├── common/
│   │   ├── inventory.json
│   │   ├── inventory_by_location_item.json
│   │   ├── inventory_by_state.json
│   │   └── inventory_item.json
│   └── dc_inventory/ (new schemas I created)
└── doc/
    └── userguide.md
```

### Interview Point
> "Design-first means I wrote the OpenAPI spec before any code. The spec defines request/response schemas, validation rules, error codes, and includes examples for every scenario - success, partial errors, and full errors. Consumers could start integration using the spec while I built the implementation. We validated implementation against spec using R2C (Request-to-Contract) testing."

---

## DC Inventory Implementation (Bullet 6)

### Architecture (gh verified from PR #271: 30 files changed)

```
Request Flow:

Supplier Request
    │
    ▼
InventorySearchDistributionCenterController
    │
    ▼
InventorySearchDistributionCenterService
    │
    ├── SiteConfigFactory.getConfig(siteId)
    │   ├── USConfig (US-specific settings)
    │   ├── CAConfig (Canada-specific settings)
    │   └── MXConfig (Mexico-specific settings)
    │
    ├── UberKeyReadService (Authorization key lookup)
    │
    ├── ServiceRequestBuilder (Build downstream request)
    │
    └── EIServiceHelper → External EI DC Inventory API
                           (Walmart's internal inventory system)
    │
    ▼
DCInventoryPayload → EIDCInventoryResponse
    │
    ▼
Response to Supplier
```

### Key Files (from repo tree)

```
src/main/java/com/walmart/inventory/
├── controller/
│   ├── InventorySearchDistributionCenterController.java
│   ├── InventorySearchDistributionCenterSandboxController.java
│   └── InventorySearchDistributionCenterSandboxIntlController.java
├── services/
│   ├── InventorySearchDistributionCenterService.java
│   ├── InventorySearchDistributionCenterSanboxService.java
│   ├── UberKeyReadService.java
│   ├── helpers/EIServiceHelper.java
│   └── builders/ServiceRequestBuilder.java
├── factory/
│   ├── SiteConfigFactory.java
│   └── impl/
│       ├── USConfig.java
│       ├── CAConfig.java
│       └── MXConfig.java
├── models/ei/dcinventory/
│   ├── DCInventoryPayload.java
│   ├── EIDCInventory.java
│   ├── EIDCInventoryByInventoryType.java
│   └── EIDCInventoryResponse.java
└── enums/
    └── InventoryType.java
```

---

## Supplier Authorization Framework (Bullet 8)

The same repo has the 4-level authorization hierarchy:

```
Consumer → DUNS → GTIN → Store

1. Consumer: API consumer (e.g., "PepsiCo Inc")
2. DUNS: Data Universal Numbering System - legal entity
3. GTIN: Global Trade Item Number - product identifier
4. Store: Individual store locations

Authorization check: Does this consumer → have this DUNS → for this GTIN → at this store?
Any "no" returns 403.
```

### Key Files

```
src/main/java/com/walmart/inventory/
├── entity/
│   ├── NrtiMultiSiteGtinStoreMapping.java
│   └── NrtiMultiSiteGtinStoreMappingKey.java
├── repository/
│   └── NrtiMultiSiteGtinStoreMappingRepository.java
└── services/
    ├── StoreGtinValidatorService.java
    └── impl/StoreGtinValidatorServiceImpl.java
```

---

## Production Timeline

```
Apr 22, 2025  │ PR #197: Cosmos to Postgres migration (database foundation)
Aug 19, 2025  │ PR #260: OpenAPI spec for DC inventory (+898 lines) ← DESIGN FIRST
Nov 11, 2025  │ PR #277: Bug fix (wm_item_nbr variable name)
Nov 20, 2025  │ PR #312: Fix DC inventory api spec (remove gtin from response)
Nov 21, 2025  │ PR #271: Full DC inventory implementation (+3,059 lines) ← MAIN PR
Nov 25, 2025  │ PR #322: Error handling refactor (+1,903 lines)
Jan 12, 2026  │ PR #330: GTIN-to-WmItemNumber error fix
Jan 13, 2026  │ PR #338: Container tests (+1,724 lines)
```

---

## What I Would Do Differently

1. **Write container tests EARLIER** - PR #338 came 2 months after implementation. Should've been part of PR #271.
2. **Include performance benchmarks in spec** - The spec defines functional behavior but not performance SLAs.
3. **Add request rate limiting** - Bulk endpoint with 100 items/request needs rate limiting to protect downstream EI API.

---

*Next: [02-openapi-design-first.md](./02-openapi-design-first.md) - Deep dive into design-first approach*
