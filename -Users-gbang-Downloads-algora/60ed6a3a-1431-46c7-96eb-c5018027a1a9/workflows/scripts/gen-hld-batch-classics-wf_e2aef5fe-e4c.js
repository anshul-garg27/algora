export const meta = {
  name: 'gen-hld-batch-classics',
  description: 'Generate 7 new HLD sessions (Instagram, Distributed Cache, Web Crawler, Dropbox, Distributed Job Scheduler, Flash Sale, Tinder/Yelp geo): produce full §1–§11 HLD markdown with computed capacity numbers and mermaid diagrams, adversarially verify, then fix. Orchestrator assembles JSON afterwards.',
  phases: [
    { title: 'Generate' },
    { title: 'Verify' },
    { title: 'Fix' },
  ],
}

const ROOT = '/Users/gbang/Downloads/algora'
const PY = `${ROOT}/.venv/bin/python`

const RECIPE = `
You are generating ONE complete HIGH-LEVEL system design (HLD) interview session for an Uber/Amazon-style senior SDE prep app.

FIRST, read these two files IN FULL — they define the exact quality bar and section structure:
- ${ROOT}/system_design_prompt.md   (the production HLD system prompt — your answer MUST match its §1–§11 structure exactly, with all the prescribed sub-structure, emoji markers (🎬 🎙️ 💬 🗣️ 🧠 🤝 🆘 ⚠️ 🔀 ❓), and the Bad→Good→Great deep dives)
- ${ROOT}/agent_prompts/hld_session_builder.md   (the build recipe; IGNORE its old /Users/anshullkgarg/... paths — the real root is ${ROOT})

WHAT HLD IS (vs LLD): NO application/algorithm code, NO classes, NO §1–§9-LLD structure. HLD is prose + tables + mermaid architecture diagrams. The ONLY code that ever appears: (1) realistic JSON request/response examples in the API section, and (2) Python you WRITE to a file and RUN to compute capacity numbers exactly — only the rounded results are surfaced in the markdown, never unrun code.

REQUIRED SECTION STRUCTURE (all 11, fully expanded, in this order — match the headings):
## 1. Requirements (Functional + Non-Functional) — 🎬 structure pitch opener; 3-5 functional flows "above the line" each with feature one-liner + 🗣️ plain words + ⚡ why it's hard; "Below the line (out of scope)" list; NFRs each with a talkable target (p99 ms, 9s) + 🗣️ plain words + 💥 what breaks without it; close with 🎙️ Script. TEXT ONLY.
## 2. Clarifying Questions & Assumptions — each: spoken question, 🗣️ why I'm asking, ↔️ design fork (If YES.../If NO...), Assumption I'll proceed with; end with 🤝 Checkpoint.
## 3. Scale & Capacity (talkable numbers) — a table: Metric | Derivation (step-by-step math) | Rounded | Talkable phrase | Decision it drives. COMPUTE the arithmetic by writing a capacity.py and running it with ${PY} capacity.py — paste the rounded results. Name the ONE decision-forcing number + its flip threshold. Plain-text math only (~, x, ÷, no LaTeX). End with a short 🎙️ Script.
## 4. Core Entities — per entity: name + what it owns, 🗣️ simple analogy, ⚠️ interviewer probe + one-line answer; 🎙️ Script.
## 5. API / Interface — per functional requirement ~1 endpoint: method+path (+ why this verb), 2-4 key request fields (+ why; call out server-set fields), a concrete JSON request+response example, one key design decision (idempotency key etc.); security note (caller from JWT, never trust client ids/prices). 🎙️ Script.
## 6. High-Level Design (one functional requirement at a time) — one ### 6.x per above-the-line requirement: one-sentence framing; ARCHITECTURE DECISIONS TABLE (Component | plain English | Why THIS | What we DIDN'T pick & why | Trade-off accepted); 🗣️ key-terms gloss block; a focused mermaid flowchart TD diagram; NUMBERED STEP NARRATION (action / why this component / state change / what could go wrong); 💬 say-while-drawing line; 🎙️ Script. End with ONE "Final (high-level)" mermaid flowchart TD that is the reconciled union of all slices + 🎙️ Script + 🤝 Checkpoint.
## 7. Data Model & Storage — PART A entity table (Entity | key fields with PK/shard key | chosen store | partition key | consistency); PART B a storage decision card per distinct store (what it is / why this — the access pattern that forces it / considered & rejected / trade-off / 🗣️ how to say it); PART C per-operation consistency table. 🎙️ Script.
## 8. Deep Dives — Bad → Good → Great — 3-5 hardest problems, each "### How do we [problem]?" escalating Bad/Good/Great; each tier: ↩️ what previous got wrong / 🗣️ plain words / Approach (mechanism) / ⚠️ what breaks (with concrete numbers) / 🔁 what forces the upgrade; Good & Great get a tier-specific mechanism mermaid diagram; Great adds 🔢 decision-forcing math + ✅ failure matrix. Each ends with 🎙️ Script + 🧠 "If they ask". Cover the binding bottleneck + relief + new ceiling, hot-key/celebrity, idempotency, any global coordinator, consistency/read-your-own-writes, failure behavior.
## 9. Reliability, Failure Modes & Cost — 9A availability (9s per path + human downtime + mechanisms); 9B per-dependency failure table (Component | what breaks | how it degrades gracefully — what USER SEES | recovery); 9C RPO/RTO (define both in plain words first, then table per data class); 9D cost (top 3 drivers + why + rough monthly order-of-magnitude + the one biggest optimization). 🎙️ Script.
## 10. Trade-off Ledger — 2-4 decision cards "🔀 Decision: [chose] vs [didn't]": what we chose & why / what we gave up / 🗣️ plain words / when this reverses (exact flip condition) / 🗣️ how to say it. 🎙️ Script.
## 11. Likely Interviewer Questions & Answers — all 7 domains (core algorithm/hardest part, failure, scale/hot-spot, consistency, security, cost, extensibility), 2-3 each, 12-18 total; each: ❓ question verbatim, the mechanism (2-3 sentences, terms glossed), 🗣️ in plain words, 💬 one-liner to say. End with a 🎙️ 60-second verbal summary.

MERMAID RULES (a real renderer parses these — get them right; HLD has MANY diagrams so this matters a lot):
- Use \`\`\`mermaid fenced blocks. DEFAULT to "flowchart TD" for architecture/multi-path (NEVER flowchart LR for multi-path — it stretches off screen; LR only for a trivial 3-4 node linear chain). Use sequenceDiagram for request flows.
- KEEP NODE/EDGE LABELS FREE of these breaking characters: ( ) [ ] | : / " < > ; and curly braces { }. A semicolon ';' or colon ':' or parens inside a label/message BREAKS the parser. Write "step 3 read cache" not "3: read cache (hot)". Use <br/> for line breaks inside a node, never a raw newline.
- Edge labels: short, like  -->|"read leaderboard"|  (text inside the pipes must itself avoid the breaking chars above — no ':' or ';' or parens inside it).
- Same component = same node id/label across every diagram. Cap ~10-12 nodes per diagram.
- Each §6.x slice gets its own diagram; §6 ends with one "Final (high-level)" union diagram; deep-dive Good/Great tiers get mechanism diagrams. Aim for 5-9 mermaid blocks total.

MARKDOWN OUTPUT:
- Write the COMPLETE §1–§11 markdown to ${ROOT}/workspace/<UUID>_hld/_response.md . It must be LONG and comprehensive (the md must be > 20,000 chars; realistically 40-55K). Pure markdown — tables with real line breaks, fenced code only for the JSON API examples and mermaid. No LaTeX. Emoji markers as prescribed.
- You MAY create a scratch workspace dir ${ROOT}/workspace/<UUID>_hld/ to write capacity.py and run it with ${PY}. Do NOT write into ${ROOT}/data/conversations/ — the orchestrator assembles the JSON afterwards.

Before finishing: (1) verify capacity.py actually runs and you used its real computed numbers; (2) self-check that all 11 section headings are present and the md is > 20K chars; (3) count your \`\`\`mermaid blocks and make sure each one's labels are free of the breaking characters listed above.
`

