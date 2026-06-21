# Bullet 2 — The Reusable Audit-Logging "Starter" JAR (`dv-api-common-libraries`)

> **Resume line (verbatim):**
> "Spearheaded a reusable Spring Boot starter JAR with async HTTP body capture (ContentCachingWrapper + @Async thread pool), adopted as the organization standard, reducing integration from 2 weeks to 1 day per service."

> **This document is the single source of truth for this bullet.** Every claim below is grounded in the real code at `/Users/a0g11b6/Desktop/walmart/dv-api-common-libraries`. Where the resume language is generous or the code contradicts it, that is called out explicitly in Section 6 — read that section before any interview, because the worst outcome is being surprised by your own code.

---

## 0. The single most important honesty caveat (read first)

The resume says **"Spring Boot starter JAR."** The code is a **shared Spring Boot library JAR, not an auto-configured starter.** The difference is concrete and an interviewer who knows Spring will probe it:

- There is **no `src/main/resources` directory at all** in this repo (verified: `find src/main/resources` returns nothing).
- Therefore there is **no `META-INF/spring.factories`** (Boot 2.7 auto-config mechanism) and **no `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`** (Boot 3 mechanism).
- A real Spring Boot **starter** auto-configures itself: you add one dependency and beans appear. This JAR does **not** do that. The consuming service must do **two manual things**:
  1. **Component-scan** `com.walmart.dv.filters` and `com.walmart.dv.services` explicitly. Verified in `cp-nrti-apis/.../NrtiApiApplication.java`:
     ```java
     @ComponentScan(basePackages = {
         "com.walmart.platform.txn.springboot.interceptor",
         "com.walmart.platform.txn.springboot3.filters",
         "com.walmart.cpnrti",
         "com.walmart.platform.ccm.client.processor",
         "com.walmart.dv.filters",      // <-- the jar
         "com.walmart.dv.services"      // <-- the jar
     })
     ```
  2. **Provide a `WebClient` bean themselves** — the jar's `AuditHttpServiceImpl` `@Autowired`s a `WebClient` but never defines one. Verified in `cp-nrti-apis/.../configs/WebClientConfig.java`.

**How to say it in the interview (one breath):** *"I'll be precise — it's packaged and consumed as a shared Spring Boot library jar, not a true auto-configured starter. There's no `spring.factories`, so the consumer component-scans `com.walmart.dv.*` and supplies a `WebClient` bean. If I were hardening it for true org-wide self-service I'd add an `AutoConfiguration.imports` file and a `@ConditionalOnProperty` auto-config class so it's genuinely zero-config. I described it as a 'starter' on the resume as shorthand for 'reusable drop-in', but the honest term is shared library."*

Saying this **before** they catch it converts a gotcha into a signal of senior-level precision.

---

## 1. Plain-English: what this actually is (ELI5 → precise)

**ELI5.** Imagine every API service in our org needs to keep a logbook: "someone called endpoint X, here's what they sent, here's what we answered, here's how long it took." Writing that logbook code correctly — capturing the request body without breaking the request, doing it without slowing the API down, signing it, shipping it somewhere central — is fiddly and easy to get wrong. Instead of every team rewriting it (2 weeks of work and bugs each time), I built it **once** as a library. A team adds one dependency, flips a config flag, and their service now auto-records every call to a central audit system — about a day of work.

**Precise.** `dv-api-common-libraries` (Maven coords `com.walmart:dv-api-common-libraries`, in-repo `pom.xml` version **0.0.45**, the version `cp-nrti-apis` consumes is **0.0.61**) is a **Spring Boot 2.7.11 / Java 11** JAR. Its job: transparently capture the HTTP request and response of audited endpoints inside any consuming service, build a structured `AuditLogPayload`, sign it with Walmart consumer-signature auth, and **asynchronously** POST it to the centralized audit producer service (`audit-api-logs-srv`). Everything is config-driven via Strati CCM:
- A **master feature flag** (`featureFlagConfig.isAuditLogEnabled`) turns the whole thing on/off at runtime, no redeploy.
- An **endpoint allow-list** (`auditLoggingConfig.enabledEndpoints`) controls which paths get audited.
- A **response-body toggle** (`auditLoggingConfig.isResponseLoggingEnabled`) controls whether response bodies are captured (request bodies always are).

This is **Tier 1 (capture)** of the larger audit pipeline. Downstream: `audit-api-logs-srv` (Avro → Kafka producer) → Kafka topic `api_logs_audit_{env}` → `audit-api-logs-gcs-sink` (Kafka Connect → Parquet in GCS, geo-segregated US/CA/MX).

The two headline mechanisms in the resume line are both real and verifiable:
- **`ContentCachingWrapper`** — `LoggingFilter` wraps the request/response in `ContentCachingRequestWrapper` / `ContentCachingResponseWrapper` so the body can be read for auditing *and* still be consumed by the application (a servlet input stream can only be read once).
- **`@Async` thread pool** — `AuditLogService.sendAuditLogRequest` is annotated `@Async`, running on a `ThreadPoolTaskExecutor` (`AuditLogAsyncConfig`: core 6, max 10, queue 100, prefix `Audit-log-executor-`). This is what keeps the audited service's request latency unaffected: capture is cheap and synchronous, but the sign + HTTP POST happens **off the request thread**.

---

## 2. The real architecture (grounded in code)

### 2.1 File map (real paths)

