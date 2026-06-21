# Post-Migration Issues & Fixes (Complete - gh Verified)

> **This file covers ALL issues from migration through the months after.**
> Real PRs, real dates, real fixes.

---

## Overview Timeline

The migration wasn't a one-time event. It was followed by several waves of fixes as we encountered issues in production at scale. Here's the FULL picture:

```
Apr 21, 2025 │ PR #1312 merged - Spring Boot 3 migration live
Apr 23       │ WAVE 1: Snyk + Sonar issues (#1332, #1335)
Apr 30       │ PR #1337 - Released to main/production
Jun 3        │ WAVE 2: More Snyk fixes + Spring Boot bump to 3.3.12 (#1394)
Aug 11       │ WAVE 3: GTP BOM upgrade, removed webflux, renamed configs (#1425)
Sep 22-23    │ WAVE 4: GTP BOM prod + ObservabilityServiceProvider fix (#1498, #1501)
Oct 6        │ WAVE 5: Heap OOM fix + Postgres changes (#1528)
Oct 6        │ Correlation ID fix (#1527)
Nov 4        │ WAVE 6: Downstream API timeout + retry logic (#1564)
Jan 6, 2026  │ WAVE 7: Kubernetes startup probe fix (#1594)
```

---

## WAVE 1: Immediate Post-Migration (April 2025)

### Issue 1: Snyk Vulnerabilities in Transitive Dependencies

**PR #1332** - Merged April 23, 2025 (+48/-36)

**What Happened:**
After upgrading to Spring Boot 3.2, transitive dependencies pulled by Spring's BOM had known CVEs flagged by Snyk.

**Root Cause:** Spring Boot 3.2's dependency tree brought in different versions of libraries than 2.7 - some of these had known vulnerabilities.

**The Fix:**
- Overrode specific dependency versions in pom.xml
- Added explicit dependency management for vulnerable libraries

**Interview Point:**
> "These weren't regressions we introduced - they were pre-existing in Spring Boot 3's dependency tree. We fixed by overriding versions. This is a common reality of framework upgrades."

---

### Issue 2: Mutable Collection Code Smell

**PR #1332** - Same PR as above

**What Happened:**
Sonar flagged `Arrays.asList()` patterns that return mutable lists.

```java
// BEFORE - mutable, risky
List<String> endpoints = Arrays.asList("endpoint1", "endpoint2");

// AFTER - immutable, safe (Java 17 best practice)
List<String> endpoints = List.of("endpoint1", "endpoint2");
```

**Interview Point:**
> "Part of the Java 17 adoption - we replaced mutable collection patterns with immutable `List.of()`. Prevents accidental state mutation."

---

### Issue 3: Sonar Major Issue

**PR #1335** - Merged April 23, 2025 (+1/-1)

Single-line code quality fix. Caught by CI pipeline, not by users.

---

## WAVE 2: Spring Boot Version Bump (June 2025)

### Issue 4: Continued Snyk Vulnerabilities

**PR #1394** - Merged June 3, 2025 (+6/-5)

**What Happened:**
More CVEs discovered in dependencies. Updated parent POM version to Spring Boot 3.3.12.

**The Fix:**
- Bumped Spring Boot from 3.2 to 3.3.12 for security patches
- Added Snyk PR check profile to kitt.yml for automated scanning

**Interview Point:**
> "After the initial migration to 3.2, we continued to keep the version current. Bumped to 3.3 within 2 months for security patches. This is why I now advocate for continuous upgrades, not one-time migrations."

---

## WAVE 3: GTP BOM Major Upgrade (August 2025)

### Issue 5: GTP BOM Compatibility Overhaul

**PR #1425** - Merged August 11, 2025 (+515/-838)

**What Happened:**
Walmart's internal GTP BOM (Global Technology Platform Bill of Materials) released version 2.2.1 which required significant changes.

