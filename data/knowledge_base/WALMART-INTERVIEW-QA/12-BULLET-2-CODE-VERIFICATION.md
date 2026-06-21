# 12 — Bullet 2 (Common JAR) Line-by-Line Code Verification

> **Audit method (so you can trust the citations).** I read **every** `src/main/java` file (9 classes), the full `pom.xml`, all 3 YAML files (`kitt.yaml`, `sr.yaml`, `ccm/NON-PROD-1.0-ccm.yml`), `.looper.yml`, `README.md`, `sonar-project.properties`, and the 4 test files. Every `file:line` below was opened and confirmed in this pass. Where I infer rather than read, I say "inferred". The earlier version of this doc graded itself "every claim confirmed / fully authentic" — that was over-claiming: the **capture-path** claims are code-true, but the prior **pom-dependency** and **"non-deployable lib"** framings were wrong. Those are corrected here (see the "Corrections vs prior doc" block at the bottom). Confidence is now stated per claim.
>
> **Repo:** `/Users/a0g11b6/Desktop/walmart/dv-api-common-libraries` · artifact `com.walmart:dv-api-common-libraries:0.0.45` (`pom.xml:5-8`) · developer `Nayana.BG` (`pom.xml:312`).

---

## A. What this thing actually IS — a library that ALSO self-deploys

### A.1 It is NOT an auto-configured Spring Boot starter (high confidence — verified)

```
dv-api-common-libraries/
  pom.xml, kitt.yaml, sr.yaml, .looper.yml, README.md (25 bytes), sonar-project.properties
  ccm/NON-PROD-1.0-ccm.yml
  src/main/java/com/walmart/dv/...      ← code ONLY
  src/test/java/com/walmart/dv/...      ← 4 test classes
  ❌ NO src/main/resources at all
```

| Claim | Confidence | Evidence |
|---|---|---|
| No `src/main/resources` directory | **Verified** | `find src/main -type d` returns only `java/...` package dirs; `ls src/main/resources` → "No such file or directory" |
| No `spring.factories` / `AutoConfiguration.imports` | **Verified** | `find ... -name spring.factories -o -name '*.imports'` returns **nothing**. Impossible to ship auto-config without a `resources/META-INF`, which doesn't exist |
| It's a **library**: beans only resolve via component scan | **Verified** | All beans are `@Component` (`LoggingFilter:36`), `@Service` (`AuditLogService:31`, `AuditHttpServiceImpl:19`), `@Configuration` (`AuditLogAsyncConfig:13`) — no auto-config registration, so a consumer MUST `@ComponentScan("com.walmart.dv")` to pick them up |
| `README.md` is one line | **Verified** | Exactly **25 bytes**: the single string `# dv-api-common-libraries` |
| `pom.xml` build block references a non-existent resources dir | **Verified** | `pom.xml:323-329` declares `<resource><directory>src/main/resources</directory><filtering>true</filtering></resource>` for a dir that does not exist — harmless (Maven skips missing resource dirs) but telling: this pom was copied from a service template |

**Lead line:** *"To be precise it's a shared library, not an auto-configured Spring Boot starter — there's no `spring.factories` and no `src/main/resources` at all, so consumers component-scan `com.walmart.dv` and must supply their own `WebClient` bean for it to wire up."*

### A.2 It ALSO ships as a deployable `springboot-web` service (CORRECTION — the prior doc was wrong)

The earlier doc said `kitt.yaml`/`sr.yaml` were "vestigial on a non-deployable lib." That is **false**, and an interviewer who pulls `kitt.yaml` would catch it. This repo is **both** a consumed JAR **and** a deployable demo/host service:

```yaml
# kitt.yaml:2-3, 56
profiles:
  - springboot-web              # deploys as a Spring Boot web service
deploy:
  namespace: cp-bulk-feeds-api
```

