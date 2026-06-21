# Q: Describe a time you led or developed a technical project. How did you proceed, and what were the success metrics?

> **LP**: Dive Deep
> **Primary story**: `W8 — DC Inventory Search API`
> **Backup story**: `G3 — Data Platform / Stir`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

In August 2025 our supplier platform had a gap. Pepsi, Coca-Cola and the rest could check store-level inventory but not distribution-center inventory. They needed it to plan replenishment. Nobody on our team had built this kind of API before, and the Enterprise Inventory team that owned the data had a 12-week backlog before they could help.

### Task

Design, build, and ship a DC Inventory Search API that supported US, Canada, and Mexico, accepted bulk requests up to 100 items, and went live before Q4 buying. I owned it end to end — spec, code, tests, rollout.

### Action

I went design-first. PR #260 was 898 lines of OpenAPI spec — endpoints, request and response schemas, validation rules, example payloads for every error scenario. I shipped the spec before any code and the consumer team started integration the same week with generated client SDKs. That alone bought us about three weeks of parallel work.

The implementation was a three-stage pipeline. Stage one converts WmItemNumbers to GTINs via the UberKey service. Stage two checks supplier authorization for each GTIN. Stage three calls Enterprise Inventory for the actual DC data. PR #271 was 3,059 lines across 30 files.

The hard part was error UX. A 100-item request can fail at any of those three stages, with different errors per item. I built a RequestProcessor abstraction — each stage takes the current (valid, invalid, errors) state, runs a function on the valid items, and accumulates failures with a source tag like `ERROR_SOURCE_UBERKEY`. The error refactor was PR #322, another 1,903 lines.

For US/CA/MX support I used a factory pattern. `SiteConfigFactory` injects `Map<String, SiteConfigProvider>` from Spring — adding Mexico was literally one `MXConfig` class with `@Component("MX")` and zero changes to the factory.

Container tests came last — PR #338, 1,724 lines with Docker, WireMock, and real Postgres test data. That's where I caught the GTIN-to-WmItemNumber reverse-mapping bug that unit tests had missed because of duplicate GTINs in production data.

### Result

Total ~8,000 lines from spec to tests across 8 PRs over 5 months. Bulk support live for US, CA, MX. P95 around 1.8 seconds for 100-item requests — about 33% faster than our similar inventory-status-srv. The design-first approach gave the consumer team a 30% integration-time reduction. Zero rollbacks since launch.

The metric I cared about most was partial-success rate. Around 12% of bulk requests have a mix of successes and failures. Because of the RequestProcessor, every one of those returns 200 with per-item `dataRetrievalStatus` and a reason. Suppliers process the 80 successes and handle the 20 errors individually — they don't throw the whole response away.

---

## Technical depth — if they probe

- **Why design-first**: The consumer team didn't have to wait for code. They mocked from the OpenAPI examples and built UI in parallel. R2C contract tests ran in CI to keep spec and implementation in sync.
- **Why always 200**: A 100-item bulk where 80 succeed is a successful request — there's useful data to return. 207 Multi-Status is technically correct (RFC 4918) but external suppliers don't all parse it. 200 with per-item status keeps the consumer code simple.
- **Why reverse-conversion**: Supplier sends WmItemNumber. Stage 2 errors come back tagged with GTIN (because that's our internal join key). Without conversion, the error reads "00012345678905 not mapped" — meaningless to the supplier. Reverse-converting back to WmItemNumber makes the error legible.
- **Why container tests caught what unit tests missed**: Unit tests stubbed the supplier-mapping repo with clean one-to-one GTIN data. Production has many-to-one mappings. Real Postgres in a Docker container surfaced the duplicate-handling gap. PR #330 fixed it with deterministic selection and integration coverage.

---

## Likely follow-ups

**Q: How did you measure the 30% integration-time saving?**
> Consumer team's internal milestone tracking. Their integration was scheduled to start when my implementation was ready (T+4 weeks). With the spec-first approach they started at T+0 and finished at T+4 instead of T+8. They reported the saving in their post-mortem.

**Q: What was the hardest technical decision?**
> Always-200 vs 207. I defended 200 in a design review against a senior architect who pushed for 207. I showed him the consumer code complexity diff: 12 lines of per-item status handling vs 40 lines of multi-status parsing. He agreed.

**Q: How did you sequence the work?**
> Spec first (PR #260). Then a thin slice end-to-end for US only (PR #271). Then the error refactor (PR #322) once we had the real bulk-error patterns from production. CA and MX added via factory after the refactor. Container tests last because we needed the stable shape.

**Q: What metric would you regret not tracking?**
> Per-stage latency breakdown. I have aggregate P95 but stage-2 (supplier validation) sometimes spikes when the supplier-mapping repo is cold. I'm adding stage-level histograms in Q2.

---

## What NOT to say

- Don't claim "I designed it in a vacuum" — name the design reviews with the senior architect and the consumer team.
- Don't list every PR — pick #260, #271, #322, #338. That's the story arc.
- Don't pitch the factory pattern as fancy — it's just Spring's `Map<String, T>` injection. Keep it simple.

---

## Backup story (if asked for another)

For G3, the Stir data platform at GCC was a different shape of project. I led the Airflow + dbt architecture — 76 DAGs, 112 dbt models — that took raw scraper output from ClickHouse and produced the materialized PostgreSQL tables the Coffee SaaS API served. Success metrics were dbt model freshness (every model under 15 minutes lag), test pass rate (95%+ across `dbt test`), and downstream API p95 (sub-second on supplier dashboards). I scoped, designed, and shipped it in 4 months as the sole architect.
