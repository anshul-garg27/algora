# Production Issues - All 3 Tiers (Complete gh Verified)

> **Every production issue across all 3 repos - real PRs, real dates, real fixes.**
> This is more detailed than 06-debugging-stories.md which focuses on the TOP stories for interview.

---

## Complete Timeline

```
Mar 2025    │ PRODUCTION LAUNCH (PRs #12 gcs-sink, #44 srv)
            │
Mar 17      │ TIER 2: Bug fix - HttpMethodNotSupported returning wrong status (srv #40)
            │
Apr 2-3     │ TIER 3: Topic name misconfiguration (gcs-sink #20-25) - 6 config fix PRs in 2 days!
Apr 16      │ TIER 2: 413 Payload too large - request size limit (srv #49-51)
            │
May 2       │ TIER 3: Consumer tuning - flush count, poll interval (gcs-sink #27)
May 7       │ TIER 3: KEDA autoscaling added (gcs-sink #29) → will cause problems!
May 12      │ TIER 3: Consumer config CRQ + multi-region EUS2 (gcs-sink #28, #30)
            │
MAY 13-16   │ === THE SILENT FAILURE INCIDENT (5 DAYS) ===
May 13      │ TIER 3: NPE in SMT filter - try-catch added (gcs-sink #35)
May 13      │ TIER 3: Consumer poll config fix (gcs-sink #38)
May 13      │ TIER 3: Changed to standard consumer configs (gcs-sink #39)
May 13      │ TIER 3: More logging added (gcs-sink #37)
May 14      │ TIER 3: KEDA removed! Heartbeat updated (gcs-sink #42) ← FEEDBACK LOOP FIX
May 14      │ TIER 3: Session timeout tuning - up then down (gcs-sink #43, #46)
May 14      │ TIER 3: Poll timeout increase (gcs-sink #47)
May 14      │ TIER 3: Multiple hotfix configs (gcs-sink #49-53)
May 14      │ TIER 3: Error tolerance set to none (gcs-sink #51, #52)
May 15      │ TIER 3: JVM heap override (gcs-sink #57)
May 15      │ TIER 3: Filter rewrite + custom header converter (gcs-sink #58, #59)
May 15      │ TIER 3: Header converter at worker level (gcs-sink #60)
May 15      │ TIER 2: Header forwarding for geo-routing (srv #67)
May 16      │ TIER 3: Heap max increase (gcs-sink #61) ← FINAL FIX
May 16      │ TIER 2: Header validation - case-insensitive matching (srv #69)
May 19      │ TIER 2: Multi-region publishing with failover (srv #65)
            │
May 22-27   │ TIER 3: International (CA/MX) support rollout (gcs-sink #64-68)
May 30      │ TIER 3: Connector upgrade + retry policy (gcs-sink #69)
Jun 9       │ TIER 3: Retry policy CRQ for production (gcs-sink #70)
Jun 11      │ TIER 3: Data type fix - DECIMAL for timeout multiplier (gcs-sink #75)
Jun 18      │ TIER 3: Connector version update (gcs-sink #81)
            │
Sep 19      │ TIER 1: GTP BOM update for Java 17 compat (common-lib #15)
Nov 3       │ TIER 3: Country code to site ID mapping change (gcs-sink #83)
Nov 18      │ TIER 2: Contract testing added (srv #77)
Dec 2       │ TIER 3: Multi-site filter support US/CA/MX (gcs-sink #85) ← MAJOR
Dec 10      │ TIER 2: Signature validation for specific consumerId (srv #81)
Dec 16      │ TIER 2: Performance test configs added (srv #76)
Jan 5, 2026 │ TIER 2: GTP BOM update (srv #82)
Jan 29      │ TIER 3: Vulnerability fix + startup probe (gcs-sink #87)
```

---

## TIER 1: Common Library (dv-api-common-libraries) Issues

### Issue: No production issues found in the library itself

The common library has been stable since launch. Only 8 merged PRs total, and post-launch changes were:
- **PR #11** (Apr 11): Regex endpoint filtering - Enhancement, not a fix
- **PR #15** (Sep 19): GTP BOM update for Java 17 - Compatibility, not a fix

**Interview Point:**
> "The library itself has been remarkably stable - zero production bugs. I attribute this to the simple design: it's just a filter, an async service, and a config. The complexity lives in the downstream tiers."

---

## TIER 2: Kafka Publisher (audit-api-logs-srv) Issues

