# Spring Boot 3 & Java 17 Migration - Complete Interview Guide

> **Resume Bullet:** 4
> **Repo:** `cp-nrti-apis`
> **Main PR:** #1312

---

## Quick Navigation

| File | Purpose |
|------|---------|
| [01-overview.md](./01-overview.md) | Why we migrated, scope, business context |
| [02-technical-challenges.md](./02-technical-challenges.md) | javax→jakarta, WebClient, Hibernate 6 |
| [03-code-changes.md](./03-code-changes.md) | Actual code examples and patterns |
| [04-deployment-strategy.md](./04-deployment-strategy.md) | Canary deployment with Flagger |
| [05-production-issues.md](./05-production-issues.md) | Post-migration fixes and lessons |
| [06-interview-qa.md](./06-interview-qa.md) | Q&A bank with model answers |
| **[07-how-to-speak-in-interview.md](./07-how-to-speak-in-interview.md)** | **HOW to talk about this project (pitches, stories, pivots)** |
| **[08-technical-decisions-deep-dive.md](./08-technical-decisions-deep-dive.md)** | **"Why X not Y?" for 10 decisions (.block(), canary, Java 17, etc.)** |
| **[09-prs-reference.md](./09-prs-reference.md)** | **All PRs with timeline (migration + 9 months post-migration)** |
| **[10-scenario-what-if-questions.md](./10-scenario-what-if-questions.md)** | **"What if canary fails? .block() starvation? GTP BOM breaks?" - 10 scenarios** |

---

## 30-Second Pitch

> "I led the migration of cp-nrti-apis from Spring Boot 2.7 to 3.2 and Java 11 to 17. The main challenges were the javax→jakarta namespace change across 74 files, migrating from RestTemplate to WebClient, and adapting to Hibernate 6's stricter type handling. We deployed to production with **zero downtime** using Flagger canary deployments - 10% traffic initially, gradually increasing over 24 hours with automatic rollback if error rate exceeded 1%."

---

## Key Numbers to Memorize

| Metric | Value |
|--------|-------|
| Files changed | **158** |
| Lines added | **1,732** |
| javax→jakarta files | **74** |
| Test files updated | **42** |
| Spring Boot version | **2.7 → 3.2** |
| Java version | **11 → 17** |
| Production issues | **0 customer-impacting** |
| Deployment strategy | **Canary: 10%→25%→50%→100%** |

---

## Why This Migration?

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                        WHY SPRING BOOT 3 MIGRATION?                             │
│                                                                                 │
│  1. END OF SUPPORT                                                              │
│     • Spring Boot 2.7 EOL: November 2023                                       │
│     • Java 11 extended support ending                                          │
│     • No security patches for older versions                                   │
│                                                                                 │
│  2. SECURITY REQUIREMENTS                                                       │
│     • Snyk/Sonar flagging vulnerabilities                                      │
│     • Couldn't patch without upgrading                                         │
│     • Compliance requirements                                                   │
│                                                                                 │
│  3. ECOSYSTEM COMPATIBILITY                                                     │
│     • GTP BOM versions require Spring Boot 3                                   │
│     • Internal libraries moving to Jakarta EE                                  │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## The Three Major Challenges

### 1. javax → jakarta Namespace (74 files)

```java
// BEFORE (Spring Boot 2.x)
import javax.persistence.Entity;
import javax.validation.Valid;
import javax.servlet.http.HttpServletRequest;

// AFTER (Spring Boot 3.x)
import jakarta.persistence.Entity;
import jakarta.validation.Valid;
import jakarta.servlet.http.HttpServletRequest;
```

### 2. RestTemplate → WebClient

```java
// BEFORE
ResponseEntity<StoreResponse> response = restTemplate.exchange(
    url, HttpMethod.GET, new HttpEntity<>(headers), StoreResponse.class);

// AFTER (with .block() for sync compatibility)
StoreResponse response = webClient.get()
    .uri(url)
    .headers(h -> h.addAll(headers))
    .retrieve()
    .bodyToMono(StoreResponse.class)
    .block();
```

### 3. Hibernate 6 Compatibility

```java
// Required for PostgreSQL enum types
@Column(name = "status", columnDefinition = "status_enum")
@Enumerated(EnumType.STRING)
@JdbcTypeCode(SqlTypes.NAMED_ENUM)  // NEW in Hibernate 6
private Status status;
```

---

## Top Interview Questions

