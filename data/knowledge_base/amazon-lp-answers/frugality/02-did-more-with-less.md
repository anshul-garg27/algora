# Q: Tell me about a time you did more with less.

> **LP**: Frugality
> **Primary story**: `G7 — Sole Architect (6 services on 5-person team)`
> **Backup story**: `G1 — ClickHouse migration (30% infra cost cut)`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

I joined Good Creator Co. as an SE-I in Feb 2023. The eng team was five people total — three on product, one on infra-and-everything-else, and me. The platform side had six services that needed an owner: Beat (Python scraping engine), Event-gRPC (Go event ingestion), Stir (Airflow + dbt data platform), Coffee (Go REST API), SaaS Gateway (Go API gateway), and a fake-follower ML service on AWS Lambda. The previous platform engineer had left and the codebases were inherited.

There was no DevOps person. No dedicated data engineer. No separate SRE.

### Task

Pick up all six services. Keep them running. Ship new features the product team needed. No new hires planned for at least a year.

### Action

The first thing I did was triage, not code. I spent the first three weeks reading every service top-to-bottom and writing a one-page brief per service — what it does, where it breaks, what's load-bearing. That brief became the team's first real ops runbook. Cost me 15 days of "not shipping anything"; saved me months later when things broke.

Then I worked the constraint, which was always my own time. Three moves:

One — standardise. Every Go service got the same 4-layer pattern (API → Service → Manager → DAO) with generics so I'd never spend brain on "where does this code live." Coffee was already structured this way; I retrofitted the gateway and event-grpc closer to it. New endpoints in Coffee took hours, not days.

Two — pick boring tech. The fake-follower system needed an ML approach. I had no GPU budget and no ML platform. I built a 5-feature heuristic ensemble — Indic script transliteration via `indictrans`, RapidFuzz fuzzy matching, 35K-name Indian database lookup, digit-count heuristics. No deep learning, no model training pipeline, no inference cluster. Ran on AWS Lambda + SQS + Kinesis. Hit our quality bar.

Three — reuse infra. When I needed to move log events off PostgreSQL, I didn't add Kafka or Snowflake — used the RabbitMQ we already had and self-hosted ClickHouse. When I needed a data platform, I built on Airflow we were already running. New tools cost time, not just money.

I also wrote down what I would not do. No Kubernetes (we used self-hosted VMs and systemd). No service mesh. No fancy observability stack — Sentry plus Slack alerts and grep'd logs.

### Result

Six services kept running for the 18 months I was there. Shipped real things on top — the ClickHouse migration (30% infra cost cut), Genre Insights and Keyword Analytics modules in Coffee, the fake-follower service, dbt pipelines in Stir. Zero new platform headcount during that period.

The trick wasn't doing more work — it was refusing the work that didn't matter, and re-using infra we already had.

---

## Technical depth — if they probe

- **4-layer generic pattern in Go**: Same `Service[RES, EX, EN, I]` type signature across modules. Adding a new module is 4 files with one converter pair injected.
- **Heuristic ML over DL**: 5 features, RapidFuzz weighted similarity, 35K-name DB. 50-100ms per record on Lambda. Quality good enough for filtering, not for legal decisions.
- **RabbitMQ + ClickHouse over Kafka + Snowflake**: Both already in production. Operating one less tool is the frugality multiplier.
- **No Kubernetes**: Self-hosted VMs + systemd + bash deploy scripts. K8s for a 5-person team is overhead, not leverage.

---

## Likely follow-ups

**Q: Wasn't this just under-investing in infra?**
> Yes and no. We picked debt deliberately and tracked it. K8s would have been the "responsible" choice; for a 5-person team it would have been a tax. We paid the tax later, when we hired.

**Q: How did you avoid burnout?**
> Strict on what I refused to take on. No 24/7 pager (we had business-hours support with Sentry alerts). No "small favours" from product without scoping. The first 'no' is the one that protects the next six months.

**Q: What if a service had blown up?**
> Beat did, twice. Once Instagram rate-limited us (built a Redis token bucket overnight). Once ClickHouse hit "too many parts" (tuned flush batch size). Sentry caught both fast.

**Q: Did the lack of formal review hurt quality?**
> Probably yes. I made fewer code-review calls than I should have, especially in the first quarter. The code is functional; some of it isn't pretty. Trade I made consciously.

**Q: What would you do differently?**
> Hire one DevOps person earlier and write that case three months in, not twelve. I under-priced my own time.

---

## What NOT to say

- Don't make this sound heroic. The frugality is in the choices to *not* do things.
- Don't trash K8s or Snowflake — they're great at scale, just not here.
- Don't oversell — six services on five people had real downside; be honest.

---

## Backup story (if asked for another)

The ClickHouse migration was the clearest "do more with less" story. PostgreSQL was choking; the team had no warehouse budget. I picked self-hosted ClickHouse, used the RabbitMQ we already had, added log-event consumers to event-grpc instead of a new service, and shipped in 4 weeks. 30% infra cost cut, 5x compression, 2.5x faster queries. Zero new tooling.
