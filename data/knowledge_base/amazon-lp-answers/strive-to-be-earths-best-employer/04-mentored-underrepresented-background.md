# Q: Describe a time you mentored someone from an underrepresented background.

> **LP**: Strive to be Earth's Best Employer
> **Primary story**: `W11 — non-CS-degree junior, first SDE role, calibrated approach to fundamentals`
> **Backup story**: `W2 — supported integration leads from smaller teams during library rollout`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Summer 2024. The SDE-1 who joined our unified-onboarding team had a mechanical engineering degree and a bootcamp behind him — no CS undergrad, first SDE role, six months of Node.js. On a team where most of us had CS degrees from the standard top engineering colleges, he was the outlier on paper. The risk wasn't that he couldn't do the work. It was that the team's defaults — vocabulary, design-review pace, assumed reading list — wouldn't meet him where he was.

### Task

His tech lead asked me to mentor him on the credential-mgmt subgraph. I had to figure out the right calibration. Pitch too high and he'd nod through everything and learn nothing. Pitch too low and I'd insult him. Both failure modes were real.

### Action

I asked him directly in our first session: what do you already know, and what's the vocabulary you've been faking. He told me. He knew JavaScript well, Postgres well enough to write queries, had heard of ACID but couldn't define it, didn't know what a B-tree index actually did. He'd been nodding through "we use a B-tree on `(site_id, principal_id)`" without knowing what that meant.

That honest map was the most useful thing he gave me. I tuned to it.

For each new concept that came up in real work, I did one of three things. If it was load-bearing for his current task — like Apollo Federation `@key` directives — we'd walk through it together with the actual code in front of us, not from a textbook. If it was background — like Hibernate filter mechanics — I'd send a one-page doc with our codebase's specific example, not a generic tutorial. If it was deep fundamentals — like B-trees — I told him: don't try to learn it now, just know it's a sorted on-disk data structure with O(log n) lookups, and we'll come back when it matters.

The last one mattered. He'd been bookmarking every concept anyone mentioned and trying to study them all on weekends. He was burning out on stuff that wasn't going to land. Giving him explicit permission to *not* learn something yet freed up his cognitive load.

I also did one thing that wasn't about the technical mentoring at all. I introduced him to two engineers in the org who had non-traditional backgrounds — one ex-physics PhD, one self-taught — both now staff engineers. Coffee chats, not formal mentorship. He came back from those saying it was the first time he'd seen people who looked like his path in senior roles at the company. The imposter feeling didn't go away after that, but it got quieter.

For code review, I held him to the same bar as anyone else. Same standard for tests, same standard for design. The calibration was on the *pacing*, not the bar. He took longer to get there. He got there.

### Result

By month six he was owning the credential-mgmt subgraph. By month ten his SDE-2 case was up — four months ahead of cohort. A year in, he's mentoring the next SDE-1 who joined, who also doesn't have a CS undergrad.

The thing I notice: he's better at meeting his mentee where they are than I was. Because he had to do it for himself, he sees the gaps faster.

The thing I'd do differently — I should have introduced him to the staff engineers in week two, not month two. The technical mentoring helps. Seeing people with your background at the level you're trying to reach helps in a different way.

---

## Technical depth — if they probe

- **Why I asked what he was faking**: Most onboarding fails because no one ever surfaces the actual knowledge gaps. He had to know I wasn't going to judge him for saying "I don't know what ACID means."
- **Why the three-tier triage**: Load-bearing learning has to happen now. Background can wait for a slow week. Deep fundamentals only matter when they hit your work.
- **Why the coffee chats mattered**: Modeling beats lecturing. Seeing a staff engineer who came in through a non-standard path does more than ten "you can do it" conversations.

---

## Likely follow-ups

**Q: Did you adjust the bar for him?**
> No. Same bar. I adjusted the pace and the scaffolding to get him to the bar. Adjusting the bar would have made the promotion meaningless.

**Q: How did you separate background gaps from ability gaps?**
> Background gap looks like: doesn't know the vocabulary, gets it in one conversation. Ability gap looks like: gets the vocabulary, can't apply it after multiple attempts. He had the first, not the second.

**Q: What if he had been an ability-gap case?**
> Different conversation, with his tech lead, at the six-week mark. Mentoring can't fix that — only honest feedback and a real plan can.

**Q: How do you mentor someone whose background you don't share?**
> Ask. Don't assume. The honest map he gave me in week one was 90% of the calibration. Without it I'd have been guessing.

---

## What NOT to say

- Don't make this a feel-good story — keep it specific to what I actually changed in my mentoring approach
- Don't say "I treated him the same as everyone" and stop — the calibration matters, and saying I didn't calibrate would be dishonest
- Don't claim I single-handedly fixed his career — the coffee chats with the staff engineers did real work too
- Don't skip the "I should have done X earlier" — it makes the answer credible

---

## Backup story (if asked for another)

For the audit-logging library rollout, the integration leads on smaller teams had less Spring Boot depth than the leads on the bigger teams. I made sure my Friday office hours weren't dominated by the deeper questions — I'd ask the basics-level team to share their screen first, so we covered "how do I add a dependency" before "should we tune the thread pool." That pacing change kept the smaller teams from dropping out.
