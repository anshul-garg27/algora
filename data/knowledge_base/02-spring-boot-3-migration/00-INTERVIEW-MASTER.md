# Spring Boot 3 Migration -- Interview Prep

> **Repo:** `cp-nrti-apis` | **Main PR:** #1312 | **Production Release:** Apr 30, 2025

---

## Your Pitches

### 30-Second Pitch
> "I led the migration of cp-nrti-apis from Spring Boot 2.7 to 3.2 and Java 11 to 17. Main challenges: javax-to-jakarta across 74 files, RestTemplate to WebClient with .block() for backwards compatibility, and Hibernate 6 enum handling. Zero-downtime canary deployment, zero customer-impacting issues."

### 60-Second Pitch
> "I led the migration of our main supplier-facing API from Spring Boot 2.7 to 3.2, along with Java 11 to 17. This was driven by security -- Snyk was flagging CVEs we couldn't patch without upgrading, and we'd fail audit in 3 months.
>
> Three major challenges: the javax-to-jakarta namespace change across 74 files, migrating RestTemplate to WebClient, and adapting to Hibernate 6's stricter handling of PostgreSQL enums.
>
> The most strategic decision was using WebClient with .block() instead of going fully reactive -- scope control over perfection. 158 files changed, zero customer-impacting issues. Deployed using Flagger canary releases -- 10% traffic initially, gradually to 100% over 24 hours with automatic rollback."

---

## Key Numbers

| Metric | Value | Source |
|--------|-------|--------|
| Files changed | **158** | PR #1312 |
| Lines added | **1,732** | PR #1312 |
| Lines deleted | **1,858** | PR #1312 |
| javax-to-jakarta files | **74** | PR #1312 diff |
| jakarta imports added | **145** | PR #1312 diff |
| Test files updated | **42** | PR #1312 diff |
| .toList() Java 17 usage | **35 instances** | PR #1312 diff |
| CompletableFuture changes | **23 instances** | PR #1312 diff |
| Spring Boot version | **2.7 -> 3.2** | |
| Java version | **11 -> 17** | |
| Production issues | **0 customer-impacting** | |
| Migration time | **~4 weeks** | PR #1312 merged Apr 21 |
| Production release | **Apr 30, 2025** | PR #1337 merged |
| Post-migration fix PRs | **10 PRs over 9 months** | |

---

## Architecture Overview

### The Service: cp-nrti-apis

`cp-nrti-apis` is the main API service for Walmart Luminate's supplier-facing APIs:
- Handles inventory queries, DSD notifications, transaction history
- External suppliers (Pepsi, Coca-Cola, Unilever) depend on it daily
- ~100 requests/second per pod
- **Critical infrastructure** -- downtime = supplier impact

### Why We Migrated

```
1. END OF SUPPORT
   - Spring Boot 2.7 EOL: November 2023
   - Java 11 extended support ending
   - No security patches for older versions

2. SECURITY REQUIREMENTS
   - Snyk/Sonar flagging CVEs in dependencies
   - Couldn't patch without upgrading framework
   - Would fail security audit in 3 months

3. ECOSYSTEM COMPATIBILITY
   - GTP BOM versions require Spring Boot 3
   - Internal libraries moving to Jakarta EE
   - New features only available in SB3
```

### Migration Scope

| What Changed | From | To |
|-------------|------|-----|
| **Spring Boot** | 2.7 | 3.2 |
| **Java** | 11 | 17 |
| **Namespace** | javax.* | jakarta.* |
| **HTTP Client** | RestTemplate | WebClient |
| **Kafka Futures** | ListenableFuture | CompletableFuture |
| **Security** | WebSecurityConfigurerAdapter | SecurityFilterChain |
| **Hibernate** | 5.x (implicit enums) | 6.x (@JdbcTypeCode) |

### My Role

I **volunteered to lead** this migration:
- Analyzed the migration path and identified 3 main challenges
- Made the strategic decision to use `.block()` instead of full reactive
- Executed all code changes (158 files, 42 test files)
- Designed the deployment strategy (canary with Flagger)
- Handled post-migration fixes proactively over 9 months

---

## The .block() Decision

**THE most important technical decision of the migration.**

| Approach | Scope | Risk | Time | Team Readiness |
|----------|-------|------|------|---------------|
| **.block()** | Framework only | Low -- same behavior | 4 weeks | Ready |
| **Full Reactive** | Architecture change | High -- new error patterns, every service | 3 months | Needs training |

### Why I Chose .block()

1. **Scope control** -- Framework upgrade, not architecture change
2. **Risk reduction** -- Minimize business logic changes
3. **Team readiness** -- Reactive has a learning curve
4. **Pragmatism** -- Full reactive would be a separate project

### The Full Story

> "When I started planning the migration, a colleague proposed we go fully reactive with WebClient. His argument was sound -- we're already touching the code, why not modernize completely?
>
> I thought about it seriously. Fully reactive would mean:
> - Every service class returns Mono or Flux instead of direct objects
> - Error handling fundamentally changes -- exceptions become signals
> - The team needs training on reactive programming concepts
> - Estimated time: 3 months
>
> Framework-only migration with .block():
> - WebClient calls behave exactly like RestTemplate
> - Business logic unchanged
> - Testing approach similar (though WebClient mocking is more complex)
> - Estimated time: 4 weeks
>
> I didn't argue in the meeting. I prepared the data, scheduled a 1:1 with our lead, presented both options with trade-offs. My proposal: framework migration now, evaluate reactive as a separate initiative. We agreed.
>
> **Result:** Shipped in 4 weeks, zero customer impact. The decision was about knowing when NOT to do something."

### Follow-up: "Isn't .block() an anti-pattern?"
> "In a fully reactive stack, yes. But we're not reactive. `.block()` on a non-reactive thread is fine -- it's effectively RestTemplate behavior with WebClient's API. The anti-pattern is `.block()` on a reactive thread (event loop), which we don't have."

### Follow-up: "When would you go fully reactive?"
> "When we need to handle significantly more concurrent requests without adding pods. Reactive shines when you have many I/O-bound calls. For our current load (~100 req/sec per pod), synchronous is fine. If we hit 1000+/sec, reactive would be the path."

### One-Liner Version
> "I chose .block() over full reactive because this was a framework upgrade, not an architecture change. Ship safely first, modernize later."

---

## javax -> jakarta Namespace Change

