# Interview Q&A - Spring Boot 3 Migration

---

## Main Questions

### Q1: "Tell me about the Spring Boot 3 migration you led."

**Level 1 Answer:**
> "I led the migration of cp-nrti-apis from Spring Boot 2.7 to Spring Boot 3.2, along with Java 11 to Java 17. The main challenges were the javax→jakarta namespace change, migrating from RestTemplate to WebClient, and adapting to Hibernate 6. We deployed to production with zero downtime using canary deployments."

**Follow-up:** "What was the biggest challenge?"
> "The WebClient migration was trickiest. RestTemplate has been the standard for years, and the team was comfortable with it. WebClient is reactive by default, but our codebase is synchronous. I decided to use `.block()` to maintain synchronous behavior rather than doing a full reactive rewrite - that would be a separate initiative. The test mocking was also more complex because WebClient uses a builder pattern with method chaining."

**Follow-up:** "Why not go fully reactive?"
> "Two reasons: scope and risk. A full reactive migration would touch every service class and fundamentally change error handling patterns. For a framework upgrade, I wanted to minimize changes to business logic. The second reason was team readiness - reactive programming has a learning curve. I'd rather do that as a dedicated project with proper training."

---

### Q2: "How did you handle the javax→jakarta namespace change?"

> "This was largely mechanical but required careful verification. We updated 74 files - entities, controllers, validators, and filters. I used IDE refactoring tools for the bulk changes, but had to manually verify servlet-related code because some classes changed behavior, not just package names.
>
> For example, `javax.servlet.Filter` became `jakarta.servlet.Filter`, but some filter lifecycle methods had slightly different semantics. We added comprehensive tests to ensure filter ordering and behavior was preserved."

---

### Q3: "What testing did you do before production deployment?"

> "Four layers of testing:
>
> 1. **Unit tests**: Updated all 42 test files. Especially important for WebClient mocking which is more complex than RestTemplate.
>
> 2. **Integration tests**: Ran full container tests to verify database connectivity with Hibernate 6, Kafka publishing with CompletableFuture, and external API calls with WebClient.
>
> 3. **Stage deployment**: Ran for one week with production-like traffic. Caught a few edge cases - one around enum handling in PostgreSQL that needed `@JdbcTypeCode`.
>
> 4. **Canary deployment**: Started with 10% traffic in prod, monitored error rates and latency. Gradually increased over 24 hours. Had automatic rollback configured if error rate exceeded 1%."

---

### Q4: "Were there any issues in production after the migration?"

> "Yes, and I'd divide them into immediate and delayed.
>
> **Immediate (Week 1):** Three minor issues caught by CI pipeline - Snyk CVEs in transitive dependencies, a mutable collection code smell, and a Sonar issue. All fixed within 48 hours, zero customer impact.
>
> **Delayed (over next 6 months):** Deeper issues that surfaced under sustained production load:
> - **Heap OOM** - Resource management wasn't using try-with-resources properly. Fixed in October.
> - **Correlation ID propagation** - Broke subtly because filter chain behavior changed in Spring Boot 3.
> - **WebClient timeouts** - RestTemplate had implicit timeout handling. WebClient needed explicit timeout and retry logic with exponential backoff. Added in November.
> - **K8s startup probes** - Spring Boot 3 changed actuator health endpoint behavior. Probes needed reconfiguration.
>
> **The lesson:** A framework migration isn't done when the PR merges. It's done when you've been through a full production cycle. I'd say ours was truly 'done' about 6 months after the initial PR."

**Follow-up:** "What would you set up differently to catch these earlier?"
> "Three things: comprehensive health check monitoring from day one, WebClient timeout and retry configuration as part of the migration (not an afterthought), and load testing in stage that simulates sustained production patterns, not just functional correctness."

---

### Q5: "What would you do differently?"

