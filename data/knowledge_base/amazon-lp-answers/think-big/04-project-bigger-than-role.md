# Q: Tell me about a project you took on that was bigger than your role.

> **LP**: Think Big
> **Primary story**: `G7 — Sole Architect Across 6 Services at SE-I`
> **Backup story**: `G3 — Stir Platform Build`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Late 2023 at Good Creator Co. I was an SDE-1 — 8 months in. Andrey, our team lead and senior engineer, gave notice. He'd been holding the architecture for the backend platform — six services across Go and Python, an Airflow data platform, and an ML pipeline. The team was four engineers. We had a few months of runway with new clients onboarding. Hiring a senior would take three months easily.

### Task

I wasn't formally promoted. But somebody needed to hold the architecture decisions across all six services and keep the platform shippable. I told my manager I'd take it on.

### Action

I started by writing down what I owned. Six services: Beat (Python scraper, 15K lines), Event-gRPC (Go ingestion, 10K lines), Stir (Airflow data platform, 17.5K lines, 76 DAGs), Coffee (Go REST API, 8.5K lines, 40+ endpoints), SaaS Gateway (Go API gateway proxying 13 microservices), and the Fake-Follower ML pipeline (Python on AWS Lambda).

Then I made one rule for myself — no decision in isolation. If a change in Coffee touched ClickHouse schema, I asked how Stir's dbt models would react. If Beat's rate limits changed, I'd check whether Event-gRPC's RabbitMQ queues could absorb the new throughput. The system-level view was the role I had to grow into.

The work itself broke into three buckets.

Bucket one — production stability. I owned every on-call rotation for those services for the first three months. I wrote runbooks because nobody else knew the internals. When something broke, I fixed it and wrote it up so the team could handle it next time.

Bucket two — architectural decisions. I had to defend a few non-obvious calls. RabbitMQ over Kafka — easier ops, our throughput didn't need Kafka's complexity. Self-hosted servers over Kubernetes — six services, four engineers, K8s was overhead we couldn't afford. ClickHouse + Postgres dual database for Coffee — benchmarks showed 30s → 2s on analytics queries. Each of these came up in design reviews and I had to explain why, with numbers.

Bucket three — onboarding. A new junior joined two months in. I wrote a System Interconnectivity doc — every service-to-service connection, every RabbitMQ exchange and queue, every database table relationship. That doc became the team's architecture bible. I walked him through it on a whiteboard.

I made plenty of mistakes. Spent a week trying to make Beat's worker pool more "elegant" before realising the existing `multiprocessing.Process + asyncio.Semaphore` pattern was actually correct for I/O-bound scraping. Learned to read production code patiently before deciding I knew better.

### Result

The platform held. Six services in production, 60K+ lines of code, no major outages during the 15 months I had end-to-end ownership. ClickHouse migration cut log retrieval from 30s to ~12s. Stir cut data freshness from 24 hours to under 1 hour. Coffee + Gateway gave 25% faster API responses. By the time I left, the system-interconnectivity doc and runbooks were what onboarded my replacement. The lesson — when a role opens up that's bigger than your title, you take it by writing things down and being honest about what you don't know yet. Andrey leaving was the moment I stopped being a junior who shipped tasks and started being an engineer who owned systems.

---

## Technical depth — if they probe

- **Six services**: Beat (Python/FastAPI/uvloop), Event-gRPC (Go), Stir (Airflow/dbt/Python), Coffee (Go/Chi/GORM), SaaS Gateway (Go/Gin), Fake-Follower (Python/Lambda/ECR).
- **Cross-service decisions I owned**: RabbitMQ vs Kafka (ops simplicity), dual database for Coffee (Postgres OLTP + ClickHouse OLAP), self-hosted over K8s, ECR Lambda for ML (250MB layer limit too small).
- **What I deliberately didn't change**: Beat's worker pool pattern. It looked unidiomatic but was correct for I/O-bound scraping at our scale.
- **Most useful artifact**: System Interconnectivity doc — every queue, exchange, DB relationship, service dependency. Drew it on paper first, then converted to a markdown architecture doc.

---

## Likely follow-ups

**Q: What was the hardest decision in that 15 months?**
> Dual database for Coffee. The senior who left had a single-Postgres plan. I changed it to Postgres + ClickHouse after benchmarking the leaderboard query. The numbers were unambiguous (30s → 2s), but I had to defend it without the senior in the room.

**Q: How did you handle being out of your depth?**
> Asked specific questions, never generic ones. Read official docs before blog posts. Wrote runbooks the day I learned a new failure mode so the next person didn't have to discover it cold.

**Q: When did you delegate?**
> Beat operations to the ops team after about 6 months. Once the rate-limiting and credential rotation systems were stable, ops could handle the day-to-day. I stayed on call for architecture-level issues.

**Q: How did you avoid burning out?**
> Wrote everything down. Every bug, every weird production behaviour, every "next person should know" moment. The doc was the substitute for me being on every call.

---

## What NOT to say

- Don't claim I was "promoted to architect." I wasn't. I took the work because someone had to.
- Don't downplay the team — there were three other engineers. I owned architecture, they owned domain features.
- Don't pretend I made every call right. The Beat refactor week was wasted. The lesson stuck.

---

## Backup story (if asked for another)

Stir data platform build. I was scoped to "replace the cron jobs." I built a full data platform — 76 DAGs, 112 dbt models, three-layer ClickHouse → S3 → Postgres pipeline, five scheduling tiers from 5 minutes to weekly. Cut data freshness 24h → 1h. The build took about three months. That work alone was beyond what an SDE-1 was supposed to scope. The smaller "replace cron" version wouldn't have fixed the customer-facing freshness problem, so going bigger was the right call.
