# Q: Tell me about a time when you had received critical feedback and how you worked upon it.

> **LP**: Earn Trust
> **Primary story**: `W3 — DiscardPolicy Feedback (first-defence angle)`
> **Backup story**: `P3 — Test Coverage Program`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

It was a Friday afternoon code review on the audit common library — the Spring Boot starter JAR I'd built for three teams to log API calls. PR was up. A senior engineer — someone whose reviews everyone respected — left a comment on the thread-pool config.

The pool was 6 core, 10 max, 100 queue, default `AbortPolicy`. My async method had a catch-all that logged and swallowed exceptions to protect the API path. His comment: "Your queue size of 100 is arbitrary. When it fills up, you'll lose audit records silently and you won't know."

The comment was public. My first reaction was honestly defensive. I'd thought about queue sizing. I had numbers in my head.

### Task

Respond well. Either justify the design with evidence or change it. The wrong move was the angry-junior-engineer reply.

### Action

I waited before I typed anything. Then I ran his scenario through the actual code path.

Each audit payload is around 2KB. Queue of 100 is 200KB total — fine on memory. But when the queue fills, `AbortPolicy` throws `RejectedExecutionException`. My async method catches all exceptions and logs them. So the record is dropped, the WARN goes into log noise that no dashboard reads, and the API keeps serving like nothing happened. He was right. There's a path where we silently lose audit data and the system reports healthy.

I replied on the PR. Not "you're right, I'll fix it" — that's cheap. I wrote out the failure path I'd just traced, said his concern was legitimate, and listed three changes I'd add before merging.

One: a Prometheus counter — `audit_log_rejected_count` — so dropped tasks show up on the dashboard.

Two: a WARN log at 80% queue depth — `audit_log_queue_depth` — so we see pressure before tasks start failing.

Three: documentation in the README spelling out the trade-off — audit is best-effort by design, but "best-effort" doesn't mean silent.

I asked if there was anything else I'd missed. He flagged the thread-name prefix — said rejected tasks should be findable in a heap dump. I added that too.

### Result

The library shipped a couple of days later. The 80% queue warning has fired twice in production — both during downstream slowdowns. Both times we scaled the pool before any record was actually dropped. The senior engineer later became one of the loudest advocates for the library and helped onboard a fourth team.

What I took away: defending first is human, but trust comes from showing the work — running the numbers, naming the failure path, listing the changes. "You were right" is one sentence. The trust is in the second paragraph.

---

## Technical depth — if they probe

- **Why `AbortPolicy` and not `CallerRunsPolicy`**: `CallerRunsPolicy` would block the API request thread when the queue fills. That makes API latency depend on audit-pool health. The right answer is bounded queue + observable rejections, not making the audit path block the API.
- **80% threshold**: 80% gives time to react before the queue actually overflows. We tested 70% (too noisy) and 90% (too late) before landing here.
- **What I almost shipped**: Default `ThreadPoolTaskExecutor` config with no instrumentation. Would've worked in load tests, failed silently in prod during sustained downstream slowness.

---

## Likely follow-ups

**Q: How did you stop yourself from being defensive?**
> Took half an hour. Walked away from the screen. Then traced the scenario in actual code. The feedback was about a specific failure path — I could verify or refute it, not argue feelings.

**Q: What if he'd been wrong?**
> Then my reply would've had the numbers showing why. Public PR thread is fine for "here's the calculation." Public PR thread is bad for "I disagree" without data.

**Q: Has this changed how you give feedback to others?**
> Yes. I now write feedback comments as "here's the failure path I'm worried about" not "this looks wrong." Gives the author something specific to verify.

**Q: Was the queue size actually arbitrary?**
> Partly. I'd picked 100 from a similar service's config. I hadn't sized it against our actual throughput. He caught that I'd cargo-culted a number without justifying it.

---

## What NOT to say

- Don't paint the senior as harsh. The comment was direct, which is what good review looks like.
- Don't claim you took it well immediately. The half-hour walk-away is the real story.
- Don't pretend the bug was theoretical. It's a real failure path with a real fix.

---

## Backup story (if asked for another)

At PayU as an intern, my mentor reviewed my first end-to-end test PR and told me the tests were brittle — too tightly coupled to implementation details. I'd written 40 tests that all broke when I refactored. I rewrote them in two passes — first against the public service interface only, then with behaviour assertions instead of state assertions. That experience is why test coverage at PayU went from 30% to 83% without becoming a maintenance burden.
