# Observability & Monitoring (Bullet 9)

> **Resume Bullet:** "Implemented comprehensive observability using Dynatrace, Prometheus, and Grafana, achieving 99.9% uptime SLA"
> **Cuts across ALL projects** - not a single repo, but a cross-cutting concern

---

## 30-Second Pitch

> "I implemented observability across our entire supplier API platform. This includes Dynatrace for distributed tracing and APM, Prometheus with custom alert rules for latency, error rates, Kafka consumer lag, and cache health, Flagger for automated canary deployments with metric-based rollback, and transaction marking for Dynatrace traces. The monitoring infrastructure is what caught our Spring Boot 3 post-migration issues proactively and what we used to debug the Kafka Connect silent failure."

---

## The Observability Stack (ACTUAL from repos)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     OBSERVABILITY ARCHITECTURE                           │
│                                                                          │
│  APPLICATION LAYER                                                       │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Transaction Marking (Dynatrace child spans)                       │ │
│  │  ├── InventorySearchDCService                                      │ │
│  │  │   ├── UberKeySupportWmItemNbrToGtinCall                        │ │
│  │  │   └── EIInventorySearchDCCall                                   │ │
│  │  ├── AuditLogService (async publish timing)                        │ │
│  │  └── Spring Boot Actuator metrics (/actuator/prometheus)           │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                              │                                           │
│  COLLECTION LAYER                                                        │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Dynatrace OneAgent (injected via kitt.yml: dtSaasOneAgentEnabled) │ │
│  │  ├── Auto-instrumented traces                                      │ │
│  │  ├── JVM metrics (heap, GC, threads)                               │ │
│  │  └── Custom child transactions (TransactionMarkingManager)         │ │
│  │                                                                     │ │
│  │  Prometheus (via springboot-metrics profile + actuator)            │ │
│  │  ├── HTTP request metrics (latency, status codes)                  │ │
│  │  ├── JVM metrics                                                   │ │
│  │  ├── Kafka consumer lag (lenses_topic_consumer_lag)                │ │
│  │  └── Custom metrics (audit rejected_count, queue depth)            │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                              │                                           │
│  ALERTING LAYER (ACTUAL Prometheus rules from repo)                     │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  service-latency-alerts.yaml                                       │ │
│  │  ├── Alert: "Latency on API {uri} above 100ms for 700s"          │ │
│  │  ├── Expr: rate(http_server_requests_seconds_sum) / rate(count)   │ │
│  │  └── Severity: critical → Slack + xMatters                        │ │
│  │                                                                     │ │
│  │  service-5xx-alerts.yaml                                           │ │
│  │  ├── Alert: "5xx on {uri} above 1 request"                       │ │
│  │  ├── Expr: backend:odnd_http_response_code_5xx:irate5m > 1       │ │
│  │  └── Severity: critical → Slack + xMatters (30s trigger)          │ │
│  │                                                                     │ │
│  │  kafka-consumer-lag-alerts.yaml                                    │ │
│  │  ├── Warning: Consumer lag > 100 for 5 min                        │ │
│  │  ├── Critical: Consumer lag > 500 for 5 min                       │ │
│  │  └── Expr: lenses_topic_consumer_lag > threshold                  │ │
│  │                                                                     │ │
│  │  megha-cache-alerts.yaml                                           │ │
│  │  ├── Alert: VM Availability < 90%                                 │ │
│  │  ├── Alert: GET call latency > 50ms                               │ │
│  │  └── Alert: CPU utilization > 80%                                 │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                              │                                           │
│  DEPLOYMENT LAYER                                                        │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Flagger (canary deployments)                                      │ │
│  │  ├── stepWeight: 10% increments                                    │ │
│  │  ├── maxWeight: 50%                                                │ │
│  │  ├── interval: 2 min checks                                       │ │
│  │  ├── Metrics: request-success-rate > 99%                           │ │
│  │  ├── Metrics: request-duration P99 < 500ms                         │ │
│  │  └── Auto-rollback on metric failure                               │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                              │                                           │
│  VISUALIZATION                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Grafana dashboards                                                │ │
│  │  ├── API latency P50/P95/P99 per endpoint                         │ │
│  │  ├── Error rate by status code (4xx vs 5xx)                        │ │
│  │  ├── Kafka consumer lag per topic/consumer group                   │ │
│  │  ├── JVM heap/GC/thread metrics                                    │ │
│  │  └── Cache hit/miss rates                                          │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## ACTUAL Alert Rules (from inventory-status-srv repo)

