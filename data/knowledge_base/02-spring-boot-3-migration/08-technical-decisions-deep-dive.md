# Technical Decisions Deep Dive - Spring Boot 3 Migration

> **"Why THIS and Not THAT?" for every major migration decision.**

---

## Decision 1: WebClient .block() vs Full Reactive

**THE most important decision of this migration.**

| Approach | Scope | Risk | Time | Team Readiness | Our Choice |
|----------|-------|------|------|---------------|------------|
| **.block()** | Framework only | Low - same behavior | 4 weeks | Ready | **YES** |
| **Full Reactive** | Architecture change | High - new error patterns, every service | 3 months | Needs training | No |

### Interview Answer
> "Full reactive would touch every service class, change return types to Mono/Flux, fundamentally change error handling. For a framework upgrade, I wanted to minimize business logic changes. `.block()` gives us WebClient's benefits (connection pooling, non-blocking I/O under the hood) while maintaining synchronous behavior the team understands. Reactive would be a dedicated follow-up project."

### Follow-up: "Isn't .block() an anti-pattern?"
> "In a fully reactive stack, yes. But we're not reactive. `.block()` on a non-reactive thread is fine - it's effectively RestTemplate behavior with WebClient's API. The anti-pattern is `.block()` on a reactive thread (event loop), which we don't have."

### Follow-up: "When would you go fully reactive?"
> "When we need to handle significantly more concurrent requests without adding pods. Reactive shines when you have many I/O-bound calls. For our current load (~100 req/sec per pod), synchronous is fine. If we hit 1000+/sec, reactive would be the path."

---

## Decision 2: Canary Deployment vs Blue/Green vs Big Bang

| Strategy | Risk | Rollback Speed | Gradual Validation | Our Choice |
|----------|------|---------------|-------------------|------------|
| **Canary (Flagger)** | Low - gradual | Instant (automatic) | Yes (10%→25%→50%→100%) | **YES** |
| **Blue/Green** | Medium - all at once | Fast (switch DNS) | No - 100% switch | No |
| **Big Bang** | High | Slow (redeploy) | No | Never for framework migration |
| **Rolling** | Medium | Medium | Partial | No (less control than canary) |

### Interview Answer
> "For a framework migration affecting 158 files, we needed maximum safety. Canary gives us gradual risk exposure - if there's a subtle performance regression, we catch it at 10% traffic. Flagger automates the entire process: checks error rate and P99 latency every minute, increases traffic by 10% if healthy, automatic rollback if error rate exceeds 1%. We deployed over 24 hours with zero customer impact."

### Follow-up: "Why not blue/green? It's simpler."
> "Blue/green switches 100% at once. For a framework migration, subtle issues may only appear under load. At 10%, we can detect regressions affecting 10% of users. At 100% blue/green, all users are affected before we detect. The canary approach caught nothing in this case - but the safety net was worth the complexity."

---

## Decision 3: Java 17 vs Java 21

| Version | LTS? | Walmart Standard | Features We Need | Our Choice |
|---------|------|-----------------|-----------------|------------|
| **Java 17** | Yes (until 2029) | Yes - standard | Records, .toList(), sealed classes | **YES** |
| **Java 21** | Yes (until 2031) | Too new, not standard | Virtual threads, pattern matching | No |
| **Java 11** | Yes (expiring) | Current but EOL | What we had | Upgrading from |

### Interview Answer
> "Java 17 is the LTS version Walmart standardizes on. Java 21 was too new - our GTP BOM (internal dependency manager) didn't support it yet, and most internal libraries weren't tested with 21. We got the features we needed: records for immutable data classes, `.toList()` for cleaner streams, and text blocks for SQL queries."

---

## Decision 4: Semi-Manual Migration vs OpenRewrite

| Approach | Accuracy | Learning | Time | Our Choice |
|----------|----------|---------|------|------------|
| **IDE refactoring + manual verification** | High (we verified each file) | Team understands every change | 4 weeks | **YES (this time)** |
| **OpenRewrite automation** | High (deterministic) | Less learning | 1-2 weeks | Next time |

### Interview Answer
> "The javax→jakarta change is deterministic - it could be scripted with OpenRewrite. We did it semi-manually because the team wanted to understand each change. Some classes changed behavior, not just package names - servlet filter lifecycle methods, for example. The manual approach gave us confidence. Next major migration, I'd use OpenRewrite for the mechanical parts and focus manual effort on behavioral changes."

