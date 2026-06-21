# How To Speak About Kafka Audit Logging In Interview

> **Ye file sikhata hai Kafka audit logging project ke baare mein KAISE bolna hai - word by word.**
> Interview se pehle ye OUT LOUD practice karo.

---

## YOUR 90-SECOND PITCH (Ye Yaad Karo)

Jab interviewer bole "Tell me about your work" ya "Tell me about a project":

> "My biggest project at Walmart was designing an audit logging system from scratch. When Splunk was being decommissioned, I saw an opportunity to build something better - not just replace logging, but give our external suppliers like Pepsi and Coca-Cola direct access to their API interaction data.
>
> I designed a three-tier architecture: a reusable Spring Boot library that intercepts HTTP requests asynchronously, a Kafka publisher for durability with Avro serialization, and a Kafka Connect sink that writes to GCS in Parquet format. Hive/Data Discovery and BigQuery sit on top - suppliers can run SQL queries on their own data.
>
> The system handles 2 million events daily with less than 5ms P99 latency impact. We went from Splunk costing $50K/month to about $500/month. And three other teams adopted the library within a month."

**Practice this until it flows naturally. Time yourself - should be ~90 seconds.**

---

## PYRAMID METHOD - Architecture Question

**Q: "Walk me through the architecture"**

### Level 1 - Headline (Isse shuru karo HAMESHA):
> "It's a three-tier system that processes 2 million audit events daily with zero impact on API latency."

### Level 2 - Structure (Agar unhone aur jaanna chaha):
> "Tier 1 is a reusable Spring Boot library that intercepts HTTP requests. It uses a servlet filter with ContentCachingWrapper to capture request and response bodies, then fires the audit payload asynchronously to Tier 2.
>
> Tier 2 is a Kafka publisher service. It serializes the payload to Avro - 70% smaller than JSON - and publishes to a multi-region Kafka cluster with geographic routing headers.
>
> Tier 3 is Kafka Connect with custom SMT filters that route US, Canada, and Mexico records to separate GCS buckets in Parquet format. Hive/Data Discovery and BigQuery external tables sit on top for SQL queries."

### Level 3 - Go deep on ONE part (Jo sabse interesting lage):
> "The most interesting design decision was in Tier 1. HTTP bodies are streams - you can only read them once. If the filter reads the body, the controller gets empty input. I used Spring's ContentCachingWrapper, which caches the bytes so both can read. Combined with @Async and a bounded thread pool - 6 core threads, max 10, queue of 100 - the API response returns immediately while audit happens in the background."

### Level 4 - OFFER (Ye zaroor bolo):
> "I can go deeper into the Kafka Connect SMT filter design, the multi-region failover, or the debugging incident we had - which interests you?"

**YE LINE INTERVIEW KA GAME CHANGER HAI - TU DECIDE KAR RAHA HAI CONVERSATION KAHAN JAAYE.**

---

## KEY DECISION STORIES - "Why did you choose X?"

### Story 1: "Why Servlet Filter instead of AOP?"

> "We considered three options: AOP, a sidecar proxy like Envoy, and a servlet filter.
>
> AOP can only access method parameters and return values - it can't access the raw HTTP body stream. For debugging, suppliers need to see the actual request body that was sent.
>
> A sidecar works at the network layer - it can't see application context like which endpoint was called semantically or which supplier made the request.
>
> We chose the servlet filter because it gives us access to the raw HTTP stream, runs in the application context, and with @Order LOWEST_PRECEDENCE, it runs after security filters - so we capture even failed auth attempts.
>
> The trade-off is in-process overhead, but the async design keeps it under 5ms P99."

### Story 2: "Why Avro over JSON?"

> "Three reasons: schema enforcement prevents bad data from entering the pipeline, binary format is 70% smaller which matters at 2 million events per day, and schema evolution lets us add fields without breaking consumers. We use Schema Registry for centralized management."

### Story 3: "Why Kafka Connect over a custom consumer?"

> "Kafka Connect gives us offset management, scaling, fault tolerance, and retry logic out of the box. A custom consumer would've taken 2-3 weeks to build the same features. Connect is battle-tested and we could focus on our SMT filter logic instead of infrastructure."

### Story 4: "Why fire-and-forget?"

> "The alternative was making audit synchronous - but then a slow audit service would slow all API responses. For compliance, audit data is important but not worth blocking supplier requests. We mitigate the risk with a bounded queue, Prometheus metrics for rejected tasks, and a warning at 80% queue capacity."

---

## THE DEBUGGING STORY (5-Day Timeline)

**This is your MOST POWERFUL story. Use it when they ask:**
- "Tell me about a debugging experience"
- "Tell me about a production incident"
- "Tell me about a challenging problem"
- "Tell me about working under pressure"

### How To Tell It (Timeline Format, NOT bullet points):