### Issue 1: HTTP 405 Method Not Supported (PR #40)

**Date:** March 17, 2025 (2 weeks after launch)
**Severity:** Medium

**What Happened:** Clients sending requests with wrong HTTP method (e.g., GET instead of POST to /v1/logRequest) got an unhandled error response.

**The Fix:** Added explicit `HttpRequestMethodNotSupportedException` handler returning 405 status with proper error body.

**Interview Point:**
> "We added proper HTTP method handling. Before, a wrong method returned a generic 500. After, it returns 405 with a clear message. Small fix but important for API correctness."

---

### Issue 2: 413 Request Entity Too Large (PRs #49-51)

**Date:** April 16-23, 2025 (3 weeks after launch)
**Severity:** Medium - Silent data loss for large payloads

**What Happened:** Some API responses (with hundreds of inventory items) had large audit payloads. The default API proxy limit was 1MB. Audit data for these requests was silently dropped.

**How Discovered:** Pattern analysis showed missing audit records. All missing records had large response bodies.

**The Fix:**
```yaml
# sr.yaml
APIPROXY_QOS_REQUEST_PAYLOAD_SIZE: 2097152  # 2MB (was 1MB default)
```
Also added URITransformPolicy for proper request mapping.

**Interview Point:**
> "We were losing audit data for large responses without knowing it. The API proxy had a default 1MB limit. This taught me: know ALL size limits in your infrastructure chain."

---

### Issue 3: Header Forwarding Missing (PR #67)

**Date:** May 15, 2025
**Severity:** High - Geographic routing not working

**What Happened:** The `wm-site-id` header wasn't being forwarded from the library to Kafka messages. This meant the GCS sink couldn't route records to the correct geographic bucket.

**The Fix:** Added allowlist-based header forwarding in KafkaProducerService:
```java
Set<String> allowedHeaders = Set.of(
    "wm_consumer.id", "wm_qos.correlation_id",
    "wm_svc.name", "wm_svc.version", "wm_svc.env",
    "wm-site-id"  // CRITICAL for geo-routing
);
```

**Interview Point:**
> "Without header forwarding, ALL records went to the US bucket because the US filter is permissive. Canada and Mexico data was in the wrong bucket. We added an allowlist pattern for forwarding - only specific headers, never sensitive ones."

---

### Issue 4: Header Validation Case-Sensitivity (PR #69)

**Date:** May 16, 2025
**Severity:** Medium

**What Happened:** Some services sent headers in different cases (e.g., `WM-Site-Id` vs `wm-site-id`). The allowlist check was case-sensitive, so some headers were dropped.

**The Fix:** Added case-insensitive matching and centralized the allowed headers definition.

**Interview Point:**
> "HTTP headers are case-insensitive by spec, but our code was doing exact string match. Some records lost their routing header. Quick fix but a good reminder: always handle headers case-insensitively."

---

### Issue 5: Dual-Region Failover Bug (PR #65)

**Date:** May 19, 2025
**Severity:** High - Messages dropped during regional outage

**What Happened:** During a Kafka outage in primary region (EUS2), the failover code returned null in `exceptionally()` instead of trying the secondary region. Messages were silently dropped.

**Before:**
```java
kafkaPrimaryTemplate.send(message)
    .exceptionally(ex -> {
        log.error("Failed: {}", ex.getMessage());
        return null;  // BUG: Secondary never tried!
    });
```

**After:**
```java
future.thenAccept(result -> log.info("Primary success"))
    .exceptionally(ex -> {
        log.warn("Primary failed, trying secondary");
        handleFailure(topicName, message, messageId).join();
        return null;
    }).join();
```

**Interview Point:**
> "Our failover was broken and we didn't know until a real outage. CompletableFuture's `.exceptionally()` returning null silently swallows the error. Lesson: always test failover scenarios, don't just write the code."

---

### Issue 6: Signature Validation Bypass Needed (PR #81)

**Date:** December 10, 2025
**Severity:** Medium

**What Happened:** Certain internal consumer IDs needed to skip signature validation for automated testing pipelines.

**The Fix:** Added policy rule to skip signature validation for specific consumer IDs via CCM config.

---

## TIER 3: GCS Sink (audit-api-logs-gcs-sink) Issues

### Issue 7: Topic Name Misconfiguration (PRs #20-25)

**Date:** April 3, 2025 (Day 1 of production!)
**Severity:** Critical - No data flowing

