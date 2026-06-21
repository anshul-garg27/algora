# Q: Tell me about a time you raised the performance bar of your team.

> **LP**: Hire and Develop the Best
> **Primary story**: `W2 — Shared library set bar for code reuse`
> **Backup story**: `W10 — Observability stack with alert YAML became SLA standard`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Early 2025 at Walmart Data Ventures. Splunk was getting decommissioned and twelve services needed audit logging. I was building the audit-logging system for cp-nrti-apis. I noticed the other eleven teams were each writing their own Filter, their own async dispatcher, their own retry logic. Same code, twelve different bugs.

### Task

Nobody had asked me to build a shared library. My job was just to make cp-nrti-apis log audit events. But shipping twelve forks of the same code felt wrong. I decided to set a bar for the org: one library, one filter, one config contract.

### Action

I designed the library so it was invisible. Spring Filter at `Ordered.HIGHEST_PRECEDENCE`, CCM YAML config, safe defaults. The other teams shouldn't have to learn anything new — just add the dependency, set one CCM flag, done.

But the technical design was the easy part. The harder bar to raise was the standard for what "shared" actually means in our org. Most internal libraries got dumped over the fence with a README. Then twelve teams asked the same question in Slack and nobody got help.

I did three things instead. One, I ran Friday office hours, one hour, every week for a quarter. Teams could share their screen and walk through their integration. Eleven small bugs got caught live — typos in CCM, wrong dependency exclusions, missed `@EnableAsync` annotations.

Two, I reviewed every one of the twelve integration PRs myself. I left detailed comments that taught, not just approved. One team had set `maxThreads=100` on the audit executor. I left a comment with the formula: events-per-second times latency times two. They changed it to 20 threads and thanked me for the math.

Three, when a senior architect found a real bug in my own code — `CompletableFuture.supplyAsync` was using the shared ForkJoinPool common pool — I didn't just fix mine. I searched the codebase, found four other services with the same pattern, opened PRs for each one with the explanation.

### Result

Twelve teams integrated in three weeks. Integration time per team dropped from a worst-case 40 hours to under one hour. Bug rate across the audit-logging path dropped to about 0.02%. The library became the org standard — five teams outside Data Ventures pulled it in.

The bar I actually raised: code review as teaching. The detailed-comment style spread. A year later I still see PR reviews on the audit codebase that look like the ones I wrote. That's the part I'm proudest of.

---

## Technical depth — if they probe

- **Why a Spring Filter, not an aspect**: Filter sits before any Spring beans initialize. Aspects need component scanning. Filter wins on simplicity and lifecycle.
- **CCM-driven config**: One YAML flag, no Java changes. Teams could disable it in dev without code touches. Opt-in via config, not via annotations.
- **The CompletableFuture fix**: `supplyAsync()` without an executor argument uses `ForkJoinPool.commonPool()`. Eight threads, shared JVM-wide. Blocking I/O exhausts it. The fix: pass a dedicated `Executors.newFixedThreadPool` sized for the workload.
- **Office hours format**: Open Zoom, anyone joins, anyone screen-shares. No agenda. Twelve teams, eleven bugs caught early.

---

## Likely follow-ups

**Q: How did you get teams to adopt without authority?**
> I made it cheaper than the alternative. One hour to integrate vs. 40 to write their own. After three teams adopted, the rest followed by social proof.

**Q: What about teams that pushed back?**
> Two team leads wanted to keep their forks. I paired with each one for 45 minutes, fixed one of their pet bugs as part of the migration. Both adopted within a month.

**Q: How did office hours scale beyond one quarter?**
> They didn't need to. By month three the FAQ doc had absorbed the repeated questions. I dropped office hours to once a month, then off entirely. The bar was self-sustaining by then.

**Q: How would you do this differently next time?**
> I'd start the office hours and the FAQ doc at the same time, not sequentially. Some of the early Slack questions never made it into the FAQ because I hadn't set up the doc yet.

---

## What NOT to say

- Don't claim I "forced" twelve teams to adopt — the right framing is I made it the cheapest path
- Don't oversell the impact ("transformed the org") — say what changed and how much
- Don't skip the office hours detail — that's the part that raises the actual bar, not the library code
- Don't say "I set a new standard for the team" — let the metrics imply that

---

## Backup story (if asked for another)

When I built the observability stack for the supplier-facing APIs, I wrote an alert YAML template — p95 latency, error rate, 4xx-vs-5xx split — and put it in a Confluence page. Three other teams copied it for their SLA dashboards. It wasn't planned. It became the template by accident, which is usually how standards actually take.