```yaml
# kitt.yaml:119-141 — it gets real pod sizing + actuator probes
helm:
  values:
    min: { cpu: 500m, memory: 512Mi }
    max: { cpu: 900m, memory: 1024Mi }
    startupProbe:   { path: /actuator/health,                port: 8080 }
    livenessProbe:  { path: /actuator/health/livenessState,  port: 8080 }
    readinessProbe: { path: /actuator/health/readinessState, port: 8080 }
```

- Istio sidecar inject `true` + golden-signal gate enabled (`kitt.yaml:50-51`).
- Build = `maven-j11`, Zulu `11-jre` Docker image (`kitt.yaml:13,19`).
- Dev target cluster `eus2-dev-a3`, `ccm.serviceConfigVersion: NON-PROD-1.0` (`kitt.yaml:190,197`).
- `sr.yaml` registers it in **Service Registry** as a `REST` service, `businessCriticality: MINOR` (`sr.yaml:12,44`), with a `serviceMeshConfig` (`requestTimeout 1000ms`, `maxConnections 10`, `retries 5`, `consecutiveFailures 10` — `sr.yaml:45-52`), ingress `passthroughURIs` for `/products`, `/actuator/*`, `/swagger-ui/*` (`sr.yaml:58-92`), and an **embedded sample `product-controller` Swagger doc** (`sr.yaml:93-218`).

**Why it matters / how to frame it:** *"The repo doubles as a reference/demo host — there's a sample `product-controller` Swagger and a full `springboot-web` kitt profile so you can run it standalone — but the part that ships into our services is the audit-capture filter and its support classes consumed as a plain JAR. So it's a library with a deployable demo skin, not a pure jar and not an auto-config starter."* That precision is exactly the senior-signal move: name the messy reality instead of the clean story.

---

## B. Versions & dependency reality — the "lone outlier" talking point, grounded in the pom

### B.1 The headline versions (verified)

| Claim | Confidence | Evidence (`pom.xml`) |
|---|---|---|
| Spring Boot **2.7.11** | **Verified** | Parent block `pom.xml:15-20`; version literal on **line 18** (`<version>2.7.11</version>`) |
| **Java 11** | **Verified** | `pom.xml:30` `<java.version>11</java.version>`; reaffirmed by `sonar.java.source=11` and `.looper.yml:3-4` (Azul JDK 11) |
| Code uses `javax.servlet` (not jakarta) | **Verified** | `LoggingFilter.java:15-18`, `AuditLogFilterUtil.java:24-25`, even the test `LoggingFilterTest.java:14-15` import `javax.servlet.*` |

This SB2.7 / Java 11 / `javax` JAR is consumed by SB3 / Java 17 / `jakarta` `cp-nrti-apis` (per canon). That cross-version coexistence is the riskiest compatibility claim in Bullet 2.

### B.2 The dependency dance most candidates miss (the real depth)

The pom is **not** a clean "SB2.7/javax" pom — it is a mid-migration pom with a manual CVE-pin dance and a genuinely incoherent servlet-API state. Each row is line-verified:

| What | `pom.xml` | Why it's there / why it matters |
|---|---|---|
| `spring-boot-starter-web`, **excluding** `starter-logging` + `starter-tomcat` | `89-102` | Strati supplies its own logging; tomcat is re-added pinned below |
| `spring-boot-starter-tomcat` pinned `2.7.11`, **excluding** `tomcat-embed-core` | `103-113` | So the embed-core version can be hand-pinned |
| `tomcat-embed-core` **direct, pinned `9.0.99`** | `114-118` | A **manual CVE pin** above what 2.7.11 ships — the team is patching a Tomcat CVE by hand |
| `spring-boot-starter-webflux` **direct** | `120-123` | **This is what puts `WebClient` on the classpath.** (The prior doc implied the consumer brings webflux — wrong; the JAR ships it) |
| `jackson-databind` pinned `2.12.1` | `133-137` | Hand-pinned below the parent's managed version (another CVE/compat pin) |
| `org.json` **`20231013`** (direct) vs **`20230227`** (`dependencyManagement`) | `140-144` vs `262-266` | **Version conflict** — the direct dependency wins (`20231013`); the depMgmt entry is stale. Source of `JSONObject`/`JSONArray` in `AuditLogFilterUtil.getErrorFromResponse` |
| `com.walmart:cp-data-apis-common` `0.0.22` | `167-189` | Source of `AuthSign`, `SignatureDetails`, `SignatureHandleException` used in `AuditLogService` — the signing primitives |
| `commons-lang3` **`3.1`** (ancient; current is 3.14+) | `232-236` | Source of `StringUtils.EMPTY`/`isEmpty`/`isNotBlank`. Pinning to 3.1 is a smell — years out of date |
| `guava` `32.0.0-jre` | `250-254` | Source of `Preconditions.checkNotNull` in `AuditHttpServiceImpl:3,44-47` |
| `jakarta.persistence-api` (managed) **and** `jakarta.servlet-api` `6.1.0` scope `provided` | `154-164` | **Incoherent:** the pom carries **jakarta** servlet 6.1.0 while the code imports **javax** servlet. The provided jakarta dep is dead relative to the code |

