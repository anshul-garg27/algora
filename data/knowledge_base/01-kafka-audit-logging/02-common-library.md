# Common Library JAR (Bullet 2) - dv-api-common-libraries

> **Resume Bullet:** "Developed reusable Spring Boot starter JAR for audit logging, adopted by 3+ teams, reducing integration time from 2 weeks to 1 day"

---

## 30-Second Pitch

> "I built a reusable Spring Boot starter JAR that gives any service audit logging by just adding a Maven dependency. No code changes needed. It uses a servlet filter with ContentCachingWrapper to capture HTTP bodies, and @Async processing so it doesn't impact API latency. Three teams adopted it within a month, reducing integration time from 2 weeks to 1 day."

---

## Why This Is a Separate Resume Bullet

This library demonstrates:
1. **Reusability thinking** - Saw 3 teams building same thing, proposed shared solution
2. **API design** - Zero-code integration (just add Maven dependency)
3. **Spring internals** - Filters, auto-config, async, thread pools
4. **Adoption skills** - Got buy-in, wrote docs, helped teams integrate

---

## The Magic: Zero-Code Integration

```xml
<!-- For JDK 11 -->
<dependency>
    <groupId>com.walmart</groupId>
    <artifactId>dv-api-common-libraries</artifactId>
    <version>0.0.54</version>
</dependency>
```

**How does it work without code changes?**

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

---

## Key Files

```
dv-api-common-libraries/
├── filters/
│   └── LoggingFilter.java          # HTTP interceptor (129 lines)
├── services/
│   └── AuditLogService.java        # Async HTTP client (111 lines)
├── configs/
│   ├── AuditLoggingConfig.java     # CCM configuration interface
│   └── auditlog/
│       └── AuditLogAsyncConfig.java # Thread pool config
├── payloads/
│   └── AuditLogPayload.java        # Data model (59 lines)
└── utils/
    └── AuditLogFilterUtil.java     # Helper methods (177 lines)
```

---

## Code Deep Dive

### 1. LoggingFilter.java - The Heart (ACTUAL CODE from repo)

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

> **Note:** This is the ACTUAL code from the repo. Key detail: `isResponseLoggingEnabled()` makes response body capture configurable per team - this was one of the 20% differences that made the library reusable across teams.

**Why `LOWEST_PRECEDENCE`?**
- Ensures we run AFTER all security filters
- We capture the FINAL state of request/response
- If auth fails, we still log the failed attempt

**Why `ContentCachingWrapper`?**
- HTTP streams can only be read ONCE
- Without wrapping, controller would get empty body
- Wrapper caches the bytes for re-reading

---

### 2. AuditLogService.java - Async Processing

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

**Key Implementation Detail — WebClient, Not RestTemplate**: The HTTP service uses `WebClient` (reactive) with `.block()`:
```java
// AuditHttpServiceImpl.java — actual production code
return webClient.method(method)
    .uri(uri)
    .headers(headers -> headers.addAll(httpEntity.getHeaders()))
    .body(Optional.ofNullable(httpEntity.getBody())
        .map(BodyInserters::fromValue)
        .orElseGet(BodyInserters::empty))
    .exchangeToMono(response -> response.toEntity(responseType))
    .block(); // Converts reactive to synchronous for filter context
```

**Why `@Async`?**
- API response time should not depend on audit logging
- If audit service is slow, user still gets fast response
- Queue absorbs traffic spikes (capacity: 100)

---

### 3. AuditLogAsyncConfig.java - Thread Pool

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
- **6 core**: Handles normal traffic (~100 requests/sec)
- **10 max**: Handles spikes without creating too many threads
- **100 queue**: Buffer during traffic bursts; prevents OOM

**What happens when queue is full?**
- Default: `AbortPolicy` throws `RejectedExecutionException`
- Our code catches exceptions - audit log silently dropped
- This is acceptable - audit is best-effort, not critical path

---

### 4. AuditLogPayload.java - Data Model

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

---

## Key Design Decisions

| Decision | Why | Alternative Considered |
|----------|-----|----------------------|
| **Servlet Filter** | Access to raw HTTP stream | AOP (no body access) |
| **@Order(LOWEST_PRECEDENCE)** | Run AFTER security filters | Higher priority (miss auth failures) |
| **ContentCachingWrapper** | Read body without consuming stream | Custom buffering (complex) |
| **@Async** | Non-blocking, fire-and-forget | Sync (blocks API response) |
| **CCM config for endpoints** | Runtime enable/disable without deploy | Hardcoded list (inflexible) |
| **ThreadPool (6 core, 10 max, 100 queue)** | Handle bursts, bounded memory | Unbounded (OOM risk) |
| **WebClient over RestTemplate** | Modern, reactive, better resource handling | RestTemplate (deprecated in Spring 6) |

### Security — Signature Authentication

Every audit log request is cryptographically signed:

