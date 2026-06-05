## 1. Requirements (Functional + Non-Functional)

> 🎙️ "Here's how I'll structure this: I'll lock the requirements and rough scale, sketch the API and data model, draw the high-level design one requirement at a time, then go deep on the two or three hardest parts — code generation, the read hot-path, and analytics — checking in with you as I go. Sound good?"

The core tension here: this is a **massively read-heavy** system with a tiny write path — we'll happily spend engineering effort making redirects cheap and fast, and treat creation as the rare event.

🏢 I'll target a **Meta-style bar** — front-load scale and the read hot-path. Tell me if it's Amazon (I'll make cost/ops first-class) or a startup (I'll start with a monolith + managed DB) and I'll re-tilt.

**Functional (the core flows — "above the line"):**
- Users should be able to **create a short URL** from a long URL (optionally a custom alias and an expiration date).
- Users should be able to **be redirected** from the short URL to the original long URL.
- Users should be able to **see basic analytics** on their short URL (click counts).

**Below the line (out of scope):** user accounts/auth flows, billing, link editing, malware/spam scanning, fancy dashboards, A/B link rotation.

**Non-Functional:**
- The system should be **highly available** for redirects — target **~99.99%** (four 9s); a dead redirect is a broken product.
- Redirects should be **fast** — **p99 < ~100ms** end to end.
- The system should **scale to ~100M new links/day** and a **read:write ratio around 100:1 or higher**.
- Short codes must be **unique** and **unguessable-ish** (no trivial enumeration).
- Consistency stance: **strong** on "a code maps to exactly one URL" (no collisions ever); **eventual** is fine for click analytics.

> 💬 "Before I draw anything — the whole game here is that reads dwarf writes by a hundred to one, so I'm going to optimize ruthlessly for the redirect path and keep creation simple."

⚠️ **Gaps I'd flag out loud:** click analytics will be eventually consistent (counts may lag a few seconds) — I'll defend that in the ledger.

🎙️ **Script:** "So at the core, three things: people create a short link, people get redirected by it, and creators want to see how many clicks it got. The redirect path is the one that matters — it has to be basically always-up and under a hundred milliseconds at p99, because a broken or slow redirect is a broken link. Codes have to be unique by construction and not trivially guessable. I'm treating strong uniqueness as a hard invariant, but I'm happy to let click counts be eventually consistent."

## 2. Clarifying Questions & Assumptions

**Questions I'd ask (and why each matters):**
- **"What's the read:write ratio and link lifetime?"** — drives whether I cache everything and how I size storage/TTL. *Assume 100:1, links default to ~years (effectively permanent unless an expiry is set).*
- **"Do we need custom aliases?"** — this creates a second namespace that can collide with generated codes; it changes the generation design. *Assume yes.*
- **"301 or 302 redirect?"** — a 301 (permanent) gets cached by browsers and **kills analytics**; a 302 (temporary) forces the browser back through us so we can count. *Assume 302.* This is a classic trap.
- **"What analytics depth — just counts, or per-geo/referrer/time series?"** — decides whether a counter suffices or I need an event pipeline. *Assume start with counts, design so richer analytics drops in.*
- **"Expected code length / vanity constraints?"** — sets the keyspace. *Assume ~7 chars, base62.*

**Assumptions I'll proceed with:** 100M creates/day, 100:1 reads, ~7-char base62 codes, 302 redirects, custom aliases allowed, links ~permanent, single logical service that we'll scale horizontally.

🤝 **Checkpoint:** "Those are my assumptions — most load-bearing one is 302-over-301 so we keep analytics. Happy with that, or do you want permanent redirects and offline analytics instead?"

Let me now do the capacity math.## 3. Scale & Capacity (talkable numbers)

I'm deferring full estimation — here are only the numbers that actually drive a decision:

| Metric | Number (rounded) | What it forces |
|---|---|---|
| Writes (creates) | ~1.2K/s avg, **~3.5K/s peak** | Trivial — one DB primary handles this |
| Reads (redirects) | ~115K/s avg, **~350K/s peak** | **THE number** — forces a cache tier + replicas |
| Read:write | ~100:1 | Spend the whole budget on reads |
| Links in 5y | ~180 billion | 7-char base62 keyspace (~3.5T) is too small long-term → **8 chars** |
| Link storage | ~90TB raw, **~275TB** with index+replication+headroom | Must shard the URL DB |
| Click events | ~10 billion/day, **~0.36PB/yr** | Biggest table by far → separate event pipeline, not the OLTP DB |
| Hot cache | ~9TB for 20% of links | Sharded Redis cluster, not one node |

