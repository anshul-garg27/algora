
#### Great: sorted index + price-band sub-sharding for hot symbols
**Approach:** keep the sorted index, but for hot symbols (AAPL) **split the rule set by price-band across matcher replicas** — each replica owns a contiguous threshold range and the same tick is broadcast to all replicas of that symbol; each only checks its band. This caps any single node's work and removes the hot-shard ceiling. Matchers are stateless-recoverable: index is rebuilt from the alert-change log + DB on startup.
**Challenges/Trade-offs:** broadcasting a hot symbol's tick to N replicas multiplies tick traffic for that symbol, but N is small (2–4) and only for hot symbols. This is what real systems do — partition by key, sub-shard the hot key.

🎙️ **Script:** "The trick is a sorted index of thresholds per symbol — above and below. When the price jumps from one value to another, I do a range lookup and only touch the rules in that band, so a tick is log-n plus a few crossings instead of a full scan. For a monster like Apple I split that symbol's rules across a couple of matcher replicas by price band and broadcast its ticks to them, so no single node melts. The index is just an in-memory cache of the DB, so a crashed matcher rebuilds it from the change log."

> 🧠 If they ask "why not just a DB query per tick?": "A DB round-trip per tick at 200K/sec is both too slow for sub-second and far too expensive; the rules are only 2GB so I keep them in RAM and treat the DB as durable backup."

### How do we evaluate percent-change-in-a-window rules?

#### Good: per-symbol sliding window in memory
**Approach:** keep a ring buffer / sorted-by-time deque of recent prices per symbol (up to max window, e.g. 15 min). On each tick, compute `(p_now - p_window_start) / p_window_start`; for percent rules, index them by their P% threshold and check crossings just like price thresholds, but against the computed change.
**Challenges:** memory grows with tick rate × window; need to evict expired points (slide the window). For 15-min windows at high tick rates, downsample to e.g. 1-second OHLC buckets to bound memory.

#### Great: bucketed windows + maintain running min/max
**Approach:** store 1-second aggregate buckets (open/high/low/close) per symbol; the window is a fixed-size ring of buckets. Maintain running reference price (window-start or window-min/max) so percent-change is O(1) per tick. Rebuild on restart by replaying the tick stream for the last W.
**Trade-offs:** bucketing loses sub-second granularity for percent rules — acceptable since percent-change-over-minutes doesn't need millisecond precision.

> 🧠 If they ask "what about windows spanning a restart?": "I replay the tick stream for the last W seconds on matcher startup to repopulate buckets before I resume firing — so I don't miss or falsely fire across a restart."

### How do we deliver notifications reliably without double-paging? (idempotency + delivery)

#### Bad: matcher calls the SMS/email API directly
**Approach:** matcher fires → directly calls Twilio/SES inline.
**Challenges:** blocks the hot path on a slow third party; on retry/crash you double-send. ⚠️ Trap: coupling eval latency to gateway latency.

#### Great: queue + idempotent consumer with dedup key
**Approach:** matcher emits a fired event with a deterministic **crossingKey** = `alertId + crossing-direction + armed-epoch`. Notification service consumes from the **Notify queue**, does a conditional insert into a **Dedup store with TTL**; if the key already exists, it's a duplicate and is dropped. Only on first-win does it dispatch. Webhooks/SMS retried with exponential backoff; channel failures go to a DLQ.
**Trade-offs:** at-least-once + dedup ≈ effectively-once for the user; true exactly-once across external gateways is impossible, so the dedup store is the guarantee. The crossingKey's `armed-epoch` increments on re-arm so the *next legitimate* crossing isn't suppressed.