Oracle transferred Java EE to Eclipse Foundation -> renamed to Jakarta EE. Every `javax.persistence`, `javax.validation`, `javax.servlet` import had to change across **74 files**.

### Persistence Layer
```java
// BEFORE
import javax.persistence.Entity;
import javax.persistence.Column;
import javax.persistence.Table;
import javax.persistence.Id;
import javax.persistence.GeneratedValue;

// AFTER
import jakarta.persistence.Entity;
import jakarta.persistence.Column;
import jakarta.persistence.Table;
import jakarta.persistence.Id;
import jakarta.persistence.GeneratedValue;
```

### Validation Layer
```java
// BEFORE
import javax.validation.Valid;
import javax.validation.constraints.NotNull;
import javax.validation.constraints.Size;

// AFTER
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
```

### Servlet Layer
```java
// BEFORE
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import javax.servlet.FilterChain;

// AFTER
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.FilterChain;
```

> "The javax-to-jakarta migration wasn't just a find-replace. Some classes changed behavior, and we had to carefully test each component. For example, servlet filters needed updated method signatures."

---

## RestTemplate -> WebClient Migration

RestTemplate is deprecated in Spring Boot 3. Must migrate to WebClient (reactive, non-blocking).

### Simple GET Request
```java
// BEFORE (RestTemplate)
ResponseEntity<StoreResponse> response = restTemplate.exchange(
    url,
    HttpMethod.GET,
    new HttpEntity<>(headers),
    StoreResponse.class
);
return response.getBody();

// AFTER (WebClient with .block())
return webClient.get()
    .uri(url)
    .headers(h -> h.addAll(headers))
    .retrieve()
    .bodyToMono(StoreResponse.class)
    .block();
```

### POST Request with Body
```java
// BEFORE
ResponseEntity<InventoryResponse> response = restTemplate.exchange(
    url,
    HttpMethod.POST,
    new HttpEntity<>(requestBody, headers),
    InventoryResponse.class
);
return response.getBody();

// AFTER
return webClient.post()
    .uri(url)
    .headers(h -> h.addAll(headers))
    .bodyValue(requestBody)
    .retrieve()
    .bodyToMono(InventoryResponse.class)
    .block();
```

### Error Handling
```java
// BEFORE (RestTemplate)
try {
    return restTemplate.exchange(url, HttpMethod.GET, entity, Response.class);
} catch (HttpClientErrorException e) {
    log.error("Client error: {}", e.getStatusCode());
    throw e;
}

// AFTER (WebClient)
return webClient.get()
    .uri(url)
    .headers(h -> h.addAll(headers))
    .retrieve()
    .onStatus(HttpStatusCode::is4xxClientError, response ->
        response.bodyToMono(String.class)
            .flatMap(body -> Mono.error(new ClientException(body))))
    .bodyToMono(Response.class)
    .block();
```

> "RestTemplate throws HttpClientErrorException on 4xx/5xx. WebClient doesn't by default -- it returns the error response as normal data. You have to explicitly handle status codes with `.onStatus()`. This is a common gotcha during migration."

### Test Mocking Complexity (Hardest Part)

```java
// BEFORE: RestTemplate mock (simple)
when(restTemplate.exchange(any(), eq(HttpMethod.GET), any(), eq(Response.class)))
    .thenReturn(new ResponseEntity<>(mockResponse, HttpStatus.OK));

// AFTER: WebClient mock (complex chain)
WebClient.RequestHeadersUriSpec requestHeadersUriSpec = mock(WebClient.RequestHeadersUriSpec.class);
WebClient.RequestHeadersSpec requestHeadersSpec = mock(WebClient.RequestHeadersSpec.class);
WebClient.ResponseSpec responseSpec = mock(WebClient.ResponseSpec.class);

when(webClient.get()).thenReturn(requestHeadersUriSpec);
when(requestHeadersUriSpec.uri(anyString())).thenReturn(requestHeadersSpec);
when(requestHeadersSpec.headers(any())).thenReturn(requestHeadersSpec);
when(requestHeadersSpec.retrieve()).thenReturn(responseSpec);
when(responseSpec.bodyToMono(Response.class)).thenReturn(Mono.just(mockResponse));
```

> "WebClient test mocking was the hardest part. Each method in the chain needs its own mock. Test files basically doubled in complexity. We updated 34 test files. It's one of those things where the production code is cleaner with WebClient, but the test code is significantly harder."

---

## Hibernate 6 Compatibility

Hibernate 6 is stricter about JPA compliance. The main issue was PostgreSQL enum types.

```java
// BEFORE (Hibernate 5 - worked implicitly)
@Column(name = "status")
@Enumerated(EnumType.STRING)
private Status status;

// AFTER (Hibernate 6 - requires explicit mapping)
@Column(name = "status", columnDefinition = "status_enum")
@Enumerated(EnumType.STRING)
@JdbcTypeCode(SqlTypes.NAMED_ENUM)  // NEW: Required for PostgreSQL enums
private Status status;
```

**Why this broke:** Hibernate 6 tried to send enums as VARCHAR, but PostgreSQL expected the custom enum type -> error: "column is of type status_enum but expression is of type character varying"

Caught during the 1-week stage deployment -- not in the main migration PR. This is exactly why staged deployment matters.

> "Hibernate 6 introduced stricter JPA compliance. We caught PostgreSQL enum compatibility issues during our 1-week stage deployment. Without the explicit `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` annotation, Hibernate tried sending enums as VARCHAR and PostgreSQL rejected it."

---

## Kafka: ListenableFuture -> CompletableFuture

Spring Kafka deprecated ListenableFuture in favor of CompletableFuture. Updated **23 instances**.

```java
// BEFORE (Spring Kafka with ListenableFuture)
ListenableFuture<SendResult<String, Message>> future = kafkaTemplate.send(message);
future.addCallback(
    result -> log.info("Success: {}", result),
    ex -> log.error("Failed: {}", ex.getMessage())
);

// AFTER (Spring Kafka with CompletableFuture)
CompletableFuture<SendResult<String, Message<IacKafkaPayload>>> future =
    kafkaTemplate.send(iacKafkaMessage);

future
    .thenAccept(result -> {
        RecordMetadata metadata = result.getRecordMetadata();
        log.info("Sent successfully to partition: {}, offset: {}",
                 metadata.partition(), metadata.offset());
    })
    .exceptionally(ex -> {
        log.warn("Failed in primary region, trying secondary: {}", ex.getMessage());
        handleFailure(topicName, message, messageId).join();
        return null;
    })
    .join();
```

