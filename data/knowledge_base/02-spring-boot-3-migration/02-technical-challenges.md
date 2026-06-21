# Technical Challenges - Spring Boot 3 Migration

---

## Challenge 1: javax → jakarta Namespace Migration

### The Problem
Java EE was transferred from Oracle to Eclipse Foundation and renamed to Jakarta EE. All `javax.*` packages became `jakarta.*`.

### Affected Areas

```java
// BEFORE (Spring Boot 2.x)
import javax.persistence.Entity;
import javax.persistence.Column;
import javax.validation.Valid;
import javax.validation.constraints.NotNull;
import javax.servlet.http.HttpServletRequest;

// AFTER (Spring Boot 3.x)
import jakarta.persistence.Entity;
import jakarta.persistence.Column;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import jakarta.servlet.http.HttpServletRequest;
```

### Files Changed
- **74 files** across entities, controllers, validators, filters, and tests

### Interview Point
> "The javax→jakarta migration wasn't just a find-replace. Some classes changed behavior, and we had to carefully test each component. For example, servlet filters needed updated method signatures."

---

## Challenge 2: RestTemplate → WebClient Migration

### The Problem
`RestTemplate` is deprecated in Spring Boot 3. Must migrate to `WebClient` (reactive, non-blocking).

### Before (RestTemplate)
```java
@Service
public class NrtiStoreServiceImpl {

    @Autowired
    private RestTemplate restTemplate;

    public StoreResponse getStoreData(String storeId) {
        ResponseEntity<StoreResponse> response = restTemplate.exchange(
            url,
            HttpMethod.GET,
            new HttpEntity<>(headers),
            StoreResponse.class
        );
        return response.getBody();
    }
}
```

### After (WebClient with .block())
```java
@Service
public class NrtiStoreServiceImpl {

    @Autowired
    private WebClient webClient;

    public StoreResponse getStoreData(String storeId) {
        return webClient.get()
            .uri(url)
            .headers(h -> h.addAll(headers))
            .retrieve()
            .bodyToMono(StoreResponse.class)
            .block();  // Blocking for compatibility with sync code
    }
}
```

### Key Considerations
- WebClient is reactive by default; used `.block()` to maintain sync behavior
- Error handling changed from exceptions to status handlers
- Had to mock `WebClient` chain in tests (more complex than RestTemplate)

### Interview Point
> "The WebClient migration was the trickiest part. We had to decide between going fully reactive or using `.block()` for backwards compatibility. We chose `.block()` because our entire codebase was synchronous, and a full reactive migration would be a separate initiative."

---

## Challenge 3: Kafka ListenableFuture → CompletableFuture

### The Problem
Spring Kafka deprecated `ListenableFuture` in favor of `CompletableFuture`.

### Before
```java
ListenableFuture<SendResult<String, Message>> future = kafkaTemplate.send(message);
future.addCallback(
    result -> log.info("Success: {}", result),
    ex -> log.error("Failed: {}", ex.getMessage())
);
```

### After
```java
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

### Interview Point
> "The CompletableFuture migration improved our error handling. With the old callback style, exceptions could be swallowed. With CompletableFuture, we use `.exceptionally()` and `.join()` to ensure failures are properly handled and we can fall back to the secondary Kafka region."

---

## Challenge 4: Java 17 Stream Improvements (.toList())

### The Change
Java 17 has `.toList()` built into streams, replacing the verbose `.collect(Collectors.toList())`. We updated **35 instances** across the codebase.

```java
// BEFORE (Java 11)
List<String> result = items.stream()
    .filter(i -> i.isActive())
    .collect(Collectors.toList());  // Verbose, mutable list

// AFTER (Java 17)
List<String> result = items.stream()
    .filter(i -> i.isActive())
    .toList();  // Cleaner, returns UNMODIFIABLE list
```

### Why This Matters
- `.toList()` returns an **unmodifiable** list (unlike `Collectors.toList()` which is mutable)
- Cleaner code, less boilerplate
- This was a natural cleanup as part of Java 17 adoption

### Interview Point
> "As part of Java 17 adoption, we replaced 35 instances of `.collect(Collectors.toList())` with `.toList()`. This isn't just cleaner syntax - `.toList()` returns an unmodifiable list, which prevents accidental mutation."

---

## Challenge 5: Hibernate 6 Compatibility

### The Problem
Hibernate 6 changed default behaviors and is stricter about JPA compliance.

### Key Changes
- Hibernate 6 is stricter with PostgreSQL enum type handling
- Some implicit type mappings that worked in Hibernate 5 need explicit annotations in Hibernate 6
- We caught and resolved enum compatibility issues during the **1-week stage testing** before production

> **Note:** The Hibernate enum fix (`@JdbcTypeCode`) was caught and resolved during stage testing, not in the main migration PR. This is why staged deployment matters.

### Interview Point
> "Hibernate 6 introduced stricter JPA compliance. We caught PostgreSQL enum compatibility issues during our 1-week stage deployment - that's exactly why we staged for a full week before production."

---

## Challenge 5: Spring Security 6 Changes

### The Problem
Spring Security 6 changed from `WebSecurityConfigurerAdapter` to component-based configuration.

### Before (Spring Security 5)
```java
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
```

### After (Spring Security 6)
```java
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

### Key Changes
- No more `WebSecurityConfigurerAdapter` (deprecated)
- Lambda-based DSL configuration
- `antMatchers()` → `requestMatchers()`
- `authorizeRequests()` → `authorizeHttpRequests()`

---

## Challenge 6: Exception Handler Updates

### The Problem
Spring MVC 6 introduced `NoResourceFoundException` for 404 errors.

### Code Added
```java
@ExceptionHandler(NoResourceFoundException.class)
@ResponseStatus(NOT_FOUND)
public ResponseEntity<NoResourceErrorBean> handleNoResourceFoundException(
    NoResourceFoundException ex, HttpServletRequest request) {

    String timestamp = ZonedDateTime.now(ZoneOffset.UTC)
        .format(DateTimeFormatter.ISO_INSTANT);

    NoResourceErrorBean errorBean = NoResourceErrorBean.builder()
        .timestamp(timestamp)
        .status(NOT_FOUND.value())
        .error(NOT_FOUND.getReasonPhrase())
        .path(request.getRequestURI())
        .build();

    return new ResponseEntity<>(errorBean, NOT_FOUND);
}
```

### Also Changed
- `HttpStatus` → `HttpStatusCode` in method signatures
- Added custom error response beans for better API consistency

---

## Summary: All Changes (gh verified from PR #1312)

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

## What I Would Do Differently

1. **Use OpenRewrite** - Automated migration tool for javax→jakarta
2. **Migrate earlier** - Don't wait until EOL is imminent
3. **Better test coverage first** - More confident migration

---

*These challenges show deep framework knowledge - great for technical interviews!*