### 1. API Latency Alerts
```yaml
# ACTUAL from telemetry/rules/service-latency-alerts.yaml
- alert: "Latency on api {uri} is above 100ms"
  expr: rate(http_server_requests_seconds_sum{namespace=..., uri=...}[5m])
        / rate(http_server_requests_seconds_count{...}[5m]) > 0.1
  for: 700s    # Must sustain for ~12 minutes
  labels:
    severity: critical
    mms_slack_channel: data-ventures-cperf-dev-ops
```
**Interview Point:** "We alert when average latency exceeds 100ms for 12 minutes. Short spikes are acceptable, sustained degradation is not."

### 2. 5xx Error Alerts
```yaml
# ACTUAL from telemetry/rules/service-5xx-alerts.yaml
- alert: "5xx request for {uri}"
  expr: sum(backend:odnd_http_response_code_5xx:irate5m{...}) > 1
  for: 30s     # Trigger fast - any 5xx is concerning
  labels:
    severity: critical
```
**Interview Point:** "5xx alerts trigger in 30 seconds - we treat any server error as critical because our consumers are external suppliers."

### 3. Kafka Consumer Lag Alerts
```yaml
# ACTUAL from telemetry/rules/kafka-consumer-lag-alerts.yaml
- alert: "PROD - Kafka Consumer Group Lag Alert"
  # WARNING at 100
  expr: lenses_topic_consumer_lag{...} > 100
  for: 5m
  labels: { severity: warning }

  # CRITICAL at 500
  expr: lenses_topic_consumer_lag{...} > 500
  for: 5m
  labels: { severity: critical }
```
**Interview Point:** "Two-tier alerting for consumer lag. Warning at 100 messages - gives us time to investigate. Critical at 500 - we need to act immediately. This is what we set up AFTER the silent failure incident where we had no lag monitoring."

### 4. Megha-Cache Alerts
```yaml
# ACTUAL from telemetry/rules/megha-cache-alerts.yaml
- alert: "Meghacache VM Availability <90%"
  expr: (count(n_cpus{...})/max(n_vms{...}) * 100) < 90
  labels: { severity: critical }

- alert: "Meghacache High GET Call Latency"
  expr: max(duration_get_us{...}) > 50000   # 50ms
  for: 8m
  labels: { severity: critical }

- alert: "Cache CPU utilization over 80%"
  expr: 100 - min(usage_idle{...}) > 80
  for: 8m
  labels: { severity: critical }
```
**Interview Point:** "Cache monitoring covers three dimensions: availability, latency, and CPU. If cache latency exceeds 50ms, every API call is affected because authorization lookups go through cache."

---

## Flagger Canary Configuration (ACTUAL from cp-nrti-apis kitt.yml)

```yaml
flagger:
  enabled: true
  defaultHooks: true
  canaryAnalysis:
    stepWeight: 10      # Increase traffic by 10% each step
    maxWeight: 50       # Max 50% to canary
    interval: 2m        # Check metrics every 2 minutes
```

**How it works in practice:**
1. New deployment detected → Flagger creates canary pod
2. Istio splits traffic: 90% old, 10% new
3. Every 2 minutes: check success rate and P99 latency
4. If healthy → increase by 10%
5. If unhealthy → automatic rollback
6. At 50% → promote canary to primary

---

## Dynatrace Integration

### How It's Configured
```yaml
# From kitt.yml
build:
  docker:
    app:
      buildArgs:
        dtSaasOneAgentEnabled: "true"  # Injects Dynatrace OneAgent into app image
```

### Transaction Marking (Custom Spans)
```java
// From InventorySearchDistributionCenterServiceImpl.java (ACTUAL CODE)
try (var uberKeyTxn = transactionMarkingManager
        .getTransactionMarkingService()
        .currentTransaction()
        .addChildTransaction(INVENTORY_SEARCH_DC_SERVICE,
                             UBER_KEY_WM_ITEM_NBR_TO_GTIN)) {
    uberKeyTxn.start();
    // ... UberKey call traced as child span
}
```

This creates a trace tree in Dynatrace:
```
GET /inventory/search-distribution-center-status (parent span)
├── InventorySearchDCService
│   ├── UberKeySupportWmItemNbrToGtinCall  (child span: 50ms)
│   └── EIInventorySearchDCCall            (child span: 300ms)
└── Total: 400ms
```

**Interview Point:** "We use transaction marking to create custom Dynatrace spans. Each downstream call - UberKey, EI API - is a child span. This lets us see exactly where time is spent in a request. When latency spikes, I can pinpoint which downstream call is slow."

---

## Spring Boot Actuator Metrics