> "Four things:
>
> 1. **Earlier migration**: We waited until Spring Boot 2.7 was close to EOL. I'd advocate for migrating within 6 months of a major release.
>
> 2. **Automated tooling**: Use OpenRewrite for the javax→jakarta change - it's deterministic and scriptable.
>
> 3. **WebClient resilience from day one**: We added timeout and retry logic 6 months later (PR #1564). Should've been part of the original migration since WebClient doesn't have RestTemplate's implicit timeout handling.
>
> 4. **Longer load testing in stage**: Functional tests passed, but the heap OOM and correlation ID issues only surfaced under sustained production load patterns. I'd do a full week of load testing at 2x production volume before releasing."

---

## Technical Deep Dive Questions

### Q6: "How did you handle Hibernate 6 compatibility?"

> "Hibernate 6 is stricter about JPA compliance. The main issue was PostgreSQL enum types - Hibernate 5 handled them implicitly, but Hibernate 6 needs explicit type mapping.
>
> Without the explicit `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` annotation, Hibernate tried to send enums as VARCHAR, but PostgreSQL expected the custom enum type. We got errors like 'column is of type status_enum but expression is of type character varying.'
>
> I added the annotation to all enum fields across 15 entity files. The lesson: Hibernate upgrades require database compatibility testing."

---

### Q7: "Explain the WebClient migration in detail."

> "RestTemplate is synchronous and blocking. WebClient is reactive and non-blocking by default. Since our entire codebase was synchronous, I had a choice:
>
> **Option 1**: Full reactive rewrite - Use Mono/Flux throughout, change return types, handle backpressure
> **Option 2**: Use WebClient with `.block()` - Maintains synchronous behavior, minimal code changes
>
> I chose Option 2 for this migration. The `.block()` call makes the reactive chain wait for completion, giving us synchronous behavior. The code looks like:
>
> ```java
> return webClient.get()
>     .uri(url)
>     .retrieve()
>     .bodyToMono(StoreResponse.class)
>     .block();
> ```
>
> The challenge was test mocking. RestTemplate has one method to mock. WebClient has a chain: `get()`, `uri()`, `headers()`, `retrieve()`, `bodyToMono()`. Each needs to return a mock that returns the next mock. Test files doubled in complexity."

---

### Q8: "How did you handle the Kafka ListenableFuture deprecation?"

> "Spring Kafka 3.x deprecated ListenableFuture in favor of CompletableFuture. The main difference is the API for handling results:
>
> **Before**: `future.addCallback(successHandler, failureHandler)`
> **After**: `future.thenAccept(successHandler).exceptionally(failureHandler)`
>
> The benefit of CompletableFuture is better composition. I could chain multiple futures and handle errors more explicitly. For our multi-region publishing, this meant cleaner failover logic:
>
> ```java
> primaryFuture
>     .thenAccept(result -> log.info("Primary success"))
>     .exceptionally(ex -> {
>         secondaryFuture.join();  // Try secondary
>         return null;
>     })
>     .join();
> ```
>
> The `.join()` at the end ensures we wait for completion, and any exception in the secondary path propagates up."

---

## Behavioral Questions

### Q9: "How did you handle disagreements about the migration approach?"

> "Early on, a team member wanted to do a full reactive rewrite since we were touching the code anyway. I disagreed because it would triple the scope.
>
> Instead of arguing in the meeting, I prepared data: estimated time for reactive rewrite (3 months) vs framework-only migration (4 weeks), risk assessment for each approach, and a proposal to do reactive as a follow-up project.
>
> In the 1:1, I presented the trade-offs and proposed the phased approach. We agreed to do framework migration first, then evaluate reactive as a separate initiative. Key was approaching it with data, not opinions."

---

### Q10: "What did you learn from this migration?"

> "Three main lessons:
>
> 1. **Test coverage matters** - The places where we had good tests, migration was easy. Places without tests required manual verification.
>
> 2. **Framework migrations should be routine** - Waiting until EOL is stressful. I now advocate for annual upgrade cycles.
>
> 3. **Backwards compatibility has value** - Using `.block()` instead of going fully reactive let us ship faster. Perfect is the enemy of good."

---

## Quick Answers

### "Why Java 17 and not 21?"
> "Java 17 is LTS, Java 21 was too new. We follow Walmart standards for LTS versions."

### "Why use .block() instead of fully reactive?"
> "Scope control. Full reactive would change every service. Framework upgrade should minimize business logic changes."

### "Why Flagger for deployment?"
> "Already our standard. Automatic rollback if metrics exceed thresholds. Proven zero-downtime deployments."

### "Why not use OpenRewrite for migration?"
> "Considered it, but team wanted to understand each change. Next major migration we'll use it."

### "What was the hardest part?"
> "WebClient test mocking - method chain requires complex mocking setup."

---

## STAR Story: The Migration

**Situation:** "Spring Boot 2.7 was approaching end-of-life. Security scans were flagging vulnerabilities we couldn't patch without upgrading."

**Task:** "I volunteered to lead the migration for our main API service, cp-nrti-apis, which handles supplier API requests."

**Action:**
- Analyzed migration path, identified 3 main challenges (namespace, WebClient, Hibernate)
- Made strategic decision to use .block() instead of full reactive rewrite
- Updated 158 files (1,732 additions, 1,858 deletions), 42 test files
- Implemented canary deployment with automatic rollback
- Staged for 1 week, then 24-hour gradual production rollout

**Result:** "Zero customer-impacting issues. Migration completed in 4 weeks. Three minor post-migration fixes, all caught proactively. Set the template for other team migrations."

---

*Practice these out loud until they feel natural!*
