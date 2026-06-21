export const meta = {
  name: 'gen-java-lld-trio',
  description: 'Generate 3 Java LLD sessions: Parking Lot, Movie Ticket Booking, API Rate Limiter. Build+test code, full §1-§9 markdown, adversarial verify, fix.',
  phases: [
    { title: 'Generate', detail: 'Build Maven workspace, write code, run tests' },
    { title: 'Verify', detail: 'Adversarial review for correctness' },
    { title: 'Fix', detail: 'Apply fixes if needed' },
  ],
}

const ROOT = '/Users/gbang/Downloads/algora_java'
const PY = `${ROOT}/.venv/bin/python`

const RECIPE = `
You are generating ONE complete Low-Level-Design interview session in Java 17+ for Uber SDE-2 prep.

FIRST, read these files IN FULL:
- ${ROOT}/lld_prompt_java.md (Java LLD system prompt with §1-§9 structure)
- ${ROOT}/agent_prompts/lld_session_builder_java.md (Maven commands, operational facts)

OPERATIONAL FACTS:
- Workspace: ${ROOT}/workspace/<UUID>_lld/
- Maven structure: pom.xml + src/main/java/com/interview/lld/<domain>/ + src/test/java/
- Package: com.interview.lld.<domain> (lowercase, no underscores)
- Run: cd ${ROOT}/workspace/<UUID>_lld && mvn compile exec:java -Dexec.mainClass="com.interview.lld.<domain>.Main" -q
- Test: cd ${ROOT}/workspace/<UUID>_lld && mvn test -q
- Copy pom.xml from ${ROOT}/workspace_template_java/pom.xml, replace DOMAIN with actual domain

QUALITY BAR:
- §3.5 API table with Java signatures
- §4.1 EVERY class ends with COMPLETE java code block
- §6 code: package declarations, imports, no ... placeholders
- §7 real mvn output (green)
- §9 Template Method: base class hooks, ThreadSafe subclass overrides
- Mermaid: NO semicolons in sequenceDiagram messages

OUTPUT:
1. Write all .java files + pom.xml (full paths)
2. Run mvn compile exec:java and mvn test — confirm green
3. Write _response.md in workspace root with FULL §1-§9 markdown

Return: {uuid, domain, files, mainPassed, testsGreen, testCount, mermaidCount, has35, concurrencyAngle}
`

const GEN_SCHEMA = {
  type: 'object',
  required: ['uuid','domain','files','mainPassed','testsGreen','testCount','has35','mermaidCount'],
  properties: {
    uuid: {type: 'string'},
    domain: {type: 'string'},
    files: {type: 'array', items: {type: 'string'}},
    mainPassed: {type: 'boolean'},
    testsGreen: {type: 'boolean'},
    testCount: {type: 'number'},
    has35: {type: 'boolean'},
    mermaidCount: {type: 'number'},
    concurrencyAngle: {type: 'string'},
  }
}

const VERIFY_SCHEMA = {
  type: 'object',
  required: ['verdict','findings'],
  properties: {
    verdict: {type: 'string', enum: ['SHIP','FIX-FIRST']},
    findings: {type: 'array', items: {type: 'object', required: ['severity','where','problem'], properties: {
      severity: {type: 'string', enum: ['BLOCKER','MAJOR','MINOR']},
      where: {type: 'string'},
      problem: {type: 'string'},
      fix: {type: 'string'},
    }}}
  }
}

const FIX_SCHEMA = {
  type: 'object',
  required: ['changed','summary','testsGreen'],
  properties: {
    changed: {type: 'boolean'},
    summary: {type: 'string'},
    testsGreen: {type: 'boolean'},
    testCount: {type: 'number'},
  }
}