```
dv-api-common-libraries/
├── pom.xml                          # com.walmart:dv-api-common-libraries:0.0.45, parent spring-boot-starter-parent 2.7.11, java 11, packaging jar
├── kitt.yaml                        # KITT deploy scaffolding (vestigial — this is a LIBRARY, not a deployable)
├── sr.yaml                          # Service Registry scaffolding (also vestigial; references cp-data-apis-common product-controller demo)
├── ccm/NON-PROD-1.0-ccm.yml         # CCM config defn; note: security.mask.enable: 'false'  <-- masking OFF
├── README.md                        # one line: "# dv-api-common-libraries"  (essentially empty)
├── (NO src/main/resources)          # <-- proves: not an auto-configured starter
└── src/main/java/com/walmart/dv/
    ├── filters/LoggingFilter.java            # OncePerRequestFilter @Order(LOWEST_PRECEDENCE)
    ├── services/AuditLogService.java         # @Async sendAuditLogRequest — sign + delegate
    ├── services/AuditHttpService.java        # generic interface <R> sendHttpRequest(...)
    ├── services/impl/AuditHttpServiceImpl.java  # reactive WebClient .block()  (dead RestTemplate import)
    ├── configs/AuditLoggingConfig.java       # @io.strati.Configuration("auditLoggingConfig")
    ├── configs/FeatureFlagCCMConfig.java      # @io.strati.Configuration("featureFlagConfig")
    ├── configs/auditlog/AuditLogAsyncConfig.java  # @EnableAsync + taskExecutor 6/10/100
    ├── payloads/AuditLogPayload.java         # 18-field snake_case JSON (Lombok @Builder)
    ├── utils/AuditLogFilterUtil.java         # static: build payload, headers, error parse, file read
    └── constants/AppConstants.java           # CCM property-name + header constants
```

### 2.2 ASCII end-to-end flow (capture → ship)

```
   Inbound HTTP request to the AUDITED service (e.g. cp-nrti-apis POST /store/inventoryActions)
        │
        ▼
   [ Servlet filter chain ... security, Strati txn, XSS, CORS ... ]
        │   LoggingFilter is @Order(Ordered.LOWEST_PRECEDENCE)  → runs LAST (closest to controller)
        ▼
 ┌─────────────────────────────────────────────────────────────────────────────────────┐
 │ LoggingFilter.doFilterInternal  (extends OncePerRequestFilter)                        │
 │  1. gate: featureFlagCCMConfig.isAuditLogEnabled() == TRUE ?                          │
 │  2. skip if URI contains "/actuator"                                                  │
 │  3. shouldNotFilter(): drop unless servletPath ∈ auditLoggingConfig.enabledEndpoints()│
 │  4. requestTs = Instant.now().getEpochSecond()                                        │
 │  5. wrap: ContentCachingRequestWrapper(request), ContentCachingResponseWrapper(resp)  │
 │  6. filterChain.doFilter(wrappedReq, wrappedResp)  ── controller runs HERE ──┐        │
 │  7. responseTs = now;  requestBody = wrapper.getContentAsByteArray()         │        │
 │  8. if isResponseLoggingEnabled → responseBody = respWrapper bytes           │        │
 │  9. AuditLogFilterUtil.prepareRequestForAuditLog(...) → AuditLogPayload (UUID)│        │
 │ 10. auditLogService.sendAuditLogRequest(payload, cfg)  ── @Async, off-thread─┼──┐     │
 │ 11. contentCachingResponseWrapper.copyBodyToResponse()  ◄── MUST do this or  │  │     │
 │     the client gets an EMPTY body (cached bytes not flushed otherwise)       │  │     │
 └──────────────────────────────────────────────────────────────────────────────┘  │   │
        │ (request thread returns to client immediately after step 11)               │   │
        ▼                                                                            │   │
   HTTP response to client  (audit work has NOT blocked this path)                   │   │
                                                                                     │   │
        ┌────────────────────────────────────────────────────────────────────────────┘   │
        │ @Async hop onto ThreadPoolTaskExecutor "Audit-log-executor-" (core6/max10/q100) │
        ▼                                                                                  │
 ┌─────────────────────────────────────────────────────────────────────────────────────┐│
 │ AuditLogService.sendAuditLogRequest  (@Async)                                          ││
 │  • URI = auditLoggingConfig.getUriPath()   (CCM prop "auditLogURI")                    ││
 │  • payload → JsonNode via ObjectMapper.convertValue                                    ││
 │  • getAuditLogHeaders: AuthSign.getAuthSign(consumerId, privateKey, keyVersion)        ││
 │       → 4 headers: WM_CONSUMER.ID, WM_SEC.AUTH_SIGNATURE, WM_SEC.KEY_VERSION,          ││
 │                    WM_CONSUMER.INTIMESTAMP  + Content-Type: application/json            ││
 │  • AuditHttpServiceImpl.sendHttpRequest(uri, POST, entity, Void.class)                 ││
 │  • try/catch (ResourceAccessException|SignatureHandleException|HttpMessageNotWritable| ││
 │              HttpClientErrorException|HttpServerErrorException) → log.error, NEVER throw││
 └─────────────────────────────────────────────────────────────────────────────────────┘│
        │                                                                                  │
        ▼                                                                                  │
 ┌─────────────────────────────────────────────────────────────────────────────────────┐│
 │ AuditHttpServiceImpl.sendHttpRequest  — reactive WebClient, used BLOCKINGLY            ││
 │   webClient.method(POST).uri(uri).headers(...).body(...).exchangeToMono(toEntity).block()│
 └─────────────────────────────────────────────────────────────────────────────────────┘│
        │ HTTP POST application/json                                                        │
        ▼
   audit-api-logs-srv  POST /v1/logs/api-requests → 204 → unbounded pool → Avro → Kafka → GCS sink
                                                          (Tier 2 / Tier 3 — separate bullets)
```

### 2.3 The end-to-end flow in words (what to narrate)

1. A request hits an audited service. Because `LoggingFilter` is `@Order(Ordered.LOWEST_PRECEDENCE)`, it sits **last** in the filter chain — closest to the controller — so it observes the request after all auth/tracing filters and observes the final response after the controller writes it.
2. It checks the **CCM master flag** and the **endpoint allow-list**. If either says no, it does nothing (and importantly, `shouldNotFilter` returning true means it never even wraps — the request passes straight through untouched).
3. It wraps request and response in **ContentCaching wrappers**, then calls `filterChain.doFilter(...)`. The controller runs. The wrappers transparently buffer the bytes that flow through them.
4. After the controller returns, it reads the buffered request bytes (and response bytes if enabled), builds the `AuditLogPayload`, and hands it to the `@Async` service.
5. **Critically**, it calls `contentCachingResponseWrapper.copyBodyToResponse()` — because the response wrapper *captured* the bytes instead of writing them to the real output stream, you must flush them back or the client receives an empty body.
6. The `@Async` method, now on a pool thread, signs the payload and POSTs it. Any transport/signing failure is caught and logged — **it never propagates back into the request path**, so an audit-sink outage can't fail a customer's API call.

