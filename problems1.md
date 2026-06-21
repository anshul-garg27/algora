## Part C — Problems to GENERATE (🆕) — the full master set

Organized so that, combined with Part A, **all 15 types + all major patterns + all concurrency flavours + DS-heavy + pure-modeling** are covered.

### Tier 1 — Concurrency-variety + data-structure-heavy (your original 4 strong picks)

| # | Problem | What it uniquely teaches | New concurrency / DS |
|---|---------|--------------------------|----------------------|
| 1 | **Connection / Resource Pool** | Borrow/return a fixed set of reusable resources; block when exhausted | **Semaphore** + acquire-with-timeout + fair return |
| 2 | **Thread Pool / Worker Executor** | Submit tasks, N workers drain a queue, graceful shutdown | **Bounded blocking queue** + **poison-pill** shutdown + futures |
a

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

