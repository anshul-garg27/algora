# Q: Tell me about a second-order impact of something you built.

> **LP**: Success and Scale Bring Broad Responsibility
> **Primary story**: `W2 — Shared Library as Audit-Logging Standard`
> **Backup story**: `W6 — BigQuery RLS Pattern Across Verticals`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

When I designed the audit-logging shared library at Walmart, the first-order goal was simple — replace Splunk for the Channel Performance services. Twelve services in our team needed audit logging, and each one would have built its own version. I built it once instead. `dv-api-common-libraries`, 696 lines, automatic instrumentation via Spring Servlet Filter.

### Task

Ship the library. Get my team's twelve services onto it. That was the scoped ask.

### Action

I went a little further than the scoped ask, which is where the second-order story starts.

I designed for zero code changes — teams just add a Maven dependency and a CCM config flag. The library auto-wires through Spring's auto-configuration. No subclassing, no annotations on every controller. The path to adoption was 30 minutes per service instead of a sprint.

I also made the payload schema strict. Every audit event carried the same fields — `request_id`, `service_name`, `endpoint_name`, `method`, `response_code`, `trace_id`, plus the body. Same Avro schema across all services. I added R2C contract tests so any service emitting events that drifted from the schema would fail CI.

We hit twelve services in eight weeks. That was the first-order win. Then the second-order effects started showing up.

The first was cross-service trace correlation. Because every service now emitted the same `trace_id` field, an SRE could query "show me everything for trace X" and get the full request path across five services. Before the library, every team had their own log format, and joining across services was hand-stitching. After the library, it was one SQL query against the BigQuery external table.

The second was that the supplier-self-service path got cheaper to extend. When we added new endpoints, suppliers could query them immediately without any per-service onboarding. The shape was already there.

The third — and this surprised me — was that three teams outside Channel Performance picked up the library on their own. The Walmart Platform team promoted it internally. By six months in, twenty-plus services were emitting in the same format, including the international ops services and a couple of returns-processing services.

### Result

First-order: 12 services, ~480 engineer-hours saved (40 hours per team × 12 if they'd each built their own). 99% cost reduction vs Splunk.

Second-order: cross-service trace correlation became possible — that one shows up daily in incident debugging. Supplier-facing endpoints extended with no per-service onboarding. The library became the org-wide standard for supplier audit logs, used by 20+ services across teams I never directly worked with.

Honestly, I didn't plan the second-order effects. I designed for simplicity and consistency, and the broader consequences fell out of those choices. The reusable-by-default mindset is the thing that scales — once a pattern is good enough for one team, it tends to spread if the friction is low.

---

## Technical depth — if they probe

- **Why one schema across all services**: BigQuery external tables on GCS Parquet. One schema means one external table, one query interface, one set of supplier-facing access patterns. Per-service schemas would have been per-service tables — N times the supplier integration work.
- **Why Spring auto-configuration**: Teams don't want to learn new libraries. Auto-configuration means the library "just works" after the dependency is added. The first integration in any new service is under 30 minutes.
- **Why R2C contract tests on the schema**: Schema drift is the silent killer of cross-service correlation. If one team adds a field nobody else knows about, the JOIN breaks. R2C catches drift at PR time.
- **How the platform team found it**: I gave a tech talk in our Data Ventures All Hands. Recording went on the internal video portal. Two teams reached out from there. The All Hands was 30 minutes of effort that drove half the external adoption.

---

## Likely follow-ups

**Q: Did you anticipate any of the second-order effects?**
> Cross-service correlation, yes — that was a design goal. The external-team adoption, no. The supplier-extension cheapness, partially — I'd hoped for it but didn't plan for it.

**Q: What's the negative second-order effect?**
> Library bug surface. When I shipped a 0.0.43 with a serialization bug, it broke audit emission for 18 services at once. I added Flagger canary on library upgrades and a deprecation policy for breaking changes. Shared infra carries shared risk.

**Q: How do you decide what to make reusable?**
> Rule of three. The first time, write it for one service. The second time, copy. The third time, extract. Premature reuse creates wrong abstractions; delayed reuse wastes hours. The library was extracted at service three.

**Q: Would you change anything?**
> Build the schema-evolution story sooner. We're now considering Confluent Schema Registry to handle backward-compatible Avro evolution. I should have planned for it from day one.

---

## What NOT to say

- Don't claim "I built the org standard." Say "it became the org standard." The platform team made it official; I made it adoptable.
- Don't oversell — say "approximately 480 engineer-hours saved" as a back-of-envelope, not a measured number.
- Don't credit yourself for the platform-team promotion — credit the All Hands and the platform-team owner who picked it up.

---

## Backup story (if asked for another)

For W6, the BigQuery RLS pattern I documented for supplier self-service had a clear second-order effect across verticals. I built it for the audit-logs use case — one supplier sees only their own rows. Six months later, the returns-processing team, the DSD events team, and an international ops team all adopted the same policy-tag pattern for their own supplier-facing data. The platform security team made it the recommended approach. Zero supplier-data-leak incidents across all adopters. The first-order win was supplier self-service in one product; the second-order win was a tested security pattern with broad reuse.
