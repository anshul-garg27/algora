# Q: Tell me about a time when you could not meet a deadline.

> **LP**: Deliver Results
> **Primary story**: `W4 — Multi-Region Rollout`
> **Backup story**: `W5 — Spring Boot 3 Migration`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Mid 2025. Leadership came to me with a vague ask — "make the audit pipeline resilient." No RTO. No RPO. No budget. The only hard constraint was "do not lose audit data." A senior director had committed to a peer team that we would have multi-region active/active in four weeks. The director told my manager. My manager told me. The four weeks was already in someone's plan when I heard it.

I came back two weeks in and said the four-week date was not realistic. I committed to five weeks instead.

### Task

Own the slip honestly, defend the new date with data, and ship a multi-region active/active rollout that did not lose any audit data during cutover.

### Action

The first thing I did was push back on the input, not the deadline. The requirements were too vague to plan against. I wrote an assumptions doc — RTO under 30 seconds, RPO zero, budget around $3,500/month, three alternatives priced (Active/Passive at $2K, Active/Active at $3.5K, no-DR at $1.2K). I sent it to leadership and asked them to either approve or push back. They approved Active/Active inside two days. That doc became the requirements spec.

Then I planned the real work. Four phases.

Phase 1, week 1 — deploy the publisher to the second region (SCUS) writing to both Kafka clusters via dual-write. EUS2 was the primary. Replication factor 3, 12 partitions, idempotent producer.

Phase 2, week 2 — deploy the GCS sink in the second region with its own Connect cluster. Same SMT filter, same Avro schema.

Phase 3, week 3 — data parity validation. Daily diff of GCS bucket counts across regions and per-partition offset comparison. I needed three consecutive clean days before I would flip routing.

Phase 4, week 4 — flip routing to geography-based on `wm-site-id` (US → EUS2, intl → SCUS depending on market) and run a deliberate failover test.

Week 3 was where the slip happened. The data-parity diff showed about a 0.02% delta — duplicate messages from the idempotent producer behaving differently across regions during retry storms. Not lost data — extra data. We had to add deduplication in the sink based on `request_id` before I could flip routing. That fix added a week.

The moment I knew — Tuesday evening of week 3. I emailed my manager and the director that night. Not Slack — email, because the original commitment was on email and I wanted the change of date on the same thread. New date: end of week 5 instead of week 4. Reason in two sentences. Mitigation plan in three bullets. I did not ask for permission. I committed and gave them the new date with the reasoning.

### Result

Active/Active shipped end of week 5. Failover 25 seconds in production, RPO zero across three real failovers in the first six months. The 0.02% duplicate-message rate stayed inside contract. Zero customer-visible audit data loss. The director sent a follow-up note when the failover test passed and said the assumptions doc had been a better artifact than what other teams had given him. The thing I learned — a vague "make it resilient" ask is the deadline trap. Write the assumptions doc first, get leadership to sign it, then estimate. The week I lost on dedupe was real engineering. The four-week date was never realistic — I just inherited it before I had built it.

---

## Technical depth — if they probe

- **Idempotent producer + dedupe**: Idempotency dedupes within a single producer session. Cross-region writes from different sessions can duplicate. Added consumer-side dedup on `request_id` in the SMT filter.
- **Geography routing**: `wm-site-id` header drives region selection — US → EUS2, intl → SCUS, with cross-region fallback if primary is unreachable.
- **Failover mechanics**: `CompletableFuture` chain — primary `.thenAccept().exceptionally(secondary)`. If both fail, throw `NrtiUnavailableException` so caller knows. PR #65 (the failover-logic fix that pre-dated this work).
- **Cost numbers**: Estimated $3,500/month, actual $3,200/month, under budget.

---

## Likely follow-ups

**Q: Why did the original 4-week date exist?**
> A senior director had committed it to a peer team before talking to engineering. Common pattern — date arrives before estimate.

**Q: How did you communicate the slip?**
> Email on the same thread as the original commitment. Two-sentence reason, three-bullet mitigation. Not Slack, not standup. The thread matched the audience.

**Q: What did the assumptions doc save you from?**
> Endless scope creep. Once leadership signed RTO < 30s and RPO = 0, every later "can we also..." had to either fit those numbers or come with budget.

**Q: What would you do differently?**
> Run the data-parity diff in week 1 against synthetic load, not in week 3 against real traffic. Would have caught the dedupe gap earlier.

---

## What NOT to say

- Do not say "the deadline was unrealistic" without acknowledging that you owned the new date.
- Do not skip the assumptions doc — that is the mechanism that made the slip survivable.
- Do not blame the director. The vague ask is a normal input. The job is to convert it.

---

## Backup story (if asked for another)

W5 — Spring Boot 3 migration. Committed to a 2-week PR. Shipped in 3. WebClient test-mock refactor across 42 test files was the gap. Told my manager same day, daily progress doc, audit deadline still hit because I had already cut scope on reactive via `.block()` early in the plan.