---

## 3. Every design decision

| # | Decision | Why (the real engineering reason) | Alternatives considered | Trade-off / what we gave up |
|---|----------|-----------------------------------|-------------------------|------------------------------|
| 1 | **Extract into a shared JAR** rather than copy-paste per service | DRY across the org; one place to fix bugs / evolve the audit contract; consistent payload shape so the downstream Avro schema and GCS partitioning are uniform | (a) copy code per service; (b) a sidecar/proxy that sniffs traffic; (c) service-mesh access logs | A shared jar creates a **fan-out upgrade problem** — a breaking change forces N services to bump versions; version drift (0.0.45 in-repo vs 0.0.61 consumed) is real. |
| 2 | **Capture in a servlet `Filter`** (`OncePerRequestFilter`) not an interceptor/AOP | A filter sees the **raw** request/response and can wrap the streams *before* anything reads them — interceptors run after the servlet has already started reading the body | `HandlerInterceptor` (too late for the body); `@Aspect` around controllers (doesn't see transport-level bytes); manual logging in each controller (the thing we're eliminating) | Filters are servlet-container coupled (`javax.servlet`); harder to unit-test than a POJO; you operate on byte arrays not typed objects. |
| 3 | **`ContentCachingRequestWrapper` / `ContentCachingResponseWrapper`** | A servlet `InputStream`/`OutputStream` can be **read only once**. If the audit code reads the body, the controller gets nothing (and vice versa). The wrappers buffer bytes so **both** the app and the auditor can read them | (a) read+re-wrap the stream manually; (b) re-parse from a `@RequestBody` object (loses raw bytes, misses validation-rejected payloads) | The **entire body is buffered in heap memory** — memory cost scales with body size × concurrency; no size cap in this code → large/streaming/multipart uploads are a latent OOM and a correctness risk (see §6). |
| 4 | **`@Async` capture + ship** off the request thread | Keeps the audited service's **request latency** unaffected. Signing (crypto) + an outbound HTTP POST on the hot path would add real milliseconds and a failure dependency to every audited call | (a) synchronous POST (couples API latency + availability to the audit sink); (b) write to a local queue/disk and drain (more infra) | If the pool saturates, audit logs are silently **dropped** (default `AbortPolicy`) or, worse, the `@Async` caller swallows the rejection — no backpressure, no delivery guarantee. |
| 5 | **`ThreadPoolTaskExecutor` core 6 / max 10 / queue 100** with named prefix | Bounded pool = bounded memory/threads (contrast with the *unbounded* pool in `audit-api-logs-srv`); named threads (`Audit-log-executor-`) make thread dumps readable | unbounded `newCachedThreadPool` (chosen downstream — and it's a known risk); a single-thread executor (too slow); a `@KafkaTemplate` direct from the lib (couples every service to Kafka) | With **no `RejectedExecutionHandler` set**, the default is `AbortPolicy`, which throws `RejectedExecutionException` *on the @Async machinery thread* — effectively a dropped audit log under burst. We traded delivery guarantee for isolation. |
| 6 | **CCM (Strati) config-driven**: master flag + endpoint allow-list + response toggle + key path | Flip auditing **at runtime without redeploy** — vital for incident response (kill audit if the sink is down) and gradual rollout per endpoint | Spring `@ConfigurationProperties` from yaml (needs redeploy to change); a DB feature-flag table (more infra) | Behavior is now **invisible in code** — you must look at CCM to know what's audited; a misconfigured allow-list silently audits nothing or everything. |
| 7 | **Sign the audit POST** with Walmart consumer-signature auth (`AuthSign` from `cp-data-apis-common` 0.0.22) | The audit producer is a real authenticated Walmart service; the lib must present the same 4 `WM_*` signed headers any caller does | mTLS only (handled at mesh, but app-level signature is the org standard for these APIs); no auth (rejected) | Reads the **private key from local disk** every call (`getAuditPrivateKeyPath`) — file-IO per request on the pool thread; key distribution becomes an ops concern. |
| 8 | **Fire-and-forget, swallow all transport errors** in `AuditLogService` | Audit logging must **never** degrade or fail the business request. Catching + logging (never rethrowing) guarantees an audit outage is invisible to customers | propagate failures (rejected — would break APIs); retry with backoff (not implemented here) | **Zero delivery guarantee.** A failed POST is a log line and a lost audit record — no retry, no DLQ at this tier. |
| 9 | **Reactive `WebClient` used with `.block()`** | The org was standardizing on WebClient; it's already on the classpath via `spring-boot-starter-webflux` | `RestTemplate` (there's a **dead import** of it — it was the original plan); async non-blocking with a returned `Mono` | You pay WebClient's complexity but get none of its non-blocking benefit (you block immediately). On a bounded pool, a slow sink can exhaust the 6–10 threads. |
| 10 | **Snake_case `AuditLogPayload` with `@JsonInclude(NON_EMPTY)`** | Matches the downstream JSON contract that `audit-api-logs-srv` deserializes and the Avro `LogEvent` schema; `NON_EMPTY` trims payload size | a Map/generic JSON (loses type safety); protobuf/Avro from the lib (over-coupling) | `NON_EMPTY` means absent fields silently disappear — downstream must treat everything as optional (it does: Avro fields are nullable-with-default). |

---

## 4. Deep-dive Q&A (Fundamentals → Internals → Scenarios → Behavioral)

### A. FUNDAMENTALS

