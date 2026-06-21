# Technical Decisions Deep Dive - DSD Notification

> "Why THIS and Not THAT?" for every DSD design decision.

---

## Decision 1: SUMO Push vs SMS vs Email vs Webhook

| Approach | Latency | Targeting | Cost | Associate Experience | Our Choice |
|----------|---------|-----------|------|---------------------|------------|
| **SUMO Push** | <5 sec | Store + Domain + Role | Free (internal) | Native device notification | **YES** |
| **SMS** | 5-30 sec | Phone number only | $$$ per message | Requires phone numbers | No |
| **Email** | Minutes | Email address | Cheap | Associates don't check email on floor | No |
| **Webhook** | <1 sec | System-to-system | Free | No associate notification | No |

### Interview Answer
> "SUMO is Walmart's internal push notification platform. It targets by store domain, site ID, and role - so only the receiving team at the specific store gets notified. SMS would cost per message and can't target by role. Email is too slow for time-sensitive dock deliveries. SUMO gives us sub-5-second delivery to the associate's handheld device."

### Follow-up: "What if Walmart didn't have SUMO?"
> "I'd use Firebase Cloud Messaging with topic-based subscriptions. Each store+role combination would be a topic. Associates subscribe when they log in. Similar targeting capability but we'd need to manage the subscription lifecycle."

---

## Decision 2: Notify on 2 Events vs All 5

| Approach | Notifications/Shipment | Fatigue Risk | Actionability | Our Choice |
|----------|----------------------|-------------|---------------|------------|
| **All 5 events** | 5 per shipment | HIGH - associates ignore | Low - most are informational | No |
| **ENROUTE + ARRIVED only** | 2 per shipment | Low | HIGH - both require action | **YES** |
| **ARRIVED only** | 1 per shipment | Lowest | Medium - no prep time | Considered |

### Interview Answer
> "Notification fatigue kills notification systems. If associates get 5 alerts per delivery, multiple deliveries per day, they'll disable notifications. ENROUTE gives them preparation time - clear the dock, assign someone. ARRIVED means act now. The other three events are informational only. This is defined as a constant in the enum: `SUMO_NOTIFICATION_ENABLER = List.of(ENROUTE, ARRIVED)` - adding a new triggering event is one line."

### Follow-up: "How do you know associates aren't ignoring notifications?"
> "Honestly, we don't have open-rate tracking yet. That's something I'd add - track notification delivery, open, and action rates. If open rates drop below a threshold, we know fatigue is setting in."

---

## Decision 3: Feature Flag (isSumoEnabled) vs Always-On

| Approach | Runtime Control | Risk | Complexity | Our Choice |
|----------|----------------|------|------------|------------|
| **Feature flag via CCM** | Disable without deploy | Low - can turn off instantly | Minimal - one if check | **YES** |
| **Always-on** | Requires deploy to disable | High - SUMO outage = errors | None | No |
| **Circuit breaker** | Auto-disable on failure | Low | Medium | Should add |

### Interview Answer
> "If SUMO has an outage, we don't want every DSD API call to fail because of notification errors. The feature flag lets us disable SUMO instantly via CCM - no code change, no deployment. The DSD event still persists to Kafka, only the push notification is skipped. If I rebuilt this, I'd add a circuit breaker (Resilience4j) that automatically disables after X consecutive failures."

---

## Decision 4: Per-Destination Loop vs Batch Notification

### What's In The Code
```java
dscRequest.getDestinations().forEach(destination -> {
    SumoRequest sumoRequest = sumoServiceRequestBuilder.getSumoRequest(destination);
    // Build body with destination-specific ETA
    sendSumoNotification(sumoRequest, dscRequest.getMessageId());
});
```

| Approach | Notification Content | Targeting | Our Choice |
|----------|---------------------|-----------|------------|
| **Per-destination loop** | Store-specific ETA window | Each store gets own notification | **YES** |
| **Batch notification** | Generic message, no specific ETA | All stores get same message | No |

### Interview Answer
> "One shipment can go to multiple stores. Each store has a different ETA window. If we batched, Store A and Store B would get the same ETA - wrong. The per-destination loop ensures each store gets a notification with THEIR specific ETA in THEIR local timezone."

---

## Decision 5: Commodity Type from CCM vs Hardcoded

```java
String commodityTypeVendorName = commodityTypeMappings
    .getOrDefault(dscRequest.getVendorId(), DSC_DEFAULT_COMMODITY_TYPE);
```

| Approach | New Vendor | Deploy Required | Our Choice |
|----------|-----------|----------------|------------|
| **CCM mapping** | Add to config | No deploy | **YES** |
| **Hardcoded map** | Change code | Yes, deploy | No |
| **Vendor API lookup** | Automatic | No, but adds latency + dependency | Over-engineered |

### Interview Answer
> "Walmart onboards new DSD suppliers regularly. If commodity type was hardcoded, every new supplier would need a code change and deployment. CCM mapping means the operations team can add new vendor-to-commodity mappings themselves. Default fallback is 'DSD' for unmapped vendors."

---

## Decision 6: Kafka + SUMO (Dual Write) vs SUMO Only

| Approach | Persistence | Audit Trail | Retry | Our Choice |
|----------|------------|-------------|-------|------------|
| **Kafka + SUMO** | Durable in Kafka | Full event history | Can replay from Kafka | **YES** |
| **SUMO only** | No persistence | No audit trail | Lost if fails | No |
| **Kafka only** | Durable | Yes | No real-time notification | No |

### Interview Answer
> "Kafka persists every DSD event regardless of SUMO success. If SUMO fails, we lose the notification but NOT the event data. We can replay from Kafka to resend notifications. Also, the Kafka topic feeds our audit logging system - suppliers can query their DSD API interactions in BigQuery."

---

## Decision 7: ETA Timezone Conversion (Store-Local) vs UTC

| Approach | Associate Experience | Complexity | Our Choice |
|----------|---------------------|-----------|------------|
| **Store-local timezone** | "ETA 2:00 PM - 3:00 PM" ← meaningful | Medium (store-timezone mapping) | **YES** |
| **UTC** | "ETA 19:00 - 20:00 UTC" ← confusing | Simple | No |
| **Supplier timezone** | Wrong timezone for store | Simple | No |

### Interview Answer
> "Associates need local time. 'ETA 2:00 PM' means something. 'ETA 19:00 UTC' doesn't. We maintain a store-to-timezone mapping and convert UTC to local AM/PM format. Different stores across the US are in different timezones, so we can't hardcode one timezone."

---

## Quick Reference

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

*"We considered [alternatives]. Chose [X] because [reason]. Trade-off: [downside]. Mitigated by: [action]."*
