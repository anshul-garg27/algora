# HLD Playbook 3: Notification / Alerting System
*Asked at Uber as: generic notification service (SDE-2, performed well =
"design I did best"), stock price alerting (SDE-2), webhook delivery (SDE-2
HLD round). One playbook covers all three skins.*

## The prompt
"Design a notification service" / "stock price alerts" / "webhook system."
Same skeleton: **events in → matching → fan-out → multi-channel delivery,
reliably, without spamming.**

## Step 1 — Requirements
- FR: channels (push/email/SMS/webhook); user preferences & opt-outs;
  templating; for alerting skins: user-defined RULES (price > X, % change).
- NFR: at-least-once delivery with idempotent sends (state this trade-off
  immediately — exactly-once delivery to a phone doesn't exist); p99 seconds;
  burst tolerance (market spike = everyone's alert fires at once).
- Ask: ordering guarantees needed? (usually no) Quiet hours/digests? Retention
  of delivery logs?

## Step 2 — Estimates
100M users; 500M notifications/day ≈ 6K/sec avg, **100K/sec burst** (breaking
news/market crash — the burst number drives the whole design: queues +
horizontally scaled workers, never synchronous fan-out).

## Step 3 — APIs
```
POST /v1/notify    {user_id|segment, template_id, params, channels?, dedupe_key}
POST /v1/alerts    {user_id, symbol, condition:{type:"price_above", value:1500}}
GET  /v1/users/{id}/preferences   |   PUT same
Webhook skin: POST /v1/endpoints {url, secret, events[]}
```

## Step 4 — Data model
- `preferences` (user, channel, opt_in, quiet_hours) — KV/row store.
- `alert_rules` (user, symbol, condition) — for matching: **inverted index
  by symbol** in Redis: `rules:AAPL` → sorted sets `above:(score=threshold)`,
  `below:(...)` so "price crossed 1500" = one ZRANGEBYSCORE, not a scan.
  (This index IS the stock-alert interview; say it slowly.)
- `deliveries` (notif_id, user, channel, status, attempts) — Cassandra-style
  append-heavy store.
- `endpoints` (webhook skin): url, secret, failing_since, disabled.

## Step 5 — Architecture
```
producers / market feed → Ingest svc → Kafka "events"
                                        │
                              Matcher workers (alert skins:
                              symbol → rules index → fired alerts)
                                        │
                              Kafka "notifications" (partition by user_id)
                                        │
                    Fan-out workers: preferences ∘ dedupe ∘ rate-limit ∘ template
                         │            │             │
                      Push prov.   Email prov.   SMS / Webhook sender
                         └──────── retries w/ backoff → DLQ
                                   delivery status → deliveries store
```

## Step 6 — Deep dives
**Reliability (the core probe):** worker crashes mid-send → Kafka redelivers
→ duplicate send? Answer: **idempotency**: dedupe_key (or notif_id) checked
in Redis `SETNX` with 24h TTL before provider call. At-least-once + idempotent
send ≈ effectively-once. Provider succeeded but ack lost → accept rare dupes,
log attempt first (say the honest trade-off).

**Retries:** exponential backoff with jitter (1m, 5m, 30m), max N attempts →
**DLQ** + alarm. Webhook skin: per-endpoint circuit breaker — failing 30 min
→ disable + notify owner (real-world answer interviewers love); HMAC-sign
payloads with endpoint secret; timeouts 3-5s; never retry 4xx except 429.

**Dedup/spam control:** per-user token bucket (e.g., 10/hour push) + collapse
keys ("3 price alerts on AAPL" → one digest). Quiet hours shift to digest
queue. This section separates SDE-2 from SDE-1 answers.

**Burst (100K/sec):** matching is read-only vs Redis index → scale workers;
fan-out partitions by user_id → no hot partition unless one user has 1M
alerts (cap rules per user — product guardrail answers are valid answers).

**Stock-alert specifics:** rule evaluation must be **crossing-based**, not
level-based (fire when price crosses threshold, else it re-fires every tick):
keep last_price per symbol, fire on sign change of (price − threshold);
de-register one-shot alerts after firing, or cooldown for repeating ones.

**Webhook ordering probe:** "consumer needs events in order" → per-endpoint
FIFO partition + sequence numbers in payload; consumer reorders; don't promise
global order (say why: parallelism dies).

## Failure modes to volunteer
Provider (APNs/SES) down → buffer in Kafka, drain on recovery (lag dashboards);
preference store down → fail-closed for marketing, fail-open for transactional
(OTP) — naming that policy split is a senior signal.

## Sentences that score
- "At-least-once plus an idempotent send gate is my effectively-once."
- "The rules inverted-index makes matching O(log n) per tick, not O(rules)."
- "Crossing semantics, not level semantics, or the alert fires every tick."
- "Webhooks get HMAC signatures, retries with backoff, and a circuit breaker."
