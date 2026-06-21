# Q: Tell me about a time you demonstrated strong team ownership.

> **LP**: Ownership
> **Primary story**: `W11 — Unified Onboarding / IAM`
> **Backup story**: `W2 — Shared Library Adoption`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

At Walmart Data Ventures, we were building a unified onboarding platform for external suppliers. The problem was real — a supplier like Pepsi wanting API credentials for Cloud Feeds would file a ServiceNow ticket, wait 3-5 days for manual approvals, and get keys handed to them over email. Across three markets (US, Mexico, Canada) and six data products, it didn't scale.

The team was four backend engineers including a junior who'd joined the team about a month before me. He owned the credential-management subgraph in NestJS and had never built an Apollo Federation service.

### Task

Two things, really. Ship the IAM platform — Spring Boot 3.5.5 auth-policies service, NestJS GraphQL BFF, React micro-frontends. And get the junior to a place where he could own his piece without me reviewing every line.

### Action

I architected the core — multi-tenant data model with three Walmart `site_id` values as a custom Postgres domain, ThreadLocal `TenantContext` propagation, Hibernate `@FilterDef` for automatic site-level filtering. Strategy pattern for credential types (`ApiKeyStrategy`, `OAuth2Strategy`) so adding a new product wouldn't touch existing code. Chain of Responsibility for onboarding steps so failures didn't cascade.

But the team-ownership part wasn't the architecture. It was the daily 1-hour pairing with the junior for the first six weeks.

First week he tried to write a GraphQL resolver that fetched credentials and made a round-trip to the database for each one. Classic N+1. I didn't fix it for him. I drew the schema on a whiteboard, walked through Apollo's batching behaviour, and let him reimplement it with DataLoader himself. Took him two days. He wouldn't make that mistake again.

By week four he hit a real frustration — JWT signature validation was failing intermittently and he'd been stuck for two days. I sat with him, but only asked questions. "What does the failed request look like?" "Are the failing requests on a specific endpoint?" Eventually he found it — Falcon SSO was rotating signing keys and we weren't refreshing the JWK set. He fixed it. I never typed code.

The whole arc, I forced myself to resist writing his code. It would have been faster for one PR. It would have been disaster for six months.

### Result

The platform shipped on time. Onboarding dropped from 3-5 days to under 10 minutes — 99% faster credential provisioning. We support 3 markets and 6+ data products. The junior owned the credential-management subgraph end-to-end by week eight. I delegated review of his PRs to him after about three months — he reviewed the next new joiner's work himself.

The thing I'd say I learned: team ownership isn't writing more code than anyone else. It's making sure the next engineer is faster than the previous one.

---

## Technical depth — if they probe

- **Multi-tenancy via Hibernate filters**: `@FilterDef(name="siteFilter", parameters=@ParamDef(name="siteId", type="long"))` on entities. A `TenantInterceptor` sets the filter parameter from JWT claims at request entry, clears it at `afterCompletion`. Application-enforced multi-tenancy is safer than database row-level security — if the filter isn't enabled, queries return zero rows. Default deny.
- **`site_id` as a custom Postgres domain**: `CREATE DOMAIN walmart_site_id AS BIGINT CHECK (VALUE IN (1694066566785477000, ...))` — three Walmart markets, enforced at the schema level. You can't accidentally insert garbage.
- **Strategy pattern for credential types**: `Map<ProductType, CredentialStrategy>` auto-wired by Spring from all `CredentialStrategy` beans. Adding a new product = new strategy class, zero changes elsewhere.
- **MeghaCache over DB sessions**: Sub-ms cache lookup vs 5-10ms DB query, at 10K req/sec the math is clear. TTL handles expiry — no cleanup job.
- **Apollo Federation BFF**: Each backend service owns its subgraph. The gateway stitches them. The credential-management subgraph the junior owned could deploy independently.

---

## Likely follow-ups

**Q: Why pair for an hour every day? That's a lot of your time.**
> I spent an hour a day for six weeks. That's 30 hours total. If he'd quit or under-delivered for six months, that's a quarter of platform work lost. The ROI is obvious.

**Q: How did you know when to stop pairing?**
> When he stopped asking me questions before trying. Week six, he had a tricky bug in cross-domain API access. He didn't ping me — he debugged for half a day, then came over with a clear hypothesis. That was the signal.

**Q: What if he'd not been good enough?**
> I asked our manager to give him 90 days before any judgement. I also wrote down what "good enough by day 90" looked like — owning the subgraph, design-reviewing his own PRs, mentoring the next joiner. He hit all three.

**Q: Wasn't the architecture the bigger contribution?**
> The architecture was a week's worth of design. Onboarding the junior was the lever that made the team faster for years. They're different scales of impact.

**Q: What's the hardest part about not writing the code for them?**
> The temptation in the moment. When he was stuck on JWT for two days I could have typed the fix in 20 minutes. I knew what it was. I sat on my hands and asked questions instead.

---

## What NOT to say

- Don't make this story about "I" — it's about a team. Use "we" naturally.
- Don't say I "trained" him — coaching is more honest. He was already a competent engineer, just new to Apollo Federation and our IAM domain.
- Don't claim he became a "principal engineer" or oversell — by month three he owned a subgraph, that's enough.
- Don't pitch the IAM architecture as my idea alone — the schema design came out of three review sessions with the team lead and architect.

---

## Backup story (if asked for another)

The shared audit-logging library at Walmart. I noticed three teams writing the same audit-logging code. Built a Spring Boot starter JAR — `LoggingFilter`, `@Async` audit service, CCM-driven config. About 500 lines. Three teams adopted in the first month, five more over the next quarter. Integration time dropped from two weeks to one day. I held weekly office hours and reviewed every integration PR personally — not just to approve, but to teach.
