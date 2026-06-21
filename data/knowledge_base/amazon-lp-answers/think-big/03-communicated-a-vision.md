# Q: Describe a time you communicated a vision.

> **LP**: Think Big
> **Primary story**: `G3 — Stir Data Platform`
> **Backup story**: `W11 — Apollo Federation BFF`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Mid-2023 at Good Creator Co. Our SaaS platform showed brands influencer analytics — engagement rates, leaderboards, audience demographics. The data was 24 hours stale on every metric. A campaign could go viral overnight and we wouldn't reflect it until the next morning's batch run. Brands complained. Internally, we had a few dozen Python cron scripts pulling data from ClickHouse, dumping to Postgres, all manually triggered.

### Task

Product asked me to "replace the cron jobs with something better." Internally I read that as a chance to pitch a bigger thing — a real data platform — and get the team to buy in.

### Action

I didn't lead with architecture. I led with the customer story. I built a one-pager that said: "Coca-Cola sees yesterday's numbers when they decide today's campaign." That sentence framed everything else.

Then I painted what "real-time" actually meant for our product. Not 24 hours stale. Not even one hour. The leaderboard rank when a post hit a million views should update within 15 minutes. The recent-post tracker should be 5 minutes. Heavy aggregates like quarterly trends could stay daily. Different metrics, different freshness — five scheduling tiers.

I drew the architecture on a single slide. Three layers. ClickHouse for OLAP — that's where transformation happened, in dbt. S3 as JSON staging — JSONEachRow format. Postgres as the serving layer, with atomic table swap so the SaaS app saw zero-downtime updates. Airflow on top, orchestrating 76 DAGs across the five tiers — every 5 min, 15 min, 30 min, hourly, daily, weekly.

The hardest part of the pitch was selling 112 dbt models. The team's first reaction was "do we really need that many." I broke it into 29 staging models — type-cast and null-handle raw data — and 83 mart models grouped by business domain: discovery (16), collection (12), leaderboard (14), genre (7), audience (4), and so on. Each model was a small, testable transformation. dbt's `ref()` made dependencies explicit. That part landed once I showed how dbt's tags meant `dbt run --models tag:core` ran exactly the right 15-minute set.

I also had to defend ClickHouse → S3 → Postgres over direct sync. The senior in the room asked the right question — "why three hops." S3 was the checkpoint. If Postgres load failed, we didn't re-export from ClickHouse — we just re-downloaded from S3. ClickHouse has native `INSERT INTO FUNCTION s3()`, so the export cost was small. Atomic table swap on the Postgres side meant readers saw consistent data the whole way through.

### Result

The platform shipped over about three months. Data freshness dropped from 24 hours to under 1 hour. Core metrics refreshed every 15 minutes. The SaaS team stopped getting "your data is stale" tickets. Three brands specifically called out faster leaderboard updates as a reason they renewed. The vision worked because I led with the customer pain, then made the architecture follow it — not the other way around. People remember the Coca-Cola sentence; nobody remembers slide eleven.

---

## Technical depth — if they probe

- **76 DAGs across 5 tiers**: 11 dbt orchestration, 17 Instagram sync, 12 YouTube sync, 15 collection/leaderboard sync, 9 operational, 7 asset upload, 5 utility.
- **112 dbt models**: 29 staging (`stg_beat_*`, `stg_coffee_*`), 83 marts grouped by domain.
- **Atomic table swap**: `BEGIN; ALTER TABLE x RENAME TO x_old; ALTER TABLE x_tmp RENAME TO x; COMMIT;`. Readers see consistent snapshot. Old table kept as `_old_bkp` for emergency restore.
- **JSONEachRow on S3**: ClickHouse's native one-JSON-per-line format. Postgres `COPY` can read it straight. CSV was rejected — too many commas in biography fields.
- **Scheduling tiers**: */5 min (recent posts, post-rank), */15 min (core metrics), */30 min (collections), hourly (sync ops), daily (leaderboards, full refresh), weekly (heavy aggregates).

---

## Likely follow-ups

**Q: Why not Kafka CDC for real-time?**
> Overkill for batch analytics. CDC adds infrastructure and operational surface. Our 15-minute tier was real-time enough for the product. A 5-minute Airflow DAG is cheaper than a Kafka stream.

**Q: How did you handle the "76 DAGs is too many" pushback?**
> Showed that DAG count tracks operational independence. If `dbt_core` fails, `sync_leaderboard` shouldn't fail with it. Each DAG had `max_active_runs=1`, `concurrency=1`, and Slack failure callbacks. The count was a feature, not a bug.

**Q: Biggest surprise during build?**
> Airflow's DAG parsing overhead. With 76 DAGs, the scheduler took noticeable time to parse all the files on each refresh. We had to tune `dag_dir_list_interval` and split DAGs across folders.

**Q: Would you do anything differently?**
> Dagster might have been a better fit — the asset-based model maps more cleanly to dbt models. But Airflow's plugin ecosystem (`ClickHouseOperator`, `DbtRunOperator`, `SSHOperator`) was the deciding factor when we started.

---

## What NOT to say

- Don't lead with architecture. Lead with the customer pain — that's what makes a vision land.
- Don't claim the platform handled "real-time" in the streaming sense. Our fastest tier was 5 minutes. That's near-real-time, not real-time.
- Don't oversell — there was a real lift here in moving from cron to Airflow, but the pitch worked because it tied to renewals, not because the tech was novel.

---

## Backup story (if asked for another)

W11 IAM platform at Walmart. The team was scoped to "replace the ServiceNow ticket flow with a self-service UI." I pitched a unified GraphQL BFF using Apollo Federation — one query, 10+ downstream services, type-safe end to end. The vision was "supplier creates credentials in 10 minutes, not 3–5 days." The architecture followed the vision: federation lets each backend team own its subgraph independently, AppToApp auth solved the cross-domain token problem, and MeghaCache made auth sub-millisecond. Same pattern as Stir — frame the customer outcome first, justify the architecture against it.