**The one number that forces the design:** **~350K redirects/sec at peak.** A single Redis node tops out around **~100–150K ops/s**, so we're 2–3x past one node → we **must** shard the cache (or lean on a CDN). That's the flip threshold.

🧠 **KGS / QPS / TTL glossed below as they appear.**

🎙️ **Script:** "Let me ground this. Creates are about a thousand a second, peaking around three and a half thousand — honestly trivial, one database handles that. The action is on reads: roughly a hundred-fifteen thousand redirects a second average, peaking near three-hundred-fifty thousand. That's the number I design around. One cache node maxes out around a hundred-fifty thousand ops a second, so I'm already past a single node — I'll need a sharded cache and ideally a CDN in front. Storage-wise, links are a couple hundred terabytes over five years which I'll shard, but the click events are the monster at a third of a petabyte a year, so those go to a separate pipeline, never the main database."

## 4. Core Entities

A first draft of the key nouns — I'll detail fields in the data model later:

- **Link** — the mapping itself: short code → long URL, plus owner, created-at, expiry.
- **Short Code** — the unique base62 key in the URL (the thing in the path).
- **User / Creator** — who made the link (owns it, sees its analytics).
- **Click Event** — one redirect happening: code, timestamp, and (later) geo/referrer.

🎙️ **Script:** "The nouns are simple: a Link that maps a short code to a long URL, the Code itself which is our primary key, the Creator who owns it, and a Click Event for every redirect. I'll keep fields loose for now and nail them down in the data model once the API forces the shape."

## 5. API / Interface

Going one-by-one through the functional requirements. Default REST. The caller is identified from a **JWT** *(a signed token proving who you are — we read the user id from it, never trust a client-supplied owner id)*.

