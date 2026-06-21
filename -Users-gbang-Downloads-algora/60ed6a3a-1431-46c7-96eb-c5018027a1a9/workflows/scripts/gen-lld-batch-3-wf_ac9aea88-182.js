export const meta = {
  name: 'gen-lld-batch-3',
  description: 'Generate 6 new-prompt LLD sessions (Order Matching Engine, ATM, Traffic Signal, Digital Wallet, Search Autocomplete, LFU Cache): build+test code and full §1–§9 markdown, adversarially verify, then fix. Orchestrator assembles JSON afterwards.',
  phases: [
    { title: 'Generate' },
    { title: 'Verify' },
    { title: 'Fix' },
  ],
}

const ROOT = '/Users/gbang/Downloads/algora'
const PY = `${ROOT}/.venv/bin/python`

const RECIPE = `
You are generating ONE complete Low-Level-Design interview session for an Uber SDE-2 prep app.

FIRST, read these two files IN FULL — they define the exact quality bar and section structure:
- ${ROOT}/lld_prompt.md   (the production LLD system prompt — your §1–§9 markdown MUST match its structure, including the "## 3.5 API / System Interface" section between §3 and §4, and the §4.1 rule that EVERY class subsection ends with a COMPLETE fenced class block after its (c) operations table — never a bare table; a method-less value record still gets a fenced class block showing its fields)
- ${ROOT}/agent_prompts/lld_session_builder.md   (the build recipe; IGNORE its old /Users/anshullkgarg/... paths — use the paths I give you below)

OPERATIONAL FACTS (override anything in those files):
- Workspace (create it): ${ROOT}/workspace/<UUID>_lld/   with tests/ subdir.
- Run code with: ${PY}  (NOT python3 — python3 lacks pytest here). e.g. \`cd ${ROOT}/workspace/<UUID>_lld && ${PY} main.py\` and \`${PY} -m pytest -q\`.
- Canonical flat file layout (bare names, NO packages): models.py, strategies.py (only if a Strategy is in §5), gateways.py (only if §5 names an external dep / injected Clock), <domain>_service.py (named after the DOMAIN, never service.py/utils.py), main.py, tests/conftest.py (sys.path shim), tests/test_<domain>.py.
- Python 3.11+ idioms ONLY: list[X], dict[K,V], X | None. NO 'from __future__ import annotations'. NO Optional/List/Dict. Imports at TOP of file only.
- ONE domain base exception; one specific subclass per failure mode. NEVER raise bare Exception/RuntimeError/ValueError from your own code. NEVER use a bare 'except:'; catch the narrowest correct type. If you must roll back / release a lock on ANY failure path, 'except BaseException:' then re-raise is the correct idiom.
- Money is integer CENTS — never floats for currency.
- Clean single-threaded CORE service with a no-op concurrency hook (e.g. a @contextmanager _lock() that just yields); a ThreadSafe<Domain>Service subclass overrides ONLY the hook(s). §6/§7 core is lock-free and readable; the thread-safe variant is the §9 "second version". Any slow I/O stays OUTSIDE the lock.
- NO '...'/'pass' placeholder bodies anywhere. Every method fully implemented. No dead code (every public method exercised by main.py or a test).
- Inject a Clock (gateways.py) wherever time matters so tests are deterministic.

CONCURRENCY TEST RIGOR (critical): the pytest suite MUST include an N-thread race using threading.Barrier so all threads hit the critical section at one instant, with STRICT post-state assertions — not just a count. Assert the invariant ACTUALLY bound (e.g. winners == K, len(set(winner_ids)) == K, every loser got the specific typed error, and the entity's own state/balance field confirms the conserved quantity). A single count assertion is necessary-but-NOT-sufficient: if work serialises, ADD a tiny hold (time.sleep) inside the critical section and assert the peak concurrency actually reached the limit.

MERMAID RULES (a real renderer parses these):
- Exactly TWO mermaid blocks: a \`\`\`mermaid classDiagram in §4.2 and a \`\`\`mermaid sequenceDiagram in §8.
- In sequenceDiagram MESSAGE TEXT (after the colon), NEVER use a semicolon ';' — mermaid treats ';' as a statement separator and the parse FAILS. Write "do A then B". Avoid tokens that break parsing. Keep participant aliases simple.

MARKDOWN OUTPUT:
- Write the COMPLETE §1–§9 markdown (⏱️ 60-Minute Interview Plan at the very top, and §3.5) to ${ROOT}/workspace/<UUID>_lld/_response.md — the full artifact, NOT abbreviated. §6 code blocks tagged \`\`\`python copy and matching the disk files (no drift, no '...').
- §7.1 and §7.2 must quote the ACTUAL stdout from running main.py and pytest -q. Both must be green.

DO NOT assemble any conversation JSON and DO NOT write into ${ROOT}/data/conversations/ — the orchestrator does that afterwards. Leave a WORKING workspace (tests green) + a complete _response.md.

Before finishing: run \`${PY} main.py\` (exit 0, all cases print OK) and \`${PY} -m pytest -q\` (fully green). If red, fix the CODE (not the test) and re-run.
`

