# DSD Notification System -- Interview Prep

> **Resume Bullet:** "Developed a notification system for DSD suppliers, automating alerts to over 1,200 Walmart associates across 300+ store locations with a 35% improvement in stock replenishment timing"
> **Repo:** `cp-nrti-apis` | **Key Service:** `SumoServiceImpl.java`

---

## Your Pitch

> "I built real-time push notifications for DSD shipments. When a supplier delivers to a store, SUMO push alerts go to the receiving team's devices with the vendor name, trailer number, and ETA. Only ENROUTE and ARRIVED events trigger notifications -- we deliberately filter the other three event types to avoid fatigue. 1,200+ associates across 300+ stores, 35% improvement in replenishment timing."

---

## Key Numbers

| Metric | Value |
|--------|-------|
| Associates notified | **1,200+** |
| Store locations | **300+** |
| Replenishment improvement | **35%** |
| Notification events | **ENROUTE** and **ARRIVED** |
| DSD event types | 5 (Planned, Started, Enroute, Arrived, Completed) |
| Notification latency | **<5 seconds** from API call to associate device |

---

## Architecture

### System Overview

```
+-------------------------------------------------------------------------+
|                    DSD NOTIFICATION SYSTEM                               |
|                                                                         |
|  1. SUPPLIER sends shipment event                                       |
|     POST /nrt/v1/directShipmentCapture                                  |
|     +-- eventType: PLANNED | STARTED | ENROUTE | ARRIVED | COMPLETED   |
|     +-- vendorId, trailerNbr                                            |
|     +-- destinations: [{storeNbr, etaWindow}]                           |
|     +-- shipmentInfo, loadInfo, packInfo                                |
|                                                                         |
|  2. NrtiStoreControllerV1 receives request                              |
|     +-- Validates request (DscServiceHelper)                            |
|     +-- Builds Kafka payload (DscKafkaMessage)                          |
|     +-- Publishes to Kafka topic                                        |
|                                                                         |
|  3. SumoServiceImpl sends PUSH NOTIFICATION                             |
|     +-- Checks: Is eventType ENROUTE or ARRIVED?                        |
|     |   (Only these 2 out of 5 trigger notifications)                   |
|     +-- Builds notification body:                                       |
|     |   ENROUTE: "{vendor} {trailer} is enroute with ETA {start}-{end}" |
|     |   ARRIVED: "{vendor} {trailer} has arrived at store"              |
|     +-- Sets audience: Site -> Domain(STORE) -> Roles (from CCM)        |
|     +-- Calls SUMO V3 Mobile Push API                                   |
|                                                                         |
|  4. Store associate receives notification on device                     |
|     +-- Goes to dock, processes delivery                                |
+-------------------------------------------------------------------------+
```

### End-to-End Data Flow

```
+--------------+      +-------------------+      +------------------+
|  Supplier     |      |   cp-nrti-apis    |      |   SUMO Platform  |
|  System       |      |   (Our Service)   |      |   (Walmart Push) |
|               |      |                   |      |                  |
|  POST /nrt/v1/|----->|  1. Validate req  |      |                  |
|  directShip-  |      |  2. Build Kafka   |      |                  |
|  mentCapture  |      |     payload       |      |                  |
|               |      |  3. Publish to    |      |                  |
|  {eventType:  |      |     Kafka topic   |      |                  |
|   "ENROUTE",  |      |  4. Check: is     |      |                  |
|   vendorId,   |      |     ENROUTE or    |      |                  |
|   trailerNbr, |      |     ARRIVED?      |      |                  |
|   destinations|      |     YES ----------|----->|  5. Route to     |
|   [{storeNbr, |      |                   |      |     Store domain |
|     etaWindow}|      |                   |      |  6. Filter by    |
|   ]}          |      |                   |      |     roles (CCM)  |
+--------------+      +-------------------+      |  7. Push to      |
                                                  |     device       |
                                                  +--------+---------+
                                                           |
                                                           v
                                                  +------------------+
                                                  |  Associate's     |
                                                  |  Device          |
                                                  |                  |
                                                  |  "Pepsi TRL-4521 |
                                                  |   has arrived    |
                                                  |   at store"      |
                                                  +------------------+
```

### The Problem and Solution