Enabled via kitt.yml profile: `enable-springboot-metrics`

```
/actuator/prometheus endpoint exposes:
├── http_server_requests_seconds     → Request latency histogram
├── http_server_requests_count       → Request count by endpoint/status
├── jvm_memory_used_bytes            → Heap usage
├── jvm_gc_pause_seconds             → GC pause times
├── jvm_threads_live                 → Active thread count
└── Custom metrics:
    ├── audit_log_rejected_count     → Thread pool rejections
    └── audit_log_queue_depth        → Current queue size
```

---

## How Observability Helped in Real Incidents

| Incident | How Monitoring Helped |
|----------|----------------------|
| **Kafka Silent Failure** | Consumer lag alerts were MISSING - that's why it was silent. Added lag alerts after. |
| **Spring Boot 3 Post-Migration** | Flagger canary caught zero issues at 10% because we monitored error rate + P99 |
| **Heap OOM (cp-nrti-apis)** | JVM memory metrics in Grafana showed steadily increasing heap usage over hours |
| **Correlation ID bug** | Dynatrace traces showed missing correlation headers in downstream calls |
| **WebClient timeout issues** | Latency alerts triggered when downstream calls exceeded 100ms |
| **KEDA feedback loop** | K8s events + consumer lag showed the scaling-rebalancing cycle |

---

## Interview Questions

### Q: "How do you monitor your systems?"

> "Four layers. **Dynatrace** for distributed tracing - every request is traced with custom child spans for downstream calls. **Prometheus** with custom alert rules for latency (>100ms for 12 min triggers), error rates (any 5xx in 30 seconds triggers), Kafka consumer lag (warning at 100, critical at 500), and cache health. **Grafana** dashboards for visualization - latency percentiles, error rates, JVM metrics. **Flagger** for deployment monitoring - automated canary with metric-based rollback."

### Q: "How do you know when something is wrong?"

> "Tiered alerting. 5xx errors alert in 30 seconds because any server error affecting suppliers is critical. Latency alerts after 12 minutes of sustained degradation - short spikes are normal, sustained is not. Consumer lag alerts at two tiers - warning at 100 messages gives us investigation time, critical at 500 means act now. All alerts go to Slack and xMatters for on-call."

### Q: "Tell me about adding monitoring to your audit system."

> "After the silent failure incident, I added monitoring that we should have had from day one: consumer lag alerts with two-tier thresholds, JVM memory metrics, connector status checks, and dropped record counters. The key learning was that 'is it running?' isn't enough - you need 'is it processing correctly?' That means monitoring the gap between what's produced and what's consumed."

### Q: "What would you change about your observability?"

> "Add OpenTelemetry from day one. Currently we use Dynatrace transaction marking which is vendor-specific. OpenTelemetry would give us vendor-neutral traces that work with any backend. Also, I'd add SLO-based alerting - instead of alerting on metrics, alert on error budget burn rate. If we're burning through our 99.9% SLO budget too fast, alert early."

---

## Numbers to Remember

| Metric | Value | Context |
|--------|-------|---------|
| **Uptime SLA** | 99.9% | Achieved across all services |
| **Latency alert** | >100ms for 12min | Prometheus rule |
| **5xx alert** | >1 request in 30s | Critical, immediate |
| **Consumer lag warning** | >100 messages for 5min | Kafka Connect |
| **Consumer lag critical** | >500 messages for 5min | Kafka Connect |
| **Cache latency alert** | >50ms for 8min | Megha-cache |
| **Canary step** | 10% every 2min | Flagger config |
| **Canary max** | 50% | Before full promotion |

---

## STAR Story: Building Monitoring After Incident

> **Situation:** "After the Kafka Connect silent failure, we had no alerting on consumer lag or processing correctness."
>
> **Task:** "Build comprehensive monitoring to prevent silent failures."
>
> **Action:** "I set up Prometheus alert rules for consumer lag (two-tier: warning at 100, critical at 500), JVM memory metrics in Grafana, connector status health checks, and custom metrics for dropped records in the audit library (rejected_count, queue depth at 80% warning). Also added Dynatrace transaction marking for downstream call tracing."
>
> **Result:** "99.9% uptime SLA achieved. The lag alerting has caught two subsequent issues before they became incidents. The 80% queue warning caught a downstream slowdown that would have caused data loss."
>
> **Learning:** "'Is it running?' is not monitoring. 'Is it processing correctly, fast enough, without losing data?' is monitoring."

---

*This is a cross-cutting story - use it when they ask about monitoring, reliability, or SRE practices.*
