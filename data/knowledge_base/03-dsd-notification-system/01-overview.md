# Overview - DSD Notification System

> **DSD = Direct Store Delivery** - Suppliers deliver goods directly to stores (not through DCs)

---

## The Problem

### Before: Manual Discovery

```
Supplier (Pepsi) delivers goods to Store #4236 dock
    │
    ▼
Goods sit on dock... no one knows they arrived
    │
    ▼
Associate discovers delivery during periodic check (every 2-4 hours)
    │
    ▼
Goods shelved hours after arrival
    │
    ▼
Customers see empty shelves even though goods are in the store
```

**Pain points:**
- Associates didn't know deliveries arrived
- Periodic checks every 2-4 hours = delayed shelving
- Customer experience impacted (empty shelf when goods are on dock)
- Support team overhead coordinating deliveries

### After: Real-Time Notifications

```
Supplier (Pepsi) truck is ENROUTE to Store #4236
    │
    ▼
System sends SUMO push notification to associate's device:
"Pepsi TRL-4521 is enroute to your store with ETA between 2:00 PM and 3:00 PM"
    │
    ▼
Supplier truck ARRIVES at Store #4236
    │
    ▼
System sends another notification:
"Pepsi TRL-4521 has arrived at store"
    │
    ▼
Associate goes to dock immediately, processes delivery
    │
    ▼
Goods shelved within minutes of arrival
```

---

## How It Works (End-to-End Flow)

```
┌──────────────┐      ┌───────────────────┐      ┌──────────────────┐
│  Supplier     │      │   cp-nrti-apis    │      │   SUMO Platform  │
│  System       │      │   (Our Service)   │      │   (Walmart Push) │
│               │      │                   │      │                  │
│  POST /nrt/v1/│─────►│  1. Validate req  │      │                  │
│  directShip-  │      │  2. Build Kafka   │      │                  │
│  mentCapture  │      │     payload       │      │                  │
│               │      │  3. Publish to    │      │                  │
│  {eventType:  │      │     Kafka topic   │      │                  │
│   "ENROUTE",  │      │  4. Check: is     │      │                  │
│   vendorId,   │      │     ENROUTE or    │      │                  │
│   trailerNbr, │      │     ARRIVED?      │      │                  │
│   destinations│      │     YES ──────────┼─────►│  5. Route to     │
│   [{storeNbr, │      │                   │      │     Store domain │
│     etaWindow}│      │                   │      │  6. Filter by    │
│   ]}          │      │                   │      │     roles (CCM)  │
└──────────────┘      └───────────────────┘      │  7. Push to      │
                                                   │     device       │
                                                   └────────┬─────────┘
                                                            │
                                                            ▼
                                                   ┌──────────────────┐
                                                   │  Associate's     │
                                                   │  Device          │
                                                   │                  │
                                                   │  "Pepsi TRL-4521│
                                                   │   has arrived    │
                                                   │   at store"      │
                                                   └──────────────────┘
```

---

## DSD Event Lifecycle (5 States)

```
PLANNED → STARTED → ENROUTE → ARRIVED → COMPLETED
                      │           │
                      ▼           ▼
              SUMO Notification  SUMO Notification
              sent to store     sent to store
              associates        associates
```

Only **ENROUTE** and **ARRIVED** trigger notifications. Why?

| Event | Associate Action Needed? | Notification? |
|-------|------------------------|---------------|
| **PLANNED** | No - delivery is scheduled | No |
| **STARTED** | No - truck is loading | No |
| **ENROUTE** | Yes - prepare for arrival | **YES** - "ETA between X and Y" |
| **ARRIVED** | Yes - go to dock now | **YES** - "has arrived at store" |
| **COMPLETED** | No - already processed | No |

**Interview Point:**
> "We only notify on ENROUTE and ARRIVED because those are the two states where associates need to take action. Notifying on all 5 states would cause notification fatigue - associates would stop paying attention."

---

## SUMO Push Notification Structure

### How SUMO Targeting Works

```
SumoRequest:
├── notification:
│   ├── title: "DSD Shipment Update"
│   ├── body: "Pepsi TRL-4521 is enroute to your store with ETA 2:00 PM - 3:00 PM"
│   └── customData: {category: "DSD_SHIPMENT"}
│
└── audience:
    └── sites:
        └── Site:
            ├── countryCode: "US"
            ├── domain: STORE         ← Only store associates, not DC or HO
            ├── siteId: 4236          ← Specific store number
            └── roles: ["role1", "role2"]  ← From CCM config (receiving team)
```

**Key design:** SUMO routes notifications by `domain` + `siteId` + `roles`. This ensures:
- Only STORE associates get notified (not DC or Home Office)
- Only the SPECIFIC store where delivery is happening
- Only associates with the RIGHT ROLE (receiving team, not checkout)

---

## Commodity Type Mapping

Different vendors deliver different types of goods. The notification mentions the commodity type:

```java
// From DscServiceHelper
String commodityTypeValue = commodityTypeMappings.getOrDefault(
    dscRequest.getVendorId(), DSC_DEFAULT_COMMODITY_TYPE);

// Examples:
// vendorId: "PEPSI-001" → "Beverage"
// vendorId: "FRITO-LAY" → "Snacks"
// vendorId: "UNKNOWN"   → "DSD" (default)
```

**Notification examples:**
- ENROUTE: "**Beverage** TRL-4521 is enroute to your store with ETA between 2:00 PM and 3:00 PM"
- ARRIVED: "**Snacks** TRL-8903 has arrived at store"

**Interview Point:**
> "The commodity type mapping is CCM-configurable. Adding a new vendor-to-commodity mapping doesn't require code changes or redeployment. This is important because Walmart onboards new DSD suppliers frequently."

---

## The 35% Improvement - How It Was Measured

> "We measured replenishment timing as the gap between the DSD shipment arrival event (when we receive the ARRIVED event via API) and the inventory scan event (when the associate scans items into the system). Before SUMO notifications, this gap averaged several hours because associates discovered deliveries during periodic checks. After implementing real-time push notifications, associates responded within minutes. The 35% represents the reduction in this end-to-end replenishment lag, tracked through timestamps in our transaction event history."

### If They Push: "35% of what exactly?"

> "35% reduction in the time between goods arriving at the store dock and goods being scanned into inventory. Before: average lag was X hours because of periodic checks. After: significantly shorter because of real-time alerts. The business team measured this using operational timestamps - the ARRIVED event time versus the first inventory scan for those items."

### If They Push More: "Who measured this?"

> "The business operations team tracks replenishment KPIs. My contribution was the technical implementation - the notification pipeline from supplier API call to associate device. The 35% metric came from their operational dashboard comparing before and after notification deployment."

---

## Connections to Other Projects

| Connection | How They Relate |
|-----------|----------------|
| **Audit Logging (Bullet 1)** | DSD API endpoints are audited by the common library. Suppliers can query their DSD API interactions in BigQuery. |
| **Kafka** | DSD events are published to Kafka for persistence and downstream consumers |
| **OpenAPI (Bullet 5)** | You wrote the OpenAPI spec migration for DSD controller (PR #975, 1,507 lines) - even though it wasn't merged, it shows initiative |
| **Spring Boot 3 (Bullet 4)** | DSD runs on cp-nrti-apis which you migrated to Spring Boot 3 |

---

*Next: [02-technical-implementation.md](./02-technical-implementation.md) - Actual code walkthrough*
