export const meta = {
  name: 'map-lld-system',
  description: 'Map the LLD problem-generation system: recipe, prompt structure, frontend contract, serving, existing problems, and the Uber prep target',
  phases: [
    { title: 'Map system' },
  ],
}

const ROOT = '/Users/gbang/Downloads/algora'

const RECIPE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['fileLayout', 'jsonToolBlockContract', 'sectionStructure', 'qualityRequirements', 'recipeSteps', 'gotchas'],
  properties: {
    fileLayout: { type: 'array', items: { type: 'string' }, description: 'Canonical source file layout for a generated LLD workspace' },
    jsonToolBlockContract: { type: 'string', description: 'Exact JSON contract for write_file / run_command tool blocks (field names, bare paths, etc.)' },
    sectionStructure: { type: 'array', items: { type: 'string' }, description: 'The markdown section structure (§1..§9 titles)' },
    qualityRequirements: { type: 'array', items: { type: 'string' }, description: 'Non-negotiable quality requirements the builder enforces' },
    recipeSteps: { type: 'array', items: { type: 'string' }, description: 'End-to-end generation steps in order' },
    gotchas: { type: 'array', items: { type: 'string' }, description: 'Pitfalls / CRITICAL notes called out in the prompt' },
  },
}

const PROMPT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['sections', 'concurrencyRequirements', 'extensibilityRequirements', 'patternsPolicy'],
  properties: {
    sections: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['num', 'title', 'summary'], properties: { num: { type: 'string' }, title: { type: 'string' }, summary: { type: 'string' } } } },
    concurrencyRequirements: { type: 'string' },
    extensibilityRequirements: { type: 'string' },
    patternsPolicy: { type: 'string', description: 'The "earn your patterns" / design-pattern policy' },
  },
}

const PROBLEMS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['count', 'problems'],
  properties: {
    count: { type: 'number' },
    problems: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['slug', 'title', 'concurrencyPattern'], properties: { slug: { type: 'string' }, title: { type: 'string' }, concurrencyPattern: { type: 'string', description: 'The distinct concurrency/threading pattern this problem demonstrates, if discernible from the JSON, else "unknown"' } } } },
  },
}

const FRONTEND_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['toolBlockContract', 'viewerBehavior', 'conversationJsonShape', 'modeHandling'],
  properties: {
    toolBlockContract: { type: 'string' },
    viewerBehavior: { type: 'string' },
    conversationJsonShape: { type: 'string' },
    modeHandling: { type: 'string', description: 'How "lld" mode is detected and rendered differently' },
  },
}

const SERVING_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['convDir', 'slugFormat', 'workspaceDir', 'howServed', 'sessionIdToFile'],
  properties: {
    convDir: { type: 'string' },
    slugFormat: { type: 'string' },
    workspaceDir: { type: 'string' },
    howServed: { type: 'string', description: 'How the backend loads/lists conversations for the frontend' },
    sessionIdToFile: { type: 'string', description: 'How a session_id maps to a conversation filename' },
  },
}

const PREP_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['structure', 'lldRelated', 'relationToConversations'],
  properties: {
    structure: { type: 'string', description: 'Directory tree / organization of uber-interviews/prep' },
    lldRelated: { type: 'string', description: 'What LLD material exists there' },
    relationToConversations: { type: 'string', description: 'Whether/how it relates to data/conversations LLD sessions' },
  },
}

phase('Map system')

const [recipe, prompt, problems, frontend, serving, prep] = await parallel([
  () => agent(
    `Read ${ROOT}/agent_prompts/lld_session_builder.md in full. This is the agent prompt that builds one complete LLD interview session. Extract the EXACT, current recipe a builder must follow: canonical source-file layout, the precise JSON tool-block contract (write_file vs run_command — exact field names, whether paths are bare/relative, content handling), the markdown section structure (§1..§9 titles), every non-negotiable quality requirement, the end-to-end generation steps in order, and any CRITICAL/gotcha notes. Be precise and complete — quote field names verbatim where they matter.`,
    { label: 'read:session-builder', phase: 'Map system', schema: RECIPE_SCHEMA }
  ),
  () => agent(
    `Read ${ROOT}/lld_prompt.md (large file ~115KB). Extract the §1..§9 section structure (number, title, one-line summary each), the CONCURRENCY requirements/vocabulary, the §9 extensibility/"interviewer twists" requirements, and the design-pattern policy (the "EARN YOUR PATTERNS" rule). Focus on what a generated session MUST contain to meet this prompt's bar.`,
    { label: 'read:lld-prompt', phase: 'Map system', schema: PROMPT_SCHEMA }
  ),
  () => agent(
    `Survey every LLD conversation in ${ROOT}/data/conversations/ whose filename ends with "_lld.json". For each, extract the "title" field and the slug (filename without .json). Also, where cheaply discernible, identify the distinct concurrency/threading pattern it demonstrates (look at the markdown body or code for terms like two-phase commit, per-key lock, read-write lock, lock ordering, condition variable, optimistic/pessimistic, idempotent dedup, etc.); if not discernible, use "unknown". Return the total count and the full list. Use grep/jq-style efficiency — do not read entire huge files line by line; extract just the title and skim for the pattern. List ALL of them, do not truncate.`,
    { label: 'survey:existing-lld', phase: 'Map system', schema: PROBLEMS_SCHEMA, agentType: 'Explore' }
  ),
  () => agent(
    `Read ${ROOT}/frontend/app.js and ${ROOT}/frontend/styles.css (and ${ROOT}/frontend/markdown.js if present). Determine: (1) the exact JSON shape of a tool block the frontend expects inside a saved assistant turn (the write_file path/content and run_command command contract), (2) how the inline tabbed "Complete Code Implementation" full-code viewer works and when it shows, (3) the full conversation JSON shape the frontend loads (messages[] + transcript[] + blocks[]), (4) how "lld" mode is detected and rendered differently from other modes. Quote key field names.`,
    { label: 'read:frontend', phase: 'Map system', schema: FRONTEND_SCHEMA }
  ),
  () => agent(
    `Read ${ROOT}/backend/config.py and any backend file that lists/serves conversations (e.g. ${ROOT}/backend/*.py — look for CONV_DIR, WORKSPACE_DIR, session_slug, and the route/function that loads a conversation by id or lists them). Determine: the conversations directory path, the workspace directory path, the exact slug/filename format for a session id, how the backend serves/lists conversation files to the frontend, and how a session_id maps to its on-disk filename.`,
    { label: 'read:backend-serving', phase: 'Map system', schema: SERVING_SCHEMA }
  ),
  () => agent(
    `Explore ${ROOT}/uber-interviews/ (especially uber-interviews/prep/). Describe its directory structure/organization, what LLD-related material lives there, and whether/how it relates to the LLD sessions in ${ROOT}/data/conversations/ (are they the same system, or is uber-interviews/prep separate study material?). Keep it factual.`,
    { label: 'explore:uber-prep', phase: 'Map system', schema: PREP_SCHEMA, agentType: 'Explore' }
  ),
])

return { recipe, prompt, problems, frontend, serving, prep }
