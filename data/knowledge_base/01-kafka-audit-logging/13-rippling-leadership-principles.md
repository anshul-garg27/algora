# Rippling Leadership Principles — Mapped to Kafka Audit Logging Project

> **Purpose**: For each of Rippling's 9 leadership principles, a concrete example from your Kafka Audit Logging project that demonstrates the behavior. Use these in behavioral interviews.

---

## 1. Go and See

> *"Rippling leaders spend time in the boiler room. Instead of living in spreadsheets, they study individual successes and failures. They know that firsthand observation is the most powerful kind of data."*

### Your Example: The 413 Error Discovery

> "During April 2025, I didn't just look at dashboards — I personally compared API Proxy request counts against Data Discovery (Hive) record counts, row by row, day by day. The dashboards said everything was fine. But when I went to the raw data, I found we were silently losing 40,000-130,000 records per day to 413 Payload Too Large errors — 5-7% of all traffic.
>
> No alert caught this. No dashboard showed it. I found it by going to the boiler room — querying the actual data at every tier boundary and comparing numbers manually. After the fix, counts matched exactly."

### Your Example: The 5-Day Silent Failure

> "When the GCS sink stopped writing, I didn't just look at the Grafana dashboard (which showed 'healthy'). I SSH'd into the K8s pods, read raw Kafka Connect logs line by line, correlated with Kubernetes events, and traced the actual message flow from topic to consumer to GCS. That's how I discovered four compounding issues — NPE, poll timeouts, KEDA feedback loop, and heap exhaustion — that no single metric would have revealed."

**Interview soundbite**: "I don't trust dashboards alone. During our biggest production incident, every dashboard said 'healthy' while we were losing data. I found the issue by going to the raw logs and tracing individual messages through the pipeline."

---

## 2. Push the Limits of Possible

> *"Rippling leaders set maximally ambitious goals for themselves and their teams. They challenge others' perceived limitations and achieve more as a result."*

### Your Example: Beyond Splunk Replacement

> "The original ask was 'replace Splunk for internal debugging.' I pushed for something much more ambitious — a platform that gives external suppliers direct SQL access to their own API interaction data. Everyone said 'that's a different project, just replace the logging first.' I argued that if we're building the pipeline anyway, designing for supplier self-service from day one costs almost nothing extra but delivers 10x the value.
>
> Result: Suppliers went from 2-day support tickets to 30-second SQL queries. That wasn't in the requirements — I pushed the scope because I saw the opportunity."

### Your Example: 99% Cost Reduction

> "The implicit goal was 'comparable cost to Splunk.' I designed for 99% cost reduction — $50K/month to ~$500/month. People thought that was unrealistic. But by choosing Parquet (90% compression), GCS (cheap object storage), and Hive external tables (no data movement), we achieved it. The key insight was that audit data is write-heavy, read-rarely — perfect for cold storage with on-demand query."

**Interview soundbite**: "The ask was 'replace Splunk.' I delivered a platform that gives suppliers self-service SQL access, handles 2-3 million events daily, and costs 99% less. The original ask was the floor, not the ceiling."

---

## 3. Go to Western Union

> *"Rippling leaders feel accountable for doing something about the problems they see. They're never bystanders. They do what's needed, even if it's outside of their lane, and even if it's unglamorous."*

### Your Example: Cross-Team Library Adoption

> "I noticed three teams independently building audit logging. Same functionality, three different implementations. Nobody asked me to fix this — it wasn't my assignment. But I saw waste and inconsistency, so I took accountability. I scheduled meetings with each team lead, gathered requirements, found the 80% common ground, and built a shared library. Then I personally paired with each team on their integration PRs — unglamorous work, but it's what made adoption happen."

### Your Example: The Geographic Routing Fix

> "Geographic routing broke because of a cross-tier issue — headers weren't being forwarded correctly from the publisher to the sink. This spanned two repos owned by different people. Instead of filing a ticket and waiting, I coordinated fixes across both repos myself — 4 PRs across 2 services in 4 days. The header forwarding fix (Tier 2), the case-sensitivity fix (Tier 2), the filter rewrite (Tier 3), and the worker-level header converter (Tier 3)."

**Interview soundbite**: "When I saw three teams building the same thing independently, I didn't file a suggestion — I built the shared library, wrote the docs, and personally paired on every integration PR. It wasn't my job. It was the right thing to do."

---

## 4. Build Winning Teams

> *"Rippling leaders identify exceptional talent. They attract and retain those people, and challenge them to their limits. They build teams with a fierce desire to win."*

### Your Example: Library Adoption as Team-Building

> "Getting 4 teams to adopt a shared library isn't a technical problem — it's a people problem. I didn't mandate adoption. I made adoption irresistible: one Maven dependency, one CCM config block, zero code changes. Then I invested in each team's success — writing migration guides, running brown-bag demos, and personally pairing on integration PRs.
>
> The measure of success: one engineer I helped later onboarded a fourth team (BULK-FEEDS) without me being involved at all. That's the winning team — people who can carry the work forward independently."

