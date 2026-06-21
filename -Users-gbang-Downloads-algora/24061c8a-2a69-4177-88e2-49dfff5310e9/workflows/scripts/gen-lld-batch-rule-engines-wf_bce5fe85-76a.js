export const meta = {
  name: 'gen-lld-batch-rule-engines',
  description: 'Generate 4 new-prompt LLD sessions (Splitwise, Rate Limiter, Coupon, Notification Router): build+test code and full §1–§9 markdown, adversarially verify, then fix. Orchestrator assembles JSON afterwards.',
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
- ${ROOT}/lld_prompt.md   (the production LLD system prompt — your §1–§9 markdown MUST match its structure, including the NEW "## 3.5 API / System Interface" section between §3 and §4, and the §4.1 rule that EVERY class subsection ends with a COMPLETE fenced class block after its (c) operations table — never a bare table)
- ${ROOT}/agent_prompts/lld_session_builder.md   (the build recipe; IGNORE its old /Users/anshullkgarg/... paths — use the paths I give you below)

OPERATIONAL FACTS (override anything in those files):
- Workspace (create it): ${ROOT}/workspace/<UUID>_lld/   with tests/ subdir.
- Run code with: ${PY}  (NOT python3 — python3 lacks pytest here). e.g. \`cd ${ROOT}/workspace/<UUID>_lld && ${PY} main.py\` and \`${PY} -m pytest -q\`.
- Canonical flat file layout (bare names, NO packages): models.py, strategies.py (only if a Strategy is in §5), gateways.py (only if §5 names an external dep), <domain>_service.py (named after the DOMAIN, never service.py/utils.py), main.py, tests/conftest.py (sys.path shim), tests/test_<domain>.py.
- Python 3.11+ idioms ONLY: list[X], dict[K,V], X | None. NO 'from __future__ import annotations'. NO Optional/List/Dict. Imports at TOP of file only.
- ONE domain base exception; one specific subclass per failure mode. NEVER raise bare Exception/RuntimeError/ValueError from your own code. NEVER use a bare 'except:'; catch the narrowest correct type (but if you must release a lock/permit on ANY failure, 'except BaseException:' then re-raise is correct).
- Clean single-threaded CORE service with a no-op concurrency hook (e.g. a @contextmanager _lock() that just yields); a ThreadSafe<Domain>Service subclass overrides ONLY the hook(s). §6/§7 core is lock-free and readable; the thread-safe variant is the §9 "second version".
- NO '...'/'pass' placeholder bodies anywhere. Every method fully implemented. No dead code (every public method exercised by main.py or a test).

CONCURRENCY TEST RIGOR (critical): the pytest suite MUST include an N-thread race using threading.Barrier so all threads hit the critical section at one instant, with STRICT post-state assertions — not just a count. Assert the capacity/uniqueness invariant ACTUALLY bound (e.g. winners == K, len(set(winner_ids)) == K, every loser got the specific typed error, and the resource's own state field confirms exactly K committed). A single count assertion is necessary-but-NOT-sufficient: if the work is so fast threads serialise, ADD a tiny hold (time.sleep) inside the critical section and assert the peak concurrency actually reached the limit — otherwise the test passes trivially and proves nothing.

MERMAID RULES (a real renderer parses these — get them right):
- Exactly TWO mermaid blocks: a \`\`\`mermaid classDiagram in §4.2 and a \`\`\`mermaid sequenceDiagram in §8.
- In sequenceDiagram MESSAGE TEXT (after the colon), NEVER use a semicolon ';' — mermaid treats ';' as a statement separator and the parse FAILS. Write "do A then B", not "A; B".
- Keep participant aliases simple; avoid characters that break parsing.

MARKDOWN OUTPUT:
- Write the COMPLETE §1–§9 markdown (with the ⏱️ 60-Minute Interview Plan at the very top, and §3.5) to ${ROOT}/workspace/<UUID>_lld/_response.md — this is the full artifact the candidate reads, NOT abbreviated. Code blocks in §6 tagged \`\`\`python copy.
- §7.1 and §7.2 must quote the ACTUAL stdout from running main.py and pytest -q (run them, paste real output). Both must be green.

DO NOT assemble any conversation JSON and DO NOT write into ${ROOT}/data/conversations/ — the orchestrator does that afterwards. Your job: leave a WORKING workspace (tests green) + a complete _response.md.

Before finishing: run \`${PY} main.py\` (exit 0, all cases print OK) and \`${PY} -m pytest -q\` (fully green). If red, fix the CODE (not the test) and re-run.
`

const GEN_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['uuid','title','problemStatement','domain','files','mainPassed','pytestPassed','pytestSummary','mermaidCount','has35','concurrencyAngle','notes'],
  properties: {
    uuid: { type: 'string' },
    title: { type: 'string', description: 'e.g. "Design Splitwise"' },
    problemStatement: { type: 'string', description: 'the one-paragraph problem the user message should contain' },
    domain: { type: 'string', description: 'the <domain> used in <domain>_service.py and test_<domain>.py' },
    files: { type: 'array', items: { type: 'string' }, description: 'bare relative paths of every source file written, in tab order' },
    mainPassed: { type: 'boolean' },
    pytestPassed: { type: 'boolean' },
    pytestSummary: { type: 'string', description: 'e.g. "21 passed in 0.4s"' },
    mermaidCount: { type: 'number', description: 'number of ```mermaid blocks in _response.md (should be 2)' },
    has35: { type: 'boolean', description: 'is the "## 3.5 API / System Interface" section present in _response.md' },
    concurrencyAngle: { type: 'string' },
    notes: { type: 'string' },
  },
}

