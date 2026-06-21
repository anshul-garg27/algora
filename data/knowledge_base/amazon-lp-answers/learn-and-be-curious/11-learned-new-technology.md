# Q: Tell me about a time you learned a new technology.

> **LP**: Learn and Be Curious
> **Primary story**: `G11 — Learn-Fast Onboarding`
> **Backup story**: `W11 — Unified Onboarding / IAM`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

February 2023. My second day at Good Creator Co. as an SDE-1. My manager pulled me aside and pointed at a service called Event-gRPC. "This handles 10K events per second from RabbitMQ to ClickHouse. Andrey is moving teams next month. You'll own it." I had Python and Java experience from PayU. I had zero Go experience. I had never touched gRPC, RabbitMQ, or ClickHouse in production. The team was four engineers.

### Task

Be productive on a high-throughput Go service in four weeks. Ship a real production PR before the end of month one. Take over from Andrey before he switched teams.

### Action

I gave myself a week to read, not write. I opened the Event-gRPC repo and walked through it top to bottom — `main.go` first because that's where every Go program tells you what it does. Then `eventsinker.go` for the buffered sinker pattern. Then `proto/eventservice.proto` for the 60+ event type definitions. I drew the architecture on paper — gRPC handler, channel, sinker goroutine, ClickHouse batch insert. That one hour of drawing was probably the most useful learning of the month.

Then I learned Go concurrency the way the codebase used it, not the way tutorials teach it. Goroutines, buffered channels, `sync.Once` for singleton init, `safego.GoNoCtx` — the team's panic-recovery wrapper. The buffered sinker pattern taught me more about Go channels than any blog. It uses a 10K-capacity channel as a producer-consumer queue, with a separate goroutine batching into slices of 1000 events OR flushing every 5 seconds. That pattern is everywhere in idiomatic Go and I learned it from real code.

For RabbitMQ, I learned by adding a new queue. I had to read how 26 existing queues were configured in `main.go` — durable, retry max 2, dead-letter on error — and then add the 27th. For ClickHouse, I learned that columnar storage means you only read columns the query touches. Batch inserts of 1000 rows beat row-by-row by 33x because of how MergeTree handles parts.

My first PR was small — a new event type that needed to flow from gRPC into a new ClickHouse table. Protobuf definition, RabbitMQ queue config, consumer wiring, ClickHouse schema. I split it into 8 micro-commits so my senior could review each piece in isolation. The code review comments were the real curriculum — when to use pointer receivers, when to wrap errors with `fmt.Errorf("...: %w", err)`, why `sync.Once` matters for singletons in a server that may restart.

### Result

First production PR shipped by end of week four. Within three months I owned Event-gRPC and Coffee outright. Within twelve months I was the sole architect across six services in two languages. The pattern I now use whenever I learn a new tech — read the codebase end to end before tutorials, draw the architecture by hand, ship a small change in micro-commits, and let code review be the style guide for the first month.

---

## Technical depth — if they probe

- **Buffered sinker pattern**: producer writes to a 10K-capacity buffered Go channel. Consumer goroutine reads, accumulates a slice, flushes on size (1000) or time (5s) — whichever comes first. Single batch INSERT to ClickHouse. 99% reduction in per-event I/O.
- **sync.Once**: singleton init for RabbitMQ connection. Safe under concurrent first-access from goroutines.
- **safego.GoNoCtx**: team wrapper around `go func(){}()` that recovers panics, logs to Sentry, prevents a single bad goroutine from crashing the service.
- **ClickHouse vs Postgres**: column storage, 5x compression, 10–100x faster aggregations. PostgreSQL handled OLTP (profile updates), ClickHouse handled OLAP (event logs, time-series).
- **Why 1000 / 5 seconds**: empirical. Smaller batches = more I/O, larger = higher latency. 1000/5s was the curve's elbow for our throughput.

---

## Likely follow-ups

**Q: What was the hardest Go concept to internalise?**
> Channels as both queue and rate limiter. Coming from Java's executor model, I instinctively wanted thread pools. The Go-idiomatic move is buffered channel + worker pool reading from it. Took me about two weeks to stop fighting the language.

**Q: How did you decide what to read first?**
> `main.go`. Every Go program's `main.go` tells you what services it starts, what dependencies it wires, what queues it consumes. After that, follow the wiring outward.

**Q: First Go bug you wrote that bit you?**
> Spawning a raw goroutine without panic recovery. A bad message crashed the consumer. Senior pointed me at `safego.GoNoCtx`. After that I never used raw `go func` in production.

**Q: How long until you felt fluent?**
> Productive in 4 weeks. Comfortable in 3 months. Fluent enough to mentor others in about 9 months.

---

## What NOT to say

- Don't say I learned Go in 4 weeks. I became productive in 4 weeks. Fluency took longer.
- Don't claim it was self-taught — I had four teammates and Andrey for handover. I asked specific questions, often.
- Don't list every Go feature. Pick concurrency and one concrete pattern.

---

## Backup story (if asked for another)

W11 IAM platform at Walmart. I needed to learn Apollo Federation and NestJS for the GraphQL BFF subgraph. Federation was new ground — `@key` directives, subgraph composition, the difference between federation and schema stitching. Two weekends of reading plus building a prototype subgraph got me productive. The trickier learning was cross-domain auth — our DevX session tokens were invalid in the Scintilla domain where backend services lived. I learned the AppToApp pattern and used the SubGraph's own consumer ID as identity for downstream calls. Same shape as Go — read the official docs, build something tiny first, ship a small real change.
