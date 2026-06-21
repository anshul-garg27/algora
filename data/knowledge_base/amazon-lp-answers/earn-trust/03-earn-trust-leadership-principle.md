# Q: Questions based on the 'Earn Trust' leadership principle.

> **LP**: Earn Trust
> **Primary story**: `W2 — Shared Library Adoption`
> **Backup story**: `W11 — Unified Onboarding / IAM`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Late 2024 at Walmart. Splunk was getting decommissioned. Three teams — mine, Inventory Status, Transaction Events — all needed audit logging for our supplier APIs before that deadline. I noticed each team was about to build it themselves. Three different shapes for the same problem.

I wanted to propose a shared library. The risk: I was the new senior on the team. The other team leads were senior engineers with more years at Walmart than me. "Hey use my library" was going to land badly.

### Task

Build something the other teams would actually adopt — not just accept on paper. Without authority over those teams.

### Action

I didn't lead with a solution. I scheduled 1:1s with the lead engineer on each team. Came in with questions, not slides. "What endpoints do you need to audit? What format do you expect? What's your latency budget? What does your auth look like?" I took notes and didn't pitch.

The pushback was real. One lead said "our needs are different" — and he wasn't wrong. His team wanted response-body logging. The other team didn't, because of payload sizes. One had strict latency budgets, the other was looser.

I went away and built a prototype that handled their 80% — the common shape — and made the 20% configurable. Response body logging became a CCM flag. Endpoint filtering used regex from CCM. Their teams could turn knobs without code changes.

I came back with the prototype, not the spec. Showed it running, showed how their team would configure it for their stack. That changed the conversation. Both leads went from "we'll evaluate" to "let's pilot."

Then I did the work of actually getting them integrated. Brown-bag session for the wider eng group. An afternoon pairing with each team on their first PR. When they hit issues, I fixed and released same-day. That last part — being responsive — is what built the trust. The library was decent. The fact that I treated their adoption like my own deadline is what made it stick.

### Result

Three teams adopted within a month. Integration time dropped from 2 weeks of custom code to about a day. The library became the standard for new services. One of the engineers I'd helped — the one who'd initially pushed back hardest — later helped onboard a fourth team without me being involved.

The trust wasn't in the library itself. It was in showing up to their integration the way I'd show up to my own.

---

## Technical depth — if they probe

- **The 80/20 design**: Servlet filter with `OncePerRequestFilter`, `@Order(LOWEST_PRECEDENCE)` so it runs after security filters, `ContentCachingWrapper` for body capture, `@Async` for non-blocking publish. Common to all teams. CCM-driven flags handled the 20% that differed.
- **CCM (Cloud Configuration Management)**: Walmart's runtime config service. Teams flip flags without redeploys. Critical for "configurable" actually meaning configurable.
- **Why a library, not a sidecar**: Sidecars run at the network layer and can't see application context — which endpoint, which supplier, what the error meant. That context only exists inside the app.

---

## Likely follow-ups

**Q: What if one team had said no?**
> They almost did. The lead who pushed back hardest was the one whose 20% was furthest from the common path. The prototype with his flags toggleable is what got him in. If he'd still said no, the library would've shipped for two teams — that's fine, the third team isn't worth bending the design.

**Q: How did you handle the latency concern?**
> Showed load-test numbers — async publish with bounded thread pool added <2ms to P99. Numbers, not assurances.

**Q: Did the configurability come with a cost?**
> Yes. The library is more complex than a single-team version would be. The trade is worth it — three teams' integration time dropped from 2 weeks to a day each.

**Q: What did you learn about earning trust without authority?**
> Show up like you own their problem. Brown-bag was fine, but pairing on their PRs is what actually built trust. Words are cheap; treating their adoption like my deadline isn't.

---

## What NOT to say

- Don't claim it was easy. The pushback was real and the 1:1s were uncomfortable.
- Don't take credit for the other teams' adoption — they ran their own integrations once it was working.
- Don't say "I influenced them" — say "I showed up for their integration."

---

## Backup story (if asked for another)

On the unified onboarding platform, I had to get two skeptical leads — one from Identity, one from Cloud Feeds — on board with the GraphQL BFF architecture. They'd both built REST APIs for years. I built a small Apollo Federation prototype that pulled real data from both their services, showed the consolidated response, and let them keep their REST services unchanged underneath. Once they could see that adopting Federation didn't mean rewriting their services, the conversation shifted. Onboarding time dropped from 3-5 days to under 10 minutes.