> "Two weeks after launch, I noticed GCS buckets stopped receiving data. No alerts, no errors in dashboards. The system was failing silently - and we were losing compliance-critical audit data.
>
> **Day 1** - I checked the obvious. Kafka Connect running? Yes. Messages in the topic? Yes - millions backing up. So the issue was between consumption and GCS write. I narrowed the search space.
>
> **Day 2** - I enabled DEBUG logging and found a NullPointerException in our SMT filter. Legacy data didn't have the wm-site-id header we expected. I added try-catch with graceful fallback. Deployed it. Fixed? **No.**
>
> **Day 3** - Problem persisted. I noticed consumer poll timeouts in the logs. The default max poll interval was 5 minutes, but our GCS writes for large batches took longer. I tuned the config. Fixed? **Still no.**
>
> **Day 4** - This is where it got interesting. I correlated with Kubernetes events and discovered KEDA autoscaling was causing a feedback loop. When lag increased, KEDA scaled up workers. But scaling triggered consumer group rebalancing. During rebalancing, no messages are consumed. So lag increases more, KEDA scales more - infinite loop. I disabled KEDA and switched to CPU-based autoscaling.
>
> **Day 5** - After stabilizing, found the last issue. JVM heap exhaustion. Default 512MB wasn't enough for large batch Avro deserialization. Increased to 2GB.
>
> **Result:** Zero data loss - Kafka retained all messages during the entire debugging period. Backlog cleared in 4 hours once fixed. I created a troubleshooting runbook that's been used twice by other teams."

### After Telling This Story, ALWAYS Add:

> "The key learning was that distributed systems fail in unexpected combinations. It wasn't one bug - it was four issues compounding. And Kafka Connect's default error tolerance was hiding the problems silently. Now I build 'silent failure' monitoring into every system I design."

### If They Ask "What would you do differently?":

> "I'd add OpenTelemetry tracing from day one. If I could trace a single message from the HTTP request through Kafka to GCS, I would've found the issue in hours, not days."

---

## BEHAVIORAL STORIES FROM THIS PROJECT

### Story: Receiving Feedback (Googleyness: Valuing Feedback)

**Trigger questions:**
- "Tell me about a time you received difficult feedback"
- "Describe a situation where you were wrong"

> **Situation:** "During code review for the audit library, a senior engineer criticized my thread pool configuration. He said the queue size of 100 was arbitrary and could cause silent data loss."
>
> **Task:** "I needed to respond constructively, not defensively."
>
> **Action:** "My first instinct was defensive - I HAD thought about this. But I paused. I ran the numbers: each payload is 2KB, queue of 100 is 200KB - not a memory issue. But when the queue fills and tasks are rejected? They're silently dropped. He was right.
>
> I added three things: a Prometheus metric for rejected tasks, a WARN log when queue exceeds 80%, and documentation explaining the trade-off. I thanked him in the PR comments."
>
> **Result:** "The library is more robust. We've had the 80% warning trigger once - caught a downstream slowdown early. That engineer later became an advocate for the library."
>
> **Learning:** "I learned to separate ego from code. Now when I feel defensive about feedback, I pause and ask: what if they're right?"

---

### Story: Influencing Without Authority (Googleyness: Bringing Others Along)

**Trigger questions:**
- "Tell me about a time you influenced others without authority"
- "Describe building something other teams adopted"

> **Situation:** "I noticed three teams building audit logging independently. Same functionality, three different implementations."
>
> **Task:** "I proposed a shared library. My challenge was getting buy-in from teams I had no authority over."
>
> **Action:** "I didn't come with a solution - I came with questions. I scheduled meetings with each team's lead: 'What are your requirements? What endpoints? What latency constraints?'
>
> There was resistance. 'Our needs are different.' One team wanted response body logging, another didn't. I showed the common 80% and made the different 20% configurable. Response body logging became a CCM config flag.
>
> I wrote documentation and a migration guide. Did a brown-bag demo. Then personally spent an afternoon with each team pairing on their integration PRs."
>
> **Result:** "Three teams adopted within a month. Integration time dropped from 2 weeks to 1 day. One engineer I helped later onboarded a fourth team without me."
>
> **Learning:** "Adoption isn't about building good software - it's about reducing friction and investing personally in others' success."

---

### Story: Handling Ambiguity (Googleyness: Thriving in Ambiguity)

**Trigger questions:**
- "Tell me about a time you had incomplete information"
- "Describe a project with unclear requirements"

> **Situation:** "We needed multi-region for disaster recovery. Leadership said 'make it resilient' without specifying RTO, RPO, budget, or timeline."
>
> **Task:** "I needed to define the requirements myself, design a solution, and execute with zero downtime."
>
> **Action:** "Instead of waiting for clarity, I proactively scheduled conversations. Asked stakeholders: 'How much data can we afford to lose?' - learned RPO was 4 hours. 'How quickly must we recover?' - learned RTO was 1 hour.
>
> I designed three options with trade-offs - Active-Passive, Active-Active, Hybrid - and presented them to the team. We chose Active-Active because audit is write-heavy.
>
> I documented my assumptions explicitly: 'I'm assuming RPO of 4 hours because...' and shared with stakeholders. That document became the de facto requirements spec.
>
> Executed in 4 weeks with a phased rollout - one component per week."
>
> **Result:** "Active-Active across two regions. Zero downtime. DR test: recovered in 15 minutes versus the 1-hour target."
>
> **Learning:** "When requirements are vague, don't wait - document assumptions and validate them. That forces clarity."

