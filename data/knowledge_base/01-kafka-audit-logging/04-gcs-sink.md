# GCS Sink - Kafka Connect (audit-api-logs-gcs-sink)

> **Resume Bullet:** 1 (Part of Audit Logging System)
> **Repo:** `audit-api-logs-gcs-sink`
> **76 PRs** (verified from gh)

---

## What This Service Does

**Tier 3** of the audit logging architecture. Kafka Connect worker that consumes Avro messages from Kafka and writes Parquet files to GCS buckets, routed by geography using custom SMT filters.

```
Kafka Topic (api_logs_audit_prod)
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│              audit-api-logs-gcs-sink (Kafka Connect)                 │
│                                                                      │
│  ┌────────────────────┐  ┌────────────────────┐  ┌──────────────┐  │
│  │ US Connector        │  │ CA Connector        │  │ MX Connector │  │
│  │ SMT: FilterUS       │  │ SMT: FilterCA       │  │ SMT: FilterMX│  │
│  │ wm-site-id: US      │  │ wm-site-id: CA      │  │ wm-site-id:MX│  │
│  │ OR no header (catch │  │ (strict match)       │  │ (strict)     │  │
│  │ all for legacy)     │  │                      │  │              │  │
│  └─────────┬──────────┘  └─────────┬──────────┘  └──────┬───────┘  │
│            │                       │                      │          │
│            ▼                       ▼                      ▼          │
│  ┌────────────────────┐  ┌────────────────────┐  ┌──────────────┐  │
│  │ GCS: us-prod       │  │ GCS: ca-prod       │  │ GCS: mx-prod │  │
│  │ Parquet format     │  │ Parquet format     │  │ Parquet      │  │
│  └────────────────────┘  └────────────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│    BigQuery     │  ← Suppliers query here!
│ External Tables │
└─────────────────┘
```

---

## Why Kafka Connect (Not Custom Consumer)?

| Aspect | Custom Consumer | Kafka Connect |
|--------|-----------------|---------------|
| **Offset Management** | You implement it | Built-in (automatic) |
| **Scaling** | You implement it | Automatic task distribution |
| **Fault Tolerance** | You implement it | Automatic rebalancing |
| **Monitoring** | Custom metrics | Standard JMX metrics |
| **Error Handling** | Manual DLQ | Built-in DLQ + retries |
| **Development Time** | 2-3 weeks | 2-3 days |

---

## Key Files (verified from repo)

```
audit-api-logs-gcs-sink/
├── src/main/java/com/walmart/audit/log/sink/converter/
│   ├── BaseAuditLogSinkFilter.java             # Abstract SMT filter
│   ├── AuditLogSinkUSFilter.java               # US records (catch-all)
│   ├── AuditLogSinkCAFilter.java               # Canada records
│   ├── AuditLogSinkMXFilter.java               # Mexico records
│   └── AuditApiLogsGcsSinkPropertiesUtil.java  # Dynamic site ID retrieval
├── src/main/resources/
│   ├── audit_api_logs_gcs_sink_prod_properties.yaml   # Prod site IDs
│   └── audit_api_logs_gcs_sink_stage_properties.yaml  # Stage site IDs
├── src/test/java/com/walmart/audit/log/sink/converter/
│   ├── BaseAuditLogSinkFilterTest.java         # Base filter tests
│   ├── AuditLogSinkUSFilterTest.java           # US filter tests
│   ├── AuditLogSinkCAFilterTest.java           # CA filter tests
│   └── AuditLogSinkMXFilterTest.java           # MX filter tests
├── kc_config.yaml                              # Kafka Connect worker config
├── ccm/
│   ├── PROD-1.0-ccm.yml                       # Production CCM
│   └── NON-PROD-1.0-ccm.yml                   # Non-prod CCM
└── kitt.yml                                    # K8s deployment
```

---

## Code Deep Dive

### 1. BaseAuditLogSinkFilter.java - SMT Base Class

```java
@Slf4j
public abstract class BaseAuditLogSinkFilter<R extends ConnectRecord<R>>
    implements Transformation<R> {

  protected static final String HEADER_NAME = "wm-site-id";

  // Each subclass provides its target site ID
  protected abstract String getHeaderValue();

  @Override
  public R apply(R record) {
    if (verifyHeader(record)) {
      return record;    // Pass through → write to GCS
    }
    return null;        // Filter out (Kafka Connect convention: null = drop)
  }

  public boolean verifyHeader(R record) {
    try {
      return StreamSupport.stream(record.headers().spliterator(), true)
          .anyMatch(header ->
              HEADER_NAME.equals(header.key()) &&
              StringUtils.equals(getHeaderValue(), String.valueOf(header.value()))
          );
    } catch (Exception e) {
      log.error("Filter error for partition {}: {}",
          record.kafkaPartition(), e.getMessage());
      return false;
    }
  }
}
```

