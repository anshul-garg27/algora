# Bullet 4 — Spring Boot 2.7→3.x / Java 11→17 Migration with Flagger Canary

> **Resume line (verbatim):** "Led Spring Boot 2.7 to 3.2 / Java 11 to 17 migration for the main supplier-facing API with Flagger canary releases (10% to 100%), achieving zero customer-impacting issues."

> **Repo:** `cp-nrti-apis` (Channel Performance Near-Real-Time Inventory APIs), org `dsi-dataventures-luminate`, WCNP namespace `data-ventures-luminate-cperf`.
> **Single source of truth for this bullet.** Every claim below is grounded in the actual `pom.xml`, `kitt.yml`, and `src/main` of `cp-nrti-apis`. Where the older prep docs (`02-spring-boot-3-migration/*`, `DEEP-DIVE-BULLET-4-...`) disagree with the code, this doc flags it loudly so you are never surprised by your own repo.

---

## 0. The single most important honesty correction (READ FIRST)

The older prep docs and the resume line contain **three drifts you must own before an interviewer opens the repo:**

1. **Version: the resume says "3.2"; the code is `spring-boot-starter-parent` 3.5.14 with the `spring-boot-dependencies` BOM pinned to `3.5.7` (`springboot.version=3.5.7`).** Both numbers are literally in `pom.xml` (parent on line 8, BOM property on line 36). The BOM import wins for the *effective* dependency versions, so the app runs on **Spring Boot 3.5.7**. The clean way to say this: *"I led the 2.7 → 3.x jump — the hard part was crossing the major version. We landed on 3.2 initially and have since stayed current; the repo is on 3.5.x today."* Never claim "we're on exactly 3.2" — they can `cat pom.xml`.

2. **There is NO Spring Security in this repo.** `grep` for `spring-security`, `SecurityFilterChain`, `WebSecurityConfigurerAdapter`, `antMatchers`, `requestMatchers` returns **zero** matches in `pom.xml` and `src/main`. The old doc `02-technical-challenges.md` "Challenge 5: Spring Security 6" with `WebSecurityConfigurerAdapter → SecurityFilterChain` is **a generic migration topic, not something this codebase did.** Auth here is done by **servlet `Filter`s + a `HandlerInterceptor` + the Walmart API gateway** (signature verification is at the gateway, not in-process). You can *speak to* the Security 5→6 break as industry knowledge, but if asked "show me your `SecurityFilterChain`," answer: *"This service doesn't use Spring Security — authentication/signature verification is enforced at the Walmart API gateway (WM-SEC headers), and in-process we use a custom `OncePerRequestFilter` (`RequestFilter`) plus an interceptor (`NrtiApiInterceptor`). So the Security-config migration cost was zero for us; our servlet-API cost was in the filters and wrappers."*

3. **There was no `RestTemplate → WebClient` migration in this repo.** `grep RestTemplate src/main` returns **zero**. The outbound client is reactive `WebClient` (defined in `configs/WebClientConfig.java`), and per the cross-repo audit it was WebClient before the migration too. The old doc's "Challenge 2: RestTemplate → WebClient" is **not** what happened here. Don't claim it. (You *can* truthfully say the WebClient stayed and you validated it against the WebFlux 6 / Reactor changes.)

Everything else in the bullet holds up well and is strongly code-backed: **javax→jakarta is real and essentially complete** (149 `jakarta.*` references vs only 2 residual `javax.*`, one of which is correct), **Java 17 is real** (`java.version=17`, `<release>17</release>`), **Flagger canary is real and configured in `kitt.yml`**, and the **Hibernate 6 enum fix (`@JdbcTypeCode`) is real** (`entity/ParentCompanyMapping.java`).

---

## 1. Plain-English: what this actually is (ELI5 then precise)

**ELI5.** Our supplier-facing inventory API was running on an old engine (Spring Boot 2.7 + Java 11) that was heading toward end-of-life — no more security patches. I swapped in the new engine (Spring Boot 3 + Java 17) **while the car was driving**, by first sending only 10% of real supplier traffic to the new engine, watching the dashboards, and only turning up the dial to 100% once the error rate and latency stayed flat. Because of that gradual rollout (driven by a tool called Flagger), no supplier ever saw a broken response.

**Precise.** A **major-version framework migration** of `cp-nrti-apis`, the external REST gateway suppliers use to read/write Walmart inventory. The migration crossed two simultaneous breaking boundaries:
- **Spring Boot 2.7 → 3.x** — which forces the **Jakarta EE namespace break** (`javax.* → jakarta.*` for servlet, persistence, validation), **Hibernate 5 → 6** / **Spring Data JPA 2 → 3**, **Spring Framework 5 → 6**, **Spring Kafka 2 → 3** (`ListenableFuture → CompletableFuture`), and **Spring MVC 6** exception-handling changes (`HttpStatus → HttpStatusCode`, new `NoResourceFoundException`).
- **Java 11 → 17** — a new LTS with language features (records, sealed types, pattern-matching `switch`, text blocks), G1/ZGC GC defaults, and removed/deprecated APIs (e.g., `SecurityManager` deprecation).

Delivery was **progressive (canary) on WCNP/Kubernetes + Istio, orchestrated by Flagger**: traffic shifted in `stepWeight: 10` increments up to `maxWeight: 50`, gated by a Prometheus/Envoy metric (5xx error rate over a 2-minute window), with **automatic rollback** on breach. The outcome metric — "zero customer-impacting issues" — is the success-rate gate never tripping plus no customer-reported incidents through the rollout.

