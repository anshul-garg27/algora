# HLD Playbook 2: Uber Eats Homepage (food delivery discovery)
*Asked 3x last year (once as bar-raiser, once as the PNR/train variant).
Stated focus of the real round: "FR/NFR, core entities, deep dives into
database and caching strategies."*

## The prompt
"Design the Uber Eats home page — user opens the app, sees restaurants and
dishes." Scope to excavate: discovery/browsing only, NO checkout.

## Step 1 — Requirements
- FR: nearby restaurants by location; personalized sections (carousels);
  menus on tap; search/filters (cuisine, rating, ETA, fees).
- NFR: p99 < 500ms for the home feed; 50M DAU; **freshness split** (the key
  insight to surface): availability (open/closed, item 86'd) must be
  near-real-time; ranking/popularity may lag minutes.
- Out of scope: cart, payment, courier logistics (SAY it).

## Step 2 — Estimates
50M DAU × 4 opens/day ≈ 2300 home-feeds/sec avg, ~10K peak (mealtimes —
mention the lunch spike; it justifies precomputation). 1M restaurants × menu
~100KB ≈ 100GB total menu corpus — fits comfortably in a cache tier.

## Step 3 — APIs
```
GET /v1/home?lat=..&lng=..&cursor=..
 -> { "sections": [ {"id":"nearby_fast", "title":"Fastest near you",
       "items":[{"rid":"r1","name":"...","eta_min":25,"rating":4.4,
                 "fee":29,"badges":["promo"]}], "next":"cursor"} ...]}
GET /v1/restaurants/{rid}/menu     -> sections/items with availability flags
GET /v1/search?q=&filters=...
```

## Step 4 — Data model + store choices (the round's stated focus)
- `restaurants` (id, geo, hours, rating, cuisine) — relational/Postgres:
  source of truth, moderate write rate.
- `menus` — document store (nested sections/items, read-heavy, schema-flexible).
- `availability` (rid/item → open/closed, 86'd) — **Redis**: tiny, hot,
  must be fresh; written by merchant app events.
- geo index — Redis GEO / Elasticsearch geo / H3 cells precomputed:
  `cell -> [restaurant ids]` (pick one, justify; H3 name-drop at Uber).
- `popularity` (rid → score per city) — recomputed by stream job (see
  playbook 1; this is where the archetypes connect).

## Step 5 — Architecture (walk the feed request)
```
app → gateway → Feed svc ──→ Geo svc      (cell → candidate rids, ~200)
                       ├──→ Ranking svc   (candidates + user features → order)
                       ├──→ Restaurant/Menu svc (hydrate cards, cached)
                       └──→ Availability check (Redis MGET, LAST step)
merchant app → Merchant svc → events → {availability Redis, menu store, search index}
```
Hydration order matters: rank first on cached features, availability-check
the final ~40 cards only (cheap MGET) so closed restaurants never render.

## Step 6 — Deep dives
**Caching layers (expect 10 minutes here):**
- CDN: images only.
- Edge/service cache: per-(cell, segment) precomputed candidate sets,
  TTL 1-5 min — absorbs the lunch spike.
- Menu cache: versioned keys `menu:{rid}:{version}` — merchant update bumps
  version, no purge race, old keys age out. (Versioned-keys answer = senior.)
- Availability: NO long cache — Redis read-through with 5-10s TTL at most.
  Stampede on hot restaurant: single-flight + jitter.

**"Restaurant closes RIGHT NOW — how long until users stop seeing it?"**
(real probe): merchant event → Redis write (~1s); feeds already rendered show
it until next open; tapping menu re-checks availability → error state with
alternatives. Staleness ≈ one screen, never a failed order. Walk this chain.

**Ranking svc down?** Fallback to popularity-only ordering from cache —
degraded, not down. (Graceful-degradation answers won the real round.)

**Why not MySQL for everything?** menus = deep nested docs (joins explosion);
availability = 10K+ writes/sec hot flags (row churn + replication lag where
freshness matters most); geo = needs spatial indexing. One sentence each.

**The train/PNR variant (asked!):** PNR → train route + ETAs per upcoming
station → for each station within delivery window: station cell → candidates
→ filter by prep_time < time_to_station → group sections BY STATION.
Geo query becomes (route × time-window) queries; precompute per station.
Nothing else changes — say that calmly and the variant is conquered.

## Sentences that score
- "I'm splitting freshness: availability is seconds-fresh, ranking is
  minutes-fresh — they get different stores and different caches."
- "Menu updates use versioned cache keys so I never purge-race."
- "On ranker timeout I serve popular-only — feed never 500s."
