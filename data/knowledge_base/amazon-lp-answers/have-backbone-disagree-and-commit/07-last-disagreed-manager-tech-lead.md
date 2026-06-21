# Q: When was the last time you disagreed with your manager or tech lead?

> **LP**: Have Backbone; Disagree and Commit
> **Primary story**: `G8 — Tech Stack Defence`
> **Backup story**: `W3 — DiscardPolicy Feedback`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

This was late 2023. I was building Coffee at Good Creator Co. — the Go SaaS API behind influencer analytics. I was the only backend engineer on it, three months to ship 12 modules covering discovery, leaderboards, collections, genre insights, the lot. We had a tech review with the CTO and a senior backend lead from the data platform side. The senior lead wanted me to rebuild the stack his way before I wrote a line of business logic.

His pitch — Kafka instead of RabbitMQ, microservices instead of a modular monolith, and Kubernetes instead of EC2. The CTO was leaning toward him because the resume-level optics looked better. Three months evaporated if I had to retool.

### Task

I had to either rebuild the stack or convince two more senior people my plan would actually ship.

### Action

I asked for a day before the decision. Did not argue in the room.

That night I built three side-by-side comparisons.

For Kafka vs RabbitMQ I pulled the real numbers. We had about 10M log events a day — that sounds like Kafka country until you ask what we were actually doing with them. Point-to-point queue work. Watermill on RabbitMQ gave me a middleware chain that already matched my HTTP request chain — context extraction, transaction session, retry with 100ms backoff, panic recovery. Kafka needed Zookeeper, partition planning, and a consumer-group story I genuinely did not need. I priced both. Kafka added 3 weeks of platform work and a permanent ops surface.

For microservices vs modular monolith I was honest about my constraint — one engineer, three months, 12 modules. Splitting into 12 services meant 12 deploys, 12 alert sets, 12 schemas, 12 CI pipelines. I would burn the first month on infra and never ship the modules. A modular monolith with the same 4-layer pattern per module gave me clean boundaries with Go generics on the framework code. Adding a new module would take 30 minutes, not a day.

For Kubernetes vs EC2, we had two production nodes, no platform team, and a heartbeat-based drain pattern (`PUT /heartbeat?beat=false`, sleep 15s, restart). Kubernetes was a six-month detour.

Next morning I sent the doc to the senior lead first — not the CTO. I asked for 30 minutes. He pushed back on the RabbitMQ piece hardest. I told him if we crossed 50M events a day or needed cross-team fan-out I would revisit. He still had reservations but said "okay, take it to the meeting."

In the actual review I led with the numbers. The CTO signed off. The senior lead said he disagreed on Kafka but he understood the timeline pressure.

### Result

Coffee shipped on time. 50+ endpoints, 12 modules, around 8500 lines of Go. The 25% API response improvement and 30% cost reduction came from the architecture we kept. Three years on, the team still has not moved off RabbitMQ — never needed to. The senior lead later asked me to review a service of his. That was the thing that mattered more than the win. The takeaway — when you are junior in the room, you do not win the argument in the room. You win it in the doc and the 1:1.

---

## Technical depth — if they probe

- **Watermill on RabbitMQ**: Topic naming `exchange___queue` encodes both. After-commit callbacks publish events only if the database transaction committed. 7 listener handlers with 3-attempt retry, 100ms backoff, panic recovery.
- **Modular monolith specifics**: 4-layer pattern — API, Service, Manager, DAO. Go generics on Service[RES, EX, EN, I] gave compile-time type safety across modules. 6 framework files instead of 36 boilerplate files.
- **Deployment**: Two-node EC2 with `/heartbeat/` GET and PUT. Rolling deploy: drain → kill → start → wait → resume.
- **When Kafka would have been right**: Multi-team event fan-out, replay needs, or genuine streaming workloads with cross-team consumers. Not our case.

---

## Likely follow-ups

**Q: What if your stack failed at scale?**
> 50M events a day was my threshold for revisiting RabbitMQ. We never hit it. The architecture had a documented exit ramp.

**Q: How did you handle being the most junior in the room?**
> I brought numbers, not opinions. And I went 1:1 with the senior lead before the meeting so he did not feel publicly overruled.

**Q: Did you regret any of those calls later?**
> The EC2 call — I would still make it. The RabbitMQ call — still right. The monolith call — yes, no regrets. The patterns we put inside the monolith would make it splittable later if needed.

**Q: How did you commit to the parts where you disagreed but were overruled?**
> The senior lead got me to add a metric for RabbitMQ publish failures and an outbox proposal for critical events. I added the metric. I documented the outbox as a future option. Both were his catches, both made the system better.

---

## What NOT to say

- Do not say "the senior was wrong." He was right for a bigger team.
- Do not skip the 1:1 before the meeting. That is the actual move.
- Do not claim you won — frame it as the right plan for the constraints.

---

## Backup story (if asked for another)

W3 — DiscardPolicy. A senior reviewer flagged my thread pool config on the audit library PR. Public comment. I was defensive at first, then sat with it overnight and realized he was right — DiscardPolicy would silently lose compliance data. Switched to CallerRunsPolicy, added queue-depth metrics, brought him in on a 1:1. He later became the library's biggest internal advocate.