---

## 2. The real architecture (grounded in code)

### 2.1 What `cp-nrti-apis` is (so the migration has context)

```
                          SUPPLIER (external)
                                │  HTTPS + WM-SEC signed headers
                                ▼
                    ┌───────────────────────────┐
                    │   Walmart API Gateway       │  ← inbound signature/auth verified HERE
                    │   (mTLS, WM_SEC.* check)    │     (NOT in this repo)
                    └───────────────┬─────────────┘
                                    ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │  cp-nrti-apis  (Spring Boot 3.5.7 / Java 17, Tomcat servlet stack)       │
   │                                                                          │
   │  filters/ (jakarta.servlet)                                              │
   │   NrtCorsFilter (HIGHEST_PRECEDENCE) → RequestFilter (LOWEST_PRECEDENCE  │
   │   -100, OncePerRequestFilter: validates wm_consumer.id → 401,            │
   │   opens Strati txn) → StoreInboundRequestFilter → XssFilter              │
   │            │                                                             │
   │            ▼                                                             │
   │  interceptors/ NrtiApiInterceptor (HandlerInterceptor; PSP supplier ctx) │
   │  registered in configs/WebConfig.java (WebMvcConfigurer.addInterceptors) │
   │            │                                                             │
   │            ▼                                                             │
   │  controller/  (header-based multitenant dispatch on wm_svc.name)         │
   │   NrtiStoreControllerV1 | IacControllerV1 | InventoryController(gen)      │
   │            │                                                             │
   │            ▼                                                             │
   │  services/impl/ NrtiStoreServiceImpl                                     │
   │     ├── reactive WebClient (.block())  →  Enterprise Inventory (EI)      │
   │     ├── JPA/Hibernate 6  →  PostgreSQL (authorization matrix)            │
   │     ├── BigQuery client  →  items-assortment                            │
   │     └── NrtKafkaProducerServiceImpl  →  dual-region Kafka (IAC/DSC)      │
   └────────────────────────────────────────────────────────────────────────┘
```

### 2.2 The migration "surface area" — real files and what changed in each

| Migration boundary | Concrete file(s) (real paths) | What the SB3/Java17 change was |
|---|---|---|
| **Build / version pin** | `pom.xml` | parent `spring-boot-starter-parent` **3.5.14** (line 8); `spring-boot-dependencies` BOM `springboot.version=3.5.7` (line 36, effective); `java.version=17` (line 26); `<release>${java.version}</release>` in compiler plugin (line 706). |
| **Servlet API (jakarta)** | `filters/RequestFilter.java`, `filters/XssFilter.java`, `filters/NrtCorsFilter.java`, `filters/NrtResponseFilter.java`, `filters/StoreInboundRequestFilter.java`, `wrappers/XssRequestWrapper.java`, `interceptors/NrtiApiInterceptor.java` | `import javax.servlet.* → jakarta.servlet.*`. E.g. `RequestFilter.java:11,15,16,17` import `jakarta.servlet.{ServletException,FilterChain}` and `jakarta.servlet.http.{HttpServletRequest,HttpServletResponse}`. |
| **Persistence API (jakarta)** | `entity/*.java` (e.g. `ParentCompanyMapping.java`, `NrtStoreGtinMapping.java`, `Vendor.java`, `BaseEntity.java`) | `javax.persistence.* → jakarta.persistence.*` (36 references). |
| **Validation API (jakarta)** | `requests/**/*.java`, `models/**`, `validations/*` | `javax.validation.* → jakarta.validation.*` (58 `jakarta.validation.constraints` + 24 `jakarta.validation.*` references). |
| **Hibernate 5 → 6 (enum + array types)** | `entity/ParentCompanyMapping.java:126-135`, `entity/NrtStoreGtinMapping.java:42` | Added `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` alongside `@Enumerated(EnumType.STRING)` for PG enums; `@JdbcTypeCode(SqlTypes.ARRAY)` for the `Integer[] store_number` column. This is the canonical Hibernate-6 strict-typing fix. |
| **Spring Kafka 2 → 3 (`ListenableFuture` removed)** | `services/impl/NrtKafkaProducerServiceImpl.java:11,67,77,84,111-145` | `ListenableFuture` → `CompletableFuture<SendResult<...>>` with `.thenAccept(...)` / `.exceptionally(...)` (the `.exceptionally` is the primary→secondary region failover). |
| **Spring MVC 6 exception handling** | `exception/handlers/NrtiRestExceptionHandler.java:56,69,101,807-810` | `HttpStatus → HttpStatusCode` in `ResponseEntityExceptionHandler` overrides; added `@ExceptionHandler` for the new `org.springframework.web.servlet.resource.NoResourceFoundException` (Spring 6 throws this for unmapped paths). |
| **Java 17 stream cleanup** | across `src/main` | `.collect(Collectors.toList())` → `.toList()` (14 `.toList()` present; 19 `Collectors.toList` still remain — a *partial* cleanup, see watch-outs). |
| **OpenAPI generator → SB3 mode** | `pom.xml:828-859` (`openapi-generator-maven-plugin`) | `useSpringBoot3=true`, `useJakartaEe=true`, `java17=true`, `delegatePattern=true` — generated `InventoryControllerApi` + models target Jakarta/SB3 and emit RFC-7807 `ProblemDetail`. |
| **Datasource wiring (unaffected but relevant)** | `NrtiApiApplication.java` (`exclude = DataSourceAutoConfiguration.class`), `configs/postgres/PostgresDbConfiguration.java` | Manual `DataSource`/`EntityManagerFactory` beans via Walmart `PostgreSQLUtil`; note `import javax.sql.DataSource` — **correctly kept** (`javax.sql` is JDK/Java SE, *not* Jakarta EE; it never moved). |

