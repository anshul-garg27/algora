# Q: Tell me about a time when you missed a deadline, what could you have done better.

> **LP**: Deliver Results
> **Primary story**: `W5 — Spring Boot 3 Migration`
> **Backup story**: `P3 — Test Coverage Program`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

The Spring Boot 3 migration on cp-nrti-apis, April 2025. Snyk was flagging CVEs in our dependency tree that we could not patch without the framework upgrade, and our security audit window was three months out. I had told my manager I would have the main migration PR up in two weeks. I shipped it in three.

### Task

Land the migration safely without missing the audit, and figure out what I should have done differently from day one.

### Action

The slip was real. Two weeks vs three. Looking back, the failure was in the estimate, not the execution.

Where I underestimated. 158 files changed, 1,732 lines added. The javax → jakarta change touched 74 files. I had assumed it was a find-replace — it was not. Some classes had behavioural changes around servlet filter method signatures. RestTemplate → WebClient was the bigger surprise. The production code looked fine — clean, declarative. The test code was a different story. RestTemplate is one mock call. WebClient is a chain of four — `get()`, `uri()`, `retrieve()`, `bodyToMono()`. Every test file with an HTTP call had to be rewritten. 42 test files. That was roughly half my actual time.

What I did right when I knew I was slipping. Told my manager the same day. End of week one — I had finished 60% of the javax conversions and the WebClient mocks were eating real time. I sent a Slack message before I went home: "I'm a week behind, here is why, here is the new plan." Then I built a daily progress doc — files migrated, tests green, lines remaining — that anyone on the team could read without me being in the room.

The strategic call I am most proud of — cutting scope on reactive. A colleague had argued for full reactive WebClient end-to-end. That was a three-month rewrite of every service class to return `Mono<T>`. With `.block()` on WebClient, behaviour stays sync, business logic stays untouched, framework upgrade ships. I wrote up the tradeoff side-by-side and walked my tech lead through it 1:1 before the broader review. He signed off. That call alone saved the audit deadline.

I also held the line on the stage week. A week of stage validation under production-like traffic. The team wanted to skip it because we were already a week late. I refused. That stage week caught the Hibernate 6 PostgreSQL enum bug — Hibernate stopped implicitly mapping enums to custom Postgres types, which means without `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` it tried to send VARCHAR and Postgres rejected it. Fixed in stage, never hit prod.

### Result

PR #1312 merged April 21. Production release April 30 via Flagger canary — 10% → 25% → 50% → 100% over 24 hours with auto-rollback at 1% error rate. Zero customer-impacting issues. Audit passed. What I would do differently — and what I have actually changed: if a migration touches every test file, my new rule is to double the original estimate before I commit. I have run two migrations since with that rule. Both landed inside their original quote.

---

## Technical depth — if they probe

- **The estimate gap**: WebClient test mock complexity. Each chained call needs its own mock instance. 42 test files, complexity roughly doubled. The single biggest delta in my plan.
- **The `.block()` call**: WebClient with `.block()` is sync behaviour with WebClient's API. Anti-pattern only on a reactive event loop. Our stack is not reactive — the call is fine.
- **Hibernate 6 catch in stage**: Stricter JPA compliance. `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` required on PostgreSQL enum columns. Would have been a production-breaking change.
- **Flagger config**: `threshold: 5`, `maxWeight: 50`, `stepWeight: 10`, `interval: 1m`. Metrics — `request-success-rate >= 99`, `request-duration P99 < 500ms`.

---

## Likely follow-ups

**Q: What's the one biggest lesson?**
> Estimating a migration is estimating the test rewrite, not the source rewrite. The test code is where the time hides.

**Q: How did you protect the audit deadline?**
> The `.block()` decision. That single call cut three months of work out of the plan.

**Q: How did you communicate the slip?**
> Same day I knew. Slack to my manager that evening, daily progress doc the next morning. No surprises at the deadline.

**Q: What would you not do differently?**
> The stage week. Even under pressure, I held it. That week caught the Hibernate enum bug. Skipping stage to ship faster is a false economy.

---

## What NOT to say

- Do not blame the codebase or the team. The estimate was mine.
- Do not say "I'd communicate better." Be specific — Slack same day, daily progress doc.
- Do not skip the audit context. The deadline mattered for real reasons.

---

## Backup story (if asked for another)

P3 — Test coverage at PayU. Committed to 80% in two months. The early classes needed dependency-injection refactors before they were testable — that ate weeks I had not planned for. Told my mentor in week three, replanned, shipped 83% in ten weeks. Lesson: refactor effort scales with coupling, not LOC.