const GEN_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['uuid','title','domain','files','mainPassed','pytestPassed','pytestSummary','mermaidCount','has35','concurrencyAngle','notes'],
  properties: { uuid:{type:'string'}, title:{type:'string'}, domain:{type:'string'},
    files:{type:'array',items:{type:'string'}}, mainPassed:{type:'boolean'}, pytestPassed:{type:'boolean'},
    pytestSummary:{type:'string'}, mermaidCount:{type:'number'}, has35:{type:'boolean'},
    concurrencyAngle:{type:'string'}, notes:{type:'string'} },
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
  required: ['changed','summary','pytestPassed','pytestSummary','mainPassed'],
  properties: { changed:{type:'boolean'}, summary:{type:'string'}, pytestPassed:{type:'boolean'}, pytestSummary:{type:'string'}, mainPassed:{type:'boolean'} },
}

const PROBLEMS = [
  {
    uuid: 'b9b8118c-3795-43c8-b3ac-5bf4a6119a42',
    title: 'Design an Order Matching Engine',
    domain: 'exchange',
    problemStatement: 'Design the matching engine of a stock exchange: traders submit limit BUY/SELL orders for a symbol; the engine maintains a per-symbol order book and matches crossing orders by PRICE-TIME priority (best price first, then earliest); a match may PARTIALLY fill orders, leaving the remainder resting. Support cancel. In-memory, thread-safe per symbol.',
    angle: 'PRICE-TIME PRIORITY order book using TWO HEAPS (max-heap of bids, min-heap of asks) + FIFO within a price level + PARTIAL-FILL atomicity (a single submit may generate several trades and leave a remainder resting — all under one per-symbol lock so the book never tears) + PER-SYMBOL lock so different symbols match in parallel. Patterns: Strategy optional (order type), Information Expert (the book owns matching). Concurrency test: Barrier-sync many threads submitting crossing orders on ONE symbol; assert total filled quantity is conserved (sum of buys filled == sum of sells filled), no quantity created or destroyed, price-time priority respected, and the book is consistent (no crossed book left).',
  },
  {
    uuid: 'a836a0bf-2597-4b84-9bcf-e51e582cdc15',
    title: 'Design an ATM',
    domain: 'atm',
    problemStatement: 'Design an ATM: insert card → enter PIN (authenticate) → select operation (withdraw / balance) → dispense cash and debit the account. The machine is a state machine (IDLE → CARD_INSERTED → AUTHENTICATED → DISPENSING). On any failure (wrong PIN, insufficient funds, dispense failure) roll back cleanly and eject the card. Thread-safe; the account store is shared.',
    angle: 'STATE MACHINE (explicit ATM states with legal transitions) + TRANSACTIONAL withdraw with ROLLBACK ON FAILURE (debit the account and dispense as an atomic unit — if dispense fails, the debit is reversed; the account balance must never be debited without cash leaving, nor cash dispensed without a debit) + per-account lock for the shared account store. Patterns: State (primary), Strategy optional (cash-dispense denomination algorithm). Concurrency test: Barrier-sync N threads withdrawing from the SAME account that only has funds for K; assert exactly K succeed, N-K get typed InsufficientFunds, final balance == initial - K*amount (never negative), and total cash dispensed matches the total debited (no money created/lost).',
  },
  {
    uuid: 'dfd83684-a260-4d7a-a9fd-5d98b53d9c1f',
    title: 'Design a Traffic Signal Control System',
    domain: 'traffic',
    problemStatement: 'Design the control logic for traffic signals at an intersection: each direction has a light cycling GREEN → YELLOW → RED on timers; the controller must enforce the SAFETY INVARIANT that conflicting directions are never GREEN (or GREEN/YELLOW) at the same time. Support emergency override (all-red, or priority green for one direction). Thread-safe; an injected Clock drives timed transitions.',
    angle: 'TIMED STATE TRANSITIONS (each signal is a state machine on a timer) + a hard SAFETY INVARIANT enforced centrally (at most one conflicting group may be GREEN/YELLOW; the controller transitions atomically so there is never a window where two conflicting directions show go) + injected Clock for deterministic timing + a lock around each cycle transition. Patterns: State, Strategy (signal timing plan / fixed-time vs adaptive). Concurrency test: Barrier-sync threads advancing the clock and requesting emergency overrides concurrently; assert the safety invariant (no two conflicting directions ever simultaneously GREEN/YELLOW) holds across EVERY observed state snapshot — sample the state repeatedly and assert it is always safe.',
  },
  {
    uuid: 'ce66643b-92f1-4928-90f8-f5d694d21d50',
    title: 'Design a Digital Wallet / Payment System',
    domain: 'wallet',
    problemStatement: 'Design a digital wallet: users hold balances; support deposit, withdraw, and transfer money between two wallets. Transfers must be atomic and idempotent (a retried transfer with the same idempotency key applies once). Maintain a double-entry ledger so the books always balance. Money is integer cents. In-memory, thread-safe.',
    angle: 'DEBIT/CREDIT ATOMICITY with DOUBLE-ENTRY LEDGER (every transfer writes two ledger entries summing to zero; system-wide money is conserved) + IDEMPOTENT transfers (an idempotency-key set so a retried transfer applies exactly once, returning the original result) + DEADLOCK-FREE two-account locking (acquire the two wallet locks in a consistent global order by wallet id). Patterns: Information Expert (wallet owns its balance), Strategy optional. Concurrency test: Barrier-sync N threads firing reciprocal + duplicate-key transfers; assert total money across all wallets is conserved (== initial sum), no balance goes negative, duplicate-key transfers applied exactly once, ledger entries sum to zero, and no deadlock.',
  },
  {
    uuid: 'd361314b-a6dd-46c7-ac2f-67321af0e7b7',
    title: 'Design a Search Autocomplete (Typeahead)',
    domain: 'autocomplete',
    problemStatement: 'Design a search autocomplete / typeahead: index terms with frequencies; given a prefix, return the top-K most-frequent completions in ranked order. Support adding/boosting a term (e.g. when a query is searched). In-memory, thread-safe with many concurrent reads and occasional writes.',
    angle: 'TRIE (prefix tree) for prefix queries + TOP-K RANKING by frequency (each prefix node can cache its top-K, or aggregate + heap on query) + READ-WRITE lock (many concurrent prefix reads, exclusive on insert/boost) since reads vastly outnumber writes. Patterns: Information Expert (trie owns prefix structure), Strategy optional (ranking/tie-break). Concurrency test: Barrier-sync R reader threads querying prefixes + W writer threads boosting term frequencies; assert final frequencies exactly equal the sum of all boosts (no lost update), top-K results are correct and correctly ordered after all writes, and concurrent reads never observe a corrupt/partial trie.',
  },
  {
    uuid: '015d7fb9-fde7-41ad-9cdc-4c5379226a17',
    title: 'Design an LFU Cache',
    domain: 'lfu',
    problemStatement: 'Design a thread-safe LFU (Least-Frequently-Used) cache with get(key) and put(key, value): on capacity overflow, evict the least-frequently-used key; break ties by least-recently-used among the minimum frequency. Both get and put must be O(1). In-memory, thread-safe.',
    angle: 'O(1) LFU via FREQUENCY BUCKETS: a dict key->node, a dict freq->ordered-list (doubly-linked / OrderedDict) of keys at that frequency, and a min-frequency pointer; get/put bump the node to the next freq bucket in O(1); eviction pops the LRU from the min-freq bucket. Lock striping or a single lock guarding the structure (the whole get/put must be atomic because it mutates several maps + the min-freq pointer together — a check-then-act on capacity). Patterns: Information Expert (cache owns eviction policy). Concurrency test: Barrier-sync N threads doing concurrent get/put that force evictions; assert the cache never exceeds capacity at any observed point, the size invariant holds, evicted keys are exactly the LFU ones, and the internal maps stay consistent (min-freq pointer valid, no orphaned nodes).',
  },
]

