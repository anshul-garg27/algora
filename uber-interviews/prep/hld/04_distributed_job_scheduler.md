# HLD Playbook 4: Distributed Job Scheduler (cron at scale)
*Asked at Uber verbatim (SDE-4 machine-coding-turned-design round): "cron
expression + REST API call details; up to 100M tasks/day; 1-minute
granularity; reliable with strong guarantees." Also the backbone of the
'delayed jobs / reminders / retries' family.*

## The prompt
"Users register a cron + an HTTP callback. Execute on schedule. 100M
tasks/day, minute granularity, report success/failure, reliable."

## Step 1 — Requirements
- FR: CRUD jobs (cron expr, URL, method, body, headers); execute at fire
  times; execution history/status API; retries policy per job.
- NFR: **no missed fires, no (uncontrolled) double fires** — say the honest
  version: "exactly-once execution is impossible over HTTP; I'll do
  at-least-once with idempotency keys, and explain misfire policy."
- Ask: max payload size? per-job rate caps? tenant isolation? jitter allowed?
  (asking about jitter/misfire policy = instant credibility)

## Step 2 — Estimates
100M/day ≈ 1.2K exec/sec avg, but cron is SPIKY: minute boundaries, and
everyone loves `0 0 * * *` → midnight spike could be 1M+ fires in one minute
⇒ design for ~20-50K exec/sec burst. Jobs table: 100M rows × 1KB = 100GB —
fine for a sharded store. State the spike; it drives everything.

## Step 3 — APIs
```
POST /v1/jobs   {cron:"*/5 * * * *", url, method, body, headers,
                 retry:{max:3, backoff:"exp"}, idempotency_mode:"key_per_fire"}
GET  /v1/jobs/{id}            PATCH /v1/jobs/{id}        DELETE ...
GET  /v1/jobs/{id}/runs?from=...   -> [{fire_time, status, attempts, latency}]
```

## Step 4 — Data model
- `jobs` (id, owner, cron, endpoint, policy, **next_fire_time**, enabled) —
  sharded SQL/Spanner-ish; **index on (shard, next_fire_time)**: the whole
  scheduler reads off this index.
- `runs` (job_id, fire_time, attempt, status, response_code) — append-heavy
  store (Cassandra), TTL per retention.
- The key derived field: next_fire_time recomputed after each fire from the
  cron expr. Scheduling = "SELECT due jobs", never "evaluate every cron every
  minute" (say this contrast explicitly — it's the design's heart).

## Step 5 — Architecture
```
API svc → jobs store (sharded by job_id; next_fire_time index per shard)

Scheduler tier (per shard, leader-elected):
  every tick: claim due jobs:
    UPDATE ... SET state='QUEUED', lease_owner, lease_until
    WHERE next_fire_time <= now AND state='IDLE' LIMIT batch
  → enqueue (job_id, fire_time) to Kafka "due-jobs"

Worker tier (stateless, scaled by burst):
  consume → HTTP call w/ timeout → record run → compute next_fire_time
  → UPDATE job state='IDLE', next_fire_time=next
  retries: backoff requeue (attempt++) → DLQ after max
```

## Step 6 — Deep dives (real probes from the round)
**Why claim-with-lease?** Two scheduler replicas must not both fire a job:
the claim is an atomic conditional UPDATE (or `SELECT ... FOR UPDATE SKIP
LOCKED` — name it); lease_until covers scheduler death: lease expires →
another scheduler reclaims → at-least-once, bounded.

**Worker dies mid-HTTP-call?** Kafka redelivers after visibility timeout →
duplicate call possible → **idempotency key = (job_id, fire_time)** sent as
header; receiver dedupes. Honest sentence: "I deliver at-least-once and give
the receiver the key to dedupe — same contract as Stripe webhooks."

**Midnight spike:** (a) per-tenant jitter (fire within [0,30s) window unless
strict), (b) pre-shard: due-scan per shard in parallel, (c) workers autoscale
on queue lag, (d) per-destination rate limits so one tenant's 1M jobs don't
DOS their own server. Mention all four briefly; deep-dive one.

**Misfire policy** (scheduler down 10 min): options — fire-all-missed,
fire-once-then-resume, skip; it's PER-JOB config. Naming "misfire policy"
unprompted is a Quartz-grade signal.

**Push vs pull** (the interviewer in the real round drilled this): scheduler
PUSHES due jobs to a queue; workers PULL from the queue — push for latency at
the scan, pull for worker backpressure. One sentence each side.

**1-minute granularity ⇒ scan tick 10-30s; clock skew:** use the DB's clock
(claim query compares against DB now()), not worker clocks.

## Failure modes to volunteer
Scheduler leader dies → lease/leader-election failover (etcd/ZK or DB lease);
Kafka down → jobs stay claimed-QUEUED until lease expiry, then re-claim (no
loss, delayed); destination down → that job's retries/DLQ, others unaffected.

## Sentences that score
- "The schedule lives in one indexed column — next_fire_time; I never
  evaluate crons in a loop."
- "Atomic claim with a lease gives me exactly-one-dispatcher; idempotency
  keys give the receiver effectively-once."
- "Misfire policy is per-job: skip, coalesce, or catch-up."