**Key Point:** Returning `null` from `apply()` is the Kafka Connect convention for dropping a record.

---

### 2. AuditLogSinkUSFilter.java - US Filter (Special!)

```java
public class AuditLogSinkUSFilter<R extends ConnectRecord<R>>
    extends BaseAuditLogSinkFilter<R> {

  @Override
  protected String getHeaderValue() {
    return AuditApiLogsGcsSinkPropertiesUtil.getSiteIdForCountryCode("US");
  }

  @Override
  public boolean verifyHeader(R r) {
    // US filter is PERMISSIVE:
    // Accept if wm-site-id = "US" OR if header is missing
    return StreamSupport.stream(r.headers().spliterator(), true)
            .anyMatch(header -> HEADER_NAME.equals(header.key())
                && StringUtils.equals(getHeaderValue(), String.valueOf(header.value())))
        ||
        StreamSupport.stream(r.headers().spliterator(), true)
            .noneMatch(header -> HEADER_NAME.equals(header.key()));
  }
}
```

**Why US filter is permissive?**
- Legacy records might not have `wm-site-id` header
- US is the default market
- Ensures no data loss during migration to header-based routing

---

### 3. SMT Filter Pipeline

```
Kafka Message arrives:
{payload: {...}, headers: {wm-site-id: "US"}}

    │
    ▼
┌─────────────────┐
│ Transform 1:    │  InsertRollingRecordTimestamp
│ Add date header │  → Adds partition date for GCS path
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Transform 2:    │  FilterUS / FilterCA / FilterMX
│ Filter by site  │  → Returns record OR null (drops it)
└────────┬────────┘
         │
         ▼
Record passed to GCS Sink Connector
Written to: gs://audit-logs-us-prod/2025-05-15/...
```

---

### 4. kc_config.yaml - Kafka Connect Configuration

```yaml
worker:
  # Serialization
  key.converter: org.apache.kafka.connect.storage.StringConverter
  value.converter: io.confluent.connect.avro.AvroConverter
  value.converter.schemas.enable: true
  group.id: com.walmart-audit-log-gcs-sink-0.0.1

  # Consumer tuning (Critical for stability!)
  max.poll.records: 50
  max.poll.interval.ms: 300000    # 5 minutes
  heartbeat.interval.ms: 5000
  session.timeout.ms: 15000

connectors:
  # US Connector
  - name: audit-log-gcs-sink-connector
    config:
      connector.class: io.lenses.streamreactor.connect.gcp.storage.sink.GCPStorageSinkConnector
      tasks.max: 1
      errors.tolerance: all
      connect.gcpstorage.error.policy: RETRY
      connect.gcpstorage.max.retries: 5
      connect.gcpstorage.retry.interval: 5000

      transforms: InsertRollingRecordTimestamp, FilterUS
      transforms.FilterUS.type: com.walmart.audit.log.sink.converter.AuditLogSinkUSFilter

  # CA Connector
  - name: audit-log-gcs-sink-connector-ca
    config:
      transforms: InsertRollingRecordTimestamp, FilterCA
      transforms.FilterCA.type: com.walmart.audit.log.sink.converter.AuditLogSinkCAFilter

  # MX Connector
  - name: audit-log-gcs-sink-connector-mx
    config:
      transforms: InsertRollingRecordTimestamp, FilterMX
      transforms.FilterMX.type: com.walmart.audit.log.sink.converter.AuditLogSinkMXFilter
```

> **Note on Error Tolerance**: The production config currently uses `errors.tolerance: all` with DLQ enabled. We oscillated between `all` (silent data loss risk) and `none` (connector stops on any error). The current approach uses `all` + DLQ + monitoring: bad records go to `api_logs_audit_prod_DLQ` topic, we get alerts on DLQ growth, and the connector continues processing good records. The Operations Guide documents a 4-step troubleshooting runbook for when issues arise.

---

## Production-Tuned Consumer Config

The `kc_config.yaml` file includes critical consumer tuning parameters that were optimized through production troubleshooting:

```yaml
# Consumer tuning (Critical for stability!)
max.poll.records: 50
max.poll.interval.ms: 300000    # 5 minutes
heartbeat.interval.ms: 5000
session.timeout.ms: 15000
```

## Why 3 Separate Connectors?

| Reason | Explanation |
|--------|-------------|
| **Data residency** | US, CA, MX data in separate GCS buckets |
| **Parallel processing** | Each connector runs independently |
| **Isolated failures** | One connector failing doesn't affect others |
| **Different policies** | Can have different retry/error configs per region |

