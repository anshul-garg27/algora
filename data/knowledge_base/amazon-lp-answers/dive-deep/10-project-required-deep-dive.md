# Q: Tell me about a project where you had to deep dive.

> **LP**: Dive Deep
> **Primary story**: `G3 — Data Platform / Stir`
> **Backup story**: `W1 — Silent Kafka Failure`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

At GCC I was handed Stir, our data platform, with a one-line brief: "make the supplier dashboards fresh and fast." Stir had 76 Airflow DAGs and 112 dbt models running on a mix of PostgreSQL and ClickHouse. Dashboards were lagging behind real time by hours, and the worst-performing models took 45 minutes to run end-to-end. Nobody on the team had a complete map of the data flow.

### Task

Get dashboards under 15 minutes of source-data lag, find and fix the slowest models, and document the platform well enough that someone else could own it next.

### Action

I spent the first week not changing any code. I read every DAG and every dbt model and drew the dependency graph by hand. Three things popped out.

First, ten DAGs were polling PostgreSQL tables every five minutes that only changed once an hour. They were idle 90% of the time and they were holding connections. I flipped them to event-triggered via the existing RabbitMQ infrastructure — Coffee API would emit a change event and the DAG would fire on the event rather than on a clock.

Second, the slowest dbt model — `mart_influencer_growth_30d` — was joining a 2-billion-row time-series table against a denormalised handle table. Postgres was full-scanning. I rewrote it to materialise on ClickHouse with `argMax(followers, event_timestamp)` keyed by `(platform, profile_id, toDate(event_timestamp))`. The same query went from 12 minutes to 90 seconds. The mart shipped on a daily incremental.

Third, the dbt model dependency chain had three "fan-out" points where one upstream model was joined into eight downstream models in parallel. Eight parallel reads of a slow upstream is the worst combination. I added a single intermediate materialisation that the eight consumers read instead. Total dbt run time dropped from 4 hours to 1 hour 20 minutes.

The deep-dive part was knowing where to look. I'd built a `dbt list --resource-type model --output json` parser that gave me model-by-model run-time data, plus the Airflow task durations from the metadata database. Without that, I'd have been guessing at hot spots.

### Result

Source-data lag dropped from 4 hours to 12 minutes. dbt full-refresh time dropped from 4 hours to 80 minutes. The two slowest models went from 45 minutes to under 2 minutes. Supplier dashboards moved off the "stale data" complaint list permanently.

The piece I'm most proud of is the documentation. I wrote one diagram per data domain — profile, post, sentiment, scrape-request — showing source, transform, mart, and downstream consumer. Six diagrams. Anyone on the team can now answer "where does this number come from?" in under 30 seconds.

---

## Technical depth — if they probe

- **Why event-triggered DAGs over polling**: RabbitMQ events from Coffee already exist for cache invalidation. Reusing them for DAG triggers cost zero new infrastructure. Polling burns connections and idle compute; event-driven runs only when there's work.
- **Why ClickHouse for the 30d growth mart**: It's a metric aggregation across a time range — exact ClickHouse shape. `argMax(metric, ts)` plus monthly `PARTITION BY toYYYYMM` plus `ORDER BY (platform, profile_id, event_timestamp)` lets the query touch one partition and skip 99% of the data.
- **Why I broke the fan-out with an intermediate materialisation**: Eight parallel reads of one slow model mean eight times the read cost. One materialisation read once by eight consumers is N times cheaper. dbt's `materialized='table'` plus a layered model design is the pattern.
- **Why I documented after, not during**: You can only draw the correct diagram once you've understood the whole system. Drawing it during the work would have produced a wrong diagram I'd have to rewrite.

---

## Likely follow-ups

**Q: How did you pick which model to optimise first?**
> Run-time histogram from Airflow. The top three models accounted for 60% of total run time. I started there. Pareto, not heroics.

**Q: What if your ClickHouse rewrite had been slower than expected?**
> I'd have rolled back. The dbt model has both implementations gated by a feature flag. I ran them side by side for a week and compared row-count and metric parity before switching the downstream marts.

**Q: How did the team react to the changes?**
> Mostly relief — the slow dashboards had been a source of supplier complaints for a year. The one pushback was on event-triggered DAGs because Airflow's sensor pattern was less familiar. I paired with one engineer for a day to walk him through the implementation.

**Q: What's still slow that you wish you'd fixed?**
> A trace-log aggregation that still takes 20 minutes. It's not on the critical path so I deprioritised it, but I have a write-up for the next person.

---

## What NOT to say

- Don't say "the platform was a mess." Say "the platform had grown organically and lacked instrumentation." Respect the prior work.
- Don't oversell "I rewrote everything." 90% of the model code is unchanged.
- Don't skip the documentation. The diagrams are how the project survives me leaving.

---

## Backup story (if asked for another)

The W1 silent-failure debug was the same shape — a multi-day dive through layers of compounding issues in a Kafka audit pipeline. Five days, four root causes (SMT NPE, KEDA loop, JVM heap, API Proxy 413). The deep-dive discipline was the same: don't trust the dashboards, follow the data, write down what you find, and resist the urge to declare victory after the first fix. The runbook I wrote afterwards was used by two other teams in the next month.
