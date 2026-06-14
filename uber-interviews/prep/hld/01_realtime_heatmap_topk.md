# HLD Playbook 1: Real-Time Driver Heatmap / Top-K Trending
*THE Uber archetype — ~10 of last year's design rounds were this shape:
driver heatmap (2x), trending dishes (2x), restaurant order metrics, top-K
heavy hitters, trending posts, e-commerce popularity, monitoring system.*

## The prompt you'll get
"Drivers upload locations every few seconds. Serve a real-time heatmap of
driver density." (Or: orders stream in, show trending/top-K per window.)

## Step 1 — Requirements to excavate (ask, don't assume)
- Who consumes it? (Real round had TWO consumers: ops dashboard = real-time
  20 min @ minute buckets; researchers = 24h-delayed, hourly buckets.)
- Freshness target? (~1-2s ingest-to-visible for ops.)
- Exact or approximate counts? (Approximate OK for rendering — say it.)
- Zoom levels? (Yes — multiple precisions.)
- Retention of raw data? (Raw to cold storage; aggregates short-lived.)

## Step 2 — Estimates (memorize this worked set)
- 1M concurrent drivers × 1 update/4s = **250K writes/sec** (peak ~1M/s global).
- Update = driver_id, lat, lng, ts ≈ 40B → **~35 GB/hour raw**.
- Reads: 50K ops users × refresh/5s ≈ 10K reads/sec, each = one viewport.
- Conclusion to state: "writes are firehose-scale ⇒ no row-per-update OLTP;
  queue + streaming aggregation; reads hit precomputed aggregates only."

## Step 3 — APIs (write them)
```
POST /v1/location          {driver_id, lat, lng, ts}        -> 202
GET  /v1/heatmap?bbox=...&zoom=12&window=last20m
  -> { "cells": [ {"geohash":"tdr1y", "minute":"...T10:41", "count":137}, ...]}
GET  /v1/research/heatmap?city=BLR&from=...&to=...   (hour granularity, T+24h)
```

## Step 4 — Data model
- Hot aggregates (Redis): key `h:{precision}:{geohash}:{minute}` → count,
  TTL 25 min. One key-space per precision (5, 6, 7).
- Raw events: Kafka topic partitioned by **geohash prefix / region**
  (NOT driver_id — aggregation locality; expect the "why?" probe).
- Cold: S3/Parquet partitioned `city/date/hour` → hourly batch aggregates
  into warehouse table `(city, geohash6, hour, count)`.

## Step 5 — Architecture (walk one update, one read)
```
driver app → API gateway → Location svc → Kafka (by region)
                                   │
                     stream workers (Flink-style, keyed by geohash)
                     ├─ per-(geohash,precision,minute) counters → Redis
                     └─ raw events → S3 (Parquet)  → hourly batch → warehouse
ops UI → Heatmap API → Redis MGET over viewport cells (per zoom precision)
researchers → Research API → warehouse (T+24h gate)
```
Update path: app sends every 4s → gateway auths → Kafka append (fire-and-
forget, 202) → worker increments 3 counters (one per precision) → visible in
~1-2s. Read path: viewport → cover with geohash cells at zoom precision →
MGET 20 minutes × cells → JSON.

## Step 6 — Deep dives (the probes WILL come from here)
**Hot cell (stadium/concert):** one geohash gets 100×. Mitigate: salted
sub-keys `h:...:{0..7}` summed on read; or count-min sketch for unbounded
keys. Also note Kafka partition skew → partition by finer region hash.

**Why not partition by driver_id?** Aggregation for one cell would touch all
partitions (shuffle); region keying gives locality; con: hot regions — handle
via sub-partitioning. (This exact probe ran in the real round.)

**Exactly how stale?** app(0-4s) + ingest(~100ms) + window flush(≤1s) +
Redis(ms) + UI poll(≤5s) ⇒ ~5-10s worst case. Walking this chain unprompted
is a Strong Hire move.

**Late/out-of-order events:** event-time windows + watermark (allow 5-10s
lateness); later than that → drop for real-time (it's a heatmap), keep in
batch path (it's exact).

**Top-K variant:** same pipeline; worker keeps per-window count map + size-K
min-heap (see `../learn/04_heaps_topk_streams.md`); unbounded keys → count-min
sketch + heap of candidates; exact top-K from the batch path reconciles.

**Failure modes:** Redis down → serve last cached frame + stale banner
(graceful degradation); worker crash → Kafka replay from offset (idempotent:
counters keyed by event minute, increments deduped by event-id if exactly-once
matters — for heatmap, at-least-once + small overcount is acceptable: SAY it).

## Sentences that score
- "Approximate is fine for rendering, so I trade exactness for memory with a
  count-min sketch — but the batch path stays exact."
- "Geohash prefix = cell containment, so zoom levels are just precisions 5/6/7
  precomputed in parallel." (At Uber, name-drop **H3 — Uber's own hex library**.)
- "I'll gate the research API at T+24h by only exposing the warehouse table,
  never Redis."