> "This wasn't just a find-replace migration. CompletableFuture improved our multi-region failover logic. With ListenableFuture's callback style, if the primary Kafka region failed, the exception was swallowed and the secondary was never tried. With CompletableFuture, I could chain `.exceptionally()` to try the secondary region and `.join()` to ensure we wait for completion. The migration fixed a real failover bug."

---

## Spring Security 6

```java
// BEFORE (Spring Security 5)
@Configuration
@EnableWebSecurity
public class SecurityConfig extends WebSecurityConfigurerAdapter {
    @Override
    protected void configure(HttpSecurity http) throws Exception {
        http
            .csrf().disable()
            .authorizeRequests()
            .antMatchers("/actuator/**").permitAll()
            .anyRequest().authenticated();
    }
}

// AFTER (Spring Security 6)
@Configuration
@EnableWebSecurity
public class SecurityConfig {
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .csrf(csrf -> csrf.disable())
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/actuator/**").permitAll()
                .anyRequest().authenticated()
            );
        return http.build();
    }
}
```

Key changes:
- No more `WebSecurityConfigurerAdapter` (deprecated)
- Lambda-based DSL configuration
- `antMatchers()` -> `requestMatchers()`
- `authorizeRequests()` -> `authorizeHttpRequests()`

---

## Java 17: .toList() Stream Improvement

Updated **35 instances** across the codebase.

```java
// BEFORE (Java 11 - verbose, mutable list)
List<String> result = items.stream()
    .filter(i -> i.isActive())
    .collect(Collectors.toList());

// AFTER (Java 17 - clean, unmodifiable list)
List<String> result = items.stream()
    .filter(i -> i.isActive())
    .toList();
```

> "`.toList()` returns an unmodifiable list, unlike `Collectors.toList()` which is mutable. In multi-threaded code, accidentally modifying a shared list causes subtle bugs. Making immutability the default prevents an entire class of concurrency issues."

---

## Exception Handler Updates

Spring MVC 6 introduced `NoResourceFoundException` for 404 errors.

```java
@ExceptionHandler(NoResourceFoundException.class)
@ResponseStatus(NOT_FOUND)
public ResponseEntity<NoResourceErrorBean> handleNoResourceFoundException(
    NoResourceFoundException ex, HttpServletRequest request) {

    NoResourceErrorBean errorBean = NoResourceErrorBean.builder()
        .timestamp(ZonedDateTime.now(ZoneOffset.UTC)
            .format(DateTimeFormatter.ISO_INSTANT))
        .status(NOT_FOUND.value())
        .error(NOT_FOUND.getReasonPhrase())
        .path(request.getRequestURI())
        .build();

    return new ResponseEntity<>(errorBean, NOT_FOUND);
}
```

> "Without handling it, our API returned Spring's default error format. Our suppliers expect a consistent error format across all endpoints. Adding a custom handler ensures 404s return the same error structure as 400s and 500s."

---

## Deployment Strategy

### Why Canary?

| Strategy | Risk | Rollback Speed | Gradual Validation |
|----------|------|---------------|-------------------|
| **Canary (Flagger)** | Low -- gradual | Instant (automatic) | Yes (10%->25%->50%->100%) |
| **Blue/Green** | Medium -- all at once | Fast (switch DNS) | No -- 100% switch |
| **Big Bang** | High | Slow (redeploy) | No |
| **Rolling** | Medium | Medium | Partial |

> "For a framework migration affecting 158 files, we needed maximum safety. Canary gives us gradual risk exposure -- if there's a subtle performance regression, we catch it at 10% traffic. Flagger automates the entire process."

### Deployment Phases

```
Phase 1: STAGE ENVIRONMENT (1 week)
  - Full regression suite passed
  - Performance testing (same throughput as prod)
  - All endpoints validated manually
  - Caught Hibernate enum issue here
  - Sign-off from team lead

Phase 2: CANARY START (Hour 0-4)
  - 10% traffic -> Spring Boot 3
  - 90% traffic -> Spring Boot 2.7 (existing)
  - Monitor: error rates, P99 latency, CPU, memory
  - Automatic rollback if error rate > 1%
  - Duration: 4 hours minimum

Phase 3: GRADUAL INCREASE (Hour 4-24)
  - 25% traffic (if metrics healthy)
  - 50% traffic (after 2 more hours)
  - 75% traffic (after 2 more hours)
  - 100% traffic (after 2 more hours)

Phase 4: FULL PRODUCTION (Hour 24+)
  - 100% on Spring Boot 3
  - Old version kept for 48 hours (quick rollback)
  - Monitor for 1 week for any delayed issues

SAFETY NET: Error rate > 1% at ANY point -> AUTOMATIC ROLLBACK
```

### Flagger + Istio

```
1. Flagger detects new deployment
2. Creates canary pod alongside primary
3. Istio VirtualService splits traffic:
   - 90% -> primary (old version)
   - 10% -> canary (new version)
4. Flagger checks metrics every 1 minute:
   - request-success-rate > 99%?
   - request-duration P99 < 500ms?
5. If healthy -> increase canary weight by 10%
6. If unhealthy -> automatic rollback
7. Once at 100% -> promote canary, remove old
```

### Flagger Config (kitt.yml)

```yaml
flagger:
  enabled: true
  analysis:
    threshold: 5           # Max failed metric checks before rollback
    maxWeight: 50          # Max canary traffic percentage
    stepWeight: 10         # Increase by 10% each step
    interval: 1m           # Check metrics every minute

    metrics:
    - name: request-success-rate
      threshold: 99        # Must have 99% success rate
    - name: request-duration
      threshold: 500       # P99 must be < 500ms
```

### Metrics During Rollout

| Metric | Threshold | Actual (SB3) | Status |
|--------|-----------|--------------|--------|
| **Error rate** | < 1% | 0.02% | PASS |
| **P99 latency** | < 500ms | 180ms | PASS |
| **CPU usage** | < 80% | 45% | PASS |
| **Memory usage** | < 85% | 62% | PASS |
| **Kafka publish errors** | < 0.1% | 0% | PASS |
| **Database errors** | 0 | 0 | PASS |

### Actual Rollout Timeline