### 2.3 The Flagger canary path (from `kitt.yml`)

```
   git push to main (releaseRefs: [main])
        │
        ▼  KITT pipeline (buildType: maven-j17, profile "flagger" + "springboot-web-jre17")
   build → dev (scus-dev-a3, useast-dev-aks-002)
        → stage (eus2-stage-a4, uswest-stage-az-006): R2C contract test (threshHold 80, Active),
          Automaton perf, RaaS resiliency gate, Looper e2e
        → prod (eus2-prod-a30, scus-prod-a63): rollbackOnError: true, changeRecord auto
        │
        ▼  Flagger (global.flagger in kitt.yml)
   ┌──────────────────────────────────────────────────────────────────┐
   │ canaryAnalysis:                                                    │
   │   stepWeight: 10        ← shift +10% per successful interval        │
   │   maxWeight: 50         ← canary caps at 50%, then promotes         │
   │   interval: 2m          ← evaluate metrics every 2 minutes          │
   │ progressDeadlineSeconds: 600                                        │
   │ canaryReplicaPercentage: 50                                         │
   │ canaryService.metrics:                                             │
   │   name: "Check for Internal Server Error (5XX)"                    │
   │   threshold: 1          ← rollback if 5xx rate > 1% over 2m         │
   │   query: PromQL over envoy_cluster_upstream_rq{response_code_class  │
   │          =~"5.*", cluster_name=~"...-canary..."} / total * 100      │
   └──────────────────────────────────────────────────────────────────┘
        │  Istio VirtualService splits traffic primary↔canary
        ▼
   10% → 20% → 30% → 40% → 50% (maxWeight) → PROMOTE to 100%
   (any 2-minute window with >1% 5xx on the canary → automatic rollback)
```

**Precise, code-grounded canary facts** (from `kitt.yml` lines 722-748):
- `stepWeight: 10`, `maxWeight: 50`, `interval: 2m`, `progressDeadlineSeconds: 600`, `canaryReplicaPercentage: 50`.
- The gate metric is a **PromQL query over Envoy sidecar metrics** (`envoy_cluster_upstream_rq`), not a generic "request-success-rate" — it computes `5xx rate / total rate * 100 > 1` over a 2-minute window for the `-canary` cluster.
- `prod` stage has `rollbackOnError: true` (line 427) and `changeRecord.create: true` (auto) — KITT-level rollback in addition to Flagger's metric-driven rollback.
- Prod scaling: `min 6 / max 12` pods, `cpuPercent: 60` HPA target (lines 485-487).
- Profiles enabling all this: `flagger`, `springboot-web-jre17`, `enable-springboot-metrics`, `goldensignal-strati`, `dynatrace-saas-walmart` (lines 5-11).

> **IMPORTANT canary nuance to be precise about:** the resume says "10% to 100%". In `kitt.yml`, Flagger steps **10% → 50% (maxWeight)** in +10 increments, then **promotes the canary to 100%** (the canary becomes the new primary). So "10% to 100%" is accurate end-to-end, but the *gradual analysis* phase tops out at 50% weight before promotion — say it that way if pushed: *"Flagger ramps weight to maxWeight 50%, and once the canary is healthy at 50% it's promoted to take 100% of traffic."*

---

## 3. Every design decision