**Before (Manual Discovery):**
```
Supplier (Pepsi) delivers goods to Store #4236 dock
    |
    v
Goods sit on dock... no one knows they arrived
    |
    v
Associate discovers delivery during periodic check (every 2-4 hours)
    |
    v
Goods shelved hours after arrival
    |
    v
Customers see empty shelves even though goods are in the store
```

**After (Real-Time Notifications):**
```
Supplier (Pepsi) truck is ENROUTE to Store #4236
    |
    v
System sends SUMO push notification to associate's device:
"Pepsi TRL-4521 is enroute to your store with ETA between 2:00 PM and 3:00 PM"
    |
    v
Supplier truck ARRIVES at Store #4236
    |
    v
System sends another notification:
"Pepsi TRL-4521 has arrived at store"
    |
    v
Associate goes to dock immediately, processes delivery
    |
    v
Goods shelved within minutes of arrival
```

### DSD Event Lifecycle (5 States)

```
PLANNED -> STARTED -> ENROUTE -> ARRIVED -> COMPLETED
                        |           |
                        v           v
                SUMO Notification  SUMO Notification
                sent to store     sent to store
                associates        associates
```

| Event | Associate Action Needed? | Notification? |
|-------|------------------------|---------------|
| **PLANNED** | No - delivery is scheduled | No |
| **STARTED** | No - truck is loading | No |
| **ENROUTE** | Yes - prepare for arrival | **YES** - "ETA between X and Y" |
| **ARRIVED** | Yes - go to dock now | **YES** - "has arrived at store" |
| **COMPLETED** | No - already processed | No |

### SUMO Push Notification Structure

```
SumoRequest:
+-- notification:
|   +-- title: "DSD Shipment Update"
|   +-- body: "Pepsi TRL-4521 is enroute to your store with ETA 2:00 PM - 3:00 PM"
|   +-- customData: {category: "DSD_SHIPMENT"}
|
+-- audience:
    +-- sites:
        +-- Site:
            +-- countryCode: "US"
            +-- domain: STORE         <-- Only store associates, not DC or HO
            +-- siteId: 4236          <-- Specific store number
            +-- roles: ["role1", "role2"]  <-- From CCM config (receiving team)
```

**Targeting ensures:**
- Only STORE associates get notified (not DC or Home Office)
- Only the SPECIFIC store where delivery is happening
- Only associates with the RIGHT ROLE (receiving team, not checkout)

---

## Technical Implementation

### SumoServiceImpl.java -- The Core Notification Logic