const VERIFY_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['verdict','findings'],
  properties: {
    verdict: { type: 'string', enum: ['SHIP','FIX-FIRST'] },
    findings: { type: 'array', items: { type: 'object', additionalProperties: false,
      required: ['severity','where','problem','fix'],
      properties: {
        severity: { type: 'string', enum: ['BLOCKER','MAJOR','MINOR'] },
        where: { type: 'string', description: 'file:line or section' },
        problem: { type: 'string' },
        fix: { type: 'string' },
      } } },
  },
}

const FIX_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['changed','summary','pytestPassed','pytestSummary','mainPassed'],
  properties: {
    changed: { type: 'boolean', description: 'were any files/_response.md modified' },
    summary: { type: 'string' },
    pytestPassed: { type: 'boolean' },
    pytestSummary: { type: 'string' },
    mainPassed: { type: 'boolean' },
  },
}

const PROBLEMS = [
  {
    uuid: 'db204167-ae0a-47cb-97df-c3388c453648',
    title: 'Design Splitwise',
    domain: 'expense',
    problemStatement: 'Design an in-memory, thread-safe expense-sharing application like Splitwise: users create groups, add expenses split equally / by exact amount / by percentage, the system maintains who-owes-whom balances, and supports settling up. Focus on the balance graph and deadlock-free concurrent settlements.',
    angle: 'DEADLOCK-FREE LOCK ORDERING: settling between two users mutates two users\' balances; acquire the two per-user locks in a CONSISTENT GLOBAL ORDER (e.g. sorted by user id) so concurrent reciprocal settlements (A→B and B→A) can never deadlock. The concurrency test must spawn many reciprocal settlements through a Barrier and assert no deadlock + balances net to zero. Patterns: Strategy (SplitStrategy: Equal/Exact/Percent), Information Expert (balance owned in one place).',
  },
  {
    uuid: 'bb2e4a02-4955-44a7-8e51-4f349bee8ad1',
    title: 'Design an API Rate Limiter',
    domain: 'rate_limiter',
    problemStatement: 'Design a per-customer API rate limiter: given a customer id and a timestamp, allow or reject the request according to a configurable policy (token bucket, fixed window, sliding window). In-memory and thread-safe; different customers must not contend.',
    angle: 'LOCK STRIPING (sharded locks): one lock PER CUSTOMER (a striped lock map) so requests from different customers never serialise — only same-customer requests contend. Inject a Clock for testability. Patterns: Strategy (RateLimitAlgorithm: TokenBucket/FixedWindow/SlidingWindow), Template Method (the _lock hook keyed per customer). Concurrency test: many threads hammering ONE customer at the boundary, assert exactly `limit` allowed; and threads across MANY customers proving no cross-customer blocking.',
  },
  {
    uuid: '295efbbb-8ccc-4bff-95f9-0bb2fd694db2',
    title: 'Design a Coupon Management System',
    domain: 'coupon',
    problemStatement: 'Design a coupon / offers management system: sellers create coupons (percent-off, flat-off, BOGO) with constraints (expiry, min cart value, per-user limit, global usage limit); the system validates and redeems a coupon against a cart. In-memory, thread-safe. Focus on the redemption race when the last use of a usage-limited coupon is claimed concurrently.',
    angle: 'USAGE-LIMIT REDEMPTION RACE: a coupon with a global usage limit redeemed concurrently — under a per-coupon lock, atomically check-and-decrement remaining uses so exactly `limit` redemptions succeed and the rest get a typed LimitExhausted error. Patterns: Chain of Responsibility (validation rules: Expiry → MinCart → PerUserLimit → GlobalLimit, each a handler), Strategy (DiscountStrategy). Concurrency test: N threads redeem the last K uses through a Barrier; assert exactly K succeed, N-K get the typed error, and remaining_uses == 0.',
  },
  {
    uuid: '7ceac10d-40b2-402f-8861-a39c7053ed5d',
    title: 'Design a Notification Router',
    domain: 'notification',
    problemStatement: 'Design a notification router for an e-commerce platform: an event (order shipped, payment failed) is routed to one or more channels (email, SMS, push) based on user preferences and rules; delivery must be idempotent (the same notification id is delivered at most once even under concurrent dispatch). In-memory, thread-safe.',
    angle: 'IDEMPOTENT DEDUP under concurrency: a concurrent "seen" set guarded so a given notification id is dispatched exactly once even if two threads race the same id (first-writer-wins); the actual channel send happens OUTSIDE the lock so a slow SMS gateway never blocks the dedup map. Patterns: Chain of Responsibility (routing rules), Adapter (ChannelAdapter: Email/SMS/Push wrap disparate gateways behind one interface), Observer optional. Concurrency test: N threads dispatch the SAME notification id through a Barrier; assert the channel received it exactly once.',
  },
]

