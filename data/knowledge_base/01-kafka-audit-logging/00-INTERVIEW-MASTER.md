# Kafka Audit Logging System — Interview Prep

---

## Your Pitches

### 30-Second Pitch

> "When Walmart decommissioned Splunk, I designed a replacement that went beyond just logging - suppliers can now query their own API data. Three-tier architecture: reusable library for interception, Kafka for durability, GCS with Parquet for cheap queryable storage. 2-3 million events daily, zero latency impact, 99% cost reduction."

### 90-Second Pitch

> "My biggest project at Walmart was designing an audit logging system from scratch. When Splunk was being decommissioned, I saw an opportunity to build something better - not just replace logging, but give our external suppliers like Pepsi and Coca-Cola direct access to their API interaction data.
>
> I designed a three-tier architecture: a reusable Spring Boot library that intercepts HTTP requests asynchronously, a Kafka publisher for durability with Avro serialization, and a Kafka Connect sink that writes to GCS in Parquet format. Hive/Data Discovery and BigQuery sit on top - suppliers can run SQL queries on their own data.
>
> The system handles 2-3 million events daily with less than 5ms P99 latency impact. We went from Splunk costing $50K/month to about $500/month. And four other teams adopted the library within a month."

### 2-Minute Pitch

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
> **Third**, a Kafka Connect sink with custom SMT filters that route US, Canada, and Mexico records to separate GCS buckets in Parquet format. Hive/Data Discovery and BigQuery external tables sit on top - that's what suppliers query.
>
> Result: 2-3 million events daily, P99 under 5ms, suppliers self-serve debugging, 99% cost savings."

---

## Key Numbers

| Metric | Value |
|--------|-------|
| Events processed daily | **2M+** |
| P99 latency impact | **<5ms** |
| Cost vs Splunk | **99% reduction** ($50K/mo to ~$500/mo) |
| Compression (Parquet) | **90%** |
| Avro vs JSON size | **70% smaller** |
| Teams adopted library | **4+** |
| Integration time | **2 weeks to 1 day** |
| Data retention | **7 years** |
| Thread pool | **6 core, 10 max, 100 queue** |
| PRs across 3 repos | **150+** |
| Daily data volume | **~10 GB/day** |
| Load test throughput | **~1.9K pub/sec, ~4K consume/sec** |
| Availability SLO | **99.9%** |

---

## The Pyramid Method

Structure your architecture answer in layers -- let the interviewer pull you deeper:

**Level 1 - Headline:**
> "It's a three-tier system that processes 2 million audit events daily with zero impact on API latency."

**Level 2 - Structure:**
> "Tier 1 is a reusable Spring Boot library that intercepts HTTP requests. It uses a servlet filter with ContentCachingWrapper to capture request and response bodies, then fires the audit payload asynchronously to Tier 2.
>
> Tier 2 is a Kafka publisher service. It serializes the payload to Avro - 70% smaller than JSON - and publishes to a multi-region Kafka cluster with geographic routing headers.
>
> Tier 3 is Kafka Connect with custom SMT filters that route US, Canada, and Mexico records to separate GCS buckets in Parquet format. Hive/Data Discovery and BigQuery external tables sit on top for SQL queries."

**Level 3 - Go deep on ONE part:**
> "The most interesting design decision was in Tier 1. HTTP bodies are streams - you can only read them once. If the filter reads the body, the controller gets empty input. I used Spring's ContentCachingWrapper, which caches the bytes so both can read. Combined with @Async and a bounded thread pool - 6 core threads, max 10, queue of 100 - the API response returns immediately while audit happens in the background."

**Level 4 - Offer:**
> "I can go deeper into the Kafka Connect SMT filter design, the multi-region failover, or the debugging incident we had - which interests you?"

---

## Architecture Overview

### Business Context

Two things happened simultaneously:

1. **Splunk Decommissioning** - Walmart was decommissioning Splunk company-wide. Expensive licensing, not being renewed. Every team needed alternatives.
2. **Supplier Demand** - External suppliers (Pepsi, Coca-Cola, Unilever) use our APIs. They asked: "Why did my request fail? Show me my interactions." They wanted self-service debugging capability.

The challenge: replace Splunk for internal debugging, give suppliers SQL query access to their data, and do this WITHOUT impacting API latency (SLA: sub-200ms responses).

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
│  ┌──────────────────┐    ┌─────────────────┐    ┌────────────────────┐    │
│  │AuditLogging      │ →  │KafkaProducer    │ →  │ Kafka Topic        │    │
│  │Controller        │    │Service          │    │ api_logs_audit_prod│    │
│  │(POST /v1/logs/api-requests) │    │(Avro + Headers) │    │ (Multi-Region)     │    │
│  └──────────────────┘    └─────────────────┘    └────────────────────┘    │
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
│                    Hive / Data Discovery + BigQuery                         │
│                    (Analytics & Compliance)                                 │
│                                                                             │
│   External tables pointing to GCS Parquet files                            │
│   - Query audit logs with SQL via Data Discovery and BigQuery              │
│   - Suppliers can query THEIR OWN data                                      │
│   - Long-term retention for compliance (7 years)                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow (11 Steps)

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

11. Data Discovery / BigQuery Query
    - Hive external tables + BigQuery
    - External table points to GCS
    - Suppliers query with SQL
```

### Supplier Self-Service Flow

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
│   │ Data Discovery / BigQuery Console    │  SELECT * FROM audit_logs                                   │
│   │              │  WHERE consumer_id = 'pepsi-supplier-id'                    │
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

### Why This Architecture (Not Alternatives)?

| Option | Why Not? |
|--------|----------|
| **ELK/Elasticsearch** | Expensive at scale, suppliers need Kibana training |
| **Datadog** | Cost prohibitive at 2M events/day |
| **Cloud Logging** | Not queryable by external users |

Why this approach works:
- **GCS + Parquet**: Cheap at scale, BigQuery reads natively
- **Kafka**: Durability - if GCS fails, no data loss
- **Library approach**: Teams get audit by adding Maven dependency
- **Async**: Never impact API latency

### Business Value

| Metric | Before (Splunk) | After (Our Solution) |
|--------|-----------------|---------------------|
| Time to add audit logging | 2-3 weeks per service | 1 day (add dependency) |
| Log format consistency | 0% (ad-hoc) | 100% (standardized) |
| Cross-service correlation | Not possible | Full trace ID support |
| Query capability | Splunk SPL (limited) | SQL via Data Discovery + BigQuery |
| Supplier access | Not possible | Direct query access |
| Data retention | 30 days (Splunk cost) | 7 years (GCS cheap) |
| Multi-region support | Manual | Automatic routing |
| Cost per event | ~$0.001 (Splunk) | ~$0.00001 (GCS) |

### What I Would Do Differently

1. **Add OpenTelemetry from day one** - Debugging silent failure would've been faster
2. **Skip the publisher service** - Publish directly to Kafka from library (removes a hop)
3. **Use Apache Iceberg** - Better than raw Parquet for ACID and GDPR deletes
4. **Add formal SLOs from day one** - We defined them retroactively in the ADT. Having them upfront would have driven monitoring setup earlier.

---

## Tier 1: Common Library

### How Zero-Code Integration Works

```xml
<!-- That's ALL a consuming service needs to add -->
<dependency>
    <groupId>com.walmart</groupId>
    <artifactId>dv-api-common-libraries</artifactId>
    <version>0.0.54</version>
</dependency>
```

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                    SPRING BOOT AUTO-CONFIGURATION MAGIC                         │
│                                                                                 │
│  1. @ComponentScan picks up LoggingFilter (it's a @Component)                  │
│     → Filter automatically added to filter chain                               │
│                                                                                 │
│  2. @EnableAsync + @Bean registers ThreadPoolTaskExecutor                      │
│     → Async method calls go to thread pool                                     │
│                                                                                 │
│  3. @ManagedConfiguration loads CCM config (feature flags, endpoints)          │
│     → Runtime configuration without code changes                               │
│                                                                                 │
│  4. Spring's filter chain auto-registers LoggingFilter                         │
│     → First HTTP request → Filter intercepts → Audit works!                    │
└────────────────────────────────────────────────────────────────────────────────┘
```

### LoggingFilter.java

