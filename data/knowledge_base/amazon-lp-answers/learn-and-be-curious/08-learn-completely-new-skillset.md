# Q: Tell me about a time when you had to learn a completely new skillset to accomplish current deliverables.

> **LP**: Learn and Be Curious
> **Primary story**: `G11 — Learn-Fast Onboarding`
> **Backup story**: `G6 — Fake-Follower ML`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

February 2023. I joined Good Creator Co. as an SDE-1 straight from PayU, where I'd written Python and Java. My first assignment was Event-gRPC — a Go service that ingested 10K events per second from RabbitMQ and batch-wrote them to ClickHouse. I had never written a line of Go. I had never used gRPC, RabbitMQ, or ClickHouse in production. The team was four engineers. There was no formal onboarding plan.

### Task

Be productive on a high-throughput Go service in four weeks. First production PR by end of month one.

### Action

I started with reading, not writing. Week one — I read the entire Event-gRPC codebase end to end. Not understanding everything, just mapping the shape. Where the gRPC handlers lived, where the buffered sinker was, how RabbitMQ consumers were wired up in `main.go`. I drew the architecture by hand on paper. That was probably the most important hour of the month.

Week two — I went deep on Go concurrency. Goroutines, channels, `sync.Once`, `sync.Mutex`, the `select` statement. I learned by mimicking patterns from the codebase, not from tutorials. The buffered sinker pattern in `eventsinker.go` taught me more about Go channels than any blog post.

Week three — I picked the smallest production task I could find. A new event type that needed to flow from gRPC into a new ClickHouse table. That meant adding a Protobuf definition, wiring a new RabbitMQ queue, and writing the consumer config. I broke the task into 8 micro-commits so my senior could review each piece in isolation. Got code review comments that were actually about Go idioms — naming, error wrapping, when to use pointers — and rewrote with those in mind.

Week four — shipped the PR to production. Then immediately I asked: "what's the next service to own?" That ended up being Coffee, our Go REST API.

What I didn't try to do: write idiomatic Go from day one. I knew my early code would be Java-shaped Go. I made it correct first and idiomatic second.

### Result

First production PR by end of week four. Within three months I was the primary owner of two Go services — Event-gRPC and Coffee. Within twelve months I was the sole architect across six services in two languages. The lesson stayed with me — when you start from zero, read existing code before tutorials, copy patterns before inventing them, and let review comments be your style guide for the first month.

---

## Technical depth — if they probe

- **Buffered sinker pattern**: each consumer pushes to a Go channel with 10K capacity. A separate goroutine batches into slices of 1000 events OR flushes every 5 seconds, then does one batch INSERT into ClickHouse. Reduces I/O per event by 99%.
- **Why Go for ingestion**: goroutines are cheap, the channel-based concurrency model maps cleanly to producer-consumer pipelines, single static binary.
- **RabbitMQ topology**: 26 consumer queues, durable, with retry max 2 then dead-letter to error queue. `sync.Once` for singleton connection setup, `safego.GoNoCtx` wrapper to recover panics in goroutines.
- **Why ClickHouse, not Postgres**: columnar, 5x compression, aggregations 10–100x faster on event-log workloads. Postgres handled OLTP, ClickHouse handled OLAP.

---

## Likely follow-ups

**Q: What was the hardest Go concept to internalise?**
> Channels for backpressure. Coming from Java's executor model, I instinctively reached for thread pools. The Go-idiomatic way is a buffered channel with a worker pool reading from it — that buffer is your queue and your rate limiter at once.

**Q: How did you handle being slower than seniors in week one?**
> I asked specific questions, never generic ones. Not "how do I do concurrency in Go" — instead "in `eventsinker.go` line 47, why is this a `sync.Mutex` and not a channel." That got me real answers in five minutes.

**Q: Anything you got badly wrong in the first month?**
> Yes. I wrote a goroutine without recovering panics. A bad message crashed the whole consumer. My senior pointed me at `safego.GoNoCtx` — the team's wrapper that recovers and logs to Sentry. After that, I never spawned a raw goroutine again.

**Q: How would you onboard a junior to your service today?**
> Same way I learned. Hand-drawn architecture diagram on day one. Read the codebase end to end before writing anything. First PR is small and reviewed in micro-commits. Avoid tutorials — they teach toy patterns, not real ones.

---

## What NOT to say

- Don't claim I was a Go expert in 4 weeks. I was productive in 4 weeks. Expert took 6–9 months.
- Don't pretend I figured it out alone — I had four teammates and a senior who answered questions.
- Don't list every Go feature I learned. Pick concurrency and one concrete pattern.

---

## Backup story (if asked for another)

For the fake-follower ML project at GCC, I had zero ML background. I read two academic papers on Indian-script transliteration, learned what an HMM and Viterbi decoder were, then used the pre-trained `indic-trans` library rather than retraining anything. Built a 5-feature heuristic ensemble around it because we had no labelled data. Shipped in about 4 weeks. The mental model was identical to learning Go — read the source, copy proven patterns, get something shippable, then sharpen.
