export const meta = {
  name: 'regen-hld-old-18',
  description: 'Regenerate 18 old HLD topics fresh with the improved prompt (URL Shortener, Ride-Sharing, Kafka, Chat, Cricket, Stock Alerts, Restaurant Metrics, View Count, Driver Heatmap, Stock Trading, Load Balancer, Error Log Monitor, Distributed Rate Limiter, Payment Gateway, CheerCoin Rewards, Live User Count, Vending Leasing Mgmt, E-Commerce): full §1-§11 markdown + computed capacity + safe mermaid, adversarially verify, then fix. Orchestrator assembles JSON afterwards.',
  phases: [ { title: 'Generate' }, { title: 'Verify' }, { title: 'Fix' } ],
}

const ROOT = '/Users/gbang/Downloads/algora'
const PY = `${ROOT}/.venv/bin/python`

const RECIPE = `
You are generating ONE complete HIGH-LEVEL system design (HLD) interview session for a senior SDE prep app.

FIRST, read these two files IN FULL — they define the exact quality bar and section structure:
- ${ROOT}/system_design_prompt.md   (the production HLD prompt — your answer MUST match its §1–§11 structure exactly, including: §1 "Scope, Requirements & Assumptions" which OPENS with a 🔒 Scope lock — 2-4 architecture-forking questions stated as vetoable assumptions FIRST, then functional requirements DERIVED from them, then PROVISIONAL non-functional targets tagged to assumptions; §2 "The Forks Behind My Assumptions" = the residual forks, NOT a fresh question round, and it must NOT re-ask anything already locked in §1; the 15 rigor invariants; the Bad→Good→Great deep dives)
- ${ROOT}/agent_prompts/hld_session_builder.md   (the build recipe; use the real paths under ${ROOT})

WHAT HLD IS (vs LLD): NO application/algorithm code, NO classes. HLD is prose + tables + mermaid architecture diagrams. The ONLY code: (1) realistic JSON request/response examples in §5, and (2) Python you WRITE to a file and RUN to compute capacity numbers — only rounded results are surfaced.

SECTION STRUCTURE (all 11, fully expanded, exact headings):
## 1. Scope, Requirements & Assumptions — 🎬 structure pitch; 🔒 SCOPE LOCK first (2-4 forking questions as vetoable assumptions + in/out-of-scope checkpoint); functional flows derived from the assumptions (each: feature one-liner + 🗣️ plain words + ⚡ why hard); "Below the line (out of scope)"; provisional NFR targets tagged to their assumption (each: target + 🗣️ plain words + 💥 what breaks). Keep the whole opener tight (~3-4 min of talk). TEXT ONLY.
## 2. The Forks Behind My Assumptions — 2-3 most consequential locked assumptions, each: the assumption restated + ↔️ what changes if wrong (If X / If Y) + 🗣️ how I'd say it. NO duplication of anything settled in §1. End 🤝 Checkpoint.
## 3. Scale & Capacity (talkable numbers) — table Metric | Derivation | Rounded | Talkable phrase | Decision it drives. COMPUTE with a capacity.py run via ${PY}. Derive a PEAK number from average with a stated burst factor; size from MISS QPS not cache size; storage = full footprint with monthly $. Name the ONE decision-forcing number + flip threshold. Plain-text math. Short 🎙️ Script.
## 4. Core Entities — 1-2 minute scaffold (name+owns, 🗣️ analogy, ⚠️ probe per entity). NOT a field-level data model.
## 5. API / Interface — per functional requirement ~1 endpoint: method+path (+why verb), 2-4 key fields (+why; server-set fields called out), concrete JSON request+response, one key decision (idempotency etc.). Note VERSIONING (/v1) + cursor PAGINATION once. Security: caller from JWT + object-level authz. 🎙️ Script.
## 6. High-Level Design (one functional requirement at a time) — one ### 6.x per above-the-line requirement: framing; ARCHITECTURE DECISIONS TABLE (Component | plain English | Why THIS | What we DIDN'T pick & why | Trade-off); 🗣️ key-terms gloss; a focused mermaid flowchart TD diagram; NUMBERED STEP NARRATION (action/why/state/what-could-go-wrong); 💬 say-while-drawing; 🎙️ Script. End with ONE "Final (high-level)" union flowchart TD + 🤝 Checkpoint.
## 7. Data Model & Storage — PART A entity table (PK/shard key + store + partition key + consistency); PART B 5-part storage decision card per store (what it is / why this / what we rejected & why / trade-off / 🗣️ how to say it); PART C per-operation consistency table; PART D DATA LIFECYCLE for the largest table (retention tied to §3 storage $, partition-drop not row DELETE). 🎙️ Script.
## 8. Deep Dives — Bad → Good → Great — 3-5 hardest problems, each "### How do we [problem]?" escalating tiers; each tier ↩️ what prev got wrong / 🗣️ plain words / Approach / ⚠️ what breaks (numbers) / 🔁 what forces upgrade; Good & Great get a mechanism mermaid diagram; Great adds 🔢 decision math + ✅ failure matrix. Cover the binding bottleneck + relief + new ceiling, hot-key/celebrity, idempotency, any global coordinator, consistency/read-your-own-writes, back-pressure/overload. 🎙️ Script + 🧠 If they ask.
## 9. Reliability, Failure Modes & Cost — 9A availability (9s + mechanisms); 9B per-dependency failure table (what breaks / how it degrades — what USER SEES / recovery); 9C RPO/RTO (define in plain words first); 9D cost (top 3 drivers + monthly order-of-magnitude + biggest optimization, ONE unit-economics number like $/1M req computed in capacity.py). Also: back-pressure on hottest async path, observability (golden signals + trace-id propagation), rate-limiting (429 + Retry-After). 🎙️ Script.
## 10. Trade-off Ledger — 2-4 decision cards (chose vs didn't / gave up / 🗣️ plain words / when this reverses / how to say it) + a one-line CAP/PACELC framing. 🎙️ Script.
## 11. Likely Interviewer Questions & Answers — all 7 domains, 12-18 Q&A; each ❓ question, mechanism (2-3 sentences glossed), 🗣️ plain words, 💬 one-liner. End with 🎙️ 60-second verbal summary.

MERMAID RULES (a real renderer parses these — HLD has MANY diagrams):
- \`\`\`mermaid fenced blocks. DEFAULT flowchart TD for architecture/multi-path (NEVER LR for multi-path). sequenceDiagram for request flows.
- KEEP NODE/EDGE LABELS FREE of breaking characters: ( ) [ ] | : / " < > ; and curly braces. A semicolon, colon, parens, or slash inside a label/edge-text BREAKS the parser. Write "step 3 read cache" not "3: read cache (hot)". Use <br/> for line breaks, never raw newlines.
- Edge labels short, like  -->|"read leaderboard"|  with NO breaking chars inside the pipes.
- Same component = same node id/label across diagrams. ~10-12 nodes max per diagram. Aim 5-9 mermaid blocks total.

MARKDOWN OUTPUT:
- Write the COMPLETE §1–§11 markdown to ${ROOT}/workspace/<UUID>_hld/_response.md . LONG (md > 20,000 chars; realistically 45-90K). Pure markdown, emoji markers as prescribed, no LaTeX.
- You MAY create the scratch dir ${ROOT}/workspace/<UUID>_hld/ for capacity.py. Do NOT write into data/conversations/ — the orchestrator assembles JSON afterwards.

Before finishing: verify capacity.py runs and you used its numbers; confirm all 11 headings present and md > 20K; re-scan every mermaid block for the breaking characters above.
`