**What Happened:** 6 config fix PRs in a single day. The Kafka topic names and KCQL (Kafka Connect Query Language) configurations were wrong for the production environment (SCUS).

**The Fix:** Multiple rapid config updates to topic names, KCQL paths, and project IDs.

**Interview Point:**
> "Day 1 of production, the sink wasn't receiving any data. Turned out topic names were misconfigured for the SCUS environment. We had 6 config fixes in one day. Lesson: always verify configurations independently for each environment - don't assume staging names carry over."

---

### Issue 8: THE SILENT FAILURE (PRs #35-61) - May 13-16

**Already documented in detail in [06-debugging-stories.md](./06-debugging-stories.md)**

Summary of the 5-day debugging across 4 root causes:
1. **NPE in SMT filter** (#35) - null headers → try-catch
2. **Consumer poll timeouts** (#38, #39) - config tuning
3. **KEDA autoscaling feedback loop** (#42) - disabled KEDA
4. **JVM heap exhaustion** (#57, #61) - increased to 7GB

**But there's MORE detail from the PRs that wasn't captured:**

**PR #58-59: Filter Rewrite**
During the debugging, the original USFilter was completely removed (PR #58: -301 lines) and rewritten with a new approach (PR #59: +386 lines) that included a CustomHeaderConverter for proper Avro header deserialization. This wasn't just a "try-catch fix" - it was a complete rewrite of the filtering approach.

**PR #51-52: Error Tolerance Oscillation**
We oscillated between `errors.tolerance: all` (silent data loss) and `errors.tolerance: none` (connector stops on any error). The final answer was `none` with proper DLQ and monitoring.

**Interview Point (Enhanced):**
> "The silent failure wasn't just 4 config changes. We actually rewrote the entire filter class (PR #58 removed it, #59 rebuilt it) and added a custom Avro header converter because the default converter couldn't handle our header format. The 5-day timeline oversimplifies what was actually 27 PRs (#35-61) of incremental fixes."

---

### Issue 9: Connector Version + Retry Policy (PRs #69, #70)

**Date:** May 30 - June 9, 2025
**Severity:** Medium

**What Happened:** Original connector version had bugs. Custom header conversion class was causing issues.

**The Fix:**
- Upgraded to newer connector version
- Removed custom header conversion class (not needed with new version)
- Added proper retry policy for GCS writes

**Interview Point:**
> "We removed our custom header converter after upgrading the connector - the new version handled headers natively. This simplified the system and removed a failure point."

---

### Issue 10: Data Type Mismatch (PR #75)

**Date:** June 11, 2025
**Severity:** Low

**What Happened:** Timeout multiplier was configured as a string but needed to be DECIMAL type in the CCM configuration.

---

### Issue 11: Site ID Mapping for International (PR #83, #85)

**Date:** November 2025 - December 2025
**Severity:** High (new feature, not a bug)

**What Happened:** Expanding from US-only to US/CA/MX required:
- Country code to site ID mapping (#83)
- Complete multi-site filter refactoring with BaseAuditLogSinkFilter (#85: +920/-30)
- Separate filters for US (permissive), CA (strict), MX (strict)

**Interview Point:**
> "The multi-site expansion was the biggest change post-launch. I designed an inheritance hierarchy: BaseAuditLogSinkFilter with an abstract getHeaderValue() method. US, CA, and MX filters extend it. US is permissive (accepts records with OR without headers). CA and MX are strict. This made adding new countries trivial - just extend the base class."

---

### Issue 12: Vulnerability + Startup Probe (PR #87)

**Date:** January 29, 2026
**Severity:** Medium

**What Happened:** Docker base image had vulnerabilities. Kubernetes startup probe wasn't configured.

**The Fix:**
- Updated Docker base image to `11-major`
- Added startup, readiness, and liveness probes
- Upgraded dependencies

---

## CROSS-TIER ISSUES (Multiple tiers involved)

### Cross-Tier Issue: Geographic Routing End-to-End

**Timeline:** May 15-19, 2025
**Tiers involved:** 2 (srv) + 3 (gcs-sink)

This required coordinated changes across tiers:
1. **Tier 2 (srv #67):** Add header forwarding to Kafka messages
2. **Tier 2 (srv #69):** Fix case-insensitive header matching
3. **Tier 3 (gcs-sink #59):** Add filter + custom header converter
4. **Tier 3 (gcs-sink #60):** Move header converter to worker level

**Interview Point:**
> "Geographic routing required coordinated changes across the publisher and sink. The header had to be forwarded correctly by the publisher, then parsed correctly by the sink's filter. We discovered case-sensitivity issues and header format problems that required fixes on both sides."

---

## Summary by Severity

| Severity | Count | Examples |
|----------|-------|---------|
| **Critical** | 3 | Topic misconfiguration (Day 1), Silent failure (5 days), KEDA feedback loop |
| **High** | 4 | Header forwarding missing, Failover bug, OOM, Multi-site expansion |
| **Medium** | 5 | 413 payload, Case-sensitivity, Header converter, Startup probes, Signature bypass |
| **Low** | 2 | Data type mismatch, Method not supported |

---

## Interview Answer: "What production issues did you face?"

### Short Version (2 min):
> "Three categories. **Day 1:** Config issues - topic names wrong for production. Fixed in hours. **Weeks 2-4:** The silent failure - a 5-day debugging incident involving 4 compounding issues: null header NPE, consumer poll timeouts, KEDA autoscaling feedback loop, and heap exhaustion. 27 PRs to fully resolve. Zero data loss. **Ongoing:** Header forwarding for geographic routing required coordinated fixes across the publisher and sink tiers - case sensitivity, header format, and filter logic."

### Long Version (When they want depth):
> "The most interesting was the silent failure. After fixing the obvious NPE, we discovered the filter code needed a complete rewrite - not just a try-catch. The original approach couldn't handle Avro-serialized headers properly. We removed the filter entirely (PR #58: -301 lines) and rebuilt it with a custom header converter (PR #59: +386 lines). Then we discovered the error tolerance dilemma: 'all' silently loses data, 'none' stops on one bad record. We settled on 'none' with DLQ and monitoring.
>
> The KEDA autoscaling lesson was the most surprising. Scaling Kafka consumers on consumer lag creates a feedback loop: more replicas → rebalancing → lag increases → more scaling. We switched to CPU-based HPA."

---

## Key Learnings by Tier

### Tier 1 (Library):
- Simple design = stable in production
- Zero production bugs since launch

### Tier 2 (Publisher):
- Test failover before you need it (dual-region bug)
- Know ALL size limits in your infrastructure (413 error)
- Headers are case-insensitive - always match accordingly

### Tier 3 (GCS Sink):
- Kafka Connect's defaults are NOT production-ready
- Don't scale consumers on lag (KEDA feedback loop)
- Error tolerance is a design decision, not a config toggle
- Always verify configs per environment (Day 1 topic issues)
- Complete filter rewrites may be needed, not just patches

### Data Validation — The 413 Error Discovery (April 2025)

During validation (April 8-14, 2025), I compared API Proxy counts vs Data Discovery (Hive) counts:

| Date | API Proxy | Data Discovery | Lost Records | Root Cause |
|------|-----------|---------------|-------------|------------|
| Apr 8 | 2,264,634 | 2,385,317 | ~39K to 413 | Payload too large |
| Apr 10 | 2,064,281 | 1,999,681 | ~39K to 413 | Same root cause |
| Apr 12 | 2,090,565 | 2,000,182 | ~91K to 413 | Larger payloads on weekends |
| Apr 13 | 1,742,647 | 1,638,352 | ~104K to 413+502 | Worst day: 104,345+5=104,350 |
| Apr 14 | 2,078,950 | 1,948,468 | ~130K to 413+502 | Peak: 130,232+11=130,243 |

**After fix (PR #49-51)**: API Proxy count exactly matched Data Discovery count — zero data loss.

> "This was discovered through systematic data validation, not alerting. Lesson: always verify data at every tier boundary."

### BULK-FEEDS Validation (April 27, 2025)

BULK-FEEDS service was the 4th team to adopt. Hourly validation showed **exact match** between API Proxy and Data Discovery:

| Time Window | API Proxy | Data Discovery | Match? |
|-------------|-----------|---------------|--------|
| 5-6 PM IST | 21,242 | 21,242 | ✅ Exact |
| 6-7 PM IST | 8,638 | 8,638 | ✅ Exact |
| 7-8 PM IST | 20,816 | 20,816 | ✅ Exact |
| 8-9 PM IST | 30,968 | 30,968 | ✅ Exact |

> "After the 413 fix, every new team onboarded with zero data loss from day one."

---

*This file supplements [06-debugging-stories.md](./06-debugging-stories.md) with the COMPLETE production history.*