**The real "lone outlier" answer (better than "it's SB2.7"):** *"It's the one SB2.7/Java 11 module our SB3/Java 17 services consume, and the pom shows it mid-migration — `javax.servlet` in the code but `jakarta.servlet-api 6.1.0` declared `provided`, an `org.json` direct-vs-managed version conflict, a manual `tomcat-embed-core 9.0.99` CVE pin, and `commons-lang3 3.1`. The clean fix is a jakarta rebuild on a current Boot line; until then it works because it's consumed as a plain jar and the consumer owns its own servlet stack."*

---

## C. The capture mechanism — request-thread vs `@Async`-thread timeline (the real latency story)

The prior doc's "the off-thread hop is the latency win" is only **partly** true. The expensive work — body buffering and the 18-field payload build (including copying **all** headers) — happens **on the request thread**. Only the JSON serialize + key read + sign + POST is off-threaded. Here is the verified split:

**On the customer's request thread (`LoggingFilter.doFilterInternal:66-117`):**
1. 3-part gate (`:70-71`): `featureFlagCCMConfig != null && auditLoggingConfig != null && isAuditLogEnabled()==TRUE`.
2. `/actuator` skip (`:74`): `request.getRequestURI().contains(AppConstants.ACTUATOR)` (`ACTUATOR="/actuator"`, `AppConstants:10`).
3. `shouldNotFilter(request)` gate (`:82`, defined `:123-128`).
4. Wrap request + response in `ContentCachingRequestWrapper`/`ContentCachingResponseWrapper` (`:83-86`).
5. `filterChain.doFilter(...)` — the actual business call (`:88-89`).
6. byte→String conversion of the cached request body, and response body if `isResponseLoggingEnabled()` (`:93-102`).
7. `prepareRequestForAuditLog(...)` (`:105-108`) → builds the 18-field payload **and** `getServiceHeaders(request)` copies **every** header into a map.
8. `auditLogService.sendAuditLogRequest(payload, config)` (`:111`) — the `@Async` handoff (cheap; just enqueues).
9. `contentCachingResponseWrapper.copyBodyToResponse()` (`:113`) — required, or the client gets an empty body.

**On the `@Async` pool thread (`AuditLogService.sendAuditLogRequest:48-80`):**
- JSON convert (`createAuditLogPayloadJson:85-87`), build signed headers (`getAuditLogHeaders:89-99`), **read the private key off disk** (`getSignatureDetails:101-110` → `AuditLogFilterUtil.getFileContents:166-175`), sign (`AuthSign.getAuthSign`), then `WebClient ... .block()` POST.

