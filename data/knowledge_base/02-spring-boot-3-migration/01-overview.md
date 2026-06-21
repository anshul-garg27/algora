# Overview - Spring Boot 3 & Java 17 Migration

> **Resume Bullet:** 4
> **Repo:** `cp-nrti-apis`
> **Main PR:** #1312

---

## The Problem

### Why We Had to Migrate

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
│     • Snyk/Sonar flagging CVEs in dependencies                                 │
│     • Couldn't patch without upgrading framework                               │
│     • Would fail security audit in 3 months                                    │
│                                                                                 │
│  3. ECOSYSTEM COMPATIBILITY                                                     │
│     • GTP BOM versions require Spring Boot 3                                   │
│     • Internal libraries moving to Jakarta EE                                  │
│     • New features only available in SB3                                       │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## What We Migrated

### The Service: cp-nrti-apis

`cp-nrti-apis` is the **main API service** for Walmart Luminate's supplier-facing APIs:
- Handles inventory queries, DSD notifications, transaction history
- External suppliers (Pepsi, Coca-Cola, Unilever) depend on it daily
- ~100 requests/second per pod
- **Critical infrastructure** - downtime = supplier impact

### The Migration Scope

| What Changed | From | To |
|-------------|------|-----|
| **Spring Boot** | 2.7 | 3.2 |
| **Java** | 11 | 17 |
| **Namespace** | javax.* | jakarta.* |
| **HTTP Client** | RestTemplate | WebClient |
| **Kafka Futures** | ListenableFuture | CompletableFuture |
| **Security** | WebSecurityConfigurerAdapter | SecurityFilterChain |
| **Hibernate** | 5.x (implicit enums) | 6.x (@JdbcTypeCode) |

### By The Numbers

| Metric | Value | Verified From |
|--------|-------|---------------|
| Files changed | **158** | gh PR #1312 (changedFiles) |
| Lines added | **1,732** | gh PR #1312 (additions) |
| Lines deleted | **1,858** | gh PR #1312 (deletions) |
| jakarta imports added | **145** | gh PR #1312 diff (grep count) |
| Test files updated | **42** | gh PR #1312 diff (grep count) |
| .toList() Java 17 usage | **35 instances** | gh PR #1312 diff |
| CompletableFuture changes | **23 instances** | gh PR #1312 diff |
| Production issues | **0** customer-impacting | |
| Migration time | **~4 weeks** | PR #1312 merged Apr 21 |
| Production release | **Apr 30, 2025** | PR #1337 merged |

> **Note:** Earlier migration PR #1176 was also merged (Mar 7, 2025, 151 files) for initial groundwork. PR #1312 was the main migration PR.

---

## My Role

I **volunteered to lead** this migration:
- Analyzed the migration path and identified 3 main challenges
- Made the strategic decision to use `.block()` instead of full reactive
- Executed all code changes (158 files, 42 test files)
- Designed the deployment strategy (canary with Flagger)
- Handled 3 post-migration fixes proactively

---

## The Three Major Challenges

### 1. javax → jakarta Namespace (74 files)
Oracle transferred Java EE to Eclipse Foundation → renamed to Jakarta EE. Every `javax.persistence`, `javax.validation`, `javax.servlet` import had to change.

### 2. RestTemplate → WebClient (8 files + 34 test files)
RestTemplate deprecated. WebClient is reactive by default. **Strategic decision:** Use `.block()` for sync compatibility instead of full reactive rewrite.

### 3. Hibernate 6 Compatibility (15 entity files)
Stricter JPA compliance. PostgreSQL enums needed explicit `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` annotations.

*See [02-technical-challenges.md](./02-technical-challenges.md) for code details.*

---

## The Strategic Decision: .block() vs Full Reactive

This was the most important technical decision of the migration:

| Option | Pros | Cons | Time |
|--------|------|------|------|
| **Full Reactive** | Modern, non-blocking, better scalability | Touches every service class, new error patterns, team needs training | ~3 months |
| **.block()** | Minimal business logic changes, same behavior, faster delivery | Not truly reactive, thread still blocked | ~4 weeks |

**I chose .block()** because:
1. **Scope control** - Framework upgrade, not architecture change
2. **Risk reduction** - Minimize business logic changes
3. **Team readiness** - Reactive has a learning curve
4. **Pragmatism** - Full reactive would be a separate project

---

## Interview Sound Bites

### 30-Second Pitch
> "I led the migration of cp-nrti-apis from Spring Boot 2.7 to 3.2 and Java 11 to 17. Main challenges: javax→jakarta across 74 files, RestTemplate to WebClient with .block() for backwards compatibility, and Hibernate 6 enum handling. Zero-downtime canary deployment, zero customer-impacting issues."

### On the Decision
> "The key decision was using .block() instead of full reactive. Full reactive would've tripled the scope and risk. For a framework upgrade, I focused on shipping safely. Reactive would be a dedicated follow-up project."

### On What I'd Do Differently
> "Two things: migrate earlier (don't wait for EOL) and use OpenRewrite for automated namespace migration instead of semi-manual."

---

*Next: [02-technical-challenges.md](./02-technical-challenges.md) - Detailed technical challenges with code*
