# Q: Share a time when you made a decision that turned out to be incorrect.

> **LP**: Unclassified (Are Right A Lot + Learn and Be Curious)
> **Primary story**: W3 — DiscardPolicy thread-pool design (incorrect failure-mode assumption)
> **Backup story**: W5 — Spring Boot 3 initial test-mocking strategy
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Late 2024. I was designing the async thread pool for the audit-logging shared library at Walmart. The library would fire-and-forget audit events from the source API into Kafka. I picked the thread pool sizing — 6 core threads, 10 max, queue capacity 100 — based on the audit payload size (~2KB) and an estimate of peak request rate.

I'd thought about it. I'd run the back-of-envelope math. I was confident in the numbers. I shipped the design into code review.

### Task

I had to defend or fix the design when a senior engineer flagged it. He didn't argue with the numbers I'd chosen for size. He argued with what happens when the queue fills up.

### Action

His comment on the PR was direct — queue capacity 100 with the default `AbortPolicy` will silently drop audit logs in a backlog scenario, and this is a compliance system. My first instinct was defensive. I'd thought about it. The 2KB payload times 100 entries is only 200KB of memory, so the queue size wasn't a memory problem.

But that's not what he was warning about. I'd designed for memory, not for back-pressure semantics.

I closed the tab, walked, and ran the actual failure mode in my head. `ThreadPoolTaskExecutor` with `AbortPolicy` throws `RejectedExecutionException` when the queue is full. Inside the `@Async` fire-and-forget annotation, that exception goes to Spring's async error handler — which logs at ERROR level but doesn't surface as a metric. In a real backlog — say, downstream Kafka cluster slow for 10 minutes — the system would silently drop audit logs with zero alert.

He was right. My decision on the queue size was *defensible*. My decision on the rejection-policy semantics was *wrong* — I'd defaulted to the JVM default without thinking about it.

The fix took an afternoon. Three changes. A Prometheus counter for `audit_log_rejected_tasks_total`. A WARN log at 80 percent queue depth — early signal before drops start. A README section explaining the trade-off and the alert threshold. I replied on the PR — not defending, just listing what I'd added — and asked "anything else I missed?".

### Result

The library shipped with the monitoring. About four months later, during a downstream Kafka slowdown, the queue-depth alert fired at 82 percent. We scaled the consumer pool before any audit logs were dropped. That alert wouldn't have existed if I'd shipped the original design or sent the defensive reply.

The deeper thing I took from it — being wrong isn't the cost. The cost is the *kind* of wrong. I'd been wrong about the failure-mode behaviour of a default I hadn't questioned. Now I have a five-question checklist before every PR — what happens when the queue fills, when downstream is slow, when input is null, what metric will alert me, what's the rollback path. The DiscardPolicy mistake is the reason that checklist exists.

---

## Technical depth — if they probe

- **The exact mistake**: `ThreadPoolTaskExecutor` defaults to `AbortPolicy`. Inside `@Async` fire-and-forget, rejected tasks throw `RejectedExecutionException`, which Spring's `AsyncUncaughtExceptionHandler` catches and logs at ERROR level. Logs are noisy; nobody alerts on a single ERROR line in a 1000-line/min stream. Silent data loss.
- **Alternatives I considered after**: `CallerRunsPolicy` would back-pressure the source API thread — violates "zero latency impact". `DiscardPolicy` is explicit silent drop — same problem with extra steps. `DiscardOldestPolicy` discards oldest queued task — loses different data. The right answer wasn't a different policy. It was visibility into the policy I had.
- **The monitoring details**: `Counter` named `audit_log_rejected_tasks_total` with tags for service and policy. `Gauge` for `audit_log_queue_depth` polled every 15 seconds. Alert rule: `sum_over_time(audit_log_queue_depth[5m]) / 100 > 0.80`. Conservative threshold — better one false positive a quarter than one silent miss.

---

## Likely follow-ups

**Q: Why did you default to `AbortPolicy` in the first place?**
> Honestly, because that's the JVM default. I didn't change it because I hadn't asked "what should happen when the queue fills?". I'd asked "what's the right size?". Wrong question. The PR comment was the right question coming at me from outside.

**Q: How did you stop yourself from sending the defensive reply?**
> The walk. Physically getting up from the desk. I have a rule now — if my first reaction to a PR comment is to type a reply within 2 minutes, I don't send it. I walk first, come back, see if the reply still feels right. Most of the time it doesn't.

**Q: Was the senior engineer right about other things too?**
> Mostly yes. He flagged the thread-pool sizing on a different library two months later — different shape, similar pattern. Both times he was right. Now he's one of the first people I ask for a brutal review when I have a design I'm uncertain about.

**Q: What's the pattern in how you've been wrong?**
> I've been wrong twice in similar ways — defaulting to language/framework defaults without questioning the failure mode. The DiscardPolicy one was the loudest. The other was an early retry policy on a partner-bank call at PayU — default exponential backoff without jitter caused a thundering-herd retry against the partner API during a transient outage. Same root cause: didn't ask "what happens when 100 of these fire at once".

**Q: Has the checklist actually changed your behaviour?**
> Yes. Concretely — the multi-region rollout (W4) at Walmart, I drafted the failure-mode section *before* the design. Where does a region failure leave us? What metric tells us? What's the rollback? Without the checklist habit I'd have designed for the happy path and discovered the gaps in production.

---

## What NOT to say

- Don't pick a decision where you were wrong but it didn't matter — interviewers want the consequences.
- Don't pick a decision where someone else made the call — own it.
- Don't make the senior engineer the villain — he was right, and your response is what makes this a learning story.
- Don't claim the lesson was "I shouldn't have shipped without code review" — code review is what *caught* it, the lesson is one layer deeper.
- Don't over-narrate the ego moment. One line: "my first instinct was defensive". Then move on.

---

## Backup story (W5 — Spring Boot 3 test mocking)

Early in the Spring Boot 3 migration, I picked Mockito + plain `WebClient` builders for unit tests of the new HTTP client paths. The decision was wrong — `WebClient`'s fluent chain (`.get().uri().retrieve().bodyToMono().block()`) requires mocking every step of the chain, which makes the tests 30 lines for what used to be 5 with `RestTemplate`. I shipped the first three tests, hated writing them, then realised mid-migration that `MockWebServer` was the right tool — fake the server, real `WebClient`, much cleaner. I switched, rewrote the three tests, and saved myself probably 20 hours over the rest of the migration. Smaller stakes than W3, same shape — defaulted to a familiar tool, didn't ask if it was the right one, corrected mid-stream.
