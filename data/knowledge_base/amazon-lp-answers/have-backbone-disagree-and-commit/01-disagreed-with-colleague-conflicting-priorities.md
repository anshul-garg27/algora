# Q: Situational questions like "Tell me about a time when you disagreed with a colleague" and "How would you handle conflicting priorities."

> **LP**: Have Backbone; Disagree and Commit
> **Primary story**: `G8 — Tech Stack Defence`
> **Backup story**: `W3 — DiscardPolicy Feedback`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

Late 2023 at Good Creator Co. I was the only backend engineer on Coffee, our influencer analytics SaaS. I had 12 modules to build in three months. A senior backend lead from a sister team walked into the design review and said the whole thing was wrong. He wanted Kafka instead of RabbitMQ, microservices instead of one Go monolith, and Kubernetes instead of plain EC2.

### Task

I had to either rebuild the stack his way or convince the room my plan would ship. He had more years than me. The CTO was in the room.

### Action

I asked for one day before the decision. Then I went and pulled real numbers.

For Kafka vs RabbitMQ — our daily event count was around 10 million log events, but the use case was point-to-point queue work, not event streaming. Watermill on RabbitMQ gave me a middleware chain that matched the HTTP pipeline I already had. Kafka needed Zookeeper, partition planning, and a consumer-group story we did not need. I wrote a one-page doc with both architectures side by side, the operational cost, and the engineering days each would take.

For microservices, I was honest. I was one engineer. Splitting Coffee into 12 services meant 12 deployments, 12 alert sets, 12 schemas. I would burn the first month on infra and never ship the modules. A modular monolith with the same 4-layer pattern per module gave me clean boundaries without the ops tax.

For Kubernetes — we had two production nodes, a heartbeat pattern, and no platform team. EC2 plus a `beat=false` drain on the load balancer was enough. Kubernetes was a six-month detour.

Next morning I walked him through the doc before the meeting. Honestly, that 1:1 mattered more than the room. He pushed back on the RabbitMQ piece for about twenty minutes. I told him I would revisit it if we crossed 50M events a day. In the actual review I led with the numbers and the timeline. The CTO signed off.

### Result

Coffee shipped on time. 50+ endpoints, 12 modules, ~8500 lines of Go. ClickHouse added later for OLAP. Three years on, the architecture still holds and the team has not migrated to Kafka. The senior engineer later asked me to review a service of his. That part felt better than the win itself.

---

## Technical depth — if they probe

- **Watermill on RabbitMQ**: Middleware chain matched my HTTP chain — request context extraction, transaction session, retry with backoff, panic recovery. Same mental model for messages and requests.
- **Modular monolith over microservices**: One binary, 12 packages, Go generics across the 4-layer API → Service → Manager → DAO pattern. New module = DaoProvider interface + two converter functions.
- **EC2 over k8s**: Two-node deploy, PUT `/heartbeat/?beat=false`, drain 15s, kill, restart, PUT back. Sufficient for our scale, zero platform team needed.
- **Tradeoff I named openly**: Kafka would have been right if we were doing event streaming with fan-out across teams. We were not.

---

## Likely follow-ups

**Q: When would Kafka have been the right call?**
> If we had multi-team event fan-out, a need for replay, or genuine streaming workloads. Our case was point-to-point queue work — RabbitMQ was the simpler fit.

**Q: What if he had insisted?**
> If he had escalated, I would have committed to a 30-day spike on Kafka with a clear exit criteria. The data I had said RabbitMQ was right, but I was not going to die on a hill if the org wanted Kafka.

**Q: Did splitting into microservices ever become the right move?**
> Not at GCC. The team stayed under 8 backend engineers. Module boundaries inside the monolith gave us enough independence.

**Q: How did you handle his ego in the room?**
> I gave him credit publicly for the Kafka point, said it was the right question to ask, and then explained why our scale did not need it yet. He needed to feel heard, not overruled.

---

## What NOT to say

- Do not say "he was wrong." He was not. He was right for a different scale.
- Do not frame it as you vs him. Frame it as me defending a plan that fit the team.
- Do not skip the 1:1 — that is the actual mechanism. Public override would have damaged the relationship.

---

## Backup story (if asked for another)

W3 — DiscardPolicy. A senior reviewer flagged my thread pool config on the audit common library PR. Public comment. I went home defensive, came back the next morning convinced he was right, added the rejection metric and the queue-warning log. The library got better and he later helped me promote it to other teams.
