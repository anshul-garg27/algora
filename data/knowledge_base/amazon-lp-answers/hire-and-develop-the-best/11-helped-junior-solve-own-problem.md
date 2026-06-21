# Q: Describe a time you helped a junior solve their own problem instead of solving it for them.

> **LP**: Hire and Develop the Best
> **Primary story**: `W11 — resisted writing the resolver, drew schema on whiteboard, let him implement`
> **Backup story**: `W2 — taught the audit-library integration via office hours, didn't write their code`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Week two of pairing with the SDE-1. He'd been assigned the credential-rotation resolver — supplier rotates an API key, we call DataSharing API to generate a new credential, mark the old one REVOKED in Postgres, audit the change in `headless_notification_audit`. The supplier demo was Friday. It was Tuesday. He hadn't started.

### Task

The easy path was to write the resolver myself. I'd done credential rotation before in a different service — maybe 90 minutes of work. The hard path was to let him write it, slower, and have it land less polished. The temptation was real because the demo had stakes.

### Action

I didn't write it. I told him I'd help him design it instead.

I asked him to walk me to the whiteboard. We drew the request flow. Supplier hits the rotate mutation. GraphQL BFF validates the JWT, extracts `siteId`. Calls our Spring Boot auth-policies service. We call DataSharing. Postgres update. Audit row.

He drew it. I asked questions instead of corrections. "What happens if DataSharing returns success but Postgres update fails?" He thought for a minute. Said, "we'd have a real credential the supplier can use, but our DB thinks the old one is still active." Right. So we drew the compensating transaction — try-catch around the Postgres update, on failure call DataSharing again to revoke the new credential.

Then I asked, "what if both fail?" He thought longer. Said, "we'd need a reconciliation job." Right. So we drew the nightly cron — find credentials in DataSharing that don't have a matching `credential_id` reference in our Postgres, close them.

I gave him exactly one piece of unsolicited input the whole session. When he drew the rotation, he had it as a single transactional method. I said: split it into three — DataSharing call, DB update, audit insert. Each one logs separately. If something fails in production you want to see which call broke.

Then I told him: now go write it. I'll be at my desk. Don't ping me unless you've thought about a question for 90 minutes.

He pinged me twice that afternoon. Both were real questions — one on `@Transactional` propagation, one on whether to throw or return an error code from the compensating path. Both took less than five minutes to resolve.

He shipped Thursday. Demo went clean Friday.

### Result

The rotation flow is still in production. The compensating-transaction logic he wrote that day caught a real failure three months later — DataSharing had a flaky window, two rotations failed mid-flight, his reconciliation job cleaned both up overnight. Zero supplier-visible impact.

The deeper result is the technique. He now does the whiteboard-first thing when he mentors the next SDE-1. He told me he stole the "now go write it, don't ping me unless you've thought for 90 minutes" line word for word.

The thing I almost did was the wrong thing. If I'd written the resolver Tuesday afternoon — even with the demo pressure — he'd have lost the most valuable design exercise of his first six months. Demos are recoverable. Lost learning isn't, easily.

---

## Technical depth — if they probe

- **The compensating-transaction pattern**: Distributed writes across external systems (DataSharing) and local DB. Can't get atomic. So: on local failure, undo the external action. On both failing, reconciliation job picks it up.
- **Why three-step split, not one**: Independent logging per step. In production logs you can see exactly which call broke. Single method with one try-catch eats that signal.
- **Why I told him 90 minutes**: A real bug deserves a real attempt before pulling someone in. Less than 90 and you're just outsourcing thinking. More than half a day and you're stuck for ego reasons.

---

## Likely follow-ups

**Q: Did the demo work?**
> Yes — Thursday ship, Friday demo, clean. The compensating transaction was even part of the demo because the product manager wanted to see what happened on failure.

**Q: What if the demo had failed?**
> Then we'd have rolled back to the previous credential-rotation flow (manual, but working) and shipped his fix the next sprint. The demo was important, not load-bearing.

**Q: How is whiteboarding different from telling them the answer?**
> When I ask "what happens if X fails?" they find the failure mode themselves. When I tell them, they nod and forget. The retention difference is huge.

**Q: When do you just give them the answer?**
> When the problem is below them — wiring up a library, fixing a config typo. Don't waste their cognitive load on those. Save the discovery work for the design and debugging problems.

---

## What NOT to say

- Don't claim credit for the compensating-transaction design — that was his
- Don't make whiteboarding sound mystical — it's just asking questions instead of giving answers
- Don't say "I never write code for juniors" — that's not true and not even right. Pick your spots.
- Don't gloss over the demo pressure — the answer is more credible when the temptation was real

---

## Backup story (if asked for another)

During the audit-logging library rollout, twelve teams needed to integrate. I ran Friday office hours instead of writing the integration code for them. One engineer kept getting `isAuditLogEnabled=false` errors. Instead of fixing the CCM config myself, I had him share his screen and walk through CCM portal — he found his own typo in about three minutes. He never made that mistake again.
