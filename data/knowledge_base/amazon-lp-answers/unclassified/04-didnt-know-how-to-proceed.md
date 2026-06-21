# Q: Tell me about a time when you didn't know how to proceed — how did you figure out, and how did you consider the options.

> **LP**: Unclassified (Are Right A Lot + Bias for Action + Learn and Be Curious)
> **Primary story**: W4 — Multi-Region Rollout (vague "make it resilient" ask)
> **Backup story**: G1 — ClickHouse Migration choice
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Early 2025. Compliance review came back with one line — our audit-logging system had to be "resilient" against regional failures. That was the brief. No RTO, no RPO, no budget, no timeline. My skip-level wanted it done "soon".

I'd never designed a multi-region system before. The audit platform was single-region — EUS2 Kafka cluster, single GCS bucket, single Kafka Connect deployment. Resilient could mean anything from "second region as cold standby" to "synchronous Active/Active write to both regions". The cost difference between those was 4x.

### Task

I had to figure out what "resilient" actually meant, pick a design I could defend, and ship it — without going back to leadership six times asking for clarification.

### Action

I broke the unknown into smaller knowns.

**First, I cleared up what I didn't know.** I wrote a single page listing every term I needed nailed down — RTO, RPO, budget ceiling, must-have regions, deadline. Each one got my best guess and the label "assumption". RPO assumption: 4 hours max gap. RTO assumption: 1 hour to recovery. Regions: EUS2 + SCUS. Budget: assume infra cost can roughly double, not triple. Deadline: this quarter.

**Second, I designed three options and made the costs concrete.**
- Active-Passive — cheap, ~30 min cold-start failover, fine for RPO but borderline on RTO.
- Active-Active — 2x infra, instant failover, easy to reason about during incidents.
- Hybrid Active-Active writes with single-region reads — half-baked, kept it in the list as a strawman.

For each one I wrote down: monthly infra cost delta, complexity score (1-5), failure modes, and one paragraph of "what an incident at 3 AM looks like for the on-call".

**Third, I let the experts correct me.** I booked 30 minutes with my lead. Walked through the doc. Single question — "where are my assumptions wrong?" He pushed back on the RPO (compliance actually wants 4 hour gap, my guess was right), pulled the RTO down to 30 minutes (he had context I didn't on a recent outage), and confirmed budget could double. Twenty minutes in, the spec was real.

**Fourth, I committed.** Active-Active. Phased rollout — Week 1 publisher in second region, Week 2 GCS sink, Week 3 data parity check, Week 4 routing on `wm-site-id` header, Week 5 controlled failover drill.

### Result

Active-Active live in five weeks. Zero downtime, zero data loss. Failover drill: 15-minute recovery, well inside the 30-minute target. The doc became the template the team uses now for any vague-brief project.

The deeper thing I learned — "I don't know how to proceed" usually means "I have too many unknowns to do anything", which usually means "I haven't broken the unknowns down". The fix is almost always: list the unknowns, make a guess on each, find the person who can correct the guesses cheap, and commit once enough are nailed down.

---

## Technical depth — if they probe

- **Why Active-Active over Active-Passive**: audit logging is write-heavy and write-bursty. Passive means cold consumers, cold connections, cold-cache GCS Sinks. 30 minutes was optimistic; my guess on a real failover was closer to 45. With a 30-minute RTO target, the math didn't work.
- **Geography-based routing on `wm-site-id`**: every Walmart audit event has a site header — US, CA, MX. Routing on that header keeps cross-region traffic minimal and makes the failover blast-radius obvious during an incident. Round-robin would've been cheaper to implement but a nightmare for the on-call at 3 AM.
- **Why the 30-minute lead sync, not a long design review**: long design reviews give you everyone's preferences but no decisions. A focused 1:1 with the person who can correct your assumptions gets you to commitment fast.

---

## Likely follow-ups

**Q: How did you decide what counted as "enough" assumptions to commit?**
> Two filters. One — does the decision change if this assumption is wrong by 50 percent? If yes, I need to nail it down. If no, I can guess. Two — can the assumption be tested cheaply post-launch? RPO/RTO had to be exact upfront. Sink batch sizes I could tune in production.

**Q: What if your lead had pushed back hard on Active-Active?**
> I had option 4 in my back pocket — Active-Passive with hot consumers (no cold-start, faster failover). I didn't bring it up because options 1-3 covered the space well enough. If he'd hated all three, I'd have introduced it in the same meeting.

**Q: Was there a moment you nearly got stuck?**
> Yes — the routing question. Geography-based vs round-robin vs latency-based. I didn't have latency data for cross-region calls. I almost spent a week building a benchmark. Instead, I picked geography-based, marked "if latency proves bad in week 5 we revisit", and shipped. It never proved bad.

**Q: How did you avoid analysis paralysis?**
> The 1-page doc forced concreteness. I gave myself two days to write it — couldn't extend. Once it was written, the lead sync was on the calendar. The deadline pressure broke the paralysis.

**Q: Have you used this pattern since?**
> Yes — twice. Once on the supplier self-service work where the exec brief was "give Pepsi access to their data". Once on the Spring Boot 3 .block() decision. Same shape: list unknowns, guess, sync with the corrector, commit.

---

## What NOT to say

- Don't pretend you knew exactly what to do from the start. The honest "I'd never designed multi-region before" opener is what makes the story land.
- Don't sound paralysed — the question is about *handling* not knowing, not failing to know.
- Don't make the lead sound like the hero. The lead corrected, you made the call.
- Don't skip the failover-drill detail (15 min vs 30 min target). That's the result that proves the design worked.

---

## Backup story (G1 — ClickHouse migration choice)

At GCC, our Postgres event-logging was choking — write saturation at ~10M logs a day, query times falling apart. I didn't know whether the right answer was sharding Postgres, moving to Cassandra, ClickHouse, or building a custom indexing layer. Same approach — wrote a one-page doc with three options (shard Postgres, ClickHouse via RabbitMQ buffered sinker, Cassandra), cost math for each, query-time benchmarks on a sample dataset. Defended ClickHouse over an external advisor who pushed Kafka. Shipped with a 2-week dual-write window. 2.5x faster reads. Same pattern — break the unknown down, guess, get corrected cheap, commit.
