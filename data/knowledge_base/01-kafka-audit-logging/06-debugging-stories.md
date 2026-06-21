# Debugging Stories & Production Issues

> **INTERVIEW GOLD:** These are REAL production issues. Memorize these - they show debugging skills and resilience.

---

## PRODUCTION ISSUE #1: The Silent Failure (PRs #35-61)

### Situation
About six weeks after launching the GCS sink in production, I noticed GCS buckets stopped receiving data. No errors in dashboards. The system was failing silently - losing compliance-critical audit data.

### Timeline of Debugging

**Day 1: Check the obvious**
- Kafka Connect running? Yes
- Messages in topic? Yes, millions backing up
- Conclusion: Issue is between consumption and GCS write

**Day 2: Enable DEBUG logging**
- Found NullPointerException in SMT filter
- Legacy data didn't have `wm-site-id` header we expected
- **Fix (PR #35):** Added try-catch with graceful fallback

**Day 3: Problem persisted**
- Noticed consumer poll timeouts
- Default `max.poll.interval.ms` was 5 minutes
- GCS writes for large batches took longer
- **Fix:** Tuned consumer configs

**Day 4: Still issues**
- Correlated with Kubernetes events
- KEDA autoscaling was causing instability
- When lag increased → KEDA scaled up → Rebalance triggered → More lag → More scaling
- **FEEDBACK LOOP!**
- **Fix (PR #42):** Disabled KEDA, switched to CPU-based HPA

**Day 5: Final issue (May 16, 2025)**
- JVM heap exhaustion
- Default 512MB wasn't enough for large batch Avro deserialization
- **Fix (PR #57, May 15 → #61, May 16):** Increased JVM heap — initially tried 2GB, but after further analysis increased to 7GB (`-Xmx7g -Xms5g`) with G1GC garbage collector tuned for low-pause operation.

### Result
- **Zero data loss** - Kafka retained all messages during debugging
- Backlog cleared in 4 hours
- Created troubleshooting runbook used twice by other teams

### Code Changes

**Before (PR #35):**
```java
public boolean verifyHeader(ConnectRecord<?> record) {
    Header header = record.headers().lastWithName("wm-site-id");
    return header.value().toString().equals("US");  // NPE if header is null!
}
```

**After:**
```java
public boolean verifyHeader(ConnectRecord<?> record) {
    try {
        Header header = record.headers().lastWithName("wm-site-id");
        if (header == null || header.value() == null) {
            return true;  // Permissive: default to US bucket
        }
        return header.value().toString().equals("US");
    } catch (Exception e) {
        return true;  // Default to US bucket
    }
}
```

### Interview Answer (STAR Format)

> **Situation:** "Two weeks after launching the GCS sink in production, I noticed GCS buckets stopped receiving data. No alerts - the system was failing silently."
>
> **Task:** "As the system owner, I needed to identify root cause and fix without losing more data."
>
> **Action:** "I took a systematic approach over five days:
> - Day 1: Checked obvious - Kafka running? Yes. Messages in topic? Yes. Issue was between consumption and write.
> - Day 2: Enabled DEBUG logging, found NPE in SMT filter on null headers. Added try-catch.
> - Day 3: Problem persisted. Found consumer poll timeouts, tuned configs.
> - Day 4: Discovered KEDA autoscaling causing rebalance storms - feedback loop! Disabled it.
> - Day 5: Found heap exhaustion on large batches. Increased JVM heap to 2GB."
>
> **Result:** "Zero data loss because Kafka retained messages. Backlog cleared in 4 hours. Created runbook used twice since. Key learning: Kafka Connect's error tolerance can hide issues - always add monitoring."

### Quantified Impact — The 413 Error Discovery

During the validation phase (April 2025), I cross-referenced API Proxy request counts with Data Discovery (Hive) record counts. The numbers didn't match — we were losing 40,000-130,000 records per day.

**Root cause**: The API Proxy gateway had a default 1MB payload limit. Large responses (especially inventory status with hundreds of items) were hitting **413 Payload Too Large** before reaching the audit publisher.

**Fix**: Set `APIPROXY_QOS_REQUEST_PAYLOAD_SIZE: 2097152` (2MB) — PRs #49-51.

**Result**: After the fix, API Proxy count exactly matched Data Discovery count — zero data loss.

> "This taught me to always validate data at every tier boundary. Monitoring inputs doesn't guarantee outputs are correct."

---

## PRODUCTION ISSUE #2: KEDA Autoscaling Rebalance Storm (PR #42)

### The Problem
KEDA autoscaling was configured to scale on consumer lag. Seemed logical: more lag = more work = scale up.

### What Actually Happened
```
Traffic spike
    ↓
Lag increases
    ↓
KEDA scales from 1 to 3 workers
    ↓
Consumer group rebalance triggered
    ↓
During rebalance, NO messages consumed
    ↓
Lag increases more
    ↓
KEDA scales to 5 workers
    ↓
Another rebalance
    ↓
INFINITE LOOP!
```

### The Fix (PR #42 - Merged May 14, 2025)

PR description confirms: "Removed scaling configurations related to consumer lag. Simplified scaling settings."

```yaml
# REMOVED from kitt.yml (-29 lines):
keda:
  triggers:
    - type: kafka
      metadata:
        consumerGroup: audit-log-consumer-group
        lagThreshold: "100"

# Also updated in kc_config.yaml:
heartbeat.interval.ms: 600000    # Was 10000 (changed to 10 min)
session.timeout.ms: 600000       # Was 30000 (changed to 10 min)

# Also increased flush.size in env_properties.yaml:
flush.size: 100000000            # Was 10000000 (10x increase)
```

### Interview Answer
> "We had KEDA autoscaling based on consumer lag. In production, a traffic spike triggered scaling, which triggered consumer rebalances, which increased lag, which triggered more scaling - a feedback loop. The connector got stuck in constant rebalancing and processed zero messages. We removed KEDA for Kafka consumers and switched to CPU-based HPA."

### Learning
> **Don't scale Kafka consumers on lag** - it triggers rebalances which cause more lag. Use CPU-based scaling instead.

---

## PRODUCTION ISSUE #3: OOM Kills (PRs #57, #61)

### The Problem
Kafka Connect workers were getting killed by OOM killer every 30-60 minutes. Lag building up during restarts.

### Root Cause
- Kafka Connect using default heap (~256MB)
- Large batch sizes (flush.size: 10M records)
- Avro deserialization overhead
- Memory exhaustion

### The Fix
```yaml
# Before: Default (~256MB)
env:
  - name: KAFKA_HEAP_OPTS
    value: "-Xms256m -Xmx512m"

# After: Explicit 7GB heap
env:
  - name: KAFKA_HEAP_OPTS
    value: "-Xms4g -Xmx7g"
```

### Interview Answer
> "Kafka Connect workers were getting OOM killed every 30-60 minutes. We were using default heap of 256MB, but our GCS sink buffers large batches - flush.size was 10 million records - in memory before writing. Combined with Avro deserialization overhead, we needed much more memory. We increased heap to 7GB and the OOM kills stopped."

---

## PRODUCTION ISSUE #4: SMT Filter NPE (PR #35)

### The Problem
Connector stopped processing ALL messages due to one bad record with null header.

### Why It Was Silent
- `errors.tolerance` was set to "none"
- One bad message → connector fails
- No alert configured for connector failure

### The Fix
1. Added try-catch in SMT filter
2. Made US filter permissive (accepts records WITH US header OR without any header)
3. Added Prometheus metrics for filter exceptions

### Interview Answer
> "Our SMT filter threw NullPointerException on malformed headers, causing the entire connector to fail. Because errors.tolerance was 'none', one bad message stopped processing of all messages. We lost about 6 hours of data before alerting triggered. I added try-catch with graceful fallback - malformed headers now default to the US bucket."

---

## PRODUCTION ISSUE #5: Dual-Region Failover Not Working (PRs #65, #69)

### The Problem
During a 2-hour Kafka outage in primary region (EUS2), secondary region (SCUS) was never tried. Messages were dropped.

### Root Cause
Failover logic used `exceptionally()` but didn't properly chain to secondary.

**Before:**
```java
kafkaPrimaryTemplate.send(message)
    .exceptionally(ex -> {
        log.error("Failed: {}", ex.getMessage());
        return null;  // Message lost! Secondary never tried!
    });
```

**After (PR #65):**
```java
CompletableFuture<SendResult<String, Message<IacKafkaPayload>>> future =
    kafkaPrimaryTemplate.send(message);

future
    .thenAccept(result -> log.info("Primary success"))
    .exceptionally(ex -> {
        log.warn("Primary failed, trying secondary: {}", ex.getMessage());
        handleFailure(topicName, message, messageId).join();  // Retry secondary!
        return null;
    })
    .join();

private CompletableFuture<Void> handleFailure(String topic, Message msg, String id) {
    return kafkaSecondaryTemplate.send(msg)
        .thenAccept(result -> log.info("Secondary success: {}", result))
        .exceptionally(ex -> {
            log.error("Both regions failed!");
            throw new NrtiUnavailableException();
        });
}
```

### Interview Answer
> "During a Kafka outage in our primary region, we discovered failover wasn't working. The code returned null in exceptionally() instead of trying the secondary region. Messages were just dropped. I refactored to properly chain CompletableFuture - if primary fails, we synchronously try secondary. If both fail, we throw so the caller knows."

---

## Summary Table

| Issue | Severity | Root Cause | Fix | Learning |
|-------|----------|------------|-----|----------|
| Silent Failure | Critical | Multiple issues compounding | PRs #35-61 | Distributed systems fail in unexpected combinations |
| KEDA Rebalance Storm | Critical | Scaling on lag triggers rebalances | Remove KEDA, use CPU-based HPA | Don't scale Kafka consumers on lag |
| OOM Kills | High | Default heap + large batches | 7GB heap | Know your memory requirements |
| SMT NPE | Critical | No null handling | Try-catch + default fallback | Defensive coding in connectors |
| Failover Logic | High | Broken CompletableFuture chain | Proper chaining + join() | Test failover regularly |

---

## Key Learnings to Mention

1. **Kafka Connect's error tolerance can hide issues** - Always add monitoring
2. **Don't scale Kafka consumers on lag** - Triggers rebalances, makes it worse
3. **Default configurations are rarely production-ready** - Always tune
4. **Test failover regularly** - Our failover was broken and we didn't know
5. **Distributed systems fail in unexpected combinations** - Need systematic debugging

---

*These stories show debugging skills, production experience, and learning from failure - all things interviewers love!*
