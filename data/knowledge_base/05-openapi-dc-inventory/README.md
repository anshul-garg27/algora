# OpenAPI Design-First & DC Inventory API - Complete Interview Guide

> **Resume Bullets Covered:** 5 (OpenAPI Design-First), 6 (DC Inventory with CompletableFuture), 8 (Supplier Authorization)
> **Repo:** `inventory-status-srv` (291 PRs total)
> **Your Key PRs:** #260, #271, #277, #312, #322, #330, #338, #197

---

## Quick Navigation

| File | Purpose |
|------|---------|
| [01-overview.md](./01-overview.md) | What DC Inventory API does, architecture, design-first approach |
| [02-openapi-design-first.md](./02-openapi-design-first.md) | Bullet 5: How design-first works, api-spec structure |
| [03-dc-inventory-implementation.md](./03-dc-inventory-implementation.md) | Bullet 6: Controller, service, factory pattern, multi-site |
| [04-technical-decisions-deep-dive.md](./04-technical-decisions-deep-dive.md) | "Why THIS not THAT?" for every technical choice (10 decisions) |
| [05-interview-qa.md](./05-interview-qa.md) | Q&A bank with model answers |
| [06-how-to-speak-in-interview.md](./06-how-to-speak-in-interview.md) | HOW to talk about this project |
| [07-prs-reference.md](./07-prs-reference.md) | Your 8 PRs with timeline (gh verified) |
| **[08-scenario-what-if-questions.md](./08-scenario-what-if-questions.md)** | **"What if EI down? UberKey fails? Cache stale?" - 10 scenarios** |

---

## 30-Second Pitch

> "I designed and built the DC Inventory Search API from spec to production. I started with OpenAPI design-first - writing the spec before any code, so consumer teams could start integration immediately. The API lets suppliers query inventory across multiple distribution centers with bulk support (up to 100 items per request). I used a factory pattern for multi-site support (US/CA/MX) and built comprehensive error handling with a centralized RequestProcessor for partial success scenarios. The spec-first approach reduced integration time by 30%."

---

## Key Numbers to Memorize

| Metric | Value | Source |
|--------|-------|--------|
| API spec PR | **+898 lines** | PR #260 (gh verified) |
| Implementation PR | **+3,059 lines** | PR #271 (gh verified) |
| Error handling refactor | **+1,903 lines** | PR #322 (gh verified) |
| Container tests | **+1,724 lines** | PR #338 (gh verified) |
| Total your code | **~8,000+ lines** | PRs #260-338 combined |
| Integration time reduction | **30%** | Design-first approach |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     DC INVENTORY SEARCH API                                  │
│                                                                              │
│  LAYER 1: API SPEC (Design-First)                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  api-spec/openapi_consolidated.json                                 │    │
│  │  ├── /search-distribution-center-status endpoint                    │    │
│  │  ├── Request/Response schemas                                       │    │
│  │  ├── Error examples (400, 401, 404, 500)                           │    │
│  │  └── openapi-generator → Server stubs + Client SDKs                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  LAYER 2: CONTROLLER                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  InventorySearchDistributionCenterController.java (Production)      │    │
│  │  InventorySearchDistributionCenterSandboxController.java (Sandbox)  │    │
│  │  InventorySearchDistributionCenterSandboxIntlController.java (Intl) │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  LAYER 3: SERVICE + FACTORY                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  InventorySearchDistributionCenterService.java                      │    │
│  │  ├── SiteConfigFactory → USConfig / CAConfig / MXConfig             │    │
│  │  ├── EIServiceHelper (calls external EI DC Inventory API)           │    │
│  │  ├── UberKeyReadService (authorization key lookup)                  │    │
│  │  └── ServiceRequestBuilder (builds downstream requests)             │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  LAYER 4: MODELS                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  DCInventoryPayload.java                                            │    │
│  │  EIDCInventory.java                                                 │    │
│  │  EIDCInventoryByInventoryType.java                                  │    │
│  │  EIDCInventoryResponse.java                                         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  LAYER 5: AUTHORIZATION (Bullet 8)                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  NrtiMultiSiteGtinStoreMapping.java (Consumer→DUNS→GTIN→Store)     │    │
│  │  StoreGtinValidatorService.java (4-level auth check)                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Your PRs (gh Verified)

| PR# | Title | Lines | Merged | What You Did |
|-----|-------|-------|--------|-------------|
| **#260** | DC inventory API spec | +898/-9 | Aug 19, 2025 | **Design-first: wrote OpenAPI spec with schemas and examples** |
| **#271** | DC inventory development | +3,059/-540 | Nov 21, 2025 | **Full implementation: controllers, services, factory, tests** |
| **#277** | wm_item_nbr fix | minor | Nov 11, 2025 | Variable name bug fix |
| **#312** | Fix DC inventory api spec | -26 | Nov 20, 2025 | Removed gtin from response (spec update) |
| **#322** | Error handling DC inv | +1,903/-376 | Nov 25, 2025 | **Major refactor: RequestProcessor, bulk validation, JUnit 5** |
| **#330** | DC inv error fix | +171/-10 | Jan 12, 2026 | GTIN-to-WmItemNumber conversion error handling |
| **#338** | Container test | +1,724/-16 | Jan 13, 2026 | **WireMock, Docker compose, SQL test data** |
| **#197** | Cosmos to Postgres | Merged | Apr 22, 2025 | Database migration for inventory-status-srv |

---

## Technology Decisions

| Decision | Why | Alternative |
|----------|-----|-------------|
| **OpenAPI Design-First** | Consumers start integration before code is ready | Code-first (spec after code) |
| **Factory Pattern** (SiteConfigFactory) | Multi-site US/CA/MX with different configs | If-else chains (unmaintainable) |
| **RequestProcessor** | Centralized validation + error handling | Scattered validation in controllers |
| **Container Tests** | Full integration with WireMock + PostgreSQL | Unit tests only (miss integration bugs) |
| **R2C Contract Testing** | Ensure implementation matches spec | Manual testing (error-prone) |

---

## Files in This Folder

```
05-openapi-dc-inventory/
├── README.md                           # This file
├── 01-overview.md                      # System overview, architecture
├── 02-openapi-design-first.md          # Design-first approach (Bullet 5)
├── 03-dc-inventory-implementation.md   # Implementation (Bullet 6)
├── 04-error-handling-and-testing.md    # Error handling + tests
├── 05-interview-qa.md                  # Q&A bank
└── 06-how-to-speak-in-interview.md     # HOW to speak
```

---

*Last Updated: February 2026*