```java
@Slf4j
@Order(Ordered.LOWEST_PRECEDENCE)  // Run LAST in filter chain
@Component
public class LoggingFilter extends OncePerRequestFilter {

  @ManagedConfiguration
  FeatureFlagCCMConfig featureFlagCCMConfig;  // Feature flag from CCM

  @ManagedConfiguration
  AuditLoggingConfig auditLoggingConfig;      // Audit config from CCM

  @Autowired
  AuditLogService auditLogService;            // Async sender

  @Override
  protected void doFilterInternal(HttpServletRequest request,
                                  HttpServletResponse response,
                                  FilterChain filterChain)
                                  throws ServletException, IOException {

    if (Objects.nonNull(featureFlagCCMConfig) && Objects.nonNull(auditLoggingConfig) &&
        Boolean.TRUE.equals(featureFlagCCMConfig.isAuditLogEnabled())) {

      if (!request.getRequestURI().contains(AppConstants.ACTUATOR)) {

        String traceId = "";
        String responseBody = StringUtils.EMPTY;
        long requestTimestamp = Instant.now().getEpochSecond();

        if (!shouldNotFilter(request)) {
          ContentCachingRequestWrapper contentCachingRequestWrapper =
              new ContentCachingRequestWrapper(request);
          ContentCachingResponseWrapper contentCachingResponseWrapper =
              new ContentCachingResponseWrapper(response);

          filterChain.doFilter(contentCachingRequestWrapper,
              contentCachingResponseWrapper);
          long responseTimestamp = Instant.now().getEpochSecond();

          String requestBody = convertByteArrayToString(
              contentCachingRequestWrapper.getContentAsByteArray(),
              request.getCharacterEncoding());

          // Response body logging is CONFIGURABLE via CCM!
          if (Objects.nonNull(auditLoggingConfig) &&
              Boolean.TRUE.equals(auditLoggingConfig.isResponseLoggingEnabled())) {
            responseBody = convertByteArrayToString(
                contentCachingResponseWrapper.getContentAsByteArray(),
                request.getCharacterEncoding());
          }

          AuditLogPayload auditLogPayload =
              prepareRequestForAuditLog(requestBody, responseBody, request,
                  response, traceId, requestTimestamp,
                  responseTimestamp, auditLoggingConfig);

          auditLogService.sendAuditLogRequest(auditLogPayload, auditLoggingConfig);

          contentCachingResponseWrapper.copyBodyToResponse();
        }
      }
    }
  }

  @Override
  protected boolean shouldNotFilter(HttpServletRequest request)
      throws ServletException {
    return auditLoggingConfig.enabledEndpoints().stream()
        .noneMatch(request.getServletPath()::contains);
  }
}
```

**Why `LOWEST_PRECEDENCE`?** Ensures we run AFTER all security filters. We capture the FINAL state of request/response. If auth fails, we still log the failed attempt.

**Why `ContentCachingWrapper`?** HTTP streams can only be read ONCE. Without wrapping, controller would get empty body. Wrapper caches the bytes for re-reading.

### AuditLogService.java

```java
@Service
@Slf4j
public class AuditLogService {

  private final AuditHttpServiceImpl httpService;
  private final ObjectMapper objectMapper;

  @Async  // CRITICAL: Non-blocking
  public void sendAuditLogRequest(AuditLogPayload payload,
                                  AuditLoggingConfig config) {
    try {
      URI uri = URI.create(config.getUriPath());
      JsonNode payloadJson = objectMapper.convertValue(payload, JsonNode.class);
      HttpHeaders headers = getAuditLogHeaders(config);

      httpService.sendHttpRequest(
          uri,
          HttpMethod.POST,
          new HttpEntity<>(payloadJson, headers),
          Void.class
      );
    } catch (Exception e) {
      // Log but don't throw - audit failure shouldn't break API
      log.error("Failed to send audit log: {}", payload.getRequestId(), e);
    }
  }

  private HttpHeaders getAuditLogHeaders(AuditLoggingConfig config) {
    HttpHeaders headers = new HttpHeaders();
    SignatureDetails signature = AuthSign.getAuthSign(
        config.getWmConsumerId(),
        getPrivateKey(config.getAuditPrivateKeyPath()),
        config.getKeyVersion()
    );

    headers.set("WM_CONSUMER.ID", config.getWmConsumerId());
    headers.set("WM_SEC.AUTH_SIGNATURE", signature.getSignature());
    headers.set("WM_SEC.KEY_VERSION", config.getKeyVersion());
    headers.set("WM_CONSUMER.INTIMESTAMP", signature.getTimestamp());
    headers.setContentType(MediaType.APPLICATION_JSON);

    return headers;
  }
}
```

