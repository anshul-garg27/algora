# Q: Tell me about a time you considered the broader impact of your work.

> **LP**: Success and Scale Bring Broad Responsibility
> **Primary story**: `W6 — BigQuery RLS Pattern as Reusable Runbook`
> **Backup story**: `W2 — Shared Library as Audit-Logging Standard`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

I'd just shipped the supplier self-service path for the audit logs — Pepsi could now run a BigQuery SQL query against their own data and see why a request failed, instead of waiting two days for us to grep Splunk. It worked. They were happy. The product manager wanted to keep moving.

But the data team had a question I couldn't ignore. We'd built row-level security via BigQuery policy tags on `consumer_id` — every supplier could only see their own rows. That security pattern wasn't documented anywhere at Walmart. We'd basically figured it out by reading Google's docs and a handful of internal threads.

### Task

Decide whether to keep moving on my next feature, or to slow down and turn the BigQuery RLS pattern into something other teams across Walmart could pick up safely.

### Action

I sat with this for a day. There are 50+ supplier-facing services across Walmart. Most of them have the same shape — sensitive data, multiple suppliers, regulatory pressure to keep them apart. If each team reinvents BigQuery RLS, two things happen. Some teams get it wrong and leak data. The rest spend two weeks each figuring out what I'd already figured out.

So I slowed down. I wrote a runbook with three sections — the schema pattern (policy tags on consumer_id), the query pattern (always filter at the table level, never trust application-level filtering), and the audit pattern (BigQuery audit logs catch any query that bypassed the tag). I put it in our shared Confluence with worked examples from our pipeline.

Then I went further. I added a section called "what NOT to do" — the three mistakes I'd nearly made. Things like trusting the JOIN order in a view (BigQuery can reorder it), or relying on `WHERE consumer_id = ?` at the application layer (one missed filter and you're leaking). These weren't theoretical — they were the failure modes I'd caught in my own code reviews.

I shared the runbook with the platform security team and offered office hours. Two teams pulled the pattern in the first month. Both came to office hours, both shipped without a security incident.

### Result

The broader impact wasn't a metric — it was a non-event. Six teams have now used the runbook. None of them have had a supplier-data-leak incident. The platform security team made the runbook the recommended pattern for new supplier-facing data products and linked it from the data governance handbook.

The piece I think about: every successful project at Walmart's scale teaches the broader org something. If I'd kept my head down and shipped the next feature, the lessons would have died with me when I rotated. Writing the runbook took two days. The downstream saving is hard to count.

---

## Technical depth — if they probe

- **Why BigQuery policy tags over row-level views**: Policy tags enforce at the storage layer. Views are easier to bypass with `SELECT *`. For sensitive data, you want the filter in a place an engineer can't accidentally remove.
- **The audit pattern**: BigQuery emits an `INFORMATION_SCHEMA.JOBS_BY_PROJECT` row per query. Quarterly we sample queries for "did a supplier see another supplier's row?" by joining the query's `consumer_id` filter against the result row's `consumer_id`. Zero hits so far.
- **Why "what NOT to do" matters more than "what to do"**: Anyone can copy a working example. The failure modes are what you only learn by making the mistakes. Documenting them saves the next person from re-learning.
- **Office hours, not just docs**: Docs answer "what." Office hours answer "why does this not work for my specific case." Both are needed.

---

## Likely follow-ups

**Q: How did you measure broader impact?**
> Two ways. Number of teams who adopted the pattern (six). Number of supplier-data-leak incidents on those teams (zero). The combination is the signal.

**Q: What if the runbook was wrong somewhere?**
> I peer-reviewed it with the platform security team before sharing. They caught two simplifications and added a section on cross-region considerations. Better than my draft.

**Q: Did anyone push back on you slowing down to write this?**
> My manager. He wanted me on the next feature. I made the case that two days of doc-writing now would save six teams two weeks each — a 30x return. He agreed once I framed it that way.

**Q: What's the most under-considered broader impact in our domain?**
> Schema evolution. Every API I build today is a contract suppliers will lean on for years. Choices that seem cheap now — like JSON-blob fields instead of typed columns — become expensive to undo when a hundred suppliers depend on the shape.

---

## What NOT to say

- Don't make this about you — make it about the six teams who didn't have to figure it out.
- Don't oversell "zero incidents." Say "no incidents on the adopting teams so far."
- Don't claim the platform security team adopted it — say "made it the recommended pattern." Smaller claim, easier to defend.

---

## Backup story (if asked for another)

For W2, when I built the audit-logging shared library, I had a choice: ship it for my one service or design it to be the standard for the org. I went standard — config-driven, zero code changes for consumers, R2C-validated. Twelve teams adopted it inside 8 weeks. The broader impact was that audit-log format consistency went from 0% to 100% across the org, which meant cross-service correlation by trace ID actually worked. That wasn't possible before, even though every team had been "logging audits" in their own format for years.
