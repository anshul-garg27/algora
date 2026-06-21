# Q: Tell me about a time you couldn't get resources you wanted.

> **LP**: Frugality
> **Primary story**: `G7 — No DevOps headcount, self-hosted services`
> **Backup story**: `G6 — No GPU budget, heuristic ML over deep learning`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

I joined Good Creator Co. as an SE-I in early 2023. The platform side had six services — Beat, Event-gRPC, Stir, Coffee, SaaS Gateway, and a fake-follower service — that needed an owner after the previous engineer left. I asked my manager twice in my first two months for a DevOps hire. The answer both times was the same: not this year, runway didn't allow it.

That meant I'd be operating six services solo, with no SRE rotation, no platform team to lean on, no managed-Kubernetes setup, no terraform-everything infra.

### Task

Keep all six services running and continue shipping product. Without the headcount.

### Action

I stopped pretending the DevOps hire was coming and built around the absence.

First — picked operationally cheap tech, not state-of-the-art. No Kubernetes. We ran on AWS EC2 with systemd unit files and bash deploy scripts I checked into each repo. Boring, simple, debuggable by one person at 2 AM. Same for messaging — kept RabbitMQ instead of moving to Kafka because RabbitMQ was already running and we had operational muscle for it.

Second — reused existing infra everywhere. When I migrated log data off PostgreSQL I picked self-hosted ClickHouse instead of Snowflake or BigQuery — same VMs, no new tooling. The fake-follower ML service ran on AWS Lambda + SQS + Kinesis because that meant zero infra to operate. The Stir data platform ran on Airflow we already had — adding new DAGs cost no new ops surface.

Third — wrote runbooks for everything. One page per service: what it does, top three failure modes, how to restart, where the logs are. Took me 15 days in my first month and saved me hours every month after that. Anyone could page me and I could fix things from my phone because the runbooks told me where to look.

Fourth — said no a lot. Product wanted a "real-time" dashboard that would have required a streaming-aggregation layer. I pushed back, scoped it to 15-minute refreshes via dbt, and shipped it in a week instead of a month. "What we already have can do this with 90% of the value" was a phrase I used a lot.

### Result

Six services kept running for 18 months without a DevOps hire. Cost incidents stayed manageable — Beat hit Instagram's rate limit once (built a Redis token bucket overnight), ClickHouse hit "too many parts" once (tuned the flush batch size). Both fixed by me, both solo.

The honest part: this wasn't ideal. The code wasn't always pretty. Some of the bash deploy scripts make me wince now. But the constraint forced choices I'd still defend — boring tech, reused infra, written runbooks. The "do it without the resources" version of a system is often the version that's actually maintainable.

---

## Technical depth — if they probe

- **systemd + bash deploys**: Each service's repo has `deploy.sh` that does git pull, build, restart. No CI/CD platform. Not pretty, fast to debug.
- **Self-hosted ClickHouse**: Single node, daily backup to S3, Sentry on the consumer. Operated by checking dashboards once a day.
- **Lambda for fake-follower**: Serverless was the frugal call because it eliminated ops. SQS for input, Kinesis for output, ECR for the container image. Pay-per-invocation.
- **RabbitMQ reuse**: Already in production for Identity and credential events. Adding log-event queues was config, not infra.
- **Airflow for everything batch**: 76 DAGs by the end. Cheaper than building point-solution schedulers.

---

## Likely follow-ups

**Q: Why didn't you escalate harder?**
> I escalated twice. The third time would have been about my framing, not the constraint. I focused on what I could control.

**Q: Wasn't this risky?**
> Yes. Single point of failure was me. We had Sentry alerts and on-call rotation across the eng team so it wasn't entirely on me, but I owned the platform incidents.

**Q: What if a service had blown up while you were on holiday?**
> Two engineers had been onboarded to Beat and Coffee with the runbooks. They could keep things alive for a week. Anything deeper would have waited or had me dial in. Imperfect but real.

**Q: Did you ever get the hire?**
> Not while I was there. The runway constraint never lifted.

**Q: What would you do differently?**
> Write the business case for the hire in numbers — hours-per-week I spent on ops, incidents per month, opportunity cost in features not shipped. I made an emotional case. I'd make a financial case now.

---

## What NOT to say

- Don't pretend this was empowering — it was a constraint I worked within, not a feature.
- Don't bash leadership — the runway was a real constraint.
- Don't oversell — solo platform ownership has real downside; flag it.

---

## Backup story (if asked for another)

For the fake-follower detection at GCC, the obvious answer was a fine-tuned transformer model. No GPU budget, no ML engineer, no inference cluster. I built a 5-feature heuristic ensemble — `indictrans` for 10 Indic-script transliteration, RapidFuzz weighted similarity, a 35K-name Indian-name database, digit-count and non-Indic-script heuristics. Ran on Lambda. Quality was good enough for content filtering; cost was Lambda invocations, not a $50K GPU bill.