### Site ID Mapping (Actual Production Values)

The `wm-site-id` header uses **18-digit numeric identifiers**, not country codes:

| Country | Production Site ID | Stage Site ID |
|---------|-------------------|---------------|
| **US** | `1704989259133687000` | `1694066566785477000` |
| **CA** | `1704989474816248000` | `1694066641269922000` |
| **MX** | `1704989390144984000` | `1694066631493876000` |

These are loaded from environment-specific properties files at connector startup via `AuditApiLogsGcsSinkPropertiesUtil.getSiteIdForCountryCode()`.

### Flush Configuration (When Data Hits GCS)

| Property | Threshold | What It Means |
|----------|-----------|---------------|
| `flush.size` | 50 MB | Flush when buffer exceeds 50MB |
| `flush.count` | 5,000 records | Flush when 5000 records buffered |
| `flush.interval` | 600 seconds (10 min) | Flush every 10 min regardless |

**Behavior**: Whichever threshold is hit first triggers the flush. With typical 4KB records, flush.count (5000) triggers first (~20MB). The 10-minute interval ensures periodic flushes even with low throughput.

### Consumer Lag Alerts (Production)

| Level | Threshold | Action |
|-------|-----------|--------|
| **WARNING** | > 50,000 messages | Investigate — check consumer group, connector status |
| **CRITICAL** | > 75,000 messages | Immediate action — check heap, restart connector if needed |

### 4-Step Troubleshooting Runbook

1. **Consumer groups analysis**: Check K8s logs for exceptions/memory errors. Is consumer group rebalancing or inactive?
2. **Connector status check**: Use REST API (`/connectors/{name}/status`). If rebalancing > 10 min, restart. Enable TRACE logging.
3. **Grafana golden signals**: Check memory utilization, CPU. Update `kitt.yml` configs if needed.
4. **Heap dump analysis**: If OOM errors, update `KAFKA_HEAP_OPTS` in `kitt.yml`. Current production: `-Xmx7g -Xms5g` with G1GC.

---

## Why Parquet Format?

| Benefit | How It Helps |
|---------|-------------|
| **Columnar storage** | "All response_codes" reads only that column |
| **Compression** | 90% smaller than JSON |
| **BigQuery native** | BQ reads Parquet directly, no ETL |
| **Predicate pushdown** | "WHERE status > 400" skips entire row groups |
| **Schema in file** | Self-describing, no external schema needed |

---

## GCS Bucket Structure

```
gs://audit-api-logs-us-prod/
└── cp-nrti-apis/           # service_name
    └── 2025-05-15/         # date partition
        └── iac/            # endpoint
            └── part-00000-abc123.parquet
```

---

## Interview Questions

### Q: "Why SMT over post-processing?"
> "SMT processes messages inline with zero external dependencies. No additional service to maintain. The filtering happens at consumption time, so only relevant records reach each GCS bucket. Lower latency, simpler architecture."

### Q: "What happens when SMT returns null?"
> "Kafka Connect convention - returning null from apply() drops the message. It won't be written to the sink. That's how we route: US connector's filter returns null for non-US records."

### Q: "Why not filter at the producer side?"
> "Two reasons. First, separation of concerns - the producer's job is to publish reliably, not to know about downstream routing. Second, flexibility - if we add a new country, we just deploy a new connector. No changes to producers."

### Q: "What happens if a record has an unknown site ID?"
> "Currently it would be dropped by all three connectors. In practice, we validate site ID at the API layer. But you're right - we should have a catch-all connector for unknowns. That's on our roadmap."

### Q: "How does Connect handle failures?"
> "RETRY policy with 5 retries and exponential backoff. If GCS is temporarily down, it retries. If a message is malformed, errors.tolerance routes it to DLQ. If the worker crashes, K8s restarts the pod and Connect resumes from last committed offset."

---

## Key PRs

| PR# | Title | Why Important |
|-----|-------|---------------|
| **#1** | Initial setup | Architecture decisions |
| **#12** | [CRQ:CHG3041101] US production | First production deployment |
| **#27-28** | Consumer tuning | Performance optimization |
| **#35** | Try-catch in filter | Fixed NPE on null headers |
| **#42** | Remove KEDA scaling | Fixed rebalance storm |
| **#57, #61** | Heap tuning | Fixed OOM kills |
| **#70** | Retry policy | Resilience patterns |
| **#85** | Site-based routing | Geographic filtering |

---

*Next: [05-multi-region.md](./05-multi-region.md) - Multi-Region Architecture*
