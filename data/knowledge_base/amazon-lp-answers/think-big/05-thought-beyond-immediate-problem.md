# Q: Describe a time you thought beyond your immediate problem.

> **LP**: Think Big
> **Primary story**: `W11 — Apollo Federation BFF`
> **Backup story**: `W2 — Shared Library Org Standard`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Mid-2025 at Walmart Data Ventures. A supplier like Pepsi needed API credentials to call our Cloud Feeds and Near-Real-Time APIs. The existing flow was a ServiceNow ticket — supplier files a request, our ops team manually creates credentials in three or four backend systems, supplier waits 3–5 days. The task assigned to me was small: "build a UI so suppliers can create credentials themselves, calling our existing REST endpoints." Standard CRUD frontend over existing services.

### Task

The literal scope was a React frontend over existing REST APIs. I could have shipped that in two months.

### Action

I went and looked at what the frontend would actually need to do. The "create credential" screen alone pulled from four services — principals, products, source identities, tenant data. The "view audit logs" page pulled from two more. The dashboard pulled from all ten. If I just wired up REST calls, the frontend would make 10+ requests on every page load, with different error formats, different auth headers per service, different latency profiles.

So I stepped back and asked the bigger question: what's the right interface between the frontend team and ten backend services. The answer was a GraphQL BFF using Apollo Federation. One endpoint, one schema, one auth flow. The frontend asks for exactly what it needs.

I also looked at multi-market. The team had focused on Walmart US. But our suppliers were also active in Walmart Mexico and Canada. If I designed the data model US-only, we'd repaint it within a year. So I baked `site_id` into the schema from day one — a PostgreSQL domain with three values (US, Mexico, Canada) and Hibernate filter-based multi-tenant isolation. Adding markets later became a config change, not a migration.

The third bigger-picture call was the auth boundary. Our DevX session tokens weren't valid in the Scintilla domain where backend services lived. The naive answer was "expose backend services in DevX." That meant 10+ services adding domain-aware auth. Instead I used AppToApp authentication — the SubGraph registered as a trusted consumer in Scintilla, and used its own token for downstream calls while propagating user context in headers. One auth boundary, not ten.

I had to defend the scope creep. My manager's question — "isn't this too much for the deadline." I broke it into phases. Phase one: SubGraph + Auth Policies Service + credential CRUD. Phase two: market expansion. Phase three: ServiceNow integration for audit. Each phase shippable on its own.

### Result

The platform shipped in phases over about five months. Onboarding time dropped from 3–5 days to under 10 minutes. Three markets supported out of the gate. The Apollo Federation pattern was picked up by two other teams in Data Ventures for their own BFF layers. The AppToApp token pattern became the reference for cross-domain access in our org. What stayed with me — the literal task was "build a UI," the right task was "fix the supplier onboarding experience." Reading the literal task narrowly would have made the right thing impossible.

---

## Technical depth — if they probe

- **Apollo Federation**: each backend team owns a subgraph schema. SubGraph composes them with `@key` directives. Teams deploy independently — no monolithic GraphQL gateway.
- **Multi-tenancy via Hibernate filter**: `@FilterDef(name = "siteFilter", parameters = @ParamDef(name = "siteId", type = "long"))`. Set by `TenantInterceptor` from JWT. SQL WHERE clause injected automatically. Default deny if context missing.
- **AppToApp auth**: SubGraph requests its own token for Scintilla domain. Backend services validate SubGraph's consumer ID, not the user's DevX token. User context propagated in `X-User-Context` header.
- **MeghaCache**: distributed session store, sub-millisecond reads. Beats database-backed sessions which add 5–10ms per request. At 10K req/sec that's 90 seconds of saved latency per second of traffic.
- **JWT sign**: ECDSA (ES256) with secp256r1 curve. Private key never leaves the User Actions Service.

---

## Likely follow-ups

**Q: How did you justify the scope expansion to your manager?**
> Phased delivery. Phase one had the same scope as the original ask. Phase two added markets. Phase three added ServiceNow. Each phase shippable on its own, so the manager could cut at any phase if needed.

**Q: What's the risk of Apollo Federation versus a single GraphQL schema?**
> Operational complexity of composition. The gateway must handle subgraph version drift. We solved that with schema validation in CI — any subgraph PR that breaks composition fails before merge.

**Q: Cross-domain auth was the hardest part?**
> Yes. The naive answer (re-expose backend services in DevX) would have cost 10+ teams two months each. AppToApp gave us one trust boundary instead of ten. The pattern stuck because it's reusable for any future cross-domain integration.

**Q: Would you do anything differently?**
> Add request-level rate limiting from day one. We added it later when one supplier accidentally hammered the credential endpoint. Should have been there at launch.

---

## What NOT to say

- Don't claim the original "build a UI" task was wrong. It wasn't — it was just narrower than what the customer actually needed.
- Don't oversell the federation pattern. It's right for our scale (10+ backend services). For 2–3 services, monolithic GraphQL is simpler.
- Don't gloss over multi-market. That decision came from looking at the supplier list, not from architecture cleverness.

---

## Backup story (if asked for another)

Shared common library at Walmart. The literal ask was "build audit logging into cp-nrti-apis." Instead I built it as a shared library — `dv-api-common-libraries`. Twelve services integrated with 2 lines of pom.xml plus 3 lines of YAML config. Integration time dropped from ~40 hours per team to under an hour. Total org-wide saving was about 480 engineering hours. Same shape — read the literal task as "solve this once" became "solve it once for the org." That re-framing is what made it stick.