### Follow-up: "That sounds slow. Why not just automate?"
> "Fair point. The first migration is learning. The second should be automated. Now that we understand the patterns, OpenRewrite would save 2 weeks. The lesson: invest in understanding once, automate forever after."

---

## Decision 5: Stage for 1 Week vs Ship Faster

| Approach | Safety | Speed | What We Catch | Our Choice |
|----------|--------|-------|--------------|------------|
| **1 week in stage** | High | Slower | Config issues, Hibernate enum problems | **YES** |
| **2 days in stage** | Medium | Faster | Functional bugs only | No |
| **Skip stage** | Low | Fastest | Nothing until production | Never |

### Interview Answer
> "We caught the Hibernate 6 PostgreSQL enum issue during the stage week. Without it, that would've been a production incident. One week lets us validate with production-like traffic patterns - not just functional tests, but load patterns, memory behavior, and database compatibility. For a framework migration, the extra week is cheap insurance."

---

## Decision 6: ListenableFuture → CompletableFuture (Not Just Migration)

| What Changed | Before | After | Why It's Better |
|-------------|--------|-------|----------------|
| **API** | `addCallback(success, failure)` | `.thenAccept().exceptionally()` | Chainable, composable |
| **Combining** | Manual | `.allOf()`, `.anyOf()` | Built-in Java |
| **Error handling** | Callbacks can swallow exceptions | `.exceptionally()` + `.join()` propagates | Explicit, safer |
| **Standard** | Spring-specific | java.util.concurrent | No Spring dependency |

### Interview Answer
> "This wasn't just a find-replace migration. CompletableFuture improved our multi-region failover logic. With ListenableFuture's callback style, if the primary Kafka region failed, the exception was swallowed and the secondary was never tried. With CompletableFuture, I could chain `.exceptionally()` to try the secondary region and `.join()` to ensure we wait for completion. The migration fixed a real failover bug."

---

## Decision 7: Mutable → Immutable Collections (List.of())

```java
// BEFORE (Java 11): Mutable, risky
List<String> items = Arrays.asList("a", "b");
items.add("c");  // Works but shouldn't

// AFTER (Java 17): Immutable, safe
List<String> items = List.of("a", "b");
items.add("c");  // Throws UnsupportedOperationException
```

### Interview Answer
> "We replaced 35 instances of `Arrays.asList()` with `List.of()`. This isn't just cleaner syntax - `List.of()` returns an unmodifiable list. In multi-threaded code, accidentally modifying a shared list causes subtle bugs. Making immutability the default prevents an entire class of concurrency issues."

---

## Decision 8: NoResourceFoundException Handler

```java
@ExceptionHandler(NoResourceFoundException.class)
@ResponseStatus(NOT_FOUND)
public ResponseEntity<NoResourceErrorBean> handleNoResourceFoundException(...)
```

### Why Add This?
> "Spring MVC 6 introduced `NoResourceFoundException` for 404 errors. Without handling it, our API returned Spring's default error format. Our suppliers expect a consistent error format across all endpoints. Adding a custom handler ensures 404s return the same error structure as 400s and 500s."

---

## Decision 9: WebClient Error Handling (onStatus)

```java
// New error handling pattern with WebClient
.onStatus(HttpStatusCode::is4xxClientError, response ->
    response.bodyToMono(String.class)
        .flatMap(body -> Mono.error(new ClientException(body))))
```

### Why This Pattern?
> "RestTemplate throws HttpClientErrorException on 4xx/5xx. WebClient doesn't by default - it returns the error response as normal data. You have to explicitly handle status codes with `.onStatus()`. This is a common gotcha during migration - tests pass because WebClient returns the error body as data, but the application doesn't handle it as an error."

---

## Decision 10: Keep Old Pods 48 Hours Post-Deploy

### Why 48 Hours?
> "After reaching 100% on Spring Boot 3, we kept the 2.7 pods running for 48 hours. If any delayed issue appeared (batch processing, overnight jobs, weekend traffic patterns), we could instantly route all traffic back. After 48 hours with clean metrics, we removed the old pods. This costs a few hours of extra compute but eliminates rollback risk."

---

## Quick Reference: All 10 Decisions

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

---

*Answer pattern: "We considered [alternatives]. We chose [X] because [reason]. Trade-off: [downside]. Mitigated by: [action]."*