### Your Example: Comprehensive Documentation

> "I wrote the ADT (Architecture Design Template), the integration guide, the operations runbook, the E2E test scenarios, and the visualization guide. Not because someone asked, but because I wanted any engineer on the team to be able to operate, debug, and extend the system without depending on me. 36 E2E test scenarios, 4-step troubleshooting runbook, sample queries — all documented."

**Interview soundbite**: "I measure my success by whether the team can operate without me. I wrote the runbooks, paired on integrations, and the fourth team onboarded themselves using my documentation — zero involvement from me."

---

## 5. Challenge Each Other

> *"Rippling leaders give and receive feedback freely. They challenge others directly and respectfully. They hold conversations in the open and voice what they think is best for the business, even when it's uncomfortable."*

### Your Example: Receiving the Thread Pool Feedback

> "During code review, a senior engineer criticized my thread pool configuration — said the queue size of 100 was arbitrary and could cause silent data loss. My first instinct was defensive — I HAD thought about this. But I paused.
>
> He was right. When the queue fills and tasks are rejected with `AbortPolicy`, `@Async` swallows the exception silently. I added three safeguards: a Prometheus metric for rejected tasks, a WARN log at 80% capacity, and documentation explaining the trade-off. I thanked him publicly in the PR comments. That engineer later became an advocate for the library."

### Your Example: Challenging the 'Just Use Splunk Alternative' Approach

> "When the team defaulted to 'let's just pick another log aggregator,' I challenged that thinking. I said: 'We're spending $50K/month because we're using an observability tool for a data warehousing problem. Audit logs are write-heavy, read-rarely. We need cheap storage with on-demand query, not real-time indexing.' It was uncomfortable because others had already started evaluating Datadog and ELK. But the data supported my position — and the 99% cost savings proved it."

**Interview soundbite**: "A senior engineer told me my thread pool config could silently lose data. He was right. I added monitoring for it, and that 80% queue warning has caught a real issue since then. I'd rather be challenged and improve than be comfortable and wrong."

---

## 6. Decide Quickly

> *"Rippling leaders unblock the organization by making decisions quickly. They know most actions can be undone and don't require extensive study. They exhibit a healthy impatience."*

### Your Example: 27 PRs in 5 Days

> "During the silent failure incident, I shipped 27 production changes in 5 days (PRs #35-61). Each was a hypothesis: 'Is it the NPE? Fix it, deploy, check. Still broken? Is it poll timeouts? Fix, deploy, check.' I didn't wait for a complete root cause analysis before acting — I iterated rapidly in production.
>
> Day 1: NPE fix. Day 2: Consumer config. Day 3: KEDA removal. Day 4: Filter rewrite. Day 5: Heap fix. Each decision was made within hours, not days."

### Your Example: Architecture Decisions Without Paralysis

> "When designing the three-tier architecture, I made 10 major decisions in the first week: Servlet Filter over AOP, @Async over sync, Avro over JSON, Kafka Connect over custom consumer, Parquet over JSON files, Active/Active over Active/Passive. Each had trade-offs, but I decided quickly because most were reversible and waiting would have delayed the entire project. The design-to-production timeline was 5 weeks."

**Interview soundbite**: "During our production incident, I shipped 27 changes in 5 days. I didn't wait for perfect information — I formed hypotheses, deployed fixes, and iterated. Healthy impatience saved us from losing more compliance data."

---

## 7. Are Right, a Lot

> *"Rippling leaders have good instincts, and they exercise good judgment. They get a lot right on the first try."*

### Your Example: Architecture That Scaled

> "The three-tier architecture I designed in week 1 is still running unchanged after a year. The core decisions — Servlet Filter, @Async, Avro, Kafka Connect, Parquet, SMT filters — were all right on the first try. The system handles 2-3 million events daily with <5ms P99 impact, exactly as designed.
>
> The sink-side SMT filtering design was particularly prescient: when we needed to add Canada and Mexico support 8 months later, it was a 5-line code change per country — exactly as I predicted. Adding a country = deploying a new connector. Zero changes to the producer or library."

### Your Example: Choosing GCS + Parquet Over Alternatives

> "I chose GCS + Parquet when others suggested Elasticsearch or direct BigQuery streaming. My instinct: audit data is write-heavy, read-rarely, and cost-sensitive. GCS + Parquet + external tables is 99% cheaper than alternatives. A year later, we're processing 1 billion events/year at ~$500/month. The instinct was right."

**Interview soundbite**: "The architecture I designed in week 1 handles 2-3 million events daily, unchanged after a year. When we added Canada and Mexico 8 months later, it was 5 lines of code per country — because the SMT filter design anticipated extensibility from day one."

---

## 8. Change Their Minds

