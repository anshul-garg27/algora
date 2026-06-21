# Q: How do you balance the quality of your work against tight deadlines?

> **LP**: Deliver Results
> **Primary story**: `W5 — Spring Boot 3 Migration`
> **Backup story**: `W7 — DSD Notification System`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Spring Boot 2.7 to 3.2 and Java 11 to 17 migration on cp-nrti-apis, our supplier-facing API. April 2025. Snyk was flagging CVEs we could not patch without the upgrade. The security audit was three months out. The audit was firm. The deadline was tight, and "we'll fix it after" was not on the table for a compliance audit.

### Task

Ship a 158-file migration in under five weeks with zero customer-impacting issues and a clean canary rollout. Quality could not slip — supplier traffic from Pepsi and Coca-Cola hits this service all day.

### Action

I put the framework upfront. Quality on a deadline is not the same as "more time on every line." It is knowing which things you do not compromise and which things you defer.

What I refused to compromise. Three things.

The one-week stage validation. The team was pushing to skip it because we were behind. I held the line. That stage week caught the Hibernate 6 PostgreSQL enum issue — Hibernate stopped implicitly mapping enums to custom Postgres types. Without `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` on the field, Hibernate sent VARCHAR and Postgres rejected it. That would have been a production-breaking change. The stage week was non-negotiable.

The Flagger canary. 10% → 25% → 50% → 100% over 24 hours, with auto-rollback at 1% error rate or P99 over 500ms. The tempting move was a faster rollout to make up time. I refused. The canary takes 24 hours either way and a fast rollout for a framework migration is a recipe for the kind of incident that costs a week of recovery and a week of credibility.

The test coverage on the migration PR itself. WebClient test mocks roughly doubled in complexity — each chained call (`get().uri().headers().retrieve().bodyToMono()`) needed its own mock. 42 test files. I rewrote every one. Several of them I would have skimmed on a normal deadline.

What I deferred. Two things.

Full reactive WebClient. A colleague had pitched a full reactive rewrite — every service returning `Mono<T>`. That was a three-month rewrite of business logic, not a framework upgrade. I picked `.block()` instead. Same sync behaviour, framework upgrade only. Wrote up the tradeoff doc and walked my tech lead through it 1:1. He signed off. That single call cut the migration from three months to four weeks.

OpenRewrite automation for the javax → jakarta change. I did it semi-manually so the team understood every change. Slower than scripting. Worth it for a first migration. Documented it as a Q3 follow-up for the next major migration — automate the deterministic stuff, focus manual effort on behavioural changes.

When I slipped a week, I told my manager the same day. Built a daily progress doc — files migrated, tests green, lines remaining. Anyone could check progress without asking.

### Result

PR #1312 merged April 21. Production release April 30 via Flagger canary. Zero customer-impacting issues. Audit passed. Three minor post-migration items in the first two weeks — Snyk transitive CVE patches, a mutable-collection code smell, a Sonar major issue. All caught in CI, all fixed inside 48 hours. The thing I held on to — quality on a deadline means picking the one or two things you will not compromise and saying it out loud before the pressure starts. Stage week, canary discipline, test coverage. Everything else is a candidate for deferral.

---

## Technical depth — if they probe

- **The `.block()` decision**: WebClient with `.block()` keeps sync behaviour. Anti-pattern on a reactive event loop, not in our non-reactive context. Saved three months.
- **Hibernate 6 enum issue**: `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` on enum fields. Caught in stage week. Would have been a production breakage.
- **Flagger canary config**: `threshold: 5`, `maxWeight: 50`, `stepWeight: 10`, `interval: 1m`. Metrics — `request-success-rate >= 99%`, `request-duration P99 < 500ms`.
- **What deferred work looked like**: Reactive rewrite, OpenRewrite automation, full timeout/retry tuning on WebClient. All shipped in the post-migration fix waves (PRs #1394, #1425, #1564) over the next six months.

---

## Likely follow-ups

**Q: Where did you actually save time?**
> The `.block()` call. Three months → four weeks. That is the only place where the time really came from.

**Q: Why was stage week non-negotiable?**
> A framework migration changes thousands of behaviours under the hood. Functional tests pass and production still breaks. Stage with production-like traffic was the only way to surface the Hibernate enum bug.

**Q: What if the audit deadline had been one month tighter?**
> I would have pre-staged the dependency upgrades alone — Spring Boot 3.2 + Java 17 swap — and deferred the WebClient migration to a second PR. The CVE patches were the audit's actual ask.

**Q: How did you keep your manager confident under pressure?**
> Daily progress doc. Concrete numbers, no narrative. He could check the file without asking me.

---

## What NOT to say

- Do not say "I worked weekends to deliver quality." Quality is structural, not heroic.
- Do not pretend everything was kept. The reactive rewrite was deferred. Be honest about it.
- Do not skip the stage-week stand. That is the part interviewers want to hear.

---

## Backup story (if asked for another)

W7 — DSD notifications. Six weeks to ship push notifications to 1,200+ associates. I held on the in-store associate interviews (refused to cut scope without them) and the per-market feature flag pilot. I deferred SMS, photo-upload, and analytics consumers to weeks 8-12. Shipped on time, 35% replenishment improvement, zero supplier-spam complaints.