```java
@Slf4j
@Service
public class SumoServiceImpl implements SumoService {
  private final HttpServiceImpl httpService;
  private final SumoServiceRequestBuilder sumoServiceRequestBuilder;

  @ManagedConfiguration
  NrtFeatureFlagCCMConfig featureFlagCCMConfig;  // Feature flag

  @ManagedConfiguration
  DscApiCCMConfig dscApiCCMConfig;  // Commodity type mappings

  @Override
  public void sendSumoNotification(String vendorName, DscRequest dscRequest) {

    // CHECK 1: Is SUMO enabled? (Feature flag)
    if (Boolean.FALSE.equals(featureFlagCCMConfig.isSumoEnabled())) {
      log.info("Sumo Notification is disabled");
      return;
    }

    // CHECK 2: Is this event type one that needs notification?
    // Only ENROUTE and ARRIVED trigger notifications
    if (!SUMO_NOTIFICATION_ENABLER.contains(dscRequest.getEventType())) {
      log.info("No Notification Required for eventType {}",
          dscRequest.getEventType());
      return;
    }

    // Get commodity type for this vendor (e.g., "Beverage", "Snacks")
    var commodityTypeMappings = getVendorCommodityMap(
        dscApiCCMConfig.getCommodityTypeMappings());
    String commodityTypeVendorName = commodityTypeMappings
        .getOrDefault(dscRequest.getVendorId(), DSC_DEFAULT_COMMODITY_TYPE);

    switch (dscRequest.getEventType()) {
      case ENROUTE:
        // For each destination store, send notification with ETA
        dscRequest.getDestinations().forEach(destination -> {
          SumoRequest sumoRequest =
              sumoServiceRequestBuilder.getSumoRequest(destination);
          var etaWindow = destination.getEtaWindow();
          String body = MessageFormat.format(
              "{0} {1} is enroute to your store with an ETA between {2} and {3}",
              commodityTypeVendorName,
              StringUtils.defaultIfBlank(dscRequest.getTrailerNbr(), ""),
              SumoHelper.getAmPmFromTimeZone(etaWindow.getEarliestEta()),
              SumoHelper.getAmPmFromTimeZone(etaWindow.getLatestEta()));
          SumoHelper.setTitleAndBody(sumoRequest, eventType, body);
          sendSumoNotification(sumoRequest, dscRequest.getMessageId());
        });
        break;

      case ARRIVED:
        // For each destination store, send arrival notification
        dscRequest.getDestinations().forEach(destination -> {
          SumoRequest sumoRequest =
              sumoServiceRequestBuilder.getSumoRequest(destination);
          String body = MessageFormat.format(
              "{0} {1} has arrived at store",
              commodityTypeVendorName,
              StringUtils.defaultIfBlank(dscRequest.getTrailerNbr(), ""));
          SumoHelper.setTitleAndBody(sumoRequest, eventType, body);
          sendSumoNotification(sumoRequest, dscRequest.getMessageId());
        });
        break;
    }
  }

  // Sends the actual SUMO API call with error handling
  private void sendSumoNotification(SumoRequest sumoRequest, String correlationId) {
    try {
      this.sumoPushApi(sumoRequest, correlationId);
    } catch (SignatureHandleException e) {
      log.error("failed to publish notification with {}", correlationId);
    }
  }

  // HTTP call to SUMO V3 Mobile Push API
  public SumoResponse sumoPushApi(SumoRequest sumoRequest, String correlationId) {
    ResponseEntity<SumoResponse> response = httpService.sendHttpRequest(
        sumoServiceRequestBuilder.createSumoPushUri(),
        HttpMethod.POST,
        new HttpEntity<>(
            sumoServiceRequestBuilder.createSumoRequestJsonNode(sumoRequest),
            sumoServiceRequestBuilder.getSumoHttpRequestHeaders(correlationId)),
        SumoResponse.class);

    SumoHelper.handleSumoResponse(response);
    return response.getBody();
  }
}
```

**Key Design Points:**
1. **Feature Flag First** -- `isSumoEnabled()` check before any processing. Can disable notifications at runtime via CCM.
2. **Event Type Filtering** -- `SUMO_NOTIFICATION_ENABLER = List.of(ENROUTE, ARRIVED)` - only 2 of 5 events trigger notifications.
3. **Per-Destination Loop** -- One shipment can go to multiple stores. Each store gets its own notification.
4. **Commodity Type Mapping** -- Vendor-specific notification text ("Beverage" vs "Snacks" vs "DSD").
5. **ETA Window Formatting** -- `SumoHelper.getAmPmFromTimeZone()` converts UTC timestamps to store-local AM/PM format.

### DscEventType.java -- Event Type Enum

```java
public enum DscEventType {
  PLANNED("Planned"),
  STARTED("Started"),
  ENROUTE("Enroute"),
  ARRIVED("Arrived"),
  COMPLETED("Completed");

  // ONLY these 2 trigger SUMO notifications
  public static final List<DscEventType> SUMO_NOTIFICATION_ENABLER =
      List.of(ENROUTE, ARRIVED);
}
```

> "The SUMO_NOTIFICATION_ENABLER list is defined as a constant IN the enum. Adding a new notification-triggering event is one line change -- add it to this list. No switch statement changes needed."

### SUMO Models (Notification Targeting)

```java
// Who gets notified
@Data @Builder
public class SumoRequest {
  private Notification notification;  // What to say
  private Audience audience;          // Who to tell
}

// What the notification says
@Data @Builder
public class Notification {
  private String title;       // "DSD Shipment Update"
  private String body;        // "Pepsi TRL-4521 has arrived at store"
  private CustomData customData;  // {category: "DSD_SHIPMENT"}
}

// Who gets the notification (targeting)
@Data @Builder
public class Audience {
  private List<Site> sites;   // List of stores to notify
}

// Specific store targeting
@Data @Builder
public class Site {
  private String countryCode;   // "US"
  private Domain domain;        // STORE (not DC, not HOME_OFFICE)
  private Integer siteId;       // 4236 (store number)
  private List<String> roles;   // ["receiving_team"] from CCM
}

// Domain = who in the organization
public enum Domain {
  STORE("store"),       // Store associates (who we notify)
  DC("dc"),             // Distribution center
  HOME_OFFICE("homeoffice"),
  CANDIDATE("candidate");
}
```