**Security — Private Key Management**: Keys stored in **AKeyless** (Walmart's secret management platform), mounted at runtime to `/etc/secrets/audit_log_private_key.txt`. Never in code repos.

### ThreadPool Config

```java
@Configuration
@EnableAsync
public class AuditLogAsyncConfig {

    @Bean
    public Executor taskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(6);       // Always-running threads
        executor.setMaxPoolSize(10);       // Can scale up to this
        executor.setQueueCapacity(100);    // Buffer before rejection
        executor.setThreadNamePrefix("Audit-log-executor-");
        executor.initialize();
        return executor;
    }
}
```

**Why 6 core, 10 max, 100 queue?**

| Setting | Value | Reasoning |
|---------|-------|-----------|
| **Core: 6** | ~100 req/sec x 50ms/audit = 5 threads needed. +1 headroom | Based on traffic analysis |
| **Max: 10** | Handles spikes without thread explosion | 2x normal is enough |
| **Queue: 100** | Buffer bursts. Each payload ~2KB = 200KB total | Won't cause OOM |

When queue is full: default `AbortPolicy` throws `RejectedExecutionException`. Our code catches exceptions so audit is silently dropped. This is acceptable -- audit is best-effort, not critical path.

### AuditLogPayload.java

```java
@Data
@Builder
public class AuditLogPayload {

    @JsonProperty("request_id")
    private String requestId;           // UUID for correlation

    @JsonProperty("service_name")
    private String serviceName;         // e.g., "cp-nrti-apis"

    @JsonProperty("endpoint_name")
    private String endpointName;        // e.g., "/iac/v1/inventory"

    @JsonProperty("path")
    private String path;                // Full path with query params

    @JsonProperty("method")
    private String method;              // GET, POST, etc.

    @JsonProperty("request_body")
    private String requestBody;         // Captured request JSON

    @JsonProperty("response_body")
    private String responseBody;        // Captured response JSON

    @JsonProperty("response_code")
    private int responseCode;           // HTTP status (200, 400, 500)

    @JsonProperty("error_reason")
    private String errorReason;         // Error message if any

    @JsonProperty("request_ts")
    private long requestTimestamp;      // Epoch seconds

    @JsonProperty("response_ts")
    private long responseTimestamp;     // Epoch seconds

    @JsonProperty("headers")
    private Map<String,String> headers; // All HTTP headers

    @JsonProperty("trace_id")
    private String traceId;             // Distributed tracing ID
}
```

### Key Design Decisions (Tier 1)

| Decision | Why | Alternative Considered |
|----------|-----|----------------------|
| **Servlet Filter** | Access to raw HTTP stream | AOP (no body access) |
| **@Order(LOWEST_PRECEDENCE)** | Run AFTER security filters | Higher priority (miss auth failures) |
| **ContentCachingWrapper** | Read body without consuming stream | Custom buffering (complex) |
| **@Async** | Non-blocking, fire-and-forget | Sync (blocks API response) |
| **WebClient over RestTemplate** | Modern, reactive, better resource handling | RestTemplate (deprecated in Spring 6) |
| **CCM config for endpoints** | Runtime enable/disable without deploy | Hardcoded list (inflexible) |
| **isResponseLoggingEnabled** | Per-team config toggle | Hardcoded (blocked adoption) |

### Library Version Note

The common library is currently on **version 0.0.54** with support for both **JDK 11** and **JDK 17**. It still uses `javax.servlet` imports (Spring Boot 2.7.11 parent). The consuming services (like cp-nrti-apis) have migrated to Spring Boot 3.5.7 / Java 17 with `jakarta.servlet` — the library's servlet API is backwards compatible at the binary level.

The library uses **WebClient** (Spring WebFlux) for HTTP calls to the publisher service — not RestTemplate. The WebClient call uses `.block()` to convert the reactive chain to synchronous within the filter context.

---

## Tier 2: Kafka Publisher

### AuditLoggingController.java

```java
@Slf4j
@RestController
@RequestMapping(produces = MediaType.APPLICATION_JSON_VALUE)
public class AuditLoggingController implements AuditLogsApi {

  @Autowired
  LoggingRequestService loggingRequestService;

  @PostMapping("v1/logRequest")
  public ResponseEntity<Boolean> saveRequest(@RequestBody LoggingApiRequest request) {
    Boolean result = loggingRequestService.processLoggingRequest(request);
    return ResponseEntity.status(HttpStatus.NO_CONTENT).body(result);
  }

  @Override  // From OpenAPI generated interface
  public ResponseEntity<Void> saveApiLog(LoggingApiRequest request) {
    loggingRequestService.processLoggingRequest(request);
    return new ResponseEntity<>(HttpStatus.NO_CONTENT);
  }
}
```

> **Note**: The service has TWO endpoints for backward compatibility:
> - **Legacy**: `POST /v1/logRequest` (original, still supported)
> - **OpenAPI-compliant**: `POST /v1/logs/api-requests` (implements generated `AuditLogsApi` interface)

### KafkaProducerService.java

```java
@Slf4j
@Service
public class KafkaProducerService implements TargetedResources {

  @ManagedConfiguration
  AuditLogsKafkaCCMConfig auditLogsKafkaCCMConfig;

  @Autowired
  private KafkaTemplate<String, Message<LogEvent>> kafkaPrimaryTemplate;

  @Autowired
  private KafkaTemplate<String, Message<LogEvent>> kafkaSecondaryTemplate;

  public void publishMessageToTopic(LoggingApiRequest request) {

    String topicName = auditLogsKafkaCCMConfig.getAuditLoggingKafkaTopicName();
    Message<LogEvent> kafkaMessage = prepareAuditLoggingKafkaMessage(request, topicName);

    try {
      kafkaPrimaryTemplate.send(kafkaMessage);  // EUS2 region
    } catch (Exception ex) {
      log.error("Primary Kafka failed, trying secondary", ex);
      kafkaSecondaryTemplate.send(kafkaMessage);  // SCUS fallback
    }
  }

  public static Message<LogEvent> prepareAuditLoggingKafkaMessage(
      LoggingApiRequest request, String topicName) {

    // 1. Convert to Avro
    LogEvent event = AvroUtils.getLogEvent(request);

    // 2. Create message key for partitioning
    AuditKafkaPayloadKey key = AuditKafkaPayloadKey.getAuditKafkaPayloadKey(
        request.getEndpointName(),
        request.getServiceName()
    );

    // 3. Build message with headers
    MessageBuilder<LogEvent> builder = MessageBuilder.withPayload(event);

    // 4. Set Kafka headers
    builder.setHeader(KafkaHeaders.TOPIC, topicName);
    builder.setHeader(KafkaHeaders.KEY, key.toString());

    // 5. Pass through important headers for routing
    Set<String> allowedHeaders = Set.of(
        "wm_consumer.id",
        "wm_qos.correlation_id",
        "wm_svc.name",
        "wm_svc.version",
        "wm_svc.env",
        "wm-site-id"  // CRITICAL for geo-routing
    );

    request.getHeaders().forEach((k, v) -> {
      if (allowedHeaders.contains(k.toLowerCase())) {
        builder.setHeader(k, v);
      }
    });

    return builder.build();
  }
}
```

> **Note on Thread Pool**: The publisher service uses `Executors.newCachedThreadPool()` (unbounded, dynamic sizing) for async processing — NOT the same as the common library's bounded `ThreadPoolTaskExecutor(6/10/100)`.

### Why Avro

| Aspect | JSON | Avro |
|--------|------|------|
| **Size** | ~100 bytes per record | ~30 bytes (70% smaller) |
| **Schema** | None - anything goes | Enforced via Schema Registry |
| **Evolution** | Breaking changes | Backward/forward compatible |
| **Speed** | Slow (text parsing) | Fast (binary) |

```
PRODUCER:
1. Has schema: {type: record, name: LogEvent, fields: [...]}
2. Registers schema → Gets schema_id = 123
3. Serializes payload to binary
4. Sends: [0][123][binary_data] to Kafka

CONSUMER:
1. Receives: [0][123][binary_data]
2. Extracts schema_id = 123
3. Fetches schema from Registry (cached)
4. Deserializes binary_data using schema
```

### Producer Configuration (Actual Production Values)

| Config | Value | Why |
|--------|-------|-----|
| `compression.type` | **LZ4** | Fast compression, ~60% size reduction |
| `acks` | **all** | Wait for all replicas — zero message loss |
| `retries` | 10 | Retry on transient failures |
| `linger.ms` | 20 | Batch for 20ms before sending |
| `max.request.size` | 10MB | Accommodate large payloads |
| `security.protocol` | SSL | TLS 1.2 encrypted |

### Key Design Decisions (Tier 2)

| Decision | Why | Alternative |
|----------|-----|-------------|
| **Separate service** | Decouples library from Kafka | Direct Kafka from library (fewer hops but more coupling) |
| **Avro serialization** | Schema enforcement + 70% smaller | JSON (no schema, larger) |
| **Dual KafkaTemplate** | Primary + Secondary region failover | Single region (no DR) |
| **Header forwarding** | Enables geo-routing downstream | Multiple topics (complex) |
| **OpenAPI interface** | Contract-first design | Manual controller |

---

## Tier 3: GCS Sink

### BaseAuditLogSinkFilter.java

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

### AuditLogSinkUSFilter.java (Permissive)

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

US filter is permissive because legacy records might not have `wm-site-id` header. US is the default market. This ensures no data loss during migration to header-based routing.

### SMT Filter Pipeline

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

### kc_config.yaml

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

> **Note on Error Tolerance**: The production config currently uses `errors.tolerance: all` with DLQ enabled. Bad records go to `api_logs_audit_prod_DLQ` topic with monitoring for DLQ growth. The connector continues processing good records.

### Production-Tuned Consumer Config

```yaml
# Final production values (after debugging incidents)
max.poll.records: 50
max.poll.interval.ms: 300000    # 5 minutes
heartbeat.interval.ms: 5000
session.timeout.ms: 15000
```

These are the final tuned values after the 5-day debugging incident. Each value has a story behind it:
- **max.poll.records: 50** — Smaller batches to avoid poll timeout with slow GCS writes
- **max.poll.interval.ms: 300000** — 5 minutes to accommodate large batch processing time
- **heartbeat.interval.ms: 5000** — Frequent heartbeats to prevent false session expiry
- **session.timeout.ms: 15000** — 3x heartbeat interval (Kafka best practice minimum)

### Why 3 Separate Connectors

| Reason | Explanation |
|--------|-------------|
| **Data residency** | US, CA, MX data in separate GCS buckets |
| **Parallel processing** | Each connector runs independently |
| **Isolated failures** | One connector failing doesn't affect others |
| **Different policies** | Can have different retry/error configs per region |

### Site ID Mapping (Actual Production Values)

| Country | Production Site ID |
|---------|-------------------|
| **US** | `1704989259133687000` |
| **CA** | `1704989474816248000` |
| **MX** | `1704989390144984000` |

### Consumer Lag Alerts

| Level | Threshold |
|-------|-----------|
| **WARNING** | > 50,000 messages |
| **CRITICAL** | > 75,000 messages |

### Why Parquet

| Benefit | How It Helps |
|---------|-------------|
| **Columnar storage** | "All response_codes" reads only that column |
| **Compression** | 90% smaller than JSON |
| **BigQuery native** | BQ reads Parquet directly, no ETL |
| **Predicate pushdown** | "WHERE status > 400" skips entire row groups |
| **Schema in file** | Self-describing, no external schema needed |

### GCS Bucket Structure

```
gs://audit-api-logs-us-prod/
└── cp-nrti-apis/           # service_name
    └── 2025-05-15/         # date partition
        └── iac/            # endpoint
            └── part-00000-abc123.parquet
```

---

## Multi-Region Architecture

### Active/Active vs Active/Passive

| Option | Pros | Cons | Failover Time |
|--------|------|------|---------------|
| **Active-Passive** | Simple, cheap | Slow failover, wasted resources | ~30 min |
| **Active-Active** | Immediate failover, load distribution | Complex, 2x cost | ~15 min |
| **Hybrid** | Active-Active for writes, single read | Moderate complexity | ~20 min |

We chose Active/Active because audit is write-heavy and compliance couldn't tolerate 30-minute failover delays.

### Architecture Diagram

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

### Phased Rollout (4 Weeks)

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

### Improved Failover Code (PR #65)

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

> **Important Clarification**: This CompletableFuture failover is implemented in the **consuming services** (like cp-nrti-apis). In audit-api-logs-srv itself, the current code catches primary failures and logs but does NOT chain to secondary. This is a known gap being addressed.

### Geographic Routing Flow

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

### DR Test Results

| Metric | Target | Achieved |
|--------|--------|----------|
| **RTO (Recovery Time)** | 1 hour | **15 minutes** |
| **RPO (Data Loss)** | 4 hours | **Zero** |
| **Downtime during migration** | Minimal | **Zero** |
| **Data parity** | >99% | **100%** |

### Exactly-Once Processing Strategy

1. **Kafka idempotent producer** - Prevents duplicate writes to same cluster
2. **Deduplication in sink** - Based on `request_id`, if already processed, SMT drops it
3. **Geographic routing** - Each region primarily handles its geography, reducing overlap

---

## Top 10 Technical Decisions

Answer framework: "We considered [alternatives]. We chose [X] because [reason]. The trade-off is [downside]. We mitigated by [action]."

### Quick Reference

| # | Decision | Chose | Over | Key Reason |
|---|----------|-------|------|------------|
| 1 | Servlet Filter | Raw HTTP access | AOP, Sidecar | Body stream + app context |
| 2 | @Async fire-and-forget | Zero latency | Sync, Direct Kafka | Keep library lightweight |
| 3 | ThreadPool 6/10/100 | Traffic-based | Unbounded | Bounded memory + monitoring |
| 4 | Avro | Schema + 70% smaller | JSON, Protobuf | Kafka ecosystem native |
| 5 | Kafka Connect | Built-in infra | Custom consumer, Flink | 2 days vs 2 weeks |
| 6 | SMT filter (sink-side) | Loose coupling | Producer routing | Add country = new connector |
| 7 | Parquet | 90% compression | JSON, ORC, BQ direct | Cheap storage + native BQ |
| 8 | Active/Active | 15-min failover | Active/Passive | Compliance requirement |
| 9 | ContentCachingWrapper | Well-tested | Custom buffering | Edge cases handled |
| 10 | isResponseLoggingEnabled | Per-team config | Hardcoded | Enabled 3-team adoption |
| 11 | UNION ALL views | Zero disruption | ETL migration, Dual-write | Splunk backward-compat |

### Decision 1: Servlet Filter vs AOP vs Sidecar

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| **Servlet Filter** | Access raw HTTP body stream, runs in filter chain, captures auth failures | In-process overhead | **YES** |
| **AOP (@Around)** | Clean, annotation-based | Can't access raw HTTP body, only method params | No |
| **Sidecar (Envoy)** | Zero application changes | No application context (endpoint name, supplier ID, error details) | No |

> "AOP can only access method parameters and return values - not the raw HTTP body stream. For debugging, suppliers need the actual request body. A sidecar like Envoy works at the network layer - it can't see which endpoint was called semantically or which supplier made the request. Servlet filter gives us both: raw HTTP access AND application context."

**Follow-up: "What about performance?"**
> "The filter adds ~1ms for ContentCachingWrapper. The actual audit is @Async so it doesn't block the response. P99 impact is under 5ms."

**Follow-up: "Why LOWEST_PRECEDENCE?"**
> "So it runs LAST in the filter chain - after security filters. This means we capture the final state of the request, including auth failures. If we ran first, we'd miss what the security filter did."

### Decision 2: @Async vs Synchronous vs Message Queue

| Approach | Latency Impact | Data Safety | Complexity | Our Choice |
|----------|---------------|-------------|------------|------------|
| **@Async fire-and-forget** | Zero (non-blocking) | Can lose data if queue full | Simple | **YES** |
| **Synchronous** | +50ms per request | No loss | Simplest | No - blocks API |
| **In-process Kafka producer** | Low (~5ms) | Durable | Medium | Considered for v2 |

> "Synchronous would add 50ms to every API response - unacceptable for supplier-facing APIs with 200ms SLA. A direct Kafka producer from the library would be more durable but adds Kafka dependencies to every service. @Async with a bounded thread pool is the simplest approach that gives us zero latency impact. The trade-off is we can lose audit data if the queue fills - we mitigate with Prometheus metrics and 80% queue warning."

**Follow-up: "Why not publish directly to Kafka from the library?"**
> "That would couple every consuming service to Kafka. They'd need Kafka dependencies, Schema Registry config, SSL certificates. The HTTP-based approach keeps the library lightweight - just add a Maven dependency."

### Decision 3: ThreadPool 6/10/100

> "Based on traffic analysis. Our APIs handle about 100 requests per second per pod. Each audit HTTP call takes about 50ms. So we need 5 threads to keep up. I set 6 core for headroom. Max 10 handles traffic spikes. Queue of 100 handles burst traffic - at 2KB per payload, that's only 200KB of memory."

**Follow-up: "A senior engineer challenged the queue size..."**
> "He was right. When the queue fills, tasks are silently rejected. I added three safeguards: Prometheus metric for rejected tasks, WARN log at 80% capacity, and documentation explaining the trade-off. That 80% warning has triggered once - caught a downstream slowdown."

### Decision 4: Avro vs JSON vs Protobuf

| Format | Size | Schema | Evolution | Kafka Ecosystem | Our Choice |
|--------|------|--------|-----------|-----------------|------------|
| **Avro** | 30% of JSON | Enforced via Schema Registry | Backward/forward compatible | Native (Confluent) | **YES** |
| **JSON** | 100% (baseline) | None | Breaking changes possible | Works but no schema | No |
| **Protobuf** | ~30% of JSON | .proto files | Compatible | Supported but less native | Considered |

> "Three reasons: schema enforcement prevents bad data from entering the pipeline, binary format is 70% smaller which matters at 2 million events per day, and schema evolution lets us add fields without breaking consumers. We chose Avro over Protobuf because it integrates natively with the Confluent Kafka ecosystem."

**Follow-up: "What if Schema Registry is down?"**
> "Producers cache schemas locally after first fetch. Existing schemas continue working. New schema registrations fail until Registry recovers."

### Decision 5: Kafka Connect vs Custom Consumer

| Approach | Dev Time | Offset Mgmt | Scaling | Error Handling | Our Choice |
|----------|----------|-------------|---------|----------------|------------|
| **Kafka Connect** | 2-3 days | Built-in | Automatic | DLQ + retries built-in | **YES** |
| **Custom Consumer** | 2-3 weeks | Manual | Manual | Manual | No |
| **Apache Flink** | 1-2 weeks | Built-in | Auto | Complex | Overkill |

> "Kafka Connect gives us offset management, scaling, fault tolerance, and retry logic out of the box. A custom consumer would take 2-3 weeks to build the same features. Connect is battle-tested and let us focus on our SMT filter logic instead of infrastructure."

**Follow-up: "But you had so many production issues with Connect..."**
> "True - but those were configuration issues, not architectural ones. A custom consumer would have had different but equally challenging production issues. The infrastructure Connect provides is worth the configuration effort."

### Decision 6: SMT Filter (Sink-Side) vs Producer-Side Routing

| Approach | Where Filtering Happens | Adding New Country | Coupling |
|----------|------------------------|-------------------|----------|
| **SMT Filter (sink-side)** | At consumption | Deploy new connector only | Loose |
| **Producer-side routing** | At publishing | Change producer code | Tight |
| **Multiple topics** | By topic name | New topic + consumer | Medium |

> "Separation of concerns. The producer's job is to publish reliably, not to know about downstream routing. If we add a new country, we just deploy a new connector with a new filter - no changes to the publisher."

### Decision 7: Parquet vs JSON vs ORC for Storage

| Format | Compression | Query Speed | BigQuery | Cost at 2M/day |
|--------|------------|-------------|----------|-----------------|
| **Parquet** | 90% | Fast (columnar) | Native external tables | ~$500/month |
| **JSON files** | ~30% | Slow (scan all) | Needs transformation | ~$5,000/month |
| **ORC** | 85% | Fast (columnar) | Not native | N/A |
| **BigQuery direct** | N/A | Fastest | Native | ~$3,000/month |

> "Parquet gives us 90% compression, columnar format so BigQuery reads only needed columns, and native BigQuery support via external tables. JSON files would be 10x more expensive. Direct BigQuery streaming inserts are fast but expensive at 2M events/day."

**Follow-up: "Why not Apache Iceberg?"**
> "Iceberg would give us ACID transactions and easier GDPR deletes. At the time, raw Parquet was simpler and met our requirements. If I rebuilt this today, I'd use Iceberg from day one."

### Decision 8: Active/Active vs Active/Passive

> "Audit is write-heavy and compliance couldn't tolerate 30-minute failover delays. Active/Active gives immediate failover. The cost is 2x infrastructure, but compliance failure costs far more. We achieve 15-minute recovery, well under our 1-hour RTO target."

**Follow-up: "How do you handle duplicates?"**
> "Geographic routing via wm-site-id header minimizes overlap. Kafka idempotent producer prevents duplicates within same cluster. Deduplication in sink based on request_id handles any remaining. Worst case: duplicates, never data loss."

### Decision 9: ContentCachingWrapper vs Custom Buffering

> "HTTP request bodies are InputStreams - you can only read them once. Without caching, either the filter or controller reads the body, not both. ContentCachingWrapper is Spring's built-in solution - well-tested, handles charset encoding, multipart, and other edge cases. The trade-off is memory - the entire body is in memory - but our gateway enforces a 2MB payload limit."

### Decision 10: isResponseLoggingEnabled Config Flag

> "One team wanted response body logging for debugging. Another team didn't - their responses were large (100KB+) and would increase storage costs 10x. Making it a CCM config flag means each team decides independently. No code changes, no redeployment - just a config toggle. This was the key to library adoption across 3 teams."

---

## The Debugging Story (5-Day Timeline)

> "About six weeks after launch, I noticed GCS buckets stopped receiving data. No alerts, no errors in dashboards. The system was failing silently - and we were losing compliance-critical audit data.
>
> **Day 1** - I checked the obvious. Kafka Connect running? Yes. Messages in the topic? Yes - millions backing up. So the issue was between consumption and GCS write. I narrowed the search space.
>
> **Day 2** - I enabled DEBUG logging and found a NullPointerException in our SMT filter. Legacy data didn't have the wm-site-id header we expected. I added try-catch with graceful fallback. Deployed it. Fixed? **No.**
>
> **Day 3** - Problem persisted. I noticed consumer poll timeouts in the logs. The default max poll interval was 5 minutes, but our GCS writes for large batches took longer. I tuned the config. Fixed? **Still no.**
>
> **Day 4** - This is where it got interesting. I correlated with Kubernetes events and discovered KEDA autoscaling was causing a feedback loop. When lag increased, KEDA scaled up workers. But scaling triggered consumer group rebalancing. During rebalancing, no messages are consumed. So lag increases more, KEDA scales more - infinite loop. I disabled KEDA and switched to CPU-based autoscaling.
>
> **Day 5** - After stabilizing, found the last issue. JVM heap exhaustion. Default 512MB wasn't enough for large batch Avro deserialization. Increased to 7GB (`-Xmx7g -Xms5g`) with G1GC.
>
> **Result:** Zero data loss - Kafka retained all messages during the entire debugging period. Backlog cleared in 4 hours once fixed. I created a troubleshooting runbook that's been used twice by other teams."

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

### KEDA Config That Was Removed (PR #42)

```yaml
# REMOVED from kitt.yml (-29 lines):
keda:
  triggers:
    - type: kafka
      metadata:
        consumerGroup: audit-log-consumer-group
        lagThreshold: "100"
```

The feedback loop:

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

### Heap Fix (PRs #57, #61)

```yaml
# Before: Default (~256MB)
env:
  - name: KAFKA_HEAP_OPTS
    value: "-Xms256m -Xmx512m"

# After: Explicit 7GB heap
env:
  - name: KAFKA_HEAP_OPTS
    value: "-Xms5g -Xmx7g"
```

### Key Learning

> "Distributed systems fail in unexpected combinations. It wasn't one bug - it was four issues compounding. And Kafka Connect's default error tolerance was hiding the problems silently. Now I build 'silent failure' monitoring into every system I design."

### The 413 Error Discovery (April 2025)

During data validation, I compared API Proxy counts against Data Discovery (Hive) counts:

| Date | API Proxy | Data Discovery | Lost Records | Root Cause |
|------|-----------|---------------|-------------|------------|
| Apr 13 | 1,742,647 | 1,638,352 | ~104K | 413 Payload Too Large |
| Apr 14 | 2,078,950 | 1,948,468 | ~130K | 413 + 502 errors |

**Fix**: Set 2MB gateway limit (PRs #49-51). After fix, counts matched exactly — zero data loss.

**"What would you do differently?"**

> "I'd add OpenTelemetry tracing from day one. If I could trace a single message from the HTTP request through Kafka to GCS, I would've found the issue in hours, not days."

---

## All Production Issues

### Complete Timeline

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
May 14      │ TIER 3: KEDA removed! Heartbeat updated (gcs-sink #42) ← FEEDBACK LOOP FIX
May 14      │ TIER 3: Session timeout tuning (gcs-sink #43, #46, #47)
May 14      │ TIER 3: Error tolerance set to none (gcs-sink #51, #52)
May 15      │ TIER 3: JVM heap override (gcs-sink #57)
May 15      │ TIER 3: Filter rewrite + custom header converter (gcs-sink #58, #59)
May 15      │ TIER 2: Header forwarding for geo-routing (srv #67)
May 16      │ TIER 3: Heap max increase (gcs-sink #61) ← FINAL FIX
May 16      │ TIER 2: Header validation - case-insensitive matching (srv #69)
May 19      │ TIER 2: Multi-region publishing with failover (srv #65)
            │
May 22-27   │ TIER 3: International (CA/MX) support rollout (gcs-sink #64-68)
May 30      │ TIER 3: Connector upgrade + retry policy (gcs-sink #69)
Jun 9       │ TIER 3: Retry policy CRQ for production (gcs-sink #70)
Jun 11      │ TIER 3: Data type fix - DECIMAL for timeout multiplier (gcs-sink #75)
            │
Sep 19      │ TIER 1: GTP BOM update for Java 17 compat (common-lib #15)
Nov 3       │ TIER 3: Country code to site ID mapping change (gcs-sink #83)
Nov 18      │ TIER 2: Contract testing added (srv #77)
Dec 2       │ TIER 3: Multi-site filter support US/CA/MX (gcs-sink #85) ← MAJOR
Dec 10      │ TIER 2: Signature validation for specific consumerId (srv #81)
Jan 29      │ TIER 3: Vulnerability fix + startup probe (gcs-sink #87)
```

### Key Issues by Tier

**Tier 1 (Common Library):** Zero production bugs since launch. Only 2 post-launch PRs were enhancements (#11: regex endpoint filtering, #15: Java 17 BOM update). The simple design — just a filter, an async service, and a config — is what makes it stable.

**Tier 2 (Publisher):**
- 413 Payload Too Large (PRs #49-51) - **How discovered:** Pattern analysis showed missing audit records; all missing records had large response bodies. **Root cause:** The API proxy had a default 1MB limit. **Fix:** `APIPROXY_QOS_REQUEST_PAYLOAD_SIZE: 2097152  # 2MB`
- Header Forwarding Missing (PR #67) - `wm-site-id` not forwarded, all data going to US bucket
- Header Case-Sensitivity (PR #69) - Some services sent `WM-Site-Id` vs `wm-site-id`
- Failover Bug (PR #65) - `exceptionally()` returning null instead of trying secondary region

**Tier 3 (GCS Sink):**
- Day 1 Topic Misconfiguration (PRs #20-25) - 6 config fixes in one day
- Silent Failure (PRs #35-61) - NPE + poll timeouts + KEDA feedback loop + heap exhaustion
- Filter Rewrite (PRs #58-59) - Complete rewrite of filtering approach with custom header converter
- Error Tolerance Oscillation - `all` silently loses data, `none` stops on any error. Settled on `none` with DLQ

### Day 1 Topic Misconfiguration (PRs #20-25)

6 config fix PRs in ONE DAY. The Kafka topic names and KCQL (Kafka Connect Query Language) configurations were wrong for the production SCUS environment. Topic names from staging didn't carry over, project IDs were wrong, and KCQL paths were mismatched.

> "Day 1 of production, the sink wasn't receiving any data. Turned out topic names were misconfigured for the SCUS environment. We had 6 config fixes in one day. Lesson: always verify configurations independently for each environment - don't assume staging names carry over."

### PR #58-59: Filter Rewrite (Not Just a Try-Catch)

The original USFilter was completely removed (PR #58: -301 lines) and rewritten with a new approach (PR #59: +386 lines) including a CustomHeaderConverter for proper Avro header deserialization. This was NOT just a "try-catch fix" -- it was a complete rewrite of the filtering approach.

The default Kafka Connect header converter couldn't handle Avro-serialized headers. The filter was reading raw bytes instead of deserialized values. The custom converter properly deserializes Avro headers before the SMT filter processes them.

> "After fixing the obvious NPE, we discovered the filter code needed a complete rewrite. The original approach couldn't handle Avro-serialized headers properly. We removed the filter entirely (PR #58: -301 lines) and rebuilt it with a custom header converter (PR #59: +386 lines). The 5-day timeline oversimplifies what was actually 27 PRs (#35-61) of incremental fixes."

### Error Tolerance Oscillation (PRs #51-52)

We oscillated between `errors.tolerance: all` (silent data loss) and `errors.tolerance: none` (connector stops on any error). The final answer was `none` with proper DLQ and monitoring.

- `errors.tolerance: all` -- Connector ignores all errors and keeps running. Problem: silently drops bad records with no visibility. This is what hid our issues for days.
- `errors.tolerance: none` -- Connector stops on ANY error. Problem: one bad record stops the entire pipeline.
- **Final answer:** `none` with proper Dead Letter Queue (DLQ) routing and monitoring. Bad records go to DLQ for inspection, connector keeps running for good records, and we get alerts on DLQ growth.

> **Current State**: The production `kc_config.yaml` currently uses `errors.tolerance: all` with DLQ enabled and retry policy (`connect.gcpstorage.error.policy: RETRY`, 5 retries, 5000ms interval). This approach tolerates transient errors while capturing persistent failures in the DLQ.

> "Error tolerance is a design decision, not a config toggle. 'all' means you're choosing silence over safety. 'none' means you're choosing strictness over availability. We chose 'none' with DLQ - strictness with a safety net."

### Dual-Region Failover Bug (PR #65)

During a Kafka outage in primary region (EUS2), the failover code returned null in `exceptionally()` instead of trying the secondary region. Messages were silently dropped during the outage.

**Before (broken):**
```java
kafkaPrimaryTemplate.send(message)
    .exceptionally(ex -> {
        log.error("Failed: {}", ex.getMessage());
        return null;  // BUG: Secondary never tried!
    });
```

**After (fixed):**
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

> "Our failover was broken and we didn't know until a real outage. CompletableFuture's `.exceptionally()` returning null silently swallows the error. Lesson: always test failover scenarios, don't just write the code."

### Cross-Tier Geographic Routing Issue

Geographic routing required coordinated changes across Tier 2 (publisher) and Tier 3 (GCS sink) simultaneously. The `wm-site-id` header had to be forwarded correctly by the publisher, then parsed correctly by the sink's filter. This was not a single-tier fix -- it was a cross-tier coordination effort over May 15-19, 2025.

**Coordinated PRs:**
1. **Tier 2 (srv #67):** Add header forwarding -- `wm-site-id` wasn't being forwarded from the library to Kafka messages, so ALL records went to the US bucket
2. **Tier 2 (srv #69):** Fix case-insensitive header matching -- some services sent `WM-Site-Id` vs `wm-site-id`
3. **Tier 3 (gcs-sink #59):** Add filter + custom header converter for proper Avro header deserialization
4. **Tier 3 (gcs-sink #60):** Move header converter to worker level for all connectors

> "Geographic routing required coordinated changes across the publisher and sink. The header had to be forwarded correctly by the publisher, then parsed correctly by the sink's filter. We discovered case-sensitivity issues and header format problems that required fixes on both sides. This is why distributed systems are hard -- a feature that sounds simple ('route by country') touched 4 PRs across 2 repos."

### Summary by Severity

| Severity | Count | Examples |
|----------|-------|---------|
| **Critical** | 3 | Topic misconfiguration (Day 1), Silent failure (5 days), KEDA feedback loop |
| **High** | 4 | Header forwarding missing, Failover bug, OOM, Multi-site expansion |
| **Medium** | 5 | 413 payload, Case-sensitivity, Header converter, Startup probes, Signature bypass |
| **Low** | 2 | Data type mismatch, Method not supported |

### Key Learnings by Tier

**Tier 1:** Simple design = stable in production. Zero production bugs since launch.

**Tier 2:** Test failover before you need it. Know ALL size limits in your infrastructure. Headers are case-insensitive - always match accordingly.

**Tier 3:** Kafka Connect's defaults are NOT production-ready. Don't scale consumers on lag. Error tolerance is a design decision, not a config toggle. Always verify configs per environment.

### Interview Answers

**Short Version (2 min):**
> "Three categories. **Day 1:** Config issues - topic names wrong for production. Fixed in hours. **Weeks 2-4:** The silent failure - a 5-day debugging incident involving 4 compounding issues: null header NPE, consumer poll timeouts, KEDA autoscaling feedback loop, and heap exhaustion. 27 PRs to fully resolve. Zero data loss. **Ongoing:** Header forwarding for geographic routing required coordinated fixes across the publisher and sink tiers - case sensitivity, header format, and filter logic."

**Long Version (when they want depth):**
> "The most interesting was the silent failure. After fixing the obvious NPE, we discovered the filter code needed a complete rewrite - not just a try-catch. The original approach couldn't handle Avro-serialized headers properly. We removed the filter entirely (PR #58: -301 lines) and rebuilt it with a custom header converter (PR #59: +386 lines). Then we discovered the error tolerance dilemma: 'all' silently loses data, 'none' stops on one bad record. We settled on 'none' with DLQ and monitoring.
>
> The KEDA autoscaling lesson was the most surprising. Scaling Kafka consumers on consumer lag creates a feedback loop: more replicas means rebalancing which means lag increases which means more scaling. We switched to CPU-based HPA."

---

## Behavioral Stories (STAR Format)

### Story 1: Receiving Feedback (Thread Pool Challenge)

**Trigger:** "Tell me about a time you received difficult feedback" / "Describe a situation where you were wrong"

> **Situation:** "During code review for the audit library, a senior engineer criticized my thread pool configuration. He said the queue size of 100 was arbitrary and could cause silent data loss."
>
> **Task:** "I needed to respond constructively, not defensively."
>
> **Action:** "My first instinct was defensive - I HAD thought about this. But I paused. I ran the numbers: each payload is 2KB, queue of 100 is 200KB - not a memory issue. But when the queue fills and tasks are rejected? They're silently dropped. He was right.
>
> I added three things: a Prometheus metric for rejected tasks, a WARN log when queue exceeds 80%, and documentation explaining the trade-off. I thanked him in the PR comments."
>
> **Result:** "The library is more robust. We've had the 80% warning trigger once - caught a downstream slowdown early. That engineer later became an advocate for the library."

### Story 2: Influencing Without Authority (Library Adoption)

**Trigger:** "Tell me about a time you influenced others without authority" / "Describe building something other teams adopted"

> **Situation:** "I noticed three teams building audit logging independently. Same functionality, three different implementations."
>
> **Task:** "I proposed a shared library. My challenge was getting buy-in from teams I had no authority over."
>
> **Action:** "I didn't come with a solution - I came with questions. I scheduled meetings with each team's lead: 'What are your requirements? What endpoints? What latency constraints?'
>
> There was resistance. 'Our needs are different.' One team wanted response body logging, another didn't. I showed the common 80% and made the different 20% configurable. Response body logging became a CCM config flag.
>
> I wrote documentation and a migration guide. Did a brown-bag demo. Then personally spent an afternoon with each team pairing on their integration PRs."
>
> **Result:** "Three teams adopted within a month. Integration time dropped from 2 weeks to 1 day. One engineer I helped later onboarded a fourth team without me."

### Story 3: Handling Ambiguity (Multi-Region Requirements)

**Trigger:** "Tell me about a time you had incomplete information" / "Describe a project with unclear requirements"

> **Situation:** "We needed multi-region for disaster recovery. Leadership said 'make it resilient' without specifying RTO, RPO, budget, or timeline."
>
> **Task:** "I needed to define the requirements myself, design a solution, and execute with zero downtime."
>
> **Action:** "Instead of waiting for clarity, I proactively scheduled conversations. Asked stakeholders: 'How much data can we afford to lose?' - learned RPO was 4 hours. 'How quickly must we recover?' - learned RTO was 1 hour.
>
> I designed three options with trade-offs - Active-Passive, Active-Active, Hybrid - and presented them to the team. We chose Active-Active because audit is write-heavy.
>
> I documented my assumptions explicitly: 'I'm assuming RPO of 4 hours because...' and shared with stakeholders. That document became the de facto requirements spec."
>
> **Result:** "Active-Active across two regions in 4 weeks. Zero downtime. DR test: recovered in 15 minutes versus the 1-hour target."

### Story 4: Failure (KEDA Feedback Loop)

**Trigger:** "Tell me about a time you failed" / "What's your biggest mistake?"

> **Situation:** "I configured KEDA autoscaling for Kafka Connect based on consumer lag. Seemed logical - more lag means more work, so scale up."
>
> **Task:** "In production, this caused a catastrophic feedback loop."
>
> **Action:** "When lag increased, KEDA scaled up workers. But scaling triggered consumer group rebalancing. During rebalancing, no messages are consumed, so lag increases more. More scaling, more rebalancing - infinite loop.
>
> The system got stuck processing zero messages. I diagnosed the loop, disabled KEDA, and switched to CPU-based autoscaling."
>
> **Result:** "No data loss because Kafka retained messages. But I should have caught this in testing."
>
> **Learning:** "I tested autoscaling in isolation but not with production-like traffic patterns. The second-order effect - scaling causes rebalancing which causes more lag - only shows up at scale. Now I always test scaling behavior with realistic load, including failure modes."

### Story 5: User Focus (Supplier Self-Service)

**Trigger:** "Tell me about improving user experience" / "Tell me about solving a customer problem"

> **Situation:** "Our external suppliers couldn't debug their own API issues. When their requests failed, they'd call support, open a ticket, wait 1-2 days, and we'd grep through logs."
>
> **Task:** "When building the audit system, I saw an opportunity beyond just replacing Splunk."
>
> **Action:** "I designed the system with supplier self-service in mind. I chose Parquet format specifically because BigQuery can query it directly. I ensured the schema captured everything suppliers need: request body, response body, error messages, status codes.
>
> I worked with our data team to set up BigQuery external tables with row-level security - each supplier only sees their own records. Created sample queries and documentation."
>
> **Result:** "Suppliers self-service debug in 30 seconds instead of waiting 2 days. Support ticket volume dropped significantly. One supplier told me this was the first time they had visibility into their API interactions with any vendor."

---

## Interview Q&A Bank

### Opening Questions

**Q: "Tell me about this audit logging system."**
> "When Walmart decommissioned Splunk, I built a replacement audit logging system. But I went beyond just logging - I designed it so external suppliers could query their own API interaction data. It handles 2-3 million events daily with zero API latency impact."

**Follow-up: "Why was Splunk being decommissioned?"**
> "Cost and licensing. Splunk is expensive at scale, and Walmart decided not to renew the enterprise license. For us, it was an opportunity to build something better."

**Q: "Why did you use a filter instead of AOP?"**
> "Filters give us access to the raw HTTP request/response at the servlet level. With AOP, we'd only have access to method parameters and return values, not the actual HTTP body stream."

**Q: "What happens if the audit service is down?"**
> "The API continues to work normally. Audit logging is async and fire-and-forget. We catch all exceptions in AuditLogService and log them, but don't propagate. The user experience is unaffected."

**Q: "How do you handle large request/response bodies?"**
> "ContentCachingWrapper buffers the body in memory. Our APIs have payload limits (2MB) set at the gateway. We also have an option to disable response body logging for endpoints with large responses."

### Technical Deep Dive Questions

**Q: "Explain the Kafka Connect SMT filter design."**
> "SMT stands for Single Message Transform - it's Kafka Connect's plugin system for processing messages inline. I created an abstract base class called BaseAuditLogSinkFilter that implements the Transformation interface. It has one abstract method: getHeaderValue(), which subclasses override to return their target site ID. The apply() method checks if the record's wm-site-id header matches. If yes, return the record. If no, return null - which tells Kafka Connect to drop it.
>
> The clever part is the US filter. Legacy records don't have the wm-site-id header. So the US filter is permissive - it accepts records WITH the US header OR records with NO header. Canada and Mexico filters are strict - exact match only."

**Q: "How does the async processing work in detail?"**
> "Spring's @Async creates a proxy that submits the method call to an Executor instead of running it directly. When LoggingFilter calls auditLogService.sendAuditLogRequest(), the proxy submits the call to the executor. The filter returns immediately. If all 10 threads are busy and the queue is full (100 items), the default RejectedExecutionHandler throws an exception. But our sendAuditLogRequest catches all exceptions, so the request is silently dropped. This is intentional - we never want audit to fail the API."

**Follow-up: "Why those specific thread pool sizes?"**
> "Based on traffic analysis. Our APIs handle about 100 requests per second per pod. Each audit call takes about 50ms. So we need 5 threads to keep up (100 x 0.05). I set 6 core for headroom. Max 10 handles spikes. Queue of 100 handles burst traffic."

### Quick Answers

**"Why LOWEST_PRECEDENCE for the filter?"**
> "Run after all security filters so we capture the final state, including auth failures."

**"Why ContentCachingWrapper?"**
> "HTTP streams can only be read once. Without caching, either filter or controller could read the body, not both."

**"Why fire-and-forget?"**
> "Audit shouldn't impact API latency. If we blocked waiting for confirmation, a slow audit service would slow all APIs."

**"How do suppliers access their data?"**
> "BigQuery external tables with row-level security. Each supplier can only see their own records."

**"What's the latency impact?"**
> "P99 under 5ms. The filter adds ~1ms for caching, the rest happens asynchronously after response is sent."

**"What happens when SMT returns null?"**
> "Kafka Connect convention - returning null from apply() drops the message. That's how we route: US connector's filter returns null for non-US records."

**"Why not filter at the producer side?"**
> "Two reasons. First, separation of concerns - the producer's job is to publish reliably, not to know about downstream routing. Second, flexibility - if we add a new country, we just deploy a new connector. No changes to producers."

**"What happens if both Kafka regions are down?"**
> "The publisher returns an error, which the common library catches and logs. The API response is not affected because the library call is async."

**"How many teams use this?"**
> "Four teams and growing: NRT, IAC, cp-nrti-apis, and BULK-FEEDS."

**"What's the data query layer?"**
> "GCS stores Parquet files. Hive external tables via Data Discovery for internal teams. BigQuery external tables for suppliers. Airflow refreshes Hive partitions daily."

**"What's your testing strategy?"**
> "Four layers: 80%+ unit coverage, Testcontainers integration tests, R2C contract testing as CI/CD gate, and 36 E2E test scenarios."

### Unique Questions

**"What if you needed 100x the throughput?"**
> "Current: 2M events/day = ~23 events/sec. Target: 200M events/day = ~2300 events/sec. Library: Switch from HTTP to direct Kafka publishing. Kafka: Increase partitions from 12 to 48. Connect: Scale horizontally - add 2-3 more workers. Cost would scale ~10x, not 100x, because of batching efficiency."

**"What if you needed real-time querying?"**
> "Current design optimizes for cost and batch analytics. For real-time, I'd add Elasticsearch as a second sink for recent data (last 7 days), keep GCS for long-term. Query router directs recent queries to ES, historical to BigQuery."

**"What if a regulator asked for all data for a specific supplier to be deleted?"**
> "Hard with immutable storage like GCS. Current process: identify all Parquet files with that supplier's data, read and filter out their records, write new file, delete original. Better design for future: encrypt each record with supplier-specific key. For deletion, delete the key (crypto-shredding). Data remains but is unreadable."

**"If you rebuilt this from scratch?"**
> "Three things: (1) Skip the publisher service - publish directly to Kafka from library. (2) Add OpenTelemetry from day one. (3) Use Apache Iceberg instead of raw Parquet for ACID transactions and GDPR deletes."

---

## What-If Scenarios

Use the DETECT, IMPACT, MITIGATE, RECOVER, PREVENT framework.

### Q1: "What if Kafka is completely down?"

> **DETECT:** "Audit error rate spikes in Prometheus. Kafka health check fails."
>
> **IMPACT:** "Audit events are lost during the outage. BUT - supplier API responses are NOT affected. @Async fire-and-forget means the API is completely decoupled from Kafka health."
>
> **MITIGATE:** "Dual-region publishing. If primary (EUS2) is down, CompletableFuture chains to secondary (SCUS). If BOTH are down, exceptions are caught and logged."
>
> **RECOVER:** "When Kafka recovers, new events flow normally. Events during outage are lost."
>
> **PREVENT:** "Multi-region Active/Active. Would need local disk buffer to survive both-region-down (not implemented, but on roadmap)."

### Q2: "What if the GCS sink stops writing but no one notices?"

> "This is EXACTLY what happened to us - the Silent Failure incident. Kafka Connect was running, messages were in the topic, but nothing was reaching GCS. No alerts fired because we only monitored 'is it running?' not 'is it processing correctly?'
>
> What we added AFTER: consumer lag alerts (warning at 100, critical at 500), GCS write rate monitoring (if rate drops to 0, alert), JVM memory metrics in Grafana, dropped record counters.
>
> Lesson: Monitor OUTPUTS not just INPUTS."

### Q3: "What if the common library JAR has a bug affecting all teams?"

> **DETECT:** "Multiple teams report audit failures simultaneously."
>
> **IMPACT:** "All services using the library are affected. BUT the library catches ALL exceptions - audit bugs never break the API."
>
> **RECOVER:** "Roll back Maven dependency version. Each team can independently pin to a known good version."
>
> **PREVENT:** "Comprehensive tests. R2C contract testing. Code review for all library changes."

### Q4: "What if the thread pool queue fills up?"

> "Tasks beyond 100 are rejected. Since @Async catches exceptions, audit logs are silently dropped.
>
> How we know: Prometheus metric `audit_log_rejected_count` increments. WARN log fires at 80% queue capacity.
>
> This happened once: During a downstream slowdown, the 80% warning triggered. We identified the slow audit-api-logs-srv and scaled it up. Queue never actually filled."

### Q5: "What if a supplier sends a massive 10MB request body?"

> "ContentCachingWrapper caches the ENTIRE body in memory. 10MB per request x 100 concurrent requests = 1GB just for body caching.
>
> Prevention: API gateway enforces 2MB limit. For endpoints with large responses, `isResponseLoggingEnabled` can be set to false via CCM.
>
> The real incident: Before we set the 2MB limit, some inventory responses were causing 413 errors in the audit publisher. We were silently losing audit data for large responses."

### Q6: "What if Avro schema becomes incompatible?"

> **DETECT:** "Producer fails fast - Schema Registry rejects the registration. Build/deployment fails."
>
> **IMPACT:** "No new messages published with the new schema. Old messages continue flowing."
>
> **MITIGATE:** "Schema Registry is in BACKWARD compatibility mode. New schema must be readable by old consumers."
>
> **PREVENT:** "Schema compatibility check in CI/CD pipeline. Schema changes go through code review."

### Q7: "What if one GCS bucket gets corrupted?"

> "Three separate buckets with three separate connectors. If US bucket is corrupted, CA and MX continue working. GCS has versioning and lifecycle policies. Messages are still in Kafka (retention period) - we can replay them."

### Q8: "What if someone pushes a bad SMT filter update?"

> "This is essentially what happened with the null header issue (PR #35). Consumer lag spikes immediately. GCS write rate drops to zero.
>
> Recovery: Roll back the Connect deployment. Kafka retains messages - nothing lost.
>
> Prevention: Unit tests for all filter classes, stage deployment before production, `errors.tolerance: none` with DLQ."

### Q9: "What happens during Black Friday at 10x traffic?"

> "Current: 2M events/day = ~23/sec. At 10x: 20M events/day = ~230/sec.
>
> Library: Thread pool handles it - 6 core threads at 50ms/call = 120 calls/sec per pod. With 5 pods = 600/sec. Fine.
>
> Kafka: 12 partitions at 230/sec still trivial. Kafka handles millions/sec.
>
> Pre-scaling checklist: Increase Connect worker replicas, increase publisher pod count, pre-warm thread pools, increase Kafka retention for safety buffer, disable response body logging for high-volume endpoints."

### Q10: "What if you need to replay the last 24 hours of audit data?"

> "Kafka retains messages for 7 days. Reset Connect consumer group offset to 24 hours ago. Connect re-consumes and re-writes to GCS. Deduplicate in BigQuery using `request_id`.
>
> Caution: Replaying creates duplicate files in GCS. BigQuery queries need DISTINCT on request_id during the replay period.
>
> Better approach: Apache Iceberg table would handle upserts properly. On our roadmap."

---

## How to Speak

### Numbers to Drop Naturally

| Number | How to Say It |
|--------|---------------|
| 2M events/day | "...handles 2-3 million events daily..." |
| <5ms P99 | "...less than 5 milliseconds impact at P99..." |
| 99% cost reduction | "...went from $50K/month with Splunk to about $500..." |
| 4+ teams adopted | "...four teams adopted within the first quarter..." |
| 2 weeks to 1 day | "...integration time dropped from two weeks to one day..." |
| 70% smaller (Avro) | "...Avro is about 70% smaller than JSON..." |
| 90% compression (Parquet) | "...Parquet compresses to about 10% of JSON size..." |
| 7 years retention | "...seven years for compliance requirements..." |
| 6/10/100 thread pool | "...six core threads, max ten, queue of a hundred..." |
| 150+ PRs across 3 repos | "...over 150 PRs across three repositories..." |

### How to Pivot TO This Project

> "That reminds me of the audit logging system I designed. The constraint was similar - [connect to what they asked]..."

> "We faced a similar challenge with our audit system. Let me walk you through how we solved it..."

### How to Pivot AWAY From This Project

> "That's the audit system. I also led a Spring Boot 3 migration that shows a different kind of challenge - not designing something new, but changing the foundation of a running system without downtime. Interested?"

### How to Answer "What Would You Improve?"

> "Four things: (1) Skip the publisher service — publish directly to Kafka from the library. (2) Add OpenTelemetry from day one. (3) Use Apache Iceberg instead of raw Parquet. (4) Define formal SLOs upfront — we defined them retroactively."

---

## PR Reference

### Top 10 PRs

| # | Repo | PR# | One-Line Summary |
|---|------|-----|------------------|
| 1 | dv-api-common-libraries | #1 | Complete audit logging library |
| 2 | audit-api-logs-gcs-sink | #1 | Initial GCS sink architecture |
| 3 | audit-api-logs-srv | #65 | Multi-region Kafka publishing |
| 4 | audit-api-logs-gcs-sink | #28 | Kafka consumer tuning |
| 5 | audit-api-logs-gcs-sink | #42 | Fixed KEDA rebalance storm |
| 6 | audit-api-logs-gcs-sink | #61 | Fixed OOM with heap increase |
| 7 | audit-api-logs-gcs-sink | #85 | Site-based geographic routing |
| 8 | dv-api-common-libraries | #11 | Regex endpoint filtering |
| 9 | audit-api-logs-srv | #77 | Contract testing |
| 10 | audit-api-logs-gcs-sink | #12 | First production deployment |

### Debugging PR Sequence (#35-61)

| PR# | Title | What It Fixed |
|-----|-------|---------------|
| **#35** | Adding try catch block | NPE on null headers |
| **#38** | Adding consumer poll config | Poll timeout issues |
| **#42** | Removing scaling on lag | KEDA rebalance storm |
| **#47** | Increasing poll timeout | Consumer stability |
| **#52** | Setting error tolerance | Error handling strategy |
| **#57** | Overriding KAFKA_HEAP_OPTS | JVM heap issues |
| **#59** | Filter and header converter | Header parsing |
| **#61** | Increasing heap max | Final memory fix |

### PR Statistics

| Repository | Total PRs | Key PRs |
|------------|-----------|---------|
| dv-api-common-libraries | 16 | #1, #3, #11, #15 |
| audit-api-logs-srv | 61+ | #4, #65, #67, #77 |
| audit-api-logs-gcs-sink | 76+ | #1, #28, #35-61, #85 |
| **TOTAL** | **150+** | |

### Timeline

```
2024-12 ┃ audit-api-logs-srv: Initial Kafka service (#4)
        ┃
2025-01 ┃ audit-api-logs-gcs-sink: Initial setup (#1)
        ┃
2025-03 ┃ dv-api-common-libraries: Audit log service (#1)
        ┃ Production deployments (#12, #44) [CRQ]
        ┃
2025-04 ┃ dv-api-common-libraries: Regex endpoints (#11)
        ┃
2025-05 ┃ PRODUCTION DEBUGGING (#35-61)
        ┃ audit-api-logs-srv: Multi-region (#65), Headers (#67)
        ┃
2025-06 ┃ audit-api-logs-gcs-sink: Retry policy (#70) [CRQ]
        ┃
2025-11 ┃ audit-api-logs-gcs-sink: Site-based routing (#85)
        ┃ audit-api-logs-srv: Contract testing (#77)
```
