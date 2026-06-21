# 16 — Deep Fundamentals: Concurrency, Annotations & Spring Boot 3 Internals

> **Purpose:** The "why does it actually work under the hood" layer for the **audit logging** and **Spring Boot 3 migration** bullets. This is the stuff a strong interviewer drills *after* you've explained the architecture: thread models, how `@Async`/`@Transactional`/`@Cacheable` actually fire, the proxy machinery, ThreadLocal propagation, `CompletableFuture` composition, and what *really* breaks in a 2.7→3 jump. **Every claim cites a real path/class/method/line** in `cp-nrti-apis`, `audit-api-logs-srv`, or `dv-api-common-libraries`.
>
> **One framing rule that drives this whole doc:** there are **TWO completely different async models** in this stack, and they must never be merged. (A) the **common-lib in-process audit capture** (`@Async` + a *bounded* `ThreadPoolTaskExecutor`) and (B) the **audit-api-logs-srv hand-off** (a plain `Executors.newCachedThreadPool()`, *unbounded*, no `@Async` at all). Most candidates describe one and assume the other behaves the same. They behave oppositely under saturation.

---

## PART 1 — CONCURRENCY (how requests actually run)

### 1.1 The thread-per-request model (Tomcat) + the Connect worker model (sink)

**Producer side — Tomcat servlet stack.** `cp-nrti-apis` and `audit-api-logs-srv` run on **embedded Tomcat** (servlet stack), even though `cp-nrti` *also* pulls `spring-boot-starter-webflux` (`pom.xml:171-178` has **both** `spring-boot-starter-webflux` *and* `spring-boot-starter-tomcat`). WebFlux is present only to get a reactive `WebClient`; the runtime is still blocking Tomcat. That means:

