# System Overview - Kafka Audit Logging

## The Problem

### Business Context
```
Two things happened simultaneously:

1. SPLUNK DECOMMISSIONING
   - Walmart was decommissioning Splunk company-wide
   - Expensive licensing, not being renewed
   - Every team needed alternatives

2. SUPPLIER DEMAND
   - External suppliers (Pepsi, Coca-Cola, Unilever) use our APIs
   - They asked: "Why did my request fail? Show me my interactions"
   - They wanted self-service debugging capability

3. **Product Metrics** - Leadership wanted real-time dashboards to understand API adoption — which suppliers are using which endpoints, error patterns, and usage trends. This data drives investment decisions.
```

### The Challenge
- Replace Splunk for internal debugging needs
- Give suppliers SQL query access to their data
- Do this WITHOUT impacting API latency (SLA: sub-200ms responses)

---

## The Solution

### Three-Tier Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CONSUMING SERVICES                                │
│              (cp-nrti-apis, inventory-status-srv, etc.)                    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              dv-api-common-libraries (JAR)                          │   │
│  │  ┌──────────────┐  ┌─────────────────┐  ┌─────────────────────┐   │   │
│  │  │LoggingFilter │→ │AuditLogService  │→ │ HTTP POST to        │   │   │
│  │  │(Intercepts)  │  │(@Async)         │  │ audit-api-logs-srv  │   │   │
│  │  └──────────────┘  └─────────────────┘  └─────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        audit-api-logs-srv                                   │
│                     (Kafka Producer Service)                                │
│                                                                             │
│  ┌──────────────────────────┐    ┌─────────────────┐    ┌────────────────────┐    │
│  │AuditLogging              │ →  │KafkaProducer    │ →  │ Kafka Topic        │    │
│  │Controller                │    │Service          │    │ api_logs_audit_prod│    │
│  │(POST /v1/logs/api-       │    │(Avro + Headers) │    │ (Multi-Region)     │    │
│  │       requests)          │    │                 │    │                    │    │
│  └──────────────────────────┘    └─────────────────┘    └────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      audit-api-logs-gcs-sink                                │
│                    (Kafka Connect Sink Connector)                           │
│                                                                             │
│  ┌────────────────┐   ┌─────────────────┐   ┌──────────────────────────┐  │
│  │Kafka Consumer  │ → │SMT Filters      │ → │GCS Buckets (Parquet)     │  │
│  │(Connect Worker)│   │(US/CA/MX)       │   │ - audit-api-logs-us-prod │  │
│  └────────────────┘   │wm-site-id header│   │ - audit-api-logs-ca-prod │  │
│                       └─────────────────┘   │ - audit-api-logs-mx-prod │  │
│                                             └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                  Hive / Data Discovery + BigQuery                           │
│                    (Analytics & Compliance)                                 │
│                                                                             │
│   External tables pointing to GCS Parquet files                            │
│   - Query audit logs with SQL                                               │
│   - Suppliers can query THEIR OWN data via Hive / Data Discovery + BigQuery│
│   - Long-term retention for compliance (7 years)                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Business Value

| Metric | Before (Splunk) | After (Our Solution) |
|--------|-----------------|---------------------|
| Time to add audit logging | 2-3 weeks per service | 1 day (add dependency) |
| Log format consistency | 0% (ad-hoc) | 100% (standardized) |
| Cross-service correlation | Not possible | Full trace ID support |
| Query capability | Splunk SPL (limited) | SQL in BigQuery |
| Supplier access | Not possible | Direct query access |
| Data retention | 30 days (Splunk cost) | 7 years (GCS cheap) |
| Multi-region support | Manual | Automatic routing |
| Cost per event | ~$0.001 (Splunk) | ~$0.00001 (GCS) |

### Formal SLOs (From Architecture Design Template)

| Type | SLI | Objective |
|------|-----|-----------|
| **Availability** | Valid requests successfully served within 100ms | ≥ 99.9% |
| **Latency** | P95 response time for successful requests | ≤ 200ms |
| **Error Rate (4xx)** | 4xx responses vs 2xx | ≤ 1% |
| **Error Rate (5xx)** | 5xx responses vs 2xx | < 0.5% |
| **RPO** | Maximum data loss during disruption | 30 minutes |
| **RTO** | Recovery time after disruption | ≤ 24 hours (formal), achieved 15 minutes |
| **Volume** | Annual event processing capacity | 1 billion/year |

### Testing Strategy

