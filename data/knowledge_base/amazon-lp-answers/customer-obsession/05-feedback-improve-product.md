# Q: Tell me about a time when you used customer feedback to improve a product.

> **LP**: Customer Obsession
> **Primary story**: `W6 — Supplier Self-Service (RLS policy review)`
> **Backup story**: `G6 — Fake-Follower ML`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

The audit-logging system at Walmart Luminate had been live for about a month. Suppliers — Pepsi, Coke, Unilever — could now query their own API interaction logs in BigQuery via external tables on Parquet. I had set up a row-level security policy on `consumer_id` so each supplier sees only their own rows. I thought I was done.

Then a Unilever data engineer sent feedback through the supplier success channel. Two pieces. First, the RLS policy was matching on `consumer_id` but their team had three different consumer IDs — one for each of their product lines. Each query showed only one slice. Second, their analyst kept hitting a "permission denied" when she tried to join the audit table with their internal catalog table.

### Task

I had to fix the access model without leaking data across suppliers. That second part was non-negotiable — Coke seeing Pepsi rows would be an incident.

### Action

I sat down with the policy review carefully. The RLS rule was `consumer_id = SESSION_USER()`. Clean and simple, but it assumed one supplier = one consumer ID. That's wrong. Walmart issues separate consumer IDs per business unit. Unilever has at least three.

I changed two things. First, I added a mapping table — `supplier_id` to `consumer_id` — owned by the supplier onboarding team. The RLS rule became "the row's `consumer_id` is in the set of consumer IDs mapped to my `supplier_id`." Same isolation, broader access for legitimate users.

Second piece — the "permission denied" on joins. The analyst was joining the BQ external table with a Unilever-owned table in a different project. BigQuery's RLS gets stricter when you cross projects. I rewrote the sample queries to use `SAFE.PARSE_JSON` on the request body and a `WITH` clause so the join happens after the RLS filter, not before. Added that to the supplier docs.

Last thing — I added an audit log on the audit log. Every query against the supplier table writes to `bq_supplier_query_audit`. If someone tried to bypass RLS, we'd see it. Belt and braces.

I tested it with two test consumer IDs against a synthetic Unilever profile. Saw rows from both, didn't see rows from a fake Pepsi profile. Shipped.

### Result

Unilever's data engineer ran a workshop the next week using the audit logs for their own incident review. She told the supplier success manager it was the first time she'd been able to run a real cross-product retrospective. We extended the mapping table to Pepsi (two consumer IDs) and Coke (four). Internal support tickets for "I can't see all my data" went to zero.

The thing I should've caught at design time was the multi-consumer-ID case. I'd designed for the simple model and shipped before validating with a real supplier's identity setup. The feedback caught it in week four instead of month six.

---

## Technical depth — if they probe

- **BigQuery row-level security**: `CREATE ROW ACCESS POLICY supplier_filter ON audit_logs GRANT TO ("group:supplier-x@walmart.com") FILTER USING (consumer_id IN (SELECT consumer_id FROM supplier_consumer_map WHERE supplier_id = SESSION_USER_SUPPLIER()))`. The mapping table is the lever.
- **Why a mapping table, not array columns**: Suppliers acquire new business units. New consumer IDs get issued. The onboarding team owns the mapping table — they update it, no engineering needed.
- **Cross-project join issue**: BigQuery's RLS applies before the join. If the supplier joins with their own table in their project, BQ evaluates RLS in the source project first. Wrapping the access in a `WITH` clause and materialising the filtered set first works.
- **`bq_supplier_query_audit`**: Captures `principal_email`, `query_text`, `referenced_tables`, `total_bytes_processed`. Anyone trying to bypass the policy shows up here.

---

## Likely follow-ups

**Q: Why didn't you catch the multi-consumer-ID case during design?**
> I designed against my mental model of "one supplier, one identity." I should have done an onboarding walkthrough with a real supplier before shipping, not after. I do that step now on any access-control work.

**Q: What if a supplier acquires another supplier — how does the mapping update?**
> The onboarding team owns the mapping table. They add the new `consumer_id` rows when M&A closes. Until then, the acquired supplier keeps their own access.

**Q: Did you consider service accounts instead of session-based SSO?**
> Some suppliers asked for that. I held off because the SSO-based model gives us per-user audit trails. With a shared service account we'd lose attribution. We can revisit once the audit log itself has more history.

**Q: How did you validate the fix worked without exposing real supplier data?**
> Synthetic profiles. Two test `consumer_ids` mapped to a test `supplier_id`, ran the canonical queries, confirmed scoped access. Then a stage run against a controlled subset of Unilever data with their engineer on the call.

---

## What NOT to say

- Don't pretend I knew about the multi-consumer-ID case from day one. The whole point is I learned it from a real user.
- Don't say "I rebuilt the RLS policy." I changed the predicate and added a mapping table.
- Don't make the cross-project join sound easy. It was annoying. The `WITH` clause workaround is real but not pretty.

---

## Backup story (if asked for another)

Fake-follower detection at GCC. After the first version of the ensemble model shipped, a content team flagged that real Indian users with year-of-birth in their handle (rahul_1998) were getting tagged as fake — the "more than 4 digits" feature was over-firing. I downgraded that single signal from a hard 1.0 to a soft 0.33 when the Indian name database also matched. False positives on real users dropped sharply. The fix took an afternoon because the feedback was specific.
