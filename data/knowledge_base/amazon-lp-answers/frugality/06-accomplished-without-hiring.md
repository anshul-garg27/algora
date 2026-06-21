# Q: Tell me about a time you accomplished something without hiring more people.

> **LP**: Frugality
> **Primary story**: `G7 — 6 services, 1 SE-I, owned everything`
> **Backup story**: `W2 — Shared library let 3 teams stop re-implementing`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

At Good Creator Co. I was the sole platform engineer. Five-person eng team total, three on product, one on infra, me on platform. The platform side had six services that needed to keep running and keep evolving: Beat (Python scraping), Event-gRPC (Go ingestion), Stir (Airflow + dbt), Coffee (Go REST), SaaS Gateway (Go API gateway), and a fake-follower ML service on Lambda. I asked for a DevOps hire twice in my first two months. Both times the answer was no — runway didn't allow it.

### Task

Run all six services. Ship the new features the product team needed for the roadmap — Genre Insights, Keyword Analytics, fake-follower detection, a ClickHouse migration. Without additional headcount for at least a year.

### Action

The win condition was "don't try to be a 3-person team in one body." Three deliberate moves:

One — standardise so all six services felt like one codebase. Coffee already had a 4-layer pattern (API → Service → Manager → DAO) with Go generics. I extended the same pattern to the gateway and to event-grpc. Every new module — Genre Insights, Keyword Analytics, Campaign Profiles — was the same four files with one converter pair. Adding endpoints stopped costing brain cycles.

Two — say no to ops complexity. No Kubernetes, no service mesh, no fancy observability stack. systemd unit files, bash deploy scripts checked into each repo, Sentry for errors, Slack for alerts, RabbitMQ management UI for messaging health. The whole platform was operable by one person at 2 AM because none of the components were complicated.

Three — push work out, not in. When the ClickHouse migration came up, I picked self-hosted ClickHouse on existing VMs instead of Snowflake or BigQuery — neither would have cost less in money but both would have cost more in operational learning. For the fake-follower ML I built a heuristic ensemble running on Lambda + SQS + Kinesis instead of a model-training pipeline. Each choice traded "best in class" for "ops-free for the team I actually had."

I also wrote a one-page runbook per service in my first month — what it does, top failure modes, how to restart, where the logs are. Cost 15 days; saved hours every month for the rest of my time there.

### Result

18 months. Six services kept running. Two cost-impacting projects shipped — the ClickHouse migration cut infra ~30%, the fake-follower detection unlocked sales conversations we'd been losing. Two product modules — Genre Insights, Keyword Analytics — shipped in Coffee. No new platform headcount during my tenure.

The honest part: this had real costs. Code quality varied. Some of my early bash deploy scripts make me wince now. But not hiring forced choices that turned out to be better than the textbook answers — standardise patterns, refuse ops complexity, push work onto managed services we already paid for.

---

## Technical depth — if they probe

- **Generic 4-layer Go pattern**: `Service[RES, EX, EN, I]` parameterised over response, entry, entity, ID types. Every module compiles type-safe.
- **systemd + bash deploys**: Each repo has `deploy.sh` that does git pull, build, restart service. No CI/CD platform.
- **Lambda for fake-follower**: Zero ops surface. SQS for input, Kinesis for output, ECR for the container image.
- **Airflow for everything batch**: 76 DAGs by the end. Schedules every dbt run, every ClickHouse-to-PG sync, every nightly export.
- **One-page runbook per service**: Markdown in each repo. Most reads are at 2 AM by me; written so future-me can fix things half-asleep.

---

## Likely follow-ups

**Q: Wasn't this risky?**
> Yes. Single point of failure was me. Mitigated by runbooks and by Sentry-driven alerts that pulled the broader eng team in when needed.

**Q: What if you'd left?**
> The two engineers onboarded to Beat and Coffee would have kept things alive for weeks. Anything deeper would have needed a hire — same problem as now, just delayed.

**Q: Did you ever push back harder on the hiring decision?**
> Twice in two months. After that I focused on what I could control. In hindsight I should have built a business case in numbers — hours/week, incidents/month — not just an emotional ask.

**Q: How did you avoid burnout?**
> Strict on ops complexity. The framework I held was — every new system has to be ops-free for me, or I don't ship it. That refused real work but it kept me functional.

**Q: What would you do differently?**
> Write the hiring business case in dollars, not adjectives. Quantify ops hours, opportunity cost, incident frequency. I under-priced my own time for too long.

---

## What NOT to say

- Don't make this heroic. The frugality is in choices to *not* do things.
- Don't pretend ops complexity is bad — at scale it's necessary. For a 5-person team it's tax.
- Don't skip the trade-off. Solo platform ownership has real downside.

---

## Backup story (if asked for another)

At Walmart, three teams were each building their own audit-logging code. Different implementations, different bugs. I built a shared Spring Boot starter — `dv-api-common-libraries` — with the filter, the async dispatcher, and the CCM-driven config. Each team integrated by adding one Maven dependency and a config block. Integration time dropped from 2 weeks to 1 day. Three teams shipped audit without me adding to my own scope.
