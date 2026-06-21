# Q: Describe a time you showed ownership of a project or task.

> **LP**: Ownership
> **Primary story**: `G7 — Sole Architect for 6 Services`
> **Backup story**: `W8 — DC Inventory Search API`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

I joined Good Creator Co. in Feb 2023 as an SE-I. By month four, the founders quietly handed me six backend services. We were a four-person engineering team. There was no "tech lead" tag, no senior watching over me. The platform was processing about 10 million data points a day for brand clients like Nike and Pepsi.

### Task

Own those six services end-to-end. Design, code, deploy, debug at 3 AM, plan the next quarter. No one else was going to do it.

### Action

I treated the six services as one product, not six silos. Beat was the Python scraping engine — 73 flows, 150+ workers, FastAPI with uvloop. Event-gRPC was the Go ingestion service — 26 RabbitMQ queues feeding ClickHouse through a buffered sinker pattern. Stir was the data platform — 76 Airflow DAGs, 112 dbt models. Coffee was the REST API. SaaS Gateway was the API gateway in front of 13 microservices. And the fake-follower ML pipeline ran on AWS Lambda.

The hard part wasn't writing code. It was deciding what NOT to do. I built a one-page architecture map showing how data flowed Beat → RabbitMQ → Event-gRPC → ClickHouse → Stir → Postgres → Coffee. Every Monday I picked the one bottleneck holding the platform back that week and fixed it. Some weeks it was Beat's credential rotation. Some weeks it was the dbt incremental models.

I also pushed myself to learn Go properly, because three of the six services were in Go and I'd never written a line before joining. Two weeks on the language, then I shipped my first Event-gRPC PR.

The buffered sinker was the one design I'm most proud of. Per-event writes to ClickHouse were killing throughput. I built a Go channel of 10,000 capacity, batched into groups of 1,000 or flushed every 5 seconds, then single batch INSERT. Cut I/O by 99%.

### Result

The platform ran at 10K events per second sustained, processed 8M images a day through S3, and log retrieval went from 30 seconds to about 12 seconds. About 60,000 lines of production code across Go and Python over 15 months. Looking back, the real lesson was that owning six services taught me what NOT to touch each week. I couldn't optimise everything. I had to pick.

---

## Technical depth — if they probe

- **Buffered sinker pattern**: Go channels as bounded queues with size-or-time flush. 1000 events or 5 seconds, whichever first. Used `sync.Once` for lazy init and a panic-safe goroutine wrapper so one bad event never crashed the consumer.
- **Multiprocessing + asyncio in Beat**: Each flow got dedicated OS processes for GIL isolation. Within each process, asyncio with uvloop and an `asyncio.Semaphore` for concurrency. ~50MB per process × 150 workers = 7.5GB, well within our 32GB boxes.
- **`FOR UPDATE SKIP LOCKED`**: PostgreSQL-based task queue. Atomically selected the next pending row, locked it, skipped already-locked rows. No Celery, no Redis broker — just Postgres we already had.
- **dbt model layering**: 29 staging models for type casting and null handling. 83 mart models grouped by domain. Five scheduling tiers from 5 minutes (post ranker) to weekly aggregations.

---

## Likely follow-ups

**Q: How did you not burn out?**
> I didn't try to be deep in all six every day. Each service had a Monday-morning health check — error rates, queue depth, p95 latency. I'd spend 80% of the week on the one with the worst signal. The rest stayed on autopilot.

**Q: Did things break?**
> Yes, a few times. Once a new RapidAPI provider's rate limit wasn't in our stacked limiter config, and we were burning expensive API credits for hours. I caught it next morning, added the limit, deployed in half a day. The fact that one bug took half a day to fix was the payoff of having clean separation between services.

**Q: How did you decide what to build vs. buy?**
> Cost and team size. Four engineers can't operate Kafka and Kubernetes. We used RabbitMQ over Kafka because our throughput (10K/sec) didn't justify the complexity. We used systemd on a few servers, not k8s. We used a SQL task queue, not Celery.

**Q: What would you do differently now?**
> I'd build proper SLOs from week one. We had Sentry and Prometheus but no SLO dashboards. So when something was "slow", debates went on for a day. With SLOs the conversation is 10 minutes.

**Q: How is this ownership different from Walmart?**
> At GCC, ownership meant "you and the disk" — if it broke, I fixed it. At Walmart, ownership means building patterns 12 other teams adopt. Different scale, same instinct: don't wait for someone else.

---

## What NOT to say

- Don't say "I built the entire platform" — there were 3-4 other engineers. I owned six backend services end-to-end, but the frontend, PM, and other backenders existed.
- Don't inflate numbers — 10M data points/day, 10K events/sec, 60K LOC. Not "millions per second", not "100K LOC".
- Don't claim I trained the HMM transliteration models from scratch — I used pre-trained `indic-trans` models and built the pipeline around them.
- Don't say "Celery workers" — Beat used custom multiprocessing + asyncio, not Celery.

---

## Backup story (if asked for another)

At Walmart I owned the DC Inventory Search API from spec to production. Wrote 898 lines of OpenAPI spec before any code so the consumer team could start integration day one. Built the 3-stage pipeline — GTIN conversion, supplier auth, EI fetch — with a factory pattern for US, Canada, Mexico. About 8,000 lines across eight PRs over five months. Cut integration time by 30%.