**1. Create short URL** (serves "create a link"):
```
POST /urls
Authorization: Bearer <JWT>
Idempotency-Key: <uuid>
Body: { "longUrl": "...", "customAlias": "promo2026"?, "expiresAt": "..."? }
→ 201 { "shortUrl": "https://sho.rt/aB3kZ9x", "code": "aB3kZ9x" }
```
POST because it creates a resource. The **Idempotency-Key** *(a client-generated unique id so a retried request doesn't create two links)* makes creates safe to retry.

**2. Redirect** (serves "be redirected"):
```
GET /{code}
→ 302 Found, Location: <longUrl>   (or 404 if unknown/expired)
```
GET because it's a pure read. **302** (temporary) not 301 — so the browser comes back through us each time and we can count clicks.

**3. Get analytics** (serves "see analytics"):
```
GET /urls/{code}/stats
Authorization: Bearer <JWT>
→ 200 { "code": "...", "clicks": 10432, "createdAt": "..." }
```
GET, and we **authorize**: the JWT's user must own the code, else 403.

> 💬 "Note I'm using a 302, not a 301 — that's deliberate, it keeps every click flowing through our servers so analytics actually work. And creates carry an idempotency key so a flaky network retry doesn't mint a duplicate."

🎙️ **Script:** "Three endpoints, one per requirement. POST to slash-urls creates a link and carries an idempotency key so retries are safe. A bare GET on the code does the redirect with a 302 — temporary on purpose, so clicks keep coming back to us. And a GET on stats returns counts, gated so only the owner can see them. I read the user from the JWT and never trust a client-sent owner id."

## 6. High-Level Design (built one functional requirement at a time)

### 6.1 "Create a short URL"

One sentence: take a long URL, mint a unique code, persist the mapping.

New components: a **Create Service**, a **URL database** (sharded SQL/KV), and a code source (I'll deep-dive the algorithm in §8 — for now assume a **counter-based generator**).

```mermaid
flowchart TD
  Client[Client] -->|1 POST urls| CreateSvc[Create Service]
  CreateSvc -->|2 get next id| KGS[(Counter / ID source)]
  CreateSvc -->|3 encode base62 + conditional insert| URLDB[(URL DB sharded by code)]
  CreateSvc -->|4 return short url| Client
  classDef cold fill:#3d1f0b,stroke:#d29922,stroke-width:2px,color:#e6edf3;
  class CreateSvc,KGS,URLDB cold;
</parameter>
```

1. Client POSTs the long URL.
2. Create Service grabs a unique number from the **ID source**.
3. It base62-encodes that number into a code and does a **conditional insert** *(insert only if the code doesn't already exist — catches custom-alias collisions)*; **state change**: a new row now maps code → longUrl.
4. Returns the full short URL.

> 💬 "Creation is the easy half — get a unique id, turn it into a 7-character string, store it, hand it back."

### 6.2 "Be redirected"

One sentence: look up the code, send a 302 to the long URL — and this is the path we scale.

New components: a **Read Service**, a **Redis cache** *(an in-memory key-value store — microsecond lookups, here it holds hot code→URL so we skip the DB)*, and read **replicas**.

```mermaid
flowchart TD
  Client[Client] -->|1 GET code| LB[Load Balancer]
  LB --> ReadSvc[Read Service]
  ReadSvc -->|2 lookup code| Redis[(Redis cache)]
  Redis -->|hit| ReadSvc
  ReadSvc -->|3 miss read| Replica[(URL DB replica)]
  ReadSvc -->|4 backfill| Redis
  ReadSvc -->|5 302 Location| Client
  CreateSvc[Create Service] --> URLDB[(URL DB primary)]
  URLDB -.->|async replicate| Replica
  classDef hot fill:#0b3d2e,stroke:#2ea043,stroke-width:2px,color:#e6edf3;
  classDef cold fill:#3d1f0b,stroke:#d29922,stroke-width:2px,color:#e6edf3;
  class ReadSvc,Redis,Replica,LB hot;
  class CreateSvc,URLDB cold;
</parameter>
```

1. GET hits the load balancer → Read Service.
2. Check Redis for the code.
3. On a **miss**, read from a DB replica.
4. Backfill Redis (with a TTL).
5. Return 302. **No state change** — pure read (clicks counted async, next slice).

> 💬 "Redirect is a cache lookup that almost always hits; on the rare miss we read a replica and warm the cache. Codes are immutable, so cached entries basically never go stale."

### 6.3 "See analytics"

One sentence: every redirect emits an event asynchronously so counting never slows the redirect.

New components: a **Kafka** *(a durable append-only log that buffers a firehose of events so nothing's lost if a consumer is slow — here it holds click events)*, a **stream consumer/Flink**, and an **analytics store**.

```mermaid
flowchart TD
  Client[Client] -->|1 GET code| ReadSvc[Read Service]
  ReadSvc -->|2 lookup| Redis[(Redis cache)]
  ReadSvc -->|3 302| Client
  ReadSvc -->|4 async click event| Kafka[[Kafka click log]]
  Kafka -->|5 consume| Flink[Stream aggregator]
  Flink -->|6 increment counts| Analytics[(Analytics store)]
  StatsSvc[Stats Service] --> Analytics
  Client2[Owner] -->|GET stats| StatsSvc
  classDef hot fill:#0b3d2e,stroke:#2ea043,stroke-width:2px,color:#e6edf3;
  classDef cold fill:#3d1f0b,stroke:#d29922,stroke-width:2px,color:#e6edf3;
  class ReadSvc,Redis hot;
  class Kafka,Flink,Analytics,StatsSvc cold;
</parameter>
```

1–3. Redirect happens exactly as before (fast path untouched).
4. Read Service **fire-and-forgets** a click event to Kafka — off the critical path.
5–6. Flink consumes, aggregates counts, writes the analytics store. **State change:** counters increment eventually (seconds of lag).

> 💬 "Analytics rides a separate async pipeline — the redirect never waits on it. Worst case, your click count is a few seconds behind, which is totally fine."

#### Final (high-level)

```mermaid
flowchart TD
  subgraph Clients
    C[Client]
  end
  subgraph HotReadPath
    LB[Load Balancer] --> ReadSvc[Read Service]
    ReadSvc <-->|code to url| Redis[(Redis cluster)]
    ReadSvc -->|miss| Replica[(URL DB replicas - code,longUrl,expiry)]
  end
  subgraph ColdWritePath
    CreateSvc[Create Service] --> KGS[(ID source)]
    CreateSvc --> URLDB[(URL DB primary - sharded by code)]
    URLDB -.->|replicate| Replica
  end
  subgraph Analytics
    ReadSvc -->|async| Kafka[[Kafka click log]]
    Kafka --> Flink[Aggregator] --> AStore[(Analytics store)]
  end
  C -->|GET code| LB
  C -->|POST urls| CreateSvc
  CDN[CDN edge] --> LB
  C --> CDN
  classDef hot fill:#0b3d2e,stroke:#2ea043,stroke-width:2px,color:#e6edf3;
  classDef cold fill:#3d1f0b,stroke:#d29922,stroke-width:2px,color:#e6edf3;
  class LB,ReadSvc,Redis,Replica,CDN hot;
  class CreateSvc,KGS,URLDB,Kafka,Flink,AStore cold;
</parameter>
```

🎙️ **Script:** "End to end: creates go down the cold path — get a unique id, base62-encode it, store the mapping. Redirects go down the hot path — load balancer to a stateless read service, which checks a sharded Redis cluster, falls back to a read replica on the rare miss, and returns a 302. Every redirect also fires a click event into Kafka, totally off the critical path, where a stream job aggregates counts into an analytics store the owner reads later. The two paths barely touch, which is exactly what I want given the hundred-to-one read skew."

🤝 **Checkpoint:** "That's the skeleton end to end. The two richest areas are how we generate codes without collisions and how we serve 350K redirects a second. Which do you want first — or is the analytics pipeline more interesting to you?"

## 7. Data Model & Storage

| Entity | Field | Type | Note |
|---|---|---|---|
| Link | code | string (PK) | 7–8 char base62, **partition/shard key** |
| Link | longUrl | string | up to ~2KB |
| Link | ownerId | string | from JWT |
| Link | createdAt | timestamp | |
| Link | expiresAt | timestamp? | null = permanent; drives TTL |
| ClickEvent | code | string | partition key |
| ClickEvent | ts | timestamp | |
| ClickEvent | geo/referrer | string | added later |
| Counts | code | string (PK) | |
| Counts | clicks | int64 | aggregated |

**Store choices:**
- **Link table → sharded key-value / NoSQL (e.g. DynamoDB or Cassandra)** *(a horizontally-partitioned store with no joins — perfect for "get value by key")*. Access pattern is 100% point-lookup by code, no relational queries → KV beats SQL at this scale and shards cleanly by code. Per-op consistency: **strong** on the conditional insert (uniqueness), eventually-consistent reads are fine for redirects since codes are immutable.
- **Cache → Redis cluster**, sharded by code, TTL on entries.
- **Click events → Kafka → columnar/OLAP store** (e.g. ClickHouse) — append-heavy, aggregation queries.

🎙️ **Script:** "The link table only ever gets point lookups by code and never joins, so I pick a sharded key-value store partitioned by the code itself — it scales horizontally and the conditional insert gives me strong uniqueness. Codes are immutable, so cached and replica reads being slightly stale is harmless. Click events are a totally different shape — high-volume append and aggregation — so they live in a columnar analytics store fed by Kafka, never in the OLTP path."

## 8. Deep Dives — Bad → Good → Great

🆘 **If you get stuck:** go back to "350K reads/s, codes must be unique, analytics async" and reason forward from there.

### How do we generate unique short codes without collisions?

#### Bad: Hash the long URL (e.g. MD5, take first 7 chars)
**Approach:** code = first 7 chars of MD5(longUrl). Deterministic, stateless.
**Challenges:** ⚠️ **Trap** — truncating a hash **collides** (birthday paradox bites well before the keyspace fills), and two different URLs can map to the same code, silently overwriting. You'd need a DB check + rehash loop on every write, and the same URL always yields the same code (can't have two independent links). This is the classic wrong answer.

#### Good: Random codes with a collision check
**Approach:** generate 7 random base62 chars, conditional-insert; on collision, retry.
**Challenges:** every write needs a **read-before-write** to check existence. Cheap while the table is sparse, but as it fills, retries climb. Works, but couples write latency to table fullness.

#### Great: Counter + base62 encoding (unique by construction)
**Approach:** a global monotonic counter hands each create a unique integer; we base62-encode it into the code. No collision is possible because every number is unique — **zero DB checks** for generated codes.

```mermaid
flowchart LR
  CreateSvc[Create Service] -->|1 fetch block 1000 ids| KGS[(ID allocator)]
  CreateSvc -->|2 base62 encode| Code[code aB3kZ9x]
  CreateSvc -->|3 insert| URLDB[(URL DB)]
  classDef cold fill:#3d1f0b,stroke:#d29922,stroke-width:2px,color:#e6edf3;
  class CreateSvc,KGS,URLDB,Code cold;
</parameter>
```

**The global coordinator concern (rigor #9):** a single counter is a **single point of contention**. Fix: each Create Service instance **leases a block of 1000 ids** *(claims ids 1,000,000–1,000,999 at once)* from the allocator, then serves them locally. This cuts allocator traffic by 1000x — at ~3.5K writes/s peak that's ~3.5 allocator calls/sec, trivial. Use a **highly-available allocator** (e.g. a small Raft/ZooKeeper-backed counter, or Redis INCRBY).
- **Holes/leakage:** if an instance dies mid-block, its remaining ids are lost — totally fine, the keyspace (3.5 trillion+) is enormous, gaps don't matter.
- **Unguessability:** raw counters are sequential and enumerable. Fix: pass the id through a reversible **Feistel/XOR permutation** *(a keyed bit-scramble that maps each integer to a unique scrambled integer — still collision-free, but the output looks random)* before base62. Keeps uniqueness, kills enumeration.

**Custom aliases — the namespace collision (rigor #7):** generated codes and user-chosen aliases share one code column. To prevent collision: custom aliases do a **conditional insert** (fail if exists → 409), and we **reserve a prefix or length class** for generated codes (e.g. generated codes are 8 chars, custom can be 4–7), so the two namespaces **cannot overlap by construction**. Loser of a race gets a 409 and picks another.

🎙️ **Script:** "I generate codes from a global counter and base62-encode it, so every code is unique by construction — no collision checks at all on the write path. To avoid the counter being a bottleneck, each server leases a thousand ids at a time, so the allocator sees only a few requests a second. Raw counters are guessable, so I run the number through a reversible keyed permutation first — still unique, but it looks random. And custom aliases live in a separate length class from generated codes so the two can never collide; a clash just returns a 409."

🧠 **If they ask "why a counter, not random codes?":** "Random needs a DB existence check on every write and gets worse as the table fills; a counter is unique by construction with zero checks. Hashing collides outright. The counter's the cleanest."

### How do we serve ~350K redirects/sec under 100ms?

#### Good: Sharded Redis + read replicas
**Approach:** cache code→URL in a Redis cluster (sharded by code). Sized from **miss QPS, not cache size** (rigor #2): with a defended **~90% hit ratio**, misses are ~35K/s at peak hitting replicas — spread across ~5–10 replicas that's fine. Cold-cache (0% hit) worst case = full 350K/s on the DB → would melt it, so we **pre-warm** popular codes and rely on the long tail being cacheable.
**Challenges:** cross-shard fan-out is none (point lookups), but a single **hot code** (a viral link) all routes to one shard → hot-key problem.

#### Great: CDN edge caching + Redis + hot-key replication
**Approach:** put a **CDN** *(geographically distributed edge caches — serves the redirect near the user without hitting origin)* in front. Since a code→URL mapping is immutable, the CDN can cache the 302 response itself, absorbing the bulk of those 350K/s at the edge and crushing p99 (no transcontinental hop). Redis handles CDN misses; replicas handle Redis misses.

- **Hot-key/celebrity (rigor #8):** a viral link could send millions/sec to one Redis shard (ceiling ~150K ops/s). Relief: the CDN absorbs it at the edge, and we additionally **replicate hot keys across multiple shards** / use local in-process LRU caches on the Read Service. New ceiling: effectively unbounded (edge scales horizontally).
- **p99 budget (rigor #5):** CDN hit ~10–20ms; Redis hit ~1ms + LB/app ~5ms + network ~20ms ≈ <50ms; miss adds one replica round-trip ~10ms → still under 100ms.

🎙️ **Script:** "Because a code-to-URL mapping never changes, it's perfectly cacheable, so I push redirects all the way out to a CDN edge — that absorbs most of the 350K a second near the user and keeps p99 tiny. CDN misses hit a sharded Redis cluster, and I size that from the miss rate, not the data size — at ninety percent hit ratio only about 35K a second reach the database replicas, which a handful of replicas handle easily. The scary case is a viral link hammering one shard, but the edge soaks that up and I can replicate the hot key across shards if needed."

🧠 **If they ask "what about cache staleness?":** "Codes are immutable, so there's nothing to invalidate — the only event is expiry/deletion, which I handle with a short TTL and a delete-propagation, accepting a few minutes of a dead link still resolving."

### How do we count clicks without slowing redirects? (read-your-own-writes, rigor #6)
The redirect **fire-and-forgets** to Kafka, so counting never blocks. Counts are **eventually consistent** — a creator checking stats may see a few seconds of lag. That's an acceptable staleness bound for analytics; I'd state it explicitly. **Delivery guarantee (rigor #10):** Kafka gives **at-least-once**; the aggregator dedups on (code, event-id) or accepts approximate counts, since exact click counts aren't billing-critical. If they were, I'd use idempotent consumers keyed by event id.

🎙️ **Script:** "Clicks go to Kafka asynchronously, so the redirect never waits. Counts lag a few seconds — fine for analytics. Kafka is at-least-once, so if I need exact counts I dedup on an event id in the aggregator; otherwise approximate is fine."

## 9. Reliability, Failure Modes & Cost

**Availability:** target **four 9s** on redirects, achieved via CDN + multi-AZ Redis + multiple stateless read services + replicas. The redirect path has no single point of failure.

**Per-dependency graceful degradation:**
- **Redis down** → read services fall through to DB replicas (slower but correct); CDN still serves hot links.
- **Analytics pipeline (Kafka/Flink) down** → redirects unaffected; click events buffer or drop — we lose some counts, never a redirect.
- **ID allocator down** → existing leased blocks keep serving creates; only sustained outage blocks new creates (reads unaffected).
- **Primary DB down** → reads continue from replicas; creates pause until failover.

**RPO/RTO:** Link data is the crown jewel — **RPO near zero** (synchronous replication + WAL), **RTO minutes** via replica promotion; tested restore from snapshots. Click events — **RPO minutes** acceptable (it's analytics). Multi-AZ by default; multi-region active-active for the read path if we need geo-resilience.

**Cost (rough monthly):** dominant driver is **read serving + CDN egress**, not the DB. The link DB (~275TB) is modest; the **CDN bandwidth for 350K req/s** and the **0.36PB/yr analytics store** dominate — order **~$100–200K/mo**, with CDN egress the biggest line.

**Observability:** **SLO burn-rate alerts** on redirect error-rate and p99, distributed tracing across LB→service→cache→DB, runbooks for replica promotion and cache flush.

🎙️ **Script:** "Redirects are designed to never go fully down — CDN, multi-AZ cache, replicas, stateless services. If Redis dies we serve from replicas; if analytics dies redirects don't care, we just lose some counts. Link data gets near-zero RPO with synchronous replication and tested restores; analytics can tolerate minutes. Biggest cost is CDN egress and the analytics store, not the link database — so that's where I'd watch the bill."

## 10. Trade-off Ledger

- **302 over 301:** I gave up browser-side caching of redirects (more load on us) to **keep analytics**. Reverses if analytics stops mattering — then 301 + edge caching is cheaper. (Ties to the analytics requirement.)
- **Eventually-consistent click counts:** gave up real-time exactness for redirect speed and decoupling. Reverses if counts become **billing-critical** → idempotent exactly-once consumers, higher cost. (Ties to the ⚠️ Gap I flagged.)
- **Counter + base62 over random/hash:** gave up statelessness (need a coordinator) for guaranteed uniqueness with zero write-time checks. Reverses only if a central allocator becomes operationally painful — then per-region prefixed counters.

🎙️ **Script:** "The three calls I'd revisit: the 302 costs us extra load to keep analytics; eventually-consistent counts trade exactness for speed; and the counter trades a bit of coordination for collision-free codes. Each flips at a clear threshold — if analytics dies, if counts become billing, or if the allocator becomes an ops headache."

## 11. Likely Interviewer Questions & Answers

**1. Why 302 not 301?** A 301 is permanent, so browsers and proxies cache it and future clicks never reach us — we'd lose all analytics and can't change the target. A 302 forces every click back through our servers. The cost is higher request volume, which the CDN absorbs.
> 💬 "302 keeps clicks flowing through us so analytics work; the CDN soaks up the extra traffic."

**2. How do you prevent two requests from getting the same code?** Generated codes come from a monotonic counter, so they're unique by construction — no race possible. Custom aliases use a conditional insert in a separate length class, so the loser of a race gets a 409.
> 💬 "Counter means unique by construction; custom aliases conditional-insert and the loser retries."

**3. What if the counter/allocator goes down?** Each service has already leased a block of 1000 ids it serves locally, so creates continue through the outage. Only a prolonged outage that drains every block blocks new creates — reads are entirely unaffected. We run the allocator HA on Raft so failover is seconds.
> 💬 "Servers pre-lease id blocks, so a brief allocator outage is invisible."

**4. How do you handle a viral/hot link?** The mapping is immutable so the CDN caches it at the edge, absorbing millions/sec near users. Behind that, if one Redis shard still gets hammered we replicate that key across shards and add a small in-process LRU on the read services.
> 💬 "Edge caching plus hot-key replication — one viral link never lands on a single shard."

**5. 7 chars enough?** 62^7 is ~3.5 trillion, but at 100M/day we'd exhaust a meaningful fraction within years and enumeration risk grows. I'd go to 8 chars (~218 trillion) for headroom.
> 💬 "Seven is ~3.5 trillion; I'd use eight for long-term headroom."

**6. How do you stop people enumerating all links?** Raw counters are sequential, so I pass the id through a reversible keyed permutation before encoding — still unique and collision-free, but the output looks random and can't be walked.
> 💬 "A keyed bit-scramble makes sequential ids look random while staying unique."

**7. Cache staleness on delete/expiry?** Codes never change, so the only invalidation is expiry/deletion. I set a TTL on cache and CDN entries and propagate deletes; I accept a short window where a dead link still resolves.
> 💬 "Nothing to invalidate except deletes — short TTL handles the window."

**8. How accurate are click counts?** Eventually consistent within seconds, and at-least-once from Kafka. For approximate analytics that's fine; if exactness mattered I'd dedup on event id for exactly-once.
> 💬 "Seconds of lag, approximately exact — I'd add idempotent dedup if counts became billing."

**9. SQL or NoSQL for links?** Access is pure point-lookup by code with no joins, at hundreds of TB — a sharded KV store fits perfectly and scales horizontally. SQL would work at small scale but the relational features buy us nothing here.
> 💬 "All point lookups, no joins, so sharded key-value beats SQL at this scale."

**10. How do you shard the URL DB?** By the code itself (hash partitioning), which spreads both storage and the uniform-ish lookup traffic evenly. Codes are random-looking post-permutation, so no natural hotspot in storage — traffic hotspots are handled by the cache layer.
> 💬 "Shard on the code; scrambled codes distribute evenly across shards."

**11. Multi-region?** Reads go active-active — CDN and read replicas in every region, routed by geo-DNS. Writes I'd keep single-write-region (or per-region counter prefixes) to avoid id conflicts, accepting cross-region replication lag for the rare create.
> 💬 "Reads active-active everywhere; writes single-region or region-prefixed counters."

**12. How do you handle malicious URLs?** Out of scope for core, but I'd add async scanning against a threat-intel feed on create and a takedown path that flips a flag the read service checks — without blocking the redirect path synchronously.
> 💬 "Async safe-browsing scan plus a takedown flag, kept off the hot redirect path."

**13. What's your single biggest bottleneck?** Peak redirect throughput at ~350K/s against single-node cache limits — relieved by CDN edge caching first, sharded Redis second, replicas third, raising the ceiling to effectively horizontal.
> 💬 "Read throughput; CDN plus sharded cache makes it horizontally scalable."

🎙️ **60-second verbal summary:** "A URL shortener is a read-dominated system — about 350K redirects a second against barely a few thousand creates, so I optimize entirely for reads. Creates get a unique id from a counter, base62-encode it through a reversible scramble so it's unique and unguessable, and store the code→URL mapping in a sharded key-value store. Redirects go CDN-first — the mapping is immutable so the edge caches it — then a sharded Redis cluster, then DB replicas on the rare miss, returning a 302 so analytics keep flowing. Every click fires asynchronously into Kafka where a stream job aggregates counts, completely off the critical path, so analytics are eventually consistent within seconds but redirects stay under 100ms. The whole design keeps the hot read path and the cold write path almost completely separate, which is exactly what a hundred-to-one read skew demands."