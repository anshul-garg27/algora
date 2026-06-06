# Candidate Profile — Anshul

## Who is this person

**Anshul** is a backend software engineer based in Bengaluru, India, with **3.5+ years** of professional experience building scalable microservices, real-time data platforms, and distributed systems across fintech and SaaS domains. He currently works at **Walmart** as a **Software Engineer III** (since June 2024). He holds an M.Tech in Computer Science and Engineering from IIIT-Bangalore (2020–2022) and a B.Tech in CSE from SKIT Jaipur. He scored **AIR 1343 in GATE** (98.6 percentile, 100,000+ candidates).

His core strength is high-throughput backend systems: he has led systems handling 2M+ daily events, 10M+ daily data points, and reusable platform components adopted by 12+ engineering teams.

## Headline skills / stack

- **Languages:** Java, Python, Go, C++, Shell
- **Backend frameworks:** Spring Boot 3, Hibernate, JPA, Django, FastAPI
- **Databases:** PostgreSQL, MySQL, Azure Cosmos DB, ClickHouse, Redis
- **Infra & tooling:** Kubernetes, Docker, Kafka, RabbitMQ, Apache Airflow, dbt, Jenkins, Ansible, ELK, Grafana, Prometheus, AWS (S3), Git
- **Specialties:** performance optimization, zero-downtime migrations, high-throughput event processing, OLTP/OLAP separation, event-driven architecture

## Companies / teams

- **Walmart** — NRT (Near-Real-Time) / Data Venture team — Software Engineer III — Jun 2024–Present
- **Good Creator Co. (GCC)** — SaaS social media analytics platform — Software Engineer I — Feb 2023–May 2024
- **PayU** — API Lending — Software Engineer I — Jul 2022–Feb 2023; Software Engineer Intern (Loan Origination System) — Jan 2022–Jul 2022

## Major projects (one line each)

**Walmart**
- **Kafka audit logging library** — high-throughput, Kafka-based audit logging system processing **2M+ events/day**, shipped as a reusable JAR adopted by **12+ teams** via a single POM dependency for real-time API request/response monitoring.
- **DSD supplier notification system** — automated alerts to **1,200+ associates across 300+ stores** for Direct-Shipment-Delivery suppliers, improving stock replenishment timing by **35%**.
- **Spring Boot 3 / Java 17 migration** — led the upgrade resolving critical CVEs while managing backward compatibility, deprecations, and dependency conflicts with **zero downtime**.
- **OpenAPI-first controller revamp** — redesigned all NRT controllers using a design-first OpenAPI approach, cutting integration overhead by **30%**.

**Good Creator Co. (GCC)** — influencer/social analytics platform spanning ~6 services (beat, event-grpc, stir, coffee, saas-gateway, fake_follower_analysis)
- **Event-driven logging migration (beat → RabbitMQ → event-grpc → ClickHouse)** — replaced direct PostgreSQL time-series writes with an event pipeline using buffered Go sinkers (batch 1000 / flush 5s); achieved a **2.5x reduction in log retrieval time** (30s→12s), 5x columnar compression, supporting **billions of logs**.
- **Async data processing system (beat + event-grpc)** — hybrid multiprocessing + asyncio worker pool (150+ workers, 73 flows, SQL task queue with FOR UPDATE SKIP LOCKED) plus 26 RabbitMQ consumer queues, handling **10M+ daily data points**.
- **API + cost optimization (coffee/beat/stir)** — dual-database (PostgreSQL OLTP + ClickHouse OLAP) plus Redis caching, 3-level rate limiting, credential rotation, and incremental dbt; **25% faster API responses** and **30% lower operational cost**.
- **ETL platform (stir: Airflow + dbt)** — 76 Airflow DAGs orchestrating 112 dbt models with a ClickHouse→S3→PostgreSQL three-layer sync and atomic table swaps; **cut data latency by 50%**.
- **S3 asset upload system (beat)** — parallel download-to-S3/CDN pipeline (up to 50 workers × 100 concurrency) processing **8M images/day** with optimized infra cost.
- **Genre Insights & Keyword Analytics** — real-time social intelligence modules (YAKE keyword extraction, reach estimation), **driving 10% user engagement growth**.
- **Fake follower analysis** — solo-built end-to-end ML system (5-feature ensemble, Indic-script name database) for follower authenticity scoring.

**PayU**
- **Multi-source loan access (API Lending)** — enabled post-disbursal multi-source loan access, **scaling business operations by 40%** and expanding lending partnerships.
- **Disbursal reliability & TAT optimization** — reduced loan-disbursal error rate from **4.6% to under 0.3%** and cut TAT from **3.2 min to 1.1 min** using Java + Spring Boot.
- **LOS refactor (intern)** — refactored the Loan Origination System, raising unit test coverage from **30% to 83%**, automating quality gates with SonarQube + GitHub Actions, and adding Flyway migrations that cut deployment errors by **90%**.

## Leadership / extras

- Teaching Assistant for CS-816 Software Production Engineering at IIIT-B, mentoring 50+ students on CI/CD, version control, and production deployments.
- Led the Infinite Cultural Fest at IIIT-B (500+ attendees); ran diversity & inclusion workshops.