| # | Decision | Why | Alternatives considered | Trade-off / what we gave up |
|---|---|---|---|---|
| 1 | **Migrate SB2.7→3.x + Java 11→17 together, not separately** | SB3 *requires* Java 17 baseline; doing them in two passes means building/testing an intermediate state that ships nothing extra. One coordinated cut reduces total regression surface. | (a) Java 17 first on SB2.7, then SB3 later. (b) Stay on 2.7 (EOL risk). | Bigger single PR / blast radius; harder to bisect a regression. Mitigated by staging + canary. |
| 2 | **BOM-first dependency upgrade** (`spring-boot-dependencies` import pins everything) | One coherent, tested set of transitive versions; avoids hand-pinning dozens of artifacts and version-skew bugs. | Manually bump each `<version>`. | The parent (3.5.14) and BOM (3.5.7) being different numbers looks confusing — you must explain BOM-wins. |
| 3 | **Keep the servlet (Tomcat) stack; do NOT go fully reactive** | The whole codebase is blocking/synchronous; controllers call `WebClient...block()`. A full reactive rewrite is a separate, riskier initiative orthogonal to a framework upgrade. | Migrate to WebFlux/Netty end-to-end. | We carry both `spring-boot-starter-webflux` and `spring-boot-starter-tomcat` on the classpath (pom lines 171-178). WebClient comes from WebFlux but runs on the servlet container — slightly unusual, must explain. |
| 4 | **Canary (Flagger) over blue/green / rolling / big-bang** | Catches load-only regressions at 10% before full exposure; **automatic** metric-gated rollback; already the org standard on WCNP+Istio. | Big-bang (no safety), blue/green (instant 100% switch — no partial-exposure signal), plain rolling (no metric gate/auto-rollback). | Canary is slower (hours) and needs good metrics; a metric the gate doesn't watch can still slip through. |
| 5 | **5xx error-rate gate (PromQL/Envoy) as the canary success criterion** | 5xx is the cleanest functional-regression signal for a backend API; available from the Istio sidecar with no app changes. | request-duration P99 gate, custom Dynatrace SLO gate, success-rate gate. | A migration bug that returns wrong 200s (semantic regression, not a 5xx) would NOT trip this gate — contract tests (R2C) must cover that. |
| 6 | **Hibernate 6 enum: `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` rather than reverting to `varchar`** | Keeps the PostgreSQL native enum type; the explicit annotation is the Hibernate-6-sanctioned way and avoids a schema change. | Map enum columns to plain `varchar`; downgrade Hibernate. | Adds Hibernate-specific annotations to entities (slight vendor lock to Hibernate types). |
| 7 | **`.exceptionally()` failover on `CompletableFuture` (Kafka)** | The `ListenableFuture` removal *forced* a callback rewrite; we used the opportunity to make failures explicit and route IAC sends to the secondary region. | Keep callbacks via a shim; ignore failover. | IAC vs DSC failure semantics ended up inconsistent (IAC→503, DSC→swallowed) — a real smell (see watch-outs). |
| 8 | **Validate via contract tests (R2C, threshold 80, Active) + Automaton perf + RaaS resiliency in stage before prod** | "Zero customer impact" needs proof the *contract* is unchanged, not just that the app boots. R2C runs the OpenAPI spec against stage and fails the pipeline below 80% pass. | Manual smoke tests only; rely on unit tests. | Heavier pipeline, longer lead time; some generated-code paths only exist after `mvn generate-sources`. |

---

## 4. Deep-dive Q&A (fundamentals → internals → scenario → behavioral)

### FUNDAMENTALS

**Q1. Why does Spring Boot 3 force a Java 17 baseline?**
> I... Spring Boot 3 / Spring Framework 6 set their minimum to Java 17 and compile against the Jakarta EE 9+ APIs. There's no supported way to run SB3 on Java 11 — the bytecode and the Jakarta namespace both require it. So the Java upgrade isn't optional; it's a precondition. That's exactly why I did them as one coordinated migration instead of two.

**Q2. What is the javax→jakarta change and why did it happen?**
> I... When Oracle transferred Java EE to the Eclipse Foundation, the trademark "javax" couldn't move, so every Java EE package was renamed to `jakarta.*` starting Jakarta EE 9. It's a *namespace* break, not a behavior break for most APIs — but because it's at the package level, it touches every import of servlet, persistence, and validation. In our repo that's 149 `jakarta.*` references across filters, entities, and request DTOs; only 2 `javax.*` references remain, and one of those — `javax.sql.DataSource` in `PostgresDbConfiguration` — is *correct* because `javax.sql` is part of Java SE and never moved. The other is a stale Javadoc comment.

**Q3. Why is the BOM version (3.5.7) different from the parent version (3.5.14)?**
> I... The Maven parent `spring-boot-starter-parent` is 3.5.14, but I also import `spring-boot-dependencies` as a BOM with the property `springboot.version=3.5.7`. The imported BOM in `dependencyManagement` takes precedence over the parent for resolving transitive versions, so the *effective* Spring Boot version the app runs is 3.5.7. We did this so we could pin the exact tested dependency set independently of the parent POM the platform provides. The honest summary: I led the 2.7→3.x major jump; we've stayed current since, and we're on 3.5.x now.

**Q4. What's the difference between a rolling, blue/green, and canary deploy, and why canary here?**
> I... Rolling replaces pods incrementally but has no automated metric gate or instant rollback. Blue/green switches 100% of traffic at once — fast rollback, but zero partial-exposure signal, so a load-only regression hits everyone simultaneously. Canary shifts a small slice (10%) first, evaluates real production metrics, and ramps only if healthy. For a *framework* migration — where the scariest bugs are subtle, load-dependent, and not caught by unit tests — canary's partial exposure plus Flagger's automatic rollback was the right risk profile. It's also the WCNP/Istio org standard, so I wasn't inventing infrastructure.

### INTERMEDIATE

**Q5. Walk me through how Flagger actually shifts traffic.**
> I... Flagger watches for a new deployment, stands up a `-canary` Deployment alongside the `-primary`, and programs the Istio VirtualService to weight traffic between them. Per my `kitt.yml`, it starts the canary at `stepWeight` 10%, and every `interval` (2 minutes) it runs the analysis: a PromQL query over the Envoy sidecar metric `envoy_cluster_upstream_rq` computing the 5xx rate on the canary cluster over a 2-minute window. If that's ≤ the threshold (1%), it adds another 10% of weight; if it breaches, Flagger automatically rolls the weight back to 0 and aborts. It ramps to `maxWeight` 50%, and once stable there it promotes the canary to become the new primary at 100%. `progressDeadlineSeconds: 600` bounds how long the whole analysis can take before it's considered failed.

