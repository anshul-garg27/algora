export const meta = {
  name: 'gen-java-coding-duo-v2',
  description: 'Regenerate 2 Java coding sessions with OPUS using the FIXED full prompts: Largest Rectangle (interview_java, 64K prompt) + Tree Diameter (assessment_java, 4.8K prompt)',
  phases: [
    {title: 'Generate', detail: 'Read fixed prompt, solve, compile+test with javac/java'},
    {title: 'Verify', detail: 'Adversarial review: correctness + prompt-adherence'},
  ],
}

const ROOT = '/Users/gbang/Downloads/algora_java'
const JBIN = '/opt/homebrew/opt/openjdk@17/bin'

const PROBLEMS = [
  {
    uuid: 'java-coding-histogram-001',
    mode: 'interview_java',
    promptFile: `${ROOT}/interview_prompt_java.md`,
    title: 'Largest Rectangle in Histogram',
    problem: 'LeetCode 84: Given an array of integers heights representing histogram bar heights where each bar width is 1, return the area of the largest rectangle in the histogram.\n\nExample: heights = [2,1,5,6,2,3] -> Output: 10 (rectangle height 5, width 2).\n\nConstraints: 1 <= heights.length <= 10^5, 0 <= heights[i] <= 10^4',
  },
  {
    uuid: 'java-coding-treediameter-001',
    mode: 'assessment_java',
    promptFile: `${ROOT}/assessment_prompt_java.md`,
    title: 'Diameter of Binary Tree',
    problem: 'Calculate the diameter of a binary tree: the length (in edges) of the longest path between any two nodes (may or may not pass through the root).\n\nExample: tree with root 1, children 2 and 3, and 2 has children 4 and 5 -> Output: 3 (path 4->2->1->3).\n\nConstraints: 1 <= number of nodes <= 10^4',
  },
]

const GEN_SCHEMA = {
  type: 'object',
  required: ['uuid','title','mode','passed','testCount','responseSizeChars','sections','summary'],
  properties: {
    uuid: {type:'string'}, title:{type:'string'}, mode:{type:'string'},
    passed:{type:'boolean', description:'all test cases pass after javac+java'},
    testCount:{type:'number'},
    responseSizeChars:{type:'number', description:'size of _response.md written'},
    sections:{type:'number', description:'how many numbered sections the response has (interview=11, assessment=5)'},
    summary:{type:'string'},
  }
}

const VERIFY_SCHEMA = {
  type: 'object',
  required: ['verdict','correct','followsPromptStructure','findings'],
  properties: {
    verdict:{type:'string', enum:['SHIP','FIX-FIRST']},
    correct:{type:'boolean', description:'is the algorithm actually correct'},
    followsPromptStructure:{type:'boolean', description:'does response follow the mode prompt structure (interview=11 sections opener-first, assessment=5 steps)'},
    findings:{type:'array', items:{type:'object', required:['severity','problem'], properties:{
      severity:{type:'string', enum:['BLOCKER','MAJOR','MINOR']},
      problem:{type:'string'}, fix:{type:'string'},
    }}}
  }
}

phase('Generate')

const results = await pipeline(
  PROBLEMS,

  // STAGE 1: generate using the FIXED full prompt
  (p) => agent(
    `You are an expert coding-interview solver. Your system prompt for this task is in a file you MUST READ IN FULL FIRST:

  READ: ${p.promptFile}

That file (mode: ${p.mode}) defines the EXACT output structure, code-quality standards, and section ordering you must follow. Obey it precisely — it is the source of truth, not any summary.

PROBLEM: ${p.title}
${p.problem}

ENVIRONMENT (Java 17):
- Workspace: ${ROOT}/workspace/${p.uuid}/ (create it).
- java/javac are NOT on PATH. Use full paths: ${JBIN}/javac and ${JBIN}/java
- Write Solution.java (public class name MUST match filename). Write a Main.java test harness with the example + edge cases (single node/bar, empty, skewed, large stress within constraints, path-not-through-root for the tree).
- Compile: ${JBIN}/javac *.java   Run: ${JBIN}/java Main
- Fix the CODE until ALL test cases pass. Watch int overflow (use long for area accumulation if needed).

DELIVERABLE: Write the FULL response (every section the ${p.mode} prompt mandates — interview_java = 11 sections with the speakable opener 1-5 BEFORE code; assessment_java = the 5-step protocol ending in the STEP 5 block) to:
  ${ROOT}/workspace/${p.uuid}/_response.md
Code blocks tagged \`\`\`java. The presented code must match the verified Solution.java.

Return the structured summary (responseSizeChars = actual char count of _response.md you wrote, sections = number of numbered sections).`,
    {label: `gen:${p.uuid.split('-')[2]}`, phase: 'Generate', schema: GEN_SCHEMA, model: 'opus'}
  ),

  // STAGE 2: adversarial verify (correctness + did it actually follow the fixed prompt)
  (gen, p) => agent(
    `Adversarially verify a Java coding-interview solution. Be skeptical.

Workspace: ${ROOT}/workspace/${p.uuid}/  (Solution.java, Main.java, _response.md)
Mode prompt (the structure it was SUPPOSED to follow): ${p.promptFile}

Recompile and run yourself to confirm correctness:
  cd ${ROOT}/workspace/${p.uuid} && ${JBIN}/javac *.java && ${JBIN}/java Main

Check and report:
1. CORRECTNESS: is the algorithm actually right? Try to find an input that breaks it (overflow, empty, single element, all-equal, skewed tree, path not through root). Does it match the claimed complexity?
2. PROMPT ADHERENCE: open _response.md. For interview_java it MUST have all 11 sections with the speakable opener (Sections 1-5: Understanding, On-Paper, Pattern, Approach-Landscape, Deep-Dive) BEFORE the code, then 6-11. For assessment_java it MUST have the 5-step protocol ending with the STEP 5 block (Core Logic, Complexity, Code, Edge Cases Conquered). Flag if sections are missing or out of order.
3. JAVA QUALITY: public class Solution, explicit types, camelCase, edge cases at top, \`\`\`java fences, code in response matches Solution.java.

Return verdict SHIP / FIX-FIRST, correct (bool), followsPromptStructure (bool), and findings.`,
    {label: `verify:${p.uuid.split('-')[2]}`, phase: 'Verify', schema: VERIFY_SCHEMA, model: 'opus'}
  ),
)

return {
  results: PROBLEMS.map((p,i) => ({
    uuid: p.uuid, title: p.title, mode: p.mode,
    gen: results[i] ? 'done' : 'failed',
  }))
}