> "The targeting model is hierarchical: Audience -> Sites -> Site with countryCode + domain + siteId + roles. This ensures notifications reach ONLY the receiving team at the SPECIFIC store. A store in Texas doesn't get notifications for a delivery to a store in California."

### SUMO API Configuration (CCM-Based)

```java
@Configuration(configName = "SUMO_API_CONFIG")
public interface SumoApiCCMConfig {
  String getWmConsumerId();       // API authentication
  String getWmAppUUID();          // SUMO app identifier
  String getUriScheme();          // "https"
  String getHost();               // SUMO API host
  String getV3MobilePushUriPath(); // "/v3/mobile/push"
  String getSumoPrivateKeyPath(); // Signing key
  Integer getKeyVersion();        // Key version
  Integer getTTL();               // Notification TTL
  List<String> getStoreRoles();   // Roles to notify (CCM configurable!)
}
```

> "The store roles are CCM-configurable. If a store reorganizes and the receiving team role name changes, we update CCM -- no code change, no redeployment."

### Kafka Payload (Event Persistence)

```java
// Built by DscServiceHelper.prepareDscKafkaPayload()
DscKafkaMessage.builder()
    .dscKafkaMessageHeader(DscKafkaMessageHeader.builder()
        .eventType(dscRequest.getEventType().toString())
        .msgTimestamp(formattedTimestamp)
        .eventCreationTime(dscRequest.getEventCreationTime())
        .vendorId(dscRequest.getVendorId())
        .tripId(buildTripId(dscRequest))
        .vendorName(vendorName)
        .commodityType(commodityTypeValue)
        .build())
    .dscKafkaMessagePayload(DscKafkaMessagePayload.builder()
        .destinations(destinations)
        .shipmentInfo(shipmentInfo)
        .loadInfo(loadInfo)
        .build())
    .build();
```

**Why Kafka alongside SUMO?**
- SUMO is fire-and-forget push notification
- Kafka persists the event for audit trail, analytics, and downstream consumers
- If SUMO fails, the event is still in Kafka for retry/replay

### Commodity Type Mapping

```java
// From DscServiceHelper
String commodityTypeValue = commodityTypeMappings.getOrDefault(
    dscRequest.getVendorId(), DSC_DEFAULT_COMMODITY_TYPE);

// Examples:
// vendorId: "PEPSI-001" -> "Beverage"
// vendorId: "FRITO-LAY" -> "Snacks"
// vendorId: "UNKNOWN"   -> "DSD" (default)
```

**Notification examples:**
- ENROUTE: "**Beverage** TRL-4521 is enroute to your store with ETA between 2:00 PM and 3:00 PM"
- ARRIVED: "**Snacks** TRL-8903 has arrived at store"

> "The commodity type mapping is CCM-configurable. Adding a new vendor-to-commodity mapping doesn't require code changes or redeployment. This is important because Walmart onboards new DSD suppliers frequently."

### Key Files (from repo)

