# Deployment Strategy - Canary with Flagger

> Zero-downtime deployment of Spring Boot 3 migration

---

## Why Canary Deployment?

| Strategy | Risk Level | Rollback Speed | Our Choice |
|----------|-----------|----------------|------------|
| **Big Bang** | High - all or nothing | Slow (redeploy) | No |
| **Blue/Green** | Medium - instant switch | Fast (DNS switch) | No |
| **Canary** | Low - gradual increase | Instant (automatic) | **Yes** |
| **Rolling** | Medium - incremental | Medium | No |

We chose **Canary** because:
- Automatic rollback if metrics exceed thresholds
- Can catch issues with only 10% traffic exposed
- Proven approach at Walmart (Flagger + Istio)

---

## Deployment Phases

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                      CANARY DEPLOYMENT STRATEGY                                 │
│                                                                                 │
│   Phase 1: STAGE ENVIRONMENT (1 week)                                          │
│   ├── Full regression suite passed                                             │
│   ├── Performance testing (same throughput as prod)                            │
│   ├── All endpoints validated manually                                         │
│   ├── Caught Hibernate enum issue here                                         │
│   └── Sign-off from team lead                                                  │
│                                                                                 │
│   Phase 2: CANARY START (Hour 0-4)                                             │
│   ├── 10% traffic → Spring Boot 3                                              │
│   ├── 90% traffic → Spring Boot 2.7 (existing)                                │
│   ├── Monitor: error rates, P99 latency, CPU, memory                          │
│   ├── Automatic rollback if error rate > 1%                                    │
│   └── Duration: 4 hours minimum                                                │
│                                                                                 │
│   Phase 3: GRADUAL INCREASE (Hour 4-24)                                        │
│   ├── 25% traffic (if metrics healthy)                                          │
│   ├── 50% traffic (after 2 more hours)                                         │
│   ├── 75% traffic (after 2 more hours)                                         │
│   └── 100% traffic (after 2 more hours)                                        │
│                                                                                 │
│   Phase 4: FULL PRODUCTION (Hour 24+)                                          │
│   ├── 100% on Spring Boot 3                                                    │
│   ├── Old version kept for 48 hours (quick rollback)                           │
│   └── Monitor for 1 week for any delayed issues                                │
│                                                                                 │
│   SAFETY NET: Error rate > 1% at ANY point → AUTOMATIC ROLLBACK               │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## Flagger + Istio Configuration

### How Flagger Works

```
┌─────────────────────────────────────────────────────────────────┐
│                    FLAGGER + ISTIO FLOW                           │
│                                                                   │
│  1. Flagger detects new deployment                               │
│  2. Creates canary pod alongside primary                         │
│  3. Istio VirtualService splits traffic:                         │
│     ├── 90% → primary (old version)                              │
│     └── 10% → canary (new version)                               │
│  4. Flagger checks metrics every 1 minute:                       │
│     ├── request-success-rate > 99%?                              │
│     └── request-duration P99 < 500ms?                            │
│  5. If healthy → increase canary weight by 10%                   │
│  6. If unhealthy → automatic rollback                            │
│  7. Once at 100% → promote canary, remove old                   │
└─────────────────────────────────────────────────────────────────┘
```

### Flagger Config (kitt.yml)

```yaml
flagger:
  enabled: true
  analysis:
    threshold: 5           # Max failed metric checks before rollback
    maxWeight: 50          # Max canary traffic percentage
    stepWeight: 10         # Increase by 10% each step
    interval: 1m           # Check metrics every minute

    metrics:
    - name: request-success-rate
      threshold: 99        # Must have 99% success rate
    - name: request-duration
      threshold: 500       # P99 must be < 500ms
```

---

## What We Monitored During Rollout

| Metric | Threshold | Actual (SB3) | Status |
|--------|-----------|--------------|--------|
| **Error rate** | < 1% | 0.02% | PASS |
| **P99 latency** | < 500ms | 180ms | PASS |
| **CPU usage** | < 80% | 45% | PASS |
| **Memory usage** | < 85% | 62% | PASS |
| **Kafka publish errors** | < 0.1% | 0% | PASS |
| **Database errors** | 0 | 0 | PASS |

---

## The Actual Rollout Timeline

```
Day 0 (Monday):
  09:00 - Deploy to stage environment
  09:30 - Run regression suite
  10:00 - All tests pass, begin manual validation

Day 0-6:
  Stage environment running with production-like traffic
  Caught and fixed Hibernate enum issue (@JdbcTypeCode)

Day 7 (Monday):
  09:00 - Begin canary deployment to production
  09:05 - 10% traffic on Spring Boot 3
  13:00 - 4 hours clean, increase to 25%
  15:00 - 2 hours clean, increase to 50%
  17:00 - End of day, leave at 50% overnight

Day 8 (Tuesday):
  09:00 - Check overnight metrics - all clean
  09:30 - Increase to 75%
  11:30 - Increase to 100%
  11:30 - Spring Boot 3 fully live!

Day 8-10:
  Monitor for delayed issues
  Keep old version available for quick rollback

Day 10:
  Remove old version pods
  Migration complete!
```

---

## Interview Questions

### Q: "Why canary and not blue/green?"
> "Canary gives us gradual risk exposure. With blue/green, you switch 100% at once. With canary, if there's a subtle performance regression that only shows under load, we catch it at 10% before it affects all users. Plus, Flagger automates the entire process including rollback."

### Q: "What if you found an issue at 50%?"
> "Flagger would automatically roll back. But even manually, we could instantly shift all traffic back to the old version via Istio VirtualService. The old pods stay running for 48 hours specifically for this scenario."

### Q: "How did you validate the canary was actually receiving traffic?"
> "Dynatrace traces showed request distribution. We also checked access logs to confirm both versions were handling requests. Istio's built-in metrics showed exact traffic split."

### Q: "What metrics did you watch most closely?"
> "Error rate and P99 latency. Error rate catches functional regressions (wrong responses, exceptions). P99 latency catches performance regressions. We also watched memory because Hibernate 6 has different memory characteristics."

---

## Key Takeaway

> "The canary deployment was as important as the code changes. A framework migration can introduce subtle issues that only appear under production load. The staged approach - 1 week in stage, then gradual canary over 24 hours - gave us confidence at each step."

---

*Next: [05-production-issues.md](./05-production-issues.md) - Post-migration fixes*