**Q1. What problem does this library solve, in one sentence?**
> "It gives every API service in our org drop-in, runtime-configurable audit logging — capture the request/response of selected endpoints, build a structured payload, and ship it asynchronously to a central audit pipeline — so teams don't each reinvent it. That collapsed integration from roughly two weeks of bespoke work to about a day."

**Q2. Why a `Filter` and not an interceptor or `@Aspect`?**
> "Because I need the **raw transport bytes**, and I need to wrap the streams *before* anything reads them. A servlet `InputStream` can only be read once. A `HandlerInterceptor` runs after Spring has already begun resolving `@RequestBody`, so the stream is consumed. An `@Aspect` around the controller sees typed Java objects, not the raw body, and misses requests that were rejected before reaching the controller. A `Filter` at `LOWEST_PRECEDENCE` sits at the boundary, wraps both streams, and observes the final response too."

**Q3. Why `OncePerRequestFilter` specifically?**
> "It guarantees the filter logic runs exactly once per request even when the container forwards or dispatches internally (async dispatch, error dispatch, `RequestDispatcher.forward`). Without it, a single client request that gets internally re-dispatched could produce duplicate audit records. `OncePerRequestFilter` tracks an attribute on the request to dedupe."

**Q4. Walk me through `ContentCachingRequestWrapper`. Why is it needed?**
> "The core constraint: `HttpServletRequest.getInputStream()` is a one-shot stream. If my audit code reads the body to log it, the controller's `@RequestBody` binding finds an empty stream — and vice versa. `ContentCachingRequestWrapper` wraps the request; as the *application* reads the body, the wrapper transparently tees the bytes into an internal buffer. After the chain completes I call `getContentAsByteArray()` to retrieve exactly what was read. The response side is symmetric with `ContentCachingResponseWrapper`, except it buffers *outgoing* bytes — which is why I must call `copyBodyToResponse()` at the end, or the client receives an empty body."

**Q5. What's in the payload you ship?**
> "`AuditLogPayload` is an 18-field snake_case JSON: `request_id` (a fresh UUID), `service_name`, `endpoint_name` (the matched allow-list entry), `version` (hardcoded `v1`), `path`, `supplier_company` (empty in this lib), `method`, `request_body`, `response_body`, `response_code`, `error_reason` (parsed from `errors[0].message` on non-2xx), `request_ts`, `response_ts`, `request_size_bytes`, `response_size_bytes`, `created_ts`, `trace_id`, and a `headers` map. It's a Lombok `@Builder` with `@JsonInclude(NON_EMPTY)`."

**Q6. How does a consuming team turn it on?**
> "Three things: (1) add the Maven dependency `com.walmart:dv-api-common-libraries`; (2) component-scan `com.walmart.dv.filters` and `com.walmart.dv.services`, and provide a `WebClient` bean; (3) set the CCM config — flip `featureFlagConfig.isAuditLogEnabled=true`, list endpoints in `auditLoggingConfig.enabledEndpoints`, and set `auditLogURI`, `wmConsumerId`, `keyVersion`, `auditPrivateKeyPath`, `serviceApplication`. No redeploy needed to change the flags after that."

### B. INTERMEDIATE

**Q7. Why `@Order(Ordered.LOWEST_PRECEDENCE)` for the filter?**
> "I want auditing to be the **innermost** filter — last in, first out. By the time it runs, all security/auth/tracing filters have executed, so the request is fully decorated and the response I observe is the real, final one. If I ran it first, I'd capture a half-formed request and might not see filters that mutate the response. LOWEST_PRECEDENCE puts me closest to the controller."

**Q8. Explain the async hop precisely. What runs on which thread?**
> "Steps 1–11 in `doFilterInternal` run on the **request (Tomcat) thread**: gate checks, wrapping, `filterChain.doFilter` (so the controller runs on this thread too), reading the buffered bytes, building the payload, and `copyBodyToResponse()`. The single call `auditLogService.sendAuditLogRequest(...)` is `@Async`, so Spring's `AsyncExecutionInterceptor` submits it to the `taskExecutor` and returns immediately. The signing and the WebClient POST then run on an `Audit-log-executor-` pool thread. So the customer's latency only includes the cheap synchronous capture, not the crypto or the network round-trip."

**Q9. What are the exact pool parameters, and why those numbers?**
> "`AuditLogAsyncConfig`: corePoolSize 6, maxPoolSize 10, queueCapacity 100, threadNamePrefix `Audit-log-executor-`. The semantics matter: Spring's `ThreadPoolTaskExecutor` only grows past core (6) toward max (10) **after the queue (100) is full**. So under load it buffers up to 100 tasks on 6 threads before spinning up to 10. The numbers are modest because each task is a single fast POST and audit is best-effort — I sized for steady-state, not worst-case burst. Honestly, in hindsight I'd make these CCM-tunable rather than hardcoded."

**Q10. What happens when the pool *and* queue are both full?**
> "No `RejectedExecutionHandler` is configured, so it's the JDK default `AbortPolicy`: the executor throws `RejectedExecutionException`. Because the submission happens inside Spring's async interceptor, that rejection effectively means the **audit log is dropped** for that request — the business request is unaffected. That's the correct priority (never hurt the customer) but it's a silent data-loss path. If I cared about delivery I'd switch to `CallerRunsPolicy` (which applies backpressure by running the task on the request thread — trading latency for durability) or add a bounded retry/local-spool. For *audit* logs I deliberately favored isolation over guaranteed delivery."

**Q11. How does the endpoint allow-list work, and what's the matching semantics?**
> "`shouldNotFilter` returns true (skip) unless `auditLoggingConfig.enabledEndpoints()` has an entry that `request.getServletPath()` **contains**. It's a substring `contains` match, not exact or regex. So `/transactionHistory` in the list matches `/store/123/gtin/456/transactionHistory`. Cheap and flexible, but the gotcha is substring collisions — a configured `/status` would also match `/statusReport`. In practice the endpoint names are distinctive enough that it's safe, but exact/prefix matching would be safer."

