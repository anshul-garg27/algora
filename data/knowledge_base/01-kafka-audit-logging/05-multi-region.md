# Multi-Region Architecture (Bullet 10)

> **Resume Bullet:** 10 - Multi-Region Kafka Architecture
> **Regions:** EUS2 (East US 2) + SCUS (South Central US)

---

## Why Multi-Region?

1. **Disaster Recovery**: If EUS2 goes down, SCUS continues
2. **Latency**: Users closer to SCUS get faster responses
3. **Compliance**: Data residency requirements
4. **Load Distribution**: Split traffic across regions

---

## Architecture

```
                          ┌─────────────────────────────────────┐
                          │         GLOBAL LOAD BALANCER        │
                          │          (Azure Front Door)         │
                          └───────────────┬─────────────────────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    │                     │                     │
                    ▼                     ▼                     ▼
         ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
         │   EUS2 Region    │  │   SCUS Region    │  │  INTL (Future)   │
         │  (East US 2)     │  │ (South Central)  │  │                  │
         │                  │  │                  │  │                  │
         │ ┌──────────────┐ │  │ ┌──────────────┐ │  │                  │
         │ │audit-api-logs│ │  │ │audit-api-logs│ │  │                  │
         │ │   -srv       │ │  │ │   -srv       │ │  │                  │
         │ └──────┬───────┘ │  │ └──────┬───────┘ │  │                  │
         │        │         │  │        │         │  │                  │
         │        ▼         │  │        ▼         │  │                  │
         │ ┌──────────────┐ │  │ ┌──────────────┐ │  │                  │
         │ │Kafka Cluster │ │◄─►│ │Kafka Cluster │ │  │                  │
         │ │(EUS2)        │ │  │ │(SCUS)        │ │  │                  │
         │ └──────┬───────┘ │  │ └──────┬───────┘ │  │                  │
         │        │         │  │        │         │  │                  │
         │        ▼         │  │        ▼         │  │                  │
         │ ┌──────────────┐ │  │ ┌──────────────┐ │  │                  │
         │ │GCS Sink      │ │  │ │GCS Sink      │ │  │                  │
         │ │(Connect)     │ │  │ │(Connect)     │ │  │                  │
         │ └──────────────┘ │  │ └──────────────┘ │  │                  │
         └──────────────────┘  └──────────────────┘  └──────────────────┘
                    │                     │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌──────────────────┐
                    │   GCS Buckets    │  (Shared across regions)
                    │ - us-prod        │
                    │ - ca-prod        │
                    │ - mx-prod        │
                    └──────────────────┘
```

---

## Active/Active vs Active/Passive

I designed three options and presented trade-offs to the team:

| Option | Pros | Cons | Failover Time |
|--------|------|------|---------------|
| **Active-Passive** | Simple, cheap | Slow failover, wasted resources | ~30 min |
| **Active-Active** | Immediate failover, load distribution | Complex, 2x cost | ~15 min |
| **Hybrid** | Active-Active for writes, single read | Moderate complexity | ~20 min |

**We chose Active-Active** because audit is write-heavy and compliance couldn't tolerate 30-minute failover delays.

---

## How I Defined Requirements (Ambiguity Story)

Requirements were vague - leadership said "make it resilient" without specifics.

**What I did:**
1. Asked stakeholders: "How much data can we lose in a disaster?" → Max 4-hour gap (RPO)
2. Asked: "How quickly must we recover?" → 1-hour recovery time (RTO)
3. Documented assumptions explicitly
4. Presented 3 options with trade-offs
5. Team chose Active-Active

**Result:** Achieved 15 min recovery (well under 1-hour target), zero data loss.

---

## Implementation: Phased Approach

```
Week 1: Deploy publisher service to second region (SCUS)
        → Write to both Kafka clusters

Week 2: Deploy GCS sink to second region
        → Both regions now consuming and writing

Week 3: Validate data parity between regions
        → Compare record counts, spot check data

Week 4: Update routing to use both regions
        → Test failover by intentionally failing one region
```

---

## Dual-Region Kafka Publishing Code

```java
public void publishMessageToTopic(LoggingApiRequest request) {
    Message<LogEvent> message = prepareMessage(request);

    try {
        kafkaPrimaryTemplate.send(message).get();  // EUS2
    } catch (Exception ex) {
        log.warn("Primary Kafka failed, trying secondary: {}", ex.getMessage());
        kafkaSecondaryTemplate.send(message).get();  // SCUS fallback
    }
}
```

### Improved Failover (After PR #65)

```java
CompletableFuture<SendResult<String, Message<LogEvent>>> future =
    kafkaPrimaryTemplate.send(message);

future
    .thenAccept(result -> log.info("Primary success"))
    .exceptionally(ex -> {
        log.warn("Primary failed, trying secondary: {}", ex.getMessage());
        handleFailure(topicName, message, messageId).join();
        return null;
    })
    .join();

private CompletableFuture<Void> handleFailure(String topic, Message msg, String id) {
    return kafkaSecondaryTemplate.send(msg)
        .thenAccept(result -> log.info("Secondary success: {}", result))
        .exceptionally(ex -> {
            log.error("Both regions failed for message: {}", id);
            throw new NrtiUnavailableException();
        });
}
```

