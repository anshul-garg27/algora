# DSD Notification System - Complete Interview Guide (Bullet 3)

> **Resume Bullet:** "Developed a notification system for DSD suppliers, automating alerts to over 1,200 Walmart associates across 300+ store locations with a 35% improvement in stock replenishment timing"
> **Repo:** `cp-nrti-apis`
> **Key Service:** `SumoServiceImpl.java` (SUMO push notifications)
> **All code below is ACTUAL from the repo (gh verified)**

---

## Quick Navigation

| File | Purpose |
|------|---------|
| [01-overview.md](./01-overview.md) | Business context, architecture, data flow |
| [02-technical-implementation.md](./02-technical-implementation.md) | Actual code: SumoServiceImpl, DscServiceHelper, Kafka payload |
| [03-interview-qa.md](./03-interview-qa.md) | Q&A bank including the "35% measurement" answer |
| [04-how-to-speak-in-interview.md](./04-how-to-speak-in-interview.md) | Pitches, STAR story, pivots |

---

## 30-Second Pitch

> "I built real-time push notifications for Direct Store Delivery shipments. When a supplier like Pepsi delivers goods to a Walmart store, our system captures the shipment event, builds a Kafka message with delivery details, and sends a SUMO push notification to the store associate's device. The notification includes the vendor name, trailer number, and ETA window. Before this, associates discovered deliveries through periodic checks - hours of delay. After: real-time alerts. 1,200+ associates across 300+ stores."

---

## Key Numbers

| Metric | Value |
|--------|-------|
| Associates notified | **1,200+** |
| Store locations | **300+** |
| Replenishment improvement | **35%** |
| Notification events | **ENROUTE** and **ARRIVED** |
| DSD event types | 5 (Planned, Started, Enroute, Arrived, Completed) |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    DSD NOTIFICATION SYSTEM                                │
│                                                                          │
│  1. SUPPLIER sends shipment event                                       │
│     POST /nrt/v1/directShipmentCapture                                  │
│     ├── eventType: PLANNED | STARTED | ENROUTE | ARRIVED | COMPLETED   │
│     ├── vendorId, trailerNbr                                            │
│     ├── destinations: [{storeNbr, etaWindow}]                           │
│     └── shipmentInfo, loadInfo, packInfo                                │
│                                                                          │
│  2. NrtiStoreControllerV1 receives request                              │
│     ├── Validates request (DscServiceHelper)                            │
│     ├── Builds Kafka payload (DscKafkaMessage)                          │
│     └── Publishes to Kafka topic                                        │
│                                                                          │
│  3. SumoServiceImpl sends PUSH NOTIFICATION                             │
│     ├── Checks: Is eventType ENROUTE or ARRIVED?                        │
│     │   (Only these 2 out of 5 trigger notifications)                   │
│     ├── Builds notification body:                                       │
│     │   ENROUTE: "{vendor} {trailer} is enroute with ETA {start}-{end}"│
│     │   ARRIVED: "{vendor} {trailer} has arrived at store"             │
│     ├── Sets audience: Site → Domain(STORE) → Roles (from CCM)         │
│     └── Calls SUMO V3 Mobile Push API                                   │
│                                                                          │
│  4. Store associate receives notification on device                     │
│     └── Goes to dock, processes delivery                                │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Key Technical Decisions

| Decision | Why | Alternative |
|----------|-----|-------------|
| **SUMO Push** (not SMS/email) | Walmart's internal push platform for associate devices | SMS (expensive, no device targeting) |
| **Only ENROUTE + ARRIVED notify** | Other events (Planned, Started, Completed) don't require associate action | All events (notification fatigue) |
| **CCM-based role targeting** | Different stores may have different roles for receiving | Hardcoded roles |
| **Kafka for event persistence** | Durable record of all DSD events for audit trail | Direct SUMO call (no persistence) |
| **Commodity type mapping** | Different vendors deliver different types (food, non-food) | Generic notifications |
| **Feature flag (isSumoEnabled)** | Can disable notifications without deploy | Always-on (risky) |

---

## Key Files (from repo)

```
cp-nrti-apis/
├── controller/
│   └── NrtiStoreControllerV1.java        # Handles POST /directShipmentCapture
├── services/
│   ├── SumoService.java                   # Interface
│   ├── impl/SumoServiceImpl.java          # SUMO push notification logic
│   ├── helpers/DscServiceHelper.java      # Kafka payload builder + validation
│   ├── helpers/SumoHelper.java            # Notification title/body formatting
│   └── builders/SumoServiceRequestBuilder.java  # HTTP request to SUMO API
├── configs/
│   ├── DscApiCCMConfig.java               # DSD feature flags + commodity mappings
│   └── SumoApiCCMConfig.java              # SUMO API credentials + roles
├── models/
│   ├── enums/DscEventType.java            # PLANNED, STARTED, ENROUTE, ARRIVED, COMPLETED
│   ├── payloads/dsc/
│   │   ├── DscKafkaMessage.java           # Kafka event payload
│   │   ├── DscKafkaMessageHeader.java     # Event metadata
│   │   ├── DscKafkaMessagePayload.java    # Shipment data
│   │   ├── DscDestinationInfoPayload.java # Store destination info
│   │   ├── DscDriverPayload.java          # Driver details
│   │   ├── DscLoadInfoPayload.java        # Load/cargo info
│   │   ├── DscPackPayload.java            # Pack quantity info
│   │   └── DscShipmentEtaWindowPayload.java # ETA window
│   └── sumo/
│       ├── SumoRequest.java               # Push notification request
│       ├── Notification.java              # Title + body + customData
│       ├── Audience.java                  # List of Sites to notify
│       ├── Site.java                      # countryCode, domain, siteId, roles
│       ├── Domain.java                    # STORE, DC, HOME_OFFICE
│       └── CustomData.java                # Category metadata
├── requests/dsdshipment/
│   ├── DscRequest.java                    # Incoming API request
│   ├── DscDestinationInfo.java            # Store destination
│   ├── DscShipmentInfo.java               # Shipment details
│   └── DscDriver.java                     # Driver info
└── api-spec/
    ├── examples/dsc_request_200.json      # Request example
    ├── schema/requests/dsc_request.json   # Request schema
    └── schema/responses/dsc_api_response.json  # Response schema
```

---

## Your PRs Related to DSD

| PR# | Title | Lines | State | What |
|-----|-------|-------|-------|------|
| **#975** | OpenAPI spec migration for Direct Shipment Controller | +1,507/-949 | CLOSED (not merged) | Your design-first spec for DSD - shows initiative even though it wasn't merged |
| **#1233** | dscRequestValidator log updated | +1/-1 | CLOSED | Logging fix |

**Important Note:** While you don't have merged DSD-specific PRs, you WORK ON the cp-nrti-apis service daily which includes DSD. You understand the full codebase. PR #975 shows you attempted the OpenAPI migration for DSD (1,507 lines of work).

---

*Last Updated: February 2026*
