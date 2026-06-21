# Q: Tell me about a time when you simplified an existing process without compromising on quality.

> **LP**: Invent and Simplify
> **Primary story**: `G10 — Event-gRPC consolidation`
> **Backup story**: `W2 — Shared Library Adoption`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

At GCC the Event-gRPC service ingested events from a bunch of upstream sources — Branch.io, WebEngage, Vidooly, Shopify, the in-house app SDK. Each had its own HTTP endpoint with its own request shape, its own validator, its own goroutine pool, its own sinker function. By the time I joined we had 6 worker pools and the code was hard to reason about. Adding a new event source meant a new HTTP handler, a new pool, a new sinker. Three days of plumbing for a 10-line business change.

### Task

I owned the service after the previous engineer left. The team wanted to add two more event types. I pushed back on adding two more HTTP endpoints and proposed consolidating onto gRPC.

### Action

I introduced a single gRPC service — `EventService.dispatch()` — with a protobuf-defined event envelope. Each event type became a `oneof` field in the proto. 60+ event types, one wire protocol. The HTTP endpoints stayed for legacy callers but new sources went straight to gRPC.

Behind the dispatch I kept the worker-pool model — 6 pools, each with its own buffered channel — but unified the sink interface. Each sinker implements the same shape: `Buffer(event) bool` and `Flush(batch)`. The dispatcher pushes events to the right pool by type. Two flush triggers per pool — 1000 records or 5 seconds, whichever first.

I added safe goroutines with panic recovery so one bad event couldn't take a pool down. Auto-reconnect on a 1-second cron for both ClickHouse and RabbitMQ. Timestamp correction at the edge — clients send their local time, we normalise to UTC at dispatch.

For migration I kept the HTTP endpoints alive and routed Branch, WebEngage, and the others to translate-and-forward into the gRPC layer. Existing producers didn't know anything had changed.

### Result

Adding a new event source dropped from three days to about an hour — define the proto, write the sinker, register the pool. Twenty sinkers running today across 26 RabbitMQ consumer configurations, 90+ worker goroutines. Same quality bar — every event still has dead-letter routing, retry up to 2x, and Sentry on panic. The pool model handled a 2x traffic spike during a creator launch with no manual intervention.

---

## Technical depth — if they probe

- **Why gRPC over HTTP**: One connection per worker pool, multiplexed streams, protobuf-typed payloads. HTTP needed JSON parsing per request and a separate handler per type.
- **Single dispatch + per-type pools**: Dispatcher is cheap (just routes); the heavy lifting stays in dedicated pools. Failure in one pool doesn't block dispatch.
- **Safe goroutines**: Every goroutine wrapped in `defer recover()` that ships the panic to Sentry. Without this, one bad event takes the whole pool down.
- **Auto-reconnect cron**: 1-second ticker that checks ClickHouse and RabbitMQ connection health. If broken, reconnect. Saved us during a RabbitMQ broker rolling restart.
- **Timestamp correction**: Clients on mobile have bad clocks. We trust `event_timestamp` for ordering but record `insert_timestamp` server-side. The dbt models use `argMax` on insert_timestamp to break ties.

---

## Likely follow-ups

**Q: How did you migrate without breaking existing producers?**
> HTTP endpoints stayed alive. They now do "translate to protobuf, call internal dispatcher." Producers didn't notice. We deprecated HTTP only after every new source was on gRPC for a full quarter.

**Q: What about backward compatibility on the proto?**
> Proto2 with optional fields. New fields added at higher numbers. Old consumers ignore unknown fields. We never deleted a field — only marked deprecated.

**Q: Why batch flush at 1000 or 5 seconds?**
> ClickHouse hates small inserts — each one creates a new data part. 1000 rows hits the sweet spot for the merge engine. The 5-second ticker handles low-traffic times so events don't sit in the channel.

**Q: What if the worker pool fills up?**
> The channel is buffered (1000 capacity). If it fills, the dispatcher blocks. RabbitMQ's prefetch QoS means only a few messages are in flight per consumer, so back-pressure flows correctly to the broker. We never dropped events.

**Q: How was quality maintained during the consolidation?**
> Two protections. Dead-letter exchanges per queue catch poison messages. Sentry catches panics. We ran the gRPC path side-by-side with HTTP for a month before deprecating any HTTP endpoint — same input went both ways, output rows in ClickHouse had to match.

---

## What NOT to say

- Don't say "I removed all HTTP" — HTTP stayed for legacy. The consolidation was unifying the ingestion layer, not killing one protocol.
- Don't pitch this as inventing gRPC — gRPC is standard. The simplification is one dispatcher + pluggable sinkers.

---

## Backup story (if asked for another)

At Walmart three teams were independently building audit logging — same servlet filter, same async sender. I pulled the common 80 percent into a shared Spring Boot starter JAR and made the 20 percent that differed configurable via CCM (response-body capture, endpoint filtering). Three teams adopted within a month. Integration time dropped from two weeks to one day. The library is on version 0.0.54 today.
