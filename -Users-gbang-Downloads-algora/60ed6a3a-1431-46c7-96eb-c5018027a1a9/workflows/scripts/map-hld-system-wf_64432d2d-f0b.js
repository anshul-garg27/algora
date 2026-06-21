export const meta = {
  name: 'map-hld-system',
  description: 'Map the HLD generation system: prompt section structure, session-builder recipe, frontend conversation-JSON contract for hld mode, and which HLD topics already exist',
  phases: [{ title: 'Map HLD' }],
}

const ROOT = '/Users/gbang/Downloads/algora'

const PROMPT_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['sections','diagramsExpected','capacityEstimation','mustHaves','toneAndLength'],
  properties: {
    sections: { type: 'array', items: { type: 'object', additionalProperties: false,
      required: ['title','summary'], properties: { title: {type:'string'}, summary: {type:'string'} } },
      description: 'Ordered list of the top-level sections an HLD answer must contain, with a one-line summary each' },
    diagramsExpected: { type: 'string', description: 'What mermaid/diagrams are expected (types, how many, where)' },
    capacityEstimation: { type: 'string', description: 'How back-of-envelope/capacity estimation is expected to be presented' },
    mustHaves: { type: 'array', items: {type:'string'}, description: 'Non-negotiable elements (API design, data model, scaling, bottlenecks, tradeoffs, etc.)' },
    toneAndLength: { type: 'string', description: 'Expected tone, length, and whether any code/pseudocode appears' },
  },
}

const BUILDER_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['recipeSteps','fileOrWorkspaceNeeds','jsonContract','gotchas'],
  properties: {
    recipeSteps: { type: 'array', items: {type:'string'} },
    fileOrWorkspaceNeeds: { type: 'string', description: 'Does HLD generation write any workspace files / run anything, or is it markdown-only?' },
    jsonContract: { type: 'string', description: 'Exact conversation-JSON contract the builder documents for hld mode (session_id form, mode, transcript/messages/blocks shape, any tool blocks)' },
    gotchas: { type: 'array', items: {type:'string'} },
  },
}

const FRONTEND_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['hldModeRendering','conversationJsonShape','toolBlocksUsed','diagramRendering','differencesFromLld'],
  properties: {
    hldModeRendering: { type: 'string', description: 'How mode==="hld" is detected and rendered (vs lld/other)' },
    conversationJsonShape: { type: 'string', description: 'The exact JSON shape a saved hld conversation needs (top-level keys, messages[], transcript[], blocks[])' },
    toolBlocksUsed: { type: 'string', description: 'Does hld mode use any write_file/run_command tool blocks, or is it a single text/markdown block? What does a real fresh hld JSON contain?' },
    diagramRendering: { type: 'string', description: 'How mermaid diagrams render in hld mode' },
    differencesFromLld: { type: 'string', description: 'Key rendering differences between hld and lld mode (e.g. no inline code viewer)' },
  },
}

const EXISTING_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['freshHldExample','count','topicsPresent'],
  properties: {
    freshHldExample: { type: 'string', description: 'The session_id + filename of one FRESH (>=2026-06-19) hld conversation to use as a structural template, and a description of its actual block structure' },
    count: { type: 'number' },
    topicsPresent: { type: 'array', items: {type:'string'} },
  },
}

phase('Map HLD')

const [prompt, builder, frontend, existing] = await parallel([
  () => agent(
    `Read ${ROOT}/system_design_prompt.md IN FULL (it's ~53KB). This is the production HLD (high-level system design) prompt. Extract the EXACT ordered section structure an HLD answer must produce (each section title + one-line summary), what diagrams are expected (mermaid types, how many, where), how capacity/back-of-envelope estimation should be presented, the non-negotiable must-have elements (API design, data model, scaling strategy, bottlenecks, trade-offs, etc.), and the expected tone/length and whether any code/pseudocode appears. Be precise and complete — quote section headings verbatim where they matter.`,
    { label: 'read:hld-prompt', phase: 'Map HLD', schema: PROMPT_SCHEMA }
  ),
  () => agent(
    `Read ${ROOT}/agent_prompts/hld_session_builder.md IN FULL. This is the agent recipe for building ONE complete HLD interview session. Extract: the end-to-end recipe steps in order; whether HLD generation writes any workspace files or runs any commands (or is markdown-only); the EXACT conversation-JSON contract it documents for hld mode (session_id form with :hld, mode field, the messages[]/transcript[]/blocks[] shape, and whether any tool blocks like write_file are used); and every CRITICAL/gotcha note. If the file references old /Users/anshullkgarg/... paths, note that the real project root is ${ROOT}. Quote field names verbatim.`,
    { label: 'read:hld-builder', phase: 'Map HLD', schema: BUILDER_SCHEMA }
  ),
  () => agent(
    `Read ${ROOT}/frontend/app.js and ${ROOT}/frontend/styles.css to determine how mode==="hld" conversations are RENDERED and what JSON shape they need. Specifically: (1) how the frontend detects/renders hld mode vs lld vs others; (2) the exact conversation-JSON shape a saved hld conversation must have (top-level keys, messages[], transcript[], blocks[] with their "k"/discriminant); (3) does hld mode use any write_file/run_command tool blocks or is the answer a single markdown text block? (4) how mermaid diagrams render in hld mode; (5) key rendering differences from lld mode (e.g. lld has the inline tabbed code viewer — does hld have anything special or is it just rendered markdown?). Quote the relevant code paths/field names.`,
    { label: 'read:frontend-hld', phase: 'Map HLD', schema: FRONTEND_SCHEMA }
  ),
  () => agent(
    `Survey ${ROOT}/data/conversations/*_hld.json. (1) Find ONE FRESH example — a file whose updated_at >= 1718755200 is NOT reliable; instead just pick a recent-looking, well-formed hld conversation — and describe its ACTUAL structure: top-level keys, how many messages, the transcript[1].blocks[] structure (how many text blocks, any tool blocks, where the markdown lives, whether mermaid is embedded in the markdown). Give its session_id and filename. (2) Count total *_hld.json files. (3) List the distinct HLD topics present (from titles). Use python/json via Bash for efficiency; do not dump whole huge files. This tells me the real on-disk template to match when I assemble new HLD JSONs.`,
    { label: 'survey:existing-hld', phase: 'Map HLD', schema: EXISTING_SCHEMA }
  ),
])

return { prompt, builder, frontend, existing }