**Q6. What was the single biggest cost of the migration?**
> I... The Jakarta namespace break, by volume — it's mechanical but pervasive, touching every servlet/persistence/validation import. But the biggest *risk* cost was Hibernate 6's stricter type handling. Hibernate 5 was lenient about how it mapped PostgreSQL enums and array columns; Hibernate 6 is strict and threw at runtime. We fixed it with `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` on the enum columns in `ParentCompanyMapping` and `@JdbcTypeCode(SqlTypes.ARRAY)` on the `Integer[] store_number` column in `NrtStoreGtinMapping`. That class of bug compiles fine and only blows up at query time, which is exactly why we baked in a full week of stage testing before any production canary.

**Q7. Spring Kafka changed — what did you have to do?**
> I... Spring Kafka 3 removed `ListenableFuture` (and the `addCallback` style) in favor of `java.util.concurrent.CompletableFuture`. In `NrtKafkaProducerServiceImpl` I rewrote the send path to `CompletableFuture<SendResult<String, Message<IacKafkaPayload>>>` with `.thenAccept(...)` for the success log (partition/offset) and `.exceptionally(...)` for the failure path. I used that forced rewrite to make the dual-region failover explicit: on a primary-region send exception, `.exceptionally` invokes `handleFailure(...)` which publishes to the secondary-region template. So a mechanical deprecation became a resilience improvement.

**Q8. The repo has both `spring-boot-starter-webflux` and `spring-boot-starter-tomcat`. Isn't that contradictory?**
> I... It looks odd but it's deliberate. We run on the **servlet (Tomcat) stack** — blocking MVC controllers. We pull in `spring-boot-starter-webflux` purely for the `WebClient`, which is the supported non-deprecated HTTP client for outbound calls to Enterprise Inventory. We then call `.block()` on it because the calling code is synchronous. Having both starters means we must be careful that Spring auto-detects the servlet web application type (it does, because Tomcat + DispatcherServlet are present) rather than starting Netty. If I were doing it greenfield I'd weigh `RestClient` (Spring 6.1+) which gives a WebClient-style fluent API on a blocking transport, removing the WebFlux dependency entirely.

**Q9. What did you change in exception handling for Spring MVC 6?**
> I... Two things. First, the `ResponseEntityExceptionHandler` base methods changed their signatures from `HttpStatus` to `HttpStatusCode`, so my overrides in `NrtiRestExceptionHandler` (e.g. the `handleMethodArgumentNotValid`-style overrides at lines 101, 169, 658) had to use `HttpStatusCode`. Second, Spring 6 introduced `NoResourceFoundException` thrown for unmapped static/resource paths instead of silently 404-ing, so I added an `@ExceptionHandler` for `org.springframework.web.servlet.resource.NoResourceFoundException` (line 807) to keep our error contract consistent and return a proper JSON error body instead of a default container 404.

### DEEP / INTERNALS

**Q10. How did you de-risk a migration where bugs compile fine and only fail at runtime under load?**
> I... Three layers. (1) **Stage soak** — a full week on stage with production-like traffic, which is where the Hibernate enum issue surfaced (it never appears in a unit test with H2/mocks). (2) **Contract tests** — R2C runs our consolidated OpenAPI spec against the deployed stage endpoint with an 80% pass threshold in Active mode, so it fails the pipeline; this catches *semantic* regressions (wrong shape, wrong status) that a 5xx gate would miss. (3) **Canary with an automatic rollback gate** in prod, so even an unknown-unknown that only manifests under real load is bounded to ~10% exposure for ≤2 minutes before Flagger pulls it back.

**Q11. Your canary gate only watches 5xx rate. What regressions would slip past it?**
> I... A great catch and I'd own it. The Flagger gate (`response_code_class=~"5.*"`) catches crashes and 500s, but it would NOT catch: a migration bug that returns a *200 with subtly wrong data* (e.g., a Hibernate mapping that silently truncates the `store_number` array), a *latency* regression that doesn't breach but degrades P99, or an *increase in 4xx* from a validation-annotation behavior change. That's the gap R2C contract tests and Automaton perf tests fill in stage. If I were hardening this, I'd add a `request-duration` P99 metric and a non-2xx-rate metric to the Flagger analysis, and a Dynatrace SLO gate, so the canary itself defends against semantic and latency drift, not just hard failures.

**Q12. Java 11→17: which language/JVM changes actually mattered to you?**
> I... Practically: `.toList()` on streams (returns an unmodifiable list, replacing `Collectors.toList()`), records and sealed types as options for DTOs, pattern-matching `instanceof`, and text blocks for the embedded SQL/JSON. On the JVM side, G1 remained the default but with better defaults, and the deprecations mattered for our dependencies more than our code — e.g. the `SecurityManager` deprecation-for-removal forced some libraries to update. Honestly, for *this* service the Java 17 step was the *low*-risk half; the Spring Boot 3 step carried almost all the breaking-change risk. I'm careful not to oversell the language features — we adopted `.toList()` opportunistically (14 call sites) but there are still 19 `Collectors.toList()` left, so it was a partial cleanup, not a sweeping rewrite.

**Q13. Why not use OpenRewrite or the Spring Boot migrator for the javax→jakarta sweep?**
> I... OpenRewrite has a `org.openrewrite.java.migrate.jakarta` recipe and Spring's own migrator that automate the import rename. For a sweep this mechanical, that's the right tool and I'd reach for it first today — it removes human error on 149 imports. We did much of it with careful IDE-assisted refactoring plus tests, which is more error-prone. The reason it still went cleanly is the *verification* layer (contract tests + stage soak + canary), not the edit mechanism. So my honest "what I'd do differently" is: lead with OpenRewrite for the mechanical 80%, then hand-handle the behavior-changing 20% (Hibernate types, Kafka futures, MVC exception signatures).

