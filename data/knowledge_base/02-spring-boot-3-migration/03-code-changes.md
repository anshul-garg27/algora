# Code Changes - Spring Boot 3 Migration

> All major code changes with before/after examples

---

## 1. javax → jakarta Namespace (74 files)

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

---

## 2. RestTemplate → WebClient

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

---

## 3. Kafka: ListenableFuture → CompletableFuture

```java
// BEFORE (Spring Kafka with ListenableFuture)
ListenableFuture<SendResult<String, Message>> future = kafkaTemplate.send(message);
future.addCallback(
    result -> log.info("Success: {}", result),
    ex -> log.error("Failed: {}", ex.getMessage())
);

// AFTER (Spring Kafka with CompletableFuture)
CompletableFuture<SendResult<String, Message<IacKafkaPayload>>> future =
    kafkaTemplate.send(message);

future
    .thenAccept(result -> {
        RecordMetadata metadata = result.getRecordMetadata();
        log.info("Sent to partition: {}, offset: {}",
                 metadata.partition(), metadata.offset());
    })
    .exceptionally(ex -> {
        log.warn("Primary failed, trying secondary: {}", ex.getMessage());
        handleFailure(topicName, message, messageId).join();
        return null;
    })
    .join();
```

---

## 4. Hibernate 6: PostgreSQL Enum Types

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

**Why this broke:** Hibernate 6 tried to send enums as VARCHAR, but PostgreSQL expected the custom enum type → error: "column is of type status_enum but expression is of type character varying"

---

## 5. Spring Security 6

```java
// BEFORE (Spring Security 5)
@Configuration
@EnableWebSecurity
public class SecurityConfig extends WebSecurityConfigurerAdapter {  // DEPRECATED!
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

**Key changes:**
- No more `WebSecurityConfigurerAdapter` (deprecated)
- Lambda-based DSL configuration
- `antMatchers()` → `requestMatchers()`
- `authorizeRequests()` → `authorizeHttpRequests()`

---

## 6. Exception Handler Updates

```java
// NEW in Spring MVC 6: NoResourceFoundException for 404
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

---

## 7. Test Changes (34 files)

### WebClient Mocking (Complex!)

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

**Interview Point:** "WebClient test mocking was the hardest part. Each method in the chain needs its own mock. Test files basically doubled in complexity."

---

## 8. Java 17: .toList() Stream Improvement (35 instances)

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

**Why this matters:** `.toList()` returns an unmodifiable list. Found 35 instances across codebase.

---

## Summary (gh verified from PR #1312)

| Category | Count | Key Pattern |
|----------|-------|-------------|
| jakarta imports | 145 changes | javax.* → jakarta.* |
| RestTemplate → WebClient | Multiple services | `.block()` for sync compatibility |
| .toList() Java 17 | 35 instances | `.collect(Collectors.toList())` → `.toList()` |
| CompletableFuture | 23 instances | ListenableFuture → CompletableFuture |
| Test files | 42 files | WebClient chain mocking |
| Security config | Config files | `SecurityFilterChain` bean |
| Exception handlers | Controllers | `NoResourceFoundException` |
| **TOTAL** | **158 files** | **+1,732 / -1,858 lines** |

---

*Next: [04-deployment-strategy.md](./04-deployment-strategy.md) - Canary deployment with Flagger*
