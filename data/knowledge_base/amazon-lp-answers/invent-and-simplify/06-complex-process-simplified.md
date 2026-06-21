# Q: Describe a complex process you simplified.

> **LP**: Invent and Simplify
> **Primary story**: `W2 — Shared Library Adoption`
> **Backup story**: `G10 — Event-gRPC consolidation`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Early last year at Walmart, Splunk was being decommissioned company-wide and suppliers (Pepsi, Coca-Cola, Unilever) were asking us to give them visibility into their API calls. Three services on our team — `cp-nrti-apis`, `inventory-status-srv`, and the DSD notification service — each started writing their own audit-logging code. Same servlet filter shape. Same async sender. Slightly different. I sat in three different design reviews and watched three teams solve the same problem three different ways.

### Task

Nobody asked me to fix this — my own service was building its version too. But the duplication was obvious. I proposed a shared library.

### Action

I met each team lead one-on-one. The conversations were the actual work — "what endpoints do you audit, do you need response bodies, what's your latency SLA". I found about 80 percent was identical: capture request body, capture response body, send to a publisher async. The 20 percent that differed — endpoint filtering, response-body capture toggle, custom headers — I made configurable via CCM (Walmart's runtime config system).

I built `dv-api-common-libraries` as a Spring Boot starter JAR. One Maven dependency. The auto-configuration picks up `LoggingFilter` (a `@Component` with `@Order(LOWEST_PRECEDENCE)` so it runs after security filters), wires up `AuditLogService` with `@Async`, and reads CCM config at runtime. Consumers add the dependency and a CCM block. No code.

The filter uses `ContentCachingRequestWrapper` so the controller still sees the request body — HTTP streams can only be read once. The async sender uses a bounded thread pool — 6 core, 10 max, 100 queue — and catches every exception so audit failures never break the API. A senior engineer challenged my queue size of 100; he was right that silent drops were a risk, so I added Prometheus metrics for rejected tasks and a WARN log at 80 percent capacity.

I personally helped each team integrate — paired on their PR, ran a brown-bag demo, wrote a migration guide.

### Result

Three teams adopted within a month. Integration time dropped from two weeks to one day. The library is on version 0.0.54 today across both JDK 11 and 17. The CCM-config approach meant teams enable response-body capture per endpoint without a redeploy. The 80 percent warning has fired once — caught a downstream slowdown before it became an outage.

---

## Technical depth — if they probe

- **`@Order(LOWEST_PRECEDENCE)`**: runs after security filters so we capture the final request/response state, including auth failures.
- **`ContentCachingRequestWrapper` + `ContentCachingResponseWrapper`**: HTTP streams are single-read. Wrapper caches the bytes so both the filter and controller can read them. Critical: call `copyBodyToResponse()` after filter logic — without it the client gets an empty response.
- **Thread pool (6/10/100)**: 100 req/sec × ~50ms per audit = 5 threads needed; 6 core gives headroom, 10 max handles spikes, 100 queue absorbs bursts. At 2KB per payload that's 200KB of memory.
- **CCM (Cloud Config Management)**: Walmart's runtime config. Endpoint regex and response-body toggle live there. No redeploy needed to add an endpoint.
- **WebClient over RestTemplate**: RestTemplate is deprecated in Spring 6. WebClient with `.block()` gives synchronous behaviour with modern resource handling.

---

## Likely follow-ups

**Q: How did you get teams to adopt without management mandate?**
> I went to them, not the other way around. Asked what they actually needed, made the 20 percent that was different configurable, paired on each integration PR. Once team #1 saw integration drop from two weeks to one day, team #2 came to me. Team #3 never needed a pitch.

**Q: Why a library and not a sidecar?**
> Sidecars work at the network layer — they don't know which endpoint was called semantically or which supplier authenticated. We needed application context: consumer ID, endpoint name, error message. That lives in the application, not the network.

**Q: What happens if the audit publisher is down?**
> API stays up. We catch every exception in `AuditLogService` and log them. The thread-pool queue absorbs brief outages. For longer outages we lose audit data — accepted trade-off. Audit is best-effort, API responses are not.

**Q: What was the hardest part of getting adoption?**
> The 20 percent of differences. One team wanted response bodies, another didn't (responses were 100KB+ and would 10x storage). Making that a per-team CCM flag was the unlock — three teams could use one library without fighting over defaults.

**Q: What would you do differently?**
> Publish directly to Kafka from the library instead of going through an HTTP publisher service. Removes a network hop. We didn't do this originally because we didn't want every consuming service to take a Kafka dependency. Now that teams are mature with Kafka, the publisher service is just a hop.

---

## What NOT to say

- Don't claim "I migrated every team" — three teams adopted. Other teams are on different stacks.
- Don't pitch the queue size as obviously right — a senior engineer challenged it and was correct. Be honest about the monitoring I added in response.

---

## Backup story (if asked for another)

At GCC, Event-gRPC had grown 60+ event types — Branch, WebEngage, Vidooly, Shopify — each with its own HTTP endpoint. I consolidated them onto one gRPC `EventService.dispatch()` with protobuf-typed events. Same wire protocol, pluggable per-type sinkers, dead-letter routing per queue. Adding a new event source dropped from three days to about an hour. HTTP endpoints stayed alive as legacy adapters.
