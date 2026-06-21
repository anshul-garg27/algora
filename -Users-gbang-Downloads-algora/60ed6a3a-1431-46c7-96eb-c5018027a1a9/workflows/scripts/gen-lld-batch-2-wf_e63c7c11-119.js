export const meta = {
  name: 'gen-lld-batch-2',
  description: 'Generate 6 new-prompt LLD sessions (Message Broker, Task Scheduler, Leaderboard, Vending Machine, Elevator, TTL KV Store): build+test code and full §1–§9 markdown, adversarially verify, then fix. Orchestrator assembles JSON afterwards.',
  phases: [
    { title: 'Generate' },
    { title: 'Verify' },
    { title: 'Fix' },
  ],
}

const ROOT = '/Users/gbang/Downloads/algora'
const PY = `${ROOT}/.venv/bin/python`          // has pytest; plain python3 does NOT

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
- ONE domain base exception; one specific subclass per failure mode. NEVER raise bare Exception/RuntimeError/ValueError from your own code. NEVER use a bare 'except:'; catch the narrowest correct type. If you must release a lock/permit/notify on ANY failure path, 'except BaseException:' then re-raise is the correct idiom (a domain-only except would leak on a non-domain error).
- Clean single-threaded CORE service with a no-op concurrency hook (e.g. a @contextmanager _lock() that just yields); a ThreadSafe<Domain>Service subclass overrides ONLY the hook(s). §6/§7 core is lock-free and readable; the thread-safe variant is the §9 "second version". Any slow I/O (notify, channel send) stays OUTSIDE the lock.
- NO '...'/'pass' placeholder bodies anywhere. Every method fully implemented. No dead code (every public method exercised by main.py or a test).
- Inject a Clock (gateways.py) wherever time matters (scheduler, TTL) so tests are deterministic — never call the real wall clock inside core logic without an injection seam.

CONCURRENCY TEST RIGOR (critical): the pytest suite MUST include an N-thread race using threading.Barrier so all threads hit the critical section at one instant, with STRICT post-state assertions — not just a count. Assert the invariant ACTUALLY bound (e.g. winners == K, len(set(winner_ids)) == K, every loser got the specific typed error, and the entity's own state field confirms exactly K committed). A single count assertion is necessary-but-NOT-sufficient: if the work is so fast threads serialise, ADD a tiny hold (time.sleep) inside the critical section and assert the peak concurrency actually reached the limit — otherwise the test passes trivially and proves nothing.

MERMAID RULES (a real renderer parses these — get them right):
- Exactly TWO mermaid blocks: a \`\`\`mermaid classDiagram in §4.2 and a \`\`\`mermaid sequenceDiagram in §8.
- In sequenceDiagram MESSAGE TEXT (after the colon), NEVER use a semicolon ';' — mermaid treats ';' as a statement separator and the parse FAILS. Write "do A then B", not "A; B". Also avoid other tokens that break parsing in message text.
- Keep participant aliases simple.

MARKDOWN OUTPUT:
- Write the COMPLETE §1–§9 markdown (with the ⏱️ 60-Minute Interview Plan at the very top, and §3.5) to ${ROOT}/workspace/<UUID>_lld/_response.md — the full artifact the candidate reads, NOT abbreviated. §6 code blocks tagged \`\`\`python copy. The §6 python blocks must match the disk files (no drift, no '...').
- §7.1 and §7.2 must quote the ACTUAL stdout from running main.py and pytest -q (run them, paste real output). Both must be green.

DO NOT assemble any conversation JSON and DO NOT write into ${ROOT}/data/conversations/ — the orchestrator does that afterwards. Your job: leave a WORKING workspace (tests green) + a complete _response.md.

Before finishing: run \`${PY} main.py\` (exit 0, all cases print OK) and \`${PY} -m pytest -q\` (fully green). If red, fix the CODE (not the test) and re-run.
`

const GEN_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['uuid','title','domain','files','mainPassed','pytestPassed','pytestSummary','mermaidCount','has35','concurrencyAngle','notes'],
  properties: {
    uuid: { type: 'string' }, title: { type: 'string' }, domain: { type: 'string' },
    files: { type: 'array', items: { type: 'string' } },
    mainPassed: { type: 'boolean' }, pytestPassed: { type: 'boolean' },
    pytestSummary: { type: 'string' }, mermaidCount: { type: 'number' },
    has35: { type: 'boolean' }, concurrencyAngle: { type: 'string' }, notes: { type: 'string' },
  },
}
const VERIFY_SCHEMA = {
  type: 'object', additionalProperties: false, required: ['verdict','findings'],
  properties: {
    verdict: { type: 'string', enum: ['SHIP','FIX-FIRST'] },
    findings: { type: 'array', items: { type: 'object', additionalProperties: false,
      required: ['severity','where','problem','fix'],
      properties: { severity: { type: 'string', enum: ['BLOCKER','MAJOR','MINOR'] },
        where: { type: 'string' }, problem: { type: 'string' }, fix: { type: 'string' } } } },
  },
}
const FIX_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['changed','summary','pytestPassed','pytestSummary','mainPassed'],
  properties: { changed: { type: 'boolean' }, summary: { type: 'string' },
    pytestPassed: { type: 'boolean' }, pytestSummary: { type: 'string' }, mainPassed: { type: 'boolean' } },
}