```java
// Signature generation per request
SignatureDetails signatureDetails = AuthSign.getAuthSign(
    consumerId,           // Unique per consuming service
    privateKey,           // RSA key from AKeyless, mounted at runtime
    keyVersion            // Rotatable key version
);
```

**Headers added to every audit request:**
- `WM_CONSUMER.ID` — unique consumer identifier
- `WM_SEC.AUTH_SIGNATURE` — HMAC-SHA256 signature
- `WM_SEC.KEY_VERSION` — supports key rotation
- `WM_CONSUMER.INTIMESTAMP` — timestamp for replay protection

**Private key management**: Stored in **AKeyless** (Walmart's secret management platform), mounted at runtime to `/etc/secrets/audit_log_private_key.txt`. Never stored in code or config repos.

---

## Interview Questions

### Q: "Why a library instead of a sidecar?"
> "Sidecars like Envoy work at the network layer - they can't see application context. We needed to capture which endpoint was called semantically, what the error message meant, which supplier made the request. That context only exists inside the application."

### Q: "How did you get other teams to adopt it?"
> "Three steps: First, I met with engineers to understand their requirements. Second, I wrote comprehensive documentation and a migration guide. Third, I did a brown-bag session and personally helped each team integrate - spent an afternoon pairing on their PRs. Three teams adopted within a month."

### Q: "What was the hardest design decision?"
> "Thread pool sizing. A senior engineer challenged my queue size of 100 - said it could cause silent data loss. He was right. I added metrics for rejected tasks and a warning when queue is 80% full. That monitoring has caught downstream slowdowns twice."

### Q: "What happens if the audit service is down?"
> "API continues normally. We catch all exceptions in AuditLogService and log them, but don't propagate. The thread pool queue absorbs brief outages. For extended outages, we lose audit data but users are unaffected. Intentional - audit is best-effort."

### Q: "How do teams configure which endpoints to audit?"
> "CCM (Cloud Configuration Management). Each team has their own CCM config with endpoint patterns. They can add/remove endpoints without code changes or redeploys. We also support regex patterns for flexible matching."

---

## The Adoption Story (STAR Format)

**Situation:** "Our team needed audit logging, but I noticed two other teams building the same thing independently."

**Task:** "I proposed building a shared library and took responsibility for getting buy-in and driving adoption."

**Action:**
- Met with engineers from other teams to understand requirements
- Made the 20% different requirements configurable (response body logging toggle, endpoint filtering)
- Wrote documentation and migration guide
- Did a brown-bag session demo
- Personally helped each team integrate (paired programming)

**Result:** "Three teams adopted within a month. Integration time dropped from 2 weeks to 1 day. The library became the standard for all new services."

---

## Numbers to Remember

| Metric | Value |
|--------|-------|
| Lines of code | ~500 (entire library) |
| Integration time | 1 day (vs 2 weeks custom) |
| Teams using it | 3+ |
| PRs in library | 16 |
| Thread pool | 6 core, 10 max, 100 queue |
| Maven version | 0.0.45 |

---

### Library Version Note

The common library is currently on **version 0.0.54** with support for both **JDK 11** and **JDK 17**. It still uses `javax.servlet` imports (Spring Boot 2.7.11 parent). The consuming services (like cp-nrti-apis) have migrated to Spring Boot 3.5.7 / Java 17 with `jakarta.servlet` — the library's servlet API is backwards compatible at the binary level.

The library uses **WebClient** (Spring WebFlux) for HTTP calls to the publisher service — not RestTemplate. The WebClient call uses `.block()` to convert the reactive chain to synchronous within the filter context.

---

## Actual File Paths (from repo)

```
src/main/java/com/walmart/dv/
├── configs/
│   ├── AuditLoggingConfig.java
│   ├── FeatureFlagCCMConfig.java
│   └── auditlog/
│       └── AuditLogAsyncConfig.java
├── constants/
│   └── AppConstants.java
├── filters/
│   └── LoggingFilter.java
├── payloads/
│   └── AuditLogPayload.java
├── services/
│   ├── AuditHttpService.java
│   ├── AuditLogService.java
│   └── impl/
│       └── AuditHttpServiceImpl.java
└── utils/
    └── AuditLogFilterUtil.java
```

---

## Key PRs

| PR# | Title | Additions | Why Important |
|-----|-------|-----------|---------------|
| **#1** | Audit log service | +1,564 | **THE MAIN PR** - Complete library |
| **#3** | adding webclient in jar | +29 | WebClient for reactive HTTP |
| **#6** | Develop | +1 | Core functionality merge |
| **#11** | enable endpoints with regex | +207/-125 | Flexible endpoint filtering |
| **#15** | Version update for gtp bom | +31 | Java 17 compatibility |

---

*Next: [03-kafka-publisher.md](./03-kafka-publisher.md) - The audit-api-logs-srv service*