> **Important Clarification**: This improved failover pattern with `CompletableFuture` is implemented in the **consuming services** (like cp-nrti-apis) for their IAC/DSC Kafka publishing. In the audit-api-logs-srv publisher itself, the current code catches primary failures and logs them but does NOT automatically chain to the secondary template. This is a known gap — if asked: "The consuming services have proper CompletableFuture failover. The publisher service logs primary failures and is next in line for the failover upgrade."

---

## Geographic Routing via wm-site-id Header

```
Message arrives with header: wm-site-id = "CA"

US Connector (FilterUS):
  - Check: header = "US"? NO
  - Check: no header? NO
  - Result: return null (DROP)

CA Connector (FilterCA):
  - Check: header = "CA"? YES
  - Result: return record (WRITE to gs://audit-api-logs-ca-prod/)

MX Connector (FilterMX):
  - Check: header = "MX"? NO
  - Result: return null (DROP)
```

---

## CCM Configuration for Multi-Region

```yaml
# PROD-1.0-ccm.yml
configOverrides:
  workerConfig:
    - description: "prod-scus env"
      pathElements:
        envProfile: "prod"
        envName: "prod-scus"
      value:
        properties:
          bootstrap.servers: "kafka-532395416-1-1708669300.scus.kafka-v2..."

    - description: "prod-eus2 env"
      pathElements:
        envProfile: "prod"
        envName: "prod-eus2"
      value:
        properties:
          bootstrap.servers: "kafka-976900980-1-1708670447.eus.kafka-v2..."
```

---

## DR Test Results

| Metric | Target | Achieved |
|--------|--------|----------|
| **RTO (Recovery Time)** | 1 hour | **15 minutes** |
| **RPO (Data Loss)** | 4 hours | **Zero** |
| **Downtime during migration** | Minimal | **Zero** |
| **Data parity** | >99% | **100%** |

### Production Validation Data (April 2025)

We validated data parity by comparing API Proxy counts against Data Discovery (Hive) counts:

| Date | API Proxy Total | Data Discovery Total | Difference | Root Cause |
|------|----------------|---------------------|------------|------------|
| Apr 8 | 2,264,634 | 2,385,317 | +120,683 | DD has retries; 39K lost to 413 errors |
| Apr 13 | 1,742,647 | 1,638,352 | -104,295 | 104,345 records lost to 413 + 5 to 502 |
| Apr 14 | 2,078,950 | 1,948,468 | -130,438 | 130,232 lost to 413 + 11 to 502 |

**Key Finding**: 5-7% of audit events were being silently dropped due to **413 Payload Too Large** errors — up to 130K records/day. After setting the 2MB gateway limit (PR #49-51), API Proxy count exactly matched Data Discovery count.

---

## Exactly-Once Processing Across Regions

**Challenge:** How to prevent duplicate processing when both regions are active?

**Solutions:**
1. **Kafka idempotent producer** - Prevents duplicate writes to same cluster
2. **Deduplication in sink** - Based on `request_id`, if already processed, SMT drops it
3. **Geographic routing** - Each region primarily handles its geography, reducing overlap

---

## Interview Questions

### Q: "Why Active/Active vs Active/Passive?"
> "Audit is write-heavy and compliance couldn't tolerate 30-minute failover delays. Active/Active gives us immediate failover - if one region fails, the other handles all traffic. We achieved 15-minute recovery in DR testing."

### Q: "How do you handle split-brain?"
> "Each region processes its geography using wm-site-id header routing. Deduplication handles any overlap. In worst case, we get duplicates not data loss - and duplicates are easily handled in BigQuery with DISTINCT queries."

### Q: "What about cost?"
> "~2x infrastructure cost, justified by compliance requirements and zero-downtime guarantee. The cost of a compliance failure far exceeds the infrastructure cost."

### Q: "How did you define requirements when they were vague?"
> "I explicitly documented assumptions: 'I'm assuming RPO of 4 hours because...' and shared with stakeholders. That document became the de facto requirements spec after they reviewed and approved it."

---

## Key PRs

| PR# | Repo | Title | Description |
|-----|------|-------|-------------|
| #30 | gcs-sink | adding prod-eus2 env | Added EUS2 region deployment |
| #65 | srv | publish in both regions | Dual-region Kafka publishing |
| #67 | srv | Allowing selected headers | Header forwarding for routing |
| #85 | gcs-sink | Site-based routing | SMT filters for geo-routing |

---

## STAR Story: Multi-Region Rollout

**Situation:** "We needed to expand from single-region to multi-region for DR. Requirements were vague - 'make it resilient.'"

**Task:** "Define requirements, design solution, execute with zero downtime."

**Action:**
- Clarified RTO/RPO through stakeholder conversations
- Designed 3 options, recommended Active/Active
- Phased implementation over 4 weeks
- Validated data parity, tested failover

**Result:** "Active/Active in 4 weeks. Zero downtime. DR test: 15 min recovery vs 1-hour target. Became reference architecture for other teams."

---

*Previous: [04-gcs-sink.md](./04-gcs-sink.md) | Next: [06-debugging-stories.md](./06-debugging-stories.md)*