**Q12. How is the error reason extracted?**
> "`AuditLogFilterUtil.getErrorFromResponse`: only on non-2xx (not 200/201/204) and non-blank body, it parses the response as JSON and pulls `errors[0].message`. If parsing fails it logs and returns empty. So `error_reason` is populated only for our standard error envelope shape; a non-standard error body just yields a null reason."

**Q13. What auth headers does the outbound POST carry and how are they generated?**
> "Four: `WM_CONSUMER.ID`, `WM_SEC.AUTH_SIGNATURE`, `WM_SEC.KEY_VERSION`, `WM_CONSUMER.INTIMESTAMP`, plus `Content-Type: application/json`. The signature comes from `AuthSign.getAuthSign(consumerId, privateKey, keyVersion)` in the shared `cp-data-apis-common` lib — it returns a `SignatureDetails` with signature + timestamp. The private key is read from disk at `auditPrivateKeyPath` (WCNP `/etc/config` or `/etc/secrets`)."

### C. DEEP / INTERNALS

**Q14. `ContentCachingResponseWrapper` buffers the response. Doesn't that defeat streaming and add latency/memory?**
> "Yes, and that's a real trade-off. The wrapper holds the entire response body in memory until `copyBodyToResponse()` flushes it, so (a) memory scales with body size × concurrency, and (b) any chunked/streaming or SSE response is effectively buffered, breaking true streaming. For our APIs — small JSON inventory responses — it's fine. For a service returning large payloads or streams I would *not* enable response-body logging (that's exactly why `isResponseLoggingEnabled` is a separate CCM toggle), or I'd cap captured bytes. This lib has **no size cap**, which I'd add before using it on heavy endpoints."

**Q15. The size fields — how are `request_size_bytes`/`response_size_bytes` computed?**
> "Honestly, incorrectly. The code does `request.toString().getBytes().length` and `response.toString().getBytes().length`. That's the length of the servlet object's `toString()`, **not** the body length. So those two fields are effectively meaningless telemetry. The actual bodies are captured correctly via the wrappers; only the *size* metric is wrong. There's also a dead guard — `Objects.isNull(...someInt.length)` on a primitive `int` can never be true. I'd fix this to use the captured byte-array lengths. It's a known wart I own."

**Q16. You said reactive WebClient but `.block()`. Why, and what's the cost?**
> "The `AuditHttpServiceImpl` builds a reactive call — `webClient.method(POST).uri().headers().body().exchangeToMono(toEntity)` — then `.block()`s immediately. There's even a leftover `import ...RestTemplate` that's unused, which tells you the original design was RestTemplate and it was half-migrated to WebClient without going fully non-blocking. The cost: I get WebClient's API but none of its event-loop benefit; I'm just occupying one of my 6–10 pool threads for the whole round-trip. The cleaner design is to return the `Mono` and let it complete on the reactor scheduler, freeing the pool entirely. For a fire-and-forget audit, fully non-blocking would be strictly better."

**Q17. How does `@Async` actually work under the hood here? What enables it?**
> "`AuditLogAsyncConfig` is `@Configuration @EnableAsync`. `@EnableAsync` registers a `AsyncAnnotationBeanPostProcessor` that wraps `@Async` beans in a proxy. When `LoggingFilter` calls `auditLogService.sendAuditLogRequest(...)`, the call hits the proxy, which submits the invocation to the `Executor` bean named `taskExecutor` (Spring resolves a single `Executor`/`TaskExecutor` bean by convention, or by name `taskExecutor`). The method returns `void`, so the caller gets nothing back — true fire-and-forget. One subtlety: `@Async` only works on **public** methods called **through the proxy** — a self-invocation within the same bean would bypass it. Here the call is cross-bean (filter → service), so the proxy is honored."

**Q18. The `@Async` method takes the `AuditLoggingConfig` as a parameter. Why pass it instead of injecting it into the service?**
> "`AuditLoggingConfig` is a Strati `@ManagedConfiguration` proxy, resolved in the `LoggingFilter`. Passing it forward avoids the service re-resolving CCM and keeps a consistent config snapshot for that request. It's a minor design choice; injecting it directly into the service with `@ManagedConfiguration` would also work."

**Q19. Why Spring Boot 2.7.11 / Java 11 when the other services are Boot 3 / Java 17?**
> "This is the outlier and I'm upfront about it. The lib predates the Boot 3 migration and is still on **2.7.11 / Java 11 / `javax.servlet`**. The pom even has a quirk: it declares **`jakarta.servlet-api` 6.1.0 as `provided`** in coordinates, but the actual code imports `javax.servlet.*` — so the running classpath is the `javax` Tomcat 9.0.99 the parent brings in. Consuming Boot 3 / Java 17 services (NRTI) can still use it because (a) NRTI **excludes `spring-boot-starter-webflux`** from the jar to avoid pulling the old reactive starter and supplies its own WebClient, and (b) at the bytecode level Java 17 runs Java 11 classes, and the `javax`→`jakarta` filter difference is bridged because NRTI also component-scans the `com.walmart.dv.filters` package and the filter contract it implements (`OncePerRequestFilter`) is satisfied by the version on NRTI's classpath. **This is the riskiest compatibility claim** — see §6 — and the honest answer is: the jar would ideally be recompiled against jakarta for Boot 3. If they push hard, I pivot to 'the real fix is a jakarta-targeted build of the lib; the current cross-version reuse works because of the explicit webflux exclusion and self-provided WebClient bean.'"

**Q20. Why is `Tomcat 9.0.99` pinned explicitly in the pom?**
> "The parent 2.7.11 would bring an older `tomcat-embed-core`; pinning 9.0.99 is a CVE patch — overriding the managed version to pull in the security-fixed Tomcat without bumping the whole Boot version. The pom does it by excluding the transitive `tomcat-embed-core` and adding 9.0.99 directly."

