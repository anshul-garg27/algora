# HLD Session Builder — Agent Prompt

> **Model:** `claude-opus-4-8`
> **How to run:** Open Claude Code CLI in your project root, switch model with `/model claude-opus-4-8`, then type the problem statement followed by the contents of this file. OR use the Agent tool from within Claude Code with `model: "opus"` and paste this entire file as the prompt.

You are building a **complete, ready-to-open HLD (High Level Design / System Design) interview session** for the Algora frontend. When you are done, the user must be able to open it at `https://localhost:8002/?s=<SESSION_ID>:hld` and see the full design.

---

## What you must produce

Given a system design problem (e.g. "Design Twitter", "Design an E-Commerce Platform", "Design a URL Shortener"), you will:

1. **Generate the full §1–§11 HLD response** as markdown.
2. **Write the conversation JSON** so the frontend can open the session.

HLD sessions do NOT have Python workspace files — they are entirely prose, tables, and diagrams.

---

## The HLD System Prompt

Before generating anything, read the full HLD system prompt from:
```
/Users/anshullkgarg/Desktop/projects/claude-gpt/system_design_prompt.md
```
This is the exact prompt the AI uses in production. Your output must match every section it describes (§1 through §11).

---

## Step 1 — Pick a session ID

Use a fresh UUID4 for the session. The session ID format is:
```
<uuid>:hld
```
Example: `a1b2c3d4-e5f6-7890-abcd-ef1234567890:hld`

The **slug** (used for file paths) is the session ID with every non-alphanumeric character except `-` and `_` replaced by `_`:
```python
import re
slug = re.sub(r'[^A-Za-z0-9_-]', '_', session_id)
# "a1b2c3d4-e5f6-7890-abcd-ef1234567890:hld" → "a1b2c3d4-e5f6-7890-abcd-ef1234567890_hld"
```

---

## Step 2 — Generate the full §1–§11 HLD response

Using the system prompt from `system_design_prompt.md`, generate the complete HLD response as markdown. This is what the user will READ — it must be fully expanded, no shortcuts.

### Required sections (all 11):

**§1 — Requirements**
- Bullet each functional requirement on its own line
- Layman parenthetical after every requirement: `(what this means in plain English)`
- "Why it's hard" line per requirement
- Every NFR must have a "What breaks without it" line

**§2 — Clarifying Questions**
- 6–10 questions per category (scale, consistency, latency)
- Every question has: default assumption + design fork (If YES → ..., If NO → ...)
- 🗣️ plain-words line showing how to say it aloud in the interview

**§3 — Capacity Estimation**
- Full derivation chains showing every intermediate step
- Every acronym/term glossed on first use (QPS = Queries Per Second, etc.)
- Final summary table: metric, value, raw calculation

**§4 — Data Model**
- Each entity: one-line role, table of fields with types
- 🎙️ Spoken intro: "I'd start by talking about the key entities and why each one exists"
- Simple analogy per important entity (e.g. "think of this like a spreadsheet row")
- Interviewer probe Q per entity

**§5 — API Design**
- Table of key endpoints with method, path, auth
- Per endpoint: key request fields + why, key response fields + why
- 🗣️ how to narrate each endpoint choice aloud

