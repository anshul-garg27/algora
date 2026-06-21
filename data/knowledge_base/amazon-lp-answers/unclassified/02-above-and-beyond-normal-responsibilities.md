# Q: Tell me about a time you went above and beyond your normal responsibilities to achieve a goal.

> **LP**: Unclassified (Ownership + Think Big)
> **Primary story**: G7 — Sole Architect (6 services at SE-I)
> **Backup story**: W2 — Shared Library Adoption
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Good Creator Co, February 2023. I joined as SE-I — first real full-time engineering job after PayU. The team was small. There was a tech lead, a couple of senior engineers focused on the front-end and ML, and me on the backend platform side.

Within the first month it became obvious that there wasn't a "backend architect" role on the org chart, but the company needed one. The platform was six services across Python and Go — Beat scrapers, the Coffee SaaS API, the Stir data platform, the Event-gRPC ingestion service, the analytics gateway, the dual-database fronting layer. New features kept coming in. Tech decisions were getting made ad-hoc.

### Task

My assigned scope was "ship features on Beat". Nobody told me to architect six services. But if I just shipped features, the platform would keep accumulating inconsistent decisions, and someone two years later would have to untangle it.

### Action

I started small. On my own service first — wrote a one-page design doc before I built a new scraper. Showed it to the tech lead. He liked it. The next feature, I did the same. Two months in, design docs were the norm for the platform.

Then I started asking to sit in on design reviews for services I didn't own. Coffee, Stir, Event-gRPC. I'd come prepared with questions — "why Postgres here, why ClickHouse there", "what's the message-size tradeoff if we move this to gRPC". I wasn't asked to be in those rooms. I just showed up and earned the seat by adding signal.

By month six, I owned the architecture for the whole backend stack — six services. Concrete examples of what that meant:

- **G1**: I proposed migrating the event logging from Postgres to ClickHouse via a RabbitMQ buffered sinker. Defended the design in front of an external advisor — the advisor pushed Kafka, I held the line with cost math (3x more for our query pattern) and shipped ClickHouse. 2.5x faster reads, 5x columnar compression.
- **G4**: For the Coffee SaaS API, I designed a dual-database pattern — Postgres for transactional reads, ClickHouse for analytics. Defended that design too — the alternative was a single-DB shortcut that would've broken under analytics load.
- **G7**: I owned the Go onboarding for the team. Wrote internal guides, paired with the two senior engineers on their first gRPC service.
- **G8**: When platform asked me to move to Kubernetes for the Stir data platform, I pushed back and stayed on self-hosted RabbitMQ — saved us 6 months of complexity we didn't need at our scale.

### Result

Eighteen months later, all six services were running in production with consistent patterns — design docs, dual-database where it fit, ClickHouse where the workload required it. Two engineers who joined after me used my onboarding guides to ramp in a week instead of a month. When I left, the tech lead told me he'd hired a SE-II partly to backfill the architecture role — that wasn't my title at GCC. It was the work I'd been doing.

The honest reflection — going above and beyond at SE-I wasn't bravery. It was that nobody else was doing it and the work was visible. Walking into design reviews uninvited the first time was the hardest 30 seconds. After that, the work spoke.

---

## Technical depth — if they probe

- **The ClickHouse migration**: events were saturating Postgres writes at ~10M logs/day. ClickHouse with `MergeTree` engine, partitioned `toYYYYMM(timestamp)`. RabbitMQ buffered sinker batched 1000 records per write to absorb the write-rate mismatch. 2-week dual-write window for safety before cutover. Reads: 2.5x faster on a typical aggregation, 5x columnar compression on disk.
- **Dual-database in Coffee**: Postgres for the OLTP path — customer-facing reads, transactions. ClickHouse for analytics — dashboard queries, time-series rollups. The service exposed both behind a single API gateway; the routing was query-shape based.
- **Why self-hosted over k8s for Stir**: at our scale (~3 services on one node), k8s was a 6-month operational tax we didn't need. The break-even was around 10 services or multi-region — we were neither.

---

## Likely follow-ups

**Q: How did you get into design reviews you weren't invited to?**
> First couple of times I asked the tech lead — "mind if I sit in? I won't talk unless asked." That gave me cover. Once I'd contributed something useful in the first one, the invites stopped being needed. It was just expected I'd be there.

**Q: Did the senior engineers resent a junior taking architecture work?**
> Some did initially. One pushed back on me defending RabbitMQ over Kafka. The way I handled it was — I never claimed authority I didn't have. I'd say "here's the cost math, here's why I'd go with X, but you're the call". The decision-making was theirs, the analysis was mine. That framing kept it collaborative.

**Q: Why wasn't there a senior architect on the team?**
> Small company, fast-growth, hiring lag. They were trying to hire one. Eventually they did — a SE-II joined about six months before I left and we co-owned things from there. The gap was real, not engineered for my benefit.

**Q: What would you do differently?**
> Two things. One — I should've asked for the title earlier. I was doing SE-II work as SE-I for over a year before I asked, and it cost me on the comp side. Two — I should've documented the architecture decisions more publicly. A lot of "why we do X" knowledge was in my head. When the SE-II joined, ramp-up was slower than it needed to be.

**Q: Is this the same as W2 (shared library) at Walmart?**
> Similar pattern, different scale. W2 was one shared library across three teams in a known org. G7 was six services across the entire backend at a company without a senior architect. W2 is "I built a piece other teams used"; G7 is "I owned the system shape across a company".

---

## What NOT to say

- Don't sound entitled — "I should've been promoted faster". The reflection is on the work, not the title.
- Don't trash the team for needing your help — it was a fast-moving startup, the gap was real, that's the context.
- Don't list all six services individually in the spoken answer. Mention two by name, gesture at the rest.
- Don't make it sound like one heroic project. The point is that it was sustained — 18 months of taking on architectural scope without the title.

---

## Backup story (W2 — Shared library at Walmart)

Closest Walmart equivalent. Splunk was being decommissioned, three teams in my org were independently building audit-logging stacks. My scope was just mine. I noticed the duplication, ran 30-min calls with both other leads, found 80% overlap, built a Spring Boot starter library. Brown-bag, migration guide, pairing afternoons with each team. Three teams adopted in month one, integration dropped from 2 weeks to 1 day. The shape is the same — see the pattern outside your scope, name it, own the adoption work.