**Q21. Where does the Avro schema / Kafka live? Is that in this jar?**
> "No — and that's an important boundary. This jar produces **JSON over HTTP** to `audit-api-logs-srv`. The JSON→Avro conversion, the `LogEvent` schema (`log.avsc`, namespace `com.walmart.dv.audit.model.api_log_events`), Schema Registry, and the Kafka produce all live in `audit-api-logs-srv`. The capture lib is intentionally Kafka-agnostic so consuming services don't take a Kafka client dependency just to be audited."

### D. SCENARIO / "WHAT IF"

**Q22. The audit sink (`audit-api-logs-srv`) is down. What happens to live customer traffic?**
> "Nothing visible. The POST runs on the async pool; on failure it throws `ResourceAccessException` (or an HTTP 4xx/5xx exception), which `AuditLogService` catches and logs — it never rethrows. The customer's request already returned at `copyBodyToResponse()`. The cost is **lost audit records** for the outage window, with no retry or DLQ at this tier. If audit completeness mattered more, I'd add a bounded retry and/or a local disk spool, but I deliberately chose availability of the business API over audit durability."

**Q23. A burst of 10,000 RPS hits an audited endpoint. What breaks first?**
> "The async pool. 6 core threads draining one POST each, queue of 100, then up to 10 threads. If the sink is slow (each `.block()` holds a thread for the round-trip), the queue fills and new tasks are rejected (`AbortPolicy`) → audit logs dropped. The **business path is still fine** — capture is cheap and the pool can't backpressure onto it given AbortPolicy. The second risk is **heap**: every in-flight request buffers its full body in the ContentCaching wrappers; 10k concurrent large bodies could OOM. So: dropped audits first, memory pressure second. At 10x scale I'd (a) go fully non-blocking to free pool threads, (b) cap captured body size, (c) make the pool CCM-tunable, (d) consider batching POSTs."

**Q24. A consumer uploads a 50 MB multipart file to an audited endpoint. What happens?**
> "The `ContentCachingRequestWrapper` will try to buffer the whole 50 MB in heap, and if response logging is on, the response too. That's a memory spike per such request and could OOM under concurrency. There's **no size cap** in the code. Mitigations I'd apply: don't put multipart/upload endpoints in `enabledEndpoints`; add a max-capture-bytes config that truncates; or special-case multipart to log metadata only. This is a real limitation I'd flag to any team auditing upload endpoints."

**Q25. Two services run different versions of the jar (0.0.45 vs 0.0.61). Is that a problem?**
> "Potentially. The payload schema is the contract with `audit-api-logs-srv` and the downstream Avro `LogEvent`. As long as field changes are **additive** (new nullable fields, which the Avro schema is designed for — nullable-with-default), old and new producers coexist. The danger is a **rename or type change** — that's a breaking change that requires coordinating the producer service and the schema. We don't do true semantic versioning enforcement here, so the discipline is: only additive changes to `AuditLogPayload`, mirrored as nullable-with-default in `log.avsc`. The 0.0.45/0.0.61 gap is just normal version drift; the schemas are compatible."

**Q26. CCM flips `isAuditLogEnabled` to false mid-traffic. What happens to in-flight async tasks?**
> "Already-submitted tasks on the pool complete normally — the flag is only read at the top of `doFilterInternal` for *new* requests. So flipping it off stops new captures immediately but drains the in-flight queue. That's the desired behavior for an incident kill-switch: stop new load, don't lose what's already queued."

**Q27. What if `copyBodyToResponse()` were accidentally removed?**
> "Clients would get **empty response bodies** — a production-down bug. The response wrapper captured the bytes into its buffer instead of the real output stream; without the copy, nothing is flushed to the socket. This is the classic ContentCaching footgun, and it's exactly why this is the last line in the happy path. I'd guard it with a `finally`/integration test that asserts a non-empty body."

**Q28. Could auditing ever corrupt or alter the actual request/response?**
> "It shouldn't. The wrappers are transparent — they tee bytes, they don't transform. The one place corruption could occur is `copyBodyToResponse()` ordering or a `Content-Length` mismatch if a downstream filter set the header before we re-flushed; `ContentCachingResponseWrapper` handles `Content-Length` correctly on copy. The bigger real risk isn't corruption, it's the **memory buffering** and the **header leak** (next section)."

### E. BEHAVIORAL / OWNERSHIP

**Q29. "Spearheaded" — what was actually yours?**
> "I owned the design and the capture tier: the filter-based capture with ContentCaching wrappers, the async off-thread shipping model and pool sizing, the CCM-driven feature-flag + endpoint allow-list design, the signed-POST integration with `cp-data-apis-common`, and the integration pattern that the first consumer (`cp-nrti-apis`) adopted. I drove it being picked up as the org pattern for CPerf services. I want to be precise though — `Nayana.BG` is the listed pom developer, so this was collaborative; my role was driving the design and the reusability/adoption story, not sole authorship of every line."

**Q30. How do you justify "2 weeks → 1 day"?**
> "Before, a team wiring audit logging from scratch had to: get the ContentCaching/stream-reuse right (the #1 time sink and bug source), build the async model and size a pool, implement Walmart signature auth, define the payload contract that matches the downstream schema, and test all of it — realistically a couple of sprints with review cycles. With the jar, integration is: add the dependency, add two packages to the component scan, add a WebClient bean, and set the CCM config — then validate one endpoint end-to-end. That's about a day. The two-week figure is the pre-library bespoke cost I'm comparing against; it's an estimate from the team's experience, not a stopwatch measurement, and I'd present it that way."

**Q31. What would you do differently if you rebuilt it today?**
> "Five things: (1) make it a **true auto-configured starter** with `AutoConfiguration.imports` + `@ConditionalOnProperty` so it's genuinely one-dependency zero-config; (2) recompile against **jakarta / Boot 3** so it's not the lone Boot 2.7 outlier; (3) go **fully non-blocking** (return the Mono) and add **bounded retry + size caps**; (4) **mask sensitive headers** (today it copies *all* headers including `Authorization`/`WM_SEC.*` with masking explicitly off) ; (5) fix the **size-byte computation** to use real body lengths. I can defend why each shortcut was acceptable at the time, but I know exactly where the seams are."

---