### 1. "Tell me about the Spring Boot 3 migration."
> "I led the migration from Spring Boot 2.7 to 3.2, Java 11 to 17. Main challenges: javax→jakarta across 74 files, RestTemplate to WebClient, Hibernate 6 compatibility. Zero-downtime deployment using Flagger canary."

### 2. "Why not go fully reactive with WebClient?"
> "Scope control. Full reactive would change every service class and error handling. For a framework upgrade, I wanted to minimize business logic changes. Used .block() for backwards compatibility."

### 3. "What was the hardest part?"
> "WebClient test mocking. RestTemplate is simple - mock exchange(). WebClient uses method chaining - had to mock get(), uri(), headers(), retrieve(), bodyToMono(). Test complexity doubled."

### 4. "Any production issues?"
> "No customer-impacting issues. Three minor post-migration fixes: Snyk vulnerabilities in transitive dependencies, one Sonar code smell around mutable collections, logging format adjustment. All caught proactively."

---

## Deployment Strategy

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                      CANARY DEPLOYMENT STRATEGY                                 │
│                                                                                 │
│   Phase 1: Stage (1 week)                                                      │
│   ├── Full regression suite                                                    │
│   ├── Performance testing                                                      │
│   └── All endpoints validated                                                  │
│                                                                                 │
│   Phase 2: Canary (traffic split)                                              │
│   ├── 10% traffic → New version (Spring Boot 3)                               │
│   ├── 90% traffic → Old version (Spring Boot 2.7)                             │
│   ├── Monitor: error rates, latency, CPU/memory                               │
│   └── Duration: 4 hours                                                        │
│                                                                                 │
│   Phase 3: Gradual Rollout                                                     │
│   ├── 25% → 50% → 75% → 100%                                                  │
│   ├── Automatic rollback if error rate > 1%                                   │
│   └── Duration: 24 hours total                                                 │
│                                                                                 │
│   Phase 4: Full Production                                                     │
│   ├── 100% traffic on Spring Boot 3                                           │
│   └── Old version kept 48 hours (rollback option)                             │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## Key PRs (gh verified)

| PR# | Title | Additions/Deletions | Merged | Why Important |
|-----|-------|---------------------|--------|---------------|
| **#1176** | Spring boot 3 migration for nrt final | +1,766 / -1,699 (151 files) | Mar 7, 2025 | **Initial migration groundwork** |
| **#1312** | Feature/springboot 3 migration | +1,732 / -1,858 (158 files) | Apr 21, 2025 | **THE MAIN PR** - Complete migration |
| **#1337** | Feature/springboot 3 migration (Release) | +1,795 / -1,892 (159 files) | Apr 30, 2025 | **Production release** (merge to main) |
| **#1332** | snyk issues fixed + mutable list | +48 / -36 | Apr 23, 2025 | Post-migration Snyk + List.of() |
| **#1335** | Major sonar issue fixed | +1 / -1 | Apr 23, 2025 | Post-migration code quality |

---

## Quick Reference: Interview Sound Bites

| Topic | Sound Bite |
|-------|-----------|
| **Overall** | "Led migration of production API from Spring Boot 2.7 to 3.2, Java 11 to 17, 158 files, zero downtime" |
| **javax→jakarta** | "145 import changes across the codebase, not just find-replace - some classes changed behavior" |
| **WebClient** | "Migrated from RestTemplate to WebClient with .block() for backwards compatibility" |
| **Hibernate 6** | "Added @JdbcTypeCode for PostgreSQL enum compatibility" |
| **Kafka** | "Migrated ListenableFuture to CompletableFuture for better error handling" |
| **Testing** | "42 test files updated. Four layers: unit, integration, stage (1 week), canary (24 hours)" |
| **Deployment** | "Flagger canary with 10%→25%→50%→100% traffic split, automatic rollback" |
| **Result** | "Zero customer-impacting issues, 3 minor post-migration fixes" |

---

## Files in This Folder

```
02-spring-boot-3-migration/
├── README.md                      # This file
├── 01-overview.md                 # Business context, scope
├── 02-technical-challenges.md     # javax→jakarta, WebClient, Hibernate
├── 03-code-changes.md             # Actual code examples
├── 04-deployment-strategy.md      # Canary deployment
├── 05-production-issues.md        # Post-migration fixes
├── 06-interview-qa.md             # Q&A bank
└── 07-how-to-speak-in-interview.md  # HOW to speak (pitches, stories)
```

---

*Last Updated: February 2026*
