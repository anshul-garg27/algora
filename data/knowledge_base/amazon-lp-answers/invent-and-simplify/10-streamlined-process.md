# Q: Tell me about a process you streamlined.

> **LP**: Invent and Simplify
> **Primary story**: `W2 — Shared Library: 2-week → 1-day integration`
> **Backup story**: `W6 — BigQuery RLS: 2-day debug → 30s self-serve`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

At Walmart, every team building a supplier-facing API had to bolt on audit logging — capture request, capture response, ship to Kafka, route to GCS, expose via BigQuery. Splunk was being decommissioned and suppliers wanted query access to their own data. The integration was taking each team about two weeks of plumbing — write a servlet filter, get the body without consuming the stream, set up an async sender, wire signature auth, handle the failure modes. I was in three design reviews where engineers drew the same diagram.

### Task

I was building my own service's audit logger. I could see I was about to write the fourth identical filter on the team. Nobody asked me to centralise it — but somebody had to.

### Action

I talked to each team lead one-on-one before I wrote any code. Three conversations, about an hour each. "What endpoints? Need response bodies? Custom headers?" About 80 percent of the requirements were identical. The 20 percent that differed — endpoint regex, response-body capture, custom headers — I made configurable via CCM (Walmart's runtime config).

I built `dv-api-common-libraries` as a Spring Boot starter. One Maven dependency, one CCM block, done.

The filter uses `@Order(LOWEST_PRECEDENCE)` so it runs after security — captures the final request and response, including auth failures. `ContentCachingRequestWrapper` caches the body so the controller still sees it. The async send uses a bounded thread pool — 6 core, 10 max, 100 queue — and catches every exception so audit failures never break the API.

I personally helped each team integrate. Paired on their PRs. Ran a brown-bag demo. Wrote the docs.

A senior engineer challenged my queue size of 100 — said silent drops were a risk. He was right. I added a Prometheus metric for rejected tasks and a WARN log at 80 percent capacity. That alarm has fired once and caught a downstream slowdown before it became a Sev-2.

### Result

Three teams adopted in the first month. Integration time dropped from two weeks to one day. Roughly 12x. The library is on version 0.0.54 today across JDK 11 and 17. About 1,500 lines of code that would have been duplicated never got written. The library is now the default any new supplier-facing service plugs into — a fourth team adopted a few months later without me pitching at all.

---

## Technical depth — if they probe

- **`@Order(LOWEST_PRECEDENCE)`**: filter runs last. Captures final state including auth failures. If it ran first, we'd miss what security did.
- **`ContentCachingRequestWrapper` + `copyBodyToResponse()`**: HTTP body stream is single-read. Wrapper caches it. Forgetting the copy-back = empty response to client. One line, catastrophic.
- **Bounded thread pool**: 6/10/100. 100 req/sec × 50ms audit = 5 threads needed. Queue absorbs bursts. At 2KB/payload, 200KB memory ceiling.
- **CCM runtime config**: endpoint regex + response-body toggle live in CCM. Teams change endpoints without redeploy.
- **AKeyless secret management**: RSA private key mounted at runtime, never in repo. Per-request signature with rotatable key version.

---

## Likely follow-ups

**Q: How did you measure 2-week → 1-day?**
> The two-week estimate came from the first team's actual story points (their custom build took 12 working days). The one-day number came from team #2's integration PR — 3 hours from "git clone" to "audit logs visible in BigQuery."

**Q: What about the teams already using their own version?**
> Team #2 had started theirs — about 2 weeks in. I offered to help them migrate; we paired for an afternoon, used their requirements (response-body toggle) to improve the library. Their feedback became a flag everyone benefits from.

**Q: Did anyone resist?**
> Some friction on team #3 about giving up control. I framed it as "you still own the config — I just own the plumbing." Once they saw the CCM config gave them more flexibility than their hardcoded version, the resistance went away.

**Q: What was the second-order effect?**
> Cross-service queries became possible. Before, each team's audit logs had a different schema. Now they all land in the same BigQuery dataset with consistent fields — `request_id`, `service_name`, `endpoint`, `response_code`. Suppliers can correlate across services.

**Q: What would you do differently?**
> Publish to Kafka directly from the library instead of through an HTTP publisher. Removes a network hop. Original concern was every service taking a Kafka dependency — teams are mature enough with Kafka now that the trade-off has flipped.

---

## What NOT to say

- Don't say the library "saved months" — the measured number is integration time per team. Be precise.
- Don't pretend the queue size was obviously right — a senior engineer challenged it; he improved the design. Be honest.
- Don't oversell as 10x productivity boost — it's a one-time setup cost reduction.

---

## Backup story (if asked for another)

At Walmart Luminate the supplier-self-service flow used BigQuery row-level security. Before: when Pepsi asked "why did my call fail," our team grepped logs for 2 days, then emailed a CSV back. After: Pepsi opens BigQuery console, runs `SELECT * FROM audit_logs WHERE consumer_id = 'pepsi-id' AND response_code >= 400` — gets the answer in 30 seconds. Row-level security via `@policy_tag` means they only see their own rows; no risk of cross-supplier leakage. 2 days → 30 seconds, and our team got the time back.