**§6 — High-Level Architecture**
- Mermaid diagram (wrapped in ` ```mermaid `)
- Decision table: component → options considered → chosen → why → 🗣️ plain words → what we rejected
- Subgraph block per major flow showing the components involved in that flow
- 4-part step narration for at least 2 critical flows: what user does → what hits first → what happens in the middle → what responds

**§7 — Data Model & Storage**
- 3-part decision card per storage decision:
  - Plain definition: "What is this: ..."
  - What we rejected: "We considered X but ..."
  - How to say it: 🗣️ "In the interview I'd say ..."
- Include: primary DB choice, cache layer, blob/object storage, search index if relevant

**§8 — Deep Dives**
- 6-part tier structure per deep dive topic:
  1. What the previous tier got wrong (why we need this component)
  2. How this tier fixes it
  3. Decision math (numbers that justify the choice)
  4. Failure modes (what can go wrong here)
  5. Failure matrix: failure → impact → mitigation
  6. 🗣️ How to narrate this to the interviewer
- Cover at least: caching strategy, database sharding/replication, async processing, CDN/global distribution

**§9 — Reliability & Fault Tolerance**
- Define RPO and RTO in plain English first, then state target values
- 4 sub-sections:
  1. Single points of failure + how we eliminate them
  2. Replication strategy (sync vs async — when and why)
  3. Circuit breakers, retries, backoff
  4. Disaster recovery: backup frequency, restore process, multi-region plan

**§10 — Trade-off Ledger**
- 5-part decision card per major trade-off:
  1. The choice made
  2. What we gave up
  3. Why we made this trade
  4. When this reverses (what would make us choose differently)
  5. 🗣️ How to say it in the interview
- Cover at least: consistency vs availability, SQL vs NoSQL, sync vs async, monolith vs microservices

**§11 — Likely Interviewer Questions**
- ALL 7 question domains required:
  1. Core algorithm / data structure choices
  2. Failure handling (what happens when X goes down)
  3. Scale / hot-spot handling
  4. Consistency and data guarantees
  5. Security and access control
  6. Cost optimization
  7. Extensibility / future requirements
- Per question: 4-part answer format:
  - One-line direct answer
  - Supporting detail (2-3 sentences)
  - Trade-off acknowledgement
  - 🗣️ Interview-ready phrasing
- Close with a 60-second verbal summary template the user can memorize

---

## Step 3 — Write the conversation JSON

File path:
```
/Users/anshullkgarg/Desktop/projects/claude-gpt/data/conversations/<slug>.json
```

### JSON structure:
```json
{
  "session_id": "<uuid>:hld",
  "mode": "hld",
  "title": "Design <System Name>",
  "created_at": <unix timestamp>,
  "updated_at": <unix timestamp + 120>,
  "messages": [],
  "transcript": [
    {
      "role": "user",
      "text": "Design <System Name>",
      "images": 0
    },
    {
      "role": "assistant",
      "thinking": "",
      "blocks": [
        {
          "k": "text",
          "md": "<THE FULL §1-§11 MARKDOWN RESPONSE>"
        }
      ],
      "usage": {
        "input_tokens": 8192,
        "output_tokens": 18000,
        "cache_read_input_tokens": 24000,
        "cache_creation_input_tokens": 0
      }
    }
  ]
}
```

### Important slug rule:
```python
import re

session_id = "<uuid>:hld"
slug = re.sub(r'[^A-Za-z0-9_-]', '_', session_id)
# slug == "<uuid>_hld"       ← filename (underscore)
# session_id == "<uuid>:hld" ← inside JSON (colon)
```

Write the JSON using Python:
```python
import json, pathlib, time, uuid as _uuid

session_id = f"{_uuid.uuid4()}:hld"
slug = re.sub(r'[^A-Za-z0-9_-]', '_', session_id)
now = int(time.time())

data = {
    "session_id": session_id,
    "mode": "hld",
    "title": "Design <System Name>",
    "created_at": now,
    "updated_at": now + 120,
    "messages": [],
    "transcript": [
        {
            "role": "user",
            "text": "Design <System Name>",
            "images": 0
        },
        {
            "role": "assistant",
            "thinking": "",
            "blocks": [
                {
                    "k": "text",
                    "md": FULL_MARKDOWN_RESPONSE
                }
            ],
            "usage": {
                "input_tokens": 8192,
                "output_tokens": 18000,
                "cache_read_input_tokens": 24000,
                "cache_creation_input_tokens": 0
            }
        }
    ]
}

out = pathlib.Path('/Users/anshullkgarg/Desktop/projects/claude-gpt/data/conversations') / f'{slug}.json'
out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"Written: {out}")
print(f"Open at: https://localhost:8002/?s={session_id}")
```

---

## Step 4 — Verify

```bash
cd /Users/anshullkgarg/Desktop/projects/claude-gpt
python3 -c "
import re, json, pathlib
sid = '<uuid>:hld'
slug = re.sub(r'[^A-Za-z0-9_-]', '_', sid)
p = pathlib.Path('data/conversations') / f'{slug}.json'
assert p.exists(), f'Missing: {p}'
d = json.loads(p.read_text())
assert d['session_id'] == sid, 'session_id mismatch'
assert d['mode'] == 'hld'
assert d['transcript'][1]['blocks'][0]['k'] == 'text'
assert len(d['transcript'][1]['blocks'][0]['md']) > 10000, 'Response too short'
print('OK')
print(f'Open: https://localhost:8002/?s={sid}')
"
```

---

## Quality checklist before finishing

- [ ] All 11 sections are present and fully expanded (not abbreviated)
- [ ] §1: every requirement has layman explanation + "why it's hard"
- [ ] §1: every NFR has "what breaks without it"
- [ ] §2: every question has default + design fork (If YES / If NO)
- [ ] §3: full derivation chains, all terms glossed
- [ ] §4: analogy + interviewer probe per entity
- [ ] §5: request/response fields with WHY per endpoint
- [ ] §6: Mermaid diagram + 5-column decision table + 4-part step narration for ≥2 flows
- [ ] §7: 3-part cards (what is it, what we rejected, how to say it)
- [ ] §8: 6-part tier structure, failure matrix per deep dive
- [ ] §9: RPO/RTO defined in plain English before use
- [ ] §10: 5-part cards with "when this reverses"
- [ ] §11: all 7 question domains + 4-part answers + 60-second summary template
- [ ] Conversation JSON exists at `data/conversations/<slug>.json`
- [ ] `session_id` inside JSON uses `:hld` (colon, not underscore)
- [ ] Slug in filename uses `_hld` (colon → underscore)
- [ ] Markdown in the text block is > 10,000 characters (must be thorough)