```
cp-nrti-apis/
+-- controller/
|   +-- NrtiStoreControllerV1.java        # Handles POST /directShipmentCapture
+-- services/
|   +-- SumoService.java                   # Interface
|   +-- impl/SumoServiceImpl.java          # SUMO push notification logic
|   +-- helpers/DscServiceHelper.java      # Kafka payload builder + validation
|   +-- helpers/SumoHelper.java            # Notification title/body formatting
|   +-- builders/SumoServiceRequestBuilder.java  # HTTP request to SUMO API
+-- configs/
|   +-- DscApiCCMConfig.java               # DSD feature flags + commodity mappings
|   +-- SumoApiCCMConfig.java              # SUMO API credentials + roles
+-- models/
|   +-- enums/DscEventType.java            # PLANNED, STARTED, ENROUTE, ARRIVED, COMPLETED
|   +-- payloads/dsc/
|   |   +-- DscKafkaMessage.java           # Kafka event payload
|   |   +-- DscKafkaMessageHeader.java     # Event metadata
|   |   +-- DscKafkaMessagePayload.java    # Shipment data
|   |   +-- DscDestinationInfoPayload.java # Store destination info
|   |   +-- DscDriverPayload.java          # Driver details
|   |   +-- DscLoadInfoPayload.java        # Load/cargo info
|   |   +-- DscPackPayload.java            # Pack quantity info
|   |   +-- DscShipmentEtaWindowPayload.java # ETA window
|   +-- sumo/
|       +-- SumoRequest.java               # Push notification request
|       +-- Notification.java              # Title + body + customData
|       +-- Audience.java                  # List of Sites to notify
|       +-- Site.java                      # countryCode, domain, siteId, roles
|       +-- Domain.java                    # STORE, DC, HOME_OFFICE
|       +-- CustomData.java                # Category metadata
+-- requests/dsdshipment/
|   +-- DscRequest.java                    # Incoming API request
|   +-- DscDestinationInfo.java            # Store destination
|   +-- DscShipmentInfo.java               # Shipment details
|   +-- DscDriver.java                     # Driver info
+-- api-spec/
    +-- examples/dsc_request_200.json      # Request example
    +-- schema/requests/dsc_request.json   # Request schema
    +-- schema/responses/dsc_api_response.json  # Response schema
```

---

## Technical Decisions

### Decision 1: SUMO Push vs SMS vs Email vs Webhook

| Approach | Latency | Targeting | Cost | Associate Experience |
|----------|---------|-----------|------|---------------------|
| **SUMO Push** | <5 sec | Store + Domain + Role | Free (internal) | Native device notification |
| **SMS** | 5-30 sec | Phone number only | $$$ per message | Requires phone numbers |
| **Email** | Minutes | Email address | Cheap | Associates don't check email on floor |
| **Webhook** | <1 sec | System-to-system | Free | No associate notification |

> "SUMO is Walmart's internal push notification platform. It targets by store domain, site ID, and role -- so only the receiving team at the specific store gets notified. SMS would cost per message and can't target by role. Email is too slow for time-sensitive dock deliveries. SUMO gives us sub-5-second delivery to the associate's handheld device."

**Follow-up: "What if Walmart didn't have SUMO?"**
> "I'd use Firebase Cloud Messaging with topic-based subscriptions. Each store+role combination would be a topic. Associates subscribe when they log in. Similar targeting capability but we'd need to manage the subscription lifecycle."

### Decision 2: Notify on 2 Events vs All 5

| Approach | Notifications/Shipment | Fatigue Risk | Actionability |
|----------|----------------------|-------------|---------------|
| **All 5 events** | 5 per shipment | HIGH - associates ignore | Low - most are informational |
| **ENROUTE + ARRIVED only** | 2 per shipment | Low | HIGH - both require action |
| **ARRIVED only** | 1 per shipment | Lowest | Medium - no prep time |

> "Notification fatigue kills notification systems. If associates get 5 alerts per delivery, multiple deliveries per day, they'll disable notifications. ENROUTE gives them preparation time -- clear the dock, assign someone. ARRIVED means act now. The other three events are informational only. This is defined as a constant in the enum: `SUMO_NOTIFICATION_ENABLER = List.of(ENROUTE, ARRIVED)` -- adding a new triggering event is one line."

**Follow-up: "How do you know associates aren't ignoring notifications?"**
> "Honestly, we don't have open-rate tracking yet. That's something I'd add -- track notification delivery, open, and action rates. If open rates drop below a threshold, we know fatigue is setting in."

### Decision 3: Feature Flag (isSumoEnabled) vs Always-On

| Approach | Runtime Control | Risk | Complexity |
|----------|----------------|------|------------|
| **Feature flag via CCM** | Disable without deploy | Low - can turn off instantly | Minimal - one if check |
| **Always-on** | Requires deploy to disable | High - SUMO outage = errors | None |
| **Circuit breaker** | Auto-disable on failure | Low | Medium |

> "If SUMO has an outage, we don't want every DSD API call to fail because of notification errors. The feature flag lets us disable SUMO instantly via CCM -- no code change, no deployment. The DSD event still persists to Kafka, only the push notification is skipped. If I rebuilt this, I'd add a circuit breaker (Resilience4j) that automatically disables after X consecutive failures."

### Decision 4: Per-Destination Loop vs Batch Notification

