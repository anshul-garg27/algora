# Technical Implementation - DSD Notification (ACTUAL Code)

> All code below is from `cp-nrti-apis` repo, verified via gh.

---

## 1. SumoServiceImpl.java - The Core Notification Logic

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

### Key Design Points:

1. **Feature Flag First** - `isSumoEnabled()` check before any processing. Can disable notifications runtime via CCM.
2. **Event Type Filtering** - `SUMO_NOTIFICATION_ENABLER = List.of(ENROUTE, ARRIVED)` - only 2 of 5 events trigger notifications.
3. **Per-Destination Loop** - One shipment can go to multiple stores. Each store gets its own notification.
4. **Commodity Type Mapping** - vendor-specific notification text ("Beverage" vs "Snacks" vs "DSD").
5. **ETA Window Formatting** - `SumoHelper.getAmPmFromTimeZone()` converts UTC timestamps to store-local AM/PM format.

---

## 2. DscEventType.java - Event Type Enum

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

**Interview Point:** "The SUMO_NOTIFICATION_ENABLER list is defined as a constant IN the enum. Adding a new notification-triggering event is one line change - add it to this list. No switch statement changes needed."

---

## 3. SUMO Models (Notification Targeting)

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

**Interview Point:** "The targeting model is hierarchical: Audience → Sites → Site with countryCode + domain + siteId + roles. This ensures notifications reach ONLY the receiving team at the SPECIFIC store. A store in Texas doesn't get notifications for a delivery to a store in California."

---

## 4. SUMO API Configuration (CCM-Based)

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

**Interview Point:** "The store roles are CCM-configurable. If a store reorganizes and the receiving team role name changes, we update CCM - no code change, no redeployment."

---

## 5. Kafka Payload (Event Persistence)

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

---

## Technical Decisions

| Decision | Why | Alternative |
|----------|-----|-------------|
| **SUMO V3 Mobile Push** | Walmart's internal push platform, targets by store/role | SMS (expensive), Email (slow) |
| **Feature flag (isSumoEnabled)** | Disable without deploy during issues | Always-on (can't disable) |
| **Per-destination loop** | One shipment → multiple stores, each needs own notification | Single notification (wrong stores) |
| **Commodity type from CCM** | New vendors added without code change | Hardcoded vendor→type map |
| **ETA in store timezone** | "2:00 PM" is meaningful to associates, UTC is not | UTC timestamps (confusing) |
| **Kafka + SUMO (dual write)** | Persistence + real-time notification | SUMO only (no audit trail) |
| **Switch on eventType** | Clear, explicit per-event logic | If-else chain (harder to read) |

---

*Next: [03-interview-qa.md](./03-interview-qa.md)*
