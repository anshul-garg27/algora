# Q: Tell me about a time when you saw a project that was not meeting your standards.

> **LP**: Insist on the Highest Standards (hybrid)
> **Primary story**: `W10 — Observability Stack`
> **Backup story**: `P3 — Test Coverage Program`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Mid-2024 at Walmart Data Ventures. Our service portfolio had grown to six Spring Boot services serving supplier-facing APIs. Each service had its own Grafana dashboard, but they were inconsistent. Some had P99 latency, some didn't. None had error-rate-by-endpoint. The 99.9 percent availability SLA we'd written down on paper had no automated check behind it.

### Task

Bring observability across the six services up to a real production standard. Nobody asked me to do this — it was just visibly missing.

### Action

I started by writing down what "observable" actually meant for these services. RED metrics (Rate, Errors, Duration) per endpoint. Saturation metrics — JVM heap, thread pool depth, DB connection pool. Distributed tracing across the audit-publisher hop. Alerts wired to PagerDuty with sane thresholds, not just "CPU above 80."

Then I built it on `cp-nrti-apis` first as a reference. Micrometer for metrics, OpenTelemetry for traces, structured JSON logs with `traceId` and `requestId`. Created a Grafana dashboard with seven panels — RED per endpoint, JVM, DB pool, async queue depth, audit dispatch errors, downstream API health, error rate by status code.

Wrote the alert YAMLs to match. Critical pages at error rate above 1 percent for 5 minutes, warning at 0.5 percent. Tied them to a PagerDuty service with on-call rotation.

Took the whole thing to the team as a Confluence page — "this is what I'm proposing as our SLA template." Two engineers pushed back on alert thresholds — too tight for their lower-traffic services. I made the thresholds CCM-driven so each service tunes its own.

Rolled it out service by service. I personally migrated three of the six; the other three were owned by senior engineers who picked it up once they saw the dashboards.

### Result

Six services on one standard within two months. The 99.9 percent SLA went from a number on a wiki page to a number with an automated burn-rate alert. We caught two issues in the next quarter that would've been silent before — a slow JDBC connection leak in inventory-status-srv and a thread-pool exhaustion in audit-publisher. The dashboard template is now the default for new services on the team.

---

## Technical depth — if they probe

- **RED method**: Rate (req/sec), Errors (5xx rate), Duration (P50/P95/P99). Per endpoint, not just service-wide. Service-wide averages hide the bad endpoint.
- **Burn-rate alerts vs threshold alerts**: For SLA, burn-rate is better. "We're burning the error budget 14x faster than allowed" catches degradation before threshold alerts fire.
- **Tracing**: OpenTelemetry SDK, B3 headers propagated through the audit publisher and the downstream EI API. Jaeger backend, retention 7 days.
- **CCM-driven thresholds**: One alert YAML, six service-specific value overrides. Each team owns their own thresholds.

---

## Likely follow-ups

**Q: Why did nobody do this before?**
> Each service was owned, but the cross-service standard wasn't. Everyone optimized for their own dashboard. The org-level view didn't exist because it wasn't anyone's job. I made it mine.

**Q: How did you get buy-in?**
> Showed, didn't tell. Built the reference on `cp-nrti-apis`, opened the dashboard in a team sync. "This is what our service looks like now. Want yours to look like this?" Three of the six said yes immediately. The other three came in over the next month.

**Q: What did the two issues you caught look like?**
> JDBC connection leak — DB pool saturation alert fired on a Saturday afternoon. We caught it before it cascaded to 5xx. Thread-pool exhaustion — async queue depth alert at 80 percent, traced to a downstream timeout that had silently jumped from 200ms to 4 seconds.

**Q: Did this slow down feature work?**
> First three weeks, yes — I spent maybe 30 percent of my time on this. After the template was solid, adoption was a few hours per service. The follow-up cost was almost nothing.

---

## What NOT to say

- "Their dashboards were bad" — frame it as a missing standard, not blame.
- Don't oversell — six services isn't a hundred. Right-size the impact.
- "I built it all" — three services I migrated personally; the others copied the template.

---

## Backup story (if asked for another)

At PayU, my team's test coverage was around 40 percent. Production bugs traced back to untested paths in the disbursement code. I introduced a 60 percent minimum gate on the CI, wrote example tests for the disbursement flow as a template, and held two pairing sessions with the team. Coverage hit 72 percent in six weeks; the bug rate per release dropped noticeably the next quarter.
