# How to Speak About Beat in Interviews

> This file is about HOW to talk, not WHAT to say. Practice delivery, not memorization.

---

## The 30-Second Pitch (Use for: "Tell me about a project")

> "At Good Creator Co., I built Beat -- the core data collection engine for our influencer marketing SaaS platform. It aggregates data from 15+ social media APIs using 150+ concurrent workers across 73 scraping flows. The key engineering challenge was reliability at scale: I designed a 3-level stacked rate limiting system, credential rotation with TTL backoff, and a SQL-based task queue with FOR UPDATE SKIP LOCKED. The system processes 10 million data points daily and uploads 8 million images through an S3 pipeline."

**Delivery notes:**
- Say "Good Creator Co." not "GCC" -- the interviewer doesn't know the acronym
- Pause after "15+ social media APIs" to let the scope register
- Emphasize "FOR UPDATE SKIP LOCKED" clearly -- it shows PostgreSQL depth
- End with concrete numbers: 10M data points, 8M images

---

## The 60-Second Pitch (Use for: "Walk me through the architecture")

> "Beat is a Python service built on FastAPI and asyncio that scrapes Instagram, YouTube, and Shopify data for enterprise-scale analytics.
>
> The architecture has three entry points: a FastAPI REST API for on-demand requests, a worker pool for batch processing, and a dedicated asset upload pipeline for media.
>
> The worker pool is where most of the complexity lives. It uses multiprocessing for CPU isolation -- each of 73 flows gets dedicated OS processes. Within each process, asyncio with uvloop handles concurrent I/O. A semaphore controls how many tasks run simultaneously per worker. Tasks are picked from PostgreSQL using FOR UPDATE SKIP LOCKED, which gives us atomic distributed coordination without external infrastructure.
>
> For external API calls, I built a 3-level stacked rate limiting system backed by Redis. The crawler uses the Strategy pattern with 8 Instagram providers and 4 YouTube providers. When a provider's credential gets rate-limited, the system marks it disabled with a TTL and falls back to the next available provider.
>
> Every data change publishes an event to RabbitMQ for downstream consumption by the dashboard, notification service, and analytics pipeline."

**Delivery notes:**
- Start with the "what" (Beat, Python, FastAPI), then go to "how" (architecture)
- Use the three entry points as your mental framework
- When you say "Strategy pattern with 8 providers," they will ask a follow-up. That's good.
- End with the event-driven architecture -- it shows you think about system boundaries

---

## The 2-Minute Technical Deep Dive (Use for: "Tell me more about X")

Use whichever branch they ask about:

### Branch A: Worker Pool System
> "Each flow in the whitelist config gets N worker processes and M concurrency. For example, `refresh_profile_by_handle` gets 10 processes with 5 concurrent tasks each -- that's 50 simultaneous profile fetches.
>
> Each process runs a `looper()` function that creates a uvloop event loop and runs a `poller()`. The poller executes a SQL query every second that atomically picks the next pending task using FOR UPDATE SKIP LOCKED. If the semaphore is fully acquired -- meaning all 5 task slots are occupied -- it sleeps for 30 seconds instead of polling.
>
> Tasks run as asyncio tasks within the event loop. A background cleanup process probabilistically checks for tasks exceeding the 10-minute timeout and cancels them. Status updates happen in a finally block, so COMPLETE or FAILED is always recorded."

### Branch B: Rate Limiting & Credential Rotation
> "There are two layers of rate limiting. The first is at the API endpoint level -- 3 stacked Redis limiters controlling how many requests hit our service. The second is at the HTTP client level -- source-specific limiters for each external provider.
>
> For credentials, each API provider has multiple keys stored in PostgreSQL with an `enabled` flag and a `disabled_till` timestamp. When we need to make an API call, the Crawler base class queries for the first enabled credential for that provider. If the credential is rate-limited, we set `disabled_till = now + TTL` and the next query skips it.
>
> For Instagram followers specifically, we use weighted random selection between providers -- 70% RocketAPI (cheaper) and 30% JoTucker (more reliable). For paginated requests, we use sticky sessions -- once you start fetching followers with JoTucker, you keep using JoTucker because cursors are provider-specific."

### Branch C: Data Pipeline
> "Three stages. Retrieval calls the external API through the crawler and gets raw JSON. Ingestion parses that JSON into our internal model -- `InstagramProfileLog` with dimensions and metrics arrays. Processing upserts to PostgreSQL and publishes to RabbitMQ.
>
> The dimension/metric model is the unifying abstraction. Every platform -- Instagram, YouTube, Shopify -- produces the same structure: a list of `{key, value}` pairs for dimensions like handle, bio, profile_pic_url, and metrics like followers, likes, engagement_rate. This makes downstream analytics platform-agnostic."

---

## STAR Stories

### STAR Story 1: "Scraping at Scale" (for: "Tell me about a complex system you built")

**Situation:** "Good Creator Co. needed to aggregate data from 15+ social media APIs for influencer analytics. The existing system was single-threaded, hitting rate limits constantly, and could only process a few thousand profiles per day."