const GEN_SCHEMA = {
  type:'object',additionalProperties:false,
  required:['uuid','title','mdChars','sectionsPresent','mermaidCount','capacityComputed','notes'],
  properties:{uuid:{type:'string'},title:{type:'string'},mdChars:{type:'number'},sectionsPresent:{type:'boolean'},mermaidCount:{type:'number'},capacityComputed:{type:'boolean'},notes:{type:'string'}},
}
const VERIFY_SCHEMA = {
  type:'object',additionalProperties:false,required:['verdict','findings'],
  properties:{verdict:{type:'string',enum:['SHIP','FIX-FIRST']},
    findings:{type:'array',items:{type:'object',additionalProperties:false,required:['severity','where','problem','fix'],
      properties:{severity:{type:'string',enum:['BLOCKER','MAJOR','MINOR']},where:{type:'string'},problem:{type:'string'},fix:{type:'string'}}}}},
}
const FIX_SCHEMA = {
  type:'object',additionalProperties:false,required:['changed','summary','mdChars','mermaidCount'],
  properties:{changed:{type:'boolean'},summary:{type:'string'},mdChars:{type:'number'},mermaidCount:{type:'number'}},
}

const PROBLEMS = [
  { uuid:'657589a4-60b0-4d99-b932-09b3f6da738f', title:'Design a URL Shortener (TinyURL / Bitly)',
    brief:'Shorten a long URL to a short code, redirect short to long, custom aliases, analytics on clicks. Read-heavy.',
    focus:'short-code generation (counter+base62 vs hash vs KGS) and why no collisions, the read-heavy redirect path + cache, 301 vs 302, the global coordinator if using a counter, click analytics async pipeline.' },
  { uuid:'969a289a-8e87-431a-b5bd-fbefd2aedb60', title:'Design a Ride-Sharing Service (Uber/Lyft)',
    brief:'Riders request a ride from A to B, system matches a nearby driver, both track the trip live, fare + payment.',
    focus:'driver-rider matching with geo-index (S2/geohash), the location-update write firehose from moving drivers, matching as a per-cell operation + hot dense cities, trip state machine, surge as a deep dive.' },
  { uuid:'277e8002-6f1a-4913-82f3-55f037d7131a', title:'Design a Distributed Messaging System (Kafka/RabbitMQ)',
    brief:'A durable pub/sub log: producers publish to topics, consumers read via offsets, partitioned + replicated, ordering within a partition, at-least-once delivery.',
    focus:'partitioning + ordering guarantee per partition, replication (ISR/leader-follower) + durability, consumer-group offset management + rebalancing, exactly-once vs at-least-once, back-pressure on slow consumers.' },
  { uuid:'2c1c09b2-95a1-465b-a31b-39030cf73fcf', title:'Design a Chat Application (WhatsApp/Messenger)',
    brief:'1:1 and group messaging, online presence, delivery + read receipts, message history, push when offline.',
    focus:'the persistent-connection fan-out (websocket gateway + which server holds a user), message delivery + ordering + receipts, group fan-out, offline push, the celebrity/large-group fan-out problem.' },
  { uuid:'247d9838-f1c5-40e2-ab97-b955f915676d', title:'Design a Live Cricket Score & Analytics Platform (Cricbuzz)',
    brief:'Real-time score + commentary + stats to millions of concurrent viewers; write rate is low (a few events/over) but read fan-out is massive.',
    focus:'the extreme read fan-out of a single hot match (CDN + edge + fan-out tree / pub-sub), push vs poll to clients, the tiny-write-huge-read asymmetry, hot-match as the binding bottleneck.' },
  { uuid:'4db3531e-3c7a-4d65-b4d5-eb027e21370a', title:'Design a Stock Price Alerting / Notification System',
    brief:'Users set price-threshold alerts on symbols; when a tick crosses the threshold, notify them fast. Millions of alerts, high-frequency price stream.',
    focus:'matching a high-frequency price stream against millions of alert rules efficiently (per-symbol alert index / interval tree), the notification fan-out, at-least-once + dedup of alerts, the price-stream as a firehose.' },
  { uuid:'6cc56ef5-159e-4e63-b69c-f35c896eb28f', title:'Design Real-Time Restaurant Order Metrics (Food Delivery)',
    brief:'Live operational dashboard: orders/min, prep times, late orders per restaurant/region, updated in near-real-time for ops teams.',
    focus:'the streaming aggregation pipeline (events → stream processor → pre-aggregated rollups), windowed aggregation, exactly-once metric counting, time-series store, late/out-of-order events.' },
  { uuid:'fce07ace-a90c-4b6a-b1cf-e83b178ee8ca', title:'Design a View Count Service (YouTube/Netflix)',
    brief:'Count views per video at massive scale, near-real-time display, resistant to inflation/double-count; billions of views/day.',
    focus:'the write-heavy increment firehose, approximate vs exact counting, dedup/anti-inflation, sharded counters + the single-hot-video counter as the binding bottleneck, eventual display consistency.' },
  { uuid:'143dbb94-126b-429e-a1d7-c615d7708804', title:'Design a Real-Time Driver Heatmap System',
    brief:'Aggregate live driver/demand density into a geo heatmap for a maps UI, updated every few seconds across a city.',
    focus:'geo-bucketing (S2 cells) + windowed aggregation of the location firehose, the read path (precomputed tiles), update frequency vs cost, hot dense cells.' },
  { uuid:'e0b7b7da-d5e7-41cb-a9fb-54724ba4c822', title:'Design a Stock Trading Platform (Zerodha)',
    brief:'Place/cancel buy/sell orders, a matching engine, portfolio + holdings, market-data feed, money movement. Correctness-critical.',
    focus:'the order matching engine (per-symbol, price-time) + its single-writer correctness, money/holdings consistency (strong), the market-data fan-out, idempotent order placement, settlement.' },
  { uuid:'ec6fef8d-7160-482a-8357-612b13ca5360', title:'Design a Load Balancer (10M requests/day)',
    brief:'Distribute incoming traffic across a fleet of backends, health-check + remove dead ones, L4 vs L7, sticky sessions, no SPOF.',
    focus:'L4 vs L7 balancing + algorithm (round-robin/least-conn/consistent-hash), health checking + ejection, the LB itself as a SPOF (active-passive + VIP/anycast), connection draining, back-pressure.' },
  { uuid:'4a62b31b-dc67-4dfc-a120-8a9e6d99bfb5', title:'Design a Real-Time Error Log Monitoring System',
    brief:'Ingest logs/errors from thousands of services, index for search, alert on error spikes, dashboards. High write volume.',
    focus:'the log ingestion firehose (agent → buffer/Kafka → indexer), search index (inverted index) at scale, alerting on aggregated error rates, retention/data-lifecycle of the huge log store, sampling under overload.' },
  { uuid:'7c1e38e4-5b67-41cf-b0ba-3d95865f88f3', title:'Design a Distributed Rate Limiter',
    brief:'Limit requests per client/API key across a fleet of servers (not in-memory single-node); accurate, low-latency, fail-open vs fail-closed.',
    focus:'the algorithm (token bucket / sliding window) + WHERE limiter state lives (shared Redis) + that the counter is a global coordinator, per-key sharding, the accuracy-vs-latency trade-off of centralized vs local counters, fail-open vs fail-closed.' },
  { uuid:'16fa303a-7778-40f6-a958-1836716398c0', title:'Design a Payment Gateway System',
    brief:'Process payments: authorize, capture, refund via external processors; idempotent; consistent ledger; PCI scope; webhooks.',
    focus:'idempotency of charges (the retried-payment race), the double-entry ledger + money conservation, external-processor failure handling + reconciliation, PCI scope (tokenization, never store raw cards), async webhooks + at-least-once.' },
  { uuid:'c8fa395a-5782-4ba0-9a57-3a5580c0cf40', title:'Design a Distributed Reward / Points System (CheerCoin)',
    brief:'Users earn and spend reward points/coins; balances must be correct under concurrency; transfer between users; audit trail.',
    focus:'balance correctness (no double-spend) via idempotent ledger entries, the earn/spend transaction, transfer with deadlock-free ordering, audit log, idempotency on award events.' },
  { uuid:'03146622-c043-4708-8846-04a4be7e0574', title:'Design a Live User Count System for a Streaming Platform',
    brief:'Show the live concurrent-viewer count for a stream, near-real-time, accurate-enough, for streams from hundreds to millions of viewers.',
    focus:'approximate distinct-counting at scale (HyperLogLog) vs exact, the heartbeat/join-leave firehose, sharded counters + aggregation tree, the single-hot-stream counter, eventual display consistency.' },
  { uuid:'57ba57b0-0d38-4169-ba5f-4750015ea3c4', title:'Design a Vending Machine Leasing Management System (HLD)',
    brief:'Fleet-scale platform managing leased vending machines: telemetry (stock, cash, faults) from thousands of machines, lease billing, restock dispatch, dashboards.',
    focus:'the telemetry ingestion from thousands of IoT machines, time-series storage of machine state, lease billing pipeline, restock/alerting on low stock or faults, offline-machine handling.' },
  { uuid:'3337c073-c8e8-49f2-965c-6946df2d6765', title:'Design an E-Commerce Portal Like Amazon',
    brief:'Browse/search products, cart, checkout with inventory reservation, orders, payments. Read-heavy browse, correctness-critical checkout.',
    focus:'product search (Elasticsearch) for the read-heavy browse path, cart + inventory reservation to prevent oversell at checkout, the order pipeline, the search-index vs catalog-DB consistency, hot-product/flash-sale spike.' },
]