```java
dscRequest.getDestinations().forEach(destination -> {
    SumoRequest sumoRequest = sumoServiceRequestBuilder.getSumoRequest(destination);
    // Build body with destination-specific ETA
    sendSumoNotification(sumoRequest, dscRequest.getMessageId());
});
```

| Approach | Notification Content | Targeting |
|----------|---------------------|-----------|
| **Per-destination loop** | Store-specific ETA window | Each store gets own notification |
| **Batch notification** | Generic message, no specific ETA | All stores get same message |

> "One shipment can go to multiple stores. Each store has a different ETA window. If we batched, Store A and Store B would get the same ETA -- wrong. The per-destination loop ensures each store gets a notification with THEIR specific ETA in THEIR local timezone."

### Decision 5: Commodity Type from CCM vs Hardcoded

```java
String commodityTypeVendorName = commodityTypeMappings
    .getOrDefault(dscRequest.getVendorId(), DSC_DEFAULT_COMMODITY_TYPE);
```

| Approach | New Vendor | Deploy Required |
|----------|-----------|----------------|
| **CCM mapping** | Add to config | No deploy |
| **Hardcoded map** | Change code | Yes, deploy |
| **Vendor API lookup** | Automatic | No, but adds latency + dependency |

> "Walmart onboards new DSD suppliers regularly. If commodity type was hardcoded, every new supplier would need a code change and deployment. CCM mapping means the operations team can add new vendor-to-commodity mappings themselves. Default fallback is 'DSD' for unmapped vendors."

### Decision 6: Kafka + SUMO (Dual Write) vs SUMO Only

| Approach | Persistence | Audit Trail | Retry |
|----------|------------|-------------|-------|
| **Kafka + SUMO** | Durable in Kafka | Full event history | Can replay from Kafka |
| **SUMO only** | No persistence | No audit trail | Lost if fails |
| **Kafka only** | Durable | Yes | No real-time notification |

> "Kafka persists every DSD event regardless of SUMO success. If SUMO fails, we lose the notification but NOT the event data. We can replay from Kafka to resend notifications. Also, the Kafka topic feeds our audit logging system -- suppliers can query their DSD API interactions in BigQuery."

### Decision 7: ETA Timezone Conversion (Store-Local) vs UTC

| Approach | Associate Experience | Complexity |
|----------|---------------------|-----------|
| **Store-local timezone** | "ETA 2:00 PM - 3:00 PM" -- meaningful | Medium (store-timezone mapping) |
| **UTC** | "ETA 19:00 - 20:00 UTC" -- confusing | Simple |
| **Supplier timezone** | Wrong timezone for store | Simple |

> "Associates need local time. 'ETA 2:00 PM' means something. 'ETA 19:00 UTC' doesn't. We maintain a store-to-timezone mapping and convert UTC to local AM/PM format. Different stores across the US are in different timezones, so we can't hardcode one timezone."

### Quick Reference

| # | Decision | Chose | Over | Key Reason |
|---|----------|-------|------|------------|
| 1 | SUMO Push | Internal, role-targeted | SMS, Email | Free, <5s, precise targeting |
| 2 | 2 events only | ENROUTE + ARRIVED | All 5 events | Notification fatigue prevention |
| 3 | Feature flag | CCM isSumoEnabled | Always-on | Instant disable without deploy |
| 4 | Per-destination loop | Store-specific ETA | Batch notification | Each store gets own ETA |
| 5 | CCM commodity mapping | No-deploy vendor updates | Hardcoded | New suppliers without code change |
| 6 | Kafka + SUMO dual | Persistence + real-time | SUMO only | Audit trail + replay capability |
| 7 | Store-local timezone | "2:00 PM" meaningful | UTC | Associate UX |

---

## Interview Q&A

### Q1: "Tell me about the DSD notification system."

> "I built real-time push notifications for Direct Store Delivery. When suppliers like Pepsi deliver to a Walmart store, our system sends SUMO push notifications to store associates. Before this, associates discovered deliveries through periodic checks -- hours of delay. After: real-time alerts within seconds.
>
> The system captures 5 event types -- Planned, Started, Enroute, Arrived, Completed -- but only ENROUTE and ARRIVED trigger notifications, because those are the states where associates need to act. Each notification includes the commodity type, trailer number, and for ENROUTE, the ETA window in the store's local timezone."

### Q2: "How did you measure the 35% improvement?"