```
Day 0 (Monday):
  09:00 - Deploy to stage environment
  09:30 - Run regression suite
  10:00 - All tests pass, begin manual validation

Day 0-6:
  Stage environment running with production-like traffic
  Caught and fixed Hibernate enum issue (@JdbcTypeCode)

Day 7 (Monday):
  09:00 - Begin canary deployment to production
  09:05 - 10% traffic on Spring Boot 3
  13:00 - 4 hours clean, increase to 25%
  15:00 - 2 hours clean, increase to 50%
  17:00 - End of day, leave at 50% overnight

Day 8 (Tuesday):
  09:00 - Check overnight metrics - all clean
  09:30 - Increase to 75%
  11:30 - Increase to 100%
  11:30 - Spring Boot 3 fully live!

Day 8-10:
  Monitor for delayed issues
  Keep old version available for quick rollback

Day 10:
  Remove old version pods
  Migration complete!
```

---

## Technical Decisions

### All 10 Decisions Summary

| # | Decision | Chose | Over | Key Reason |
|---|----------|-------|------|------------|
| 1 | .block() | Sync behavior | Full reactive | Scope control, 4 weeks vs 3 months |
| 2 | Canary deployment | Gradual risk | Blue/green, big bang | Auto-rollback, 10% at a time |
| 3 | Java 17 | LTS standard | Java 21 | Walmart standard, GTP BOM support |
| 4 | Semi-manual migration | Team learning | OpenRewrite | First time = understand, next = automate |
| 5 | 1 week in stage | Safety | Ship faster | Caught Hibernate enum issue |
| 6 | CompletableFuture | Better chaining | ListenableFuture | Fixed multi-region failover bug |
| 7 | List.of() | Immutable default | Arrays.asList() | Prevent concurrency bugs |
| 8 | Custom 404 handler | Consistent errors | Spring default | Supplier UX |
| 9 | .onStatus() | Explicit error handling | RestTemplate exceptions | WebClient doesn't throw by default |
| 10 | Keep old pods 48hr | Safety net | Remove immediately | Zero rollback risk |

### Decision 3: Java 17 vs Java 21

| Version | LTS? | Walmart Standard | Features We Need |
|---------|------|-----------------|-----------------|
| **Java 17** | Yes (until 2029) | Yes -- standard | Records, .toList(), sealed classes |
| **Java 21** | Yes (until 2031) | Too new, not standard | Virtual threads, pattern matching |

> "Java 17 is the LTS version Walmart standardizes on. Java 21 was too new -- our GTP BOM didn't support it yet, and most internal libraries weren't tested with 21. We got the features we needed: records for immutable data classes, `.toList()` for cleaner streams, and text blocks for SQL queries."

### Decision 4: Semi-Manual vs OpenRewrite

| Approach | Accuracy | Learning | Time |
|----------|----------|---------|------|
| **IDE refactoring + manual verification** | High (verified each file) | Team understands every change | 4 weeks |
| **OpenRewrite automation** | High (deterministic) | Less learning | 1-2 weeks |

> "The javax-to-jakarta change is deterministic -- it could be scripted with OpenRewrite. We did it semi-manually because the team wanted to understand each change. Some classes changed behavior, not just package names. Next major migration, I'd use OpenRewrite for the mechanical parts and focus manual effort on behavioral changes."

### Follow-up: "That sounds slow. Why not just automate?"
> "Fair point. The first migration is learning. The second should be automated. Now that we understand the patterns, OpenRewrite would save 2 weeks. The lesson: invest in understanding once, automate forever after."

### Decision 5: Stage for 1 Week vs Ship Faster

> "We caught the Hibernate 6 PostgreSQL enum issue during the stage week. Without it, that would've been a production incident. One week lets us validate with production-like traffic patterns -- not just functional tests, but load patterns, memory behavior, and database compatibility."

### Decision 10: Keep Old Pods 48 Hours

> "After reaching 100% on Spring Boot 3, we kept the 2.7 pods running for 48 hours. If any delayed issue appeared (batch processing, overnight jobs, weekend traffic patterns), we could instantly route all traffic back. After 48 hours with clean metrics, we removed the old pods. This costs a few hours of extra compute but eliminates rollback risk."

---

## Post-Migration Issues

### The HONEST answer to "Any production issues?"

> "Yes, and I'd divide them into immediate and delayed.
>
> **Immediate (Week 1):** Three minor issues caught by our CI pipeline -- Snyk CVEs in transitive dependencies, a mutable collection code smell, and a Sonar issue. All fixed within 48 hours, zero customer impact.
>
> **Delayed (Months 2-8):** Deeper issues that only surfaced under sustained production load:
> - Heap memory issues from resource management changes
> - Correlation ID propagation broke because filter chain behavior changed subtly
> - WebClient needed explicit timeout and retry configuration that RestTemplate handled differently
> - Kubernetes health probes needed reconfiguration for Spring Boot 3's actuator changes
>
> **The lesson:** A framework migration isn't done when the PR merges. It's done when you've been through a full production cycle and addressed all the edge cases. I'd say our migration was truly 'done' about 6 months after the initial PR."

### Full Issue Timeline

```
Apr 21, 2025  | PR #1312 merged - Spring Boot 3 migration live
Apr 23        | WAVE 1: Snyk + Sonar issues (#1332, #1335)
Apr 30        | PR #1337 - Released to main/production
Jun 3         | WAVE 2: More Snyk fixes + Spring Boot bump to 3.3.12 (#1394)
Aug 11        | WAVE 3: GTP BOM upgrade, removed webflux, renamed configs (#1425)
Sep 22-23     | WAVE 4: GTP BOM prod + ObservabilityServiceProvider fix (#1498, #1501)
Oct 6         | WAVE 5: Heap OOM fix + Postgres changes (#1528)
Oct 6         | Correlation ID fix (#1527)
Nov 4         | WAVE 6: Downstream API timeout + retry logic (#1564)
Jan 6, 2026   | WAVE 7: Kubernetes startup probe fix (#1594)
```

### Wave 1: Immediate (April 2025)

**Snyk Vulnerabilities in Transitive Dependencies** -- PR #1332 (+48/-36)

After upgrading to Spring Boot 3.2, transitive dependencies pulled by Spring's BOM had known CVEs flagged by Snyk. Fixed by overriding specific dependency versions in pom.xml.

