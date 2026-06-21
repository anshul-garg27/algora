# LLD Interview Curriculum — Coverage Map & Generation Plan

> Goal: cover **every type** of LLD problem an Uber SDE-2 (and similar) loop can throw —
> across 4 axes: **design patterns**, **concurrency flavours**, **data-structure-heavy**, and **pure OO modeling**.
>
> Status legend: ✅ already generated (full §1–§9) · 🟡 exists but legacy/old format · 🆕 to generate

---

## Part A — What you ALREADY have (14 sessions) — ⚠️ ALL ON THE OLD PROMPT

These are tested, frontend-openable LLD sessions in `data/conversations/*_lld.json`. They have full §1–§9 markdown, BUT they were generated **before** the prompt changes made in this session, so **none of them match the current quality bar.**

**What every one of these 14 is MISSING vs the new prompt:**
- ❌ **§3.5 API / System Interface** section — added to the prompt *after* these were built; present in **0 / 14**.
- ❌ **§4.1 per-class final class block** — the bug we found: later classes end on a bare `(c)` operations table with no complete class block. Present in **12 / 12** modern ones (i.e. broken everywhere).
- 🟡 §9 concurrency vocabulary + extensibility twists — present in the *later-built* ones, may be partial/absent in earlier ones.

➡️ **To match the new prompt, these need either regeneration or surgical backfill.** (Decision currently: "new only, skip backfill" — revisit if you want the whole library consistent.)

| # | Problem | Type | Key patterns / concurrency it teaches | New-prompt status |
|---|---------|------|----------------------------------------|-------------------|
| 1 | **Parking Lot** | Resource allocation | Strategy (spot-fit), State, per-spot lock | 🟡 old prompt |
| 2 | **Movie Ticket Booking** | Booking + seat-lock | State (seat machine), two-phase reserve→confirm | 🟡 old prompt |
| 3 | **Meeting Room Reservation** | Booking + interval | overlap check, per-room lock | 🟡 old prompt |
| 4 | **Ride Sharing** | Resource allocation | Strategy (ride pick), optimistic-pick/pessimistic-confirm | 🟡 old prompt |
| 5 | **Splitwise** | Money / settlement | balance graph, lock-ordering (deadlock-free) | 🟡 old prompt |
| 6 | **API Rate Limiter** | Rule / policy engine | Strategy (algorithms), sharded per-customer lock | 🟡 old prompt |
| 7 | **Coupon Management** | Rule / policy engine | Chain of Responsibility, usage-limit redemption race | 🟡 old prompt |
| 8 | **Notification Router** | Rule / policy engine | Chain of Responsibility, Adapter (channels), idempotent dedup | 🟡 old prompt |
| 9 | **Message Broker (Pub-Sub)** | Pub-sub / messaging | Observer, per-topic offsets, condition var wait/notify | 🟡 old prompt |
| 10 | **Task Scheduler** | Scheduling | priority queue + worker, condition-variable wait/notify | 🟡 old prompt |
| 11 | **Leaderboard** | Data-structure-heavy | read-write lock, sharded buckets | 🟡 old prompt |
| 12 | **Vending Machine** | State-machine device | State pattern (coin/dispense), single-machine lock | 🟡 old prompt |
| 13 | **Elevator System** | State-machine device | State + SCAN, Strategy (dispatch), per-car lock | 🟡 old prompt |
| 14 | **TTL Key-Value Store** | Data-structure-heavy | active-expiry sweeper, RLock | 🟡 old prompt |

