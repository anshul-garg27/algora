# Q: Tell me about a time you had to learn something new and apply it in your work.

> **LP**: Learn and Be Curious
> **Primary story**: `W5 — Spring Boot 3 Migration`
> **Backup story**: `W11 — Unified Onboarding / IAM`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Early 2025 at Walmart Data Ventures. Spring Boot 2.7 was approaching end-of-life. Snyk was already flagging CVEs we couldn't patch without upgrading. Our security team gave us 3 months before audit failure. Our main supplier API — cp-nrti-apis — was on Spring Boot 2.7, Java 11. The migration target was Spring Boot 3.2 and Java 17. The catch — Hibernate 6 had changed how PostgreSQL enums work, RestTemplate was deprecated for WebClient, and the entire `javax.*` namespace had moved to `jakarta.*`.

### Task

I volunteered to lead the migration. None of the team had done a Hibernate 6 or `jakarta` migration before. I needed to learn what was actually changing, then ship it without breaking supplier APIs.

### Action

I treated it like a research project for the first week. Read the Spring Boot 3 migration guide front to back. Then read the Hibernate 6 migration guide, which is where the real surprises live. Hibernate 6 is much stricter about JPA compliance — PostgreSQL enum fields that worked implicitly in Hibernate 5 now needed an explicit `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` annotation. I learned this by reading, not by guessing.

WebClient was the part I had no experience with. RestTemplate is synchronous and simple — `restTemplate.exchange(...)`. WebClient is reactive — `webClient.get().uri().retrieve().bodyToMono(...)`. The decision I had to learn enough to make was: go fully reactive, or use `.block()` to keep synchronous behaviour. A colleague pushed for full reactive — "we're already touching the code." I built a comparison: 4 weeks framework-only with `.block()` versus 3 months full reactive with new error patterns across every service. The team agreed. `.block()` won.

Then I learned about Hibernate 6 PostgreSQL enums the hard way — caught the issue in our 1-week stage soak, not in unit tests. H2 in-memory database doesn't enforce the same type rules as PostgreSQL. Lesson there — for type-sensitive ORM migrations, you have to run against the real database in stage. PR added `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` to 15 entity files.

The CompletableFuture migration — `ListenableFuture` was deprecated in Spring Kafka 3.x. I learned to chain `.thenAccept().exceptionally().join()`. The bonus — our multi-region Kafka failover code had a real bug under `ListenableFuture` where exceptions were swallowed silently. Migrating to CompletableFuture actually fixed that bug.

158 files changed in total. 42 test files updated. Deployed with Flagger canary — 10% to 100% over 24 hours with automatic rollback at 1% error rate.

### Result

Zero customer-impacting issues. Four weeks total. Three minor post-migration fixes — all caught by CI, not by users. The pattern I now apply — read the official migration guide before the Stack Overflow answers, validate type-sensitive changes against the real database, and use canary deployments with auto-rollback when changing the framework under a running system. I now advocate for annual upgrade cycles instead of waiting for EOL panic.

---

## Technical depth — if they probe

- **Hibernate 6 enum fix**: `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` on the field. Without it Hibernate sends VARCHAR and PostgreSQL rejects with "column is of type status_enum but expression is of type character varying."
- **.block() reasoning**: scope control. Full reactive changes every service method signature to return `Mono`/`Flux`. Framework upgrade should minimise business logic change.
- **Why .block() is not an anti-pattern here**: it's only an anti-pattern on a reactive event loop thread. On a normal Tomcat servlet thread, it's effectively RestTemplate behaviour with WebClient's API.
- **CompletableFuture fixes a real bug**: with ListenableFuture's callback style, exceptions in primary Kafka publish were swallowed, secondary never tried. With CompletableFuture, `.exceptionally()` chains the secondary publish.
- **Flagger canary**: 10% → 25% → 50% → 100% over 24 hours. Auto-rollback if `request-success-rate < 99%` for 5 consecutive 1-minute checks.

---

## Likely follow-ups

**Q: Why didn't H2 catch the Hibernate enum issue?**
> H2 doesn't have PostgreSQL's strict custom-type enforcement. The mismatch only shows when Hibernate sends VARCHAR to a column declared as a PostgreSQL enum type. That's why we kept a 1-week stage soak against the real database.

**Q: Anything you'd do differently?**
> Yes — set WebClient timeout and retry from day one. We added that 6 months later in PR #1564 after sustained production load surfaced gaps. RestTemplate had implicit timeout, WebClient doesn't.

**Q: How did you get sign-off on .block()?**
> 1:1 with the team lead, not the design meeting. I brought the timeline comparison (4 weeks vs 3 months) and a one-page risk doc. Decision in 30 minutes.

**Q: What was the most surprising thing you learned?**
> That a framework migration isn't done when the PR merges. We had 10 post-migration PRs over 9 months — GTP BOM upgrades, heap OOM, correlation ID, K8s probe behaviour. The migration was truly "done" about 6 months after go-live.

---

## What NOT to say

- Don't claim the migration was zero work. 158 files, 4 weeks of focused effort, plus 9 months of follow-on.
- Don't say `.block()` is always fine. It's fine for this codebase. On a reactive stack it's an anti-pattern.
- Don't gloss over the Hibernate enum issue — that's the concrete "I almost shipped a bug, stage soak caught it" moment.

---

## Backup story (if asked for another)

W11 IAM platform. I needed to learn Apollo Federation and NestJS to build the GraphQL BFF. Federation was new — `@key` directives, subgraph composition, schema stitching versus federation. Two weekends of reading and a prototype subgraph got me productive. The harder learning was cross-domain auth — our DevX session tokens were invalid in the Scintilla domain. I learned the AppToApp token pattern and used it for all downstream calls. Same shape as SB3 — read the official docs first, then build something small to feel the edges.