---

### Story: Failure (Googleyness: Honesty, Learning)

**Trigger questions:**
- "Tell me about a time you failed"
- "What's your biggest mistake?"

> **Situation:** "I configured KEDA autoscaling for Kafka Connect based on consumer lag. Seemed logical - more lag means more work, so scale up."
>
> **Task:** "In production, this caused a catastrophic feedback loop."
>
> **Action:** "When lag increased, KEDA scaled up workers. But scaling triggered consumer group rebalancing. During rebalancing, no messages are consumed, so lag increases more. More scaling, more rebalancing - infinite loop.
>
> The system got stuck processing zero messages. I diagnosed the loop, disabled KEDA, and switched to CPU-based autoscaling."
>
> **Result:** "No data loss because Kafka retained messages. But I should have caught this in testing."
>
> **Learning:** "I tested autoscaling in isolation but not with production-like traffic patterns. The second-order effect - scaling causes rebalancing which causes more lag - only shows up at scale. Now I always test scaling behavior with realistic load, including failure modes."

---

### Story: User Focus (Googleyness: Putting Users First)

**Trigger questions:**
- "Tell me about improving user experience"
- "Tell me about solving a customer problem"

> **Situation:** "Our external suppliers couldn't debug their own API issues. When their requests failed, they'd call support, open a ticket, wait 1-2 days, and we'd grep through logs."
>
> **Task:** "When building the audit system, I saw an opportunity beyond just replacing Splunk."
>
> **Action:** "I designed the system with supplier self-service in mind. I chose Parquet format specifically because Hive/Data Discovery and BigQuery can query it directly. I ensured the schema captured everything suppliers need: request body, response body, error messages, status codes.
>
> I worked with our data team to set up Hive/Data Discovery and BigQuery external tables with row-level security - each supplier only sees their own records. Created sample queries and documentation."
>
> **Result:** "Suppliers self-service debug in 30 seconds instead of waiting 2 days. Support ticket volume dropped significantly. One supplier told me this was the first time they had visibility into their API interactions with any vendor."
>
> **Learning:** "When building infrastructure, ask 'who else might benefit?' The primary use case was internal logging, but that question led to the supplier access feature with minimal extra work but huge impact."

---

## NUMBERS TO DROP NATURALLY

Don't list numbers. Drop them IN CONTEXT:

| Number | How to Say It |
|--------|---------------|
| 2M events/day | "...handles 2 million events daily..." |
| <5ms P99 | "...less than 5 milliseconds impact at P99..." |
| 99% cost reduction | "...went from $50K/month with Splunk to about $500..." |
| 4+ teams adopted | "...four teams adopted within the first quarter..." |
| 2 weeks → 1 day | "...integration time dropped from two weeks to one day..." |
| 70% smaller (Avro) | "...Avro is about 70% smaller than JSON..." |
| 90% compression (Parquet) | "...Parquet compresses to about 10% of JSON size..." |
| 7 years retention | "...seven years for compliance requirements..." |
| 6/10/100 thread pool | "...six core threads, max ten, queue of a hundred..." |
| 150+ PRs across 3 repos | "...over 150 PRs across three repositories..." |
| 40K-130K/day (413 errors) | "...we were losing up to 130K records per day to payload size limits..." |
| 99.9% availability SLO | "...designed for 99.9% availability with formal SLOs..." |
| 36 E2E test scenarios | "...validated with 36 end-to-end test scenarios..." |

---

## HOW TO PIVOT TO THIS PROJECT

If you're talking about something else and want to bring up Kafka:

> "That reminds me of the audit logging system I designed. The constraint was similar - [connect to what they asked]..."

> "We faced a similar challenge with our audit system. Let me walk you through how we solved it..."

## HOW TO PIVOT AWAY FROM THIS PROJECT

If they've heard enough about Kafka and you want to show range:

> "That's the audit system. I also led a Spring Boot 3 migration that shows a different kind of challenge - not designing something new, but changing the foundation of a running system without downtime. Interested?"

### How to Answer "What Would You Improve?"

> "Three things I'd do differently:
> 1. **Skip the publisher service** — publish directly to Kafka from the library. Removes a network hop and the separate CachedThreadPool.
> 2. **Add OpenTelemetry from day one** — tracing a single message from HTTP request through Kafka to GCS would have found the silent failure in hours, not days.
> 3. **Use Apache Iceberg** — better than raw Parquet for ACID transactions and GDPR compliance deletes.
> 4. **Define formal SLOs upfront** — we defined them retroactively in the ADT. Having them day one would have driven better monitoring setup."

---

*Practice these OUT LOUD. Record yourself. Listen back. Repeat until it feels natural, not rehearsed.*