**Legacy / older-format versions also on disk** (don't even have the §9 concurrency section): Amazon Locker, Idempotent Order Processing Engine, Food Ordering, Delivery Partner Assignment, Offline Download Manager, File System APIs (mkdir/cd), Notification System. *(Oldest format — regenerate if you want them.)*

> **Important:** ONLY problems generated from here on (Part C) will be on the new prompt (with §3.5 + the §4.1 fix). The 14 above are the *old* baseline.

---

## Part B — Coverage gaps (what's MISSING)

**Concurrency axis** — ✅ SATURATED. RLock, Barrier, CAS, per-resource locks, two-phase, optimistic/pessimistic, read-write, condition vars, idempotency, sweeper all appear across 11–13 problems.

**Design-pattern axis** — ❌ big holes. Frequency across existing sessions:

| Pattern | # problems | |
|---|---|---|
| Strategy, State, Information Expert | 12–13 | ✅ saturated |
| Template Method, Factory, Singleton, Observer | 7–11 | ✅ covered |
| Chain of Responsibility | 2 | 🟡 light |
| **Command, Composite, Decorator, Builder, Mediator, Memento, Flyweight, Proxy, Visitor** | **0** | ❌ missing |

**Problem-type axis** — missing whole categories: Money/wallet, Trie/autocomplete, Composite/tree, Command/undo, Mediator/collaboration, pure game-modeling, social feed/fan-out, e-commerce/inventory.

---

## Part C — Problems to GENERATE (🆕) — the full master set

Organized so that, combined with Part A, **all 15 types + all major patterns + all concurrency flavours + DS-heavy + pure-modeling** are covered.

### Tier 1 — Concurrency-variety + data-structure-heavy (your original 4 strong picks)

| # | Problem | What it uniquely teaches | New concurrency / DS |
|---|---------|--------------------------|----------------------|
| 1 | **Connection / Resource Pool** | Borrow/return a fixed set of reusable resources; block when exhausted | **Semaphore** + acquire-with-timeout + fair return |
| 2 | **Thread Pool / Worker Executor** | Submit tasks, N workers drain a queue, graceful shutdown | **Bounded blocking queue** + **poison-pill** shutdown + futures |
| 3 | **Order Matching Engine** (stock exchange) | Buy/sell order book, match by price-time priority, partial fills | **Heap/priority-queue** DS + per-symbol lock + partial-fill atomicity |
| 4 | **Thread-Safe LRU Cache** | get/put in O(1) with eviction; the canonical DS-heavy LLD | **HashMap + doubly-linked list** + **lock striping** |

### Tier 2 — Pattern-axis fillers (fill the 0-coverage patterns)

| # | Problem | Missing pattern it teaches | Notes |
|---|---------|----------------------------|-------|
| 5 | **Text Editor (undo / redo)** | **Command + Memento** | Each edit = a Command; undo stack; snapshot state |
| 6 | **In-Memory File System** | **Composite** | File/Directory tree, recursive size/search; (modernizes the legacy one) |
| 7 | **Pizza / Coffee Customizer** | **Decorator + Builder** | Base + toppings wrap dynamically; Builder assembles order |
| 8 | **Chat Room / Group Chat** | **Mediator** (+ Observer) | Room mediates members; no member-to-member coupling |
| 9 | **Chess / Board Game** | **pure OO domain modeling** (low concurrency) | Piece-move polymorphism, board state, legal-move validation |

### Tier 3 — Type-axis fillers (categories you have NONE of)

| # | Problem | Type it fills | Key idea |
|---|---------|---------------|----------|
| 10 | **ATM** | State-machine + transaction | Card→PIN→select→dispense state machine, rollback on failure |
| 11 | **Traffic Signal Control** | State-machine device | Timed state transitions, intersection safety invariant |
| 12 | **Digital Wallet / Payment System** | Money / settlement | Debit/credit atomicity, double-entry, idempotent transfers |
| 13 | **Search Autocomplete (Typeahead)** | Data-structure-heavy | **Trie** + top-K ranking, prefix queries |
| 14 | **LFU Cache** | Data-structure-heavy | Frequency buckets + O(1) eviction (harder cousin of LRU) |
| 15 | **Spreadsheet** | Composite / dependency graph | Cell formula DAG, recompute on change, cycle detection |
| 16 | **Drawing App / Collaborative Whiteboard** | Command / undo | Shape commands, undo/redo, layered canvas |
| 17 | **Snake & Ladder** | Pure game modeling | Board, dice Strategy, turn loop |
| 18 | **Deck of Cards & Card Game** | Pure game modeling | Card/Deck/Hand modeling, shuffle Strategy |
| 19 | **Twitter / News Feed** | Social / fan-out | Fan-out-on-write vs read, feed ranking, follow graph |
| 20 | **Shopping Cart / Inventory** | E-commerce | Cart + inventory reservation, oversell-prevention race |

### Tier 4 — Optional deepeners (already-covered axes, but classic asks)

| # | Problem | Why optional |
|---|---------|--------------|
| 21 | **Snowflake ID Generator** | Only ~1 class; concurrency micro-drill (atomic seq + clock spin-wait) |
| 22 | **Online Auction** | CAS already in 11 problems; only soft-close auto-extend is novel |
| 23 | **Distributed Lock / Lease Manager** | Fencing tokens are new, but it's more a distributed-systems concept |
| 24 | **Library Management** | Classic CRUD-heavy modeling; low novelty |
| 25 | **Bowling Score Calculator** | Rules/calculation; small scope |

---

## Recommended generation order

1. **Pilot:** #4 Thread-Safe LRU Cache — multi-class, stress-tests the new §3.5 API + §4.1 per-class-block fixes; verify it renders in the frontend.
2. **Tier 1** (1–4): concurrency + DS variety.
3. **Tier 2** (5–9): the 0-coverage patterns — highest marginal value.
4. **Tier 3** (10–20): fills every remaining type.
5. **Tier 4** (21–25): only if you want exhaustive depth.

**Minimum for "har trah ka sab cover":** Tiers 1–3 = problems **1–20**. That + your existing 14 = **34 problems, zero gaps** on any axis.

---

## Notes
- All new sessions are generated with the **updated prompt** (now includes **§3.5 API / System Interface** + the **§4.1 per-class final class block** fix).
- Output per problem: tested Python code (`workspace/<slug>/`) + full §1–§9 markdown + frontend-openable `data/conversations/<slug>_lld.json`.
- Each opens at `https://localhost:8002/?s=<uuid>:lld`.