- **Unit Tests**: 80%+ code coverage across all tiers. LoggingFilter tested with MockMvc + ContentCachingWrapper. SMT filters tested with mock ConnectRecord headers.
- **Integration Tests**: Testcontainers for Kafka in audit-api-logs-srv. Container tests for GCS sink.
- **Contract Testing**: R2C (Request-to-Contract) testing integrated into CI/CD pipeline. Contract test gate blocks deployment if API spec changes break consumers.
- **E2E Testing**: 36 test scenarios covering IAC/TransactionHistory endpoints, Kafka schema validation, Hive DB traceability, and supplier analytics queries.
- **Load Testing**: Tested at 30 and 50 virtual users. ~1.9K requests published/sec, ~4K consumed/sec with 0 failures. System handles 3x production load.
- **QA Sign-off**: Component testing for both audit-logs-srv and GCS Sink Service — positive, negative, edge, and boundary test cases all passing.

### CI/CD Pipeline

```
Code Push → Looper CI → Maven Build + SonarQube → Contract Tests (R2C)
    → Stage Deploy (EUS2 + SCUS) → Automaton Performance Tests
    → CRQ for Production → Flagger Canary (10% → 50%) → Full Rollout
```

- **Canary Deployment**: Flagger with Istio — 10% step weight, 50% max, 2-minute intervals, 1% error threshold
- **API Linting**: Automated spec validation on every PR
- **Security Scanning**: Snyk + CodeGate on every build

### Project Timeline (Shipped in ~5 Weeks)

| Milestone | Date |
|-----------|------|
| Dev Deployment | Jan 10, 2025 |
| Stage Deployment (Initial) | Jan 10, 2025 |
| Stage Deployment (Reviewed) | Jan 17, 2025 |
| QA Sign-off | Jan 24, 2025 |
| **Production Deployment** | **Feb 5, 2025** |
| Multi-region rollout (CRQ) | March 2025 |
| Production incidents & tuning | May 2025 |
| Multi-country (US/CA/MX) support | Nov 2025 |

> "From design to production in 5 weeks. The cross-team dependency with Core Services (Kafka, GCS infra) was the biggest risk — I managed that by starting infra requests in parallel with development."

### Consuming Services — Multi-Kafka Architecture

The NRT consuming service (`cp-nrti-apis`) has **4 separate Kafka templates** for different event types:

| Template | Region | Purpose |
|----------|--------|---------|
| `kafkaPrimaryTemplate` (IAC) | EUS2 | Inventory Activity Capture - primary |
| `kafkaSecondaryTemplate` (IAC) | SCUS | Inventory Activity Capture - failover |
| `kafkaDscPrimaryTemplate` (DSC) | EUS2 | Direct Shipment Capture - primary |
| `kafkaDscSecondaryTemplate` (DSC) | SCUS | Direct Shipment Capture - failover |

Each template pair implements CompletableFuture failover: primary fails → automatically chains to secondary region. The audit logging pipeline uses the same Kafka cluster but a separate topic (`api_logs_audit_prod`).

---

## The Interview Sound Bite

### 30-Second Version
> "When Walmart decommissioned Splunk, I designed a replacement that went beyond just logging - suppliers can now query their own API data. Three-tier architecture: reusable library for interception, Kafka for durability, GCS with Parquet for cheap queryable storage. 2 million events daily, zero latency impact, 99% cost reduction."

### 2-Minute Version
> "At Walmart Luminate, we serve external suppliers like Pepsi, Coca-Cola, and Unilever through APIs. Two things happened: Splunk was being decommissioned company-wide, and suppliers asked for visibility into their API interactions.
>
> So I needed to build a system that would: replace Splunk for internal debugging, give suppliers query access, and do this without impacting API latency - they expect sub-200ms responses.
>
> I designed a three-tier solution:
>
> **First**, a reusable Spring Boot JAR that any service can import. It has a servlet filter that intercepts requests, caches the body using ContentCachingWrapper, and after the response, sends the audit payload asynchronously. Fire-and-forget - no latency impact.
>
> **Second**, a Kafka publisher service that serializes to Avro (70% smaller than JSON) and publishes to a multi-region Kafka cluster.
>
> **Third**, a Kafka Connect sink with custom SMT filters that route US, Canada, and Mexico records to separate GCS buckets in Parquet format. BigQuery external tables sit on top - that's what suppliers query.
>
> Result: 2 million events daily, P99 under 5ms, suppliers self-serve debugging, 99% cost savings."

---

## Why This Architecture?

### Why Not Just Another Log Aggregator?

