# Scenario-Based "What If?" Questions - Stir Data Platform

> **Hiring managers LOVE these.** They test if you truly understand your system under failure.
> Use the framework: DETECT -> IMPACT -> MITIGATE -> RECOVER -> PREVENT

---

## Q1: "What if ClickHouse goes down?"

> **DETECT:** "Airflow `DbtRunOperator` tasks fail. ClickHouseOperator export tasks fail. Slack notifications fire for every affected DAG."
>
> **IMPACT:** "All 11 dbt orchestration DAGs stop. The 19 ClickHouse export tasks fail. BUT -- PostgreSQL still serves the SaaS app with the last successfully synced data. Users see slightly stale data, but the app doesn't break. The atomic swap pattern means the last successful table is always intact."
>
> **MITIGATE:** "There's no automatic failover since we run a single ClickHouse node. The SaaS app degrades gracefully -- it reads from PostgreSQL which has the last synced data. How stale depends on which DAG ran last: core metrics could be 15 minutes old, leaderboards up to 24 hours."
>
> **RECOVER:** "Restart ClickHouse. Since dbt materializes as tables (not views), the models are persisted on disk. We don't need to rebuild from scratch. The Airflow scheduler with `catchup=False` picks up the next scheduled run without trying to backfill missed runs."
>
> **PREVENT:** "Move to ClickHouse Cloud or a multi-node cluster with ReplicatedMergeTree. In our startup context, the cost of HA didn't justify the risk -- single-node downtime was rare and the PostgreSQL fallback was acceptable."

---

## Q2: "What if the S3 export fails midway -- partial JSON file?"

> **DETECT:** "The SSHOperator download would succeed (partial file exists). But the PostgreSQL COPY would fail -- invalid JSON at the point of truncation. Slack notification fires."
>
> **IMPACT:** "The PostgreSQL COPY fails, so the temp table is never populated, so the atomic swap never executes. The old production table remains live and untouched. Users see no impact -- they read the previous successful sync's data."
>
> **MITIGATE:** "This is where the three-layer architecture shines. We set `s3_truncate_on_insert=1` which means the file is fully overwritten on each run. If the write is interrupted, the file is corrupt, but the next scheduled run will overwrite it with a complete file."
>
> **RECOVER:** "Simply wait for the next scheduled run. The DAG retries automatically. Or manually trigger the DAG from the Airflow UI. No data loss because ClickHouse still has all the source data."
>
> **PREVENT:** "We could add a file integrity check -- SSHOperator runs `wc -l` to count JSON lines and compares to a ClickHouseOperator count query. If they don't match, ShortCircuit the downstream tasks. We haven't implemented this because the PostgreSQL COPY failure is already a sufficient guard."

---

## Q3: "What if the atomic table swap fails mid-transaction?"

> **DETECT:** "PostgresOperator task fails. Slack notification with task ID `swap_tables` and a link to Airflow logs."
>
> **IMPACT:** "PostgreSQL's transaction guarantee protects us. The `BEGIN; ALTER TABLE RENAME; COMMIT;` either fully completes or fully rolls back. If it rolls back, the old production table is still in place, untouched. Users see no change."
>
> **MITIGATE:** "The old table is preserved. The `_old_bkp` table from the previous run might still exist (if DROP TABLE for the old backup failed), but that doesn't affect the production table."
>
> **RECOVER:** "Investigate why the swap failed -- usually a constraint violation in the new table, or the temp table name was already taken from a previous failed run. The `DROP TABLE IF EXISTS` at the start of the SQL handles stale temp tables. Re-trigger the DAG."
>
> **PREVENT:** "Our SQL starts with `DROP TABLE IF EXISTS` for the temp table and backup table, cleaning up any artifacts from previous failed runs. This makes the pipeline idempotent."

---

## Q4: "What if the daily batch (dbt_daily) takes longer than 6 hours?"