| Claim | Confidence | Evidence |
|---|---|---|
| `LoggingFilter` is `OncePerRequestFilter`, `@Order(LOWEST_PRECEDENCE)`, `@Component` | **Verified** | `LoggingFilter.java:35-37` — runs last so it sees the fully-filtered request/response |
| Gate is a **3-part compound** condition, not a single flag | **Verified** | `:70-71` (two null checks + the flag) **plus** the `/actuator` skip `:74` **plus** `shouldNotFilter` `:82` — four gates total before any work |
| CCM feature-flag drives it | **Verified** | `featureFlagCCMConfig.isAuditLogEnabled()` (`:71`); flag interface `FeatureFlagCCMConfig:7-15`, CCM key `isAuditLogEnabled` (`AppConstants:19`) |
| ContentCaching wrappers + `copyBodyToResponse()` | **Verified** | `:83-86,113` |
| Response body captured only if a 2nd flag is on | **Verified** | `auditLoggingConfig.isResponseLoggingEnabled()` (`:97-98`); flag at `AuditLoggingConfig:37-38` |
| Expensive work (body copy + payload + header copy) runs **on the request thread** | **Verified** | `:93-111` all execute before the `@Async` enqueue completes; only the enqueue at `:111` is async |

**Latency framing (corrected per canon):** *"The win is that signing + the network POST never run on the customer's thread — those are off-threaded. But I won't overstate it: body buffering and the 18-field payload assembly, including the all-headers copy, still tax the request thread. And the `<5ms P99` number is overhead added to the audited API, not audit end-to-end freshness, which is minutes given the downstream sink's 600s flush window."*

---

## D. `@Async` wiring correctness — works by naming convention, drops silently on saturation

| Claim | Confidence | Evidence |
|---|---|---|
| Pool: core **6** / max **10** / queue **100**, prefix `Audit-log-executor-` | **Verified** | `AuditLogAsyncConfig.java:20-23` |
| `@EnableAsync` present; bean **named `taskExecutor`** | **Verified** | `@Configuration @EnableAsync` (`:13-14`); `@Bean public Executor taskExecutor()` (`:17-18`). Spring's `@Async` resolves the executor by the **conventional bean name `taskExecutor`** — there's no `@Async("...")` qualifier on the method, so the wiring works purely by naming convention. Rename the bean and audit silently falls back to `SimpleAsyncTaskExecutor` (unbounded, a thread per task) |
| Default **AbortPolicy** → silent drop under saturation | **Verified (inferred behavior)** | No `setRejectedExecutionHandler(...)` is called (`:19-25`), so `ThreadPoolTaskExecutor` keeps its default `AbortPolicy`. When all 10 threads are busy and the 100-slot queue is full, the next submission throws `RejectedExecutionException` |
| The rejection is **lost** | **Verified** | `sendAuditLogRequest` is `@Async public void` (`AuditLogService:48-49`) — no `Future`/`CompletableFuture` returned, so nothing observes the rejection. There is no metric/counter on drops |
| The `@Async` catch is **narrow** — misses `RuntimeException` | **Verified** | The catch at `AuditLogService:73-78` only handles `ResourceAccessException | SignatureHandleException | HttpMessageNotWritableException | HttpClientErrorException | HttpServerErrorException`. A generic `RuntimeException`/`NPE`/`IllegalArgumentException` is **not** caught and, on an `@Async void` method, propagates to the executor's uncaught-exception path and is effectively lost |
| **Dead double null-guard** before the work | **Verified** | `:52-55` returns early if `auditLogPayload == null`, then `:57` immediately does `Optional.ofNullable(auditLogPayload).ifPresent(...)` on the **same** object — the `Optional` guard can never see null because of the early return. Dead code |

**Contrast worth volunteering (per canon):** *"Two different audit codepaths, two different failure modes. This shared-JAR path uses a **bounded** `core6/max10/queue100` pool with the default AbortPolicy — under burst it drops audit logs with no metric. The `audit-api-logs-srv` producer takes the opposite trap: an **unbounded** `Executors.newCachedThreadPool()`, which never rejects but can exhaust memory/threads. I'd fix this one with a `CallerRunsPolicy` plus a dropped-audit counter, and bound the other one."*

---

## E. The smells — each one now line-pinned (volunteer these = senior signal)