const GEN_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['uuid','title','mdChars','sectionsPresent','mermaidCount','capacityComputed','notes'],
  properties: {
    uuid: { type: 'string' }, title: { type: 'string' },
    mdChars: { type: 'number', description: 'character length of _response.md' },
    sectionsPresent: { type: 'boolean', description: 'all 11 "## N." headings present' },
    mermaidCount: { type: 'number' },
    capacityComputed: { type: 'boolean', description: 'capacity numbers computed by running python, not hand-waved' },
    notes: { type: 'string' },
  },
}
const VERIFY_SCHEMA = {
  type: 'object', additionalProperties: false, required: ['verdict','findings'],
  properties: { verdict:{type:'string',enum:['SHIP','FIX-FIRST']},
    findings:{type:'array',items:{type:'object',additionalProperties:false,
      required:['severity','where','problem','fix'],
      properties:{severity:{type:'string',enum:['BLOCKER','MAJOR','MINOR']},where:{type:'string'},problem:{type:'string'},fix:{type:'string'}}}} },
}
const FIX_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['changed','summary','mdChars','mermaidCount'],
  properties: { changed:{type:'boolean'}, summary:{type:'string'}, mdChars:{type:'number'}, mermaidCount:{type:'number'} },
}

const PROBLEMS = [
  { uuid:'e20d25e8-c990-40f3-9f7c-87018d8fc5bd', title:'Design Instagram',
    brief:'A photo/video sharing social network: upload media, follow users, a home feed of followees\' posts, likes/comments. Focus on the feed (fan-out-on-write vs fan-out-on-read), media storage + CDN, and the celebrity/hot-key problem.',
    focus:'feed fan-out (write vs read hybrid), blob storage + CDN for media, the celebrity fan-out problem (millions of followers), read-heavy ratio. Deep dives: feed generation at scale, hot-key celebrity, media upload pipeline + CDN, consistency of likes/counts.' },
  { uuid:'084c563c-9047-4d34-a2b8-18502316af3c', title:'Design a Distributed Cache (Redis-style)',
    brief:'A distributed in-memory key-value cache: get/put/expire, sharded across many nodes, replication for availability, eviction (LRU/LFU). Focus on partitioning (consistent hashing), replication + consistency, hot keys, and failure/failover.',
    focus:'consistent hashing for partitioning + rebalancing on node add/remove, replication (primary-replica) + consistency model, eviction policies, hot-key mitigation (replicate hot shard / client-side cache), cache stampede/thundering herd. Deep dives: consistent hashing + rebalancing, hot key, replication & failover, cache stampede.' },
  { uuid:'94edbaa4-9115-492e-bd64-45c7dc88343d', title:'Design a Web Crawler',
    brief:'A scalable web crawler/scraper: fetch billions of pages, extract links, respect robots.txt + politeness, dedup URLs and content, store crawled data. Focus on the URL frontier, dedup at scale, politeness, and freshness.',
    focus:'URL frontier (priority + politeness per-domain queues), URL dedup (bloom filter) + content dedup (simhash/checksum), distributed fetchers, robots.txt + rate limiting per domain, freshness/recrawl scheduling, trap avoidance. Deep dives: frontier design + politeness, dedup at billions scale, distributed coordination, freshness.' },
  { uuid:'2737ae68-6526-408d-96a0-0e4581758130', title:'Design a Cloud Storage Service Like Dropbox',
    brief:'A file sync + storage service: upload/download files, sync across a user\'s devices, share files, version history. Focus on file chunking + dedup, sync (detecting + propagating changes), metadata vs blob split, and conflict resolution.',
    focus:'file chunking + content-addressed dedup (only changed chunks uploaded), metadata DB vs blob/object store split, sync via change notification (long-poll/websocket) + a per-user change journal/cursor, conflict resolution across devices, large-file resumable upload. Deep dives: chunking + dedup, sync engine + change propagation, conflict resolution, metadata scaling.' },
  { uuid:'692baf11-4116-4073-b333-d8a8411e97b8', title:'Design a Distributed Job Scheduler',
    brief:'A distributed scheduler that runs jobs at a scheduled time or on a cron/recurring schedule, across a fleet of workers, at scale, exactly-once where possible. Focus on durable scheduling, the due-job dispatch at scale, worker coordination, and at-least-once vs exactly-once.',
    focus:'durable job store + time-bucketed/sharded due-index so finding due jobs is cheap at scale, a leader/coordinator that leases jobs to workers (avoid double-run), at-least-once delivery + idempotent execution = effectively exactly-once, retries/backoff/dead-letter, recurring (cron) materialization. Deep dives: finding due jobs at scale, exactly-once / avoiding double-run (the global coordinator), worker failure + lease expiry, thundering herd at the top of the minute.' },
  { uuid:'84929a55-c466-4e23-af3a-581f842f3fdd', title:'Design a Flash Sale System',
    brief:'A flash-sale / limited-inventory system: sell exactly K items with NO overselling under a massive concurrent spike (e.g. 1M users for 1K items). Focus on the inventory decrement race at scale, queueing/admission control, and fairness.',
    focus:'preventing oversell under extreme concurrency (atomic decrement in Redis / reservation tokens), admission control + queue (virtual waiting room), the single-hot-key inventory counter as the binding bottleneck + how to shard/relieve it, idempotent checkout, payment + reservation timeout/release. Deep dives: oversell prevention (the hot inventory counter — the global coordinator), admission control / waiting room, reservation + timeout release, fairness vs throughput.' },
  { uuid:'75db5204-414d-4c67-a406-d744f3acb6d4', title:'Design Nearby Places / Proximity Service (Yelp/Tinder-style)',
    brief:'A proximity/geo service: given a user location, return nearby places (or people) within a radius, ranked. Focus on geo-indexing (geohash/quadtree/S2), the read path at scale, and updating moving entities.',
    focus:'geo-indexing options (geohash vs quadtree vs S2 cell) and why, radius/k-nearest query on the index, sharding by geo-cell + hot dense cells (cities) as the hot-key problem, caching popular queries, updating location for moving entities (Tinder/driver case). Deep dives: geo-index choice + query, hot dense cell (city) problem, moving-entity location updates, ranking + read scaling.' },
]