> "These weren't regressions we introduced -- they were pre-existing in Spring Boot 3's dependency tree. This is a common reality of framework upgrades."

**Mutable Collection Code Smell** -- PR #1332

```java
// BEFORE - mutable, risky
List<String> endpoints = Arrays.asList("endpoint1", "endpoint2");

// AFTER - immutable, safe (Java 17 best practice)
List<String> endpoints = List.of("endpoint1", "endpoint2");
```

**Sonar Major Issue** -- PR #1335 (+1/-1). Single-line code quality fix caught by CI.

### Wave 2: Spring Boot Version Bump (June 2025)

**PR #1394** (+6/-5) -- Bumped Spring Boot from 3.2 to 3.3.12 for security patches. Added Snyk PR check profile to kitt.yml.

> "After the initial migration to 3.2, we continued to keep the version current. I now advocate for continuous upgrades, not one-time migrations."

### Wave 3: GTP BOM Major Upgrade (August 2025)

**PR #1425** (+515/-838) -- Walmart's internal GTP BOM released version 2.2.1. Updated GTP BOM version, renamed FeatureFlagCCMConfig, added dv-api-common-libraries, removed spring-webflux dependency, fixed missing configs.

> "The GTP BOM upgrade was almost as significant as the original migration -- 515 additions, 838 deletions. When you're in a large enterprise, the framework migration is just the beginning. Internal platform dependencies need to align too."

### Wave 4: Service Provider Migration (September 2025)

**PR #1498, #1501** -- `StratiServiceProvider` deprecated, migrated to `ObservabilityServiceProvider`.

> "Framework migrations create a ripple effect. The Spring Boot 3 upgrade triggered our GTP BOM to update, which deprecated our service provider. Each wave was smaller but required attention."

### Wave 5: Heap OOM and Correlation ID (October 2025)

**Heap Out of Memory** -- PR #1528 (+224/-66). Memory leak under heavy production load. Fixed by cleaning up unused fields/methods, adding try-with-resources for resource management, adding `PostgresDbConfigException`.

> "This is why I say production issues can surface weeks or months later. The heap OOM only showed under sustained production load patterns."

**Correlation ID Not Propagating** -- PR #1527 (+34/-16). `RequestFilter` had issues propagating correlation IDs after filter chain behavior changed in Spring Boot 3.

> "Correlation ID propagation broke subtly because filter chain behavior changed. Dynatrace traces showed missing correlation headers in downstream calls."

### Wave 6: Downstream API Resilience (November 2025)

**PR #1564** (+573/-35) -- WebClient's default behavior lacked proper timeout and retry logic. Added retry with exponential backoff, `executeHttpRequest` method, `NrtiUnavailableException`.

> "With RestTemplate, we had simpler timeout handling. WebClient needed explicit timeout and retry configuration. This is something I'd set up from day one if I did the migration again."

### Wave 7: Kubernetes Probe Fix (January 2026)

**PR #1594** (+31/-11) -- Spring Boot 3 changed actuator health endpoint behavior. K8s probes needed reconfiguration.

> "Spring Boot 3 changed the actuator health endpoint behavior. Our K8s probes needed updating to match. This is the kind of subtle change that only surfaces in production when pods start failing health checks under load."

### Summary Table

| Wave | Issue | PR# | Date | Severity | Root Cause |
|------|-------|-----|------|----------|------------|
| 1 | Snyk CVEs in transitive deps | #1332 | Apr 23 | Medium | New dependency versions |
| 1 | Mutable collections | #1332 | Apr 23 | Low | Java 17 best practices |
| 1 | Sonar major issue | #1335 | Apr 23 | Low | Code quality |
| 2 | More Snyk CVEs | #1394 | Jun 3 | Medium | Ongoing security |
| 3 | GTP BOM compatibility | #1425 | Aug 11 | High | Enterprise platform alignment |
| 4 | ServiceProvider deprecated | #1498, #1501 | Sep 22-23 | Medium | Platform evolution |
| 5 | Heap OOM under load | #1528 | Oct 6 | High | Resource management |
| 5 | Correlation ID broken | #1527 | Oct 6 | Medium | Filter chain changes |
| 6 | Downstream API timeouts | #1564 | Nov 4 | High | WebClient timeout config |
| 7 | K8s probe configuration | #1594 | Jan 6 | Medium | Actuator changes |

### Key Learnings

1. **Framework migrations have a long tail** -- Issues surface weeks/months later
2. **Enterprise dependencies create ripple effects** -- GTP BOM, ServiceProvider changes
3. **WebClient needs explicit resilience** -- RestTemplate's implicit timeout/retry doesn't carry over
4. **Resource management changes** -- try-with-resources matters more in Spring Boot 3
5. **K8s probes need updating** -- Actuator health endpoint behavior changed
6. **Continuous upgrades > Big-bang** -- Staying current is easier than catching up

---

## Behavioral Stories (STAR)

### Story: Disagreement -- The .block() Debate

> **Situation:** "During migration planning, a colleague wanted to go fully reactive with WebClient since we were touching the code."
>
> **Task:** "I disagreed, but needed to handle it constructively."
>
> **Action:** "Instead of arguing in the meeting, I prepared data: 3 months vs 4 weeks timeline, risk assessment for each. Scheduled a 1:1, presented trade-offs, proposed phased approach. Took ownership: 'If framework migration fails, that's on me.'"
>
> **Result:** "Shipped in 4 weeks, zero customer impact. Set the template for other teams."
>
> **Learning:** "Sometimes the hardest engineering decision is knowing what NOT to do."

### Story: Technical Leadership -- Volunteering

> **Situation:** "Spring Boot 2.7 EOL approaching. Snyk flagging CVEs. Would fail security audit in 3 months."
>
> **Task:** "I volunteered to lead the migration for our main supplier API."
>
> **Action:** "Analyzed migration path, identified 3 challenges, made the strategic .block() call, updated 158 files, designed canary deployment, personally monitored the 24-hour rollout."
>
> **Result:** "Zero customer-impacting issues, 4 weeks total. Became the template for other team migrations."
>
> **Learning:** "Framework migrations should be routine, not emergencies. I now advocate for annual upgrade cycles."

### Story: Prioritization -- Framing as Security

