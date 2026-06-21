# Q: Tell me about a time you refused to compromise on quality.

> **LP**: Insist on the Highest Standards
> **Primary story**: `W5 — Flagger canary on Spring Boot 3 migration`
> **Backup story**: `W3 — Refused to ship DiscardPolicy without instrumentation`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

The Spring Boot 3 migration was ready in stage. PR #1312 — 158 files changed, 1,732 additions, 1,858 deletions. Stage had been running for a week with production-like traffic. Everyone wanted it out before the next release window closed.

A senior on the team suggested the fastest path: full deploy at off-peak hours, watch the graphs, roll back manually if anything wobbled. "It's just a framework upgrade, we tested it."

### Task

I was the one who'd led the migration. I was also the one who'd be paged at 2 AM. The decision was mine: ship fast or insist on the canary.

### Action

I refused the manual cutover. The argument was specific — this wasn't "just a framework upgrade." We had 74 files moving from `javax` to `jakarta`, RestTemplate to WebClient, Hibernate 5 to 6. Each of those had at least one subtle behavior change I'd already seen in stage. Hibernate 6 stricter enum handling needed `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` on every entity. WebClient doesn't throw on 4xx by default. CompletableFuture changed how our multi-region failover chained.

Manual cutover means a human watching dashboards. Humans miss things at 11 PM. Flagger doesn't.

I set up Flagger with two metrics — `request-success-rate > 99` and `request-duration P99 < 500ms`. Step weight 10%, check every 2 minutes, automatic rollback after 5 failed checks. The plan was 10% to 25% to 50% to 75% to 100% over 24 hours, not 30 minutes.

I also held the line on keeping the old 2.7 pods alive for 48 hours after we hit 100%. That cost some extra compute. It meant rollback was a traffic-shift in Istio, not a redeploy.

It cost a day. It also cost a couple of awkward conversations.

### Result

Rollout went clean. Error rate stayed at 0.02%, P99 at 180ms, no automatic rollback ever triggered. Zero customer-impacting issues during the 24-hour window. The two post-migration fixes that did come (heap OOM in October, correlation ID in October) surfaced months later — exactly the kind of thing manual cutover wouldn't have caught either, but at least Flagger gave us a clean signal that initial rollout was healthy.

The pattern — Flagger canary on any framework upgrade — became the team default after this.

---

## Technical depth — if they probe

- **Why Flagger over manual canary**: Manual canary depends on a human spotting a P99 drift at 3 AM. Flagger checks deterministically every 2 minutes and rolls back without waking anyone.
- **48-hour old-pod retention**: After 100% Spring Boot 3, the 2.7 pods stayed running for two more days. Rollback became "shift Istio weight." Cost a few hours of extra compute; eliminated the redeploy-to-rollback risk.
- **The Hibernate enum landmine**: Caught in stage — `column is of type status_enum but expression is of type character varying`. If that had reached production without canary, every query on that entity would have 500'd.
- **WebClient default behavior**: Doesn't throw on 4xx unless you wire `.onStatus(...)`. RestTemplate threw `HttpClientErrorException`. Different downstream code paths even though the request looked identical.

---

## Likely follow-ups

**Q: How did you handle the pushback?**
> I didn't make it personal. Showed the Hibernate-enum bug we caught in stage and asked: "If that had been in prod for 30 minutes, what would the rollback have cost?" The number landed.

**Q: What if Flagger had auto-rolled back?**
> Plan was: read the trace, find the failing endpoint, fix in code, redeploy to stage, re-run the canary. Old 2.7 pods stayed serving 100% traffic the whole time.

**Q: When would you skip the canary?**
> Single-line config flips on a service we deploy daily. The risk surface needs to justify the canary cost.

**Q: Did you over-engineer this?**
> 158 files, three framework boundaries (Spring, Java, Hibernate), one cross-region failover path. I don't think one extra day of rollout was over-engineering for that surface area.

---

## What NOT to say

- Don't make the senior look bad. They had a reasonable instinct; I had specific data they didn't.
- Don't say "I just trusted my gut." The whole point is the data showed canary was right.
- Don't claim Flagger is always required. It's required when the change surface is large.

---

## Backup story (if asked for another)

During the audit library code review, a senior asked me to ship the default `AbortPolicy` for the audit thread pool's queue. Faster, simpler. I pushed back: with `AbortPolicy` and our existing exception swallow, dropped audit records would be silently lost. I refused to merge until I'd added a Prometheus counter for rejected tasks plus a WARN log at 80% queue depth. That instrumentation has caught a downstream slowdown twice — both times before any data was actually dropped.
