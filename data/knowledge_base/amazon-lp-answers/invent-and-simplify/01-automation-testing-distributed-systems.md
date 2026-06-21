# Q: Automation testing strategies for distributed systems.

> **LP**: Invent and Simplify
> **Primary story**: `W5 — Spring Boot 3 Migration`
> **Backup story**: `G3 — Stir Data Platform`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Last April I led the Spring Boot 2.7 to 3.2 upgrade on `cp-nrti-apis`, our main supplier-facing API. Suppliers like Pepsi and Coca-Cola hit it daily. 158 files moved. Zero downtime expected. The scary part wasn't the namespace change — it was proving the new stack behaved exactly like the old one.

### Task

I owned the test strategy. I needed confidence that javax → jakarta, WebClient with `.block()`, and Hibernate 6 wouldn't blow up under real supplier traffic.

### Action

I built four layers, smallest to most expensive.

Unit tests came first. 42 test files updated. WebClient mocking is painful — the builder chain needs five mocks per call. I wrote a small helper that pre-stubs `get()`, `uri()`, `headers()`, `retrieve()`, `bodyToMono()`. Test files basically doubled in complexity but were readable.

Then container tests with Testcontainers — real Postgres, real Kafka. This is where Hibernate 6 burned us. Enums on Postgres started failing with "column is of type status\_enum but expression is of type character varying". H2 in-memory tests never caught it. Real Postgres did. I added `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` and the test went green.

Then a one-week stage soak. Production-like traffic shape, not just functional smoke. That's where we caught one more enum-mapping case and a correlation-ID propagation edge case.

Finally Flagger canary in prod. 10 percent of traffic on Spring Boot 3, automatic rollback if error rate crossed 1 percent or P99 went past 500ms. Two-minute check intervals. I watched the dashboards for the first four hours myself.

### Result

Zero customer-impacting issues on rollout. The enum bug we caught in stage would have been a Sev-2. The pattern — unit, container, stage, canary — got copied by two other teams doing their own SB3 migrations. Honestly, the value wasn't the test count; it was knowing which layer would catch which class of bug.

---

## Technical depth — if they probe

- **Testcontainers over H2**: H2 lies about Postgres types. Testcontainers boots a real Postgres in Docker. Hibernate 6 enum bug would have shipped to prod otherwise.
- **WebClient mock chain**: Each call needs `mock(WebClient.RequestHeadersUriSpec.class)`, `mock(WebClient.RequestHeadersSpec.class)`, `mock(WebClient.ResponseSpec.class)`. We extracted a builder helper to cut boilerplate.
- **R2C contract testing**: Request-to-Contract checks every build that the API response matches the OpenAPI spec. Breaks the build if spec drifts from implementation.
- **Flagger config**: `stepWeight: 10`, `interval: 1m`, `request-success-rate > 99`, `request-duration P99 < 500ms`. If five checks fail, automatic rollback. No human needed.
- **Stage week**: Functional tests pass in 10 minutes. We ran stage for a week with production traffic to surface heap, correlation-ID, and probe issues that only appear under real load.

---

## Likely follow-ups

**Q: How did you handle flaky tests?**
> Testcontainers can be flaky on slow CI runners. I pinned image versions and added a 30-second startup wait on the Postgres container. Flake rate dropped from ~5 percent to under 1 percent.

**Q: What about chaos testing?**
> We didn't do formal chaos engineering on this migration. I did manually kill primary Kafka region in stage to verify the new CompletableFuture failover chain — the old `ListenableFuture` code silently swallowed exceptions and the secondary was never tried. That alone made the migration worth doing.

**Q: Did you do load testing?**
> Yes. Same throughput as production for a week in stage. That's how we caught the heap OOM patterns later — actually we didn't catch them, they showed up six months in. Functional load isn't the same as sustained production load.

**Q: How do you test something async like `@Async` audit logging?**
> We use `Awaitility` for async assertions in tests. For the audit library specifically, the thread pool is bounded, so we wait up to 5 seconds for the queue to drain and then assert the HTTP mock got hit.

**Q: What would you do differently?**
> Two things. Use OpenRewrite for the mechanical javax → jakarta — it's deterministic, four weeks of manual work could be a day. And run load tests at 2x production volume in stage, not 1x — the production-load issues only surface above peak.

---

## What NOT to say

- Don't say "100 percent coverage" — testing strategy isn't about a number, it's about which bug is caught at which layer.
- Don't overclaim chaos engineering — we didn't run Chaos Monkey.
- Don't pitch this as a testing framework I invented — Testcontainers, Flagger, R2C are existing tools used together.

---

## Backup story (if asked for another)

At GCC I built the Stir data platform — 76 Airflow DAGs, 112 dbt models reading from ClickHouse. For testing I leaned on dbt's built-in `dbt test` for schema checks (`not_null`, `unique`, `accepted_values`) plus custom data tests for row-count parity between source and mart. Slack alerts fired on any DAG failure. The test suite caught a profile-id mismatch between Beat and Coffee before it hit any leaderboard.
