# Scenario-Based "What If?" Questions - Spring Boot 3 Migration

> Use framework: DETECT → IMPACT → MITIGATE → RECOVER → PREVENT

---

## Q1: "What if the canary deployment detected errors at 10%?"

> **DETECT:** "Flagger checks every 2 minutes. If request-success-rate < 99% or P99 > 500ms, failure counter increments."
>
> **IMPACT:** "Only 10% of users affected. 90% still on old version."
>
> **MITIGATE:** "After 5 failed checks, Flagger automatically rolls back. All traffic returns to old version. Zero manual intervention."
>
> **RECOVER:** "Old version is still running. Rollback is instant via Istio VirtualService traffic shift. Investigate root cause in canary logs."
>
> **PREVENT:** "This is exactly WHY we use canary. If we'd done blue/green, 100% of users would be affected before detection."

---

## Q2: "What if .block() causes a thread starvation issue?"

> "`.block()` holds the calling thread until the WebClient response returns. If downstream is slow:
>
> **Scenario:** Downstream API takes 30 seconds. 100 concurrent requests. Each holds a thread. Tomcat default thread pool is 200. After 200 concurrent slow requests → no threads available → all requests queue → timeout.
>
> **How we mitigate:**
> 1. **Explicit timeout** on WebClient calls (added in PR #1564) - don't wait forever
> 2. **Retry with exponential backoff** - don't hammer a slow service
> 3. **Circuit breaker** (should add) - stop calling after N failures
>
> **Why .block() is still OK for us:**
> Our APIs handle ~100 req/sec per pod. At 200ms avg response, we need ~20 threads. Tomcat's 200-thread pool gives 10x headroom. Thread starvation would only happen if downstream is consistently >2s, at which point the timeout kicks in.
>
> **If I rebuilt today:** I'd set WebClient timeout to 2 seconds, add Resilience4j circuit breaker, and consider reactive for I/O-heavy endpoints only."

---

## Q3: "What if a Hibernate entity mapping breaks in production?"

> "This almost happened during our migration. Hibernate 6 changed PostgreSQL enum handling - `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` was needed.
>
> **How we caught it:** 1-week stage deployment with production-like traffic. The enum error showed as 'column is of type status_enum but expression is of type character varying.'
>
> **If it had reached production:**
> - All queries involving that entity would fail with 500
> - Flagger canary would detect error rate spike at 10% traffic
> - Automatic rollback within 10 minutes (5 failed checks × 2 min interval)
>
> **Why stage testing matters:** Hibernate issues only show up when you hit the actual database with real data types. Unit tests with H2 in-memory DB won't catch PostgreSQL-specific type mismatches."

---

## Q4: "What if a transitive dependency has a critical CVE after migration?"

> "This ACTUALLY happened. PR #1332 (April 23, 2025) - 2 days after migration.
>
> **What happened:** Snyk flagged CVEs in dependencies that came with Spring Boot 3.2's BOM. These weren't in 2.7's dependency tree.
>
> **How we handled:**
> 1. Snyk scan caught it automatically in CI pipeline
> 2. We overrode specific dependency versions in pom.xml
> 3. Verified no functionality changes
> 4. Fixed within 48 hours, zero customer impact
>
> **Later (June):** Bumped to Spring Boot 3.3.12 for more security patches (PR #1394).
>
> **Lesson:** Framework upgrades bring NEW transitive dependencies. Your old Snyk baseline is invalid - expect new CVEs and have a response plan."

---

## Q5: "What if the WebClient test mocking breaks and tests pass incorrectly?"

> "This is a real risk. WebClient method chain mocking is complex:
>
> ```java
> when(webClient.get()).thenReturn(requestHeadersUriSpec);
> when(requestHeadersUriSpec.uri(anyString())).thenReturn(requestHeadersSpec);
> // ... 5+ mock setups per test
> ```
>
> **If mocking is wrong:** Test passes but doesn't actually test the code path. False confidence.
>
> **How we mitigate:**
> 1. **Container tests** (PR #1587-1590) - real HTTP calls to real service
> 2. **Stage deployment** for 1 week with production traffic
> 3. **Code review** specifically checks WebClient mock chain completeness
>
> **What I'd add:** WireMock-based integration tests that start a real WebClient against a WireMock server. Tests the actual HTTP client, not mocks."

---

## Q6: "What if the migration breaks Kafka publishing?"

> "We migrated from ListenableFuture to CompletableFuture for Kafka. If the migration broke publishing:
>
> **Detection:** Kafka publish error rate spikes. Consumer lag doesn't increase (no new messages).
>
> **Actual improvement we found:** The old ListenableFuture code had a REAL bug - failover to secondary region didn't work because `exceptionally()` returned null instead of trying secondary. CompletableFuture made the failover logic correct.
>
> **Testing:**
> - PR #65 added Testcontainers-based Kafka integration tests
> - Tests verify: primary success, primary fail → secondary success, both fail → exception
>
> **Lesson:** Migration isn't just about compatibility - it's an opportunity to fix existing bugs. The CompletableFuture migration exposed a failover bug we didn't know existed."

---

## Q7: "What if you need to rollback from Spring Boot 3 to 2.7?"

> "We kept old version pods running for 48 hours post-migration.
>
> **Within 48 hours:** Instant rollback via Istio traffic shift. Old pods still have 2.7 code, warm JVM, active connections.
>
> **After 48 hours:** Old pods removed. Rollback requires:
> 1. Revert git to pre-migration commit
> 2. Build old version
> 3. Deploy
> 4. ~30 min total
>
> **Why we didn't need it:** Canary caught nothing. 48-hour monitoring clean. Three minor fixes were additive (pom overrides, List.of(), Sonar fix) - didn't require rollback.
>
> **What makes rollback hard:** If post-migration code writes data in new format (e.g., new database columns), old code can't read it. We avoided this by not changing data formats during the migration."

---

## Q8: "What if K8s probes aren't configured correctly after migration?"

> "This ACTUALLY happened - PR #1594 (January 2026).
>
> **What happened:** Spring Boot 3 changed actuator health endpoint behavior. Our K8s startup probe was checking an endpoint that behaved differently. Pods were passing health checks but not fully initialized.
>
> **Impact:** Under heavy load, requests would hit pods that were still initializing → slow responses or errors.
>
> **Fix:** Reconfigured startup, readiness, and liveness probes to match Spring Boot 3's actuator behavior.
>
> **Lesson:** K8s probes are part of the migration. They're not 'infrastructure' that you can ignore. Every framework upgrade should include probe validation."

---

## Q9: "What if the correlation ID stops propagating after migration?"

> "This ACTUALLY happened - PR #1527 (October 2025).
>
> **What happened:** Spring Boot 3 changed filter chain behavior subtly. The `RequestFilter` that propagated correlation IDs through the request chain had issues with the new filter ordering.
>
> **How we detected:** Dynatrace traces showed missing correlation headers in downstream calls. Requests couldn't be traced end-to-end.
>
> **Fix:** Refactored RequestFilter with helper methods. Removed redundant transaction handling in NrtiApiInterceptor.
>
> **Lesson:** Correlation ID propagation is invisible until it breaks. Test it explicitly during migration. We should have had an automated test that verifies correlation ID appears in downstream call headers."

---

## Q10: "What if GTP BOM (Walmart's internal dependency manager) releases a breaking update?"

> "This ACTUALLY happened THREE TIMES post-migration:
>
> 1. **PR #1425 (Aug):** GTP BOM 2.2.1 - required renaming FeatureFlagCCMConfig, removing spring-webflux, +515/-838 lines
> 2. **PR #1498-1501 (Sep):** StratiServiceProvider deprecated → ObservabilityServiceProvider
> 3. **PR #1528 (Oct):** Heap OOM from resource management changes
>
> **The reality of enterprise Java:** Your framework migration is never truly done. Internal platform dependencies evolve and create ripple effects. Each GTP BOM update is a mini-migration.
>
> **How we handle:** Monitor GTP BOM release notes. Test in stage before upgrading. Keep a buffer between migration and BOM updates - don't do both at once."

---

*Every Q7-Q10 is a REAL incident. Connect scenario questions to real experiences.*