phase('Generate')

const results = await pipeline(
  PROBLEMS,

  // STAGE 1 — generate
  (p) => agent(
    `${RECIPE}

=== YOUR ASSIGNED PROBLEM ===
UUID: ${p.uuid}
TITLE: ${p.title}
DOMAIN (for <domain>_service.py / test_<domain>.py): ${p.domain}
PROBLEM STATEMENT (put this in §1 and return it verbatim): ${p.problemStatement}

DISTINCT CONCURRENCY ANGLE you MUST realize in code + §9 (this is what makes this session unique — do not drift to a generic lock):
${p.angle}

Build the complete session now in ${ROOT}/workspace/${p.uuid}_lld/ . Read the two prompt files first, then write code, run tests green with ${PY}, write the full _response.md. Return the structured summary. Set has35=true only if "## 3.5 API / System Interface" is literally in _response.md, and mermaidCount to the actual count of \`\`\`mermaid blocks (must be 2).`,
    { label: `gen:${p.domain}`, phase: 'Generate', schema: GEN_SCHEMA, agentType: 'general-purpose' }
  ),

  // STAGE 2 — adversarial verify
  (gen, p) => agent(
    `Adversarially review a generated LLD session. Be a skeptic — find REAL defects, do not rubber-stamp. Review-only: DO NOT modify files.

Workspace: ${ROOT}/workspace/${p.uuid}_lld/  (source files + _response.md)
Run tests yourself to check: \`cd ${ROOT}/workspace/${p.uuid}_lld && ${PY} main.py\` and \`${PY} -m pytest -q\`.

Problem: ${p.title}. Required distinct concurrency angle: ${p.angle}

Check and report PASS/FAIL with evidence (file:line) on each:
1. CONCURRENCY CORRECTNESS: is the claimed angle actually implemented and correct? Can the invariant be violated? Any deadlock, lost-wakeup, permit/lock leak, or check-then-act that isn't atomic? Does releasing happen even on failure paths (factory/handler raising a NON-domain exception)?
2. CONCURRENCY TEST STRENGTH: does the test PROVE the invariant under real contention (Barrier + strict post-state: counts AND uniqueness AND typed losers AND committed-state count)? Or could it pass trivially because the work serialises (no hold in the critical section, peak never reaches the limit)?
3. §3.5 API section present with a real typed contract table (Method | Signature | Returns | Raises | Purpose)? Every method also in §4.1/§4.2/§6?
4. §4.1: does EVERY class subsection end with a COMPLETE fenced class block after its (c) table (not a bare table)?
5. Does the §6 \`\`\`python code match the actual disk files (no drift, no '...' bodies)?
6. EARN YOUR PATTERNS: are all claimed patterns genuinely realized in code?
7. MERMAID: exactly 2 blocks; NO semicolon ';' inside any sequenceDiagram message text (that breaks the parser); both would parse.
8. Python: 3.11+ idioms only, no bare except, one domain exception base, no dead code.

Return verdict SHIP or FIX-FIRST and a findings list (severity/where/problem/fix). Only BLOCKER/MAJOR matter for the fix step; list MINORs too but they won't block.`,
    { label: `verify:${p.domain}`, phase: 'Verify', schema: VERIFY_SCHEMA, agentType: 'general-purpose' }
  ),

  // STAGE 3 — fix (only acts if there are BLOCKER/MAJOR findings)
  (verify, p) => {
    const actionable = (verify?.findings || []).filter(f => f.severity === 'BLOCKER' || f.severity === 'MAJOR')
    if (!actionable.length) {
      return { changed: false, summary: `No BLOCKER/MAJOR findings (verdict ${verify?.verdict}). Nothing to fix.`, pytestPassed: true, pytestSummary: 'unchanged', mainPassed: true }
    }
    return agent(
      `Fix REAL defects in a generated LLD session, then re-verify by running tests. Workspace: ${ROOT}/workspace/${p.uuid}_lld/

The adversarial reviewer found these actionable issues — fix EACH in the CODE and/or _response.md (keep them consistent — if you change code that appears in a §6 \`\`\`python block, update that block too):
${actionable.map((f,i)=>`${i+1}. [${f.severity}] ${f.where}: ${f.problem}\n   FIX: ${f.fix}`).join('\n')}

Rules: fix the CODE not the test (unless the test itself is the defect, e.g. too weak to prove the invariant — then strengthen it). Keep Python 3.11+ idioms, one domain exception base, no bare except, no '...' bodies. If you touch the §8 sequence diagram, ensure NO semicolons in message text. After fixing, run \`cd ${ROOT}/workspace/${p.uuid}_lld && ${PY} main.py\` and \`${PY} -m pytest -q\` and confirm both green. Also update §7.1/§7.2 in _response.md if the test count/output changed. Return what you changed and the final test status.`,
      { label: `fix:${p.domain}`, phase: 'Fix', schema: FIX_SCHEMA, agentType: 'general-purpose' }
    )
  },
)

return PROBLEMS.map((p, i) => ({
  uuid: p.uuid, title: p.title, domain: p.domain,
  gen: results[i] ? 'see-gen' : 'FAILED',
}))
