export const meta = {
  name: 'gen-java-coding-duo',
  description: 'Generate 2 Java coding interview sessions: Largest Rectangle in Histogram (interview_java) + Tree Diameter (assessment_java)',
  phases: [
    {title: 'Generate', detail: 'Code solution, verify with test cases'},
  ],
}

const ROOT = '/Users/gbang/Downloads/algora_java'

const PROBLEMS = [
  {
    uuid: 'java-coding-histogram-001',
    mode: 'interview_java',
    title: 'Largest Rectangle in Histogram',
    problem: 'LeetCode 84: Given an array of integers heights representing the histogram bar heights where the width of each bar is 1, return the area of the largest rectangle in the histogram.\n\nExample: heights = [2,1,5,6,2,3] → Output: 10 (the rectangle with height 5 and width 2)\n\nConstraints: 1 <= heights.length <= 10^5, 0 <= heights[i] <= 10^4',
  },
  {
    uuid: 'java-coding-treediameter-001',
    mode: 'assessment_java',
    title: 'Diameter of Binary Tree',
    problem: 'Calculate the diameter of a binary tree. The diameter is the length of the longest path between any two nodes (may or may not pass through root). The length is measured in number of edges.\n\nExample: Tree [1,2,3,4,5] (where 2,3 are children of 1, and 4,5 are children of 2) → Output: 3 (path 4→2→1→3)\n\nConstraints: 1 <= number of nodes <= 10^4',
  },
]

const GEN_SCHEMA = {
  type: 'object',
  required: ['uuid','title','mode','passed','summary'],
  properties: {
    uuid: {type: 'string'},
    title: {type: 'string'},
    mode: {type: 'string'},
    passed: {type: 'boolean', description: 'did test cases pass'},
    summary: {type: 'string'},
  }
}

phase('Generate')

const results = await pipeline(
  PROBLEMS,
  
  (p) => agent(
    `You are solving a coding interview problem in Java 17+ for mode: ${p.mode}.

PROBLEM: ${p.title}
${p.problem}

MODE-SPECIFIC GUIDANCE:
${p.mode === 'interview_java' ? `
INTERVIEW MODE (11 sections):
Write FULL opener (Sections 1-5) FIRST before any code:
1. Problem Understanding (restate, constraints, clarify)
2. Understand On Paper (diagrams, trace small example)
3. Pattern Recognition (tag: stack/DP/tree/etc + why)
4. Approach Landscape (table: brute vs optimal, pick one)
5. Optimal Approach Deep Dive (detailed walkthrough)

THEN verify internally (write Java code, test), THEN write Sections 6-11:
6. Solution (verified Java code, public class Solution)
7. Code Walkthrough (line-by-line teaching)
8. Complexity Analysis (Time/Space Big-O)
9. Optimize Further (can we do better?)
10. Edge Cases Handled
11. Follow-up Probes

Java format: public class Solution { public ReturnType methodName(...) { ... } }
Use descriptive names, edge cases at TOP, comments for non-obvious logic.
` : `
ASSESSMENT MODE (fast, 5-step):
1. PROBLEM ANALYSIS (inputs, outputs, constraints → complexity target)
2. STRATEGY (brute force bottleneck, optimal approach, Big-O)
3. CODE (write Java, save to file, test samples + edges)
4. RIGOROUS TESTING (run, fix until green)
5. FINAL ANSWER: Core Logic (2 sentences), Complexity, Code (verified java block), Edge Cases Conquered

Quick, correct, complete. Java format: public class Solution { ... }
`}

Write the solution following the mode structure. Use Write tool to save code, Bash to test. Return structured summary with pass/fail status.

Workspace: ${ROOT}/workspace/${p.uuid}/ (create if needed, write Solution.java there, test it).

Java template:
import java.util.*;

public class Solution {
    public ReturnType methodName(ParamType param) {
        // edge cases
        if (param == null) return default;
        
        // core logic
        ...
        
        return result;
    }
}

Return: {uuid, title, mode, passed: boolean, summary: string}`,
    {label: `code:${p.title.split(' ').slice(0,2).join('-')}`, phase: 'Generate', schema: GEN_SCHEMA, effort: 'medium'}
  )
)

return {solutions: results.map(r => r || {failed: true})}