## 5. Defending the numbers

**"2 weeks → 1 day per service":**
- **What it measures:** developer effort to add audit logging to a new service.
- **How to derive it:** Pre-library, the work items are: ContentCaching stream-reuse (the hard part, often days of debugging empty-body bugs), async pool design, Walmart signature auth wiring, payload contract definition matching the downstream schema, plus tests and reviews → ~2 weeks. Post-library: 1 dependency + 2 component-scan packages + 1 WebClient bean + CCM config + 1 endpoint validated → ~1 day.
- **If pushed:** "It's an engineering estimate based on the team's before/after experience, not an instrumented metric. The credible core of it is that the genuinely hard, bug-prone part — stream reuse, async, and signing — is now solved once and consumed as config. Even if you discount it to '1 week → 1 day', the reuse argument holds."

**Pool sizing 6/10/100 — defend the numbers:**
- core 6 / max 10 are modest because each task is one fast POST and audit is best-effort; queue 100 absorbs short bursts. Honest caveat: they're hardcoded, not load-tested per service; I'd make them CCM-tunable.

**"<5ms" latency story (if conflated with Bullet 1/10):**
- The reason added latency is tiny is the **async hop** — the request thread only does capture + `copyBodyToResponse()`, never the crypto or the network POST. The sub-5ms figures for the *producer* (`audit-api-logs-srv` returning 204 immediately) belong to that service; here the point is the capture lib adds negligible synchronous overhead because the expensive work is off-thread. Be careful not to attribute the producer's 204-latency to this jar.

**"Organization standard / adopted":**
- Verifiable: `cp-nrti-apis` consumes `0.0.61`, component-scans `com.walmart.dv.filters`/`services`, and points `auditLoggingConfig` at `.../audit/api-logs-srv/v1/logs/api-requests`. The honest scope is "the CPerf/Luminate services in our org," not literally all of Walmart.

---

## 6. HONEST watch-outs (if they open the code, they'll see ___)

1. **"Starter" is generous — it's a library.** No `src/main/resources`, no `spring.factories`, no `AutoConfiguration.imports`. Consumers must component-scan and provide a WebClient. → Lead with this (Section 0).
2. **Boot 2.7.11 / Java 11 / `javax.servlet` outlier**, while consumers are Boot 3 / Java 17. The pom lists `jakarta.servlet-api` `provided` but code uses `javax`. Cross-version reuse works via NRTI's webflux exclusion + self-provided WebClient, but the clean fix is a jakarta rebuild. **This is the most likely place to get cornered** — have the "the real fix is a jakarta-targeted build" pivot ready.
3. **No masking — header leak.** `getServiceHeaders()` copies **every** request header into the audit payload, including `Authorization` and `WM_SEC.*` signature headers, and the CCM config explicitly sets `com.walmart.platform.logging.security.mask.enable: 'false'`. This is a real PII/secret-leak concern in the audit store. **Raise it proactively** as a known gap with a fix (allow-list of headers / mask sensitive ones).
4. **Size fields are wrong.** `request.toString().getBytes().length` is the servlet object's toString length, not the body size. The `Objects.isNull(int.length)` guard is dead. Own it as a known wart with a one-line fix.
5. **No delivery guarantee.** Fire-and-forget, no retry, no DLQ; pool rejection (`AbortPolicy`) silently drops audit logs under burst. Defensible (audit ≠ business-critical) but be explicit that it's a *choice*.
6. **Dead `RestTemplate` import** in `AuditHttpServiceImpl` betrays a half-finished RestTemplate→WebClient migration; and the WebClient is used blockingly (`.block()`), so no reactive benefit.
7. **No body-size cap** → large/multipart/streaming endpoints risk heap pressure / broken streaming. Don't audit upload endpoints without a cap.
8. **Vestigial deploy scaffolding.** `kitt.yaml` and `sr.yaml` exist as if this were a deployable service (KITT stages, a `product-controller` demo Swagger), but it's a **non-deployable library**. Easy to misread; clarify it's leftover archetype scaffolding.
9. **README is empty** (literally one line). No real docs — adoption relied on tribal knowledge / the NRTI reference integration. A self-service starter should ship docs.
10. **Substring `contains` matching** for the endpoint allow-list can have collisions (`/status` matches `/statusReport`). Fine in practice, but prefix/exact would be safer.

---

## 7. Follow-up rabbit holes (the deeper questions after the obvious ones)

**Q. Why not use Spring Boot's built-in `CommonsRequestLoggingFilter`?**
> "It logs to the app log, doesn't capture the response body, doesn't ship anywhere, and doesn't sign/structure the payload for a downstream pipeline. We needed structured capture + async ship + auth, so a purpose-built filter was warranted."

**Q. Why not the service mesh / Istio access logs, since you're already on WCNP with mTLS?**
> "Mesh access logs give you metadata (method, path, status, latency) but **not request/response bodies** — and the audit requirement was body-level. Bodies at the mesh would also mean the mesh terminating and buffering payloads, which is worse for security and memory. App-level capture is the right layer for body auditing."

**Q. Why JSON-over-HTTP from the lib instead of having the lib produce to Kafka directly?**
> "Decoupling. If the lib produced to Kafka, every audited service would take a Kafka client + Schema Registry dependency, broker config, and the Avro schema — heavy coupling for something that should be a drop-in. By POSTing JSON to a thin producer service, the capture lib stays light and the Kafka/Avro complexity is centralized in `audit-api-logs-srv`, which can evolve independently."

**Q. How would you make delivery reliable without hurting latency?**
> "Local durable buffer + async drain: write the payload to an on-disk append-only queue (or an in-process ring buffer with a bounded backlog), and have a drainer ship to the sink with retry/backoff. That decouples capture from delivery and survives sink outages, at the cost of disk and a drainer. For higher fidelity, produce directly to Kafka from a sidecar. For *audit* logs we judged best-effort acceptable; for, say, financial audit I'd build the durable buffer."

