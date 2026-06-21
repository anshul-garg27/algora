# Q: Tell me about a long-term initiative you championed.

> **LP**: Think Big
> **Primary story**: `W2 — Shared Library Org Standard`
> **Backup story**: `W10 — Observability Stack as SLA Template`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Mid-2024. I was on the team building Kafka audit logging for our supplier APIs in cp-nrti-apis. As I drafted the design, I realised — we were one of about a dozen services in Walmart Data Ventures that needed exactly this pattern. If I built audit logging just for cp-nrti-apis, the 11 other teams would each rewrite the same logic. Twelve times the work, twelve times the bugs, twelve times the maintenance.

### Task

I'd been scoped to ship audit for cp-nrti-apis. The bigger play was building it as a shared library that 12 teams could adopt with no code changes — but that meant convincing my own team and 12 other teams to bet on a library that didn't exist yet.

### Action

I started with a design principle — make the library invisible. Engineers don't want to learn another internal library. So integration had to be two lines of pom.xml plus three lines of YAML. Auto-instrumentation via a Spring Filter at `Ordered.HIGHEST_PRECEDENCE` — no code changes in the consuming service. Config-driven via CCM YAML. Safe defaults — opt-in, never opt-out.

The first version landed as `dv-api-common-libraries 0.0.54`. I integrated it into cp-nrti-apis myself to prove the pattern. Wrote a README that was copy-paste examples, not reference docs. Recorded a 5-minute video tutorial. Built a sample Spring Boot app that other teams could clone and run.

Then came the long-term part — adoption. I didn't email teams and walk away. I held Friday office hours for an hour a week. Anyone integrating the library could show up and ask anything. The first three weeks had 11 teams come through. The issues were mostly small — CCM config case sensitivity, dependency conflicts with old `spring-boot-starter-webflux`, executor pool sizing.

I reviewed every integration PR. Not just approved — taught. When `inventory-status-srv` set `auditLogExecutor` to 100 threads, I left a comment with the sizing formula: `(events/sec × latency) × 2`. For their load (2M events/day), 20 threads was sufficient. The engineer changed it and thanked me. That code review became a teaching moment, not a gate.

Six months in, I realised the library had become the org's de facto pattern. Three teams outside Data Ventures asked if they could use it. I added their use cases as test scenarios and bumped the library to support broader configurations.

I kept upgrading it. When CompletableFuture replaced ListenableFuture in Spring Kafka 3, I updated the library and pushed the upgrade across all consumers. When Snyk flagged a transitive CVE, I patched once and propagated through Dependabot PRs in every consuming repo.

### Result

12 teams integrated within 3 weeks. Integration time per team — under 1 hour, against ~40 hours if they'd built custom. Total saved engineering time across the org: roughly 480 hours. Bug rate in audit logging — under 0.1%, versus the 5–10% you'd expect with 12 independent implementations. The library is still the standard 18 months later. The harder lesson — long-term initiatives aren't about the first version. They're about the next 18 months of office hours, code reviews, dependency upgrades, and tactically saying yes when teams want to use the library in ways you didn't design for.

---

## Technical depth — if they probe

- **Auto-instrumentation**: `@Component @Order(Ordered.HIGHEST_PRECEDENCE) public class LoggingFilter implements Filter`. Captures every HTTP request/response. Consumers don't write any code.
- **Config-driven**: CCM YAML — `audit.logging.enabled: true`, plus executor pool sizing and circuit-breaker config. All overridable per environment.
- **Executor sizing formula**: `(events/sec × latency) × 2` for safety margin. For 2M events/day at 50ms latency, that's about 20 threads.
- **Why a shared library, not a sidecar**: 12 services on shared infrastructure, no service mesh. Library is the lowest-friction integration path. A sidecar would have required infra team changes.
- **Library version cadence**: monthly releases for non-breaking changes. Major bumps coordinated with consuming teams via the office hours channel.

---

## Likely follow-ups

**Q: What if a team wanted to fork the library?**
> Happened once. A team needed a Kafka header forwarding pattern I hadn't built in. Instead of letting them fork, I added the feature to the main library — took two days. Forks defeat the purpose.

**Q: How did you handle a team that didn't want to adopt?**
> One team initially declined — they had custom logic they were attached to. I let them be. Six months later they came back when their custom code shipped a real bug we'd already fixed in the library. Adoption can't be forced; it earns trust.

**Q: What was the hardest part of long-term ownership?**
> Saying no. Teams asked for features that would have made the library too generic — every config option you add is one more thing to test, document, and maintain. I declined feature requests when they were one-off needs that could live in the consuming service.

**Q: Would you build it the same way again?**
> Yes, except I'd add Dependabot automation from day one. The first six months of manual dependency upgrade PRs across 12 repos was tedious. Automating it would have saved real time.

---

## What NOT to say

- Don't claim I "mandated" adoption. I made it the easiest path; teams adopted because it was cheaper than building their own.
- Don't oversell the 480-hour saving as money — that's developer hours, not dollar value. The real win was consistency and fewer bugs.
- Don't pretend the library was bug-free. Version 0.0.54 → 0.0.96 over 18 months reflects real fixes, not theoretical perfection.

---

## Backup story (if asked for another)

W10 observability stack at Walmart. I built a Grafana + OpenTelemetry + Dynatrace template for cp-nrti-apis — alert YAML, dashboard JSON, runbook structure. It became the SLA template the team uses for every new service. Same shape as the shared library — build it once well, then maintain it through code review and adoption support over the next year. The long-term part is the maintenance, not the initial build.