**Q14. The `DataSourceAutoConfiguration` is excluded. Did the migration affect datasource wiring?**
> I... We exclude `DataSourceAutoConfiguration` in `NrtiApiApplication` and build the `DataSource`/`EntityManagerFactory` manually in `PostgresDbConfiguration` using Walmart's `PostgreSQLUtil` + CCM2 config (`POSTGRESQL-DB-PROVIDER`). The migration didn't change *that* wiring, but it's relevant because the manual `LocalContainerEntityManagerFactoryBean` + `HibernateJpaVendorAdapter` is exactly where Hibernate 6 took effect — the JPA provider version moved under us via the BOM, and our entities had to satisfy the stricter Hibernate 6 typing. Note the `@ConditionalOnMissingBean(DataSource.class)` and `@Profile("!test")` guards so integration tests can supply their own datasource.

**Q15. Where is inbound authentication, and why didn't the migration touch Spring Security?**
> I... There's no Spring Security in this service — and that's intentional, not an omission. Inbound request signing (the WM_SEC.* headers) is verified at the Walmart API gateway in front of us. In-process, our "security" is a custom `OncePerRequestFilter` — `RequestFilter` — that validates `wm_consumer.id` (presence, sanitization, exact length) and throws `NrtiUnauthorizedException` → 401, plus `NrtiApiInterceptor` for supplier-context validation, plus `XssFilter`/`NrtCorsFilter`. So the Spring Security 5→6 breaking change (`WebSecurityConfigurerAdapter` → `SecurityFilterChain`) simply didn't apply to us; our servlet-API migration cost was in the filters and the `XssRequestWrapper`, all moved from `javax.servlet` to `jakarta.servlet`.

### SCENARIO / "what if"

**Q16. What if the canary breached the 5xx gate at 30%?**
> I... Flagger automatically rolls the canary weight to 0 and aborts the promotion — no human action needed — so within one 2-minute analysis window we're back to 100% on the old primary. Then it's a normal incident: pull the canary's Dynatrace traces and logs to root-cause, fix forward, redeploy. Because `prod` also has `rollbackOnError: true` at the KITT level, a deploy-time failure (not just a metric breach) also rolls back. The old primary pods stay up the whole time, so there's no cold-start penalty on rollback.

**Q17. What if a bug only appears at 100%, after promotion — no canary left to catch it?**
> I... That's the residual risk canary can't fully eliminate, which is why we keep the previous version deployable for a rollback window and monitor post-promotion (Dynatrace + the golden-signal Strati gate). If something surfaces at 100%, we redeploy the prior image — which itself goes through canary — or, for a true emergency, KITT can roll back the Deployment to the last good ReplicaSet. The deeper fix is better pre-prod load coverage so 100%-only bugs are vanishingly rare; our Automaton perf test in stage exists for exactly this.

**Q18. Suppose Hibernate 6 silently changed a query result instead of throwing. How would you have caught it?**
> I... A silent semantic change is the worst case and the 5xx gate is blind to it. My defense is the R2C contract suite running against stage — it asserts response shape and values per the OpenAPI spec, so a truncated array or a dropped field fails the pipeline before prod. For data-correctness specifically, I'd also lean on the Strati transaction logs and the audit pipeline (every API call is logged to Kafka→GCS), which lets us diff pre/post-migration responses for the same inputs. If I'm honest, I'd want a golden-dataset regression test comparing SB2.7 vs SB3 responses byte-for-byte during the stage soak — that's the gap I'd close.

**Q19. The PromQL gate references a `-canary` cluster. What if Istio metrics weren't flowing?**
> I... Then the analysis has no data and Flagger treats missing metrics conservatively — it won't promote on absent data, and `progressDeadlineSeconds: 600` will eventually fail the rollout rather than promote blindly. Operationally we validate metrics are flowing in stage first (same Istio sidecar, `sidecar.istio.io/inject: "true"` in the pod annotations), and the `enable-springboot-metrics` + `goldensignal-strati` profiles plus the actuator `/actuator/prometheus` endpoint (whitelisted in `kitt.yml`) ensure the scrape targets exist before we ever canary in prod.

**Q20. If you had 10x the traffic, what changes about this migration?**
> I... The migration mechanics are the same, but the canary economics change. At 10x, a 10% canary is a lot of absolute requests, so I'd (a) shorten the early steps or use a smaller initial weight with a tighter interval to limit blast radius, (b) add a latency P99 and error-budget-burn gate (not just raw 5xx) because at scale a 0.5% regression is a real incident, and (c) make sure HPA headroom is real — at 10x, the canary's cold JVM (Java 17 JIT warm-up, G1 region sizing) matters, so I'd pre-warm or raise the canary replica count. I'd also seriously evaluate `RestClient` to drop the WebFlux/`.block()` thread-per-request cost under high concurrency.

### BEHAVIORAL / LEADERSHIP

**Q21. What does "Led" mean here — what did you personally do?**
> I... I owned the migration end-to-end: scoped the breaking-change inventory (Jakarta, Hibernate 6, Spring Kafka 3, MVC 6 exceptions), sequenced it as a single coordinated SB2.7→3 + Java 11→17 cut, drove the BOM-first upgrade, wrote/reviewed the entity and Kafka-producer changes, set up the stage soak and the contract/perf/resiliency gates, configured the Flagger canary in `kitt.yml`, and ran the production rollout watching the gates. "Led" also means I made the call to *not* go reactive and to *not* introduce Spring Security where the gateway already handles auth — keeping the migration scoped.