> **DETECT:** "`dagrun_timeout=dt.timedelta(minutes=360)` kills the DAG run after 6 hours. Slack failure notification fires."
>
> **IMPACT:** "The daily models (leaderboards, time series) are stale for that day. But the ShortCircuitOperator in `dbt_hourly` and `dbt_collections` pauses those DAGs during 19:00-22:00 UTC -- if the daily batch exceeds that window, the hourly and collection DAGs resume automatically, so near-real-time data keeps flowing."
>
> **MITIGATE:** "The downstream sync DAGs (`sync_leaderboard_prod`, `sync_time_series_prod`) are scheduled AFTER the daily batch -- at 20:15 and 03:03. If the daily batch doesn't complete, these sync DAGs will export stale models. Since the data in the old tables is from the previous day's successful run, it's still valid, just one day old."
>
> **RECOVER:** "Investigate the slow queries. ClickHouse `SETTINGS max_bytes_before_external_group_by = 20GB` allows disk spilling, but if the data grew significantly, we might need to increase memory limits or optimize the queries. We could also run `dbt_daily` manually with `--full-refresh` during off-peak hours."
>
> **PREVENT:** "Monitor query execution time trends. Add alerting when the daily batch exceeds 80% of its timeout budget. Consider breaking the daily batch into smaller tag groups that can run in parallel on a ClickHouse cluster."

---

## Q5: "What if two DAGs try to swap the same PostgreSQL table simultaneously?"

> **DETECT:** "This shouldn't happen because of `max_active_runs=1` and `concurrency=1` on every DAG. But if two DIFFERENT DAGs target the same table (e.g., `sync_leaderboard_prod` and a manual trigger), one would fail with a 'table does not exist' error during the RENAME."
>
> **IMPACT:** "PostgreSQL's DDL locking would serialize the two transactions. The first one would succeed; the second would fail because `leaderboard_tmp` was already renamed to `leaderboard` by the first. The Slack notification would fire for the failed DAG."
>
> **MITIGATE:** "Each sync DAG uses uniquely named temp tables. The leaderboard DAG uses `leaderboard_tmp`, the time series uses `time_series_tmp`. So different DAGs don't conflict. The risk is only with the SAME DAG running twice."
>
> **RECOVER:** "The failed DAG's next scheduled run will succeed. `DROP TABLE IF EXISTS` at the start cleans up any leftover temp tables."
>
> **PREVENT:** "`max_active_runs=1` is the primary guard. The leaderboard DAG also generates random index name suffixes: `''.join(random.choices(string.ascii_letters + string.digits, k=10))` to prevent index name collisions between runs."

---

## Q6: "What if the scrape pipeline stops producing data -- dbt models process empty tables?"

> **DETECT:** "dbt models would still succeed -- they'd just produce empty results. The downstream sync would export an empty JSON to S3, COPY it into PostgreSQL, and swap with an empty table. The SaaS app would show no data."
>
> **IMPACT:** "This is the most dangerous scenario -- silent data loss. The atomic swap replaces good data with empty data."
>
> **MITIGATE:** "Some DAGs have implicit guards. The `sync_insta_collection_posts` DAG queries ClickHouse for posts needing refresh and only creates scrape requests for posts within a 2-month window and with fewer than 2 failures. If no posts match, it simply does nothing. But the sync DAGs don't check row counts before swapping."
>
> **RECOVER:** "The `_old_bkp` table from the previous run is still on disk. Manual `ALTER TABLE leaderboard_old_bkp RENAME TO leaderboard` restores the previous version."
>
> **PREVENT:** "I would add a row count validation step: after COPY, check `SELECT COUNT(*) FROM temp_table`. If it's less than 50% of the current production table's row count, ShortCircuit the swap. This prevents accidental data deletion from empty or partial exports."

---

## Q7: "What if a dbt model has a SQL error that produces wrong results?"

> **DETECT:** "dbt might succeed (the SQL is valid) but produce incorrect business metrics. For example, a wrong JOIN condition could inflate engagement rates. This would only be caught by users noticing anomalous data in the SaaS app."
>
> **IMPACT:** "Wrong analytics in the production app. Campaign managers might make incorrect influencer selection decisions based on inflated engagement rates."
>
> **MITIGATE:** "The tag-based scheduling limits the blast radius. A bug in a `tag:core` model only affects models that run every 15 minutes. A bug in `tag:daily` only affects daily models. The `exclude=['tag:deprecated']` pattern ensures we can quickly deprecate a broken model without removing the file."
>
> **RECOVER:** "Fix the SQL, commit to GitLab, deploy via manual CI/CD trigger. dbt models are idempotent -- the next run produces correct results. For the PostgreSQL side, the `_old_bkp` table has the last correct data."
>
> **PREVENT:** "Implement dbt tests: `unique` on primary keys, `not_null` on critical fields, `accepted_values` for enums, and custom tests for business logic (e.g., `engagement_rate BETWEEN 0 AND 100`). Also add a staging environment where dbt models run against production data before promotion."

