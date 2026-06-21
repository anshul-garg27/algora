# Q: Describe a time you identified high potential in someone.

> **LP**: Hire and Develop the Best
> **Primary story**: `W11 — junior's first whiteboard session, design instincts visible`
> **Backup story**: `G7 — peer who picked up Go fundamentals in two weeks`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

The new SDE-1 had been on the team five days. His tech lead had asked me to mentor him on the credential-mgmt subgraph. I'd been told he was from a mechanical engineering background, six months of Node.js, first real SDE role. I came into his first whiteboard session prepared to walk him through everything slowly.

### Task

The session was supposed to be me explaining the principal-product junction table — many-to-many mapping between suppliers and data products like Cloud Feeds and NRT APIs. I was going to draw the schema and talk him through it.

### Action

I asked him to draw it first. Just to see where his head was at.

He drew it in about four minutes. Two entity tables, a junction table with a composite unique constraint on `(pid, product_id)`, an `is_active` flag instead of soft-delete. That last choice was the one that caught me. He didn't know our codebase conventions — he'd inferred from how the principal table worked that we used status enums and `is_active` flags, not `deleted_at` timestamps. He'd noticed the pattern in his five days.

I asked him why. He said, "status enums are richer than booleans. A credential can be PENDING, ACTIVE, EXPIRED, REVOKED. Soft-delete loses that." That was the actual answer I'd have given.

I changed the plan for the session. Instead of walking him through the schema, I asked him to design the cursor pagination for the credential list. He'd never written cursor pagination before. He took 20 minutes. He came back with offset pagination as a first cut.

I told him to think about what happens during concurrent writes. He paused, thought, then said: "offset breaks because the rows shift. I need a stable anchor." He landed on cursor pagination on his own. We just needed to walk through the composite-cursor trick — `(created_at, id)` for the tiebreaker.

Three things I noticed in that first session. He extrapolated patterns from the codebase quickly. He gave reasons for design choices instead of cargo-culting. And he course-corrected when I challenged him without getting defensive. That's a senior trait at SDE-1.

### Result

I told his tech lead the next day: this one has staff-engineer instincts, just no exposure. Let me invest. We blocked one hour every weekday for six weeks. By week six he owned the subgraph. His promotion case for SDE-2 went up four months ahead of cohort and cleared without debate.

The signal I trust most: a year in, he's now mentoring the next SDE-1 the same way. That recursion is the real test.

---

## Technical depth — if they probe

- **What "design instincts" looked like**: He chose `is_active BOOLEAN` plus status enum over `deleted_at` timestamp, with the right reasoning — richer lifecycle states.
- **The cursor pagination moment**: He hit offset first (normal), then identified the concurrent-write issue (good), then designed his way to cursor (rare for an SDE-1).
- **What I didn't read into**: His Node.js was rough at first. Syntax is teachable. Schema instinct isn't, easily.

---

## Likely follow-ups

**Q: What if you'd been wrong about him?**
> The investment was one hour a day. Worst case I'd have wasted 30 hours over six weeks and learned where the ceiling was. Cheap experiment.

**Q: How do you separate potential from current skill?**
> Skill shows in code quality. Potential shows in how someone reacts to being wrong. Defensive means low ceiling. Curious means high ceiling.

**Q: Did anyone disagree with your read?**
> One other senior thought he was too quiet to be senior material. I pointed out that quiet on day five is normal. By month three he was running design reviews — the quiet was uncertainty, not absence.

**Q: How did you advocate for him?**
> When his promotion case came up, I wrote the technical recommendation. I cited specific design choices — the composite cursor, the compensating transaction for orphaned ServiceNow tickets — and quoted the code. Specifics beat adjectives.

---

## What NOT to say

- Don't say "I knew right away" — that sounds performative. Say "I noticed three things in the first session"
- Don't make it sound like I discovered him single-handedly — his tech lead asked me to look
- Don't oversell — say "staff instincts, no exposure", not "the best engineer I've worked with"
- Don't skip the recursion line — him mentoring others is the proof, and it lands

---

## Backup story (if asked for another)

At GCC, the engineer who joined as my peer on the Coffee API had never written Go. Two weeks in he was correcting my goroutine patterns. He'd read Effective Go cover to cover on his own. I told my lead that hire was undervalued and pushed for him on the next architectural project.