**Q22. How did you get "zero customer-impacting issues" — luck or process?**
> I... Process. The number isn't "no bugs" — we caught the Hibernate enum bug in stage. It's "no bug reached a customer," which is what the staged pipeline + canary buys you: bugs are caught in stage, or bounded to a tiny traffic slice for ≤2 minutes by an automatic gate in prod. I'd frame it honestly: the headline outcome is a property of the *rollout design*, not a claim that the code was perfect on the first commit.

**Q23. Biggest mistake or thing you'd redo?**
> I... Two. First, I'd lead the mechanical Jakarta sweep with OpenRewrite instead of IDE refactoring — less human error on 149 imports. Second, I'd harden the canary gate before the rollout, not after — adding P99 latency and non-2xx-rate metrics, because the 5xx-only gate has a real blind spot for semantic regressions. The migration succeeded because of the surrounding verification, and I'd rather the *gate itself* be that robust.

---

## 5. Defending the numbers

| Metric in the line | How it's measured / where it comes from | How to justify if pushed |
|---|---|---|
| **"2.7 to 3.2"** | `pom.xml`: parent 3.5.14, BOM `springboot.version=3.5.7`. The "3.2" is the *initial* SB3 target. | "I led the 2.7→3.x major jump; we landed on 3.2 first and stayed current — the repo is on 3.5.x today. The hard, breaking part is crossing the 2→3 boundary; minor bumps after are routine." Never claim it's exactly 3.2 now. |
| **"Java 11 to 17"** | `pom.xml` `java.version=17`, compiler `<release>17</release>`; `kitt.yml buildType: maven-j17`, profile `springboot-web-jre17`. | Directly verifiable. Java 17 is the SB3 baseline, so it's non-optional, not a vanity bump. |
| **"Flagger canary releases (10% to 100%)"** | `kitt.yml` `global.flagger.canaryAnalysis`: `stepWeight: 10`, `maxWeight: 50`, `interval: 2m`; promotion to 100% after maxWeight. | Show the YAML. Be precise: ramps in +10% steps to maxWeight 50%, then promotes to 100%. "10% to 100%" describes the full journey from first canary slice to full cutover. |
| **"zero customer-impacting issues"** | The Flagger 5xx gate (`threshold: 1`) never tripped during prod ramp; no customer-reported incident; `rollbackOnError: true` never fired in prod. Stage caught the Hibernate enum bug *before* prod. | "Zero customer impact" = no bug reached a customer, enforced by stage soak + R2C contract gate + automatic canary rollback. Don't claim "zero bugs" — claim "zero *customer-impacting* bugs," which is the rollout design's guarantee. |

**Deriving "1% error gate":** the PromQL in `kitt.yml` literally computes `sum(rate(5xx)) / sum(rate(total)) * 100 > 0` with `threshold: 1`, i.e. a canary 5xx rate above ~1% over a rolling 2-minute window aborts. That's your concrete, defensible definition of "customer-impacting" for the rollout.

---

## 6. HONEST watch-outs (if they open the code)

1. **Resume says "3.2"; code is 3.5.7/3.5.14.** Lead with the correction (Section 0.1). This is the most likely "gotcha."
2. **No Spring Security in the repo.** Don't claim a `WebSecurityConfigurerAdapter → SecurityFilterChain` migration. If you mention Security 5→6 at all, frame it as industry knowledge and immediately say *this service uses gateway auth + servlet filters, so that migration cost was zero for us.* (Section 0.2 / Q15.)
3. **No `RestTemplate` in the repo.** The old prep doc's "RestTemplate→WebClient" challenge did NOT happen here. WebClient was already the client. (Section 0.3.) `grep RestTemplate src/main` = 0.
4. **`.toList()` cleanup is partial:** 14 `.toList()` vs 19 remaining `Collectors.toList()`. Don't claim a sweeping "35 instances replaced." Say "opportunistic cleanup where I touched the code."
5. **Canary gate is 5xx-only.** It will not catch semantic 200-with-wrong-data regressions or P99 latency creep. You rely on R2C contract tests + Automaton perf in stage for those. Own this proactively (Q11) — it's a strong senior-signal admission.
6. **`maxWeight: 50`, not 100, in the analysis phase.** Flagger ramps to 50% then *promotes* to 100%. "10% to 100%" is true end-to-end but be precise if pushed.
7. **Both `webflux` and `tomcat` starters on the classpath** (pom 171-178). Looks contradictory; the answer is "WebClient on a servlet stack, blocking `.block()`." (Q8.)
8. **Inconsistent Kafka failure semantics** post-migration: IAC send failure → `NrtiUnavailableException` (503); DSC send failure → logged-and-swallowed (still 201). This lives in `NrtKafkaProducerServiceImpl`. If they read it, own it as a known smell you'd reconcile.
9. **The `02-spring-boot-3-migration/*.md` prep docs cite a "PR #1312" with "158 files / 145 imports / 42 test files."** Those exact numbers are NOT independently verifiable from the working tree (git log shows CCM/feature commits, not a single labeled migration PR). Treat them as illustrative; the *defensible* counts are: 149 `jakarta.*` refs, 2 residual `javax.*`, 14 `.toList()`. Quote the verifiable ones.
10. **Residual `javax.sql.DataSource` import** in `PostgresDbConfiguration.java:16` is **correct** (Java SE, not Jakarta EE). If an interviewer "catches" it as a missed migration, calmly explain `javax.sql`/`javax.crypto`/`javax.net` are JDK packages that never moved — this is a chance to show you actually understand the boundary, not just ran find-replace.

