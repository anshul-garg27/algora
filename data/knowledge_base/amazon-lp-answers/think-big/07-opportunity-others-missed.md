# Q: Describe an opportunity others missed that you saw.

> **LP**: Think Big
> **Primary story**: `W6 — Supplier Self-Service via BigQuery RLS`
> **Backup story**: `G6 — Heuristic Ensemble Over DL`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Mid-2024 at Walmart Data Ventures. Pepsi's data team filed a ticket — their daily inventory dashboard was showing stale numbers and they couldn't tell why. Our team triaged it and the process took 2 days. An engineer wrote a custom SQL query, ran it against the data warehouse, exported to Excel, sent it to Pepsi. That happened roughly once a week across our top 20 suppliers. The team treated it as "supplier support overhead" — normal cost of doing business.

### Task

I picked up the Pepsi ticket. As I traced the data path, I noticed something nobody had named: the same query pattern repeated for every supplier. Every time, someone wrote essentially the same SQL with a different supplier filter, exported, emailed. Nobody had asked "why is this manual at all?"

### Action

I looked at the actual workflow. The data lived in BigQuery already. Every supplier had a DUNS identifier. The "custom" SQL each engineer wrote was the same template — `SELECT ... WHERE supplier_duns IN (...)`. The 2-day delay was almost entirely human routing: ticket triage, engineer pickup, SQL writing, Excel export, email.

The opportunity was right there. BigQuery has row-level security via policy tags. If we tagged supplier data with the supplier's DUNS and exposed BigQuery views with `@policy_tag` constraints, suppliers could query their own data directly through our existing API gateway. Zero manual queries. Two-day debug becomes a 30-second API call.

I prototyped it on a Friday. Tagged a sample dataset with DUNS-based policy tags. Built a thin Spring Boot endpoint that mapped the supplier's auth context to their DUNS, ran the underlying BigQuery query with row-level filters applied. Tested with Pepsi's actual auth token in stage — got back exactly what they would have gotten via manual ticket, in 30 seconds.

Took the prototype to my team lead on Monday. The conversation lasted 20 minutes. His pushback was reasonable — "we'd be exposing data to suppliers directly, can we trust the row-level security." I'd come prepared. BigQuery policy tags are enforced at the database layer; the application can't bypass them even with a bug. I'd also tested cross-supplier access — Pepsi couldn't see Coca-Cola data even if I forged the DUNS in the request payload, because the auth context propagation was server-side.

We rolled it out incrementally — Pepsi first, then 10 suppliers over six weeks, then the rest of the top 20.

### Result

Manual debug tickets for this workflow dropped from about 2 per week to essentially zero. The 2-day-debug-becomes-30-second-self-serve was the headline. Supplier satisfaction scores on data freshness went up. The pattern — BigQuery row-level security as a self-service interface — became the default for any new supplier-facing data product in our team. What stayed with me — the opportunity was visible to everyone but it lived between two roles. Ops engineers saw the tickets; data engineers saw the warehouse; nobody had stood in the supplier's seat and asked "why is this not self-serve." That gap was the opportunity.

---

## Technical depth — if they probe

- **BigQuery row-level security**: policy tags on columns + row-level access policies enforce filtering at the query engine. Application can't bypass even with a compromised endpoint.
- **DUNS-based isolation**: each supplier's data tagged with their DUNS. Auth context propagation from JWT → service → BigQuery query. Server-side enforcement, not client-side.
- **External tables**: data sits in GCS, BigQuery reads it via external tables with the same policy tags. No data duplication.
- **Why I tested cross-supplier access**: row-level security is only as good as the auth boundary. I forged a DUNS in a test request and confirmed the database rejected it — the auth context came from the JWT, not the payload.

---

## Likely follow-ups

**Q: How did you find this opportunity if nobody else had?**
> I read the actual ticket queue, not the team's status report. The ticket queue showed the same workflow repeating. The status report showed "supplier support handled."

**Q: What was the risk you were most worried about?**
> Data leak between suppliers. That's why I tested cross-DUNS access on day one before pitching. If policy tags hadn't held, I wouldn't have proposed it.

**Q: How did you sell this without it sounding like criticism of the existing process?**
> Framed it as "what if suppliers got answers in 30 seconds instead of 2 days." Didn't say "the team has been doing this wrong." The implicit critique was there, but the pitch was forward-looking.

**Q: Why didn't anyone else build this?**
> Two reasons. Ops engineers were measured on closing tickets, not eliminating them. Data engineers were busy on the warehouse. The opportunity lived in the gap between roles — nobody owned "supplier developer experience."

---

## What NOT to say

- Don't sound like I criticised the team's previous handling. The opportunity was visible only after Pepsi's specific ticket landed.
- Don't claim BigQuery row-level security is novel — it's a documented feature. The novelty was applying it to supplier self-service.
- Don't oversell numbers. The "2 days to 30 seconds" was for this specific workflow, not all supplier interactions.

---

## Backup story (if asked for another)

Fake-follower ML at GCC. The team had floated training a deep-learning model for fake detection. We had no labelled data and would have spent months labelling before training. I proposed a heuristic ensemble — 5 interpretable features. Each feature debuggable independently. Output: 0.0 / 0.33 / 1.0 confidence. Shipped in about 4 weeks. The opportunity others missed was that "no labelled data" wasn't a blocker — it was a signal that supervised ML was the wrong tool. Heuristics worked, and the scored outputs became the labelled dataset for a future supervised v2.
