# Q: Describe a time when you proposed an ambitious idea.

> **LP**: Think Big
> **Primary story**: `W4 — Multi-Region Rollout`
> **Backup story**: `G3 — Data Platform / Stir`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Early 2025. Walmart Data Ventures, audit logging pipeline. Leadership came to my team with a vague brief — "make audit resilient, we can't lose data if a region goes down." Everyone read that as "set up backup region for disaster recovery." Maybe Active/Passive with MirrorMaker, a manual failover runbook. Standard stuff.

### Task

I was the engineer they'd nominated to scope it. I could have shipped the standard answer. Active/Passive in a second Azure region, document the failover, done in a week.

### Action

I pushed for something bigger. Active/Active dual-region — both EUS2 and SCUS taking writes simultaneously, with geographic routing so each region primarily served its own market (US, Mexico, Canada). Zero data loss. Near-instant failover. 2x infrastructure cost.

The bigger ask was on me to defend. I started by asking compliance the question nobody had explicitly asked — "what's your real RPO." The answer was zero on paper, four hours in practice. With Active/Passive and MirrorMaker, replication lag alone was 1–5 minutes, and a manual failover would take 30 minutes. That's roughly 35 minutes of potential data loss during an outage. Active/Active dual-write was the only honest path to the RPO they actually needed.

I built a one-page comparison. Active/Passive: cheaper, simpler ops, 30-minute failover, 1–5 minute replication gap. Active/Active: 2x infra, more complex topology, near-zero failover time, zero data loss. Hybrid: middle ground, awkward to operate.

The harder argument was cost. 2x infrastructure was a real number — about $3.5K a month per service. I framed it against the alternative: a single compliance audit failure would cost more than a year of dual-region infrastructure. The compliance team backed that framing.

Phased the rollout over 4 weeks. Publisher to SCUS week one. GCS sink to SCUS week two. Data parity validation week three. Traffic split week four. Built `wm-site-id` header routing in the Kafka Connect sinks using Single Message Transforms — each region wrote only its own market's data.

### Result

Active/Active was live in 4 weeks. DR test: 15-minute recovery against a 1-hour target. Zero data loss across three EUS2 outages we've had since. Three other teams later asked to copy the pattern — I shared the ADR, implementation guide, and reference code. The pattern is now the Data Ventures default for any audit-class service. What I learned — the bigger idea is worth proposing when the smaller one has a real failure mode the team hasn't named. Active/Passive looked safe until someone asked "what's the RPO." Then it didn't.

---

## Technical depth — if they probe

- **Dual-write topology**: publisher service writes to both Kafka clusters with `CompletableFuture.thenAccept().exceptionally().join()`. Primary EUS2, secondary SCUS. Failure on primary chains to secondary automatically.
- **wm-site-id routing**: Kafka Connect Single Message Transform filters by header. US Connector keeps `US` or no-header records; CA Connector keeps `CA`; MX keeps `MX`. No duplicate writes between regions.
- **Why not MirrorMaker**: Active/Passive replication adds 1–5 minute lag. That alone blows RPO targets if you lose primary during the replication gap.
- **Exactly-once at sink**: Kafka idempotent producer for in-cluster dedup. SMT-level dedup on `request_id` for cross-cluster overlap. Worst case is duplicates, handled in BigQuery with DISTINCT.
- **Cost**: ~$3.5K/month per service vs single-region. ~$2K saved by Active/Passive. Decision was on RPO, not cost.

---

## Likely follow-ups

**Q: How did you sell the 2x infrastructure cost?**
> Compliance failure cost more than a year of dual infra. I didn't have to invent that framing — compliance lead said it after I showed her the RPO numbers.

**Q: Did anyone push back?**
> SRE lead asked about operational complexity. Fair concern. I addressed it by making the failover automatic — Flagger-managed traffic shift, no manual runbook required. Once it's automatic, two regions is barely more ops than one.

**Q: What if leadership had said "just Active/Passive, it's cheaper"?**
> I'd have shipped Active/Passive with explicit documentation that RPO was 35 minutes, not zero. The right thing isn't to win every argument — it's to make the tradeoff visible.

**Q: Three EUS2 outages — what happened?**
> Two were Azure-side network blips, one was a Kafka cluster restart we caused ourselves during a patch window. All three: SCUS picked up traffic, no data loss, supplier APIs didn't notice.

---

## What NOT to say

- Don't claim I "owned" the entire DR strategy. Compliance set the RPO; SRE owned Kafka cluster ops; I owned the publisher and sink design.
- Don't pitch Active/Active as universally right. For low-write read-heavy services, Active/Passive is fine.
- Don't make 4 weeks sound easy. There was a real bug — 5–7% of audit events dropping silently from 413 Payload Too Large — that we only found in week three of data parity validation. The fix was a 2MB gateway limit.

---

## Backup story (if asked for another)

Stir data platform at GCC. The team had me scoped to "replace these cron jobs with Airflow." I proposed a full data platform instead — 76 DAGs, 112 dbt models across staging and marts, three-layer pipeline (ClickHouse → S3 → Postgres with atomic table swap), scheduling tiers from 5 minutes to weekly. Cut data freshness from 24 hours to under 1 hour. The bigger pitch worked because brands were making campaign decisions on yesterday's numbers — the small "replace cron" version wouldn't have solved that.