phase('Generate')

const results = await pipeline(
  PROBLEMS,
  (p) => agent(
    `${RECIPE}

=== YOUR ASSIGNED HLD PROBLEM ===
UUID: ${p.uuid}
TITLE: ${p.title}
PROBLEM BRIEF (frame §1 around it; this becomes transcript[0]): ${p.brief}

WHAT TO EMPHASIZE (capacity numbers, the binding bottleneck, and the deep dives should center on these):
${p.focus}

Assume a senior-SDE (L5/SDE-3) bar: cost & operations first-class. Build the complete §1–§11 HLD now in ${ROOT}/workspace/${p.uuid}_hld/_response.md . Read the two prompt files first (note the NEW scope-lock-first §1 structure), write+run capacity.py, then write the full markdown. Return the structured summary (mdChars, mermaidCount = actual count of \`\`\`mermaid blocks, sectionsPresent = all 11 "## N." headings present).`,
    { label: `gen:${p.title.slice(7,26)}`, phase: 'Generate', schema: GEN_SCHEMA, agentType: 'general-purpose' }
  ),
  (gen, p) => agent(
    `Adversarially review a generated HLD session. Be a skeptic — find REAL defects, review-only, DO NOT modify files.

Workspace: ${ROOT}/workspace/${p.uuid}_hld/_response.md (+ maybe capacity.py). Problem: ${p.title}. Emphasis: ${p.focus}

Report PASS/FAIL with evidence on each:
1. ALL 11 sections present and fully expanded; md > 20,000 chars. §1 must OPEN with the 🔒 scope-lock (forking assumptions FIRST), then derived functional requirements, then provisional NFRs. §2 must be the residual forks and must NOT re-ask anything §1 already locked (flag any duplication).
2. CAPACITY (§3): numbers actually derived + self-consistent (re-run capacity.py with ${PY} if present); a named decision-forcing number + flip threshold; a peak-from-average burst factor; no false precision.
3. TECHNICAL CORRECTNESS for THIS problem + the emphasis: are the deep dives the genuinely hardest parts (binding bottleneck, hot-key, global coordinator, consistency/read-your-own-writes, back-pressure)? Find any wrong or hand-wavy claim.
4. MERMAID SAFETY (CRITICAL — many diagrams): scan EVERY \`\`\`mermaid block; FAIL any label/edge-text containing breaking chars — parentheses, a colon, a semicolon, slashes, quotes, angle brackets, curly braces. Report the exact offending line. Confirm flowchart TD for multi-path.
5. §5 has real REST endpoints + JSON + idempotency + object-level authz + versioning/pagination noted. §7 has 5-part storage cards + PART D data lifecycle. §9 covers back-pressure, observability, rate-limiting. §10 has CAP/PACELC line.
6. Markdown hygiene: no LaTeX, no stray tags, tables well-formed, emoji-script structure present.

Return verdict SHIP or FIX-FIRST + findings (severity/where/problem/fix). Mermaid breaking-char issues are BLOCKER. Only BLOCKER/MAJOR block.`,
    { label: `vfy:${p.title.slice(7,24)}`, phase: 'Verify', schema: VERIFY_SCHEMA, agentType: 'general-purpose' }
  ),
  (verify, p) => {
    const actionable = (verify?.findings || []).filter(f => f.severity === 'BLOCKER' || f.severity === 'MAJOR')
    if (!actionable.length) return { changed:false, summary:`No BLOCKER/MAJOR (verdict ${verify?.verdict}).`, mdChars:0, mermaidCount:0 }
    return agent(
      `Fix REAL defects in a generated HLD session. Workspace: ${ROOT}/workspace/${p.uuid}_hld/_response.md (+ maybe capacity.py).

Fix EACH directly in _response.md (and capacity.py if math is wrong, re-running with ${PY}):
${actionable.map((f,i)=>`${i+1}. [${f.severity}] ${f.where}: ${f.problem}\n   FIX: ${f.fix}`).join('\n')}

CRITICAL for any mermaid finding: rewrite offending node/edge labels to remove ALL breaking characters (parens, colons, semicolons, slashes, quotes, angle/curly braces) — replace ":" and ";" with words, drop parens, use <br/> for line breaks; keep flowchart TD. Keep all 11 sections, md > 20,000 chars, no LaTeX, scope-lock-first §1. Re-scan mermaid after fixing. Return what changed, final mdChars, final mermaidCount.`,
      { label: `fix:${p.title.slice(7,24)}`, phase: 'Fix', schema: FIX_SCHEMA, agentType: 'general-purpose' }
    )
  },
)

return PROBLEMS.map((p,i)=>({uuid:p.uuid,title:p.title,done:!!results[i]}))
