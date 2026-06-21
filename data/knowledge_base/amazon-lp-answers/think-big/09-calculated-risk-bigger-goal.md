# Q: Describe a time you took a calculated risk on a bigger goal.

> **LP**: Think Big
> **Primary story**: `W4 — Active/Active 5-Week Canary`
> **Backup story**: `G1 — Postgres + ClickHouse Dual-Write`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Early 2025 at Walmart Data Ventures. Our audit logging pipeline was single-region in EUS2. Leadership had asked for "make it resilient." I'd proposed and got sign-off on Active/Active dual-region — both EUS2 and SCUS taking writes simultaneously. 2x infrastructure cost, zero data loss, near-instant failover. The bigger goal was clear.

The risk was the rollout itself. Active/Active means both regions writing in parallel, with geographic routing by `wm-site-id` header. If routing was wrong, we'd either get duplicate writes (manageable) or split-brain with the wrong region serving the wrong market (compliance issue). And we couldn't really "test" Active/Active in stage — the failure modes only show up under real traffic at scale.

### Task

Roll out Active/Active in 4 weeks with zero data loss. The bigger goal was the right pattern for the team. The calculated risk was the path to get there.

### Action

I designed the rollout in phases that let us cut at any point.

Week one — publisher in SCUS, dual-writing to both Kafka clusters. Zero traffic shift. If SCUS publisher misbehaved, EUS2 was still primary and unaffected. The bet here was that dual-publishing wouldn't add real load to the request path.

Week two — GCS sink in SCUS with the `wm-site-id` Single Message Transform routing. EUS2 sink kept consuming as before. We now had both regions writing to GCS but no traffic flowing through SCUS yet. The bet was that the SMT would correctly filter by header.

Week three was the real risk week — data parity validation. Both regions producing data for a week, with daily comparison of API Proxy counts versus Data Discovery counts. The hypothesis was that if both regions saw the same input stream, they should produce matched outputs. I had to be willing to extend this week if parity broke.

It broke. On day three I noticed API Proxy was reporting about 100K fewer records per day than Data Discovery. Up to 130K on the worst day. That's a 5–7% silent drop. Tracing it — 413 Payload Too Large errors at the API gateway. The payload size limit was inconsistent across paths. Some audit events were quietly dropping before they ever hit Kafka.

That was the moment the bigger goal could have been blocked. I had two choices — accept the 5–7% drop as out of scope and continue to traffic split, or pause and fix it. I paused. Set a 2MB gateway limit (PR #49, #50, #51). Validated parity again — API Proxy count exactly matched Data Discovery count.

Week four — traffic split. Geographic routing turned on. EUS2 served US, SCUS served Canada and Mexico. Flagger-managed failover ready.

### Result

Active/Active was live at end of week four. DR test gave 15-minute recovery against a 1-hour target. Zero data loss across three EUS2 outages we've had since. The risk paid off because the rollout was phased — we could have cut at any week if data didn't match. The 413 discovery in week three was the calculated risk doing its job: instead of finding the bug in production with real customer impact, we found it in dual-write validation.

The bigger lesson — taking a calculated risk on a bigger goal isn't about being brave with one big bet. It's about cutting the bet into pieces, each one independently safe, with explicit checkpoints. Week three was where the goal would have been wrong without the discipline.

---

## Technical depth — if they probe

- **Phased rollout**: dual-publish (week 1) → dual-sink (week 2) → data parity validation (week 3) → traffic split (week 4). Each phase has a cut point.
- **413 root cause**: API gateway payload limit was 1.5MB on one path, 5MB on another. Audit headers were being dropped silently when total payload exceeded the smaller limit. 2MB cap unified the behaviour.
- **Data parity validation**: daily API Proxy total versus Data Discovery (Hive) total. Worst day showed 130,232 records lost to 413 + 11 to 502. After the 2MB cap, counts matched within 0.01%.
- **wm-site-id routing**: Connect SMT filters by header. `US` and no-header records stay in EUS2; `CA` and `MX` route to SCUS. No duplicate writes between regions.
- **Idempotent producer + request_id dedup**: even if a record reaches both regions during split-brain, sink-side dedup on `request_id` prevents double-write to GCS.

---

## Likely follow-ups

**Q: What if you'd missed the 413 drops?**
> Compliance audit would have caught it later — they cross-check on a weekly basis. We'd have shipped a known-bad system. The calculated risk worked because I built data parity into the rollout, not as a post-launch step.

**Q: Why not skip the 4-week rollout and just do it in a weekend?**
> Because Active/Active failure modes show up under real load. Stage testing wouldn't have surfaced the 413 issue — it only emerged with full production traffic volume.

**Q: How did you decide when to cut versus continue?**
> Each weekly milestone had a clear pass/fail. Week three's pass was "API Proxy and Data Discovery counts match within 0.1%." When they didn't, I paused. The criteria were defined before week three, not invented after.

**Q: Would you take this risk again?**
> Yes, same way. Phased rollout with explicit cut points and a willingness to extend any phase. That's not really risk — that's controlled experimentation.

---

## What NOT to say

- Don't claim the 4-week timeline was always realistic. We extended week three because of the 413 issue. The bigger goal was non-negotiable; the timeline was.
- Don't oversell — the "zero data loss across three outages" is true, but the outages were Azure-side issues we caused or absorbed, not catastrophic regional failures.
- Don't pretend Active/Active is universally right. Workload had to be write-heavy with tight RPO. It is, here.

---

## Backup story (if asked for another)

ClickHouse migration at GCC. Postgres was choking on 10M daily event inserts — write latency had degraded 100x. The team wanted to scale Postgres vertically. I proposed migrating analytics to ClickHouse with a dual-write strategy. The calculated risk was two weeks of dual-write with daily count + checksum validation. Zero data drift. Once validated, reads flipped to ClickHouse. 30s analytics queries dropped to about 12s. 33x write throughput improvement via the buffered sinker. Same shape — phased rollout with explicit data-parity checkpoints, willing to extend if validation breaks.