**Q. How do you prevent the audit POST from itself being audited (infinite loop)?**
> "The audit POST goes *out* to `audit-api-logs-srv`; it's not an inbound request to the audited service, so this filter never sees it. And `audit-api-logs-srv` doesn't run this capture filter on its own ingest endpoint. The `/actuator` skip also prevents health checks from being audited."

**Q. `@Async` returns void — how do you observe failures or success rate?**
> "Today: only `log.info`/`log.error` lines, no metrics. That's a gap. I'd add Micrometer counters (audit.sent / audit.failed / audit.rejected) and a timer on the POST, exported via the actuator `/prometheus` endpoint the deploy already exposes. Without that, the only signal of a silent drop is log scraping."

**Q. Thread-safety of the static `AuditLogFilterUtil`?**
> "It's stateless static methods operating on per-call parameters — no shared mutable state — so it's thread-safe across the pool. The `@NoArgsConstructor(AccessLevel.PRIVATE)` enforces no instantiation. The one risk is `getFileContents` doing disk IO per call (reading the private key), which is a per-request file read on the pool thread — I'd cache the key in memory."

**Q. What about trace correlation? `trace_id` looks empty.**
> "In this lib `traceId` is passed as an empty string from the filter (`String traceId = ""`). The real correlation is meant to come from Strati's transaction marking / OTEL context, and the downstream `audit-api-logs-srv` populates trace context from `wm_*` headers. So in this tier `trace_id` is a placeholder — another thing I'd wire to the actual MDC/trace context."

**Q. If two filters both wrap the response, do the ContentCaching wrappers compose?**
> "They nest — wrapping an already-wrapped response works, but you can end up double-buffering. Because this filter is `LOWEST_PRECEDENCE` and is the only one doing ContentCaching here, it's a single wrap. If another caching filter existed I'd ensure ordering so only one buffers, to avoid 2x memory."

---

## 8. One-paragraph + 30-second verbal pitch

**One-paragraph (written):**
`dv-api-common-libraries` is a shared Spring Boot 2.7 / Java 11 JAR I drove that gives any CPerf service drop-in, runtime-configurable API audit logging. A `LoggingFilter` (an `OncePerRequestFilter` at `LOWEST_PRECEDENCE`) wraps each request/response in Spring's `ContentCaching` wrappers — necessary because a servlet input stream is read-once, so wrapping lets both the app and the auditor read the body — gates on a CCM feature flag plus an endpoint allow-list, builds an 18-field `AuditLogPayload`, and hands it to an `@Async` `ThreadPoolTaskExecutor` (core 6 / max 10 / queue 100) that signs it and POSTs it to the central audit producer. Doing the sign+ship off the request thread is what keeps the audited service's latency unaffected, and swallowing all transport errors means an audit-sink outage never fails a customer call. It cut audit integration from roughly two weeks of bespoke, bug-prone work (mostly getting stream-reuse and async right) to about a day of dependency + config. I'm precise that it's a shared *library*, not a true auto-configured starter — consumers component-scan `com.walmart.dv.*` and supply a WebClient — and I know its seams: it's the lone Boot 2.7 outlier, it copies headers unmasked, and it offers no delivery guarantee, all of which I can defend as deliberate trade-offs with concrete fixes.

**30-second verbal:**
> "I built the reusable audit-capture library every CPerf service uses. A servlet filter wraps the request and response in ContentCaching wrappers — needed because the body is a read-once stream — captures it, and hands it to an async thread pool that signs and ships it to our central audit service. The async hop is the trick: the customer's request never waits on crypto or the network, and an audit outage can't fail their call. It's all CCM-flag driven, so teams flip it on per endpoint without redeploying. That turned roughly two weeks of fiddly per-service audit code into about a day of add-a-dependency-and-config. I'll be precise — it's a shared library, not a true auto-configured starter, and I know exactly where I'd harden it next: jakarta rebuild, header masking, and bounded retry."

---

### Appendix: verified code anchors (quote these if challenged)

- Pool: `AuditLogAsyncConfig` — `setCorePoolSize(6); setMaxPoolSize(10); setQueueCapacity(100); setThreadNamePrefix("Audit-log-executor-")`. No `setRejectedExecutionHandler` → default `AbortPolicy`. Test `AuditLogAsyncConfigTest` asserts exactly 6/10/100.
- Filter: `LoggingFilter` `@Order(Ordered.LOWEST_PRECEDENCE)` extends `OncePerRequestFilter`; gates on `featureFlagCCMConfig.isAuditLogEnabled()`, skips `/actuator`, `shouldNotFilter` uses `enabledEndpoints().stream().noneMatch(servletPath::contains)`; wraps + `copyBodyToResponse()`.
- Async: `AuditLogService.sendAuditLogRequest` is `@Async`; catches `ResourceAccessException | SignatureHandleException | HttpMessageNotWritableException | HttpClientErrorException | HttpServerErrorException` and logs only.
- HTTP: `AuditHttpServiceImpl` `@Autowired WebClient`; `webClient.method(...).uri(...).headers(...).body(...).exchangeToMono(...).block()`; dead `import ...RestTemplate`.
- Payload: `AuditLogPayload` 18 fields, snake_case, `@JsonInclude(NON_EMPTY)`.
- Headers (unmasked leak): `AuditLogFilterUtil.getServiceHeaders` copies ALL headers; CCM `com.walmart.platform.logging.security.mask.enable: 'false'`.
- Size bug: `request.toString().getBytes().length` / `response.toString().getBytes().length`.
- Not-a-starter proof: no `src/main/resources`; consumer `NrtiApiApplication` component-scans `com.walmart.dv.filters` + `com.walmart.dv.services`; `WebClientConfig` supplies the `WebClient` bean; NRTI pom consumes `0.0.61` and **excludes** `spring-boot-starter-webflux` from the jar.
- Versions: in-repo `pom.xml` `0.0.45`; parent `spring-boot-starter-parent` `2.7.11`; `java.version` `11`; Tomcat pinned `9.0.99` (CVE); `cp-data-apis-common` `0.0.22`.