> "I framed the Spring Boot 3 migration not as 'newer is better' but as a security requirement. 'Snyk is flagging CVEs we cannot patch without upgrading. We'll fail security audit in 3 months.'
>
> That got it prioritized immediately. The lesson: frame technical debt in terms of business impact, not engineering purity. 'This code is ugly' doesn't get prioritized. 'We'll fail audit' does."

---

## Interview Q&A Bank

### Q: "Tell me about the Spring Boot 3 migration you led."

> "I led the migration of cp-nrti-apis from Spring Boot 2.7 to Spring Boot 3.2, along with Java 11 to Java 17. The main challenges were the javax-to-jakarta namespace change, migrating from RestTemplate to WebClient, and adapting to Hibernate 6. We deployed to production with zero downtime using canary deployments."

**Follow-up:** "What was the biggest challenge?"
> "The WebClient migration was trickiest. RestTemplate has been the standard for years, and the team was comfortable with it. WebClient is reactive by default, but our codebase is synchronous. I decided to use `.block()` to maintain synchronous behavior rather than doing a full reactive rewrite. The test mocking was also more complex because WebClient uses a builder pattern with method chaining."

### Q: "How did you handle the javax-to-jakarta namespace change?"

> "This was largely mechanical but required careful verification. We updated 74 files -- entities, controllers, validators, and filters. I used IDE refactoring tools for the bulk changes, but had to manually verify servlet-related code because some classes changed behavior, not just package names. For example, servlet filter lifecycle methods had slightly different semantics."

### Q: "What testing did you do before production deployment?"

> "Four layers of testing:
>
> 1. **Unit tests**: Updated all 42 test files. Especially important for WebClient mocking which is more complex than RestTemplate.
>
> 2. **Integration tests**: Ran full container tests to verify database connectivity with Hibernate 6, Kafka publishing with CompletableFuture, and external API calls with WebClient.
>
> 3. **Stage deployment**: Ran for one week with production-like traffic. Caught a few edge cases -- one around enum handling in PostgreSQL that needed `@JdbcTypeCode`.
>
> 4. **Canary deployment**: Started with 10% traffic in prod, monitored error rates and latency. Gradually increased over 24 hours. Had automatic rollback configured if error rate exceeded 1%."

### Q: "How did you handle Hibernate 6 compatibility?"

> "Hibernate 6 is stricter about JPA compliance. The main issue was PostgreSQL enum types -- Hibernate 5 handled them implicitly, but Hibernate 6 needs explicit type mapping. Without the explicit `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` annotation, Hibernate tried to send enums as VARCHAR, but PostgreSQL expected the custom enum type. I added the annotation to all enum fields across 15 entity files."

### Q: "Explain the Kafka ListenableFuture deprecation."

> "Spring Kafka 3.x deprecated ListenableFuture in favor of CompletableFuture. Before: `future.addCallback(successHandler, failureHandler)`. After: `future.thenAccept(successHandler).exceptionally(failureHandler)`. The benefit of CompletableFuture is better composition. For our multi-region publishing, this meant cleaner failover logic -- the migration actually fixed a failover bug where exceptions were being swallowed."

### Q: "What would you do differently?"

