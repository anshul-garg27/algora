# Q: Tell me about a time you proposed a bold idea.

> **LP**: Think Big
> **Primary story**: `W4 — Multi-Region Active/Active`
> **Backup story**: `G3 — Stir Data Platform`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

January 2025. My team at Walmart Data Ventures owned the audit logging pipeline for supplier API calls. Leadership came to standup one morning with a one-line ask: "Make this resilient — we can't lose audit data if a region goes down." Most engineers in the room heard "spin up a backup region for DR." MirrorMaker, Active/Passive, document the failover, ship it.

### Task

I'd been nominated to scope the work. The safe move was Active/Passive — one or two weeks, low risk, easy to defend. I had room to propose something bigger if I could make it stick.

### Action

I went bigger. Active/Active dual-region in EUS2 and SCUS, both Azure regions taking writes simultaneously, with geographic routing via `wm-site-id` headers so each region primarily served its own market — US, Mexico, Canada.

The bold part was the cost — 2x infrastructure, around $3.5K a month per service. I had to justify that to the room. So I asked compliance the question that everyone had been dancing around — "what's your actual RPO." The answer on paper was zero. Under questioning, they admitted four hours was the real attestation tolerance. With Active/Passive and MirrorMaker, replication lag was 1–5 minutes and failover took 30 minutes. That's about 35 minutes of potential data loss during an outage — comfortably over the real RPO once you stop ignoring replication gaps.

I built the case on three pages. Topology comparison. Failover timing. Cost versus a compliance failure. Compliance lead's exact words after seeing it — "the cost of a compliance failure far exceeds the infrastructure cost." That sentence won the room.

The rollout was 4 weeks, phased. Week one — publisher in SCUS, dual-writing to both Kafka clusters. Week two — GCS sink in SCUS with the `wm-site-id` Single Message Transform routing. Week three — data parity validation, comparing API Proxy record counts against Data Discovery counts daily. That week is when I found the 413 Payload Too Large drops — 5–7% of audit events silently lost because of a gateway payload limit. Fixed it with a 2MB cap before going to full traffic split.

### Result

Active/Active was live in 4 weeks. DR test gave 15-minute recovery against a 1-hour target. Zero data loss across three EUS2 outages since go-live. Three other teams adopted the pattern — I shared the ADR, the implementation guide, and the reference code. The pattern became the Data Ventures default for audit-class services. The bigger lesson — when the safe answer has an unnamed failure mode, naming it is what unlocks the bolder option.

---

## Technical depth — if they probe

- **Dual-write code**: `CompletableFuture.thenAccept().exceptionally(ex -> kafkaSecondaryTemplate.send(...).join())`. The `CompletableFuture` chain replaced an older `ListenableFuture` version that silently swallowed primary failures.
- **Single Message Transform for routing**: Connect SMT filters records by `wm-site-id` header. US Connector keeps `US` or no-header. CA Connector keeps `CA`. MX keeps `MX`. No duplicate writes between regions.
- **Why Active/Passive was wrong here**: MirrorMaker lag (1–5 min) + manual failover (30 min) ≈ 35 min of potential loss. Compliance accepted 4 hours on paper but really wanted near-zero.
- **413 discovery**: API Proxy was reporting ~100K records/day fewer than Data Discovery. Headers were being dropped because payloads exceeded the gateway limit. 2MB cap brought counts back into match.

---

## Likely follow-ups

**Q: How did you handle SRE pushback on operational complexity?**
> SRE lead's question was fair — two regions, two failure modes, more pages at 3am. I made failover automatic — Flagger traffic shift, no manual runbook. Once it's automatic, the "ops complexity" cost is mostly upfront, not ongoing.

**Q: Why not three regions?**
> Compliance only required two for DR. Three adds cost and operational surface for marginal benefit. Two solves the failure mode.

**Q: What's the biggest risk you're still carrying?**
> Split-brain — both regions taking writes during a network partition that doesn't quite go far enough to trigger failover. Mitigation is request-id dedup at sink and DISTINCT in downstream BigQuery. Not perfect, but acceptable.

**Q: Would you propose Active/Active again?**
> Yes, if the workload is write-heavy and the RPO is tight. For read-heavy services with relaxed RPO, Active/Passive is fine. The decision is workload-shape, not "always go big."

---

## What NOT to say

- Don't pitch Active/Active as universally correct. It's right when writes matter and RPO is tight. Otherwise it's overkill.
- Don't claim I overrode SRE. I addressed their concern (automation) and they signed off.
- Don't gloss over the 413 bug — that's the concrete proof of "data parity validation actually caught something real."

---

## Backup story (if asked for another)

Stir data platform at GCC. The team had scoped me to "replace these cron jobs with Airflow." I proposed a full data platform — 76 DAGs, 112 dbt models across staging and marts, three-layer ClickHouse → S3 → Postgres pipeline with atomic table swap, scheduling tiers from 5 minutes to weekly. Cut data freshness from 24 hours to under 1 hour. The "replace cron" version wouldn't have helped brands making campaign decisions on yesterday's numbers — that's why the bigger pitch landed.