| Smell | Confidence | Evidence |
|---|---|---|
| **No header masking** — copies ALL headers incl. `Authorization`/`WM_SEC.*` | **Verified** | `AuditLogFilterUtil.getServiceHeaders:94-108` iterates `request.getHeaderNames()` and puts **every** name/value into the map — no allow/deny list, no mask. Whatever the gateway forwarded ends up in `payload.headers` |
| `request_size_bytes` / `response_size_bytes` are **meaningless** | **Verified** | `AuditLogFilterUtil:83-84` computes `request.toString().getBytes().length` — that's the **servlet object's identity/`toString()` string**, not the body byte count. Same for the response at `:85-86` |
| **Dead `Objects.isNull` guard on a primitive `int`** | **Verified** | `:83` `Objects.isNull(request.toString().getBytes().length) ? 0 : ...` — `byte[].length` is an `int`, can never be null, so the ternary always takes the else branch. Repeated for the response at `:85` |
| **Two different inputs to the same substring matcher** | **Verified** | The filter gate `shouldNotFilter` keys on `request.getServletPath()` (`LoggingFilter:127`), but the payload's `endpoint_name` (`getEndpointPath`) keys on `request.getRequestURI()` (`AuditLogFilterUtil:113-116`). Servlet path vs request URI differ when there's a context path — so the "is this endpoint audited?" decision and the recorded endpoint name use **different** inputs |
| Endpoint matching is substring `contains()` (collision-prone) | **Verified** | `getEndpointPath` → `enabledEndpoints.stream().filter(requestURI::contains)` (`:114`); `shouldNotFilter` → `noneMatch(servletPath::contains)` (`:127`). Enabling `/status` would also match `/statusReport` |
| `getErrorFromResponse` assumes a fixed error envelope, no length check | **Verified** | `:122-141` hard-codes `{"errors":[{"message":...}]}` (`ERROR="errors"`, `ERROR_MESSAGE="message"`, `AppConstants:24-25`), calls `errorArray.getJSONObject(0)` with **no length check**, and only runs for non-200/201/204. A different error shape silently yields an empty `errorReason` (caught `JSONException` → logged → empty) |
| **Dead `RestTemplate` import** alongside reactive `WebClient.block()` | **Verified** | `AuditHttpServiceImpl:15` imports `org.springframework.web.client.RestTemplate` (never used); the class actually does `webClient.method(...).uri(...).headers(...).body(...).exchangeToMono(r -> r.toEntity(type)).block()` (`:50-59`) — reactive client used synchronously. Half-finished migration artifact |
| No body-size cap → heap pressure | **Verified (inferred risk)** | `ContentCachingRequestWrapper`/`ResponseWrapper` (`LoggingFilter:83-86`) buffer the entire body in memory with no limit; a large/multipart upload is fully held to build the audit payload |
| Per-request **private-key disk read** on the async thread | **Verified** | `getSignatureDetails:104-105` → `AuditLogFilterUtil.getFileContents:166-175` does `Files.readAllLines(path).get(0)` on **every** audit send. The signing key is re-read from disk each call (security + perf smell) |
| Three effectively **dead/placeholder payload fields** | **Verified** | `version` is hardcoded `"v1"` (`WM_VERSION`, `AppConstants:23`, set at `AuditLogFilterUtil:71`); `supplier_company` is **always** `StringUtils.EMPTY` (`:73`); `trace_id` is **always** `""` (the `traceId=""` literal at `LoggingFilter:77`, threaded through to `AuditLogPayload`). The comment `//fetch traceId from service application` at `:76` is aspirational — it never happens |

### E.1 The 18-field payload + serialization annotations (was hand-waved before)

