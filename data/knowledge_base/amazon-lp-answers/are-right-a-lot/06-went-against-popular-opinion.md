# Q: Tell me about a time you went against popular opinion.

> **LP**: Are Right, A Lot
> **Primary story**: `G8 — Self-hosted not k8s`
> **Backup story**: `W11 — GraphQL Federation over REST`
> **Time budget**: 90–120 seconds spoken

---

## STAR — how to actually tell it

### Situation

At GCC mid-2023 the engineering org was on a "Kubernetes everything" push. New services were being containerised and shipped to a managed EKS cluster. The Coffee API and SaaS Gateway I'd built were running on bare-metal VMs with a custom heartbeat-based deployment script. The infra team's recommendation was to migrate both to k8s "to standardise the platform."

### Task

I owned both services. I'd written the bare-metal deploy script. I had to decide whether to spend a quarter migrating to k8s or push back and stay on the existing setup.

### Action

I sat with it for a few days before pushing back, because the popular case was real — standardisation has value, especially as the org grew.

I made my counter-case in a written doc.

One — the existing bare-metal setup worked. Graceful deploy via heartbeat toggle (take out of LB, drain 15s, kill, start new, sleep 20s, put back). Two-node production, deployed one at a time, zero-downtime. No incidents in 18 months.

Two — k8s would add real complexity without real benefit at our scale. Two-node Coffee + two-node Gateway. Auto-scaling not needed — traffic was predictable. Service discovery not needed — gateway routes to fixed upstream URLs. The k8s features that justify the complexity didn't apply.

Three — the actual cost. Quarter of engineering time for migration. New on-call training. Helm chart maintenance. Deeper k8s expertise on the team — which we didn't have. Net negative ROI.

Four — what would change my mind. If we hit 4+ nodes per service, if auto-scaling became a real need, or if we needed canary deploys (Flagger requires k8s-style infra), I'd reconsider.

I presented this to the CTO and the infra lead. Infra lead pushed back hard — standardisation is the point, exceptions undermine it. I acknowledged that and offered a compromise: I'd migrate when we hit the first of my "would change my mind" triggers. Until then, the bare-metal setup stays.

The CTO sided with me. Infra lead was unhappy for a few weeks but came around once we hit a different priority (the ClickHouse migration) and the engineering time would have been wasted on k8s instead of revenue work.

### Result

Coffee and Gateway stayed bare-metal for the rest of my time at GCC. Zero deployment incidents. The engineering time saved went into the ClickHouse migration that cut infrastructure costs 30 percent. Two other services that did need auto-scaling went to k8s — the standardisation point was satisfied for services where it added value.

The lesson I took: "everyone's doing it" isn't a reason. Trigger-based exceptions are a way to disagree honestly — "I'll do it when X is true" beats "I'll never do it" or "I'll do it now even though I shouldn't."

---

## Technical depth — if they probe

- **Bare-metal graceful deploy**: heartbeat HTTP endpoint, `PUT /heartbeat/?beat=false` removes from LB, 15s drain, `kill -9`, 10s wait, start new binary, 20s warmup, `PUT /heartbeat/?beat=true`. Two-node, one at a time.
- **Why k8s wasn't a fit**: auto-scaling not needed (predictable traffic), service discovery not needed (fixed upstream URLs), no canary requirement, no pod-level isolation requirement.
- **Trigger conditions for migration**: 4+ nodes per service, auto-scaling need, canary requirement, or pod-level isolation requirement.
- **What did go to k8s**: the Beat scraper service later — it needed horizontal pod scaling for traffic-based crawling. Right tool, right service.
- **Standardisation value**: real but bounded. Two services on a different stack didn't undermine the platform; they just had their own runbook.

---

## Likely follow-ups

**Q: How did you handle the infra lead's pushback?**
> Acknowledged the standardisation point was real. Offered the trigger-based compromise. Didn't dig in on "never." That gave him a way to accept the decision without it feeling like a defeat.

**Q: What if the CTO had sided with infra?**
> I'd have done the migration. My case was a recommendation, not an ultimatum. I work for the company, not the architecture.

**Q: How did you know auto-scaling wasn't a real need?**
> Traffic data. The Coffee API request rate was bounded by the gateway's authenticated session count — predictable, slowly growing. Bare-metal at two nodes was way under capacity. We weren't getting scaling pressure.

**Q: What changed your mind later (or did it)?**
> It didn't change. By the time I left, the bare-metal setup was still running fine. The Beat scraper did move to k8s because it had a different load profile — bursty, traffic-driven. Right reason.

**Q: How did you write the doc?**
> Three sections: current state and why it works, what k8s would add, what would make me migrate. No emotional language. Just the case.

---

## What NOT to say

- Don't disparage k8s — it's the right tool for many services, including one we did migrate. Wrong tool for the two we kept.
- Don't pretend everyone agreed in the end — the infra lead was unhappy for a while. Be honest.
- Don't oversell — the engineering time saved went somewhere useful, but it wasn't the only factor.

---

## Backup story (if asked for another)

At Walmart on the W11 unified onboarding work, the team's default was "build it as REST endpoints, that's what we know." I pushed for GraphQL via Apollo Federation. Most of the team hadn't used GraphQL. I made the case based on the data shape — onboarding pulls across 7 services and the consumer needs only a subset of fields per service. REST would mean either 7 round trips or 7 BFF endpoints. GraphQL Federation does it in one query with field-level granularity. Pushed past the initial resistance, did a brown-bag to ramp the team, and the federation became the standard pattern for cross-service reads.