const PROBLEMS = [
  {
    uuid: 'java-lld-parking-001',
    title: 'Design a Parking Lot',
    domain: 'parking',
    statement: 'Design an in-memory, thread-safe parking lot: multiple floors, spots of different sizes (compact/large/handicapped), vehicles park and unpark, find nearest available spot, charge by time. Focus on: (1) spot allocation strategy (best-fit by size), (2) concurrent park/unpark without double-allocation.',
    angle: 'PER-SPOT FINE-GRAINED LOCKS: each ParkingSpot has its own ReentrantLock. park() acquires spot.lock() before marking occupied → prevents double-allocation race. Multiple threads can park/unpark different spots concurrently (no global bottleneck). Concurrency test: N threads park at once, assert no two get same spot.',
  },
  {
    uuid: 'java-lld-movieticket-001',
    title: 'Design Movie Ticket Booking',
    domain: 'moviebooking',
    statement: 'Design a movie ticket booking system: theaters with screens and showtimes, seats (available/booked/held), book multiple seats atomically, hold seats for 10min then release if unpaid. Thread-safe. Focus on: (1) atomic multi-seat booking (all-or-nothing), (2) seat hold expiry.',
    angle: 'TWO-PHASE COMMIT for multi-seat atomicity: under a per-showtime lock, first CHECK all seats available, then BOOK all or rollback. Prevents partial booking race (thread A books seat 1, thread B books seat 2, but A wanted both). Hold expiry: background thread scans held seats older than 10min, releases them. Concurrency test: many threads book overlapping seat sets, assert no double-booking.',
  },
  {
    uuid: 'java-lld-ratelimiter-002',
    title: 'Design an API Rate Limiter',
    domain: 'ratelimiter',
    statement: 'Design a per-customer API rate limiter: allow(customerId, timestamp) returns true/false per policy (token bucket or sliding window). Thread-safe, different customers should not contend. Injectable Clock for testing.',
    angle: 'LOCK STRIPING (per-customer sharded locks): ConcurrentHashMap<CustomerId, RateLimitState> with per-customer ReentrantLock. Requests from different customers never block each other. Inject Clock for testability. Strategy pattern: TokenBucket/SlidingWindow implementations. Concurrency test: many threads hammer ONE customer at boundary, assert exactly limit allowed; threads across MANY customers prove no cross-contention.',
  },
]

phase('Generate')

const results = await pipeline(
  PROBLEMS,
  
  // STAGE 1: generate
  (p) => agent(
    `${RECIPE}

=== YOUR PROBLEM ===
UUID: ${p.uuid}
TITLE: ${p.title}
DOMAIN: ${p.domain}
PROBLEM: ${p.statement}

CONCURRENCY ANGLE (MUST realize in code + §9):
${p.angle}

Build complete session in ${ROOT}/workspace/${p.uuid}_lld/. Read prompt files, write code, run mvn green, write _response.md. Return structured summary.`,
    {label: `gen:${p.domain}`, phase: 'Generate', schema: GEN_SCHEMA, effort: 'medium'}
  ),
  
  // STAGE 2: verify
  (gen, p) => agent(
    `Adversarially review Java LLD session at ${ROOT}/workspace/${p.uuid}_lld/. Be skeptical, find REAL defects.

Problem: ${p.title}. Required angle: ${p.angle}

Run tests yourself: cd ${ROOT}/workspace/${p.uuid}_lld && ${PY} -m pytest ... (wait, Java uses mvn test).

Check:
1. Concurrency correctness (claimed angle actually implemented? races? leaks?)
2. Test strength (Barrier + strict assertions? or trivial pass?)
3. §3.5 API table present with Java signatures?
4. §4.1 every class ends with COMPLETE java block?
5. §6 code matches disk (no drift, no ... bodies)?
6. Patterns earned (claimed patterns in code)?
7. Mermaid: 2 blocks, NO semicolons in sequence messages?
8. Java idioms (explicit types, null checks, one base exception)?

Return verdict SHIP or FIX-FIRST + findings (BLOCKER/MAJOR/MINOR).`,
    {label: `verify:${p.domain}`, phase: 'Verify', schema: VERIFY_SCHEMA, effort: 'medium'}
  ),
  
  // STAGE 3: fix
  (verify, p) => {
    const actionable = (verify?.findings || []).filter(f => f.severity === 'BLOCKER' || f.severity === 'MAJOR')
    if (!actionable.length) {
      return {changed: false, summary: `Verdict ${verify?.verdict}, no BLOCKER/MAJOR`, testsGreen: true, testCount: 0}
    }
    return agent(
      `Fix BLOCKER/MAJOR issues in ${ROOT}/workspace/${p.uuid}_lld/.

Issues:
${actionable.map((f,i) => `${i+1}. [${f.severity}] ${f.where}: ${f.problem}\n   Fix: ${f.fix || 'apply correction'}`).join('\n')}

Fix CODE (not test unless test itself is weak). Keep Java 17+ idioms, one base exception, no ... bodies. After fix, run mvn test, confirm green. Update §7 in _response.md if output changed. Return what changed + final test status.`,
      {label: `fix:${p.domain}`, phase: 'Fix', schema: FIX_SCHEMA, effort: 'low'}
    )
  }
)

return {
  problems: PROBLEMS.map((p,i) => ({
    uuid: p.uuid,
    title: p.title,
    domain: p.domain,
    gen: results[i] ? 'done' : 'failed',
  }))
}