> "We measured replenishment timing as the gap between the ARRIVED event timestamp and the inventory scan timestamp. Before notifications, this gap averaged hours because associates discovered deliveries during periodic checks. After real-time push alerts, they responded within minutes. The 35% represents the reduction in this end-to-end lag. The business operations team tracked this through operational dashboards. My contribution was the technical pipeline -- from supplier API to associate device."

**Follow-up: "35% of what exactly?"**
> "35% reduction in the time between goods arriving at the dock and goods being scanned into inventory. The business team measured pre vs post notification deployment."

**Follow-up: "Who measured this?"**
> "The business operations team tracks replenishment KPIs. My contribution was the technical implementation -- the notification pipeline from supplier API call to associate device. The 35% metric came from their operational dashboard comparing before and after notification deployment."

### Q3: "What is SUMO?"

> "SUMO is Walmart's internal push notification platform for associate devices -- similar to Firebase Cloud Messaging but internal. We call SUMO's V3 Mobile Push API with a notification payload and audience targeting. The audience specifies countryCode, domain (STORE vs DC vs HomeOffice), siteId (specific store number), and roles (receiving team). This ensures the right associates at the right store get the notification."

### Q4: "Why only ENROUTE and ARRIVED, not all events?"

> "Notification fatigue. If we sent 5 notifications per shipment per store, associates would start ignoring them. ENROUTE gives them preparation time -- 'delivery coming in 30 min, clear the dock.' ARRIVED means 'go to the dock now.' PLANNED and STARTED are informational only -- no associate action needed. COMPLETED means it's already done."

### Q5: "How does the targeting work?"

> "Three levels: Domain -> Site -> Roles. Domain is STORE (not DC or Home Office). Site is the specific store number from the shipment destination. Roles come from CCM config -- we target the receiving team roles, not all store associates. A delivery to Store 4236 only notifies associates at Store 4236 with the receiving role."

### Q6: "What if SUMO is down?"

> "The notification fails silently -- we catch SignatureHandleException and log the error. The API response to the supplier is NOT affected. The DSD event is still persisted to Kafka regardless of SUMO success. We also have a feature flag (isSumoEnabled) that can disable SUMO notifications without redeployment if there's a widespread issue."

### Q7: "What was the hardest part?"

> "ETA timezone handling. Suppliers send timestamps in UTC. But associates need 'ETA between 2:00 PM and 3:00 PM' in their LOCAL timezone. Different stores are in different timezones. We built a store-to-timezone mapping and convert UTC to local AM/PM format before building the notification body. Getting this right for stores across multiple timezones was tricky."

### Q8: "How does this connect to the audit logging system?"

> "The DSD API endpoint POST /directShipmentCapture is one of the endpoints audited by our common library. Every supplier call -- successful or failed -- is captured asynchronously and stored in GCS as Parquet. Suppliers can query their DSD API interactions in BigQuery. So the audit system and DSD system work together -- DSD captures the shipment events, audit captures the API interactions."

### Q9: "What would you do differently?"

> "Three things. First, add delivery confirmation -- currently we notify on arrival but don't track when the associate actually processes it. A confirmation button in the notification would close the loop. Second, add retry for failed SUMO calls -- currently we log and move on. Third, add notification analytics -- track open rates to measure if associates are actually reading notifications."

### Quick Answers

**"Why not SMS?"** -> "SUMO targets associate devices directly by store and role. SMS would require phone numbers and can't target by role."

**"Why CCM for roles?"** -> "Stores reorganize. Role names change. CCM means no code change when roles update."

**"Why Kafka AND SUMO?"** -> "Kafka for persistence and audit trail. SUMO for real-time push. If SUMO fails, the event is still in Kafka."

**"What's the notification latency?"** -> "Under 5 seconds from API call to associate device, depending on SUMO platform and device connectivity."

---

## Behavioral Story

### STAR Format