| Option | Why Not? |
|--------|----------|
| **ELK/Elasticsearch** | Expensive at scale, suppliers need Kibana training |
| **Datadog** | Cost prohibitive at 2M events/day |
| **Cloud Logging** | Not queryable by external users |

### Why This Approach?
- **GCS + Parquet**: Cheap at scale, BigQuery reads natively
- **Kafka**: Durability - if GCS fails, no data loss
- **Library approach**: Teams get audit by adding Maven dependency
- **Async**: Never impact API latency

---

## Key Technical Decisions

| Decision | Why | Alternative |
|----------|-----|-------------|
| **Servlet Filter** | Access raw HTTP body stream | AOP (can't access body) |
| **@Order(LOWEST_PRECEDENCE)** | Run AFTER security filters | Higher priority (miss auth failures) |
| **ContentCachingWrapper** | Read body without consuming stream | Custom buffering (complex) |
| **@Async** | Non-blocking, fire-and-forget | Sync (blocks API) |
| **Avro** | Schema enforcement, 70% smaller | JSON (no schema, larger) |
| **Parquet** | 90% compression, columnar | JSON files (expensive) |
| **Kafka Connect** | Built-in offset management, retries | Custom consumer |
| **SMT Filter** | Per-message geographic routing | Multiple topics |

---

## Data Flow (Step by Step)

```
1. Supplier Request
   POST /iac/v1/inventory → cp-nrti-apis

2. LoggingFilter (Before)
   - Wraps request in ContentCachingRequestWrapper
   - Records timestamp

3. Controller Processes
   - Business logic runs
   - Response generated

4. LoggingFilter (After)
   - Extracts cached bodies
   - Builds AuditLogPayload
   - Calls AuditLogService.sendAuditLogRequest() [ASYNC]
   - Copies body back to response

5. Response to Supplier
   - API response returns immediately (~150ms)
   - Audit work continues in background

6. AuditLogService (Thread Pool)
   - HTTP POST to audit-api-logs-srv
   - Includes WM_CONSUMER.ID, signature

7. audit-api-logs-srv
   - Converts to Avro
   - Publishes to Kafka with wm-site-id header

8. Kafka Persistence
   - Message replicated across brokers
   - Durable storage

9. Kafka Connect
   - Polls topic (batch of 50)
   - SMT filter checks wm-site-id
   - Routes to correct GCS bucket

10. GCS Write
    - Parquet format
    - Partitioned by service/date/endpoint

11. BigQuery Query
    - External table points to GCS
    - Suppliers query with SQL
```

---

## Supplier Self-Service Flow

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                           SUPPLIER SELF-SERVICE FLOW                            │
│                                                                                 │
│   ┌──────────────┐                                                             │
│   │ Supplier     │  "Why did my request fail?"                                 │
│   │ (e.g., Pepsi)│                                                             │
│   └──────┬───────┘                                                             │
│          │                                                                      │
│          ▼                                                                      │
│   ┌──────────────┐                                                             │
│   │  BigQuery    │  SELECT * FROM audit_logs                                   │
│   │  Console     │  WHERE consumer_id = 'pepsi-supplier-id'                    │
│   │              │  AND response_code >= 400                                    │
│   │              │  AND DATE(timestamp) > DATE_SUB(CURRENT_DATE(), INTERVAL 7)│
│   └──────┬───────┘                                                             │
│          │                                                                      │
│          ▼                                                                      │
│   ┌──────────────────────────────────────────────────────────────────────────┐ │
│   │                          QUERY RESULT                                     │ │
│   │                                                                           │ │
│   │  request_id  | endpoint        | response_code | error_message           │ │
│   │  abc-123     | /iac/v1/inv     | 400           | "Invalid store_id"      │ │
│   │  def-456     | /iac/v1/inv     | 401           | "Expired token"         │ │
│   │  ghi-789     | /dsd/v1/ship    | 500           | "Downstream timeout"    │ │
│   │                                                                           │ │
│   └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│   BEFORE: Call support → 2 day wait → we grep logs                            │
│   AFTER: Self-service SQL query in 30 seconds                                 │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## What I Would Do Differently

1. **Add OpenTelemetry from day one** - Debugging silent failure would've been faster
2. **Skip the publisher service** - Publish directly to Kafka from library (removes a hop)
3. **Use Apache Iceberg** - Better than raw Parquet for ACID and GDPR deletes
4. **Add formal SLOs from day one** - We defined them retroactively in the ADT. Having them upfront would have driven monitoring setup earlier.

---

*Next: [02-common-library.md](./02-common-library.md) - Deep dive into the Spring Boot Starter JAR*
