# PRs Reference - DSD Notification System

---

## Your DSD-Related PRs

| PR# | Title | Lines | State | What |
|-----|-------|-------|-------|------|
| **#975** | OpenAPI spec migration for Direct Shipment Controller | +1,507/-949 | CLOSED | Design-first spec for DSD (shows initiative) |
| **#1233** | dscRequestValidator log updated | +1/-1 | CLOSED | Logging fix |

> **Note:** Your main DSD contributions are through working on cp-nrti-apis daily (which includes DSD), the Spring Boot 3 migration (which migrated DSD code too), and the audit logging library (which audits DSD API calls).

---

## Key DSD PRs in cp-nrti-apis (Team PRs - gh verified)

| PR# | Title | Lines | Merged | What Changed |
|-----|-------|-------|--------|-------------|
| **#902** | DSC caching changes | +68 | Aug 2024 | CCM caching for DSD config |
| **#919** | DSC store timezone + caching | +1,464/-201 | Aug 2024 | **MAJOR: Timezone-aware notifications** |
| **#1085** | DSC Sumo roles changes | +3/-43 | Oct 2024 | Updated SUMO role targeting |
| **#1140** | PalletQty and CaseQty | +133/-2 | Jan 2025 | Added pallet/case quantity to payload |
| **#1179** | Pallet qty change | +22/-9 | Jan 2025 | Pallet quantity totalling |
| **#1397** | Driver ID to DSC request | +373/-3 | Jun 2025 | **Added driver info to Kafka payload** |
| **#1405-1417** | packNbrQty to payload | +16/-6 | Jun-Jul 2025 | Pack number quantity |
| **#1433-1446** | isDockRequired field | +24/-4 | Sep 2025 | **Dock availability in request** |
| **#1514** | Dock required to main | +12/-2 | Sep 2025 | Production deployment |
| **#1548** | Event type changes | +141/-6 | Oct 2025 | Completed event type enhancements |

---

## Timeline

```
Aug 2024  │ DSC caching + timezone-aware notifications (#902, #919)
Oct 2024  │ SUMO roles update (#1085)
Jan 2025  │ Pallet/case quantity (#1140, #1179)
Jun 2025  │ Driver ID added to payload (#1397)
Jul 2025  │ Pack number quantity (#1405-1417)
Sep 2025  │ isDockRequired field (#1433-1514)
Oct 2025  │ Event type changes (#1548)
Nov 2025  │ API spec changes (#1571)
```

---

## Key Observation for Interview

The DSD system evolved significantly over time - new fields added to Kafka payload (driverId, packNbrQty, isDockRequired), role targeting updates, timezone improvements. This shows an actively maintained, evolving system - not a one-time build.

---

*DSD is a supporting story. Use these PRs only if they ask for specific evolution details.*