- Tomcat has a worker pool (default `server.tomcat.threads.max=200`). Each HTTP request is bound to **one** worker thread for its entire lifecycle: filter chain → controller → service → DB/Kafka → response.
- That thread is **blocked** the whole time. A `.block()` on a `WebClient` (`HttpServiceImpl.executeHttpRequest:94`) or a `.join()` on a Kafka future (`NrtKafkaProducerServiceImpl.publishIacKafkaMessage:89`) holds the Tomcat thread idle-but-occupied.
- **Capacity ≈ pool size ÷ avg request time** (Little's Law). 200 threads × 100 ms ≈ 2,000 req/s. If a downstream slows requests to 1 s, you collapse to ~200 req/s, then the accept queue backs up → 503s.

**Sink side — Kafka Connect worker threads (not Spring).** The `audit-api-logs-gcs-sink` is **not** a Spring Boot app — it's a Lenses `GCPStorageSinkConnector` running on Kafka Connect. There the unit of concurrency is **tasks**, not request threads: each connector instance is `tasks.max=1`, and there are **three** connector instances (US permissive catch-all, `-ca` strict, `-mx` strict) → 3 consumer tasks → the topic is read **3×** (read amplification). This is a different concurrency primitive worth naming so you don't accidentally describe the sink as "more Tomcat threads."

**Why this matters for YOUR code (the killer follow-up):**

```java
// cp-nrti-apis/.../services/impl/NrtKafkaProducerServiceImpl.java:84-89  (IAC path)
.exceptionally(ex -> {
    log.warn("Failed to Publish Iac Event ... trying in Secondary region", ex.getMessage());
    handleFailure(iacTopicName, iacKafkaMessage, messageId).join();  // re-send to secondary
    return null;
}).join();                                                            // <-- blocks the Tomcat thread
```

The outer `.join()` (line 89) runs **on the Tomcat worker thread**. If the primary broker is unhealthy, that thread is held until the producer's send future completes exceptionally — and *how long that takes* is governed by the producer retry budget (see §1.4a), not by a single timeout. Under load, threads get consumed → pool exhaustion → cascading 503s. The same mechanism that gives you "synchronous 503 on failure" is what couples HTTP availability to Kafka health.

The **EI read** has the same shape: `HttpServiceImpl.executeHttpRequest` is a reactive `WebClient` chain with `.timeout(Duration.ofSeconds(10))` + `Retry.backoff(3, 100ms, maxBackoff 2s)` (`HttpServiceImpl.java:80-82`) terminated by `.block()` (line 94). You pay the reactive machinery cost but still occupy a blocking Tomcat thread for up to ~10 s + retry backoff — worst of both worlds.

**The senior fix to say:** bulkhead (a dedicated executor for the Kafka publish so a slow broker can't starve request threads), a circuit breaker (Resilience4j) to fail fast when the broker is unhealthy, and a bounded `future.orTimeout(2, SECONDS)` so a black-hole send can't pin a request thread for the full retry budget. (And on the sink: `tasks.max=1 ×3` is a deliberate isolation choice but it triples read load — I'd consolidate the country filtering into one connector with more tasks if throughput became a problem.)

### 1.2 Two async models — keep them SEPARATE (this is the section interviewers reward)

#### Model A — common-lib in-process audit capture (`@Async`, **bounded** pool)

In `dv-api-common-libraries`, the audit log is sent off-thread via `@Async`:

```java
// dv-api-common-libraries/.../filters/LoggingFilter.java:111  (REQUEST thread)
auditLogService.sendAuditLogRequest(auditLogPayload, auditLoggingConfig);  // cross-bean call => proxy fires
```

```java
// dv-api-common-libraries/.../services/AuditLogService.java:48-49
@Async
public void sendAuditLogRequest(AuditLogPayload auditLogPayload, AuditLoggingConfig auditLoggingConfig) { ... }
```

```java
// dv-api-common-libraries/.../configs/auditlog/AuditLogAsyncConfig.java:17-26
@Bean
public Executor taskExecutor() {
    ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
    executor.setCorePoolSize(6);
    executor.setMaxPoolSize(10);
    executor.setQueueCapacity(100);
    executor.setThreadNamePrefix("Audit-log-executor-");
    executor.initialize();                  // NOTE: no setRejectedExecutionHandler(...) and no setTaskDecorator(...)
    return executor;
}
```

Mechanically, when `LoggingFilter` calls `auditLogService.sendAuditLogRequest(...)`:
1. `@EnableAsync` (on `AuditLogAsyncConfig:14`) caused an `AsyncAnnotationBeanPostProcessor` to wrap `AuditLogService` in a **proxy** at startup. The bean other code autowires is the proxy, not the raw `@Service`.
2. The proxy's interceptor does **not** run the body inline — it packages the invocation as a task and `submit`s it to the `taskExecutor` bean.
3. The **calling (Tomcat) thread returns immediately** — that's the latency win. The signing + WebClient POST runs on an `Audit-log-executor-*` thread.

**Pool growth order (the classic trap, correct for a *bounded* `ThreadPoolTaskExecutor`):** fill **core (6)** → fill **queue (100)** → grow to **max (10)** → only then **reject**. Not core→max→queue. So this pool absorbs a burst of up to 110 in-flight tasks before it rejects anything.

#### Model B — audit-api-logs-srv hand-off (`Executors.newCachedThreadPool()`, **unbounded**)

This is the path the old version of this doc **completely omitted**. There is no `@Async` here at all:

```java
// audit-api-logs-srv/.../controllers/AuditLoggingController.java:56-61
@SneakyThrows @Override
public ResponseEntity<Void> saveApiLog(LoggingApiRequest loggingApiRequest) {
    loggingRequestService.processLoggingRequest(loggingApiRequest);   // returns near-instantly
    return new ResponseEntity<>(HttpStatus.NO_CONTENT);               // HTTP 204 immediately
}
```

```java
// audit-api-logs-srv/.../services/LoggingRequestService.java:34-43
public Boolean processLoggingRequest(LoggingApiRequest loggedRequest) {
    var target = targetedResourcesFactory.getOrDefault("kafkaProducerService", null);
    if (target != null) {
        executorPoolService.executeTaskInThreadPool(
            () -> target.processRequestToTarget(loggedRequest));      // fire-and-forget
    }
    return Boolean.TRUE;
}
```

```java
// audit-api-logs-srv/.../services/ExecutorPoolService.java:10-14
ExecutorService pool = Executors.newCachedThreadPool();    // UNBOUNDED
public void executeTaskInThreadPool(Runnable task){
    pool.execute(task);
}
```

`Executors.newCachedThreadPool()` is a `ThreadPoolExecutor` with `corePoolSize=0`, `maximumPoolSize=Integer.MAX_VALUE`, a `SynchronousQueue`, and a 60 s idle keep-alive. A `SynchronousQueue` has **zero capacity** — every submitted task either hands off to an idle thread or **spawns a brand-new thread**. There is effectively **no back-pressure**: under a burst, the pool creates threads without bound.

#### The comparison table interviewers want

| Dimension | **Model A** common-lib `@Async` (bounded) | **Model B** audit-srv `ExecutorPoolService` (unbounded) |
|---|---|---|
| Engine | `ThreadPoolTaskExecutor` core6/max10/queue100 | `Executors.newCachedThreadPool()` (core0/maxMAX/`SynchronousQueue`) |
| Activation | `@Async` proxy (`AuditLogService:48`) | plain `pool.execute(Runnable)` (`ExecutorPoolService:13`) |
| Back-pressure under burst | queue 100 then **reject** (drop) | **none** — spawns threads until OOM / `OutOfMemoryError: unable to create new native thread` |
| Failure mode | **bounded drop** (audit log lost, request unaffected) | **thread explosion / GC pressure / OOM** that can take the *whole JVM* down |
| Caller coupling | request thread returns instantly | request thread returns instantly (204 at `AuditLoggingController:60`) |
| Failure visibility | internal try/catch logs it (see §1.2a) | `KafkaProducerService.publishMessageToTopic:44-51` swallows the send exception with a log line |

**What to say:** "Both audit paths are fire-and-forget so the audited request never waits, but they fail *oppositely*. The common-lib pool is bounded, so the worst case under a burst is a *dropped* audit log — a `RejectedExecutionException`. The audit-srv pool is `newCachedThreadPool()`, which is unbounded with a synchronous queue, so the worst case is *thread explosion and OOM*. If I owned audit-srv I'd swap that for a bounded `ThreadPoolExecutor` with an explicit rejection policy, because a backed-up Kafka should degrade audit, not kill the JVM."

#### 1.2a Where the exception actually goes (the old doc got this mechanism wrong)

The old version said: "`@Async void` → exception → `AsyncUncaughtExceptionHandler` → audit logs silently dropped under burst." The **conclusion** (logs can be dropped) is right; the **causal chain** is wrong. Two corrections:

1. **The method body can't throw most exceptions to the handler**, because `AuditLogService.sendAuditLogRequest` wraps the entire HTTP call in its own try/catch (`AuditLogService.java:73-78`) catching `ResourceAccessException | SignatureHandleException | HttpMessageNotWritableException | HttpClientErrorException | HttpServerErrorException` and *logging* them. So a normal HTTP failure is handled *inside* the method — it never reaches `AsyncUncaughtExceptionHandler`.
2. **The drop happens at SUBMIT time, on the caller thread.** When the bounded pool is full (6 threads busy + 100 queued), the proxy's `executor.submit(...)` throws `RejectedExecutionException` on the **Tomcat thread**, not inside the `@Async` body. `AsyncUncaughtExceptionHandler` only catches exceptions that *propagate out of a void `@Async` method body* — which here largely can't, because of the internal catch.

So the accurate statement is: "Under burst, the bounded executor rejects the submission with `RejectedExecutionException` thrown on the calling thread; nobody is currently catching that, so the audit log is silently dropped. It is **not** routed through `AsyncUncaughtExceptionHandler`."

#### 1.2b The rejection policy is default-by-omission, not a choice

`AuditLogAsyncConfig:17-26` sets `corePoolSize/maxPoolSize/queueCapacity/threadNamePrefix` and calls `initialize()`. It calls **`setRejectedExecutionHandler(...)` nowhere**. So the policy is the `ThreadPoolTaskExecutor` default, which is `AbortPolicy` (throw `RejectedExecutionException`). Say it precisely: *"AbortPolicy by default, because no rejection handler is configured."* Don't imply someone deliberately chose AbortPolicy.

### 1.3 ThreadLocal propagation — the silent `@Async` killer (the single most impressive point)

Spring stores request-scoped state in **ThreadLocals**:
- `RequestContextHolder` — request attributes. **Real cite:** `NrtBusinessValidatorService.getCurrentRequestUri:217` does `(ServletRequestAttributes) RequestContextHolder.getRequestAttributes()`.
- `SecurityContextHolder` — auth (generic; **note:** this repo has *no* Spring Security, so frame it as the general mechanism, not something we use).
- `MDC` (SLF4J) — trace/correlation IDs.
- The **bound JDBC connection** for an active `@Transactional` (via `TransactionSynchronizationManager`).

**ThreadLocals are bound to the thread.** When `@Async` hops to an `Audit-log-executor-*` thread, those ThreadLocals are gone by default. The crucial safe-vs-unsafe boundary:

- **SAFE (request thread):** `NrtBusinessValidatorService:217` reads `RequestContextHolder` while running **in-request** on the Tomcat thread (the validator is called synchronously in the request path), so the ThreadLocal is populated — it works.
- **UNSAFE (pool thread):** if that exact call were moved into the `@Async` body, `getRequestAttributes()` would return **null**, and any `request.getHeader(...)` would blow up because the servlet request is recycled once the response commits.

**This is precisely why** the audit capture builds the *entire* `AuditLogPayload` **on the request thread** inside `LoggingFilter.doFilterInternal` (the `prepareRequestForAuditLog(...)` call at `LoggingFilter.java:105-108`) and only hands the finished payload across the `@Async` boundary at line 111. Everything ThreadLocal-dependent (the `request`, headers, content-cached body) is read *before* the thread hop. Smart, deliberate design.

**The real current gap to volunteer:** `AuditLogAsyncConfig` installs **no `TaskDecorator`** (`AuditLogAsyncConfig:17-26`). So **MDC trace/correlation IDs are genuinely lost today** on `Audit-log-executor-*` threads — the audit log line emitted inside `sendAuditLogRequest` (`AuditLogService:59`) cannot be correlated by MDC to the originating request. State this as a real gap, not a hypothetical: *"We don't propagate MDC to the audit pool, so I'd add a `TaskDecorator` that snapshots `MDC.getCopyOfContextMap()` on submit and restores it at run-start (and clears in a finally), or use `DelegatingSecurityContextAsyncTaskExecutor` if we ever add security context."*

### 1.4 `CompletableFuture` — the Kafka failover engine (Bullet 3), the REAL code

`KafkaTemplate.send()` returns `CompletableFuture<SendResult<...>>` in spring-kafka 3.x (it was `ListenableFuture` in 2.x — see §3.4). The imports prove it: `NrtKafkaProducerServiceImpl.java:11-12` imports `java.util.concurrent.CompletableFuture` and `CompletionException`, and lines 67/111 type the futures as `CompletableFuture<SendResult<String, Message<...>>>`. The **IAC and DSC paths are asymmetric** — this asymmetry is a real smell worth owning.

**IAC path (business-critical → blocks and reports):**

```java
// NrtKafkaProducerServiceImpl.java:68-92
try {
    iscompletableFuture = kafkaPrimaryTemplate.send(iacKafkaMessage);
} catch (Exception ex) {                       // synchronous send-setup failure
    log.info("Send failure falling into exception and Auditing", ex);
    throw new NrtiUnavailableException();       // -> HTTP 500 (@ResponseStatus INTERNAL_SERVER_ERROR; not 503)
}
try {
    iscompletableFuture
        .thenAccept(iacSendResult -> { /* log partition+offset */ })   // runs on kafka-producer-network-thread
        .exceptionally(ex -> {                                         // primary send failed
            log.warn("... trying in Secondary region", ex.getMessage());
            handleFailure(iacTopicName, iacKafkaMessage, messageId).join();   // re-send to secondary, BLOCK
            return null;
        }).join();                                                     // re-block the Tomcat thread
} catch (CompletionException ex) {
    throw new NrtiUnavailableException();        // -> HTTP 500 on total failure (INTERNAL_SERVER_ERROR; not 503)
}
```

The IAC `handleFailure` **rethrows** so a *secondary* failure re-propagates to the `.join()`:

```java
// NrtKafkaProducerServiceImpl.java:159-175  (IAC overload returns CompletableFuture<Void>)
return kafkaSecondaryTemplate.send(iacKafkaMessage)
    .thenAccept(sendResult -> { /* log secondary success */ })
    .exceptionally(ex -> {
        log.error("Secondary send failed: ...", ...);
        throw new CompletionException(new NrtiUnavailableException());   // line 173: re-propagate
    });
```

So when *both* regions fail, the inner `.join()` (line 87) surfaces a `CompletionException`, the outer `.join()` (line 89) re-throws it, the `catch (CompletionException)` (line 90) maps it to `NrtiUnavailableException` → **HTTP 5xx**. The supplier gets a hard failure and retries → no silent loss of an *acknowledged* event.

**DSC path (fire-and-forget → 201 regardless — the asymmetry):**

```java
// NrtKafkaProducerServiceImpl.java:113-126
dscCompletableFuture
    .thenAccept(dscSendResult -> { /* log success */ })
    .exceptionally(ex -> {
        log.warn("... trying in Secondary region", ex.getMessage());
        handleFailure(dscTopicName, dscKafkaMessage, messageId, messageKey);   // NO .join()
        return null;                                                           // just logs and returns
    });
// NOTE: no outer .join(); the method returns immediately. The DSC handleFailure (line 135-151) only LOGS on secondary failure.
```

There is **no outer `.join()`** on the DSC path and its `handleFailure` (lines 135-151) just logs `.exceptionally`. So the DSC controller returns **HTTP 201 regardless of whether the event reached either region**. That's the real durability asymmetry the canon calls out: IAC is "send synchronously, report 5xx on failure"; DSC is "fire-and-forget, optimistically 201." If I owned it I'd make DSC at least record a failure metric / DLQ, because right now a total DSC outage is invisible to the caller.

**The deep mechanics (keep these — they're correct and valuable):**
- The future completes on a **`kafka-producer-network-thread`**, NOT the Tomcat thread. So `.thenAccept`/`.exceptionally` callbacks run on that I/O thread.
- `.exceptionally` is the functional equivalent of `catch` — it only fires on completion-exception (send failed/timed out) and lets you substitute a recovery value.
- The outer `.join()` (IAC only) **re-blocks the Tomcat thread** until the chain resolves — that's how an *asynchronous* send becomes a *synchronous* 503. (This is the coupling from §1.1.)
- `.join()` vs `.get()`: `.join()` throws unchecked `CompletionException`; `.get()` throws checked `ExecutionException` + `InterruptedException`. The code catches `CompletionException` and maps to `NrtiUnavailableException` — clean, and the reason it can be wrapped in `@SneakyThrows` (§2.6).

**Why `CompletableFuture` here but `@Async` for audit?** Because IAC needs the *result* to choose the HTTP status; you must block-and-report. The audit path (Model A) is fire-and-forget telemetry — `@Async void` is appropriate. Different durability needs → different tools. Great contrast to draw.

#### 1.4a Kafka producer timing — what *actually* bounds the `.join()` hold time

The old doc said the IAC thread is "held until `request.timeout.ms` (300000 = 5 min)." That is **imprecise** and a Kafka-savvy interviewer will pounce. The real picture, using the canonical NRTI config (`acks=all`, `retries=10`, `enable.idempotence=false`, `request.timeout.ms=300000`, `linger.ms=20`, `compression.type=lz4`, `max.request.size=10,000,000` — all from the LUMINATE CCM bundle, *not* the repo):

- **`linger.ms` (20 ms):** how long the producer batches before sending. Tiny here.
- **`request.timeout.ms` (300000 = 5 min):** the timeout for **a single in-flight request/retry attempt** — how long the client waits for the broker to respond to *one* produce request before considering that attempt failed.
- **`retries` (10):** how many times the client re-attempts a *retriable* failure.
- **`delivery.timeout.ms`:** the **real** upper bound on `send()` → future-completion. It caps the *entire* retry loop (batching + all attempts + backoffs) and must be `>= request.timeout.ms + linger.ms`. The send future completes exceptionally when `delivery.timeout.ms` is exhausted, **not** after a single `request.timeout.ms`.

So the worst-case `.join()` hold time is bounded by `delivery.timeout.ms`, with `retries=10` attempts each capped at `request.timeout.ms`. Two failure shapes:

- **Connection refused / no brokers (fast RST):** the TCP layer fails immediately → future fails fast → failover (or 5xx) is **sub-second**. This is the "advertised" failover.
- **Black-hole (SYN accepted, no response):** each attempt burns up to `request.timeout.ms` before failing, retried up to `retries` times, all capped by `delivery.timeout.ms` → the future can take **minutes** to complete exceptionally, and the Tomcat thread is pinned the whole time. This is the dangerous case.

And because `enable.idempotence=false` with `retries=10`, the semantics are **at-least-once** (possible duplicates *and* reordering on retry), **not** exactly-once. The honest mitigation: `future.orTimeout(2, SECONDS)` to bound failover latency independent of `delivery.timeout.ms`, and flip `enable.idempotence=true` (prerequisites `acks=all` + `retries>0` + `max.in.flight<=5` are already met) to kill retry-duplicates and per-partition reordering for free.

### 1.5 ForkJoinPool.commonPool vs a dedicated executor (a subtle `CompletableFuture` gotcha)

When you chain `.thenAccept(...)` **without** an explicit executor, the continuation runs either on the thread that completed the future (here the `kafka-producer-network-thread`) or — for `*Async` variants without an executor arg — on `ForkJoinPool.commonPool()`. The NRTI code uses the **non-`Async`** variants (`.thenAccept`, `.exceptionally`), so the logging callbacks run on the **producer network thread**, which is fine because they only log. The trap to mention: if a callback did real work (a blocking DB call), running it on the shared `kafka-producer-network-thread` would stall the producer's I/O for *all* partitions, and switching to `.thenAcceptAsync(...)` without an executor would silently dump it onto the JVM-wide `commonPool` (sized to CPU-1, shared with parallel streams) — you'd want a *dedicated* bounded executor instead. Naming `commonPool` here shows you understand where async continuations actually land.

### 1.6 Virtual Threads (Java 17 → 21 angle) with the in-repo caveats

`cp-nrti` is on **`spring-boot-starter-parent` 3.5.14 / Java 17** (`pom.xml:8,26`), so virtual threads (Project Loom, GA in Java 21) aren't enabled — but it's the perfect "what would you do next":

- The thread-per-request blocking problem (§1.1) **dissolves** with virtual threads: a blocked `.join()` (`NrtKafkaProducerServiceImpl:89`) or `.block()` (`HttpServiceImpl:94`) parks a cheap *virtual* thread instead of pinning a precious platform thread. Tomcat can carry thousands of concurrent blocking requests.
- Spring Boot **3.2+** supports `spring.threads.virtual.enabled=true` — and since we're already on 3.5.x, this is a *scoped flag flip*, not a rewrite.
- **In-repo caveat #1 (pinning):** virtual threads pin to their carrier when you block inside a `synchronized` block or a native call — defeating the purpose. The `.block()`/`.join()` sites are exactly where you'd audit for pinning.
- **In-repo caveat #2 (both starters present):** `pom.xml:171-178` pulls **both** `spring-boot-starter-webflux` and `spring-boot-starter-tomcat`. Enabling `spring.threads.virtual.enabled` affects the Tomcat side; since `WebClient` is the only thing using webflux and it's already `.block()`ing on Tomcat threads, the change is real but scoped — I'd verify the WebClient connection pool sizing doesn't become the new bottleneck once thread count is effectively unlimited.

---

## PART 2 — HOW ANNOTATIONS ACTUALLY WORK (the proxy machinery)

### 2.1 The big secret: annotations do nothing by themselves *(keep — accurate, well-pitched)*

An annotation is just **metadata** — a marker compiled into the class file. `@Async`, `@Transactional`, `@Cacheable`, `@Component` have zero behavior on their own. Behavior comes from something that **reads** the annotation at runtime:
- **`BeanPostProcessor`s** (e.g. `AsyncAnnotationBeanPostProcessor`, `AnnotationAwareAspectJAutoProxyCreator`) scan beans during context startup and wrap matching ones in **proxies**.
- **`BeanFactoryPostProcessor`s** / `@ComponentScan` find `@Component`/`@Service` classes and register `BeanDefinition`s. (Note: `dv-api-common-libraries` is **not** an auto-configuring starter — no `spring.factories`, no `AutoConfiguration.imports`, no `src/main/resources` — so the consumer must `@ComponentScan com.walmart.dv.*` to even *find* `AuditLogService`/`LoggingFilter` for the post-processors to act on. See §3.5.)

Mental model: **annotation = "please proxy me and add this cross-cutting behavior."**

### 2.2 JDK dynamic proxy vs CGLIB — which one wraps YOUR beans (corrected)

Spring picks the proxy strategy:
- **JDK dynamic proxy** — when the bean implements an interface; the proxy implements the same interface and delegates.
- **CGLIB** — when there's no interface; Spring generates a runtime **subclass** overriding your methods.

**The correction the old doc needed:** Spring Boot's AOP/`@Async` auto-config defaults **`proxyTargetClass=true`**, so even interface-implementing beans get **CGLIB subclass proxies**. Mapped to the real beans:

- **`AuditLogService`** (`AuditLogService.java:33`) is a concrete `@Service` with **no interface** → it is **always CGLIB**, unconditionally. This is the bean that actually carries `@Async`, so the live audit proxy is CGLIB.
- **`KafkaProducerService` implements `TargetedResources`** (`audit-api-logs-srv/.../kafka/KafkaProducerService.java:22`). Even though it has an interface, `proxyTargetClass=true` means it would *still* be CGLIB if it were proxied. (It carries no `@Async`/`@Transactional`, so it isn't actively advised — but the point stands: having an interface does **not** force JDK proxy in Spring Boot.)

**Interview-grade consequences (each tied to a real method):**
- **`final` classes/methods can't be CGLIB-proxied** — you can't subclass `final`. If someone marked `ParentCompanyMappingService.getSupplierMapping` (`:42`) `final`, its `@Cacheable`/`@Transactional` advice would **silently vanish**.
- **`private` methods are never proxied.** `NrtKafkaProducerServiceImpl.handleFailure` (`:135,:159`) is `private` — if you ever annotated it `@Transactional`, nothing would happen.
- **Self-invocation bypasses the proxy** (§2.3 below).

### 2.3 Self-invocation — proved by a REAL cross-bean call site

`@Async`/`@Transactional`/`@Cacheable` only fire when the call **crosses a bean boundary** through the proxy reference. A `this.someAnnotatedMethod()` self-call goes straight to the raw method — the advice never runs.

**Proof that YOUR code is safe (structural, not hypothetical):** the audit `@Async` is triggered by a **cross-bean** call — `LoggingFilter.doFilterInternal:111` calls `auditLogService.sendAuditLogRequest(...)` on an **autowired `AuditLogService`** field (`LoggingFilter.java:54-55`). That autowired reference is the CGLIB proxy, so the boundary is crossed and `@Async` fires. If `AuditLogService` had instead called its own `@Async` method via `this.sendAuditLogRequest(...)`, it would run **synchronously on the Tomcat thread** and you'd lose the whole latency benefit. This is the #1 "why isn't my `@Async` working" trap; cite line 111 as the proof you avoided it.

### 2.4 `@Transactional` + `@Cacheable` proxy ordering (you stack BOTH — high-value)

`ParentCompanyMappingService.getSupplierMapping` carries **both** annotations, stacked:

```java
// cp-nrti-apis/.../services/ParentCompanyMappingService.java:36-42
@Cacheable(value = AppConstants.PARENT_COMPANY_MAPPING_CACHE,
           cacheManager = "parentCompanyMappingCacheManager",
           key = "#consumerId + '_' + @siteIdFilterService.getCurrentSiteId()",
           unless = "#result == null || #result.isEmpty()")
@Transactional(readOnly = true)
public Optional<List<ParentCompanyMapping>> getSupplierMapping(String consumerId) {
    return repository.findByIdConsumerIdAndStatus(UUID.fromString(consumerId), Status.ACTIVE);
}
```

Under the hood there are **two interceptors on one proxy**, and **order matters**:
1. `@EnableCaching` → `CacheInterceptor`. By default caching advice has **higher precedence** (lower order) than transaction advice, so it wraps **outermost**.
2. `@EnableTransactionManagement` → `TransactionInterceptor`, which opens a tx and **binds a JDBC `Connection` to a ThreadLocal** via `TransactionSynchronizationManager`.

So the live invocation order is: **CacheInterceptor → (cache miss) → TransactionInterceptor → method → DB**. On a **cache hit** the `CacheInterceptor` short-circuits and returns the cached value **without ever opening a transaction** — which is exactly what you want for a read-through cache (no pointless DB connection on a hit). This is backed by an in-repo **Caffeine** cache (`pom.xml:284-285`, with `ParentCompanyMappingRepositoryCachingTest` verifying it). The teaching point: *"caching wraps transactions, so a hit costs zero DB connections; if it were reversed you'd open a transaction on every hit."*

`readOnly=true` is a **hint**: Hibernate sets `FlushMode.MANUAL` (skips dirty-checking/flush → faster reads) and the driver/DB may route to a read replica.

**The ThreadLocal tie-in again:** the tx connection lives in a ThreadLocal, so `@Transactional` + `@Async` is dangerous — an `@Async` method does **not** join the caller's transaction; the new thread has no bound connection. Transactions don't cross threads.

### 2.5 Filter order & `OncePerRequestFilter` — richer ordering than before *(keep + extend)*

Both audit/edge filters extend `OncePerRequestFilter`, but their `@Order` values differ and the numeric semantics matter:
- `LoggingFilter` — `@Order(Ordered.LOWEST_PRECEDENCE)` (`LoggingFilter.java:35`).
- `RequestFilter` (cp-nrti) — `@Order(Ordered.LOWEST_PRECEDENCE - 100)` with the comment `// we want this to be invoked before StoreInboundRequestFilter` (`RequestFilter.java:34`).

**Numeric rule:** *lower order value = higher precedence = earlier in the chain.* `LOWEST_PRECEDENCE` is `Integer.MAX_VALUE`; subtracting 100 makes `RequestFilter` *slightly higher* precedence, so it runs **before** `StoreInboundRequestFilter` (auth/consumer-id checks happen before the store-inbound feature gate). `LoggingFilter` sits at the very bottom (`LOWEST_PRECEDENCE`) so it is the **innermost** filter — closest to the controller — which is exactly right for audit: it wraps the response **after** every other filter has run, capturing the final bytes.

Other deep points (all match `LoggingFilter` exactly):
- **Filters are NOT AOP-proxied beans** — they're part of the servlet `FilterChain`, registered via `FilterRegistrationBean`. `@Order` controls chain position, not proxy advice.
- `OncePerRequestFilter` guards against double execution on forwards/includes/**async dispatches** (a request can re-enter the chain on async dispatch; the base class uses a request-attribute flag to run exactly once). Critical for audit correctness — you don't want two audit records per request.
- **Why a Filter and not a `HandlerInterceptor`/`@Aspect`?** Only a Filter sees the **raw `ServletRequest`/`ServletResponse`** early enough to wrap them in `ContentCachingRequestWrapper`/`ContentCachingResponseWrapper` (`LoggingFilter.java:83-86`) so the **read-once** body stream can be re-read via `getContentAsByteArray()` (`:94,:100`). A `HandlerInterceptor` runs inside Spring MVC (too late to swap the wrapper); an `@Aspect` on the controller can't see the raw HTTP bytes.

### 2.6 `@SneakyThrows` (Lombok) — a concrete annotation-processing detail

`NrtKafkaProducerServiceImpl.publishIacKafkaMessage` (`:58`) and `publishDscKafkaMessage` (`:102`) are annotated `@SneakyThrows` (Lombok). At compile time Lombok rewrites the method to wrap the body in a `try/catch (Throwable t) { throw Lombok.sneakyThrow(t); }`, which lets a checked-style exception (here `NrtiUnavailableException`) propagate **without a `throws` clause** and without the interface declaring it. It's an *annotation processor* doing AST rewriting at compile time — a nice contrast to Spring's *runtime* proxy machinery: Lombok changes the bytecode before the JVM ever sees it; Spring wraps the bean at startup. Worth naming when the interviewer asks "how do annotations get behavior" — there are (at least) two mechanisms: compile-time processors and runtime BPP/proxies.

### 2.7 `@ManagedConfiguration` (Strati CCM) — TWO different annotations + the dead-config trap

`@ManagedConfiguration` is **not** a Spring annotation — it's Strati's, and there are **two distinct imports** in play:
- `io.strati.configuration.annotation.ManagedConfiguration` — used in `cp-nrti` (`NrtKafkaProducerServiceImpl.java:9`, `StoreInboundRequestFilter.java:10`, `NrtBusinessValidatorService.java:46`).
- `io.strati.ccm.utils.client.annotation.ManagedConfiguration` — used in `dv-api-common-libraries` (`LoggingFilter.java:11`).

Conceptually both work like Spring's: a Strati post-processor injects a **dynamic proxy** that reads config from the CCM plane **at call time**, so `nrtKafkaCCMConfig.getNrtIacKafkaTopicName()` (`NrtKafkaProducerServiceImpl:63`) returns the *current* value without a redeploy.

**The canon trap to volunteer:** "config is live" is true *only for values the interface actually exposes a getter for*. A producer `acks` declared in a CCM yaml that the `@ManagedConfiguration` interface never reads is **dead config** — it does **not** take effect. So a yaml that *looks* like it sets `acks` can be silently ignored; the effective value is the Kafka client default. This is exactly why the **audit producer's effective `acks` is 1** despite any yaml appearance. Don't claim a config is live unless there's a getter wired to it.

---

## PART 3 — SPRING BOOT 2.7 → 3 / JAVA 11 → 17 MIGRATION INTERNALS

### 3.1 Why it's a *major* version (not a number bump)

SB3 is built on **Spring Framework 6**, requires a **Java 17 baseline**, and moves to **Jakarta EE 9+**. Three independent breaking axes hit at once. **Framing note (per canon):** the résumé says "3.2," but the repo is on `spring-boot-starter-parent` **3.5.14** (`pom.xml:8`) with a `spring-boot-dependencies` **3.5.7** BOM override (`pom.xml:36` `<springboot.version>3.5.7</springboot.version>`, imported at `:75-76`). Frame it honestly: *"I led the 2.7→3.x jump and have kept it current — we're on 3.5.x now, the BOM is pinned to 3.5.7 while the parent is 3.5.14."*

### 3.2 The Jakarta namespace migration (`javax.*` → `jakarta.*`) — proved at import level

The biggest mechanical change. **Why it happened:** Oracle donated Java EE to the Eclipse Foundation but kept the `javax` trademark, so Jakarta EE 9 had to rename **every** `javax.*` package → `jakarta.*`. Not a feature change — a forced rename.

**Proof in YOUR two codebases, at the import line:**
- `dv-api-common-libraries` is still **`javax`**: `LoggingFilter.java:15-18` imports `javax.servlet.FilterChain` / `javax.servlet.ServletException` / `javax.servlet.http.HttpServletRequest` / `HttpServletResponse` (it's SB2.7 / Java 11).
- `cp-nrti-apis` is **`jakarta`**: `RequestFilter.java:11,15-17` imports `jakarta.servlet.ServletException` / `jakarta.servlet.FilterChain` / `jakarta.servlet.http.HttpServletRequest` / `HttpServletResponse`.

**The landmine — how they coexist:** the SB3 consumer pulls the old SB2.7 JAR but **excludes its webflux starter** (`pom.xml:468-478` excludes `spring-boot-starter-webflux` from `dv-api-common-libraries` 0.0.61) and provides its own `WebClient` bean. The two servlet namespaces coexist only because the old JAR's `javax.servlet.Filter` is **not instantiated as a servlet filter** in the SB3 container — if it were, its `javax.servlet.Filter` type wouldn't match the `jakarta.servlet.Filter` the new container expects, and registration would fail. This is the most fragile part of the migration story; be ready for it.

### 3.3 Hibernate 5 → 6 strict typing — the bug you actually caught

Hibernate 6 rewrote its type system to be **strict about JDBC type mapping**. Hibernate 5 loosely mapped enums and Postgres arrays; Hibernate 6 demands the exact JDBC type via `@JdbcTypeCode`. Verified anchors:

```java
// cp-nrti-apis/.../entity/ParentCompanyMapping.java:125-128  AND :133-136
@Column(name = "status", columnDefinition = "status_enum", nullable = false, length = 20)
@Enumerated(EnumType.STRING)
@JdbcTypeCode(SqlTypes.NAMED_ENUM)          // line 127: maps `Status` -> Postgres NATIVE enum `status_enum`
private Status status;

@Column(name = "user_type", columnDefinition = "user_type_enum", nullable = false, length = 20)
@Enumerated(EnumType.STRING)
@JdbcTypeCode(SqlTypes.NAMED_ENUM)          // line 135: maps `UserType` -> Postgres NATIVE enum `user_type_enum`
private UserType userType;
```

```java
// cp-nrti-apis/.../entity/NrtStoreGtinMapping.java:42-45
@JdbcTypeCode(SqlTypes.ARRAY)               // maps Integer[] -> SQL ARRAY column `integer[]`
@Column(name = "store_nbr", columnDefinition = "integer[]")
private Integer[] storeNumber;
```

**Persistence behavior:** `SqlTypes.NAMED_ENUM` binds the enum to the **Postgres native enum type** named in `columnDefinition` (`status_enum`, `user_type_enum`) — *not* an ordinal int and *not* a plain varchar. Note the deliberate pairing with `@Enumerated(EnumType.STRING)`: the Java side serializes by name, and `NAMED_ENUM` tells Hibernate 6 the column is a DB-level enum, so the name must match an existing enum label. Without `@JdbcTypeCode`, Hibernate 6's stricter resolver may bind the wrong JDBC type → wrong/failing reads. `SqlTypes.ARRAY` maps the `Integer[]` to a native `integer[]` column instead of trying to serialize it as a scalar.

**This is the "Hibernate enum bug caught in stage" story:** an enum that mapped fine on Hibernate 5 produced wrong/failing reads under 6 until annotated. The **5xx Flagger canary gate (threshold 1%) wouldn't catch it** — a wrong-but-200 response isn't a 5xx — so **contract/integration tests in stage caught it**. Concrete proof that "no customer-impacting issues" came from *process*, not luck.

### 3.4 Spring Kafka 2.x → 3.x: `ListenableFuture` → `CompletableFuture` (REAL here)

In spring-kafka **2.x**, `KafkaTemplate.send()` returned `ListenableFuture` with a callback style:

```java
// OLD (spring-kafka 2.x) — the signature this code replaced
kafkaTemplate.send(msg).addCallback(
    success -> log.info("sent {}", success.getRecordMetadata().offset()),
    failure -> { /* retry to secondary */ });
```

In **3.x** it returns `CompletableFuture`. The migration artifact is concrete: `NrtKafkaProducerServiceImpl.java:11-12` imports `java.util.concurrent.CompletableFuture` / `CompletionException`, types its futures as `CompletableFuture<SendResult<String, Message<...>>>` (`:67,:111`), and composes with `.thenAccept` / `.exceptionally` / `.join()`. So the failover code **had to be rewritten** from `addCallback(success, failure)` to the functional `CompletableFuture` chain during the migration. The asymmetric IAC/DSC handling (§1.4) lives entirely in that rewritten chain — a great, specific migration artifact to cite.

### 3.5 Is `dv-api-common-libraries` a "starter"? (No — and SB3 makes that concrete)

A real SB3 auto-configuring starter registers config via `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports` (SB3 deprecated the old `spring.factories` mechanism for this). `dv-api-common-libraries` has **no `AutoConfiguration.imports`, no `spring.factories`, and in fact no `src/main/resources`** — it's a plain shared Maven library (in-repo version `0.0.45`, consumed `0.0.61`). So consumers must `@ComponentScan com.walmart.dv.*` and supply their own `WebClient` bean. Frame it honestly: *"It's a shared library that standardizes the audit filter and async config, not a true Spring Boot starter — there's no auto-configuration."*

### 3.6 Other real SB3 breaking changes — clearly demarcated as general knowledge

> The items below are **general SB3 release-notes knowledge** ("have ready"), *not* verified-in-repo artifacts — keep them at a lower altitude than the cited claims above so you don't dilute credibility.

- **`WebSecurityConfigurerAdapter` removed** → `SecurityFilterChain` bean. **NOT in this repo** — there is *no Spring Security*; auth is gateway `WM_SEC.*` headers + custom servlet filters (`RequestFilter`, `XssFilter`, `NrtCorsFilter`). Do **not** claim a Security migration.
- **Trailing-slash matching changed.** SB3/Spring MVC 6 no longer treats `/path` and `/path/` the same by default (`setUseTrailingSlashMatch` removed) — a sneaky post-migration 404 source. (General.)
- **`@ConstructorBinding` no longer needed** on `@ConfigurationProperties` records. (General.)
- **Jakarta Validation:** `javax.validation` → `jakarta.validation` (e.g. `jakarta.validation.constraints.NotEmpty`). (Verified at the namespace level via §3.2; the validation package moved with it.)
- **Java 17 strong encapsulation:** reflective access to JDK internals that only *warned* on Java 11 now **throws** `InaccessibleObjectException` — a common cause of old-library breakage during the jump. Plus you gain sealed classes, records, pattern matching. (General, but the Java-17 baseline is verified at `pom.xml:26`.)

### 3.7 How you'd sequence the migration (the method)

1. **BOM-first:** bump parent/BOM, let it pull aligned versions, fix compile errors **by category** — Jakarta imports first (often automatable with OpenRewrite).
2. **Keep the servlet stack** (don't also flip to WebFlux) to limit blast radius — one variable at a time. (This is why both starters coexist but Tomcat stays the runtime, `pom.xml:171-178`.)
3. **Hibernate 6 typing pass:** annotate enums/arrays with `@JdbcTypeCode` (`ParentCompanyMapping:127,135`, `NrtStoreGtinMapping:42`).
4. **Spring Kafka 3 rewrite:** `ListenableFuture` → `CompletableFuture` (§3.4).
5. **Soak in stage** with contract + perf tests for a week (this is what caught the Hibernate enum bug — §3.3).
6. **Flagger canary** (stepWeight 10 → maxWeight 50 → promote 100; 5xx-rate gate threshold 1%; auto-rollback). Note the gate is **blind to semantic + latency regressions**, which is why stage contract tests, not the canary, are the real safety net.

---

## PART 4 — RAPID-FIRE DEEP Q&A (30+, drill these)

**Q1. Why does the calling thread return instantly on `@Async` but block on `.join()`?**
→ `@Async` submits a task to an executor and returns; `.join()` explicitly waits for a future. Fire-and-forget vs await. Audit uses the former (`AuditLogService:48`); IAC uses the latter (`NrtKafkaProducerServiceImpl:89`).

**Q2. Your `@Async` method is `void`. Where does an exception go — and what really drops the audit log?**
→ The *body* exceptions are caught internally (`AuditLogService:73-78`) so they don't reach `AsyncUncaughtExceptionHandler`. The actual drop is a `RejectedExecutionException` thrown at **submit time on the caller thread** when the bounded pool (6+100) is full — default `AbortPolicy` (set nowhere, so it's the default). Not the uncaught-handler path.

**Q3. Contrast the two audit async pools.**
→ Common-lib: bounded `ThreadPoolTaskExecutor` core6/max10/queue100 → worst case is a *dropped* log. Audit-srv: `Executors.newCachedThreadPool()` (`ExecutorPoolService:10`), unbounded + `SynchronousQueue` → worst case is *thread explosion / OOM*. Opposite failure modes.

**Q4. What's the growth order of a bounded `ThreadPoolExecutor`?**
→ core (6) → queue (100) → grow to max (10) → reject. Not core→max→queue. For `newCachedThreadPool` it's different: core 0, `SynchronousQueue`, so every task spawns a thread if none is idle.

**Q5. If `@Async` and `@Transactional` are on the same method, does the async work run in the caller's transaction?**
→ No. The tx connection is bound to a ThreadLocal; the async thread has no bound connection. You'd start a *new* tx (only if the async method is itself `@Transactional` and called across a proxy boundary).

**Q6. Why CGLIB even though `KafkaProducerService implements TargetedResources`?**
→ Spring Boot sets `proxyTargetClass=true`, so it subclasses the concrete class regardless of interfaces. And `AuditLogService` has *no* interface, so it's always CGLIB.

**Q7. Why can't `@Transactional`/`@Cacheable` work on a `private` or `final` method?**
→ Proxies intercept only overridable methods. `private` isn't visible to the subclass proxy; `final` can't be overridden. E.g. marking `handleFailure` (`NrtKafkaProducerServiceImpl:135`) `@Transactional` would do nothing — it's private.

**Q8. Prove your `@Async` actually fires (self-invocation check).**
→ It's a cross-bean call: `LoggingFilter:111` invokes the autowired proxy `auditLogService.sendAuditLogRequest(...)`. A `this.method()` self-call would bypass the proxy and run synchronously.

**Q9. `@Cacheable` and `@Transactional` are stacked on one method. Which wraps which, and what happens on a cache hit?**
→ Caching has higher precedence by default → `CacheInterceptor` outermost. On a hit it short-circuits and returns the cached value **without opening a transaction** (`ParentCompanyMappingService:36-42`, Caffeine via `pom.xml:284`). If reversed, you'd open a tx on every hit.

**Q10. What ThreadLocals silently disappear across `@Async`?**
→ `RequestContextHolder` request attributes (`NrtBusinessValidatorService:217` reads it *safely* on the request thread), `SecurityContextHolder`, SLF4J `MDC` (trace IDs), and the bound tx connection.

**Q11. Are MDC trace IDs propagated to the audit pool today?**
→ No. `AuditLogAsyncConfig:17-26` installs **no `TaskDecorator`**, so trace/correlation IDs are lost on `Audit-log-executor-*` threads. Fix: a `TaskDecorator` that snapshots/restores `MDC.getCopyOfContextMap()`.

**Q12. Why build the audit payload on the request thread?**
→ Because everything ThreadLocal/servlet-scoped (request, headers, cached body) is only valid there; the servlet request is recycled after the response commits. `LoggingFilter:105-108` builds the payload, `:111` hands the finished object across the boundary.

**Q13. On which thread do `.thenAccept`/`.exceptionally` run in the IAC chain?**
→ The `kafka-producer-network-thread` (the thread that completes the future), since the code uses the non-`Async` variants. Fine because they only log; a blocking callback there would stall producer I/O for all partitions.

**Q14. If you used `.thenAcceptAsync(...)` with no executor, where would it run?**
→ `ForkJoinPool.commonPool()` (CPU-1 size, JVM-wide, shared with parallel streams). For real work you'd pass a dedicated bounded executor instead.

**Q15. What *actually* bounds the IAC `.join()` hold time on a hung broker?**
→ `delivery.timeout.ms` (caps the whole retry loop with `retries=10`), **not** a single `request.timeout.ms`. Connection-refused fails fast (sub-second); black-hole can burn the full budget (minutes). Mitigate with `future.orTimeout(2, SECONDS)`.

**Q16. acks=all vs idempotence — if I have acks=all why can I still get duplicates?**
→ `acks=all` guarantees replication-before-ack; it says nothing about retries. A retry after a lost ack duplicates unless `enable.idempotence=true` (producer-id + sequence numbers dedup retries broker-side). NRTI has idempotence **false** → at-least-once with possible duplicates *and* reordering.

**Q17. What does `enable.idempotence=true` require, and is it free here?**
→ Requires `acks=all`, `retries>0`, `max.in.flight<=5` — **all already met** in NRTI. Flipping it on removes retry-duplicates and per-partition reordering for free.

**Q18. Why is the audit producer's effective `acks` = 1 even if a yaml mentions acks?**
→ The `@ManagedConfiguration` interface never reads that key → dead config. The Kafka client default (`acks=1`) applies. "Live config" only holds for values with a wired getter.

**Q19. Two different `@ManagedConfiguration` annotations — name them.**
→ `io.strati.configuration.annotation.ManagedConfiguration` (cp-nrti, `NrtKafkaProducerServiceImpl:9`) vs `io.strati.ccm.utils.client.annotation.ManagedConfiguration` (common-lib, `LoggingFilter:11`). Different packages, same concept (runtime proxy reads CCM at call time).

**Q20. IAC returns 5xx on failure but DSC returns 201 regardless — why?**
→ IAC `.join()`s the chain and maps `CompletionException` → `NrtiUnavailableException` (`NrtKafkaProducerServiceImpl:89-92`); its `handleFailure` rethrows on secondary failure (`:173`). DSC has **no outer `.join()`** and its `handleFailure` only logs (`:113-126,:135-151`) → 201 even on total failure. A real durability asymmetry/smell.

**Q21. Why a Filter, not a `HandlerInterceptor` or `@Aspect`, for audit?**
→ Only a Filter sees the raw servlet request early enough to wrap it in `ContentCachingRequestWrapper`/`ContentCachingResponseWrapper` (`LoggingFilter:83-86`) so the read-once body can be re-read.

**Q22. Why `@Order(LOWEST_PRECEDENCE)` on the audit filter but `LOWEST_PRECEDENCE - 100` on `RequestFilter`?**
→ Lower value = higher precedence = earlier. `LoggingFilter` (`:35`) is innermost (last in, captures final bytes); `RequestFilter` (`:34`) runs slightly earlier so auth/consumer-id checks precede the store-inbound feature gate.

**Q23. What does `OncePerRequestFilter` protect against?**
→ Double execution on forwards/includes/async dispatches — uses a request-attribute flag to run exactly once. Prevents duplicate audit records.

**Q24. Why are servlet Filters not affected by `proxyTargetClass`?**
→ They're not AOP-advised beans; they're registered in the servlet `FilterChain` via `FilterRegistrationBean`. `@Order` controls chain position, not proxy type.

**Q25. Why `StringSerializer` for the key but Avro/JSON for the value?**
→ The key is a routing/partitioning string (audit: `serviceName/endpoint`; NRTI DSC: `tripId`; NRTI IAC: **null key**, only a `MESSAGE_ID` header). The value is the structured payload needing schema (Avro) or structure (JSON). Keys rarely evolve.

**Q26. `@SneakyThrows` — what does it actually do?**
→ Lombok rewrites the method at **compile time** to wrap the body and rethrow checked exceptions without a `throws` clause. Lets `NrtiUnavailableException` propagate from `publishIacKafkaMessage` (`:58`). Compile-time AST rewrite vs Spring's runtime proxying — two different annotation mechanisms.

**Q27. Java 17 illegal reflective access — why does it break libs that worked on 11?**
→ Java 16+ enforces strong encapsulation; reflective access that only *warned* on 11 now throws `InaccessibleObjectException`. Old libs poking `sun.*`/internal APIs fail. Baseline verified at `pom.xml:26`.

**Q28. Is `dv-api-common-libraries` a Spring Boot starter?**
→ No. No `AutoConfiguration.imports`/`spring.factories`/`src/main/resources`. It's a shared library; consumers must `@ComponentScan com.walmart.dv.*` and provide a `WebClient` bean.

**Q29. How do `javax` and `jakarta` servlet types coexist across the two repos?**
→ The SB3 consumer excludes the old JAR's webflux starter (`pom.xml:468-478`) and never registers the old `javax.servlet.Filter` as a servlet filter, so the `javax`/`jakarta` `Filter` type mismatch never surfaces at runtime.

**Q30. What is the resume "3.2" vs reality?**
→ Reality is parent **3.5.14** (`pom.xml:8`) + BOM **3.5.7** (`:36`). Frame as "led the 2.7→3.x jump, kept it current to 3.5.x."

**Q31. Why does the dead `RestTemplate` import in `AuditHttpServiceImpl` matter?**
→ `AuditHttpServiceImpl.java:15` imports `org.springframework.web.client.RestTemplate` but the class uses reactive `WebClient.block()` (`:59`). A leftover import — a "spot the smell" beat showing the audit HTTP call is actually reactive-on-a-pool-thread (off the request thread, so acceptable).

**Q32. Two `.block()` sites — same risk?**
→ No. `cp-nrti HttpServiceImpl.block()` (`:94`) runs on the **Tomcat request thread** (couples HTTP to EI latency). `common-lib AuditHttpServiceImpl.block()` (`:59`) runs on an `Audit-log-executor-*` **pool thread** (off the request thread) — materially lower risk.

**Q33. What would virtual threads change, and what's the in-repo caveat?**
→ They unpin the `.join()`/`.block()` blocking (§1.6); SB 3.2+ enables via `spring.threads.virtual.enabled`. Caveat: pinning on `synchronized`/native calls, and both webflux+tomcat starters are present (`pom.xml:171-178`) so the change is scoped to the Tomcat side.

---

## PART 5 — The one-paragraph "I know the internals" answer

"At the runtime level both producer services are thread-per-request on Tomcat — even cp-nrti, which pulls webflux only for a `WebClient` — so every handler holds one blocking thread end to end. That's exactly why the IAC Kafka `.join()` (`NrtKafkaProducerServiceImpl:89`) and the EI `WebClient.block()` (`HttpServiceImpl:94`) are a coupling risk, and on a black-hole broker the hold time is bounded by `delivery.timeout.ms` with `retries=10`, not a single `request.timeout.ms` — so I'd `orTimeout(...)` them or move to virtual threads on 3.5.x. There are actually **two** different audit async models: the common-lib in-process capture (`@Async` on a *bounded* `ThreadPoolTaskExecutor`, core6/max10/queue100, so the worst case is a *dropped* log via default AbortPolicy at submit time) and the audit-srv hand-off (`Executors.newCachedThreadPool()` in `ExecutorPoolService`, *unbounded*, so the worst case is *thread explosion*). The capture sidesteps ThreadLocal loss by building the whole payload on the request thread before crossing the `@Async` boundary — though we don't propagate MDC today because there's no `TaskDecorator`. All that 'magic' is just Spring's `BeanPostProcessor`s wrapping beans in **CGLIB** proxies (CGLIB even for `KafkaProducerService` because `proxyTargetClass=true`, and always for `AuditLogService` which has no interface) that read the annotations — which is also why a `final`/`private`/self-invoked method would silently disable `@Async`/`@Transactional`. The SB3 migration was three breaking axes at once — the Jakarta rename (common-lib still `javax`, cp-nrti `jakarta`, coexisting via the webflux exclusion at `pom.xml:468-478`), Hibernate 6 strict typing (the `@JdbcTypeCode(NAMED_ENUM)` at `ParentCompanyMapping:127,135` we added after a stage-caught enum bug), and Spring Kafka's `ListenableFuture` → `CompletableFuture` switch, which is literally why the failover uses `.exceptionally().join()` — and why IAC reports a 5xx but DSC returns 201 regardless, which is the asymmetry I'd fix next."