---

## Q8: "What if PostgreSQL runs out of disk during a table swap?"

> **DETECT:** "The `CREATE TABLE ... (like production_table)` or `INSERT INTO` would fail with a disk space error. PostgresOperator fails, Slack notification fires."
>
> **IMPACT:** "The temp table creation or population fails. The atomic swap never executes. Production table is untouched. Users see no change. But the `_old_bkp` table from the previous run might be consuming space."
>
> **MITIGATE:** "Our SQL starts with `DROP TABLE IF EXISTS` for both the temp table and the old backup, freeing disk from previous runs. The leaderboard DAG uses `UNLOGGED` tables for temp data, which consume less WAL space."
>
> **RECOVER:** "Clean up old backup tables: `DROP TABLE IF EXISTS leaderboard_old_bkp`. Delete old JSON files from `/tmp/`. Then re-trigger the DAG."
>
> **PREVENT:** "Add disk space monitoring. The `VACUUM ANALYZE` step after the swap reclaims dead tuple space. We could also add a cleanup DAG that runs daily to remove `_old_bkp` tables and `/tmp/` JSON files. Monitor table sizes over time and plan capacity."

---

## Q9: "What if AWS credentials in the DAG code are rotated?"

> **DETECT:** "The ClickHouseOperator S3 export fails with an authentication error. All sync DAGs that export to S3 fail simultaneously. Slack notifications fire for multiple DAGs."
>
> **IMPACT:** "All ClickHouse-to-S3 exports fail. ClickHouse-only DAGs (dbt models) continue working. PostgreSQL still serves the last successfully synced data."
>
> **MITIGATE:** "This is a known issue -- credentials are hardcoded in DAG SQL strings. There's no automatic rotation. The blast radius is all 15+ sync DAGs that use S3."
>
> **RECOVER:** "Update the AWS credentials in all affected DAG files. Deploy via GitLab CI. DAGs pick up the new files after Airflow's scheduler re-parses."
>
> **PREVENT:** "Move credentials to Airflow Variables or Connections. Use `Variable.get('aws_key')` in DAG code. Better yet, use IAM roles on the EC2 instance so ClickHouse inherits credentials automatically with no hardcoding. This is a tech debt item I would prioritize."

---

## Q10: "What if someone needs to add a new metric to the leaderboard?"

> **DETECT:** "This is a feature request, not a failure scenario."
>
> **IMPACT:** "Requires changes across multiple layers: dbt model, sync DAG PostgreSQL SQL, and potentially the SaaS app frontend."
>
> **STEPS:**
> 1. **dbt model**: Add the new metric computation to `mart_leaderboard.sql` or its upstream model. Add the rank to the Map type columns (both `current_month_ranks` and `last_month_ranks`).
> 2. **Sync DAG**: Add the new field to the PostgreSQL `INSERT INTO` statement in `sync_leaderboard_prod.py`. Add JSONB parsing: `(data->>'new_metric')::float`.
> 3. **PostgreSQL schema**: `ALTER TABLE leaderboard ADD COLUMN new_metric float`. The temp table creation uses `LIKE production_table` so it automatically picks up new columns.
> 4. **Test**: Run the dbt model manually with `--select mart_leaderboard`. Verify in ClickHouse. Trigger the sync DAG manually.
>
> **TIME ESTIMATE:** "About 2-4 hours for a straightforward metric. The Map type for ranks makes adding new rank dimensions backward-compatible -- no schema migration needed. The Jinja templating in `mart_instagram_account` means adding a new grade is just appending to a list."
>
> **WHY THIS IS A GOOD DESIGN:** "The tag-based architecture means the new metric gets picked up by the existing scheduling. If it's in `mart_leaderboard` tagged `daily`, it automatically runs at 19:00 UTC. No DAG changes needed for scheduling."
