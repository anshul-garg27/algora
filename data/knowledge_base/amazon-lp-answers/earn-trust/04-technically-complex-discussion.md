# Q: Tell me about a technically complex discussion you had.

> **LP**: Earn Trust
> **Primary story**: `W11 — Unified Onboarding / IAM`
> **Backup story**: `G8 — Tech Stack Defence`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

At Walmart Data Ventures, mid-2025. We needed a single onboarding flow for external suppliers — Pepsi, Coca-Cola — across six different data products. Cloud Feeds, NRT APIs, BI Link, the rest. Each product had its own service, its own auth model, its own REST API.

I proposed an Apollo Federation GraphQL BFF in front of all of them. Two senior leads pushed back — one from Identity, one from Cloud Feeds. Both had been at Walmart longer than me. Both had reasonable concerns. Their reasoning was: "We've built REST for years. Federation adds operational complexity we don't need. What problem are we solving?"

### Task

Win them over with the technical case, not the org chart. If I forced it through with manager backing, the platform would ship and nobody downstream would help maintain it.

### Action

I didn't argue in the meeting. I built a small Apollo Federation prototype over a weekend. Real data, not mock. Pulled `principal` records from the Identity service's REST API and `subscription` records from Cloud Feeds, joined them through a federated `Supplier` type, returned them in one round trip to the React frontend.

Then I walked the two leads through it on a screen-share. Three points I made specifically.

One: their services didn't have to change. The NestJS subgraph wraps their existing REST endpoints. They keep their codebase, their deploy pipeline, their on-call rotation. The Federation layer is additive.

Two: the cost they were worried about — operational complexity — was real but bounded. One NestJS service, OpenTelemetry traces wired in, the same Kubernetes pattern as everything else. Not a new platform.

Three: the win on the frontend side was real. The React micro-frontend was making 5 to 7 REST calls per page load and stitching them in the browser. One GraphQL query replaced that — p95 dropped from around 600ms to under 200ms.

The Identity lead was still skeptical on auth. We spent an extra hour on JWT propagation — how the BFF forwards the supplier's token to each subgraph, how each service stays independently authorisable. He stress-tested me on token-replay attacks, JWT signature validation, what happens if one downstream is slow. I had specific answers because I'd built the prototype.

By the end of that session both leads were in. Cloud Feeds lead actually offered to be the second team onboarded.

### Result

The platform shipped. Onboarding time for new suppliers went from 3 to 5 days down to under 10 minutes. Both leads' teams adopted it without me needing to push. The Identity lead became one of the people who'd review my PRs proactively — a relationship I rely on now.

The trust I earned was specifically about engineering judgement. They didn't trust the design because of my title. They trusted it because I'd anticipated their objections, built a prototype before pitching, and didn't blink under stress-testing.

---

## Technical depth — if they probe

- **Apollo Federation specifically**: Each team owns their subgraph's schema. The gateway composes them. No central schema team. Their services stay independent but compose into one query.
- **JWT propagation**: BFF forwards the supplier's Falcon SSO token to each subgraph. Each service does its own ECDSA signature validation against the public key. BFF can't impersonate.
- **The 5–7 round trips**: Before BFF, the React frontend pulled `/principals`, `/subscriptions`, `/products`, `/audit`, `/credentials` separately. Each pull was 80–120ms. Browser stitching was custom for each page. One federated query replaces it.
- **OpenTelemetry traces**: Distributed trace ID propagates from React through NestJS through each subgraph. A slow page is debuggable in Dynatrace as one trace.

---

## Likely follow-ups

**Q: What if they'd still said no?**
> Then I'd have shipped a thinner version — REST aggregation in the BFF without Federation. Worse, but the architectural argument was the right hill. I wasn't going to force it.

**Q: What was the hardest question they asked?**
> "What happens if one subgraph is slow?" Real answer: the federated query times out at the slowest subgraph. We needed per-subgraph timeouts and parallel fan-out, both of which I had to wire after the prototype.

**Q: Did the operational complexity concern turn out to be valid?**
> Partly. The Federation gateway is one more service to monitor. We added it to the standard Dynatrace + Prometheus stack. The cost is real but the latency win earned it back.

**Q: How is this different from BFF without Federation?**
> BFF without Federation means writing custom aggregation code per query. Federation means each subgraph owns its schema and composes automatically. Less code, more standardisation.

---

## What NOT to say

- Don't claim you "convinced" them — you showed them. Different word, different posture.
- Don't dismiss their concern as conservative. They were right that REST was simpler. The latency case is what tipped it.
- Don't oversell Federation. It's right for 10+ microservices behind one UI. Wrong for a 3-service shop.

---

## Backup story (if asked for another)

At GCC I had to defend the dual-database tech stack — PostgreSQL plus ClickHouse — against the team lead who wanted to stay single-DB. The argument I made wasn't theoretical. I pulled actual query latencies: a typical analytics aggregation over 30 days of events ran in 30 seconds on Postgres and 2 seconds on ClickHouse. Compression was 5x better. Once the numbers were on the screen, the conversation shifted from "do we?" to "how do we cut over safely?"