> *"Rippling leaders are willing to be wrong. They let their ideas rise and fall on the merits, and they don't pull rank."*

### Your Example: KEDA Autoscaling — I Was Wrong

> "I configured KEDA autoscaling on Kafka consumer lag. It seemed logical — more lag means more work, so scale up. I was wrong. Scaling Kafka consumers triggers consumer group rebalancing. During rebalancing, no messages are consumed, so lag increases. KEDA scales more. Infinite loop.
>
> I publicly acknowledged the mistake, disabled KEDA, and switched to CPU-based autoscaling. I didn't defend my original decision — I changed my mind based on production evidence. And I documented the anti-pattern so others wouldn't repeat it."

### Your Example: Error Tolerance Oscillation

> "I originally set `errors.tolerance: all` — tolerate all errors and keep processing. When we discovered this was silently hiding failures, I changed to `none` — stop on any error. But that was too aggressive — one bad record stopped the entire pipeline. I changed my mind again: `all` with DLQ and monitoring. Three positions, each based on new evidence. The final answer wasn't the first or second attempt."

**Interview soundbite**: "I configured autoscaling that created an infinite feedback loop in production. I didn't defend it — I disabled it, documented why it failed, and switched to a better approach. Being wrong quickly and publicly is better than being wrong slowly and quietly."

---

## 9. Are Frugal

> *"Rippling leaders count the nickels. They're resourceful in finding paths to the goal, and they avoid waste. They spend the company's money as though it were their own."*

### Your Example: 99% Cost Reduction

> "Splunk cost $50K/month. My solution costs ~$500/month. That's not a rounding error — that's $594K/year saved. How:
> - **GCS** instead of a managed log platform: ~$0.02/GB/month for storage
> - **Parquet** compression: 90% smaller → 90% less storage cost
> - **Hive external tables**: query-on-demand, no always-running compute
> - **Kafka Connect**: open-source, no licensing fees
> - **Reusable library**: one implementation serves 4+ teams, not 4 separate solutions"

### Your Example: Right-Sizing Resources

> "I didn't over-provision. The thread pool is 6/10/100 — sized based on actual traffic analysis (100 req/sec × 50ms = 5 threads needed). The GCS sink runs 1 pod per region — not 10 'just in case.' The flush config (50MB/5000 records/10 min) is tuned to minimize GCS write operations (which cost money) while keeping data fresh.
>
> When KEDA tried to scale to 5 pods, I recognized that as waste — 1 pod with proper configuration handles the load. Scaling added cost and caused instability."

**Interview soundbite**: "I saved $594K/year by choosing the right storage tier, compression format, and query layer. Frugality isn't about cutting corners — it's about understanding your access patterns and choosing tools that match. Audit data is write-heavy, read-rarely — it doesn't need an expensive real-time platform."

---

## Quick Reference: Principle → Story

| # | Principle | Story | Key Number |
|---|-----------|-------|------------|
| 1 | **Go and See** | 413 error discovery by manual data comparison | 130K records/day lost |
| 2 | **Push the Limits** | Supplier self-service beyond Splunk replacement | 2-day tickets → 30-sec queries |
| 3 | **Go to Western Union** | Built shared library across 3 teams, not my job | 4 teams adopted |
| 4 | **Build Winning Teams** | Docs + pairing so team operates without me | 36 E2E tests, runbooks |
| 5 | **Challenge Each Other** | Received thread pool feedback, improved the library | 80% queue warning saved us |
| 6 | **Decide Quickly** | 27 PRs in 5 days during production incident | 5-day resolution |
| 7 | **Are Right, a Lot** | Architecture unchanged after 1 year, 1B events | 5 lines to add a country |
| 8 | **Change Their Minds** | KEDA mistake acknowledged publicly | Infinite loop → CPU scaling |
| 9 | **Are Frugal** | 99% cost reduction, right-sized everything | $50K → $500/month |

---

## How to Use in Interview

**When asked a behavioral question**, pick the principle that maps best:

| Interview Question | Map to Principle | Story |
|-------------------|-----------------|-------|
| "Tell me about debugging" | Go and See (#1) | 413 error / Silent failure |
| "Biggest accomplishment" | Push the Limits (#2) | Supplier self-service platform |
| "Initiative / ownership" | Go to Western Union (#3) | Shared library, cross-team |
| "Team leadership" | Build Winning Teams (#4) | Library adoption + docs |
| "Handling feedback" | Challenge Each Other (#5) | Thread pool criticism |
| "Fast decision making" | Decide Quickly (#6) | 27 PRs in 5 days |
| "Good judgment" | Are Right, a Lot (#7) | Architecture still works |
| "When you were wrong" | Change Their Minds (#8) | KEDA feedback loop |
| "Cost optimization" | Are Frugal (#9) | 99% cost reduction |

---

*Prepared for Rippling interview — February 2026*
