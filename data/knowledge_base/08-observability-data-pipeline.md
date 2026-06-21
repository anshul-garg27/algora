# Observability and Data Pipeline Tools -- Complete Study Guide

> **Purpose:** Interview-ready deep dive into observability and data pipeline tools used at Walmart (Data Ventures) and GCC (Good Creator Co). Covers Prometheus, Grafana, Dynatrace, ELK Stack, Flagger, Apache Airflow, dbt, BigQuery, and Apache Parquet with architecture diagrams, real-world usage, and interview Q&A.

---

## TABLE OF CONTENTS

### Part 1: Observability
1. [Prometheus](#1-prometheus)
2. [Grafana](#2-grafana)
3. [Dynatrace](#3-dynatrace)
4. [ELK Stack](#4-elk-stack-elasticsearch-logstash-kibana)
5. [Flagger](#5-flagger)
6. [Observability Interview Q&A](#6-observability-interview-qa)

### Part 2: Data Pipeline Tools
7. [Apache Airflow](#7-apache-airflow)
8. [dbt (Data Build Tool)](#8-dbt-data-build-tool)
9. [BigQuery](#9-bigquery)
10. [Apache Parquet](#10-apache-parquet)
11. [Data Pipeline Interview Q&A](#11-data-pipeline-interview-qa)
12. [How Anshul Used These Tools](#12-how-anshul-used-these-tools)

---

# PART 1: OBSERVABILITY

---

## 1. PROMETHEUS

### What is Prometheus?

Prometheus is an **open-source systems monitoring and alerting toolkit** originally built at SoundCloud in 2012 and now a graduated CNCF (Cloud Native Computing Foundation) project. It is the de facto standard for metrics collection in Kubernetes environments.

**Core philosophy:** Pull-based metrics collection with a powerful query language.

### Pull-Based vs Push-Based Collection

| Aspect | Pull-Based (Prometheus) | Push-Based (StatsD, Datadog Agent) |
|--------|------------------------|-----------------------------------|
| **Direction** | Prometheus scrapes targets | Targets push metrics to collector |
| **Discovery** | Prometheus discovers targets | Targets must know collector address |
| **Health detection** | If a scrape fails, target is down | No scrape = no signal (ambiguous) |
| **Network** | Prometheus must reach targets | Targets must reach collector |
| **Backpressure** | Prometheus controls scrape rate | Targets can overwhelm collector |
| **Short-lived jobs** | Needs Pushgateway | Natural fit |

**Why pull-based is preferred in Kubernetes:**
- Prometheus uses Kubernetes service discovery to automatically find new pods
- If a pod dies, the scrape fails, which itself is a signal (up metric = 0)
- No agent configuration needed inside application containers
- Central control over scrape intervals and targets

### Metric Types

Prometheus defines four core metric types. Understanding when to use each is critical.

#### 1. Counter
A **monotonically increasing** value. It only goes up (or resets to zero on restart).

```
# HELP http_requests_total Total number of HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET", endpoint="/api/inventory", status="200"} 15234
http_requests_total{method="POST", endpoint="/api/inventory", status="500"} 42
```

**Use cases:** Request counts, error counts, bytes sent, tasks completed.

**Key rule:** Never use a counter's raw value. Always use `rate()` or `increase()`:
```promql
# WRONG: Raw counter value (meaningless, always goes up)
http_requests_total

# RIGHT: Rate of requests per second over 5 minutes
rate(http_requests_total[5m])

# RIGHT: Total increase in requests over 1 hour
increase(http_requests_total[1h])
```

#### 2. Gauge
A value that can **go up and down**. Represents a snapshot of current state.

```
# HELP temperature_celsius Current temperature
# TYPE temperature_celsius gauge
temperature_celsius{location="server_room"} 23.5

# HELP active_connections Current number of active connections
# TYPE active_connections gauge
active_connections{service="cp-nrti-apis"} 847
```

**Use cases:** Temperature, memory usage, active connections, queue depth, CPU utilization.

**Key functions for gauges:**
```promql
# Current value
active_connections

# Average over time
avg_over_time(active_connections[5m])

# Min/Max over time
min_over_time(active_connections[1h])
max_over_time(active_connections[1h])

# Rate of change (useful for memory leak detection)
deriv(process_resident_memory_bytes[1h])
```

#### 3. Histogram
Samples observations and counts them in **configurable buckets**. Tracks the distribution of values.

```
# HELP http_request_duration_seconds Request latency in seconds
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{le="0.005"} 24054    # requests <= 5ms
http_request_duration_seconds_bucket{le="0.01"}  33444     # requests <= 10ms
http_request_duration_seconds_bucket{le="0.025"} 100392
http_request_duration_seconds_bucket{le="0.05"}  129389
http_request_duration_seconds_bucket{le="0.1"}   133988
http_request_duration_seconds_bucket{le="0.25"}  134978
http_request_duration_seconds_bucket{le="0.5"}   135123
http_request_duration_seconds_bucket{le="1"}     135140
http_request_duration_seconds_bucket{le="+Inf"}  135140    # total count
http_request_duration_seconds_sum  53903.7                  # total sum
http_request_duration_seconds_count 135140                  # total count
```

**Use cases:** Request latency, response size, batch processing time.

**Calculating percentiles with histograms:**
```promql
# P99 latency over 5 minutes
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))

# P50 (median) latency
histogram_quantile(0.50, rate(http_request_duration_seconds_bucket[5m]))

# Average latency
rate(http_request_duration_seconds_sum[5m]) / rate(http_request_duration_seconds_count[5m])
```

**Bucket design matters:** If your buckets are [0.01, 0.1, 1.0] but most requests take 0.05s, the P99 will be interpolated between 0.01 and 0.1 -- not precise. Choose buckets that match your SLA boundaries.

#### 4. Summary
Similar to histogram but calculates **quantiles on the client side** (in the application).

```
# HELP rpc_duration_seconds RPC latency
# TYPE rpc_duration_seconds summary
rpc_duration_seconds{quantile="0.5"}  0.042
rpc_duration_seconds{quantile="0.9"}  0.085
rpc_duration_seconds{quantile="0.99"} 0.149
rpc_duration_seconds_sum   8953.3
rpc_duration_seconds_count 112400
```

**Histogram vs Summary:**

| Aspect | Histogram | Summary |
|--------|-----------|---------|
| **Quantile calculation** | Server-side (PromQL) | Client-side (application) |
| **Aggregatable** | Yes (across instances) | No (cannot aggregate quantiles) |
| **Bucket configuration** | Required upfront | Not needed |
| **CPU cost** | Low (just increment counters) | High (streaming quantile computation) |
| **Accuracy** | Depends on bucket granularity | Configurable phi-quantile error |
| **Recommendation** | Preferred for most use cases | Use only when pre-defined quantiles suffice |

### PromQL Query Language

PromQL (Prometheus Query Language) is a functional query language for selecting and aggregating time-series data.

**Selector types:**
```promql
# Instant vector: single value per time series at a point in time
http_requests_total{job="cp-nrti-apis"}

# Range vector: set of values over a time range
http_requests_total{job="cp-nrti-apis"}[5m]

# Label matchers
http_requests_total{status=~"5.."}         # regex match: all 5xx
http_requests_total{status!="200"}          # not equal
http_requests_total{endpoint=~"/api/.*"}    # regex: all /api/ paths
```

**Essential PromQL functions:**
```promql
# rate(): per-second average rate of increase (for counters)
rate(http_requests_total[5m])

# irate(): instant rate using last two data points (more volatile)
irate(http_requests_total[5m])

# increase(): total increase over time range
increase(http_requests_total[1h])

# sum(): aggregate across labels
sum(rate(http_requests_total[5m])) by (endpoint)

# topk(): top N time series
topk(5, rate(http_requests_total[5m]))

# absent(): alert when a metric disappears
absent(up{job="cp-nrti-apis"})  # fires when service is down

# predict_linear(): predict future values
predict_linear(disk_usage_bytes[1h], 4*3600)  # predict 4 hours ahead
```

**Real-world PromQL for Walmart services:**
```promql
# Error rate for cp-nrti-apis
sum(rate(http_requests_total{job="cp-nrti-apis", status=~"5.."}[5m]))
/
sum(rate(http_requests_total{job="cp-nrti-apis"}[5m]))

# P99 latency for inventory-status-srv
histogram_quantile(0.99,
  sum(rate(http_request_duration_seconds_bucket{job="inventory-status-srv"}[5m])) by (le)
)

# Memory usage as percentage
(process_resident_memory_bytes / container_memory_limit_bytes) * 100

# Pod restart rate (detects crashloops)
increase(kube_pod_container_status_restarts_total{namespace="data-ventures"}[1h])
```

### Service Discovery

Prometheus can automatically discover scrape targets through multiple mechanisms:

| Discovery Type | How It Works | Use Case |
|---------------|-------------|----------|
| **kubernetes_sd** | Queries K8s API for pods/services/endpoints | Kubernetes clusters (Walmart WCNP) |
| **consul_sd** | Queries Consul service registry | HashiCorp Consul environments |
| **dns_sd** | DNS SRV record lookups | Traditional infrastructure |
| **file_sd** | Reads JSON/YAML target files | Static targets, file-based config |
| **ec2_sd** | Queries AWS EC2 API | AWS instances |
| **static_config** | Hardcoded targets in config | Development, known fixed targets |

**Kubernetes service discovery example:**
```yaml
scrape_configs:
  - job_name: 'kubernetes-pods'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      # Only scrape pods with annotation prometheus.io/scrape: "true"
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      # Use custom port from annotation
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_port]
        action: replace
        target_label: __address__
        regex: (.+)
```

### Alertmanager

Alertmanager handles alerts sent by Prometheus server. It takes care of deduplication, grouping, silencing, inhibition, and routing to notification receivers.

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m

route:
  receiver: 'slack-notifications'
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 30s        # wait before sending first notification
  group_interval: 5m     # wait before sending updated notification
  repeat_interval: 4h    # resend if not resolved

  routes:
    - match:
        severity: critical
      receiver: 'pagerduty-critical'
    - match:
        severity: warning
      receiver: 'slack-warnings'

receivers:
  - name: 'slack-notifications'
    slack_configs:
      - channel: '#alerts-data-ventures'
        send_resolved: true
  - name: 'pagerduty-critical'
    pagerduty_configs:
      - service_key: '<key>'

# Inhibition: suppress warning if critical is already firing
inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'instance']
```

**Alert rules example:**
```yaml
groups:
  - name: service-alerts
    rules:
      - alert: HighErrorRate
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m])) by (job)
          /
          sum(rate(http_requests_total[5m])) by (job)
          > 0.01
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate on {{ $labels.job }}"
          description: "Error rate is {{ $value | humanizePercentage }} (threshold: 1%)"

      - alert: PodCrashLooping
        expr: increase(kube_pod_container_status_restarts_total[1h]) > 5
        for: 10m
        labels:
          severity: warning
```

### Prometheus Architecture Diagram

```mermaid
graph TB
    subgraph "Kubernetes Cluster"
        SD["Service Discovery<br/>(K8s API)"]

        subgraph "Application Pods"
            APP1["cp-nrti-apis<br/>/metrics :8080"]
            APP2["inventory-status-srv<br/>/metrics :8080"]
            APP3["audit-api-logs-srv<br/>/metrics :8080"]
        end

        subgraph "Prometheus Server"
            SCRAPE["Scrape Manager"]
            TSDB["Time Series DB<br/>(Local Storage)"]
            RULES["Rule Evaluator<br/>(Recording + Alert Rules)"]
            HTTP["HTTP API<br/>(PromQL Endpoint)"]
        end

        subgraph "Alertmanager"
            DEDUP["Deduplication"]
            GROUP["Grouping"]
            ROUTE["Routing"]
        end
    end

    subgraph "Visualization"
        GRAFANA["Grafana Dashboards"]
    end

    subgraph "Notification Channels"
        SLACK["Slack"]
        PD["PagerDuty"]
        EMAIL["Email"]
    end

    subgraph "Long-Term Storage (Optional)"
        THANOS["Thanos / Cortex / Mimir"]
    end

    SD -->|"Discover targets"| SCRAPE
    SCRAPE -->|"HTTP GET /metrics<br/>every 15-30s"| APP1
    SCRAPE -->|"HTTP GET /metrics"| APP2
    SCRAPE -->|"HTTP GET /metrics"| APP3
    SCRAPE -->|"Store samples"| TSDB
    TSDB -->|"Evaluate rules"| RULES
    RULES -->|"Fire alerts"| DEDUP
    DEDUP --> GROUP --> ROUTE
    ROUTE --> SLACK
    ROUTE --> PD
    ROUTE --> EMAIL
    TSDB -->|"PromQL queries"| HTTP
    HTTP -->|"Data source"| GRAFANA
    TSDB -->|"Remote write"| THANOS
```

### Prometheus Data Model

Every time series is uniquely identified by its **metric name** and a set of **key-value labels**:

```
<metric_name>{<label1>=<value1>, <label2>=<value2>, ...}  <value>  <timestamp>

http_requests_total{method="GET", endpoint="/api/inventory", status="200"}  15234  1706140800
```

**Storage internals:**
- Data stored in 2-hour blocks on local disk
- Each block contains: chunks (compressed time series), index, tombstones, meta.json
- Blocks are compacted over time (small blocks merged into larger ones)
- Default retention: 15 days (configurable with `--storage.tsdb.retention.time`)
- Typical compression: ~1.3 bytes per sample

### Recording Rules (Pre-computed Queries)

For expensive queries that are evaluated frequently, recording rules pre-compute and save results:

```yaml
groups:
  - name: api-performance
    interval: 30s
    rules:
      # Pre-compute error rate (expensive query, used in many dashboards)
      - record: job:http_errors:rate5m
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m])) by (job)
          /
          sum(rate(http_requests_total[5m])) by (job)

      # Pre-compute P99 latency
      - record: job:http_latency_p99:5m
        expr: |
          histogram_quantile(0.99,
            sum(rate(http_request_duration_seconds_bucket[5m])) by (job, le)
          )
```

---

## 2. GRAFANA

### What is Grafana?

Grafana is an **open-source analytics and interactive visualization platform**. It provides charts, graphs, and alerts when connected to supported data sources. Grafana is the standard visualization layer for Prometheus metrics, but it supports dozens of data sources.

### Data Sources

| Data Source | Type | Use Case at Walmart/GCC |
|------------|------|------------------------|
| **Prometheus** | Time series | Application metrics, K8s metrics |
| **ClickHouse** | Analytics DB | GCC social media analytics dashboards |
| **PostgreSQL** | Relational DB | Application data, sync status |
| **Elasticsearch** | Log search | Log-based dashboards |
| **CloudWatch** | AWS metrics | AWS infrastructure monitoring |
| **BigQuery** | Data warehouse | Walmart audit log analytics |
| **Loki** | Log aggregation | Kubernetes pod logs |

### Dashboard Creation

A Grafana dashboard is a collection of **panels** organized in rows. Each panel runs a query against a data source and renders a visualization.

**Panel types:**
- **Time series:** Line/area charts for metrics over time (most common)
- **Stat:** Single value display (current error rate, uptime percentage)
- **Gauge:** Radial gauge for values within a range
- **Bar chart:** Categorical comparisons
- **Table:** Tabular data display
- **Heatmap:** Distribution over time (latency heatmaps)
- **Logs:** Log line display (with Loki or Elasticsearch)
- **Node graph:** Service dependency visualization

**Example dashboard JSON model (simplified):**
```json
{
  "dashboard": {
    "title": "CP-NRTI-APIs Service Dashboard",
    "panels": [
      {
        "title": "Request Rate",
        "type": "timeseries",
        "datasource": "Prometheus",
        "targets": [
          {
            "expr": "sum(rate(http_requests_total{job=\"cp-nrti-apis\"}[5m])) by (endpoint)",
            "legendFormat": "{{endpoint}}"
          }
        ]
      },
      {
        "title": "P99 Latency",
        "type": "timeseries",
        "datasource": "Prometheus",
        "targets": [
          {
            "expr": "histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{job=\"cp-nrti-apis\"}[5m])) by (le, endpoint))",
            "legendFormat": "{{endpoint}}"
          }
        ]
      },
      {
        "title": "Error Rate",
        "type": "stat",
        "datasource": "Prometheus",
        "targets": [
          {
            "expr": "sum(rate(http_requests_total{job=\"cp-nrti-apis\", status=~\"5..\"}[5m])) / sum(rate(http_requests_total{job=\"cp-nrti-apis\"}[5m])) * 100"
          }
        ],
        "thresholds": {
          "steps": [
            {"value": 0, "color": "green"},
            {"value": 1, "color": "yellow"},
            {"value": 5, "color": "red"}
          ]
        }
      }
    ]
  }
}
```

### Variables and Templating

Grafana variables make dashboards dynamic and reusable. Instead of hardcoding service names, you use dropdown selectors.

**Variable types:**
```
Query variable:     Populated from a data source query
Custom variable:    Manually defined list of values
Constant variable:  A fixed value (useful for base URLs)
Text box variable:  Free-form user input
Interval variable:  Time intervals ($__interval)
```

**Example: Namespace variable from Prometheus:**
```
# Variable name: namespace
# Type: Query
# Data source: Prometheus
# Query: label_values(kube_pod_info, namespace)
# Regex filter: /data-ventures|inventory|audit/
```

**Using variables in queries:**
```promql
# $namespace and $service are dashboard variables
rate(http_requests_total{namespace="$namespace", job="$service"}[5m])
```

**Chained variables (cascading dropdowns):**
```
# Variable 1: namespace
label_values(kube_pod_info, namespace)

# Variable 2: service (filtered by selected namespace)
label_values(kube_pod_info{namespace="$namespace"}, pod)
```

### Grafana Alerting

Grafana 9+ has a unified alerting system that can evaluate alert rules against any data source:

```yaml
# Grafana alert rule (conceptual)
Alert: HighLatencyAPI
Condition: P99 latency > 500ms for 5 minutes
Query: |
  histogram_quantile(0.99,
    sum(rate(http_request_duration_seconds_bucket{job="$service"}[5m])) by (le)
  )
Evaluation interval: 1m
Pending period: 5m
Notification policy:
  - Contact point: Slack #alerts-data-ventures
  - Group by: [service, endpoint]
  - Repeat interval: 4h
```

**Grafana alerting vs Prometheus Alertmanager:**

| Aspect | Grafana Alerting | Prometheus Alertmanager |
|--------|-----------------|----------------------|
| **Data sources** | Any Grafana data source | Prometheus only |
| **Configuration** | UI-based | YAML config files |
| **Multi-source correlation** | Yes (alert on Prometheus + DB data) | No |
| **Scaling** | Grafana HA required | Clustered Alertmanager |
| **At Walmart** | Used for dashboard-level alerts | Used for infrastructure alerts |

---

## 3. DYNATRACE

### What is Dynatrace?

Dynatrace is a **commercial full-stack Application Performance Management (APM) platform** that provides automatic instrumentation, distributed tracing, infrastructure monitoring, and AI-powered root cause analysis. Unlike Prometheus+Grafana (which require manual setup), Dynatrace uses an agent-based approach that auto-discovers and instruments applications.

### OneAgent Automatic Instrumentation

The core differentiator of Dynatrace is **OneAgent** -- a single agent deployed on each host (or as a Kubernetes operator) that automatically:

1. **Discovers all processes** running on the host (JVM, Node.js, .NET, Python, Go)
2. **Injects bytecode instrumentation** into Java applications at the class-loading level
3. **Captures distributed traces** across service boundaries without code changes
4. **Monitors infrastructure** (CPU, memory, disk, network) at the host level
5. **Captures full-stack topology** from user browser through load balancer, service, database

**How OneAgent works in Kubernetes (Walmart WCNP):**
```
1. DaemonSet deploys OneAgent pod on every K8s node
2. OneAgent uses init containers or CSI driver to inject into app pods
3. For Java (Spring Boot) apps:
   - Injects via -javaagent at JVM startup
   - Bytecode-instruments key classes (Servlet, JDBC, HTTP clients)
   - Zero code changes required
4. Agent communicates with Dynatrace SaaS cluster via HTTPS
```

### Service Flow Visualization

Dynatrace automatically builds a **service flow map** (called Smartscape) showing:
- Every service and its dependencies
- Request flow between services
- Database calls, external API calls, message queue interactions
- Response times at each hop
- Error rates at each service boundary

**Example: Walmart Data Ventures service flow:**
```
Supplier Request
    |
    v
[API Gateway / Torbit]
    |
    v
[cp-nrti-apis] --HTTP--> [Enterprise Inventory API]
    |                          |
    |--Kafka-->                v
    |  [audit-api-logs-srv]   [Database: PostgreSQL]
    |      |
    |      |--Kafka-->
    |      |  [Kafka Connect GCS Sink]
    |      |      |
    |      |      v
    |      |  [GCS Buckets]
    |      |
    |      v
    |  [Kafka Cluster EUS2/SCUS]
    |
    v
[inventory-status-srv] --HTTP--> [EI API]
```

Dynatrace builds this map **automatically** from OneAgent trace data. No manual configuration.

### Root Cause Analysis with Davis AI

Davis is Dynatrace's **causal AI engine**. It correlates events across the full stack to identify root causes:

**How Davis works:**
1. **Baseline learning:** Davis continuously learns normal behavior for every metric (response time, error rate, throughput) using seasonal decomposition
2. **Anomaly detection:** When a metric deviates significantly from its baseline, Davis creates a "problem"
3. **Topology correlation:** Davis walks the dependency graph (from Smartscape) to find the common root cause
4. **Root cause identification:** Instead of alerting on 50 symptoms, Davis identifies 1 root cause

**Example scenario:**
```
Symptom 1: cp-nrti-apis response time increased from 200ms to 2000ms
Symptom 2: inventory-status-srv error rate increased from 0.1% to 15%
Symptom 3: PostgreSQL connection pool exhaustion
Symptom 4: K8s node memory pressure

Davis AI Analysis:
  Root Cause: K8s node memory pressure caused PostgreSQL connection pool
  to shrink, which caused inventory-status-srv to fail, which caused
  cp-nrti-apis to retry and slow down.

  Impact: 1,200 suppliers affected. 15,000 failed requests.

  Remediation: Scale K8s node pool or increase memory limits.
```

### Dynatrace vs Prometheus+Grafana

| Aspect | Dynatrace | Prometheus + Grafana |
|--------|-----------|---------------------|
| **Cost** | Commercial ($$$) | Open-source (free) |
| **Setup** | Deploy OneAgent, auto-discovers everything | Manual scrape config, dashboard creation |
| **Instrumentation** | Automatic (bytecode injection) | Manual (add /metrics endpoint, client libraries) |
| **Distributed tracing** | Automatic (across all services) | Requires OpenTelemetry SDK integration |
| **Root cause analysis** | AI-powered (Davis) | Manual (human correlates dashboards) |
| **Infrastructure monitoring** | Built-in (host, process, container) | Requires node_exporter, kube-state-metrics |
| **Log analysis** | Built-in log ingestion | Requires separate ELK/Loki stack |
| **Alerting** | AI-based anomaly detection | Threshold-based rules |
| **Customization** | Limited to Dynatrace UI | Unlimited (PromQL, Grafana plugins) |
| **Data retention** | SaaS-managed (35 days default) | Self-managed (configurable) |
| **Scaling** | SaaS handles it | Must manage Thanos/Cortex for federation |
| **At Walmart** | Primary APM tool across all services | Used for custom metrics and detailed dashboards |
| **At GCC** | Not used | Primary monitoring stack |

**Why Walmart uses BOTH:**
- Dynatrace provides the "big picture" -- automatic topology, AI root cause, full-stack traces
- Prometheus+Grafana provides "deep detail" -- custom business metrics, PromQL flexibility, cost-free scaling
- Example: Dynatrace detects "cp-nrti-apis is slow." Grafana dashboard shows exactly which endpoint, which consumer ID, and which downstream dependency is causing the slowdown.

---

## 4. ELK STACK (Elasticsearch, Logstash, Kibana)

### What is the ELK Stack?

The ELK Stack is a collection of three open-source tools for **centralized log management**: collecting, processing, storing, and visualizing log data.

| Component | Role | Analogy |
|-----------|------|---------|
| **Elasticsearch** | Storage and search engine | The database |
| **Logstash** | Log processing pipeline | The ETL tool |
| **Kibana** | Visualization and UI | The dashboard |
| **Beats** | Lightweight data shippers | The agents |

### Elasticsearch: Full-Text Search Engine

Elasticsearch is a distributed search and analytics engine built on Apache Lucene. It stores data as JSON documents in indices.

**Core concepts:**

| Concept | Description |
|---------|-------------|
| **Index** | A collection of documents (like a database table) |
| **Document** | A JSON object (like a row) |
| **Shard** | A horizontal partition of an index (for scaling) |
| **Replica** | A copy of a shard (for fault tolerance) |
| **Mapping** | Schema definition (field types, analyzers) |
| **Inverted Index** | The core data structure for full-text search |

**How the inverted index works:**

```
Document 1: "inventory status check failed for store 4215"
Document 2: "inventory update succeeded for store 4215"
Document 3: "audit log export failed for store 8830"

Inverted Index:
  "inventory" -> [Doc 1, Doc 2]
  "status"    -> [Doc 1]
  "check"     -> [Doc 1]
  "failed"    -> [Doc 1, Doc 3]
  "store"     -> [Doc 1, Doc 2, Doc 3]
  "4215"      -> [Doc 1, Doc 2]
  "update"    -> [Doc 2]
  "succeeded" -> [Doc 2]
  "audit"     -> [Doc 3]
  "log"       -> [Doc 3]
  "export"    -> [Doc 3]
  "8830"      -> [Doc 3]

Query: "failed store 4215"
  "failed" -> [Doc 1, Doc 3]
  "store"  -> [Doc 1, Doc 2, Doc 3]
  "4215"   -> [Doc 1, Doc 2]
  Intersection with scoring -> Doc 1 (best match)
```

**Index lifecycle management (ILM):**
```
Hot phase:    0-7 days     (SSD storage, all queries)
Warm phase:   7-30 days    (HDD storage, read-only)
Cold phase:   30-90 days   (compressed, minimal replicas)
Delete phase: 90+ days     (auto-deleted)
```

**Elasticsearch query example:**
```json
{
  "query": {
    "bool": {
      "must": [
        { "match": { "service": "cp-nrti-apis" } },
        { "range": { "@timestamp": { "gte": "now-1h" } } }
      ],
      "filter": [
        { "term": { "level": "ERROR" } }
      ]
    }
  },
  "sort": [{ "@timestamp": { "order": "desc" } }],
  "size": 100
}
```

### Logstash: Log Processing Pipeline

Logstash processes logs through a three-stage pipeline: **Input -> Filter -> Output**.

```ruby
# logstash.conf
input {
  beats {
    port => 5044                    # Receive from Filebeat agents
  }
  kafka {
    bootstrap_servers => "kafka:9092"
    topics => ["application-logs"]  # Consume from Kafka
    codec => json
  }
}

filter {
  # Parse structured log lines
  grok {
    match => {
      "message" => "%{TIMESTAMP_ISO8601:timestamp} %{LOGLEVEL:level} %{DATA:logger} - %{GREEDYDATA:msg}"
    }
  }

  # Parse JSON fields
  json {
    source => "msg"
    target => "parsed"
  }

  # Enrich with GeoIP
  geoip {
    source => "client_ip"
  }

  # Add computed fields
  mutate {
    add_field => { "environment" => "production" }
    remove_field => ["agent", "ecs", "host"]
  }

  # Date parsing
  date {
    match => ["timestamp", "ISO8601"]
    target => "@timestamp"
  }

  # Drop debug logs in production
  if [level] == "DEBUG" {
    drop {}
  }
}

output {
  elasticsearch {
    hosts => ["http://elasticsearch:9200"]
    index => "logs-%{[service]}-%{+YYYY.MM.dd}"
    template_name => "logs"
  }

  # Also send errors to a dedicated index
  if [level] == "ERROR" {
    elasticsearch {
      hosts => ["http://elasticsearch:9200"]
      index => "errors-%{+YYYY.MM.dd}"
    }
  }
}
```

### Kibana: Visualization

Kibana provides:
- **Discover:** Search and browse raw log documents
- **Dashboards:** Visual panels combining multiple visualizations
- **Lens:** Drag-and-drop visualization builder
- **Alerting:** Rule-based alerts on log patterns
- **APM:** Application performance monitoring (if using Elastic APM)

### Filebeat and Metricbeat

**Filebeat** is a lightweight log shipper that:
- Tails log files on disk
- Handles log rotation, backpressure, and at-least-once delivery
- Ships to Logstash, Elasticsearch, or Kafka
- Uses modules for common formats (nginx, Apache, system logs)

```yaml
# filebeat.yml
filebeat.inputs:
  - type: container
    paths:
      - /var/log/containers/*.log
    processors:
      - add_kubernetes_metadata:
          host: ${NODE_NAME}

output.logstash:
  hosts: ["logstash:5044"]
```

**Metricbeat** collects system and service metrics:
- CPU, memory, disk, network (system module)
- JVM metrics (Java module)
- PostgreSQL metrics (postgresql module)
- Kubernetes metrics (kubernetes module)

### ELK Architecture Diagram

```mermaid
graph TB
    subgraph "Application Layer"
        APP1["cp-nrti-apis<br/>Pod Logs"]
        APP2["inventory-status-srv<br/>Pod Logs"]
        APP3["audit-api-logs-srv<br/>Pod Logs"]
    end

    subgraph "Data Collection"
        FB["Filebeat<br/>(DaemonSet on every K8s node)<br/>Tails container logs"]
        MB["Metricbeat<br/>(DaemonSet)<br/>System + JVM metrics"]
    end

    subgraph "Processing Layer"
        LS["Logstash<br/>- Grok parsing<br/>- JSON extraction<br/>- Enrichment<br/>- Filtering"]
        KAFKA_BUF["Kafka<br/>(Optional buffer<br/>for high throughput)"]
    end

    subgraph "Storage Layer"
        ES_HOT["Elasticsearch<br/>Hot Nodes (SSD)<br/>Recent data 0-7 days"]
        ES_WARM["Elasticsearch<br/>Warm Nodes (HDD)<br/>Older data 7-30 days"]
        ES_COLD["Elasticsearch<br/>Cold Nodes<br/>Archive 30-90 days"]
    end

    subgraph "Visualization Layer"
        KIB["Kibana<br/>- Discover (search logs)<br/>- Dashboards<br/>- Alerting<br/>- APM"]
    end

    subgraph "Alerting"
        ALERT["Kibana Alerting<br/>or ElastAlert"]
        SLACK_ELK["Slack / PagerDuty"]
    end

    APP1 --> FB
    APP2 --> FB
    APP3 --> FB
    FB --> KAFKA_BUF
    FB --> LS
    MB --> LS
    KAFKA_BUF --> LS
    LS --> ES_HOT
    ES_HOT -->|"ILM rollover"| ES_WARM
    ES_WARM -->|"ILM rollover"| ES_COLD
    ES_HOT --> KIB
    ES_WARM --> KIB
    KIB --> ALERT
    ALERT --> SLACK_ELK
```

### ELK vs Alternatives

| Aspect | ELK Stack | Loki (Grafana) | Splunk | CloudWatch Logs |
|--------|-----------|----------------|--------|----------------|
| **Cost** | Open source (self-managed) | Open source | Very expensive | Pay per GB |
| **Full-text search** | Excellent (Lucene) | No (label-based only) | Excellent | Basic |
| **Storage efficiency** | Low (indexes everything) | High (only indexes labels) | Low | Medium |
| **Query language** | KQL / Lucene | LogQL | SPL | CloudWatch Insights |
| **Setup complexity** | High | Low | Low (SaaS) | Low (managed) |
| **At Walmart** | Available but replaced by custom pipeline | Not used | Being decommissioned | Available |

---

## 5. FLAGGER

### What is Flagger?

Flagger is a **progressive delivery operator for Kubernetes**. It automates the promotion of canary deployments using metrics from Prometheus, Datadog, or other providers. Flagger works with Istio, Linkerd, App Mesh, Nginx, Contour, and Gloo Edge for traffic shifting.

**Core idea:** Instead of deploying new code to 100% of traffic instantly (risky), Flagger gradually shifts traffic from the old version to the new version while continuously checking metrics. If metrics degrade, Flagger automatically rolls back.

### How Flagger Works with Istio and Kubernetes

```
Traditional Deployment:
  Deploy v2 -> 100% traffic instantly -> Hope nothing breaks

Flagger Canary Deployment:
  Deploy v2 -> 0% traffic (canary created)
  Step 1: 10% to v2, 90% to v1 -> Check metrics -> OK
  Step 2: 20% to v2, 80% to v1 -> Check metrics -> OK
  Step 3: 30% to v2, 70% to v1 -> Check metrics -> OK
  Step 4: 40% to v2, 60% to v1 -> Check metrics -> OK
  Step 5: 50% to v2, 50% to v1 -> Check metrics -> OK
  Promotion: 100% to v2, v1 removed
```

### Flagger Canary Resource

```yaml
apiVersion: flagger.app/v1beta1
kind: Canary
metadata:
  name: cp-nrti-apis
  namespace: data-ventures
spec:
  # Reference to the Kubernetes Deployment
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: cp-nrti-apis

  # Istio virtual service for traffic shifting
  service:
    port: 8080
    targetPort: 8080
    gateways:
      - public-gateway.istio-system.svc.cluster.local
    hosts:
      - cp-nrti-apis.walmart.com

  # Canary analysis configuration
  analysis:
    # Check interval
    interval: 1m

    # Max number of failed checks before rollback
    threshold: 5

    # Max traffic percentage routed to canary
    maxWeight: 50

    # Traffic increase step
    stepWeight: 10

    # Metrics to evaluate
    metrics:
      - name: request-success-rate
        # Prometheus query: percentage of successful requests
        thresholdRange:
          min: 99
        interval: 1m

      - name: request-duration
        # Prometheus query: P99 latency
        thresholdRange:
          max: 500
        interval: 1m

    # Webhooks for custom checks
    webhooks:
      - name: load-test
        type: rollout
        url: http://flagger-loadtester.test/
        metadata:
          cmd: "hey -z 1m -q 10 -c 2 http://cp-nrti-apis-canary:8080/health"
```

### Canary Analysis with Metrics

Flagger queries Prometheus to evaluate canary health at each step:

```promql
# Success rate metric (built-in)
# Flagger computes this from Istio telemetry:
sum(rate(istio_requests_total{
  reporter="destination",
  destination_workload_namespace="data-ventures",
  destination_workload="cp-nrti-apis",
  response_code!~"5.*"
}[1m]))
/
sum(rate(istio_requests_total{
  reporter="destination",
  destination_workload_namespace="data-ventures",
  destination_workload="cp-nrti-apis"
}[1m]))
* 100

# Latency metric (built-in)
histogram_quantile(0.99,
  sum(rate(istio_request_duration_milliseconds_bucket{
    reporter="destination",
    destination_workload_namespace="data-ventures",
    destination_workload="cp-nrti-apis"
  }[1m])) by (le)
)
```

**Custom metrics (beyond built-in):**
```yaml
# flagger-metric-template.yaml
apiVersion: flagger.app/v1beta1
kind: MetricTemplate
metadata:
  name: kafka-consumer-lag
  namespace: data-ventures
spec:
  provider:
    type: prometheus
    address: http://prometheus:9090
  query: |
    max(kafka_consumer_group_lag{
      topic="api_logs_audit_prod",
      consumergroup=~"{{ target }}-.*"
    })
```

### Flagger Canary to Primary Promotion Flow

```mermaid
sequenceDiagram
    participant DEV as Developer
    participant K8S as Kubernetes
    participant FL as Flagger Controller
    participant ISTIO as Istio VirtualService
    participant PROM as Prometheus
    participant SLACK as Slack

    DEV->>K8S: kubectl apply (new image tag)
    K8S->>FL: Deployment change detected

    FL->>K8S: Create canary Deployment<br/>(cp-nrti-apis-canary)
    FL->>ISTIO: Set weights: primary=100%, canary=0%
    FL->>SLACK: "Canary initialized for cp-nrti-apis"

    Note over FL: Wait for canary pods to be ready

    loop Every 1 minute (analysis interval)
        FL->>ISTIO: Increase canary weight by stepWeight (10%)
        FL->>PROM: Query: request-success-rate >= 99%?
        FL->>PROM: Query: request-duration P99 < 500ms?

        alt Metrics PASS
            FL->>SLACK: "Canary weight advanced to X%"
            Note over FL: Continue to next step
        else Metrics FAIL
            FL->>FL: Increment failure counter
            alt Failures >= threshold (5)
                FL->>ISTIO: Set weights: primary=100%, canary=0%
                FL->>K8S: Scale down canary to 0
                FL->>SLACK: "ROLLBACK: Canary failed for cp-nrti-apis"
                Note over FL: Canary analysis aborted
            else Failures < threshold
                Note over FL: Retry at same weight
            end
        end
    end

    Note over FL: Canary reached maxWeight (50%)<br/>and all checks passed

    FL->>K8S: Copy canary spec to primary Deployment
    FL->>ISTIO: Set weights: primary=100%, canary=0%
    FL->>K8S: Scale down canary to 0
    FL->>SLACK: "Canary PROMOTED for cp-nrti-apis"
```

### Flagger at Walmart (KITT + Flagger)

At Walmart, Flagger is integrated into **KITT** (Walmart's internal deployment platform built on Kubernetes):

```yaml
# kitt.yml (Walmart deployment config)
flagger:
  enabled: true
  analysis:
    threshold: 5
    maxWeight: 50
    stepWeight: 10
    interval: 1m
    metrics:
    - name: request-success-rate
      threshold: 99
    - name: request-duration
      threshold: 500
```

**Deployment flow at Walmart:**
```
1. Developer merges PR to main branch
2. CI/CD pipeline builds Docker image, pushes to registry
3. KITT updates the Deployment manifest with new image tag
4. Flagger detects the change and starts canary analysis
5. Traffic gradually shifts: 0% -> 10% -> 20% -> 30% -> 40% -> 50%
6. At each step, Flagger checks Prometheus metrics (via Istio telemetry)
7. If all checks pass at maxWeight, Flagger promotes canary to primary
8. If any step fails 5 times, Flagger rolls back to previous version
```

### Flagger Deployment Strategies

| Strategy | How It Works | Use Case |
|----------|-------------|----------|
| **Canary** | Gradual traffic shifting by percentage | Standard deployments (Walmart) |
| **A/B Testing** | Route by HTTP header or cookie | Feature flag testing |
| **Blue/Green** | Instant switch after validation | Database migrations, breaking changes |

---

## 6. OBSERVABILITY INTERVIEW Q&A

### Q1: What is the difference between monitoring and observability?

**Answer:** Monitoring tells you WHEN something is wrong (alerts, dashboards). Observability tells you WHY something is wrong (traces, logs, metrics correlation). Monitoring is about known-unknowns (you define what to watch). Observability is about unknown-unknowns (you can explore and discover causes).

The three pillars of observability are:
- **Metrics:** Numeric measurements over time (Prometheus) -- "What is happening?"
- **Logs:** Discrete events with context (ELK, Loki) -- "What happened?"
- **Traces:** Request flow across services (Jaeger, Dynatrace) -- "Where did it happen?"

At Walmart, we used all three: Prometheus metrics for dashboards and alerts, Dynatrace for distributed tracing and auto-discovery, and a custom audit logging pipeline (Kafka to GCS to BigQuery) for queryable structured logs.

### Q2: Why does Prometheus use a pull-based model instead of push-based?

**Answer:** Pull-based gives Prometheus several advantages:
1. **Health detection for free:** If a scrape fails, the target is down. With push, silence is ambiguous.
2. **Central control:** Prometheus controls scrape interval and target list. No misconfigured agents flooding the system.
3. **Service discovery integration:** Prometheus watches the Kubernetes API to auto-discover new pods.
4. **Simplified targets:** Applications just expose a /metrics HTTP endpoint. No agent SDK needed.

The tradeoff is that pull does not work for short-lived batch jobs (they may finish before Prometheus scrapes). For those, Prometheus provides the Pushgateway as a workaround.

### Q3: How do you choose between Histogram and Summary metric types?

**Answer:** Use Histogram in almost all cases. The key decision factor is aggregatability.

Histograms record observations in buckets. You calculate percentiles server-side with `histogram_quantile()`. Because buckets are counters, they can be aggregated across instances: "give me the P99 across all 8 pods of cp-nrti-apis." The tradeoff is that accuracy depends on bucket boundaries.

Summaries calculate percentiles client-side (in the application). They are precise for a single instance but CANNOT be aggregated. You cannot combine P99 from Pod A with P99 from Pod B to get a meaningful overall P99. Summary is only useful when you have a single instance and need exact quantiles.

### Q4: How would you set up alerting for a microservice?

**Answer:** I would use a layered approach with the RED method and USE method:

**RED method (for request-driven services):**
- **Rate:** Alert if request rate drops below baseline (service may be unreachable)
- **Errors:** Alert if error rate exceeds 1% for 5 minutes
- **Duration:** Alert if P99 latency exceeds SLA threshold

**USE method (for resources):**
- **Utilization:** CPU > 80%, Memory > 85%
- **Saturation:** Thread pool queue depth > threshold
- **Errors:** Disk errors, network errors

At Walmart, our cp-nrti-apis had these alerts:
```promql
# Error rate > 1% for 5 min = critical
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) > 0.01

# P99 latency > 500ms for 5 min = warning
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le)) > 0.5

# Pod restarts > 3 in 1 hour = warning
increase(kube_pod_container_status_restarts_total[1h]) > 3
```

### Q5: What is the purpose of Flagger in a CI/CD pipeline?

**Answer:** Flagger automates progressive delivery, specifically canary deployments. Without Flagger, you either deploy to 100% of traffic instantly (risky) or manually manage traffic splitting.

Flagger integrates with the service mesh (Istio at Walmart) to gradually shift traffic from the old version to the new version. At each step, it queries Prometheus for success rate and latency. If metrics are healthy, it increases traffic. If metrics degrade, it automatically rolls back.

At Walmart, our Flagger config did 10% traffic increments up to 50%, checking every minute. If the canary failed 5 health checks, it rolled back automatically. This caught a regression where a new version of cp-nrti-apis had a 5% error rate on one endpoint -- Flagger rolled back at the 20% traffic step before it affected most users.

### Q6: How does Dynatrace's Davis AI differ from threshold-based alerting?

**Answer:** Threshold-based alerting (Prometheus Alertmanager) fires when a metric crosses a fixed number: "alert if error rate > 1%." This has problems:
- You get alert storms (50 services all alert because one database is slow)
- Thresholds may not account for seasonal patterns (1% error rate at 3 AM is normal, at 2 PM is not)
- You must manually correlate which symptom is the root cause

Davis AI uses:
1. **Automatic baselining:** It learns the normal behavior pattern for every metric, including time-of-day and day-of-week seasonality
2. **Anomaly detection:** It detects deviations from the baseline, not fixed thresholds
3. **Topology-aware correlation:** It knows the service dependency graph (from OneAgent tracing) and walks the graph to find the root cause
4. **Single problem vs multiple alerts:** Instead of 50 alerts for 50 symptoms, Davis creates one "Problem" card with the identified root cause

### Q7: Explain the inverted index in Elasticsearch.

**Answer:** An inverted index is a mapping from content (words/tokens) to their locations in documents. It is the inverse of a forward index (document to content).

When you index a log line like "inventory check failed for store 4215", Elasticsearch:
1. Tokenizes it into terms: ["inventory", "check", "failed", "for", "store", "4215"]
2. Applies analyzers: lowercase, stemming, stop-word removal
3. For each term, records which document contains it and the position

To search for "failed store", Elasticsearch:
1. Looks up "failed" in the inverted index -- gets list of document IDs
2. Looks up "store" -- gets another list
3. Intersects the lists
4. Scores by relevance (TF-IDF or BM25)

This makes full-text search O(1) per term lookup instead of O(n) scanning every document. The tradeoff is write amplification: every indexed document must update multiple posting lists.

### Q8: How do you handle high cardinality in Prometheus?

**Answer:** High cardinality means a label has many unique values (e.g., user_id, request_id). Each unique label combination creates a new time series. 10,000 unique user IDs with 10 metric types = 100,000 time series, which can crash Prometheus.

Solutions:
1. **Never use unbounded labels:** Do not use user_id, request_id, or IP address as Prometheus labels
2. **Aggregate at the application level:** Instead of per-user metrics, emit bucketed metrics (e.g., "users with 0-100 requests", "users with 100-1000 requests")
3. **Use recording rules:** Pre-aggregate high-cardinality queries into low-cardinality results
4. **Relabeling:** Drop high-cardinality labels in Prometheus scrape config using `metric_relabel_configs`
5. **Use logs for high-cardinality data:** Store per-user/per-request data in Elasticsearch or Loki, not Prometheus

### Q9: What is the difference between logs, metrics, and traces?

**Answer:**

| Aspect | Metrics | Logs | Traces |
|--------|---------|------|--------|
| **Data type** | Numeric time series | Text events | Request flow graphs |
| **Example** | http_requests_total = 5234 | "ERROR: Connection refused to DB" | Request A -> Service B -> Service C (200ms) |
| **Cardinality** | Low (bounded labels) | High (free-form text) | Medium (trace ID per request) |
| **Storage cost** | Low (~1.3 bytes/sample) | High (full text) | Medium (spans) |
| **Query pattern** | "What is the error rate?" | "Show me all errors containing 'timeout'" | "Show me the path of request X" |
| **Retention** | Months (cheap) | Weeks (expensive) | Days (moderate) |
| **Tool** | Prometheus | ELK, Loki | Jaeger, Dynatrace |

They complement each other:
- Metrics tell you something is wrong (error rate spike)
- Traces show you where in the request flow the problem is
- Logs give you the detailed error message and stack trace

### Q10: How do you design Grafana dashboards for a production service?

**Answer:** I follow a top-down structure with four levels:

**Level 1 -- Service Overview (the "golden signals"):**
- Request rate (throughput)
- Error rate (percentage of 5xx)
- Latency (P50, P95, P99)
- Saturation (CPU, memory, connections)

**Level 2 -- Endpoint Breakdown:**
- Same metrics, but broken down by endpoint (/api/inventory, /api/status)
- Allows pinpointing which endpoint is degraded

**Level 3 -- Dependency Health:**
- Downstream service latency (Enterprise Inventory API, PostgreSQL)
- Kafka producer lag, consumer lag
- Connection pool utilization

**Level 4 -- Infrastructure:**
- Pod count, HPA scaling events
- Node CPU/memory
- Disk I/O, network throughput

I use Grafana variables ($namespace, $service, $endpoint) so one dashboard template works for all services. I add annotations for deployments so you can visually correlate metric changes with code releases.

### Q11: What are the three pillars of observability and how do they work together?

**Answer:** The three pillars are metrics, logs, and traces. In practice, you use them in a triage workflow:

1. **Alert fires from metrics:** "Error rate on cp-nrti-apis exceeded 1%"
2. **Check Grafana dashboard (metrics):** Error rate spiked at 14:32. P99 latency also increased. Specific endpoint /api/inventory/search-items is affected.
3. **Check traces (Dynatrace or Jaeger):** Look at traces for that endpoint during the spike. See that calls to Enterprise Inventory API have 30% timeout rate. Trace shows the EI API call takes 10 seconds instead of normal 200ms.
4. **Check logs (ELK or BigQuery):** Search for ERROR logs on cp-nrti-apis during 14:30-14:45. Find: "java.net.SocketTimeoutException: Read timed out" on calls to ei-inventory-history-lookup.walmart.com.
5. **Root cause:** The Enterprise Inventory API had a degradation. We did not need to change our code. We added a circuit breaker to gracefully degrade.

### Q12: How would you implement SLOs (Service Level Objectives) using Prometheus?

**Answer:** SLOs define target reliability. For example: "99.9% of requests to cp-nrti-apis should succeed with latency under 500ms."

Implementation with Prometheus:
```promql
# Define the SLI (Service Level Indicator)
# Good requests: status != 5xx AND latency < 500ms
# Total requests: all requests

# Error budget: 100% - 99.9% = 0.1% of requests can fail

# SLI: Success rate over 30 days
sum(rate(http_requests_total{job="cp-nrti-apis", status!~"5.."}[30d]))
/
sum(rate(http_requests_total{job="cp-nrti-apis"}[30d]))

# Error budget remaining
1 - (
  sum(increase(http_requests_total{job="cp-nrti-apis", status=~"5.."}[30d]))
  /
  sum(increase(http_requests_total{job="cp-nrti-apis"}[30d]))
  / (1 - 0.999)
)

# Alert when error budget is being consumed too fast
# Burn rate alert: if current error rate would exhaust budget in < 1 hour
```

---

# PART 2: DATA PIPELINE TOOLS

---

## 7. APACHE AIRFLOW

### What is Airflow?

Apache Airflow is an **open-source workflow orchestration platform** for programmatically authoring, scheduling, and monitoring data pipelines. Created at Airbnb in 2014, it is now a top-level Apache project.

**Key philosophy:** Workflows are defined as Python code (not YAML or drag-and-drop), which means they are versionable, testable, and reviewable through standard software engineering practices.

**What Airflow is NOT:**
- Not a data processing framework (it orchestrates, not processes)
- Not a streaming system (it is batch-oriented)
- Not an ETL tool itself (it triggers ETL tools like dbt, Spark, SQL)

### DAGs (Directed Acyclic Graphs)

A **DAG** is a collection of tasks with dependencies that define execution order. "Directed" means tasks have a defined direction (A runs before B). "Acyclic" means there are no circular dependencies (A cannot depend on B which depends on A).

```python
# Example DAG structure
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago
import datetime as dt

with DAG(
    dag_id="example_pipeline",
    schedule_interval="0 */3 * * *",      # Every 3 hours
    start_date=days_ago(1),
    catchup=False,                          # Don't backfill past runs
    max_active_runs=1,                      # Only 1 concurrent run
    concurrency=4,                          # Max 4 tasks in parallel
    dagrun_timeout=dt.timedelta(minutes=60),
    tags=["production", "data-pipeline"],
    default_args={
        "owner": "anshul",
        "retries": 2,
        "retry_delay": dt.timedelta(minutes=5),
        "email_on_failure": True,
        "email": ["anshul@gcc.com"],
    },
) as dag:

    extract = PythonOperator(
        task_id="extract_data",
        python_callable=extract_function,
    )

    transform = PythonOperator(
        task_id="transform_data",
        python_callable=transform_function,
    )

    load = BashOperator(
        task_id="load_to_warehouse",
        bash_command="psql -c 'COPY target FROM /tmp/data.csv'",
    )

    # Define dependencies
    extract >> transform >> load
```

### DAG Parameters Deep Dive

| Parameter | What It Does | Anshul's Usage |
|-----------|-------------|----------------|
| `schedule_interval` | Cron expression or timedelta for run frequency | `*/5 * * * *` to `0 6 */7 * *` (5-min to weekly) |
| `catchup` | If True, backfills all missed runs since start_date | Always `False` in production (avoid thundering herd) |
| `max_active_runs` | Max concurrent DAG runs | `1` for most DAGs (prevent resource contention) |
| `concurrency` | Max concurrent tasks within a DAG run | `1-4` depending on downstream capacity |
| `dagrun_timeout` | Kill the run if it exceeds this duration | `60 min` for hourly, `360 min` for daily batch |
| `on_failure_callback` | Function to call on failure | `SlackNotifier.slack_fail_alert` |
| `on_success_callback` | Function to call on success | `SlackNotifier.slack_fail_alert` (yes, same -- logs both) |

### Operators

Operators define a single task in a DAG. Each operator type knows how to perform a specific kind of work.

| Operator | Purpose | Example at GCC |
|----------|---------|---------------|
| **PythonOperator** | Execute a Python function | API calls, data fetching, custom logic |
| **BashOperator** | Execute a bash command | Shell scripts, CLI tools |
| **PostgresOperator** | Execute SQL against PostgreSQL | Table creation, data loading, atomic swaps |
| **ClickHouseOperator** | Execute SQL against ClickHouse | Export data to S3 via `INSERT INTO FUNCTION s3()` |
| **SSHOperator** | Execute command on remote host via SSH | Download files to PostgreSQL server |
| **DbtRunOperator** | Execute dbt models | `dbt run --select tag:core` |
| **ShortCircuitOperator** | Conditionally skip downstream tasks | Skip during daily batch window (19:00-22:00) |
| **DummyOperator** | No-op placeholder | DAG structure organization |
| **Sensor** | Wait for a condition to be true | Wait for file, wait for partition, wait for DAG |

**Sensor example:**
```python
from airflow.sensors.filesystem import FileSensor
from airflow.sensors.external_task import ExternalTaskSensor

# Wait for a file to appear
wait_for_file = FileSensor(
    task_id="wait_for_export",
    filepath="/tmp/leaderboard.json",
    poke_interval=60,        # Check every 60 seconds
    timeout=600,             # Give up after 10 minutes
    mode="poke",             # poke = keep worker slot; reschedule = release slot
)

# Wait for another DAG to finish
wait_for_dbt = ExternalTaskSensor(
    task_id="wait_for_dbt_daily",
    external_dag_id="dbt_daily",
    external_task_id=None,   # Wait for entire DAG to succeed
    timeout=7200,
    mode="reschedule",       # Release worker slot while waiting
)
```

### XCom: Inter-Task Communication

XCom (cross-communication) allows tasks to exchange small amounts of data.

```python
def extract(**context):
    data = fetch_from_api()
    # Push data to XCom
    context['ti'].xcom_push(key='extracted_data', value=data)
    # Or simply return it (auto-pushed with key 'return_value')
    return {"record_count": len(data), "file_path": "/tmp/data.csv"}

def transform(**context):
    # Pull data from XCom
    extracted = context['ti'].xcom_pull(task_ids='extract_data', key='return_value')
    print(f"Processing {extracted['record_count']} records from {extracted['file_path']}")

extract_task = PythonOperator(
    task_id="extract_data",
    python_callable=extract,
    provide_context=True,
)

transform_task = PythonOperator(
    task_id="transform_data",
    python_callable=transform,
    provide_context=True,
)
```

**XCom limitations:**
- Stored in Airflow's metadata database (PostgreSQL/MySQL)
- Not designed for large data (keep under 48KB)
- For large data, pass file paths or S3 URIs through XCom instead

### Scheduling: Cron Expressions

```
# Cron format: minute hour day_of_month month day_of_week
# ┌───────── minute (0-59)
# │ ┌─────── hour (0-23)
# │ │ ┌───── day of month (1-31)
# │ │ │ ┌─── month (1-12)
# │ │ │ │ ┌─ day of week (0-7, 0 and 7 are Sunday)
# │ │ │ │ │
# * * * * *

*/5 * * * *       # Every 5 minutes
*/15 * * * *      # Every 15 minutes
*/30 * * * *      # Every 30 minutes
0 * * * *         # Every hour (at minute 0)
0 */3 * * *       # Every 3 hours
0 0 * * *         # Daily at midnight
0 19 * * *        # Daily at 19:00 UTC
15 20 * * *       # Daily at 20:15 UTC
0 6 */7 * *       # Every 7 days at 06:00 UTC
```

### Executor Types

The executor determines HOW tasks are run (single process, multiple processes, distributed).

| Executor | How It Works | Use Case | At GCC |
|----------|-------------|----------|--------|
| **SequentialExecutor** | One task at a time, same process | Development only | No |
| **LocalExecutor** | Multiple tasks in parallel, same machine | Small to medium workloads | Yes (production) |
| **CeleryExecutor** | Tasks distributed to Celery workers via Redis/RabbitMQ | Large-scale, multi-machine | No |
| **KubernetesExecutor** | Each task runs in its own K8s pod | Cloud-native, isolation | Not at GCC |

**LocalExecutor at GCC:**
```
Airflow runs on a single server (gcc-airflow-prod)
LocalExecutor forks child processes for each task
parallelism = 32 (max 32 concurrent tasks across all DAGs)
Each DAG has max_active_runs=1 and concurrency=1-4
```

### Connections and Hooks

Connections store credentials for external systems. Hooks provide Python interfaces to those systems.

```python
# Connections configured in Airflow UI or environment variables
# AIRFLOW_CONN_CLICKHOUSE_GCC=clickhouse://user:pass@clickhouse-host:9000/vidooly
# AIRFLOW_CONN_PROD_PG=postgresql://user:pass@pg-host:5432/gcc_prod
# AIRFLOW_CONN_SSH_PROD_PG=ssh://user@pg-host:22

# Using connections in operators
ClickHouseOperator(
    clickhouse_conn_id='clickhouse_gcc',  # References connection
    sql="SELECT * FROM dbt.mart_leaderboard",
)

PostgresOperator(
    postgres_conn_id='prod_pg',           # References connection
    sql="SELECT count(*) FROM leaderboard",
)

SSHOperator(
    ssh_conn_id='ssh_prod_pg',            # References connection
    command="aws s3 cp s3://bucket/file.json /tmp/",
)
```

### How Anshul Used Airflow at GCC

**Scale:** 76 Airflow DAGs, frequency-based scheduling from every 5 minutes to weekly.

**Architecture pattern:** Every data sync DAG follows a 4-step pipeline:
```
Step 1: ClickHouseOperator  -- Export analytics data to S3
Step 2: SSHOperator         -- Download file to PostgreSQL server
Step 3: PostgresOperator    -- Load, transform, build indexes, atomic swap
Step 4: PostgresOperator    -- VACUUM ANALYZE
```

**Scheduling tiers (from actual production DAGs):**

| Tier | Interval | DAG Count | Example | Business Reason |
|------|----------|-----------|---------|-----------------|
| Real-time | */5 min | 2 | `dbt_recent_scl` | Monitor if scraping system is alive |
| Core | */15 min | 2 | `dbt_core` | Power influencer discovery page |
| Collections | */30 min | 2 | `dbt_collections` | Campaign tracking dashboards |
| Hourly | 0 * * * * | 12 | `sync_insta_post_insights` | Trigger API data fetching |
| Heavy | 0 */3 * * * | 8 | Heavy sync DAGs | Audience demographics (slow-changing) |
| Daily | 0 19 * * * | 15 | `dbt_daily` | Full leaderboard recomputation |
| Post-daily | 15 20 * * * | 2 | `sync_leaderboard_prod` | Export leaderboards to PostgreSQL |
| Weekly | 0 6 */7 * * | 1 | `dbt_weekly` | Week-over-week trend metrics |

**Conflict avoidance with ShortCircuitOperator:**
```python
# dbt_collections.py: Skip during daily batch window
def check_hour():
    hour = datetime.now().hour
    if 19 <= hour < 22:
        return False  # Skip: dbt_daily is running
    return True

check_hour_task = ShortCircuitOperator(
    task_id="check_hour",
    python_callable=check_hour,
)
check_hour_task >> dbt_run_task
```

### Airflow Architecture Diagram

```mermaid
graph TB
    subgraph "Airflow Components"
        WEB["Web Server<br/>(Flask UI)<br/>DAG visualization,<br/>trigger runs, view logs"]
        SCHED["Scheduler<br/>- Parses DAG files<br/>- Creates DagRuns<br/>- Queues tasks<br/>- Monitors execution"]
        EXEC["Executor<br/>(LocalExecutor at GCC)<br/>Forks child processes<br/>for each task"]
        META["Metadata DB<br/>(PostgreSQL)<br/>DAG state, task state,<br/>XCom, connections"]
    end

    subgraph "DAG Files (76 Python files)"
        DAG1["dbt_core.py<br/>*/15 min"]
        DAG2["dbt_daily.py<br/>0 19 * * *"]
        DAG3["sync_leaderboard_prod.py<br/>15 20 * * *"]
        DAG4["dbt_collections.py<br/>*/30 min"]
    end

    subgraph "External Systems"
        CH["ClickHouse<br/>(Analytics DB)"]
        S3["AWS S3<br/>(Intermediate storage)"]
        PG["PostgreSQL<br/>(API serving DB)"]
        SLACK_AF["Slack<br/>(Notifications)"]
        BEAT["Beat Scraping<br/>(Trigger crawls)"]
    end

    SCHED -->|"Parse every 30s"| DAG1
    SCHED -->|"Parse"| DAG2
    SCHED -->|"Parse"| DAG3
    SCHED -->|"Parse"| DAG4
    SCHED -->|"Read/write state"| META
    SCHED -->|"Queue tasks"| EXEC
    WEB -->|"Read state"| META
    EXEC -->|"ClickHouseOperator"| CH
    EXEC -->|"SSHOperator: aws s3 cp"| S3
    EXEC -->|"PostgresOperator"| PG
    EXEC -->|"DbtRunOperator"| CH
    EXEC -->|"PythonOperator"| BEAT
    EXEC -->|"Callback"| SLACK_AF
    EXEC -->|"Update state"| META
```

### DAG Execution Flow Diagram

```mermaid
graph LR
    subgraph "sync_leaderboard_prod DAG"
        A["fetch_leaderboard_from_ch<br/>(ClickHouseOperator)<br/>INSERT INTO FUNCTION s3()"]
        B["download_to_pg_local<br/>(SSHOperator)<br/>aws s3 cp to /tmp/"]
        C["import_to_pg_db<br/>(PostgresOperator)<br/>COPY + Transform +<br/>Index + Atomic Swap"]
        D["vacuum_to_pg_db<br/>(PostgresOperator)<br/>VACUUM ANALYZE"]
    end

    A -->|"success"| B
    B -->|"success"| C
    C -->|"success"| D

    subgraph "Step C Detail"
        C1["DROP TABLE IF EXISTS *_tmp"]
        C2["CREATE TEMP TABLE (JSONB)"]
        C3["COPY FROM /tmp/*.json"]
        C4["CREATE UNLOGGED TABLE"]
        C5["INSERT INTO ... SELECT (data->>col)::type"]
        C6["UPDATE ... SET (enrich from other tables)"]
        C7["ALTER TABLE SET LOGGED"]
        C8["CREATE INDEXES"]
        C9["BEGIN; RENAME old; RENAME new; COMMIT;"]
    end

    C1 --> C2 --> C3 --> C4 --> C5 --> C6 --> C7 --> C8 --> C9
```

---

## 8. DBT (DATA BUILD TOOL)

### What is dbt?

dbt (data build tool) is an **open-source SQL-based transformation framework** that enables data teams to transform data in their warehouse using SELECT statements. dbt handles the boilerplate (CREATE TABLE, INSERT INTO, dependency resolution, testing, documentation) while you write the business logic in SQL.

**Core philosophy:** "Analytics engineering" -- apply software engineering practices (version control, testing, documentation, modularity) to data transformations.

**What dbt does:**
- Compiles SQL SELECT statements into CREATE TABLE/VIEW/INSERT statements
- Resolves dependencies between models and runs them in the correct order
- Runs data quality tests
- Generates documentation and lineage graphs

**What dbt does NOT do:**
- Extract data from source systems (that is Airflow's job)
- Load data into the warehouse (that is also Airflow/Fivetran/Airbyte)
- dbt is the **T** in ELT (Extract-Load-Transform)

### Models

A dbt **model** is a SQL SELECT statement saved as a .sql file. dbt compiles and runs it against the data warehouse.

```sql
-- models/staging/stg_beat_instagram_account.sql
{{ config(
    materialized='table',
    engine='ReplacingMergeTree',
    order_by='ifNull(id, 0)',
    tags=["core"]
) }}

SELECT
    id,
    ig_id,
    handle,
    full_name,
    biography,
    followers,
    following,
    media_count,
    engagement_rate,
    is_verified,
    category,
    updated_at
FROM {{ source('beat_replica', 'instagram_account') }}
WHERE handle IS NOT NULL
  AND followers > 0
```

When you run `dbt run`, dbt compiles this into:
```sql
CREATE TABLE dbt.stg_beat_instagram_account
ENGINE = ReplacingMergeTree
ORDER BY ifNull(id, 0)
AS (
    SELECT
        id, ig_id, handle, full_name, biography,
        followers, following, media_count, engagement_rate,
        is_verified, category, updated_at
    FROM beat_replica.instagram_account
    WHERE handle IS NOT NULL AND followers > 0
);
```

### Sources

Sources define the raw tables that dbt reads from (but does not manage):

```yaml
# models/sources.yml
version: 2

sources:
  - name: beat_replica
    database: beat_replica
    description: "Replica of Beat's PostgreSQL database in ClickHouse"
    tables:
      - name: instagram_account
        description: "Raw Instagram profile data"
        columns:
          - name: id
            description: "Primary key"
            tests:
              - unique
              - not_null
      - name: instagram_post_simple
        description: "Raw Instagram post data"

  - name: _e
    database: _e
    description: "Event stream tables from event-grpc service"
    tables:
      - name: profile_log_events
        description: "Profile crawl log events from Beat"

  - name: coffee
    database: coffee
    description: "Coffee SaaS application database"
    tables:
      - name: post_collection
        description: "Campaign post collections"
```

### Materialization Types

| Type | SQL Generated | Storage | Rebuild Time | Use Case |
|------|-------------|---------|-------------|----------|
| **table** | `CREATE TABLE AS SELECT` | Full table on disk | Full rebuild every run | Small-medium tables, staging models |
| **view** | `CREATE VIEW AS SELECT` | No storage (computed on query) | Instant | Lightweight transformations, rarely queried |
| **incremental** | `INSERT INTO ... WHERE new_rows` | Appends only new data | Fast (only new data) | Large tables, event logs, time-series |
| **ephemeral** | Inlined as CTE | No storage, no table | N/A | Reusable SQL snippets, intermediate CTEs |

**Incremental model example (from GCC):**
```sql
-- models/staging/stg_beat_instagram_post.sql
{{ config(
    materialized='incremental',
    engine='ReplacingMergeTree',
    tags=["post_ranker_partial"],
    order_by='ifNull(id, 0)'
) }}

SELECT
    id,
    ig_id,
    shortcode,
    caption,
    like_count,
    comment_count,
    view_count,
    timestamp as post_timestamp,
    updated_at
FROM {{ source('beat_replica', 'instagram_post_simple') }}

{% if is_incremental() %}
    -- Only process rows updated in the last 4 hours
    WHERE updated_at > (SELECT max(updated_at) - INTERVAL 4 HOUR FROM {{ this }})
{% endif %}
```

**How incremental works:**
1. First run: `CREATE TABLE AS SELECT` (full table)
2. Subsequent runs: `INSERT INTO ... SELECT ... WHERE updated_at > max(updated_at) - 4 HOURS`
3. The 4-hour lookback window catches late-arriving data
4. `ReplacingMergeTree` (ClickHouse) automatically deduplicates by `order_by` key

### ref() and source() Functions

These are the core of dbt's dependency resolution:

```sql
-- source(): Reference a raw table defined in sources.yml
SELECT * FROM {{ source('beat_replica', 'instagram_account') }}
-- Compiles to: SELECT * FROM beat_replica.instagram_account

-- ref(): Reference another dbt model
SELECT * FROM {{ ref('stg_beat_instagram_account') }}
-- Compiles to: SELECT * FROM dbt.stg_beat_instagram_account
```

**Why ref() matters:**
1. **Dependency graph:** dbt builds a DAG of model dependencies from ref() calls
2. **Execution order:** dbt runs models in topological order (staging before marts)
3. **Environment switching:** ref() resolves to different schemas in dev vs prod
4. **Lineage:** dbt docs show which models depend on which

### Jinja Templating

dbt uses Jinja2 for dynamic SQL:

```sql
-- Conditional logic
{% if target.name == 'production' %}
    SELECT * FROM production.large_table
{% else %}
    SELECT * FROM dev.sample_table LIMIT 1000
{% endif %}

-- Loops
SELECT
    {% for platform in ['instagram', 'youtube', 'tiktok'] %}
        SUM(CASE WHEN platform = '{{ platform }}' THEN followers ELSE 0 END) as {{ platform }}_followers
        {% if not loop.last %},{% endif %}
    {% endfor %}
FROM profiles

-- Macros (reusable SQL functions)
{% macro calculate_engagement_rate(likes, comments, followers) %}
    CASE
        WHEN {{ followers }} > 0
        THEN ({{ likes }} + {{ comments }}) * 100.0 / {{ followers }}
        ELSE 0
    END
{% endmacro %}

-- Using the macro
SELECT
    handle,
    followers,
    {{ calculate_engagement_rate('avg_likes', 'avg_comments', 'followers') }} as engagement_rate
FROM {{ ref('stg_beat_instagram_account') }}
```

### Tests

dbt provides built-in tests and supports custom tests:

```yaml
# models/staging/schema.yml
version: 2

models:
  - name: stg_beat_instagram_account
    description: "Cleaned Instagram profile data"
    columns:
      - name: id
        tests:
          - unique
          - not_null
      - name: handle
        tests:
          - not_null
      - name: followers
        tests:
          - not_null
          - accepted_values:
              values: []  # Not applicable for numeric
      - name: engagement_rate
        tests:
          - dbt_utils.accepted_range:
              min_value: 0
              max_value: 100
```

**Custom test:**
```sql
-- tests/assert_positive_followers.sql
SELECT *
FROM {{ ref('stg_beat_instagram_account') }}
WHERE followers < 0
-- If this query returns any rows, the test FAILS
```

**dbt commands:**
```bash
dbt run                              # Run all models
dbt run --select tag:core            # Run models tagged "core"
dbt run --select stg_beat_*          # Run models matching pattern
dbt run --exclude tag:deprecated     # Exclude deprecated models
dbt run --full-refresh               # DROP + CREATE (not incremental)
dbt test                             # Run all tests
dbt test --select stg_beat_*         # Test specific models
dbt docs generate                    # Generate documentation site
dbt docs serve                       # Serve docs locally
dbt compile                          # Compile SQL without running
dbt debug                            # Test connections
```

### How Anshul Used dbt at GCC

**Scale:** 112 dbt models (29 staging + 83 marts) running against ClickHouse.

**Model architecture:**
```
SOURCES (raw databases)
  beat_replica.instagram_account        -- Raw scraped data
  beat_replica.instagram_post_simple    -- Raw post data
  _e.profile_log_events                -- Event stream logs
  coffee.post_collection               -- Campaign data
       |
       v
STAGING LAYER (29 models)
  stg_beat_instagram_account.sql       -- Type-safe, cleaned
  stg_beat_instagram_post.sql          -- Incremental model
  stg_coffee_post_collection.sql       -- Collection data
       |
       v
MART LAYER (83 models)
  mart_instagram_account.sql           -- 560 lines, 10+ JOINs
  mart_instagram_leaderboard.sql       -- Multi-dimensional rankings
  mart_leaderboard.sql                 -- Cross-platform leaderboard
  mart_time_series.sql                 -- Growth charts
  mart_collection_post.sql             -- Campaign analytics
```

**Tag-based execution:**
```python
# From Airflow DAGs that orchestrate dbt
DbtRunOperator(
    select=["tag:core"],                       # 11 core models (*/15 min)
    exclude=["tag:deprecated", "tag:post_ranker"],
    target="production",
    profile="gcc_warehouse",
)

DbtRunOperator(
    select=["tag:daily"],                      # Daily batch models
    exclude=["tag:deprecated", "tag:post_ranker", "tag:core"],
    full_refresh=True,                         # DROP + RECREATE
)
```

**ClickHouse-to-S3-to-PostgreSQL sync pattern:**
dbt models are materialized in ClickHouse (analytics DB). But the Coffee API reads from PostgreSQL (serving DB). The sync pipeline bridges them:
```
dbt model in ClickHouse  ->  S3 (JSON export)  ->  PostgreSQL (COPY + atomic swap)
```

### dbt Transformation Flow Diagram

```mermaid
graph TB
    subgraph "Raw Sources (not managed by dbt)"
        SRC1["beat_replica.instagram_account<br/>(500K+ profiles)"]
        SRC2["beat_replica.instagram_post_simple<br/>(10M+ posts)"]
        SRC3["_e.profile_log_events<br/>(Event stream from event-grpc)"]
        SRC4["coffee.post_collection<br/>(Campaign data)"]
    end

    subgraph "Staging Layer (29 models) -- Clean and type-safe"
        STG1["stg_beat_instagram_account<br/>materialized=table<br/>tag:core"]
        STG2["stg_beat_instagram_post<br/>materialized=incremental<br/>tag:post_ranker_partial"]
        STG3["stg_beat_profile_log<br/>materialized=table<br/>tag:core"]
        STG4["stg_coffee_post_collection<br/>materialized=table<br/>tag:collections"]
    end

    subgraph "Mart Layer (83 models) -- Business logic"
        MART1["mart_instagram_account<br/>560 lines, 10+ JOINs<br/>tag:core, */15 min"]
        MART2["mart_instagram_leaderboard<br/>RANK() OVER PARTITION BY<br/>tag:daily"]
        MART3["mart_leaderboard<br/>Cross-platform unified<br/>tag:daily"]
        MART4["mart_collection_post<br/>Campaign analytics<br/>tag:collections"]
        MART5["mart_time_series<br/>Growth charts<br/>tag:core"]
    end

    subgraph "Serving Layer (PostgreSQL via Airflow sync)"
        PG1["leaderboard table<br/>(atomic swap)"]
        PG2["collection_post_metrics_summary<br/>(atomic swap)"]
        PG3["time_series table<br/>(atomic swap)"]
    end

    SRC1 --> STG1
    SRC2 --> STG2
    SRC3 --> STG3
    SRC4 --> STG4

    STG1 --> MART1
    STG2 --> MART1
    STG3 --> MART1
    STG1 --> MART2
    MART2 --> MART3
    STG4 --> MART4
    STG1 --> MART5
    STG3 --> MART5

    MART3 -->|"Airflow: CH->S3->PG"| PG1
    MART4 -->|"Airflow: CH->S3->PG"| PG2
    MART5 -->|"Airflow: CH->S3->PG"| PG3
```

---

## 9. BIGQUERY

### What is BigQuery?

BigQuery is Google Cloud's **fully managed, serverless data warehouse** designed for large-scale analytics. It can query petabytes of data using standard SQL without managing any infrastructure.

**Key characteristics:**
- **Serverless:** No servers to provision, manage, or scale
- **Columnar storage:** Data stored in Capacitor format (Google's columnar format)
- **Separation of storage and compute:** Storage is in Colossus (Google's distributed file system), compute is on-demand
- **Standard SQL:** ANSI SQL with extensions for arrays, structs, geography

### Architecture

```
User Query (SQL)
    |
    v
[BigQuery API / Query Engine]
    |
    v
[Dremel Execution Engine]
    |-- Breaks query into stages
    |-- Distributes across thousands of workers
    |-- Columnar scan (reads only needed columns)
    |
    v
[Colossus (Distributed Storage)]
    |-- Data stored in Capacitor columnar format
    |-- Automatically replicated across zones
    |-- Compressed and encrypted at rest
```

### Columnar Storage Advantage

```
Row-oriented (PostgreSQL):
  Row 1: [user_id=1, name="Alice", email="alice@...", followers=50000, ...]
  Row 2: [user_id=2, name="Bob",   email="bob@...",   followers=30000, ...]
  Row 3: [user_id=3, name="Carol", email="carol@...", followers=80000, ...]

  Query: SELECT AVG(followers) FROM users
  Must read: ALL columns of ALL rows (wasteful!)

Columnar (BigQuery):
  Column "user_id":  [1, 2, 3, ...]
  Column "name":     ["Alice", "Bob", "Carol", ...]
  Column "email":    ["alice@...", "bob@...", "carol@...", ...]
  Column "followers": [50000, 30000, 80000, ...]

  Query: SELECT AVG(followers) FROM users
  Reads ONLY the "followers" column (10x less I/O!)
```

### Partitioning and Clustering

**Partitioning** physically divides a table into segments based on a column value (usually date):

```sql
CREATE TABLE `project.dataset.audit_logs`
(
    request_id STRING,
    service_name STRING,
    endpoint STRING,
    status_code INT64,
    response_time_ms FLOAT64,
    created_at TIMESTAMP,
    site_id STRING
)
PARTITION BY DATE(created_at)
CLUSTER BY service_name, site_id;
```

**How partitioning helps:**
```sql
-- Without partitioning: scans ALL data (expensive!)
SELECT * FROM audit_logs WHERE created_at > '2024-01-01'

-- With partitioning: scans only partitions for Jan 2024+
-- BigQuery automatically prunes partitions not matching the WHERE clause
-- 365 partitions/year, query for last 7 days scans only 7/365 = 2% of data
```

**Clustering** sorts data within each partition by the specified columns:
```sql
-- Clustered by service_name, site_id
-- Data within each date partition is sorted by service_name, then site_id
-- Query filtering on service_name scans only the relevant blocks

SELECT * FROM audit_logs
WHERE DATE(created_at) = '2024-01-15'    -- Partition pruning
  AND service_name = 'cp-nrti-apis'       -- Cluster pruning
  AND site_id = 'US'                      -- Cluster pruning
-- Scans maybe 0.1% of total data
```

### Streaming Inserts vs Batch Loading

| Aspect | Streaming Insert | Batch Load |
|--------|-----------------|------------|
| **Latency** | Seconds (near real-time) | Minutes to hours |
| **Cost** | $0.01 per 200 MB | Free (up to limits) |
| **Method** | `insertAll` API or `INSERT DML` | `bq load` from GCS/local file |
| **Best for** | Real-time dashboards, alerts | ETL pipelines, historical data |
| **Deduplication** | Best-effort (use `insertId`) | Exact (idempotent) |
| **At Walmart** | Not used (batch from GCS) | Yes (Parquet files from GCS) |

### How Anshul Used BigQuery at Walmart

BigQuery was the analytics layer for the audit logging pipeline:

```
Kafka (audit logs)
    |
    v
Kafka Connect GCS Sink
    |-- Writes Parquet files to GCS buckets
    |-- Partitioned by: service_name/date/endpoint_name
    |-- Three buckets: audit-api-logs-us-prod, ca-prod, mx-prod
    |
    v
GCS Buckets (Parquet files)
    |
    v
BigQuery External Tables
    |-- Points to GCS Parquet files (no data duplication)
    |-- Schema inferred from Parquet metadata
    |-- Queries scan GCS directly
    |
    v
Supplier Queries + Internal Dashboards
    |-- "Show me all failed API calls for supplier X last week"
    |-- "What is the average response time for /api/inventory today?"
    |-- "Which endpoints have the highest error rate?"
```

**External table definition:**
```sql
CREATE EXTERNAL TABLE `project.dataset.audit_logs_us`
OPTIONS (
    format = 'PARQUET',
    uris = ['gs://audit-api-logs-us-prod/topics/api_logs_audit_prod/partition_date=*/service_name=*/endpoint_name=*/*.parquet']
);

-- Query example: supplier investigating their failed requests
SELECT
    request_id,
    endpoint,
    status_code,
    response_time_ms,
    error_message,
    created_at
FROM `project.dataset.audit_logs_us`
WHERE consumer_id = 'supplier-pepsi-uuid'
  AND status_code >= 400
  AND DATE(created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
ORDER BY created_at DESC;
```

**Why external tables (not native tables):**
- No data duplication (GCS is the single source of truth)
- No ETL job needed to load data into BigQuery
- Cost-effective: storage cost is only in GCS (cheaper than BigQuery native storage)
- Tradeoff: slightly slower queries (BigQuery must read from GCS each time)

---

## 10. APACHE PARQUET

### What is Parquet?

Apache Parquet is an **open-source columnar storage file format** designed for efficient data storage and retrieval. It provides high compression ratios and is optimized for analytics workloads. Parquet is the de facto standard file format for data lakes.

### File Structure

```
Parquet File Layout:
+----------------------------------+
| Magic Number: "PAR1" (4 bytes)   |
+----------------------------------+
| Row Group 1                      |
|   +----------------------------+ |
|   | Column Chunk: user_id      | |
|   |   Page 1 (data page)      | |
|   |   Page 2 (data page)      | |
|   +----------------------------+ |
|   | Column Chunk: name         | |
|   |   Page 1 (data page)      | |
|   +----------------------------+ |
|   | Column Chunk: followers    | |
|   |   Page 1 (data page)      | |
|   +----------------------------+ |
+----------------------------------+
| Row Group 2                      |
|   +----------------------------+ |
|   | Column Chunk: user_id      | |
|   | Column Chunk: name         | |
|   | Column Chunk: followers    | |
|   +----------------------------+ |
+----------------------------------+
| Footer                           |
|   +----------------------------+ |
|   | File Metadata              | |
|   |   - Schema                 | |
|   |   - Row group metadata     | |
|   |     - Column chunk offsets | |
|   |     - Min/Max statistics   | |
|   |     - Encoding info        | |
|   |     - Compression codec    | |
|   +----------------------------+ |
+----------------------------------+
| Footer Length (4 bytes)          |
+----------------------------------+
| Magic Number: "PAR1" (4 bytes)  |
+----------------------------------+
```

**Key components:**

| Component | Description |
|-----------|-------------|
| **Row Group** | Horizontal partition of data (typically 128 MB). Contains column chunks for all columns. |
| **Column Chunk** | All data for one column within one row group. Stored contiguously for efficient I/O. |
| **Page** | The unit of I/O and compression. Each column chunk has one or more pages (typically 1 MB). |
| **Footer** | Metadata about the file: schema, row group locations, column statistics (min/max/null count). |

### Compression and Encoding

Parquet achieves excellent compression through two mechanisms:

**1. Encoding (within column chunks):**

| Encoding | How It Works | Best For |
|----------|-------------|----------|
| **Dictionary** | Replace values with integer IDs. "US"=0, "CA"=1, "MX"=2 | Low-cardinality columns (site_id, status, category) |
| **Run-Length (RLE)** | "AAABBBCC" = (A,3)(B,3)(C,2) | Sorted columns with repeated values |
| **Delta** | Store differences: [100, 102, 105] = [100, +2, +3] | Timestamps, incrementing IDs |
| **Bit Packing** | Use minimal bits for small integers | Boolean flags, small enums |

**2. Compression (across pages):**

| Codec | Compression Ratio | Speed | Use Case |
|-------|-------------------|-------|----------|
| **Snappy** | ~2:1 | Very fast | Default, balanced (Walmart GCS sink) |
| **Gzip** | ~5:1 | Slow | Maximum compression, archival |
| **Zstd** | ~4:1 | Fast | Best of both worlds |
| **LZ4** | ~2:1 | Fastest | Real-time workloads |
| **Uncompressed** | 1:1 | No overhead | When CPU is bottleneck |

**Combined effect:** A 100 GB CSV dataset might compress to 10-20 GB in Parquet (5-10x reduction) due to columnar layout + encoding + compression.

### Predicate Pushdown

Predicate pushdown allows query engines to **skip entire row groups** by reading the footer metadata (min/max statistics):

```
Footer metadata for Row Group 1:
  Column "created_at": min=2024-01-01, max=2024-01-31
  Column "site_id": min="CA", max="US"
  Column "status_code": min=200, max=503

Query: WHERE created_at >= '2024-06-01'

Engine reads footer -> Row Group 1 max is 2024-01-31 -> SKIP entire row group!
No need to decompress or read any data from Row Group 1.
```

**Projection pushdown:** If you query `SELECT user_id, followers FROM table`, the engine reads only the `user_id` and `followers` column chunks, skipping all other columns entirely.

### Parquet vs Other Formats

| Aspect | Parquet | CSV | JSON | ORC | Avro |
|--------|---------|-----|------|-----|------|
| **Storage model** | Columnar | Row | Row | Columnar | Row |
| **Compression** | Excellent (5-10x) | Poor (1x) | Poor (1x) | Excellent (5-10x) | Good (3-5x) |
| **Schema** | Embedded in file | None | Self-describing | Embedded | Separate (.avsc) |
| **Predicate pushdown** | Yes (min/max stats) | No | No | Yes | No |
| **Column pruning** | Yes (read only needed columns) | No (must read all) | No | Yes | No |
| **Nested data** | Yes (repeated/group) | No | Yes | Yes (struct) | Yes |
| **Ecosystem** | Spark, BigQuery, Athena, Presto | Everything | Everything | Hive, Spark | Kafka, Spark |
| **Best for** | Analytics, data lakes | Simple exchange | APIs, configs | Hive ecosystem | Streaming, Kafka |
| **At Walmart** | GCS audit log storage | Not used | Intermediate sync (GCC) | Not used | Kafka messages |

### How Anshul Used Parquet at Walmart

Parquet was the storage format for the entire audit logging pipeline:

**GCS bucket structure:**
```
gs://audit-api-logs-us-prod/
  topics/
    api_logs_audit_prod/
      partition_date=2024-01-15/
        service_name=cp-nrti-apis/
          endpoint_name=searchItems/
            0001.parquet        (128 MB)
            0002.parquet        (128 MB)
          endpoint_name=getItemDetails/
            0001.parquet
        service_name=inventory-status-srv/
          endpoint_name=getDCInventory/
            0001.parquet
      partition_date=2024-01-16/
        ...
```

**Why Parquet was chosen:**
1. **Compression:** 90% reduction from JSON. At 2M+ events/day, storage costs matter.
2. **BigQuery compatibility:** BigQuery reads Parquet natively without ETL.
3. **Predicate pushdown:** Supplier queries filter by date + service + endpoint. Parquet skips irrelevant row groups.
4. **Schema evolution:** New fields can be added without breaking existing files.
5. **Kafka Connect support:** The GCS Lenses Connector outputs Parquet natively.

**Cost comparison:**
```
2M events/day x 365 days = 730M events/year
Average event size: 2 KB (JSON)

JSON storage: 730M x 2 KB = 1.46 TB/year
Parquet storage: 730M x 0.2 KB = 146 GB/year (10x smaller)

GCS cost (Standard): $0.02/GB/month
JSON: 1,460 GB x $0.02 x 12 = $350/year
Parquet: 146 GB x $0.02 x 12 = $35/year

Savings: $315/year just on storage (plus faster BigQuery queries = lower compute cost)
```

---

## 11. DATA PIPELINE INTERVIEW Q&A

### Q1: What is a DAG in Airflow and why is it important?

**Answer:** A DAG (Directed Acyclic Graph) is Airflow's core abstraction for defining workflows. It is a collection of tasks with dependencies that define execution order. "Directed" means there is a defined direction (task A runs before B). "Acyclic" means there are no circular dependencies.

DAGs are important because they:
1. **Enforce execution order:** Task B will not start until Task A succeeds
2. **Enable parallelism:** Independent tasks (no dependency) run in parallel
3. **Provide idempotency:** Each DAG run has a logical date, and tasks can be re-run without side effects
4. **Enable monitoring:** Airflow's UI shows the state of every task in every run
5. **Handle failure:** If task C fails, tasks D and E (which depend on C) are automatically skipped

At GCC, I had 76 DAGs. A typical sync DAG had 4 sequential tasks: ClickHouse export to S3, S3 download to PostgreSQL server, PostgreSQL load with atomic swap, and VACUUM ANALYZE. Each step depended on the previous one.

### Q2: How do you handle task failures in Airflow?

**Answer:** Multiple levels of failure handling:

1. **Retries:** `retries=2, retry_delay=timedelta(minutes=5)` -- automatic retry with backoff
2. **Failure callbacks:** `on_failure_callback=SlackNotifier.slack_fail_alert` -- Slack notification on failure
3. **Timeouts:** `dagrun_timeout=timedelta(minutes=60)` -- kill long-running DAGs
4. **Task-level timeouts:** `execution_timeout=timedelta(minutes=30)` per task
5. **SLA monitoring:** `sla=timedelta(hours=2)` -- alert if task takes longer than expected
6. **Manual intervention:** Airflow UI allows clearing failed tasks to re-run them

At GCC, we also used `catchup=False` to prevent backfill storms after an outage. If the scheduler was down for 4 hours, we did not want 48 runs of the 5-minute DAG queued up -- just the next scheduled run.

### Q3: Explain the difference between dbt models materialized as table vs incremental.

**Answer:** A `table` materialization runs `CREATE TABLE AS SELECT` every time. It drops and rebuilds the entire table. This is simple and correct but slow for large tables.

An `incremental` materialization runs `INSERT INTO ... SELECT ... WHERE <new rows>` on subsequent runs. It only processes new data. This is fast but requires careful design:
- You must define a reliable incremental predicate (usually `WHERE updated_at > max(updated_at)`)
- Late-arriving data can be missed (we used a 4-hour lookback window to handle this)
- Schema changes require `--full-refresh` to rebuild

At GCC, our staging models for Instagram posts used incremental materialization because the table had 10M+ rows. A full rebuild took 20 minutes; an incremental run took 2 minutes. But leaderboard models used table materialization because ranking requires the entire dataset (you cannot incrementally compute a RANK() without all values).

### Q4: What is the ClickHouse-to-S3-to-PostgreSQL sync pattern and why not sync directly?

**Answer:** At GCC, analytics data lived in ClickHouse (optimized for OLAP queries) but the Coffee API served from PostgreSQL (optimized for OLTP). We synced using a three-step pattern:

1. **ClickHouse exports to S3:** `INSERT INTO FUNCTION s3('url', 'JSONEachRow') SELECT * FROM dbt.mart_leaderboard`
2. **SSHOperator downloads to PostgreSQL server:** `aws s3 cp s3://bucket/file.json /tmp/`
3. **PostgresOperator loads with atomic swap:** COPY from local file, transform JSONB to typed columns, build indexes, BEGIN/RENAME/RENAME/COMMIT

Why not sync directly?
- ClickHouse and PostgreSQL were on different VPCs/networks
- S3 decouples the systems (if PostgreSQL is slow, ClickHouse is not blocked)
- The JSON file on S3 serves as a point-in-time backup
- PostgreSQL's COPY command reads from local filesystem only
- Atomic swap (table rename) ensures the API never sees a partially-loaded table

### Q5: How does Airflow differ from a cron job?

**Answer:**

| Aspect | Cron | Airflow |
|--------|------|---------|
| **Dependencies** | None (each job is independent) | Tasks have defined dependencies |
| **Retry** | None (must build yourself) | Built-in retries with backoff |
| **Monitoring** | Log files (manual) | Web UI with task status, duration, logs |
| **Backfill** | Manual | Built-in catchup mechanism |
| **Parallelism** | Unlimited (dangerous) | Controlled (max_active_runs, concurrency) |
| **Alerting** | Must build yourself | Callbacks, SLA monitoring, email |
| **Idempotency** | Not enforced | Logical date + re-run mechanism |
| **Cross-job deps** | Not possible | ExternalTaskSensor |
| **Variables** | Environment variables | Airflow Variables, Connections, XCom |

### Q6: What is the purpose of the ref() function in dbt?

**Answer:** ref() serves three purposes:

1. **Dependency resolution:** When model B calls `{{ ref('model_A') }}`, dbt knows to run A before B. This builds the DAG of model execution order.

2. **Environment abstraction:** In development, ref() resolves to `dev_schema.model_A`. In production, it resolves to `prod_schema.model_A`. Same code, different environments.

3. **Documentation and lineage:** dbt uses ref() calls to generate a lineage graph showing which models depend on which. This is invaluable for impact analysis ("if I change this staging model, which mart models are affected?").

source() is similar but references raw tables that dbt does not manage. The distinction makes it clear which tables are dbt-managed transformations and which are external inputs.

### Q7: How would you design a data pipeline for processing 2M events per day?

**Answer:** This is exactly what I built at Walmart. The design:

1. **Ingestion (Kafka):** Events published to Kafka with Avro serialization (70% size reduction from JSON). Dual-region publishing for fault tolerance.

2. **Processing (Kafka Connect):** Three parallel GCS Sink Connectors consuming from the same topic. Custom SMT filters route events by site_id header (US, CA, MX). Automatic batching and Parquet output.

3. **Storage (GCS):** Parquet files partitioned by date/service/endpoint. 90% compression. Immutable (append-only).

4. **Analytics (BigQuery):** External tables pointing to GCS. No ETL needed. SQL queries with partition pruning.

Key design decisions:
- Kafka decouples producers from consumers (producers never blocked)
- Parquet for columnar analytics (only read needed columns)
- GCS for cheap, durable storage (pennies per GB)
- BigQuery external tables avoid data duplication
- Partition by date for time-range query efficiency

### Q8: What is predicate pushdown and why does it matter for Parquet?

**Answer:** Predicate pushdown means the query engine pushes filter conditions down to the storage layer, so data that does not match the filter is never read from disk.

Parquet enables this through **footer metadata** that stores min/max statistics for each column in each row group. When a query has `WHERE created_at >= '2024-06-01'`, the engine reads the footer, checks each row group's min/max for `created_at`, and skips any row group whose max is before June 2024.

Combined with **partition pruning** (directory-level filtering) and **column pruning** (reading only needed columns), Parquet queries can scan 1% of the actual data.

Example at Walmart: A supplier query for their failed API calls last week touches maybe 0.5% of total Parquet data: 7/365 date partitions x 1/6 services x 1/10 endpoints x only 3 needed columns out of 20.

### Q9: How do you handle schema evolution in a data pipeline?

**Answer:** Schema evolution means changing the structure of data over time (adding columns, changing types). Each tool handles it differently:

- **Parquet:** Supports additive schema evolution. New columns can be added; old files simply have NULL for the new column. Removing columns or changing types requires rewriting files.

- **Avro:** Full schema evolution with compatibility modes (backward, forward, full). The schema registry at Walmart enforced backward compatibility (new schema can read old data).

- **BigQuery:** External tables infer schema from Parquet. New columns appear automatically. For native tables, use `ALTER TABLE ADD COLUMN`.

- **dbt:** Models are re-created on each run (table materialization), so schema changes are automatic. For incremental models, `--full-refresh` is needed when adding columns.

- **Airflow:** No schema management (it is an orchestrator). But we handled schema changes by using JSONB as an intermediate format in PostgreSQL. Raw JSON was loaded first, then transformed with explicit type casts, so new fields were simply added to the SELECT.

### Q10: Explain the difference between ETL and ELT.

**Answer:**

**ETL (Extract, Transform, Load):**
- Transform happens BEFORE loading into the warehouse
- Requires a separate transformation engine (Informatica, Talend, custom code)
- Transform runs on compute you manage
- Traditional approach (pre-cloud)

**ELT (Extract, Load, Transform):**
- Load raw data into the warehouse FIRST, then transform using SQL
- Warehouse handles the heavy computation (BigQuery, Snowflake, ClickHouse)
- Transform is SQL (dbt), not custom code
- Modern approach (leverage cheap, scalable cloud warehouses)

At GCC, we used ELT:
- **Extract:** Beat scraping engine + event-grpc (extract from Instagram/YouTube APIs)
- **Load:** Raw data loaded into ClickHouse via RabbitMQ pipeline
- **Transform:** dbt models transform raw data into analytics-ready tables using SQL in ClickHouse

The advantage was that adding a new transformation was just writing a SQL file, not deploying new code. The 112 dbt models were all SQL -- no Python transformation logic needed.

### Q11: How do you ensure data quality in a pipeline?

**Answer:** Multiple layers:

1. **Schema validation at ingestion:** Avro schema enforcement at Walmart (rejects malformed messages). At GCC, GORM struct validation in event-grpc.

2. **dbt tests:** Every staging model has `not_null` and `unique` tests on primary keys. Custom tests check business rules (e.g., `engagement_rate BETWEEN 0 AND 100`).

3. **Row count validation:** After each sync, compare source count with destination count. Alert if mismatch exceeds threshold.

4. **Freshness checks:** Airflow DAGs have SLA monitoring. If `dbt_core` has not completed in 30 minutes, Slack alert fires.

5. **Atomic swaps:** The table rename pattern ensures the API never sees a partially-loaded table. Either it sees the old complete data or the new complete data.

6. **Idempotent pipelines:** Every DAG can be re-run safely. `DROP TABLE IF EXISTS *_tmp` at the start cleans up any leftover state from a previous failed run.

### Q12: What are the trade-offs of using ClickHouse vs PostgreSQL for analytics?

**Answer:**

| Aspect | ClickHouse | PostgreSQL |
|--------|-----------|------------|
| **Storage** | Columnar (column-oriented) | Row-oriented |
| **Compression** | 5-10x (columnar + codecs) | 1-2x (TOAST + basic) |
| **Analytics queries** | Extremely fast (column pruning, vectorized execution) | Slow for full-table scans |
| **Point lookups** | Slow (must reconstruct row from columns) | Fast (row stored together) |
| **Writes** | Batch-optimized (MergeTree) | Row-optimized (MVCC) |
| **Transactions** | Limited (no full ACID) | Full ACID transactions |
| **JOINs** | Limited (best with denormalized data) | Full support (normalized data) |
| **Concurrent queries** | Low (designed for few heavy queries) | High (designed for many light queries) |
| **Use at GCC** | Analytics warehouse (dbt models) | API serving database (Coffee API) |

This is exactly why we needed both databases and the sync pipeline between them. ClickHouse for analytics (dbt models computing leaderboards, rankings). PostgreSQL for serving (Coffee API with many concurrent small queries).

---

## 12. HOW ANSHUL USED THESE TOOLS

### Walmart (Data Ventures) -- Observability Stack

```
TOOL              USAGE
-----------       ------------------------------------------------
Dynatrace         Primary APM tool across all 6 microservices.
                  OneAgent auto-instruments Spring Boot apps.
                  Service flow visualization for request tracing.
                  Davis AI for root cause analysis during incidents.
                  Full-stack monitoring: JVM, K8s pods, PostgreSQL.

Prometheus        Custom metrics collection. Application-specific
                  business metrics exposed via /metrics endpoint.
                  PromQL queries for detailed dashboard panels.
                  Alert rules for error rate, latency, pod health.

Grafana           Custom dashboards for each service:
                  - Request rate, error rate, P99 latency
                  - Kafka producer/consumer lag
                  - PostgreSQL connection pool utilization
                  - HPA scaling events
                  Variables for namespace/service/endpoint filtering.

Flagger           Progressive delivery for all services via KITT.
                  Canary analysis: 10% step increments to 50% max.
                  Metrics: 99% success rate, P99 < 500ms.
                  Automatic rollback on 5 failed health checks.
                  Integrated with Istio for traffic shifting.

ELK (Wolly)       Walmart's internal log aggregation (Wolly).
                  Structured logging from all microservices.
                  Used for debugging specific request failures.
                  Replaced by custom Kafka->GCS->BigQuery pipeline
                  for audit logs when Splunk was decommissioned.
```

**Walmart observability architecture:**
```
                        +------------------+
                        |    Dynatrace     |
                        |  (Full-Stack APM)|
                        |  - Auto-tracing  |
                        |  - Davis AI      |
                        +--------+---------+
                                 |
                        OneAgent instrumentation
                                 |
+------------------+    +--------+---------+    +------------------+
|   Prometheus     |<---|  cp-nrti-apis    |--->|   Kafka          |
|  (Custom Metrics)|    |  inventory-srv   |    |  (Audit Logs)    |
+--------+---------+    |  audit-api-srv   |    +--------+---------+
         |              +------------------+             |
         v                                               v
+------------------+                            +------------------+
|    Grafana       |                            | GCS (Parquet)    |
|  (Dashboards)    |                            | BigQuery         |
+------------------+                            +------------------+

Deployment:
  KITT -> Flagger -> Istio -> Canary analysis -> Promote/Rollback
```

### GCC (Good Creator Co) -- Data Pipeline Stack

```
TOOL              USAGE
-----------       ------------------------------------------------
Apache Airflow    76 DAGs orchestrating the entire data platform.
                  Frequency-based scheduling: 5-min to weekly.
                  Operators: ClickHouse, SSH, PostgreSQL, dbt, Python.
                  Slack notifications on success/failure.
                  ShortCircuitOperator for conflict avoidance.
                  Running on single server with LocalExecutor.

dbt               112 SQL models (29 staging + 83 marts).
                  ClickHouse as the data warehouse.
                  Staging layer: clean and type-safe raw data.
                  Mart layer: business logic, rankings, aggregations.
                  Incremental models for high-volume tables.
                  Tag-based execution (core, daily, weekly, collections).
                  Orchestrated by Airflow DbtRunOperator.

ClickHouse        Analytics database for all dbt models.
                  MergeTree engine for time-series event data.
                  ReplacingMergeTree for deduplicated staging models.
                  INSERT INTO FUNCTION s3() for data export.
                  Handles 10M+ daily log events.
                  5x columnar compression vs PostgreSQL.

PostgreSQL        API serving database for Coffee API.
                  Receives data via ClickHouse->S3->PostgreSQL sync.
                  Atomic table swaps for zero-downtime updates.
                  Full indexing for OLTP query patterns.

Prometheus +      Primary observability for GCC services.
Grafana           Metrics for Beat scraping engine, event-grpc,
                  Coffee API, Airflow health.
                  Custom dashboards for pipeline monitoring.
```

**GCC data platform architecture:**
```
INGESTION                    ANALYTICS                    SERVING
+-----------+               +-----------+               +-----------+
|           |   RabbitMQ    |           |   dbt models  |           |
|   Beat    |-------------->| event-grpc|-------------->| ClickHouse|
| (Python)  |  publish()    |   (Go)    |  buffered     | (Analytics|
| 150+ async|               | 10K evt/s |  batch write  |    DB)    |
|  workers  |               +-----------+               +-----+-----+
+-----------+                                                 |
                                                              | Airflow DAGs
                                                              | CH->S3->PG sync
ORCHESTRATION                                                 |
+-----------+               +-----------+               +-----v-----+
|           |  DbtRunOp     |           |   atomic      |           |
|  Airflow  |-------------->|    dbt    |   swap        | PostgreSQL|
| (76 DAGs) |  */15 min     | (112 SQL  |-------------->| (Serving  |
| 5min-weekly|  to weekly   |  models)  |               |    DB)    |
+-----------+               +-----------+               +-----+-----+
                                                              |
                                                              | API queries
                                                              |
                                                        +-----v-----+
                                                        |  Coffee   |
                                                        |  SaaS API |
                                                        | (Python)  |
                                                        +-----------+
```

### Summary: Tools by Category

| Category | Walmart Tools | GCC Tools |
|----------|--------------|-----------|
| **APM / Tracing** | Dynatrace (OneAgent) | N/A (smaller scale) |
| **Metrics** | Prometheus | Prometheus |
| **Dashboards** | Grafana | Grafana |
| **Logging** | Wolly (ELK variant) + Kafka->GCS->BigQuery | Application logs |
| **Deployment** | Flagger + Istio + KITT | GitLab CI/CD |
| **Workflow Orchestration** | N/A (not a data platform) | Apache Airflow (76 DAGs) |
| **SQL Transformations** | N/A | dbt (112 models) |
| **Analytics DB** | BigQuery (audit log queries) | ClickHouse |
| **Serving DB** | PostgreSQL | PostgreSQL |
| **File Format** | Parquet (GCS storage) | JSON (S3 intermediate) |
| **Message Queue** | Kafka (audit logs) | RabbitMQ (event pipeline) |
| **Object Storage** | GCS (Google Cloud Storage) | AWS S3 |

---

## QUICK REFERENCE CARD

### Prometheus PromQL Cheat Sheet
```promql
rate(counter[5m])                           # Per-second rate
increase(counter[1h])                       # Total increase
histogram_quantile(0.99, rate(bucket[5m]))  # P99 from histogram
sum(metric) by (label)                      # Aggregate by label
topk(5, metric)                             # Top 5 time series
absent(up{job="svc"})                       # Alert if metric missing
predict_linear(gauge[1h], 3600)             # Predict 1 hour ahead
avg_over_time(gauge[5m])                    # Average over window
```

### Airflow Operator Cheat Sheet
```python
PythonOperator(task_id="x", python_callable=fn)
BashOperator(task_id="x", bash_command="echo hello")
PostgresOperator(task_id="x", postgres_conn_id="pg", sql="SELECT 1")
SSHOperator(task_id="x", ssh_conn_id="ssh", command="ls")
DbtRunOperator(task_id="x", select=["tag:core"], target="production")
ShortCircuitOperator(task_id="x", python_callable=check_fn)
ExternalTaskSensor(task_id="x", external_dag_id="other_dag")
```

### dbt Command Cheat Sheet
```bash
dbt run                            # Run all models
dbt run --select tag:core          # Run by tag
dbt run --select model_name+       # Run model and all downstream
dbt run --full-refresh             # Force full rebuild (no incremental)
dbt test                           # Run all tests
dbt docs generate && dbt docs serve  # Generate and view docs
```

### Metric Types Decision Tree
```
Is the value monotonically increasing?
  YES -> Counter (use rate() to query)
  NO -> Can it go up AND down?
    YES -> Gauge
    NO -> Are you measuring a distribution (latency, size)?
      YES -> Do you need to aggregate across instances?
        YES -> Histogram
        NO  -> Summary
```

---

*This document covers the observability and data pipeline tools used across Walmart (Data Ventures) and GCC (Good Creator Co). Every tool description includes the theoretical foundation, practical configuration, and how Anshul applied it in production systems.*
