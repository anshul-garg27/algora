# Q: How did you approach it?

> **LP**: Unclassified (follow-up question, not a fresh STAR)
> **Primary story**: W1 — Silent Kafka Failure (5-day debug)
> **Backup story**: G1 — ClickHouse Migration approach
> **Time budget**: 60–90 seconds spoken (it's a follow-up, not a fresh STAR)

---

## How to read this question

"How did you approach it" is almost never the opening question. It's a **follow-up** after you've already told a story. The interviewer is checking whether you have a systematic process or whether you got lucky.

So the answer is shorter than a fresh STAR. You skip situation and task — they already heard those. You go straight to the **approach**, broken into the actual steps you took, in the order you took them.

The example below assumes they've just heard the W1 silent Kafka failure story and asked "so how did you approach the debugging".

---

## The spoken answer (60–90 sec)

Five days, but the approach was the same five steps each day, looped.

**Step one — narrow the failure surface.** Day one, I checked the obvious. Was Kafka Connect running? Yes. Were messages in the topic? Yes, millions backing up. So the failure was somewhere between consumption and the GCS write. That cut the search space by roughly 80 percent.

**Step two — make the system tell me what it's hiding.** Day two, I cranked DEBUG logging on the SMT filters. That surfaced a `NullPointerException` on records with null headers — legacy data the schema didn't expect. Patched with a try-catch defaulting to the US bucket if the header was missing.

**Step three — patch, ship, observe.** Deployed the SMT fix. Watched whether the backlog moved. It didn't. That meant the SMT was one bug among several, not the only one.

**Step four — correlate with adjacent systems.** Day four, the breakthrough wasn't in the application logs. It was in Kubernetes events. KEDA was scaling the consumer pool up every time lag increased. Scale-up triggered Kafka consumer-group rebalancing. Rebalancing caused more lag. More lag triggered more scaling. A feedback loop. Disabled KEDA, switched to CPU-based HPA.

**Step five — keep going until the metric flatlines.** Day five, the remaining issue was JVM heap exhaustion — default 512 MB OOMing on large Avro batches. Bumped to 2 GB. The backlog cleared in 4 hours.

The thing that made the five steps work — I wrote down every hypothesis and every result on the same Confluence doc. That doc became the runbook. Two other teams have used it since.

---

## Why this works as a follow-up

- **Short** — 60–90 seconds. You're answering "how", not retelling the story.
- **Step-by-step**, but not robotic. Each step has a real action, a real outcome, and a decision rule for whether to move on.
- **The runbook detail at the end** is the meta-answer to "how" — your approach included writing it down as you went. That signals systematic.
- You can substitute any story they ask "how did you approach it" about — the shape is the same.

---

## Technical depth — if they probe

- **Step 1 (narrow the failure surface)**: classic bisection. Kafka Connect running ✓, messages in topic ✓, GCS not receiving — failure is in consumption-or-write. Eliminates publisher, library, source API.
- **Step 2 (DEBUG logging)**: SMT filters in Kafka Connect process every record. NPE on null headers was silent because `errors.tolerance: all` was set — messages dropped without alerts. Try-catch + default-to-US route fixed the NPE; later I changed `errors.tolerance` to `none` for compliance-critical sinks.
- **Step 3 (patch, observe)**: this is the discipline that catches multi-bug situations. If I'd assumed the SMT fix was THE fix and walked away, I'd have been paged again 6 hours later.
- **Step 4 (correlate with adjacent systems)**: the KEDA feedback loop wasn't visible in any single log stream. Found it by sitting next to the SRE on call and walking through k8s events alongside Kafka consumer-group state. Cross-system correlation needs cross-team eyes.
- **Step 5 (JVM heap)**: 512 MB default + large Avro batches + heavy `String` deserialization = OOM. Bumped to 2 GB initially, later 7 GB after profiling with `jmap -histo:live`.

---

## Variants — how the same approach maps to other stories

If they ask "how did you approach it" about a different story, the five steps shift slightly:

### G1 — ClickHouse migration
1. Narrow the problem: writes saturating, not reads. Postgres write capacity was the bottleneck.
2. Make the system tell me: `pg_stat_statements` to find write-heavy queries; query latency p99 by table.
3. Patch, observe: tried Postgres tuning first. Got 20% improvement, not enough. Confirmed sharding wouldn't help either.
4. Correlate: looked at query patterns — 90% were time-range aggregations, which is ClickHouse's strength. Match found.
5. Keep going until the metric flatlines: dual-write for 2 weeks, validate read parity, cut over. Reads 2.5x faster, writes stable.

### W5 — Spring Boot 3 migration
1. Narrow: three categories of changes — javax→jakarta (mechanical), RestTemplate→WebClient (design), Hibernate 6 enums (config).
2. Make the system tell me: ran the build, captured every error class, grouped them.
3. Patch, observe: per category, fix in one service first, validate, propagate.
4. Correlate: stage environment for 1 week, watch JVM memory + p99 latency for regressions.
5. Keep going: Flagger canary 10→25→50→100 with auto-rollback on error rate > 1%.

---

## Likely follow-ups

**Q: What if step one had been wrong?**
> I'd have re-bisected. The point of step one is to commit cheaply — narrow the surface, then validate quickly. If I'd been wrong about "issue is between consumption and write", the messages-in-topic check would've told me.

**Q: When did you know you were on the wrong track?**
> Whenever a patch shipped and the metric didn't move. That's the "patch, observe" loop. If the metric doesn't move after a patch you believed in, you have another bug. Walking away early is the failure mode.

**Q: Did you involve anyone else?**
> Yes — day 4, I pulled the SRE on-call into a screenshare for the Kubernetes events correlation. Earlier than that I was deep enough alone that I didn't need it. The "going deep without surfacing" pattern is the one thing I'd do differently — I should've looped someone in around day 2 or 3.

**Q: How did you decide which bug to fix first?**
> Order of evidence, not order of importance. The NPE was first because it was the loudest signal. If I'd known KEDA was the biggest one, I'd have gone there first — but I didn't, so I followed the breadcrumbs.

---

## What NOT to say

- Don't retell the full STAR. They've heard it. Go straight to the approach.
- Don't claim you had the runbook written before you started. The doc emerged during the debug, not before.
- Don't pretend the five steps were planned in advance. They were the pattern that emerged across five days, which is what makes them transferable.
- Don't go past 90 seconds. This is a follow-up, not a fresh question.

---

## Backup story (G1 — ClickHouse migration approach)

See the variant above. Same five-step shape — narrow, instrument, patch+observe, correlate, keep going until the metric flatlines. The discipline of writing down every hypothesis and every result on a shared doc carried across both — at GCC the doc became the migration plan; at Walmart it became the runbook.