```java
// AuditLogPayload.java:19-58 (abridged)
@JsonIgnoreProperties(ignoreUnknown = true)
@JsonInclude(JsonInclude.Include.NON_EMPTY)        // ← why empty strings/maps drop out of the JSON
public class AuditLogPayload {
  @JsonProperty("request_id")          private String requestId;
  @JsonProperty("service_name")        private String serviceName;
  @JsonProperty("endpoint_name")       private String endpointName;
  @JsonProperty("version")             private String version;          // always "v1"
  @JsonProperty("path")                private String path;
  @JsonProperty("supplier_company")    private String supplierCompany;  // always ""
  @JsonProperty("method")              private String method;
  @JsonProperty("request_body")        private String requestBody;
  @JsonProperty("response_body")       private String responseBody;
  @JsonProperty("response_code")       private int    responseCode;
  @JsonProperty("error_reason")        private String errorReason;
  @JsonProperty("request_ts")          private long   requestTimestamp;
  @JsonProperty("response_ts")         private long   responseTimestamp;
  @JsonProperty("request_size_bytes")  private int    requestSizeBytes;   // meaningless (toString())
  @JsonProperty("response_size_bytes") private int    responseMessageBytes;
  @JsonProperty("created_ts")          private long   createdTimestamp;
  @JsonProperty("trace_id")            private String traceId;            // always ""
  @JsonProperty("headers")             private Map<String,String> headers; // ALL headers, unmasked
}
```

`@JsonInclude(NON_EMPTY)` is the subtle one: it's exactly **why** `error_reason` is set to `null` (not `""`) at `AuditLogFilterUtil:80` (`errorReason.isEmpty() ? null : errorReason`) — a null/empty field is then dropped from the serialized JSON entirely. The three placeholder fields (`version`, `supplier_company`, `trace_id`) are emitted only because `v1` is non-empty / dropped because empty.

### E.2 The signing path (correct in the prior doc — kept and deepened)

```java
// AuditLogService.getAuditLogHeaders:89-99
header.set(AppConstants.CONSUMER_ID,              auditLoggingConfig.getWmConsumerId());        // "WM_CONSUMER.ID"
header.set(AppConstants.CONSUMER_AUTH_SIGNATURE,  signatureDetails.getSignature());             // "WM_SEC.AUTH_SIGNATURE"
header.set(AppConstants.WM_SVC_KEY_VERSION,       auditLoggingConfig.getKeyVersion());          // "WM_SEC.KEY_VERSION"
header.set(AppConstants.WM_CONSUMER_IN_TIMESTAMP, signatureDetails.getTimestamp());             // "WM_CONSUMER.INTIMESTAMP"
```

The 4 header **names** are the `WM_SEC.*`/`WM_CONSUMER.*` constants (`AppConstants:13-18`); the signature is produced by `AuthSign.getAuthSign(consumerId, privateKey, keyVersion)` from `cp-data-apis-common 0.0.22` (`getSignatureDetails:101-110`), with the private key read per-call off disk (smell above).

---

## F. Two **independent** leak surfaces (the prior doc conflated them)

The old doc treated "no masking" and `mask.enable=false` as one point. They are **two separate causes with two separate fixes**:

1. **App-level header copy (code path).** `AuditLogFilterUtil.getServiceHeaders:94-108` copies **all** request headers — including `Authorization` and `WM_SEC.*` — verbatim into `payload.headers`, and `request_body`/`response_body` are captured verbatim (`AuditLogFilterUtil:75-78`). **Fix:** add a header allow/deny-list in code; redact bodies for sensitive endpoints. (The test `AuditLoggingUtilTest:118-143` literally asserts `Authorization: "Bearer token"` survives into the map — the leak is encoded into the test.)
2. **Platform-logging mask flag (CCM path).** `ccm/NON-PROD-1.0-ccm.yml:82` sets `com.walmart.platform.logging.security.mask.enable: 'false'` — but note **line 82 sits inside the `platform-logging-client` Telemetry override block** (`:70-86`), so it governs Walmart's platform **logging** masking, not the audit payload the app builds. **Fix:** flip the CCM flag. That alone does **not** clean the audit payload, because surface #1 is independent code.

*"There are two leak surfaces, not one: the app copies all headers into the audit payload in `getServiceHeaders`, and separately the platform-logging `mask.enable` is `false` in CCM. They need separate fixes — a code-side allow-list plus flipping the CCM flag."*

---

## G. Test coverage & quality gate — why the half-finished reactive code shipped