---

## 7. Follow-up rabbit holes (+ crisp answers)

- **"Why is Hibernate 6 stricter about enums?"** → Hibernate 6 reworked its type system around `JdbcType`/`JavaType` descriptors and `SqlTypes`. Implicit "just map the enum somehow" behavior from Hibernate 5 was removed; you now declare the JDBC SQL type explicitly. `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` tells it to use the native PG enum.
- **"What's `SqlTypes.ARRAY` doing on `store_number`?"** → The authorization column is a PostgreSQL `integer[]`; Hibernate 6 needs the explicit `@JdbcTypeCode(SqlTypes.ARRAY)` to bind a Java `Integer[]` to the native array type. Migration-relevant because Hibernate 5 handled this differently.
- **"Why `interval: 2m` not 1m?"** → Longer windows reduce metric noise (a single transient 5xx in a 1-minute window can spike the ratio); 2 minutes gives a more stable rate estimate before deciding to ramp. Trade-off: slower total rollout.
- **"What is `canaryReplicaPercentage: 50`?"** → How many replicas (relative to primary) Flagger runs for the canary during analysis — enough capacity to serve up to maxWeight without the canary being CPU-starved and falsely tripping the gate.
- **"How does Istio actually split traffic?"** → Flagger writes weights into the Istio `VirtualService`'s `route[].weight`; the Envoy sidecars enforce the split. The gate metric (`envoy_cluster_upstream_rq`) is read straight from those same Envoy sidecars, so the signal and the control plane are consistent.
- **"Did Spring Data JPA 2→3 break repository method signatures?"** → The big one is `CrudRepository` return types (`Optional`/`Iterable` semantics largely stable) and the jakarta-persistence imports in entities; our repositories were query-derivation + `@Query`, which were source-compatible. The behavioral risk was in Hibernate, not the Spring Data layer.
- **"Why keep `springdoc-openapi-ui` 1.7.0 AND 2.3.0 properties in the pom?"** → 1.x is SB2-era and dead; the active one is `springdoc-openapi-starter-webmvc-ui` 2.3.0 (SB3-compatible). The 1.7.0 property (pom line 33) is leftover — flag it as cleanup if asked.
- **"What about the OpenAPI generator — did it need changes?"** → Yes: `useSpringBoot3=true`, `useJakartaEe=true`, `java17=true` in the plugin config (pom 841-842). Without those, generated code emits `javax.*` and won't compile on SB3. The generated `InventoryController` path also produces RFC-7807 `ProblemDetail`, a Spring 6 feature.
- **"If a dependency wasn't Jakarta-ready, what then?"** → BOM-first surfaces it at compile time. For our internal libs (`cp-data-apis-common` 0.0.22, `dv-api-common-libraries` 0.0.61) we depended on Jakarta-ready versions; note `dv-api-common-libraries` is itself still SB2.7/Java 11 (`javax.servlet`) — we consume it as a plain jar via component-scan, and we *exclude* its `spring-boot-starter-webflux` (pom 472-477) so its old reactive starter can't leak into our SB3 app. That cross-version coexistence is a real talking point.

---

## 8. One-paragraph + 30-second verbal pitch

**One paragraph.** I led the migration of `cp-nrti-apis` — our external supplier-facing inventory gateway — from Spring Boot 2.7 / Java 11 to Spring Boot 3 / Java 17, which I sequenced as a single coordinated cut because SB3 requires the Java 17 baseline. The real work was the breaking changes: the Jakarta EE namespace move (servlet, persistence, validation — 149 `jakarta.*` references), Hibernate 6's stricter typing (fixed with `@JdbcTypeCode` for PostgreSQL enums and the `Integer[]` authorization array), Spring Kafka 3 replacing `ListenableFuture` with `CompletableFuture` (which I used to make our dual-region failover explicit), and Spring MVC 6's `HttpStatusCode` and `NoResourceFoundException` changes. I upgraded BOM-first for a coherent dependency set, kept the servlet/Tomcat stack rather than going reactive to scope the risk, soaked it for a week in stage behind R2C contract tests and Automaton perf/RaaS resiliency gates, then rolled it to production as a Flagger canary on WCNP+Istio — +10% steps to 50% with a 2-minute Prometheus/Envoy 5xx gate at a 1% threshold and automatic rollback, promoting to 100% only when healthy. We caught the Hibernate bug in stage; nothing reached a customer.

**30-second verbal.** "I owned a Spring Boot 2.7→3 and Java 11→17 migration on our supplier-facing inventory API. The hard part was the breaking changes — Jakarta namespace, Hibernate 6 strict typing, and Spring Kafka's switch to CompletableFuture — not the version number itself. I upgraded BOM-first, kept the servlet stack to limit risk, validated for a week in stage with contract and perf tests, then rolled out as a Flagger canary on Istio: 10% steps with an automatic 5xx-rate rollback gate, promoting to 100% only when healthy. Zero customer-impacting issues — and to be precise, that's a property of the staged rollout design, since we *did* catch a Hibernate enum bug in stage before it ever reached prod."
