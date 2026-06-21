# Key PRs Reference - Kafka Audit Logging

---

## dv-api-common-libraries (The Library)

| PR# | Title | Why Important | Interview Point |
|-----|-------|---------------|-----------------|
| **#1** | Audit log service | **THE MAIN PR** - Complete library | "Built the reusable Spring Boot starter" |
| **#3** | adding webclient in jar | WebClient for reactive HTTP | "Added WebClient for tracing outbound calls" |
| **#6** | Develop | Core functionality merge | "Enhanced configuration options" |
| **#11** | enable endpoints with regex | Regex-based filtering | "Added regex for flexible endpoint matching" |
| **#15** | Version update for gtp bom | Java 17 compatibility | "Upgraded for Java 17 support" |

---

## audit-api-logs-srv (Kafka Publisher)

| PR# | Title | Why Important | Interview Point |
|-----|-------|---------------|-----------------|
| **#4** | initial commit for kafka service | **Initial Kafka producer** | "Built the Kafka publisher service" |
| **#44** | [CRQ:CHG3024893] kitt and sr changes | **Production CRQ** | "Production deployment with CRQ" |
| **#49-51** | Increasing request entity size to 2 MB | Payload size increase | "Fixed 413 errors for large payloads" |
| **#57** | int changes | International support | "Added CA/MX region support" |
| **#65** | publish in both region changes | **Multi-region publishing** | "Implemented dual-region Kafka" |
| **#67** | Allowing selected headers | Header forwarding | "Enabled geo-routing via headers" |
| **#77** | Contract test changes | R2C testing | "Added contract testing" |

---

## audit-api-logs-gcs-sink (Kafka Connect)

### Core Setup

| PR# | Title | Why Important | Interview Point |
|-----|-------|---------------|-----------------|
| **#1** | Initial setup | **Architecture decisions** | "Designed GCS sink architecture" |
| **#3** | Deployment changes | K8s deployment | "Set up Kubernetes deployment" |
| **#9** | Prod config | Production config | "Configured for production" |
| **#12** | [CRQ:CHG3041101] GCS Sink for US | **US production** | "First production deployment" |

### Performance Tuning

| PR# | Title | Why Important | Interview Point |
|-----|-------|---------------|-----------------|
| **#27** | flush count, poll interval | Consumer tuning | "Tuned for 2M+ events/day" |
| **#28** | CHG3180819 - Consumer config | **Production tuning CRQ** | "Kafka consumer optimization" |
| **#29** | Adding autoscaling profile | **KEDA autoscaling** | "Initial autoscaling setup" |

### The Debugging PRs (MEMORIZE THIS SEQUENCE!)

| PR# | Title | What It Fixed |
|-----|-------|---------------|
| **#35** | Adding try catch block | NPE on null headers |
| **#38** | Adding consumer poll config | Poll timeout issues |
| **#42** | Removing scaling on lag | **KEDA rebalance storm** |
| **#47** | Increasing poll timeout | Consumer stability |
| **#52** | Setting error tolerance | Error handling strategy |
| **#57** | Overriding KAFKA_HEAP_OPTS | JVM heap issues |
| **#59** | Filter and header converter | Header parsing |
| **#61** | Increasing heap max | **Final memory fix** |

> **Interview Story:** "PRs #35-61 over two weeks - systematic debugging of silent failure. First null headers, then poll timeouts, then KEDA feedback loop, finally heap exhaustion."

### Multi-Region

| PR# | Title | Why Important | Interview Point |
|-----|-------|---------------|-----------------|
| **#30** | adding prod-eus2 env | **East US 2 region** | "Multi-region expansion" |
| **#70** | [CHG3235845] Retry policy | Resilience | "Added retry for reliability" |
| **#85** | Site-based routing | **SMT filters for geo** | "Geographic routing" |

---

## Quick Reference: Top 10 PRs to Know

| # | Repo | PR# | One-Line Summary |
|---|------|-----|------------------|
| 1 | dv-api-common-libraries | #1 | Complete audit logging library |
| 2 | audit-api-logs-gcs-sink | #1 | Initial GCS sink architecture |
| 3 | audit-api-logs-srv | #65 | Multi-region Kafka publishing |
| 4 | audit-api-logs-gcs-sink | #28 | Kafka consumer tuning |
| 5 | audit-api-logs-gcs-sink | #42 | Fixed KEDA rebalance storm |
| 6 | audit-api-logs-gcs-sink | #61 | Fixed OOM with heap increase |
| 7 | audit-api-logs-gcs-sink | #85 | Site-based geographic routing |
| 8 | dv-api-common-libraries | #11 | Regex endpoint filtering |
| 9 | audit-api-logs-srv | #77 | Contract testing |
| 10 | audit-api-logs-gcs-sink | #12 | First production deployment |

---

## Commands to View PRs

```bash
# Set Walmart GitHub host
export GH_HOST=gecgithub01.walmart.com

# View PR details
gh pr view <PR#> --repo dsi-dataventures-luminate/<repo-name>

# View PR diff
gh pr diff <PR#> --repo dsi-dataventures-luminate/<repo-name>

# Examples:
gh pr view 1 --repo dsi-dataventures-luminate/dv-api-common-libraries
gh pr view 1 --repo dsi-dataventures-luminate/audit-api-logs-gcs-sink
gh pr view 65 --repo dsi-dataventures-luminate/audit-api-logs-srv
```

---

## PR Statistics

| Repository | Total PRs | Key PRs |
|------------|-----------|---------|
| dv-api-common-libraries | 16 | #1, #3, #11, #15 |
| audit-api-logs-srv | 61+ | #4, #65, #67, #77 |
| audit-api-logs-gcs-sink | 76+ | #1, #28, #35-61, #85 |
| **TOTAL** | **150+** | |

---

## Timeline

```
2024-12 ┃ audit-api-logs-srv: Initial Kafka service (#4)
        ┃
2025-01 ┃ audit-api-logs-gcs-sink: Initial setup (#1)
        ┃
2025-03 ┃ dv-api-common-libraries: Audit log service (#1)
        ┃ Production deployments (#12, #44) [CRQ]
        ┃
2025-04 ┃ dv-api-common-libraries: Regex endpoints (#11)
        ┃
2025-05 ┃ PRODUCTION DEBUGGING (#35-61)
        ┃ audit-api-logs-srv: Multi-region (#65), Headers (#67)
        ┃
2025-06 ┃ audit-api-logs-gcs-sink: Retry policy (#70) [CRQ]
        ┃
2025-11 ┃ audit-api-logs-gcs-sink: Site-based routing (#85)
        ┃ audit-api-logs-srv: Contract testing (#77)
```

---

*These PRs tell the story of building, debugging, and evolving a production system.*
