# LLD + HLD Generation Plan

> **Policy (your call):** Old sessions (older than 2 days, i.e. before **2026-06-19**) were built with weaker models — we **regenerate** them fresh with the new prompt on **Opus 4.8 max**. Only sessions from the last 2 days (this session + Cursor) count as "good / keep". "Already exists" is NOT a skip reason — old = regenerate.
>
> Date today: 2026-06-21. Status legend: ✅ done-fresh (keep) · 🔄 in-flight (generating now) · 🆕 to generate · ♻️ regenerate (old, weak-model)

---

## PART 1 — LLD

### A. Already DONE fresh / in-flight (this session + Cursor) — do NOT redo
| Problem | Source |
|---|---|
| Connection / Resource Pool | ✅ this session (verified) |
| Splitwise · API Rate Limiter · Coupon · Notification Router | ✅ this session batch (verified) |
| Message Broker (Pub-Sub) · Task Scheduler · Leaderboard · Vending Machine · Elevator · TTL KV Store | 🔄 batch-2 (in-flight) |
| Order Matching Engine · ATM · Traffic Signal · Digital Wallet · Search Autocomplete · LFU Cache | 🔄 batch-3 (in-flight) |
| Thread Pool / Worker Executor | ✅ Cursor |
| LRU Cache · Text Editor (undo/redo) · In-Memory File System · Pizza/Coffee Customizer · Chat Room · Chess/Board | 🔄 Cursor (in-flight) |
| Parking Lot · Movie Ticket · Meeting Room · Ride Sharing | ✅ Cursor (fresh, verified) |

> ⚠️ **DUPLICATE to resolve:** Order Matching Engine is running in BOTH my batch-3 AND Cursor. Keep one, drop the other at assembly.

### B. OLD LLD to REGENERATE (weak-model, older than 2 days) — still pending
| # | Topic | New concurrency / DS angle to give it |
|---|---|---|
| L1 | **Food Ordering System** | order lifecycle State machine + restaurant inventory reservation + per-order lock |
| L2 | **Vending Machine Leasing System** | lease lifecycle State + per-machine lock (distinct from plain Vending Machine) |
| L3 | **Idempotent Order Processing Engine** | idempotency-key dedup + exactly-once processing + per-key lock |
| L4 | **Ride Sharing** (if Cursor's isn't kept) | optimistic-pick / pessimistic-confirm — only if the fresh Cursor one is dropped |

### C. NEW LLD gaps (never generated, genuinely missing)
| # | Problem | Why — what it uniquely teaches |
|---|---|---|
| L5 | **Insert/Delete/GetRandom in O(1)** | array + hashmap swap-to-tail; pure DS, top Uber ask |
| L6 | **Snakes and Ladders** | board + dice Strategy; pure game modeling (distinct from Chess) |
| L7 | **Logger Library** | Chain of Responsibility + appenders + log levels; classic staple |
| L8 | **Calendar Application (Google Calendar)** | events + recurrence rules + conflict detection |
| L9 | **Inventory Management System** | stock + reservation + oversell-prevention race |
| L10 | **Customer Issue / Ticket System (Jira-style)** | assignment + priority queue + ticket State machine |
| L11 | **Auction System** | bidding + soft-close auto-extend + optimistic CAS on highest bid |
| L12 | **In-Memory Relational Database (simplified)** | tables + indexes + simple query; strong senior signal |
| L13 | **Cart Management System** | cart + inventory hold + checkout (e-commerce; ≈ pairs with Inventory) |
| L14 | **Task Dependency Resolution / DAG Scheduler** | topological sort + cycle detection (distinct from time-Scheduler) |
| L15 | **Concurrent Log Processor** | producer-consumer pipeline + ordered flush |

### LLD priority order
**First:** L5, L6, L7, L8, L9 (cleanest gaps, highest interview value)
**Then:** L10, L11, L12 (rich senior-signal)
**Then:** L1–L4 regenerate (old topics) + L13–L15 (overlap-y)

---

## PART 2 — HLD

> 40 HLD on disk, but **24 are old (weak-model) → regenerate**. Only 20 are fresh.

### A. OLD HLD to REGENERATE (older than 2 days) — distinct topics (dedup'd)
| # | Topic | Notes |
|---|---|---|
| H1 | **URL Shortener (TinyURL/Bitly)** | the canonical HLD; many old dupes — make ONE clean version |
| H2 | **Ride-Sharing Backend (Uber/Lyft)** | many old dupes/fragments — one clean version |
| H3 | **Distributed Messaging System (Kafka/RabbitMQ)** | |
| H4 | **Chat Application (WhatsApp/Messenger)** | |
| H5 | **Live Cricket Score & Analytics (Cricbuzz)** | |
| H6 | **Stock Price Alerting / Notification System** | |
| H7 | **Real-Time Restaurant Order Metrics** | |
| H8 | **View Count Service (YouTube/Netflix)** | |
| H9 | **Real-Time Driver Heatmap** | |
| H10 | **Stock Trading Platform (Zerodha)** | |
| H11 | **Load Balancer (10M req)** | |
| H12 | **Real-Time Error Log Monitoring** | |
| H13 | **Distributed Rate Limiter** | distinct from the in-memory LLD rate limiter |
| H14 | **Payment Gateway System** | |
| H15 | **CheerCoin Distributed Reward System** | |
| H16 | **Live User Count (Streaming Platform)** | |
| H17 | **Vending Machine Leasing Management (HLD)** | |
| H18 | **E-Commerce Portal Like Amazon** | |

### HLD priority order
**First (highest value classics):** H19 Instagram, H20 Distributed Cache, H22 Dropbox, H21 Web Crawler, H24 Flash Sale
**Then regenerate the heavy hitters:** H1 URL Shortener, H2 Ride-Sharing, H3 Kafka, H4 Chat, H14 Payment Gateway, H18 E-Commerce
**Then the rest of the old list:** H5–H13, H15–H17, H23, H25

---

## Notes / open decisions
- **HLD needs a different pipeline** than LLD: it uses `system_design_prompt.md` + `agent_prompts/hld_session_builder.md` — no §1–§9 code; instead requirements → capacity estimation → API → data model → high-level architecture → scaling/bottlenecks → trade-offs. A separate generate→verify→fix workflow must be authored before generating HLD.
- Old sessions, once a fresh replacement is verified, get **deleted** (so history shows one clean version per topic), and the new one is timestamped to the top.
- Everything new is generated on **Opus 4.8 max** with the updated LLD prompt (§3.5 API section + §4.1 per-class-block fix) / the HLD prompt.
