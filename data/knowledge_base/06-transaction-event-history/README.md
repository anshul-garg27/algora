# Transaction Event History API (Bullet 7)

> **Resume Bullet:** 7 - Transaction Event History API with cursor-based pagination
> **Repo:** `inventory-events-srv` (123 PRs total)
> **Your Key PRs:** #80-92 (Cosmos to Postgres migration)
> **Key PRs:** #8 (+11,667 lines), #38 (+11,950 lines - CRQ production), #80 (+529 - your Cosmos→Postgres)

---

## 30-Second Pitch

> "I worked on the Transaction Event History API that lets suppliers query their historical transaction data. The API supports cursor-based pagination for efficient traversal of millions of records. I led the Cosmos to PostgreSQL database migration for this service - which involved migrating the persistence layer, fixing codegate issues, and deploying with zero downtime. The service handles multi-tenant data with site-based partitioning for US, Canada, and Mexico."

---

## What This API Does

```
GET /inventory/transactionHistory?pageToken=xxx&siteId=US

Input:  Supplier credentials, site ID, optional filters
Output: Paginated transaction events (shipments, receipts, adjustments)
        with cursor-based pagination token for next page
```

---

## Key Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                  TRANSACTION EVENT HISTORY API                     │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  InventoryEventsController.java                             │  │
│  │  ├── GET /inventory/transactionHistory                      │  │
│  │  ├── Cursor-based pagination (pageToken)                    │  │
│  │  └── Multi-tenant (US, CA, MX via siteId)                  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                              │                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Services                                                   │  │
│  │  ├── InventoryStoreService                                  │  │
│  │  ├── SupplierMappingService                                 │  │
│  │  ├── StoreGtinValidatorService                              │  │
│  │  └── HttpService (downstream calls)                         │  │
│  └────────────────────────────────────────────────────────────┘  │
│                              │                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Database: PostgreSQL (migrated from Cosmos DB)             │  │
│  │  ├── Site-based partitioning (US, CA, MX)                   │  │
│  │  └── Cursor-based queries (WHERE created_ts > last_seen)    │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Key Technical Concepts

### 1. Cursor-Based Pagination (vs Offset)

```
OFFSET PAGINATION (Bad for large datasets):
  Page 1: SELECT * FROM events LIMIT 10 OFFSET 0     ← Fast
  Page 5: SELECT * FROM events LIMIT 10 OFFSET 40    ← OK
  Page 100: SELECT * FROM events LIMIT 10 OFFSET 990 ← SLOW! DB scans 990 rows

CURSOR PAGINATION (What we use):
  Page 1: SELECT * FROM events WHERE created_ts > '0' LIMIT 10
  Page 2: SELECT * FROM events WHERE created_ts > '2025-01-15T10:30:00' LIMIT 10
  Page N: Always fast! Uses index, doesn't scan previous rows
```

**Interview Point:**
> "Cursor pagination keeps response times constant regardless of how deep you page. With millions of transaction events, offset pagination would get progressively slower. The pageToken encodes the last seen timestamp as a bookmark."

### 2. Multi-Tenancy (Site-Based Partitioning)

```
Each request includes siteId (US, CA, MX):
├── PostgreSQL tables partitioned by site
├── Queries include partition key
├── Data isolation: CA suppliers can't see US data
└── Performance: partition pruning
```

### 3. Cosmos to PostgreSQL Migration (Your PR #80)

**Why migrate?**
- Cosmos pricing based on RUs (Request Units) - unpredictable costs
- PostgreSQL on WCNP has predictable costs
- Better operational expertise with PostgreSQL

**Your Work (PRs #80-92):**

| PR# | Title | Lines | Merged |
|-----|-------|-------|--------|
| **#80** | Cosmos to postgres migration | +529/-333 | May 28, 2025 |
| **#83** | Code gate issue resolved | +1/-0 | May 28, 2025 |
| **#85** | Codegate issue fixed | +4/-4 | May 29, 2025 |
| **#86** | Codegate issue fixed | +9/-21 | May 29, 2025 |
| **#87** | Codegate issue fixed stage | +535/-350 | May 30, 2025 |
| **#89-92** | Non-prod CCM changes | Config | Jun 2, 2025 |

---

## Key Files (from repo tree)

```
inventory-events-srv/
├── controller/
│   ├── InventoryEventsController.java
│   ├── InventoryEventsSandboxController.java
│   └── InventoryEventsSandboxIntlController.java
├── services/
│   ├── HttpService.java
│   ├── InventoryStoreService.java
│   ├── StoreGtinValidatorService.java
│   ├── SupplierMappingService.java
│   └── builders/ServiceRequestBuilder.java
├── models/ei/
│   ├── TransactionDocument.java
│   ├── TransactionEventHistory.java
│   └── TransactionHistoryPayload.java
├── common/config/postgres/
│   └── PostgresDbConfiguration.java
└── enums/
    ├── InventoryEventCSVHeader.java
    └── InventoryEventType.java
```

---

## Interview Questions

### Q: "Why cursor pagination instead of offset?"
> "Offset pagination like LIMIT 10 OFFSET 1000 is expensive for large datasets - the database has to scan all 1000 rows before returning the next 10. Cursor pagination uses a bookmark like WHERE created_ts > last_seen_ts, which hits an index directly. For our transaction history with millions of events, cursor pagination keeps response times constant regardless of how deep you page."

### Q: "Why migrate from Cosmos to PostgreSQL?"
> "Three reasons: unpredictable costs (Cosmos charges per RU which fluctuates), operational simplicity (better PostgreSQL expertise on the team), and compatibility (our other services already use PostgreSQL on WCNP). I led the migration - changed the persistence layer, fixed codegate issues over 5 PRs, and deployed with zero downtime."

### Q: "How do you handle multi-tenancy?"
> "Site-based partitioning. Each request includes a siteId (US, CA, MX). PostgreSQL tables are partitioned by site. Queries include the partition key, so Canadian suppliers can't accidentally query US data. Partition pruning also gives us performance benefits."

### Q: "What challenges did you face with the Cosmos to Postgres migration?"
> "Codegate issues were the biggest challenge. After the initial migration PR, I had 4 follow-up PRs fixing codegate problems - these are Walmart's automated code quality and security gates. The fixes involved adjusting configurations for stage and prod environments. The migration itself went smoothly because I kept the API contract identical - only the persistence layer changed."

---

## STAR Story: Cosmos to Postgres Migration

**Situation:** "Transaction Event History API was using Cosmos DB with unpredictable RU-based pricing."

**Task:** "I led the migration to PostgreSQL to reduce costs and improve operational simplicity."

**Action:**
- Migrated persistence layer from Cosmos to PostgreSQL (+529/-333 lines)
- Fixed codegate issues across 4 follow-up PRs
- Updated CCM configurations for all environments
- Ensured API contract remained identical (zero consumer impact)

**Result:** "Zero-downtime migration, predictable costs, better operational support. The CA launch later (PR #96) built on this PostgreSQL foundation."

---

## Connections to Other Projects

- **Audit Logging (Bullet 1):** Transaction events are one of the endpoints audited by the common library
- **Authorization (Bullet 8):** Uses the same StoreGtinValidatorService for supplier authorization
- **OpenAPI (Bullet 5):** api-spec folder with openapi_consolidated.json, same design-first approach

---

*This is a supporting story - use it when you need to show database migration experience or pagination knowledge.*