| Observation | Confidence | Evidence |
|---|---|---|
| `LoggingFilterTest` is **happy-path only** | **Verified** | `LoggingFilterTest:46-73` sets flag `true`, status `200`, asserts `filterChain.doFilter` and `auditLogService.sendAuditLogRequest` were invoked. **No** test for AbortPolicy drop, header masking, or error paths |
| Other tests exist (so don't claim "untested" wholesale) | **Verified** | `AuditLogAsyncConfigTest` (asserts 6/10/100 + prefix), `AuditHttpServiceImplTest` (null-arg `checkNotNull` paths + one happy WebClient mock + one error), `AuditLoggingUtilTest` (endpoint/error-envelope/header tests). But these are unit-narrow |
| Sonar gate is **75% Passive** — failures don't block deploy | **Verified** | `kitt.yaml:37-40` `threshold: 75`, `mode: Passive`; mirrored by `.looper.yml` running sonar in build/PR flows |
| `services/impl` (i.e. `AuditHttpServiceImpl`) is **excluded** from Sonar | **Verified** | `pom.xml:68-79` `<sonar.exclusions>` lists `**/services/impl/*.java`, `**/models/*.java`, `**/config/*.java`, `**/exceptions/*.java`, etc. JaCoCo also excludes `**/config/*` (`pom.xml:387-389`) |

**Why this is a strong authenticity detail:** *"The reason that half-finished reactive `.block()` impl with a dead `RestTemplate` import shipped is structural — `services/impl` is in the Sonar exclusion glob (`pom.xml:74`) and the gate is 75% Passive (`kitt.yaml:39`), so coverage gaps and quality smells in that class never blocked a deploy."*

---

## H. CI / build / release — "how is this built and released?"

- Build tooling: **Azul JDK 11**, **Maven 3.6.1**, sonarscanner `4.6.2` (`.looper.yml:1-7`); matches `kitt.yaml` `buildType: maven-j11`, Zulu `11-jre`.
- Default flow: `build → sonar-fetch-origin → sonar`, then `finally: hygieiaPublish` (`.looper.yml:19-27`).
- PR flow: `run-sonar-pr` with `-Dsonar.pullrequest.*` params (`.looper.yml:29,63-70`).
- Release: `main` flow calls `release` → `mvn ... build-helper:parse-version -Prelease release:clean release:prepare release:perform` (`.looper.yml:36-48`) — standard maven-release-plugin cut.
- Notify: Slack `data-ventures-cperf-dev-ops` + email `dv_dataapitechall@email.wal-mart.com` on success/failure (`.looper.yml:72-104`).

---

## I. Attribution & version drift (kept — matches canon)

- **"Spearheaded/Led/Developed end-to-end" is collaborative.** The pom's sole listed developer is **Nayana.BG** (`pom.xml:312-313`); the `sr.yaml` contact is `Harshit.sharma1@walmart.com` and member `homeoffice\h0s0acv` (`sr.yaml:17-18`). Own the design, the reusability/adoption story, and the SB3-migration framing; credit the team for authorship.
- **Version drift:** in-repo artifact is `0.0.45` (`pom.xml:7`); `cp-nrti-apis` consumes **`0.0.61`**. Be ready for "which version?" — the consumer's pinned `0.0.61` is what runs in prod; `0.0.45` is just the current head of this repo.
- **Latency attribution:** don't attribute the producer's `<5ms` / `204-immediately` to this JAR. This JAR's win is the `@Async` off-thread signing+POST hop (Section C), not audit freshness.

---

## J. Bullet 2 spoken caveat (memorize — corrected facts baked in)

*"I'll be precise. It's a shared **library**, not an auto-configured starter — there's no `spring.factories` and no `src/main/resources`, so consumers component-scan `com.walmart.dv` and must define their own `WebClient` bean for the `@Autowired` constructor in `AuditHttpServiceImpl` to satisfy injection — the JAR ships `spring-boot-starter-webflux` so the `WebClient` **type** is on the classpath, but it never defines the **bean**. The repo also has a deployable `springboot-web` kitt profile with a sample `product-controller` Swagger, so it doubles as a demo host. The code is `javax.servlet` while the pom carries a `jakarta.servlet-api 6.1.0 provided` dep — it's mid-migration, which is the real 'lone SB2.7/Java 11 outlier' story. Capture is a lowest-precedence `OncePerRequestFilter` that buffers the body and builds an 18-field payload — including an all-headers copy — **on the request thread**, then off-threads only signing + the POST to a bounded `core6/max10/queue100` pool whose default AbortPolicy drops silently with no metric. Honest gaps I'd fix: the header copy leaks `Authorization`/`WM_SEC.*` (separate from the CCM `mask.enable=false`), `request_size_bytes` is `toString().getBytes().length` so it's meaningless, the `@Async` catch misses `RuntimeException`, and `services/impl` is excluded from a 75%-Passive Sonar gate so the half-finished reactive `.block()` code shipped untested."*

---

## K. Claim-by-claim verdict

| # | Claim | Verdict |
|---|---|---|
| 1 | Shared library, not an auto-config starter (no `spring.factories`/resources) | ✅ Code-true |
| 2 | "Vestigial kitt/sr on a non-deployable lib" | ❌ **Corrected** — it self-deploys as `springboot-web` + registers a REST service |
| 3 | SB 2.7.11 / Java 11 | ✅ Code-true (`pom:18,30`) |
| 4 | "Cleanly javax" | ⚠️ **Refined** — code is javax, but pom carries `jakarta.servlet-api 6.1.0 provided`: mid-migration |
| 5 | "Consumer excludes the JAR's webflux starter" | ❌ **Corrected** — the JAR itself declares webflux (`pom:120-123`); the gap is the missing `WebClient` **bean**, not the dependency |
| 6 | `@Async` pool core6/max10/queue100, AbortPolicy silent drop | ✅ Code-true (`AuditLogAsyncConfig:20-23`) + ✅ wired by bean-name convention |
| 7 | Off-thread hop is the latency win | ⚠️ **Refined** — only signing+POST are off-threaded; body copy + payload build stay on the request thread |
| 8 | No header masking; `mask.enable=false` | ✅ Both true, but they are **two independent** leak surfaces, not one |
| 9 | `request_size_bytes` meaningless; dead `Objects.isNull` on `int` | ✅ Code-true (`AuditLogFilterUtil:83-86`) |
| 10 | Substring `contains()` matching | ✅ Code-true, + servletPath-vs-requestURI input mismatch |
| 11 | Dead `RestTemplate` import + reactive `.block()` | ✅ Code-true (`AuditHttpServiceImpl:15,50-59`); ships untested behind Sonar exclusion |
| 12 | "Every claim confirmed / fully authentic" (prior verdict) | ❌ **Replaced** — capture path is code-true; the pom-dependency and "non-deployable" framings were wrong and are corrected above |

### Corrections vs prior doc
1. `kitt.yaml`/`sr.yaml` are **not** vestigial — the artifact deploys as a `springboot-web` service (namespace `cp-bulk-feeds-api`, helm min/max, actuator probes, dev cluster `eus2-dev-a3`) and registers in Service Registry as a REST service with a sample Swagger.
2. The JAR **itself** ships `spring-boot-starter-webflux` (`pom:120-123`); the accurate gap is that it defines **no `@Bean WebClient`**, so the consumer must wire one.
3. The pom is **not** cleanly "javax" — it declares `jakarta.servlet-api 6.1.0 provided` and `jakarta.persistence-api` (`pom:154-164`) while the code is `javax`: a transitional/incoherent servlet-API state (stronger "outlier" point).
4. Line citations are now pinned and verified: parent version is `pom:18` (block `15-20`), not "17-18"; the `Objects.isNull`/`request_size_bytes` smell is `AuditLogFilterUtil:83-86`; `mask.enable` is `ccm:82` but inside the `platform-logging-client` Telemetry block, distinct from the app's header-copy leak.
5. The self-congratulatory "fully authentic / gap closed" verdict is replaced with per-claim confidence.