> **Situation:** "Walmart associates at 300+ stores were discovering DSD deliveries through periodic checks, causing hours of delay in shelving goods."
>
> **Task:** "Build a real-time notification system to alert associates immediately when deliveries are enroute or arrive."
>
> **Action:** "I integrated with Walmart's SUMO push notification platform. Built the notification service with event-type filtering -- only ENROUTE and ARRIVED trigger alerts to avoid fatigue. Implemented commodity-type mapping so notifications say 'Beverage delivery' not just 'DSD delivery.' Added CCM-configurable role targeting so only receiving team gets notified. Used feature flags for safe rollout."
>
> **Result:** "1,200+ associates across 300+ stores receive real-time delivery alerts. 35% improvement in stock replenishment timing as measured by the operations team."
>
> **Learning:** "Notification design is about restraint -- knowing what NOT to notify is as important as knowing what to notify. Five events, but only two matter for action."

### User Focus: Notification Fatigue Filtering

> "I could have notified associates on all 5 DSD events. More notifications seems like better coverage. But I thought about the ASSOCIATE's experience -- getting 5 alerts per delivery, multiple times a day, across multiple suppliers? They'd stop paying attention. I deliberately limited notifications to the 2 events that require action: ENROUTE (prepare) and ARRIVED (go now). Restraint in design is user empathy."

---

## How to Speak

### When to Use This Story

| They Ask About... | Use This |
|-------------------|----------|
| "Tell me about all your projects" | Quick mention as third project |
| "User-facing impact" | 1,200 associates getting real-time alerts |
| "Notification system design" | Full DSD architecture |
| "How do you think about users?" | Notification fatigue filtering |

### The Key Insight to Share

> "The most important design decision was what NOT to notify. DSD has 5 event types but only 2 require associate action. Sending 5 notifications per delivery would cause fatigue. This taught me: in notification systems, restraint is more important than coverage."

### Numbers to Drop

| Number | How to Say It |
|--------|---------------|
| 1,200+ associates | "...over twelve hundred store associates receive alerts..." |
| 300+ stores | "...across 300+ store locations..." |
| 35% improvement | "...35% improvement in replenishment timing..." |
| 5 event types, 2 notify | "...five event types but only two trigger notifications..." |
| ENROUTE + ARRIVED | "...ENROUTE gives prep time, ARRIVED means go to dock now..." |

### Pivot TO This Story

**From audit logging:** "The DSD endpoints are actually audited by the logging system I built. Every supplier API call is captured for compliance. Want me to walk through that architecture?"

**From Spring Boot 3:** "DSD runs on cp-nrti-apis which I migrated to Spring Boot 3. That migration was a bigger technical challenge -- 158 files, zero downtime."

### Pivot AWAY From This Story

> "The DSD notification was one part of a larger system. The more technically interesting challenge was the audit logging architecture or the DC Inventory API design. Which would you like to hear about?"

### Connections to Other Projects

| Connection | How They Relate |
|-----------|----------------|
| **Audit Logging (Bullet 1)** | DSD API endpoints are audited by the common library. Suppliers can query their DSD API interactions in BigQuery. |
| **Kafka** | DSD events are published to Kafka for persistence and downstream consumers |
| **OpenAPI (Bullet 5)** | You wrote the OpenAPI spec migration for DSD controller (PR #975, 1,507 lines) |
| **Spring Boot 3 (Bullet 4)** | DSD runs on cp-nrti-apis which you migrated to Spring Boot 3 |

---

## PR Reference

### Your DSD-Related PRs

| PR# | Title | Lines | State | What |
|-----|-------|-------|-------|------|
| **#975** | OpenAPI spec migration for Direct Shipment Controller | +1,507/-949 | CLOSED | Design-first spec for DSD (shows initiative) |
| **#1233** | dscRequestValidator log updated | +1/-1 | CLOSED | Logging fix |

> Your main DSD contributions are through working on cp-nrti-apis daily (which includes DSD), the Spring Boot 3 migration (which migrated DSD code too), and the audit logging library (which audits DSD API calls).

### System Evolution Timeline

```
Aug 2024  | DSC caching + timezone-aware notifications (#902, #919)
Oct 2024  | SUMO roles update (#1085)
Jan 2025  | Pallet/case quantity (#1140, #1179)
Jun 2025  | Driver ID added to payload (#1397)
Jul 2025  | Pack number quantity (#1405-1417)
Sep 2025  | isDockRequired field (#1433-1514)
Oct 2025  | Event type changes (#1548)
```

The DSD system evolved significantly over time -- new fields added to Kafka payload (driverId, packNbrQty, isDockRequired), role targeting updates, timezone improvements. This shows an actively maintained, evolving system, not a one-time build.
