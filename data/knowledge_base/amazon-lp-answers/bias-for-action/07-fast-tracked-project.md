# Q: Tell me about a time you fast-tracked a project.

> **LP**: Bias for Action
> **Primary story**: `P2 — Disbursal TAT 3.2 min → 1.1 min in a single sprint`
> **Backup story**: `W6 — BigQuery RLS shipped in a week`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

I was on PayU's API Lending team. The loan disbursal journey ran 3.2 minutes end-to-end. Sales had locked a partner demo for the following Wednesday and the partner had been blunt — anything over 2 minutes and they don't sign. We were 4 working days out from the demo. The original engineering estimate to "optimise disbursal" was 2 sprints.

### Task

Pull at least 50% latency out of the flow before Wednesday. My lead's framing was useful — "pick what you can ship, not what looks best on a design doc."

### Action

Day 1 was traces, not code. I pulled the APM traces for 200 representative disbursals and drew the call chain on paper: KYC verify → bank account validation → partner pre-check → credit bureau → internal scoring → partner final-call → ledger write. Seven calls, mostly synchronous, about 190 seconds of wall time.

I looked for dependencies, not at the calls themselves. KYC verify, bank validation, and credit bureau all took the same user input and didn't read each other's output. They were sequential only because that's how the original spec was written. That was my target.

Day 2-3 was the actual change. About 80 lines of Java. Wrapped the three independent calls in `CompletableFuture.supplyAsync` on a dedicated `ThreadPoolExecutor` (core 10, max 20, queue 100), joined with `CompletableFuture.allOf`, added a 2-second `orTimeout` on each future so a slow partner couldn't drag the rest down. The slowest single call now bounded the block — about 35 seconds instead of 95.

The other win was a Redis cache on KYC results, keyed by PAN + amount bucket, TTL 10 minutes. Users were retrying disbursals after small failures and we were re-running KYC every time. Cached retries became near-instant.

Day 3 evening I deployed behind a feature flag for one partner. Day 4 morning I watched the metrics — no failures, latency holding around 1.1 minutes, response payload byte-identical to the old flow on a 1,000-disbursal diff.

### Result

Disbursal TAT dropped from 3.2 minutes to 1.1 minutes — 66% reduction. The partner demo went through. The same parallelisation pattern was applied to two other lending journeys over the next quarter. What worked was constraining the scope on day 1 — I didn't touch the seven-call sequence as a whole, I touched the three calls that could run in parallel.

---

## Technical depth — if they probe

- **`CompletableFuture` over reactive**: Sync Spring MVC codebase. Reactive would've meant rewriting every controller. Out of scope for 4 days.
- **Dedicated `ThreadPoolExecutor`**: Not the common ForkJoinPool. One slow partner shouldn't choke unrelated work that also uses the common pool.
- **`orTimeout(2, SECONDS)`**: Per-future, not on the `allOf`. Tightens the worst case.
- **Cache key includes amount bucket**: Different loan amounts trigger different KYC variants. Keying only on PAN would have cross-contaminated results.
- **Feature flag rollout**: Per-partner toggle. Rollback was one click.

---

## Likely follow-ups

**Q: Why not reactive while you were at it?**
> 4 days. Reactive would have been 4-6 weeks for that codebase. Reactive is a separate project worth doing, not a side quest.

**Q: How did you validate correctness?**
> Ran the old and new flow against the same 1,000 disbursals on staging. Diffed the response payloads byte-by-byte ignoring timing fields. Identical.

**Q: What if one of the three parallel calls fails?**
> Each future's `exceptionally` block returns a structured failure. The aggregator decides — KYC failure is hard stop, bank validation failure routes to manual review queue. The original sequential code did the same; I preserved the failure semantics.

**Q: How did you size the thread pool?**
> Concurrency math, not a load test. We had ~50 concurrent disbursals at peak. Pool of 20 worker threads serving 3 futures each gives headroom. I'd run a proper load test before scaling further.

**Q: Did the cache cause any subtle bugs?**
> Caught one — a partner had updated their KYC validation rules mid-window and our cached result was stale. Added a per-partner cache invalidation hook for that case. 10-minute TTL otherwise.

---

## What NOT to say

- Don't oversell — this was one method's worth of parallelism plus a cache.
- Don't pretend I scoped this from scratch — the lead's "pick what you can ship" framing made it possible.
- Don't skip the feature flag — that's why it was a safe fast-track, not a reckless one.

---

## Backup story (if asked for another)

Mid-sprint at Walmart, I paused the Spring Boot 3 migration work to ship BigQuery row-level security for supplier self-service. Pepsi's debug cycle had been 2 days because we were the bottleneck — they'd email support, we'd grep audit logs. I set up BigQuery external tables on the GCS Parquet we already had, added `@policy_tag` columns for consumer_id, and tested with one supplier on a Thursday. By the following Monday two suppliers were self-serving in 30 seconds. One week, no new infra.