**The Fix:**
- Updated GTP BOM version
- Renamed `FeatureFlagCCMConfig` file
- Added dv-api-common-libraries to pom
- Removed spring-webflux dependency (wasn't needed since we use .block())
- Updated Spring version
- Fixed missing configs and removed commented code

**Interview Point:**
> "The GTP BOM upgrade was almost as significant as the original migration - 515 additions, 838 deletions. When you're in a large enterprise, the framework migration is just the beginning. Internal platform dependencies need to align too."

---

## WAVE 4: Service Provider Migration (September 2025)

### Issue 6: ObservabilityServiceProvider Replacement

**PR #1498** - Merged September 22, 2025 (+19/-42)
**PR #1501** - Merged September 23, 2025 (+542/-884)

**What Happened:**
`StratiServiceProvider` was deprecated. Needed to migrate to `ObservabilityServiceProvider` across multiple files.

**The Fix:**
- Replaced all `StratiServiceProvider` references with `ObservabilityServiceProvider`
- Updated GTP BOM and Spring Boot versions again
- Updated deployment configurations and secrets in kitt.yml

**Interview Point:**
> "Framework migrations create a ripple effect. The Spring Boot 3 upgrade triggered our GTP BOM to update, which deprecated our service provider. Each wave was smaller but required attention."

---

## WAVE 5: Heap OOM & Postgres Changes (October 2025)

### Issue 7: Heap Out of Memory

**PR #1528** - Merged October 6, 2025 (+224/-66)

**What Happened:**
Memory leak issues discovered under heavy production load, months after migration.

**Root Cause:** Unused fields and methods were not being garbage collected properly. Transaction handling wasn't using try-with-resources.

**The Fix:**
- Removed unused fields and methods to reduce memory footprint
- Enhanced transaction handling with try-with-resources for better resource management
- Added `PostgresDbConfigException` with detailed responses
- Updated repository methods and tests

**Interview Point:**
> "This is why I say production issues can surface weeks or months later. The heap OOM only showed under sustained production load patterns. We fixed it by cleaning up resource management and adding try-with-resources."

---

### Issue 8: Correlation ID Not Propagating

**PR #1527** - Merged October 6, 2025 (+34/-16)

**What Happened:**
After the migration, the `RequestFilter` had issues propagating correlation IDs correctly through the request chain.

**The Fix:**
- Refactored `RequestFilter` with helper methods for better modularity
- Removed redundant transaction handling in `NrtiApiInterceptor`
- Enhanced error handling for unauthorized exceptions

**Interview Point:**
> "Correlation ID propagation broke subtly after the migration because the filter chain order and interceptor behavior changed slightly with Spring Boot 3's new filter handling."

---

## WAVE 6: Downstream API Resilience (November 2025)

### Issue 9: Downstream API Timeouts

**PR #1564** - Merged November 4, 2025 (+573/-35)

**What Happened:**
WebClient's default behavior for downstream API calls didn't have proper timeout and retry logic. Under production load, slow downstream services caused cascading failures.

**The Fix:**
- Added retry logic with exponential backoff for HTTP requests
- Introduced `executeHttpRequest` method with retry and timeout handling
- Added `NrtiUnavailableException` for retry exhaustion
- Added comprehensive logging for all retry attempts

**Interview Point:**
> "With RestTemplate, we had simpler timeout handling. WebClient needed explicit timeout and retry configuration. We added exponential backoff with configurable retries. This is something I'd set up from day one if I did the migration again."

---

## WAVE 7: Kubernetes Probe Fix (January 2026)

### Issue 10: Startup Probe Configuration

**PR #1594** - Merged January 6, 2026 (+31/-11)

**What Happened:**
Spring Boot 3 changed how health endpoints work. The Kubernetes startup, liveness, and readiness probes needed reconfiguration.

**The Fix:**
- Added proper Kubernetes probe configurations
- Updated `application.properties` with health probe settings
- Adjusted probe settings for better reliability

**Interview Point:**
> "Spring Boot 3 changed the actuator health endpoint behavior. Our K8s probes needed updating to match. This is the kind of subtle change that only surfaces in production when pods start failing health checks under load."

---

## Summary Table (Complete)

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

---

## What This Shows in an Interview

### The HONEST answer to "Any production issues?"

> "Yes, and I'd divide them into immediate and delayed.
>
> **Immediate (Week 1):** Three minor issues caught by our CI pipeline - Snyk CVEs in transitive dependencies, a mutable collection code smell, and a Sonar issue. All fixed within 48 hours, zero customer impact.
>
> **Delayed (Months 2-8):** Deeper issues that only surfaced under sustained production load:
> - Heap memory issues from resource management changes
> - Correlation ID propagation broke because filter chain behavior changed subtly
> - WebClient needed explicit timeout and retry configuration that RestTemplate handled differently
> - Kubernetes health probes needed reconfiguration for Spring Boot 3's actuator changes
>
> **The lesson:** A framework migration isn't done when the PR merges. It's done when you've been through a full production cycle and addressed all the edge cases. I'd say our migration was truly 'done' about 6 months after the initial PR."

### Why This HELPS in an Interview:

1. **Shows honesty** - You're not claiming it was perfect
2. **Shows systematic approach** - Issues found, root-caused, and fixed
3. **Shows depth** - You understand WHY issues happened (filter chain changes, resource mgmt, actuator changes)
4. **Shows learning** - "If I did this again, I'd set up timeout/retry from day one"
5. **Shows resilience** - Months of follow-up, not just one PR and done

---

## Key Learnings to Mention

1. **Framework migrations have a long tail** - Issues surface weeks/months later
2. **Enterprise dependencies create ripple effects** - GTP BOM, ServiceProvider changes
3. **WebClient needs explicit resilience** - RestTemplate's implicit timeout/retry doesn't carry over
4. **Resource management changes** - try-with-resources matters more in Spring Boot 3
5. **K8s probes need updating** - Actuator health endpoint behavior changed
6. **Continuous upgrades > Big-bang** - Staying current is easier than catching up

---

*Previous: [04-deployment-strategy.md](./04-deployment-strategy.md) | Next: [06-interview-qa.md](./06-interview-qa.md)*