const PROBLEMS = [
  {
    uuid: '9a6dfee3-23d7-4977-ba89-3f9513c33122',
    title: 'Design a Message Broker (Pub-Sub)',
    domain: 'broker',
    problemStatement: 'Design an in-memory, thread-safe topic-based message broker (Kafka-style pub/sub): producers publish messages to a topic; multiple consumer groups subscribe and each consumer reads from its own committed OFFSET so every group sees every message independently; consumers block until a new message arrives. Support multiple topics.',
    angle: 'CONDITION-VARIABLE wait/notify + PER-CONSUMER-GROUP OFFSETS: each topic holds an append-only log; each consumer group tracks its own read offset; a poll() blocks on a threading.Condition until publish() appends and notifies. Observer pattern (subscribers), per-topic lock. The concurrency test: producers publish N messages while M consumer-group threads poll concurrently (Barrier-synced); assert every group reads ALL N messages exactly once in order, offsets end at N, and no message lost or duplicated.',
  },
  {
    uuid: '14739f84-55e7-4699-8245-d7d3bf7eca9c',
    title: 'Design a Task Scheduler',
    domain: 'scheduler',
    problemStatement: 'Design an in-memory concurrent task scheduler: submit a task to run at a scheduled time (one-shot, and optionally fixed-delay recurring); worker threads execute due tasks; the soonest task runs first. Thread-safe; an injected Clock makes it testable.',
    angle: 'MIN-HEAP priority queue (by run-at time) + CONDITION-VARIABLE timed wait: worker waits on a Condition with a timeout equal to "time until the next due task"; submitting an earlier task notifies so the worker re-computes its wait. Injected Clock for determinism. Patterns: Strategy (a scheduling/retry policy or recurring vs one-shot), State (task lifecycle SCHEDULED→RUNNING→DONE/CANCELLED). Concurrency test: Barrier-sync many submitters + workers; assert every task runs exactly once, in time order, none lost, cancel before run is honored. Use the injected clock — do NOT sleep on the real wall clock in the test beyond tiny holds.',
  },
  {
    uuid: '5b1d7c37-61ef-44f6-96d4-0c8311832886',
    title: 'Design a Thread-Safe Leaderboard',
    domain: 'leaderboard',
    problemStatement: 'Design a thread-safe leaderboard: submit/increment a player score, get a player rank (1-based), and get the top-K players. Many concurrent score updates with frequent reads. In-memory.',
    angle: 'READ-WRITE LOCK (many concurrent readers, exclusive writers) + a SORTED structure for O(log n) rank/top-K. Reads (rank, top-K) take the shared read lock; score updates take the exclusive write lock. Optionally shard by player-id bucket to reduce write contention. Patterns: Information Expert (the leaderboard owns ordering), Strategy optional (tie-break policy). Concurrency test: Barrier-sync W writer threads each incrementing distinct + shared players while R reader threads read; assert final scores exactly equal the sum of increments (no lost update), ranks are consistent, and top-K is correct. A plain lock that drops updates must fail the test.',
  },
  {
    uuid: '56b68468-1a94-427b-a556-a86f12dd402f',
    title: 'Design a Vending Machine System',
    domain: 'vending',
    problemStatement: 'Design a vending machine: insert coins, select a product, dispense the product with correct change, refund on cancel. The machine moves through states (IDLE → COLLECTING_MONEY → DISPENSING). Reject invalid selections, insufficient funds, out-of-stock. Thread-safe for a single machine.',
    angle: 'STATE PATTERN (the machine is a finite state machine with explicit state objects/transitions: Idle, HasMoney, Dispensing) + a SINGLE-MACHINE lock making the whole insert→select→dispense transaction atomic (one customer interacts at a time; concurrent button presses must not corrupt the state machine). Patterns: State (primary), Strategy optional (change-making algorithm). Concurrency test: Barrier-sync N threads all trying to buy the LAST item of a 1-stock product; assert exactly ONE succeeds and dispenses, the rest get a typed OutOfStock/typed error and are refunded, and stock ends at 0 — never negative, never double-dispense.',
  },
  {
    uuid: 'f92b9828-3a48-4edc-8af4-8bd704a2f7dd',
    title: 'Design an Elevator System',
    domain: 'elevator',
    problemStatement: 'Design the control logic for a bank of elevators: passengers make hall calls (UP/DOWN on a floor) and car calls (a destination inside a car); the system dispatches a suitable car and each car moves efficiently using the SCAN (elevator) algorithm without starving floors. Model each car as a state machine; dispatch policy is pluggable. Reject invalid floors/directions/unknown cars/out-of-service cars. Thread-safe under concurrent button presses; pressing the same floor twice is one stop (idempotent).',
    angle: 'SCAN movement algorithm + STATE machine per car (IDLE/MOVING/DOORS_OPEN/MAINTENANCE) + PLUGGABLE DISPATCH STRATEGY (nearest-car, least-busy) + PER-CAR lock so concurrent button presses on the same car serialise while different cars move in parallel; idempotent stop-queue (a set). Patterns: State, Strategy (DispatchStrategy), Template Method (_lock hook per car). Concurrency test: Barrier-sync many threads pressing the SAME floor on the same car plus distinct floors; assert the floor is queued exactly once (idempotent), all distinct stops are honored, and SCAN order is preserved — no lost or duplicated stop.',
  },
  {
    uuid: '4b84ed1f-7cdd-4050-9191-fb00141a0e7c',
    title: 'Design a Time-to-Live (TTL) Key-Value Store',
    domain: 'ttl_store',
    problemStatement: 'Design an in-memory TTL key-value store: put(key, value, ttl), get(key) returns the value only if not expired, delete(key), and an active count of currently-live keys. Expired keys must be reclaimed. Thread-safe; an injected Clock makes expiry testable.',
    angle: 'ACTIVE-EXPIRY SWEEPER (a background reaper thread that periodically evicts expired keys) + LAZY expiry on read (get also checks expiry) + an RLock guarding the store (reentrant because the sweeper and public methods may call shared guarded helpers). Injected Clock for deterministic expiry. Patterns: Template Method (_lock hook), Information Expert (an Entry owns its own expiry check). Concurrency test: Barrier-sync writers putting keys with short TTLs + readers + the sweeper running; advance the injected clock; assert expired keys are gone from both get() and the active count, live keys remain, active_count is exactly correct, and no race between lazy-expiry and the sweeper double-frees or miscounts.',
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

DISTINCT CONCURRENCY ANGLE you MUST realize in code + §9 (this is what makes this session unique — do not drift to a generic per-resource lock):
${p.angle}

Build the complete session now in ${ROOT}/workspace/${p.uuid}_lld/ . Read the two prompt files first, then write code, run tests green with ${PY}, write the full _response.md. Return the structured summary. Set has35=true only if "## 3.5 API / System Interface" is literally in _response.md, and mermaidCount to the actual count of \`\`\`mermaid blocks (must be 2).`,
    { label: `gen:${p.domain}`, phase: 'Generate', schema: GEN_SCHEMA, agentType: 'general-purpose' }
  ),

  (gen, p) => agent(
    `Adversarially review a generated LLD session. Be a skeptic — find REAL defects, do not rubber-stamp. Review-only: DO NOT modify files.

Workspace: ${ROOT}/workspace/${p.uuid}_lld/  (source files + _response.md)
Run tests yourself: \`cd ${ROOT}/workspace/${p.uuid}_lld && ${PY} main.py\` and \`${PY} -m pytest -q\`.

Problem: ${p.title}. Required distinct concurrency angle: ${p.angle}

Report PASS/FAIL with evidence (file:line) on each:
1. CONCURRENCY CORRECTNESS: is the claimed angle actually implemented and correct? Can the invariant be violated (lost update, lost/duplicated message, double-dispense, negative stock, miscounted TTL)? Any deadlock, lost-wakeup (Condition not re-checked in a while loop / notify missed), or lock/permit leak? Does release/notify happen even when a callback or factory raises a NON-domain exception? Is slow I/O kept outside the lock?
2. CONCURRENCY TEST STRENGTH: does the test PROVE the invariant under real contention (Barrier + strict post-state: counts AND uniqueness AND typed losers AND committed-state)? Or could it pass trivially (work serialises, peak never reaches the limit, no hold in the critical section)? For scheduler/TTL: is the injected Clock used instead of real sleeps?
3. §3.5 API section present with a real typed contract table (Method | Signature | Returns | Raises | Purpose)? Every method also in §4.1/§4.2/§6?
4. §4.1: does EVERY class subsection end with a COMPLETE fenced class block after its (c) table (a method-less record still needs its fields block)?
5. Does the §6 \`\`\`python code match the actual disk files (no drift, no '...' bodies)?
6. EARN YOUR PATTERNS: are all claimed patterns genuinely realized in code (real State objects/transitions, real Strategy interface+impls, real Observer registration, real read-write lock)?
7. MERMAID: exactly 2 blocks; NO semicolon ';' inside any sequenceDiagram message text; both would parse in a real renderer.
8. Python: 3.11+ idioms only, no bare except, one domain exception base, no dead code.

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

Rules: fix the CODE not the test (unless the test itself is the defect — e.g. too weak to prove the invariant — then strengthen it). Keep Python 3.11+ idioms, one domain exception base, no bare except, no '...' bodies, slow I/O outside locks. If you touch the §8 sequence diagram, ensure NO semicolons in message text. After fixing, run \`cd ${ROOT}/workspace/${p.uuid}_lld && ${PY} main.py\` and \`${PY} -m pytest -q\` and confirm both green. Update §7.1/§7.2 in _response.md if the test count/output changed. Return what you changed and final test status.`,
      { label: `fix:${p.domain}`, phase: 'Fix', schema: FIX_SCHEMA, agentType: 'general-purpose' }
    )
  },
)

return PROBLEMS.map((p, i) => ({ uuid: p.uuid, title: p.title, domain: p.domain, done: !!results[i] }))
