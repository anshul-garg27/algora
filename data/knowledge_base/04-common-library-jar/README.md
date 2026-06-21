# Common Library JAR (Bullet 2) - Quick Redirect

> **This bullet is fully documented in the Kafka Audit Logging folder.**

---

## Where to Find Everything

The Common Library JAR (dv-api-common-libraries) is **Tier 1** of the Kafka Audit Logging system. All documentation is in:

**Full documentation:** [../01-kafka-audit-logging/02-common-library.md](../01-kafka-audit-logging/02-common-library.md)

This includes:
- 30-second pitch
- Code deep dive (LoggingFilter, AuditLogService, ThreadPool config)
- Design decisions table
- Interview Q&A (5 questions with answers)
- STAR adoption story
- Key PRs list
- Numbers to remember

---

## Quick Reference

| Metric | Value |
|--------|-------|
| Integration time | **2 weeks → 1 day** |
| Teams adopted | **3+** |
| Lines of code | **~500** |
| Thread pool | **6 core, 10 max, 100 queue** |
| Maven version | **0.0.45** |

### 30-Second Pitch
> "I built a reusable Spring Boot starter JAR that gives any service audit logging by just adding a Maven dependency. No code changes needed. Three teams adopted it within a month, reducing integration time from 2 weeks to 1 day."

---

*Go to [01-kafka-audit-logging/02-common-library.md](../01-kafka-audit-logging/02-common-library.md) for the full deep dive.*