**Task:** "I was tasked with building a new data collection engine that could handle 10 million data points daily while respecting API rate limits from 8 different Instagram providers."

**Action:** "I designed a distributed architecture with three key innovations:
1. A worker pool using multiprocessing + asyncio + semaphore for 150+ concurrent workers
2. A 3-level stacked rate limiting system backed by Redis
3. A credential rotation system with TTL backoff and priority-ordered fallback chains

I also built a SQL-based task queue using PostgreSQL's FOR UPDATE SKIP LOCKED, which eliminated the need for Redis or RabbitMQ for task coordination."

**Result:** "The system processes 10M+ daily data points, uploads 8M images through S3, and has operated reliably for over a year. API costs dropped 30% through intelligent credential rotation and rate limiting. Response times improved 25% through connection pooling and asyncpg."

---

### STAR Story 2: "Provider Reliability" (for: "Tell me about a time you dealt with unreliable dependencies")

**Situation:** "Our Instagram data relied on a single RapidAPI provider. When they had outages or changed their API, all scraping stopped. This happened 2-3 times per month and each time took hours to fix."

**Task:** "Eliminate single-provider dependency and build a system that automatically handles provider failures."

**Action:** "I implemented the Strategy pattern with an interface that all providers implement. I built a crawler class with a provider registry and capability map -- each function type has an ordered list of providers that support it. I added automatic fallback: if GraphAPI fails for a profile fetch, it tries ArrayBobo, then JoTucker, then Lama, without any code changes. I also added weighted random selection for certain operations based on cost/reliability ratios."

**Result:** "Provider outages became invisible to the business. When one provider goes down, the system automatically uses alternatives. We went from 2-3 visible outages per month to zero. The abstraction also made adding new providers trivial -- just implement the interface and add an entry to the registry."

---

### STAR Story 3: "The @sessionize Decorator" (for: "Tell me about a time you simplified something")

**Situation:** "Every async function in our codebase had 10 lines of database session boilerplate: create engine, create session, try/except, commit, rollback, close. With 75+ flow functions, this was 750+ lines of repetitive error-prone code."

**Task:** "Eliminate the boilerplate while maintaining correct session lifecycle management, including transaction propagation across nested function calls."

**Action:** "I wrote the `@sessionize` decorator. It checks if a session was passed from a caller -- if so, it uses that session (propagation). If not, it creates a new session, wraps the function call in try/except, commits on success, rolls back on failure, and always closes. This means `refresh_profile` creates one session that flows through `upsert_profile` -> `upsert_insta_post` -> `upsert_insta_account` as a single transaction."

**Result:** "Eliminated 750+ lines of boilerplate. Made session management impossible to get wrong. New developers adding flows just add `@sessionize` and get correct behavior automatically. Zero session leak bugs since adoption."

---

## Pivot Phrases (When they ask about something you don't know deeply)

| When they ask about... | Pivot to... |
|------------------------|-------------|
| "What about Kubernetes?" | "We deployed on VMs with GitLab CI. The deploy script uses heartbeat for graceful shutdown. I'd be interested in containerizing with K8s for auto-scaling workers based on queue depth." |
| "Any monitoring/alerting?" | "We have trace logging for every HTTP request, task status tracking in PostgreSQL, and heartbeat health checks. If I were adding observability, I'd add OpenTelemetry tracing and Prometheus metrics for task completion rates." |
| "Unit tests?" | "The project prioritized integration-level validation through the 3-stage pipeline. Each stage's output model (InstagramProfileLog) serves as a contract. I'd add property-based testing for the parsers as a next step." |
| "Security concerns?" | "Credentials are stored in PostgreSQL JSONB with application-level access control. API keys are rotated through the credential management system. In a more mature setup, I'd use AWS Secrets Manager." |
| "How big was the team?" | "Small team of 3-4 developers. I owned the Beat engine end-to-end -- architecture, implementation, deployment. Other team members built the dashboard frontend and the analytics service that consumed Beat's events." |

---

## Numbers to Drop Naturally

Don't recite numbers. Weave them into your answers:

- "...with **150+ concurrent workers** across **73 flows**..."
- "...the system handles **10 million data points daily**..."
- "...uploads **8 million images** through S3..."
- "...across **15+ API integrations** -- 8 for Instagram alone..."
- "...with **3-level rate limiting** backed by Redis..."
- "...the codebase is about **15,000 lines** of Python with **128 dependencies**..."
- "...credential rotation across **8 Instagram providers**..."

---

## Common Mistakes to Avoid

1. **Don't say "just a scraper"** -- This is a distributed data pipeline with sophisticated reliability engineering.
2. **Don't over-explain RapidAPI** -- Just say "third-party Instagram data providers" unless asked.
3. **Don't apologize for Python** -- uvloop + asyncio is competitive with Go for I/O-bound workloads at this scale.
4. **Don't skip the "why"** -- Every choice has a reason. FOR UPDATE SKIP LOCKED is not just "because PostgreSQL" -- it's because you need queryability + persistence + priority.
5. **Don't forget the business impact** -- This isn't just engineering. It powers influencer analytics for enterprise customers paying for the SaaS platform.
