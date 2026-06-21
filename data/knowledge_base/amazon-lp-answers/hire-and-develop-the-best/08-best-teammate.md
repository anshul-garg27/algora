# Q: Tell me about the best teammate you've worked with.

> **LP**: Hire and Develop the Best
> **Primary story**: Senior architect at Walmart who mentored me on CompletableFuture pools
> **Backup story**: W11 SDE-1 — flip side, person I mentored, but talk about what made him strong
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Late 2024 at Walmart Data Ventures. I was building the DC inventory search API — supplier-facing endpoint that fanned out to Enterprise Inventory's internal services. I'd written it with `CompletableFuture.allOf` to parallelize the calls. Ten DCs in parallel, looked clean, passed code review, shipped to staging.

### Task

The senior architect on the team — let's call him John — was reviewing my staging metrics before the production rollout. He flagged something I'd missed. I didn't know him well at this point. The expected interaction: he'd file a Jira ticket, I'd fix it, we'd move on.

### Action

He didn't do that.

He pinged me on a Wednesday afternoon. Said, "got 30 minutes? I want to show you something on your code." We hopped on Zoom. He shared his screen with my code open on one side and a `jmap -histo:live` output on the other.

He pointed at the heap dump. ForkJoinPool common pool — 8 threads, saturated. He said, "your `CompletableFuture.supplyAsync` calls aren't passing an executor. They default to `ForkJoinPool.commonPool()`. Eight threads, shared JVM-wide. Your I/O is blocking on those threads. Under load you'll exhaust the pool and starve everything else in the JVM."

I'd been writing Java for three years. I didn't know this. He could have just told me — "use a dedicated executor." He didn't. He walked me through *why*: the common pool is sized for CPU work, not I/O. The math: pool size should be roughly (events/sec × latency × 2) for I/O workloads.

Then he did the thing that made him the best teammate I've worked with. He said, "this isn't just your bug. I bet four other services have it. Want to look together?" We grepped the codebase. Found four. He let me write the fixes and the PRs. He reviewed them. He didn't take credit for the catch.

The pattern stuck. Every time I review code now, I ask: is this specific to one PR, or a class of bug? That question is from him.

### Result

I shipped the dedicated-pool fix with a comment in code explaining the trade-off. The four other PRs landed across the next month. I wrote up the pattern as a one-page doc — "Async Pool Sizing in Spring Boot Services" — that's still in our Confluence.

The real result is harder to measure. He turned a code review comment into a conversation, a conversation into a pattern, and a pattern into a doc. Now I do that with the SDE-1 I mentor. Recursion is the actual signal that a teammate is good.

I told him months later he was the reason I started running my own pairing sessions. He shrugged it off. That's also part of why he's the best.

---

## Technical depth — if they probe

- **The bug itself**: `CompletableFuture.supplyAsync(supplier)` without a second argument uses `ForkJoinPool.commonPool()`. Common pool defaults to `Runtime.getRuntime().availableProcessors() - 1`. On our 8-vCPU pods that's 7 threads, shared by every async task in the JVM.
- **The fix**: Pass `Executors.newFixedThreadPool(N, threadFactory)` as the second arg. Size N for I/O — rule of thumb (concurrent requests × p99 latency) / target latency.
- **Why he was right to teach, not tell**: I'd have repeated the mistake. The next service I built would have had the same issue.

---

## Likely follow-ups

**Q: What specifically made him the best teammate?**
> Three things. He taught instead of told. He hunted for the class of bug, not just the instance. And he gave credit forward — let me write the four fix PRs and put my name on them.

**Q: How did this change how you work?**
> I run pairing sessions now the way he ran that one. Screen on, heap dump open, walk through *why*. I also now look for the bug-class, not the bug.

**Q: Was he your manager?**
> No, senior architect on the team. He didn't have authority over me. He spent the time anyway.

**Q: How do you spot teammates like this?**
> They give detailed code-review comments that teach, not just approve. They open PRs that aren't theirs to clean up a pattern. They don't claim credit.

---

## What NOT to say

- Don't gush — keep it specific and technical
- Don't make him a hero — make the *technique* the hero, then attribute it
- Don't skip the recursion — the fact that I now do this with my mentee is the real measurement
- Don't say "I learned everything from him" — say "this specific thing changed how I work"

---

## Backup story (if asked for another)

The SDE-1 I mentored on the credential-mgmt subgraph turned out to be a great teammate in his own way — he asked precise questions, course-corrected without defensiveness, and within six months was mentoring the next SDE-1 himself. The thing I most respect about him: he treated every code review as a chance to learn the codebase deeper, not just to get his PR merged.
