# Q: How did you manage to complete the task?

> **LP**: Unclassified (follow-up question — Deliver Results + Ownership)
> **Primary story**: W5 — Spring Boot 3 Migration
> **Backup story**: W8 — DC Inventory Search API
> **Time budget**: 60–90 seconds spoken (follow-up depth, not fresh STAR)

---

## How to read this question

Like "how did you approach it", this is a **follow-up** after a story. The interviewer wants to know what made the task actually finish — the discipline, the resource decisions, the cuts you made along the way.

The honest answer is rarely "I worked harder". It's almost always:
1. I broke the work into shippable pieces
2. I cut scope ruthlessly when needed
3. I had a clear definition of done
4. I had a safety net for shipping

The example below assumes they've just heard the W5 Spring Boot 3 migration story and asked "how did you actually manage to complete it".

---

## The spoken answer (60–90 sec)

Four things.

**One — I split the work by risk, not by feature.** The migration was 158 files, but I didn't treat it as one PR. I split it into three categories. The javax→jakarta namespace change was mechanical — 74 files, fast review, low risk. The Hibernate 6 enum mapping change was a config-level fix per entity, medium risk. The RestTemplate→WebClient change was the one with real design exposure. I shipped them in that order so the easy 80 percent of files were in main before the risky 20 percent.

**Two — I made the call to use `.block()`, not full reactive.** That was the scope cut. A colleague wanted a full reactive rewrite while we were "touching the code anyway". I disagreed. I went away, ran numbers — 3 months reactive vs 4 weeks `.block()` — and brought the math to my lead. We agreed: framework upgrade now, reactive as a separate Q3 project. That decision was the difference between shipping in 4 weeks and shipping in 12.

**Three — I had a hard definition of done.** Definition of done for me was: zero test regressions in stage for a week, plus zero customer-impacting issues during canary. Not "all tests pass on my laptop". The canary metric was the contract — error rate > 1% triggered auto-rollback. That gave me a clear exit criterion instead of an open-ended "is it good enough".

**Four — Flagger canary was the safety net.** 10 percent traffic for 24 hours, then 25, then 50, then 100. Auto-rollback configured. Three minor post-canary fixes — all caught by the gradual rollout before customers noticed. Without the canary I'd have been stuck either delaying further or shipping with my fingers crossed.

The headline result — 158 files, zero customer impact, shipped in 4 weeks. The way it got done was scope discipline plus the safety net, not heroics.

---

## Why this works as a follow-up

- **Four discrete moves**, not a vague "I worked hard". Each one is a concrete decision the interviewer can probe.
- The **scope-cut moment** (.block() over reactive) is the highest-signal detail — engineers who can't cut scope ship slow.
- **Definition of done** + **safety net** are the two things SDE-3-and-above engineers track. Naming them signals seniority.
- You can substitute any story they ask "how did you manage to complete it" about — the shape is the same.

---

## Technical depth — if they probe

- **javax→jakarta migration in a single PR**: actually three PRs. Entities, validators+servlets, tests. Each PR ran the full CI build green before the next started.
- **Hibernate 6 enum fix**: added `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` on every PostgreSQL enum field. Hibernate 6 stopped inferring the enum type from the column metadata — without the annotation, it used `VARCHAR` and PostgreSQL rejected the binding.
- **`.block()` design**: `WebClient` with `.block()` calls preserves the synchronous call site. The reactive rewrite would've meant every `Service` method returning `Mono<T>`, every caller adapting, error handling fundamentally changing. The math: 158 files vs ~3000 files of follow-on changes.
- **Flagger canary configuration**: `progressDeadlineSeconds: 1800`, automatic analysis on `error_rate` (Prometheus query), `failureThreshold: 5`, traffic step 10%→25%→50%→100% with 30 minutes between steps once metrics held green.

---

## Variants — same four moves, different stories

### W8 — DC Inventory Search API
1. **Split by risk**: GTIN→CID conversion first (well-understood internal API), then supplier validation (PostgreSQL, owned), then DC inventory fetch (third-party API, riskiest). Each layer testable in isolation.
2. **Scope cut**: skipped a "fancy" caching layer in v1, shipped with direct calls. Added caching post-launch when monitoring showed actual hot keys.
3. **Definition of done**: 80% unit coverage, integration test against stage UberKey, load test 100 concurrent users in stage.
4. **Safety net**: KITT CI/CD with auto-rollback on health-check failure, Grafana dashboards live before launch.

### G1 — ClickHouse migration
1. **Split by risk**: build the buffered sinker first (testable standalone), then dual-write window (low-risk because Postgres still authoritative), then read cutover.
2. **Scope cut**: did not migrate historical data — only forward-write. Historical data stayed in Postgres for the 90-day retention window.
3. **Definition of done**: 2 weeks of dual-write with bit-for-bit parity on a sample query set.
4. **Safety net**: feature flag for read source — could revert ClickHouse reads to Postgres in 30 seconds.

---

## Likely follow-ups

**Q: What if Flagger had auto-rolled-back the canary?**
> It would've been fine. I'd have looked at the rollback metrics, fixed the issue, and re-canaried. Auto-rollback is the safety net — using it isn't failure, ignoring it would be.

**Q: How did you decide what to cut?**
> Test: "does this customer-visible behaviour change if we ship without this?" If no, it's cuttable. The reactive rewrite passed that test — no customer would notice the difference between synchronous and reactive at our load levels.

**Q: Did the scope cut create technical debt?**
> Yes — explicitly. The `.block()` calls are technical debt. I wrote a ticket for the reactive follow-up project before shipping, with the rationale, the affected files, and an effort estimate. That's the deal — you cut scope, you write the IOU.

**Q: Was there a moment you thought it wouldn't finish in time?**
> Yes — week 3, when I hit the Hibernate 6 enum issue. It looked like 200+ entities would need changes. Turned out only 18 had explicit PostgreSQL enum fields. The fear was bigger than the actual scope. The lesson — when the unknown looks scary, the cost of *measuring* the scope is almost always less than the cost of *fearing* the scope.

**Q: Would the canary safety net have caught a wrong design decision?**
> No — canary catches behavioural regressions, not architectural ones. If `.block()` had turned out to be the wrong call, canary would've shown nothing — it would've taken months for the cost to show up as developer drag. Different layer of risk needs a different safety net.

---

## What NOT to say

- Don't say "I worked nights and weekends" — that's not a competence story, it's a burnout flag.
- Don't claim "I followed Agile" — vague and unverifiable.
- Don't skip the scope cut. That's the SDE-3 signal — ship by cutting, not by adding.
- Don't pretend the canary was your idea — Flagger is the team's tool. Saying "I used the canary safety net" is honest; claiming credit for inventing it isn't.

---

## Backup story (W8 — DC Inventory Search API)

See the variant above. Same four moves — split-by-risk, scope cut (skipped caching v1), definition of done (coverage + load test in stage), safety net (KITT auto-rollback). Different surface area, same shape. Shipped in 4 weeks vs an EI-team estimate of 12. The discipline that made it finish was the same one that made the Spring Boot 3 migration finish — risk-ordered slices, ruthless scope discipline, and explicit safety nets.