phase('Generate')

const results = await pipeline(
  PROBLEMS,

  (p) => agent(
    `${RECIPE}

=== YOUR ASSIGNED PROBLEM ===
UUID: ${p.uuid}
TITLE: ${p.title}
DOMAIN (for <domain>_service.py / test_<domain>.py): ${p.domain}
PROBLEM STATEMENT (put this in §1 and keep it verbatim): ${p.problemStatement}

DISTINCT CONCURRENCY / DATA-STRUCTURE ANGLE you MUST realize in code + §9 (this is what makes this session unique — do not drift to a generic per-resource lock):
${p.angle}

Build the complete session now in ${ROOT}/workspace/${p.uuid}_lld/ . Read the two prompt files first, then write code, run tests green with ${PY}, write the full _response.md. Return the structured summary. Set has35=true only if "## 3.5 API / System Interface" is literally in _response.md, and mermaidCount to the actual count of \`\`\`mermaid blocks (must be 2).`,
    { label: `gen:${p.domain}`, phase: 'Generate', schema: GEN_SCHEMA, agentType: 'general-purpose' }
  ),

  (gen, p) => agent(
    `Adversarially review a generated LLD session. Be a skeptic — find REAL defects, do not rubber-stamp. Review-only: DO NOT modify files.

Workspace: ${ROOT}/workspace/${p.uuid}_lld/  (source files + _response.md)
Run tests yourself: \`cd ${ROOT}/workspace/${p.uuid}_lld && ${PY} main.py\` and \`${PY} -m pytest -q\`.

Problem: ${p.title}. Required distinct angle: ${p.angle}

Report PASS/FAIL with evidence (file:line) on each:
1. CORRECTNESS of the core DS/algorithm: is the claimed structure actually implemented correctly (two-heap order book with price-time + partial fills / O(1) LFU buckets + min-freq pointer / trie + top-K / double-entry ledger conservation / state-machine legal transitions)? Find an input that breaks it.
2. CONCURRENCY CORRECTNESS: can the invariant be violated (money created/lost, crossed book, negative balance, cache over capacity, lost update, unsafe traffic state, debit-without-dispense)? Any deadlock, lost-wakeup, lock leak, or non-atomic check-then-act? Does rollback/release happen even when a step raises a NON-domain exception? Slow I/O outside the lock?
3. CONCURRENCY TEST STRENGTH: does it PROVE the invariant under real contention (Barrier + strict post-state: conservation AND uniqueness AND typed losers AND committed-state)? Or trivially passable (serialised, no hold, peak never reaches limit)? Injected Clock used where time matters?
4. §3.5 API section present with a real typed contract table (Method | Signature | Returns | Raises | Purpose)? Every method also in §4.1/§4.2/§6?
5. §4.1: does EVERY class subsection end with a COMPLETE fenced class block after its (c) table (method-less record still needs its fields block)?
6. Does the §6 \`\`\`python code match the actual disk files (no drift, no '...' bodies)?
7. EARN YOUR PATTERNS: are all claimed patterns genuinely realized in code?
8. MERMAID: exactly 2 blocks; NO semicolon ';' inside any sequenceDiagram message text; both would parse.
9. Python: 3.11+ idioms only, no bare except, one domain exception base, integer cents for money, no dead code.

Return verdict SHIP or FIX-FIRST and a findings list (severity/where/problem/fix). Only BLOCKER/MAJOR block; list MINORs too.`,
    { label: `verify:${p.domain}`, phase: 'Verify', schema: VERIFY_SCHEMA, agentType: 'general-purpose' }
  ),

  (verify, p) => {
    const actionable = (verify?.findings || []).filter(f => f.severity === 'BLOCKER' || f.severity === 'MAJOR')
    if (!actionable.length) {
      return { changed: false, summary: `No BLOCKER/MAJOR findings (verdict ${verify?.verdict}). Nothing to fix.`, pytestPassed: true, pytestSummary: 'unchanged', mainPassed: true }
    }
    return agent(
      `Fix REAL defects in a generated LLD session, then re-verify by running tests. Workspace: ${ROOT}/workspace/${p.uuid}_lld/

The adversarial reviewer found these actionable issues — fix EACH in the CODE and/or _response.md (keep them consistent — if you change code shown in a §6 \`\`\`python block, update that block too):
${actionable.map((f,i)=>`${i+1}. [${f.severity}] ${f.where}: ${f.problem}\n   FIX: ${f.fix}`).join('\n')}

Rules: fix the CODE not the test (unless the test itself is too weak to prove the invariant — then strengthen it). Keep Python 3.11+ idioms, one domain exception base, no bare except, integer cents for money, no '...' bodies, slow I/O outside locks. If you touch the §8 sequence diagram, ensure NO semicolons in message text. After fixing, run \`cd ${ROOT}/workspace/${p.uuid}_lld && ${PY} main.py\` and \`${PY} -m pytest -q\` and confirm both green. Update §7.1/§7.2 if the test count/output changed. Return what you changed and final test status.`,
      { label: `fix:${p.domain}`, phase: 'Fix', schema: FIX_SCHEMA, agentType: 'general-purpose' }
    )
  },
)

return PROBLEMS.map((p, i) => ({ uuid: p.uuid, title: p.title, domain: p.domain, done: !!results[i] }))