> "Four things:
>
> 1. **Earlier migration**: We waited until Spring Boot 2.7 was close to EOL. I'd advocate for migrating within 6 months of a major release.
>
> 2. **Automated tooling**: Use OpenRewrite for the javax-to-jakarta change -- it's deterministic and scriptable.
>
> 3. **WebClient resilience from day one**: We added timeout and retry logic 6 months later (PR #1564). Should've been part of the original migration since WebClient doesn't have RestTemplate's implicit timeout handling.
>
> 4. **Longer load testing in stage**: Functional tests passed, but the heap OOM and correlation ID issues only surfaced under sustained production load patterns. I'd do a full week of load testing at 2x production volume before releasing."

### Q: "What did you learn from this migration?"

> "Three main lessons:
>
> 1. **Test coverage matters** -- The places where we had good tests, migration was easy. Places without tests required manual verification.
>
> 2. **Framework migrations should be routine** -- Waiting until EOL is stressful. I now advocate for annual upgrade cycles.
>
> 3. **Backwards compatibility has value** -- Using `.block()` instead of going fully reactive let us ship faster. Perfect is the enemy of good."

### Quick-Fire Answers

| Question | Answer |
|----------|--------|
| "Why Java 17 and not 21?" | "Java 17 is LTS, Java 21 was too new. We follow Walmart standards for LTS versions." |
| "Why use .block()?" | "Scope control. Full reactive would change every service. Framework upgrade should minimize business logic changes." |
| "Why Flagger for deployment?" | "Already our standard. Automatic rollback if metrics exceed thresholds. Proven zero-downtime deployments." |
| "Why not OpenRewrite?" | "Considered it, but team wanted to understand each change. Next major migration we'll use it." |
| "What was the hardest part?" | "WebClient test mocking -- method chain requires complex mocking setup." |

---

## What-If Scenarios

Use framework: **DETECT -> IMPACT -> MITIGATE -> RECOVER -> PREVENT**

### "What if the canary detected errors at 10%?"

> **DETECT:** "Flagger checks every 2 minutes. If request-success-rate < 99% or P99 > 500ms, failure counter increments."
>
> **IMPACT:** "Only 10% of users affected. 90% still on old version."
>
> **MITIGATE:** "After 5 failed checks, Flagger automatically rolls back. All traffic returns to old version. Zero manual intervention."
>
> **RECOVER:** "Old version is still running. Rollback is instant via Istio VirtualService traffic shift. Investigate root cause in canary logs."
>
> **PREVENT:** "This is exactly WHY we use canary. If we'd done blue/green, 100% of users would be affected before detection."

### "What if .block() causes thread starvation?"

> "`.block()` holds the calling thread until the WebClient response returns. If downstream is slow:
>
> **Scenario:** Downstream API takes 30 seconds. 100 concurrent requests. Each holds a thread. Tomcat default thread pool is 200. After 200 concurrent slow requests -> no threads available -> all requests queue -> timeout.
>
> **How we mitigate:**
> 1. **Explicit timeout** on WebClient calls (added in PR #1564) -- don't wait forever
> 2. **Retry with exponential backoff** -- don't hammer a slow service
> 3. **Circuit breaker** (should add) -- stop calling after N failures
>
> **Why .block() is still OK for us:** Our APIs handle ~100 req/sec per pod. At 200ms avg response, we need ~20 threads. Tomcat's 200-thread pool gives 10x headroom. Thread starvation would only happen if downstream is consistently >2s, at which point the timeout kicks in.
>
> **If I rebuilt today:** I'd set WebClient timeout to 2 seconds, add Resilience4j circuit breaker, and consider reactive for I/O-heavy endpoints only."

### "What if a Hibernate entity mapping breaks in production?"

> "This almost happened. Hibernate 6 changed PostgreSQL enum handling.
>
> **How we caught it:** 1-week stage deployment. The enum error showed as 'column is of type status_enum but expression is of type character varying.'
>
> **If it had reached production:**
> - All queries involving that entity would fail with 500
> - Flagger canary would detect error rate spike at 10% traffic
> - Automatic rollback within 10 minutes (5 failed checks x 2 min interval)
>
> **Why stage testing matters:** Hibernate issues only show up when you hit the actual database with real data types. Unit tests with H2 in-memory DB won't catch PostgreSQL-specific type mismatches."

### "What if a transitive dependency has a critical CVE?"

> "This ACTUALLY happened. PR #1332 -- 2 days after migration.
>
> Snyk flagged CVEs in dependencies that came with Spring Boot 3.2's BOM. We overrode specific dependency versions in pom.xml. Fixed within 48 hours, zero customer impact.
>
> **Lesson:** Framework upgrades bring NEW transitive dependencies. Your old Snyk baseline is invalid -- expect new CVEs and have a response plan."

### "What if WebClient test mocking breaks and tests pass incorrectly?"

> "This is a real risk. WebClient chain mocking needs 5+ mock setups per test. If mocking is wrong, test passes but doesn't actually test the code path -- false confidence.
>
> **How we mitigate:**
> 1. **Container tests** -- real HTTP calls to real service
> 2. **Stage deployment** for 1 week with production traffic
> 3. **Code review** specifically checks WebClient mock chain completeness
>
> **What I'd add:** WireMock-based integration tests that start a real WebClient against a WireMock server."

### "What if Kafka publishing breaks after migration?"

> "We migrated from ListenableFuture to CompletableFuture. The old code actually had a REAL bug -- failover to secondary region didn't work because exceptions were swallowed. CompletableFuture made the failover logic correct.
>
> **Testing:** Testcontainers-based Kafka integration tests verify: primary success, primary fail -> secondary success, both fail -> exception.
>
> **Lesson:** Migration isn't just about compatibility -- it's an opportunity to fix existing bugs."

### "What if you need to rollback from Spring Boot 3 to 2.7?"

> "We kept old pods running for 48 hours post-migration.
>
> **Within 48 hours:** Instant rollback via Istio traffic shift. Old pods still have 2.7 code, warm JVM, active connections.
>
> **After 48 hours:** Rollback requires: revert git, build old version, deploy. ~30 min total.
>
> **What makes rollback hard:** If post-migration code writes data in new format. We avoided this by not changing data formats during the migration."

### "What if K8s probes aren't configured correctly?"

> "This ACTUALLY happened -- PR #1594 (January 2026). Spring Boot 3 changed actuator health endpoint behavior. Pods were passing health checks but not fully initialized. Under heavy load, requests hit initializing pods.
>
> **Lesson:** K8s probes are part of the migration. Every framework upgrade should include probe validation."

### "What if correlation ID stops propagating?"

> "This ACTUALLY happened -- PR #1527 (October 2025). Spring Boot 3 changed filter chain behavior subtly. Dynatrace traces showed missing correlation headers in downstream calls.
>
> **Fix:** Refactored RequestFilter with helper methods. Removed redundant transaction handling in NrtiApiInterceptor.
>
> **Lesson:** Correlation ID propagation is invisible until it breaks. Test it explicitly during migration."

### "What if GTP BOM releases a breaking update?"

> "This happened THREE TIMES post-migration:
>
> 1. **PR #1425 (Aug):** GTP BOM 2.2.1 -- +515/-838 lines
> 2. **PR #1498-1501 (Sep):** StratiServiceProvider deprecated -> ObservabilityServiceProvider
> 3. **PR #1528 (Oct):** Heap OOM from resource management changes
>
> **The reality of enterprise Java:** Your framework migration is never truly done. Internal platform dependencies evolve and create ripple effects. Each GTP BOM update is a mini-migration.
>
> **How we handle:** Monitor GTP BOM release notes. Test in stage before upgrading. Keep a buffer between migration and BOM updates -- don't do both at once."

---

## How to Speak

### Numbers to Drop Naturally

| Number | How to Say It |
|--------|---------------|
| 158 files | "...I updated 158 files total..." |
| 74 files javax-to-jakarta | "...74 files across entities, controllers, validators..." |
| 42 test files | "...42 test files updated, test complexity doubled for WebClient..." |
| Zero customer issues | "...zero customer-impacting issues in production..." |
| 4 weeks | "...completed in about 4 weeks, from planning to full production..." |
| 10%->100% canary | "...started at 10%, gradually increased to 100% over 24 hours..." |
| 3 post-migration fixes | "...three minor fixes, all caught by CI pipeline, not by users..." |
| +1,732 / -1,858 lines | "...over 3,500 lines of changes across the codebase..." |

### How to Pivot TO This Project

From Kafka conversation:
> "That's the audit system -- designing something new. The Spring Boot 3 migration was a different challenge: changing the foundation of a running system without downtime. Would you like to hear about that?"

From general "Tell me about technical challenges":
> "One of my most strategic decisions was during the Spring Boot 3 migration -- choosing what NOT to do was as important as what we did..."

### How to Pivot AWAY

Back to Kafka:
> "The migration also affected the audit system -- we migrated from ListenableFuture to CompletableFuture for Kafka publishing. That actually improved our failover logic..."

To behavioral:
> "The migration taught me a lot about scope management and disagreeing constructively. Want me to tell you about the reactive vs .block() debate?"

### Pyramid Method for Deep Dive

**Level 1 -- Headline:** "158 files changed, zero customer-impacting issues, deployed with canary releases over 24 hours."

**Level 2 -- Three Challenges:** "First, javax-to-jakarta. Second, RestTemplate to WebClient. Third, Hibernate 6 compatibility."

**Level 3 -- Key Decision:** The .block() story (see above).

**Level 4 -- Offer:** "I can go into the deployment strategy, the Hibernate issues, or the test migration challenges -- which interests you?"

### Why This Project Impresses

| What They See | What It Shows |
|---------------|---------------|
| You VOLUNTEERED to lead | Ownership, initiative |
| .block() decision | Pragmatism, scope control |
| Canary deployment | Risk management |
| Zero customer issues | Execution quality |
| Framed as security requirement | Business awareness |
| Template for other teams | Impact beyond your code |

### Answer Pattern
> "We considered [alternatives]. We chose [X] because [reason]. Trade-off: [downside]. Mitigated by: [action]."

---

## All Changes Summary

| Category | Before | After | Count |
|----------|--------|-------|-------|
| **Namespace** | javax.* | jakarta.* | 145 import changes |
| **HTTP Client** | RestTemplate | WebClient + .block() | Multiple services |
| **Streams** | .collect(Collectors.toList()) | .toList() (Java 17) | 35 instances |
| **Kafka** | ListenableFuture | CompletableFuture | 23 instances |
| **Security** | WebSecurityConfigurerAdapter | SecurityFilterChain bean | Config files |
| **Exception handling** | HttpStatus | HttpStatusCode + NoResourceFoundException | Controllers |
| **Tests** | RestTemplate mocks | WebClient chain mocks | 42 test files |
| **TOTAL** | | | **158 files** |

---

## PR Reference

### Migration PRs

| PR# | Title | +/- Lines | Files | Merged | Role |
|-----|-------|-----------|-------|--------|------|
| **#1176** | Spring Boot 3 migration initial | +1,766/-1,699 | 151 | Mar 7, 2025 | Initial groundwork |
| **#1312** | Feature/springboot 3 migration | +1,732/-1,858 | **158** | Apr 21, 2025 | **THE MAIN PR** |
| **#1337** | Feature/springboot 3 migration (Release) | +1,795/-1,892 | 159 | Apr 30, 2025 | Production release |

### Post-Migration PRs

| PR# | Title | +/- Lines | Merged | What Fixed |
|-----|-------|-----------|--------|-----------|
| **#1332** | snyk issues + mutable list | +48/-36 | Apr 23 | Snyk CVEs + List.of() |
| **#1335** | sonar issue fixed | +1/-1 | Apr 23 | Code quality |
| **#1394** | snyk fixes + Spring Boot 3.3.12 | +6/-5 | Jun 3 | Version bump for security |
| **#1425** | GTP BOM 2.2.1 | +515/-838 | Aug 11 | Internal platform alignment |
| **#1498** | GTP BOM issue fix | +19/-42 | Sep 22 | ObservabilityServiceProvider |
| **#1501** | GTP BOM prod changes | +542/-884 | Sep 23 | Production GTP alignment |
| **#1528** | Heap OOM fix + postgres | +224/-66 | Oct 6 | Memory leak, try-with-resources |
| **#1527** | Correlation ID fix | +34/-16 | Oct 6 | Filter chain propagation |
| **#1564** | Downstream API timeout | +573/-35 | Nov 4 | WebClient retry + backoff |
| **#1594** | Startup probe fix | +31/-11 | Jan 6 | K8s actuator health |

### Top 5 PRs to Know

| # | PR# | One-Line Summary |
|---|-----|------------------|
| 1 | **#1312** | Main migration: 158 files, javax-to-jakarta, WebClient, CompletableFuture |
| 2 | **#1564** | WebClient timeout + retry with exponential backoff (573 lines) |
| 3 | **#1528** | Heap OOM fix -- try-with-resources for resource management |
| 4 | **#1425** | GTP BOM 2.2.1 alignment (515 additions, 838 deletions) |
| 5 | **#1332** | Immediate post-migration: Snyk CVEs + List.of() immutability |

### Full Timeline

```
Mar 7, 2025   | PR #1176: Initial migration groundwork (151 files)
              |
Apr 21        | PR #1312: MAIN migration PR (158 files) <-- THE BIG ONE
Apr 23        | PR #1332: Snyk + mutable list fix
Apr 23        | PR #1335: Sonar fix
Apr 30        | PR #1337: Released to production <-- GO LIVE
              |
Jun 3         | PR #1394: Bumped to Spring Boot 3.3.12 (security)
              |
Aug 11        | PR #1425: GTP BOM 2.2.1 (+515/-838) <-- MAJOR
              |
Sep 22-23     | PR #1498, #1501: ObservabilityServiceProvider migration
              |
Oct 6         | PR #1528: Heap OOM fix (try-with-resources)
Oct 6         | PR #1527: Correlation ID propagation fix
              |
Nov 4         | PR #1564: WebClient timeout + retry logic (+573) <-- IMPORTANT
              |
Jan 6, 2026   | PR #1594: K8s startup probe fix
              |
              | Migration truly "done" ~9 months after initial PR
```

### STAR Story Summary

**Situation:** "Spring Boot 2.7 approaching end-of-life. Security scans flagging vulnerabilities we couldn't patch without upgrading."

**Task:** "I volunteered to lead the migration for our main API service, cp-nrti-apis, which handles supplier API requests."

**Action:**
- Analyzed migration path, identified 3 main challenges (namespace, WebClient, Hibernate)
- Made strategic decision to use .block() instead of full reactive rewrite
- Updated 158 files (1,732 additions, 1,858 deletions), 42 test files
- Implemented canary deployment with automatic rollback
- Staged for 1 week, then 24-hour gradual production rollout

**Result:** "Zero customer-impacting issues. Migration completed in 4 weeks. Three minor post-migration fixes, all caught proactively. Set the template for other team migrations."

---

## Interview Sound Bites

| Topic | Sound Bite |
|-------|-----------|
| **Overall** | "Led migration of production API from Spring Boot 2.7 to 3.2, Java 11 to 17, 158 files, zero downtime" |
| **javax-to-jakarta** | "145 import changes across the codebase, not just find-replace -- some classes changed behavior" |
| **WebClient** | "Migrated from RestTemplate to WebClient with .block() for backwards compatibility" |
| **Hibernate 6** | "Added @JdbcTypeCode for PostgreSQL enum compatibility" |
| **Kafka** | "Migrated ListenableFuture to CompletableFuture for better error handling" |
| **Testing** | "42 test files updated. Four layers: unit, integration, stage (1 week), canary (24 hours)" |
| **Deployment** | "Flagger canary with 10%->25%->50%->100% traffic split, automatic rollback" |
| **Result** | "Zero customer-impacting issues, 3 minor post-migration fixes" |
