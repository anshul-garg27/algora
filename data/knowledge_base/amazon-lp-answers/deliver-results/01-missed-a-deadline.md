# Q: Tell me about a time when you missed a deadline.

> **LP**: Deliver Results
> **Primary story**: `W5 — Spring Boot 3 Migration`
> **Backup story**: `P3 — Test Coverage Program`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

April 2025. I was leading the Spring Boot 2.7 → 3.2 and Java 11 → 17 migration on cp-nrti-apis — our main supplier-facing API. Snyk was flagging CVEs we could not patch without the upgrade. The audit deadline was three months out. I had committed to wrapping the main migration PR in two weeks, with a one-week stage validation before production.

I missed the two-week target by a week. The PR — eventually #1312 — landed on April 21, not April 14.

### Task

I had to be honest with my manager about the slip, find a path that did not compromise the audit deadline, and explain what I had learned.

### Action

The cause was not lazy planning. The migration was bigger than my initial estimate. 158 files, 1,732 lines added, 1,858 deleted. 74 files needed the javax → jakarta namespace change. 23 places needed `ListenableFuture` → `CompletableFuture` for Spring Kafka. 35 places adopted Java 17 `.toList()`. The WebClient test mocking alone roughly doubled the test code complexity — RestTemplate is one mock, WebClient is a four-step chain of mocks per call. I had estimated all of that as one week. It was two.

The moment I knew I would miss the date — end of week one, I had cleared 60% of the javax → jakarta files and the WebClient test mocks were eating real time — I told my manager that same day. Did not wait for the standup. Slack message: "I'm a week behind on #1312, here is why, here is the revised plan." I gave him a daily progress doc he could check without me having to interrupt him.

I made one strategic call to protect the audit deadline. A colleague had been pushing for full reactive with WebClient end-to-end. That would have been a three-month rewrite. I picked `.block()` on WebClient instead — same sync behavior, framework upgrade only, no business logic changes. Three weeks of work instead of three months. I wrote up the tradeoff doc — Mono/Flux refactor vs `.block()` — and walked my tech lead through it 1:1. He signed off.

I shipped the PR on April 21. Then I deliberately ran a one-week stage validation with production-like traffic. That stage week caught one issue that would have been a production incident — Hibernate 6 needed `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` on PostgreSQL enum columns. Without it, Hibernate sent VARCHAR and PostgreSQL rejected it. Fixed in stage, never hit prod.

### Result

Audit deadline hit. Production release April 30 with a Flagger canary — 10% → 25% → 50% → 100% over 24 hours, threshold of 99% success and P99 under 500ms. Zero customer impact across the rollout. Zero rollbacks. The thing I would do differently — start with a sized-up estimate for WebClient test mocking, because that was the single largest delta from my original plan. My new rule of thumb: if a migration touches every test file, double the estimate before you commit.

---

## Technical depth — if they probe

- **The .block() call**: WebClient with `.block()` keeps sync behavior. Anti-pattern only on a reactive event loop; our stack is not reactive. Saved 2-3 months of architecture change.
- **javax → jakarta scope**: 74 files, 145 jakarta imports added. Eclipse Foundation rename, every persistence/validation/servlet import touched.
- **WebClient test mocking**: Each chained call (`get().uri().headers().retrieve().bodyToMono()`) needs its own mock. 42 test files touched, complexity roughly doubled.
- **Hibernate 6 catch**: PostgreSQL custom enum types need `@JdbcTypeCode(SqlTypes.NAMED_ENUM)`. Hibernate 5 worked implicitly. Hibernate 6 strictly maps to VARCHAR without it, PostgreSQL throws "column is of type X but expression is of type character varying."

---

## Likely follow-ups

**Q: When exactly did you tell your manager?**
> The same day I knew. End of week one. Slack message before I left the office, daily progress doc by the next morning. The worst thing is hiding a slip until the deadline.

**Q: Why didn't you cut scope instead?**
> I did cut scope — `.block()` over reactive. The framework migration itself was non-negotiable because the audit deadline was firm.

**Q: What would you do differently?**
> Double the estimate on anything that touches every test file. The migration plan estimated WebClient mock refactor at half the time it took.

**Q: How did you keep the team confident?**
> Daily progress doc with concrete numbers — files migrated, tests passing, lines remaining. Anyone could check progress without asking me.

---

## What NOT to say

- Do not pretend you hit the deadline. The PR date is `git log` and the interviewer can ask.
- Do not blame the codebase. It was my estimate that was wrong.
- Do not say "I learned to communicate better." Be specific — daily progress doc, told manager day one of the slip.

---

## Backup story (if asked for another)

P3 — Test coverage at PayU intern. Committed to 80% in two months, delivered 83% in ten weeks. Slip was the early classes I refactored — coupling was worse than I estimated, extracting services for dependency injection took longer than writing tests. Told my mentor in week three, replanned, and shipped a week late but past target.
