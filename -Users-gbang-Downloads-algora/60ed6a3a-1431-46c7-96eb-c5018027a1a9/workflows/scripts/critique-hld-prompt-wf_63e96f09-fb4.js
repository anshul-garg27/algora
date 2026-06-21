export const meta = {
  name: 'critique-hld-prompt',
  description: 'Critically evaluate the HLD system_design_prompt.md for improvements — including whether clarifying questions should come BEFORE functional/non-functional requirements — via 4 independent reviewer lenses, then synthesize a prioritized recommendation.',
  phases: [
    { title: 'Critique' },
    { title: 'Synthesize' },
  ],
}

const ROOT = '/Users/gbang/Downloads/algora'
const PROMPT = `${ROOT}/system_design_prompt.md`
const BUILDER = `${ROOT}/agent_prompts/hld_session_builder.md`
const SAMPLE1 = `${ROOT}/data/conversations/84929a55-c466-4e23-af3a-581f842f3fdd_hld.json`
const SAMPLE2 = `${ROOT}/data/conversations/94edbaa4-9115-492e-bd64-45c7dc88343d_hld.json`

const FINDING_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['lens','orderingVerdict','findings'],
  properties: {
    lens: { type: 'string' },
    orderingVerdict: { type: 'string', description: 'Verdict ONLY on: should clarifying questions come BEFORE functional+non-functional requirements? One of CLARIFY-FIRST, REQUIREMENTS-FIRST, HYBRID, NO-STRONG-OPINION, plus a 2-3 sentence justification grounded in real senior-interview practice.' },
    findings: { type: 'array', items: { type: 'object', additionalProperties: false,
      required: ['priority','area','problem','suggestedChange'],
      properties: {
        priority: { type: 'string', enum: ['HIGH','MEDIUM','LOW'] },
        area: { type: 'string' },
        problem: { type: 'string' },
        suggestedChange: { type: 'string', description: 'concrete specific edit to the prompt' },
      } } },
  },
}

const SYNTH_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['orderingRecommendation','orderingRationale','topRecommendations','minorRecommendations','overallAssessment'],
  properties: {
    orderingRecommendation: { type: 'string', enum: ['CLARIFY-FIRST','REQUIREMENTS-FIRST','HYBRID','KEEP-AS-IS'] },
    orderingRationale: { type: 'string' },
    topRecommendations: { type: 'array', items: { type: 'object', additionalProperties: false,
      required: ['title','why','concreteEdit'],
      properties: { title:{type:'string'}, why:{type:'string'}, concreteEdit:{type:'string'} } } },
    minorRecommendations: { type: 'array', items: { type: 'string' } },
    overallAssessment: { type: 'string' },
  },
}

phase('Critique')

const LENSES = [
  {
    key: 'interview-realism',
    prompt: `You are a senior FAANG system-design interviewer (ex-Amazon/Google bar-raiser). Read the HLD prompt at ${PROMPT} IN FULL, focusing on section 1 (Requirements) and section 2 (Clarifying Questions and Assumptions) and the opener.

CENTRAL QUESTION (answer decisively in orderingVerdict): in a REAL senior system-design interview, should the candidate ask CLARIFYING QUESTIONS to scope the problem BEFORE stating functional + non-functional requirements, or state requirements first? Consider: you cannot write correct functional requirements without first knowing scope (argues clarify-first); BUT a senior candidate states decisive assumptions rather than asking a junior-sounding laundry list (argues requirements-as-confirmed-assumptions). Give the verdict that reflects what actually earns strong-hire at the senior bar, and the concrete reordering it implies for THIS prompt. Then list other interview-realism problems with the prompt.`,
  },
  {
    key: 'completeness-gaps',
    prompt: `You are a distributed-systems architect. Read the HLD prompt at ${PROMPT} and the builder at ${BUILDER} IN FULL. Evaluate COMPLETENESS across all 11 sections: what important system-design concerns are missing, under-specified, or could be probed deeper? Consider back-pressure and load shedding, observability/tracing/metrics, API versioning and pagination, rate-limiting/quotas, data lifecycle/TTL/archival, schema migration, idempotency depth, multi-region write topology, CAP/PACELC framing, security depth (authz model, PII), cost modeling rigor, and capacity-estimation rigor. For orderingVerdict, also give your take on clarify-vs-requirements ordering. List concrete gaps with concrete additions.`,
  },
  {
    key: 'framework-comparison',
    prompt: `You are an expert on system-design interview frameworks (Hello Interview Delivery framework, Alex Xu 4-step, ByteByteGo). Read the HLD prompt at ${PROMPT} IN FULL. Compare its section 1 to 11 structure to those canonical frameworks: where does it MATCH, where does it DEVIATE, and is each deviation an improvement or a risk? Specifically assess the ordering of Requirements vs Clarifying Questions vs Core Entities vs API vs High-Level Design vs Deep Dives. Note: Hello Interview folds clarifying INTO requirements and puts functional requirements first; Alex Xu step 1 is understand-the-problem-and-establish-design-scope via questions FIRST. Give a clear orderingVerdict grounded in these frameworks. List where our prompt should adopt or reject framework conventions.`,
  },
  {
    key: 'empirical-output',
    prompt: `You are a critical reviewer checking whether a prompt actually PRODUCES good output. Read the HLD prompt at ${PROMPT} (skim for structure), then read the FULL markdown answer inside two freshly-generated sessions it produced: extract transcript[1].blocks[0].md from ${SAMPLE1} (Flash Sale) and ${SAMPLE2} (Web Crawler) using python/json. Judge EMPIRICALLY: does the section-1-then-section-2 ordering read naturally in the actual output, or is it awkward (e.g. requirements stated, THEN questions that should have preceded them)? Are the clarifying questions in section 2 actually scoping questions that logically belong before section 1 requirements? Are there repetitive/bloated sections, weak deep dives, or hand-waved capacity numbers in practice? For orderingVerdict, base it on what you actually observe in these two outputs. List concrete evidence-backed problems and quote the output.`,
  },
]

const critiques = await parallel(LENSES.map(L => () =>
  agent(L.prompt, { label: `critic:${L.key}`, phase: 'Critique', schema: FINDING_SCHEMA, agentType: 'general-purpose' })
))

phase('Synthesize')

const valid = critiques.filter(Boolean)
const synthesis = await agent(
  `You are synthesizing 4 independent expert critiques of an HLD (high-level system design) interview prompt into ONE actionable recommendation set.

Here are the 4 critiques (each has a lens, an orderingVerdict on clarifying-questions-before-requirements, and a findings list):
${JSON.stringify(valid, null, 2)}

Produce:
1. orderingRecommendation + orderingRationale: a DECISIVE synthesized verdict on whether clarifying questions should come before functional+non-functional requirements. Weigh the 4 reviewers. The prompt owner specifically believes clarifying should come first — evaluate that honestly (agree or push back with reasons), and give the CONCRETE reordering/edit it implies (e.g. swap section 1 and 2, or keep order but add a brief scoping step before section 1).
2. topRecommendations: the highest-value improvements, deduped across reviewers, each with a concrete edit, ranked by impact.
3. minorRecommendations: smaller polish items.
4. overallAssessment: honest bottom line — is this prompt already strong or does it need real work?

Be specific and concrete. Do NOT pad. If reviewers disagree, say so and take a position.`,
  { label: 'synthesize', phase: 'Synthesize', schema: SYNTH_SCHEMA, agentType: 'general-purpose' }
)

return synthesis