phase('Generate')

const results = await pipeline(
  PROBLEMS,

  (p) => agent(
    `${RECIPE}

=== YOUR ASSIGNED HLD PROBLEM ===
UUID: ${p.uuid}
TITLE: ${p.title}
PROBLEM BRIEF (this is what transcript[0] will say; frame §1 around it): ${p.brief}

WHAT TO EMPHASIZE (capacity numbers, the binding bottleneck, and the deep dives should center on these — this is what makes the session strong):
${p.focus}

Assume an Amazon/Uber senior-SDE (SDE-3 / L5) bar: cost & operations are first-class, work backwards from the customer, decide and move. Build the complete §1–§11 HLD now in ${ROOT}/workspace/${p.uuid}_hld/_response.md . Read the two prompt files first, write+run capacity.py for the numbers, then write the full markdown. Return the structured summary (mdChars = actual char count, mermaidCount = actual count of \`\`\`mermaid blocks, sectionsPresent = all 11 "## N." headings present).`,
    { label: `gen:${p.title.slice(0,18)}`, phase: 'Generate', schema: GEN_SCHEMA, agentType: 'general-purpose' }
  ),

  (gen, p) => agent(
    `Adversarially review a generated HIGH-LEVEL DESIGN (HLD) interview session. Be a skeptic — find REAL defects, do not rubber-stamp. Review-only: DO NOT modify files.

Workspace: ${ROOT}/workspace/${p.uuid}_hld/_response.md  (+ maybe capacity.py)
Problem: ${p.title}. Emphasis was: ${p.focus}

Report PASS/FAIL with evidence (section / line) on each:
1. ALL 11 sections present and FULLY EXPANDED (not stubs): §1 Requirements, §2 Clarifying Qs, §3 Scale & Capacity, §4 Entities, §5 API, §6 High-Level Design, §7 Data Model & Storage, §8 Deep Dives Bad→Good→Great, §9 Reliability/Failure/Cost, §10 Trade-off Ledger, §11 Interviewer Q&A. md length > 20,000 chars.
2. CAPACITY MATH (§3): are the numbers actually derived (visible derivation chains) and self-consistent (the arithmetic checks out)? Is there a named decision-forcing number + flip threshold? Any false precision or hand-waving? Re-run capacity.py with ${PY} if present and confirm numbers match.
3. TECHNICAL CORRECTNESS: is the architecture sound for THIS problem and the emphasized focus? Are the deep dives actually the hardest problems (the binding bottleneck, hot-key/celebrity, the global coordinator, consistency/read-your-own-writes, idempotency on mutating endpoints)? Find any claim that is wrong or hand-wavy (e.g. "just add a cache" without the miss-QPS reasoning, oversell not actually prevented, consistency hand-waved).
4. MERMAID SAFETY (CRITICAL — HLD has many diagrams): scan EVERY \`\`\`mermaid block. FAIL any that contains a label/edge-text with breaking characters: parentheses ( ), square brackets used wrongly, a colon ':' inside an edge/label, a semicolon ';' inside a label, slashes, quotes, angle brackets, or curly braces in node/edge text. These break the renderer. Report the exact offending line per diagram. Also confirm diagrams are flowchart TD (not LR) for multi-path architecture.
5. API (§5): real REST endpoints with JSON examples, idempotency on mutating endpoints, security (caller identity from token)?
6. Data model (§7): stores chosen with the access-pattern justification, partition/shard keys, per-operation consistency?
7. Markdown hygiene: no LaTeX, no stray tool/XML tags, tables well-formed, the prescribed emoji-script structure present.

Return verdict SHIP or FIX-FIRST and a findings list (severity/where/problem/fix). Mermaid breaking-char issues are BLOCKER (they break rendering). Only BLOCKER/MAJOR block; list MINORs too.`,
    { label: `verify:${p.title.slice(0,16)}`, phase: 'Verify', schema: VERIFY_SCHEMA, agentType: 'general-purpose' }
  ),

  (verify, p) => {
    const actionable = (verify?.findings || []).filter(f => f.severity === 'BLOCKER' || f.severity === 'MAJOR')
    if (!actionable.length) {
      return { changed: false, summary: `No BLOCKER/MAJOR findings (verdict ${verify?.verdict}). Nothing to fix.`, mdChars: 0, mermaidCount: 0 }
    }
    return agent(
      `Fix REAL defects in a generated HLD session. Workspace: ${ROOT}/workspace/${p.uuid}_hld/_response.md (+ maybe capacity.py).

The adversarial reviewer found these actionable issues — fix EACH directly in _response.md (and capacity.py if the math is wrong, re-running it with ${PY}):
${actionable.map((f,i)=>`${i+1}. [${f.severity}] ${f.where}: ${f.problem}\n   FIX: ${f.fix}`).join('\n')}

CRITICAL for any mermaid finding: rewrite the offending node/edge labels to remove ALL breaking characters — parentheses, colons, semicolons, slashes, quotes, angle brackets, square/curly braces inside label or edge text. Replace ":" and ";" with words, drop parens, use <br/> for line breaks. Keep flowchart TD for multi-path diagrams.
Keep all 11 sections intact and fully expanded; keep md > 20,000 chars; no LaTeX. After fixing, re-read your mermaid blocks and confirm every label is renderer-safe. Return what you changed, final mdChars, and final mermaidCount.`,
      { label: `fix:${p.title.slice(0,18)}`, phase: 'Fix', schema: FIX_SCHEMA, agentType: 'general-purpose' }
    )
  },
)

return PROBLEMS.map((p, i) => ({ uuid: p.uuid, title: p.title, done: !!results[i] }))
