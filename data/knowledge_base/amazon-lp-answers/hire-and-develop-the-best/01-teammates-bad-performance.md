# Q: Describe a time when a teammate's bad performance affected your own work.

> **LP**: Hire and Develop the Best
> **Primary story**: `W11 — Unified Onboarding / IAM`
> **Backup story**: `W2 — Shared Library Adoption`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Mid-2024, I was the SDE-3 on the unified onboarding platform at Walmart Data Ventures. Apollo Federation BFF in NestJS, two Spring Boot 3.5.5 services behind it. A new SDE-1 joined and was assigned the credential-mgmt subgraph. He was bright, but his first resolver shipped to staging and triggered an N+1 query storm. Every supplier list call was hitting Postgres 50 times.

### Task

I was blocked. My principal-onboarding flow depended on his subgraph returning in under 200ms p95. It was returning in 2.5 seconds. I had two real choices: take the work back, or actually invest in him.

### Action

I took it back for one day to unblock the demo. Then I told him I was giving the subgraph back to him with help, not without it.

I sat with him on a Tuesday after standup. Pulled up his resolver in IntelliJ. I didn't fix anything yet. I asked him to walk me through what he expected the query plan to look like. He drew it out and we both saw the gap. Apollo Federation resolves each entity reference one at a time, so his nested `credentials { product { name } }` was firing one SELECT per row.

I drew the schema on a whiteboard. Showed him DataLoader. Showed him the batch loader pattern. He went and wrote the fix himself the next day. I reviewed it line by line in the PR, left maybe twelve comments, half of them praise.

Then I changed the routine. We blocked one hour every day, 10 to 11 AM, for six weeks. His work, his keyboard. I watched, asked questions, never typed.

### Result

By week four his PRs were landing without rework. By week six he owned the entire credential-mgmt subgraph and the on-call rotation for it. p95 dropped from 2.5 seconds to about 180ms. Honestly, the bigger win for me was getting two hours of my own day back — I stopped having to review every change twice.

---

## Technical depth — if they probe

- **The N+1 root cause**: Apollo Federation's `@key` directive resolves entity references one at a time. Without DataLoader batching, every nested field triggers a separate downstream call. He had `principals { credentials { product } }` — 50 principals meant 50 product lookups.
- **Why I didn't just fix it**: One fix doesn't build a senior engineer. He'd hit the same shape of problem on the next subgraph. The hour-a-day pairing was cheaper for me long-term than reviewing every PR twice.
- **What I gave him to read**: Apollo Federation docs on `@key` and reference resolvers, then the DataLoader README. In that order — concept first, library second.

---

## Likely follow-ups

**Q: How did you decide to invest rather than escalate?**
> His instincts on the schema were right. The miss was a knowledge gap on Apollo Federation, not on engineering judgment. Knowledge gaps close with hours. Judgment gaps don't.

**Q: Did you talk to his manager?**
> I told his manager I was pairing daily and I'd flag in two weeks if it wasn't moving. It was moving. I gave a positive read at the two-week mark and a stronger one at six weeks.

**Q: What if pairing hadn't worked?**
> I had a tripwire. If by week three he wasn't writing review-ready PRs, I'd escalate to staff a different owner. I didn't want to spend six months propping someone up.

**Q: Did this slow your own work?**
> First two weeks, yes — about 25% slower. After that I gained time back because I trusted his PRs and stopped double-checking everything.

---

## What NOT to say

- Don't call him "bad" — say "early in his career" or "new to GraphQL"
- Don't take credit for his fix — the DataLoader code was his
- Don't make it sound like I was the hero who saved the project — frame it as an investment
- Don't say "I had to do his work" — it sounds resentful and missed the mentoring beat

---

## Backup story (if asked for another)

When I shipped the shared audit-logging library, two team leads pushed back hard — they wanted to keep their own forks. Their forks had three known bugs. I sat with each lead for a 45-minute walkthrough, fixed one of their pet bugs as part of the migration, and the library moved from one team to twelve in a quarter.
