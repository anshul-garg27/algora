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
/Users/gbang/Downloads/algora/system_design_prompt.md
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

### Required sections (all 11)

**The section structure, exact headings, and per-section requirements are defined EXCLUSIVELY by `system_design_prompt.md` (its `<output_format>` block, §1 through §11). Read that file and follow it VERBATIM — do NOT paraphrase, re-label, or re-derive the sections here.** This builder used to embed its own mini-spec; that drifted out of sync with the production prompt (wrong section names, wrong card structure, an uncapped question count) and produced weaker artifacts. The production prompt is the single source of truth.

Two things to be especially careful to carry over from the production prompt (they were previously gotten wrong here):
- §1 is **"Scope, Requirements & Assumptions"** and opens with the **🔒 Scope lock** — 2-4 architecture-forking questions stated as vetoable assumptions FIRST, then functional requirements derived from them, then provisional NFR targets. §2 is the **residual forks** ("what changes if I'm wrong"), NOT a fresh 6-10 question interrogation. Cap clarifying questions at the 2-4 that actually fork the design; everything else is a stated assumption.
- §4 is **"Core Entities"** (a 1-2 minute scaffold, not a field-level data model — that lives in §7), §6 is **"High-Level Design"**, and §7 storage decision cards are **5-part** (what it is / why this / what we rejected & why / trade-off accepted / 🗣️ how to say it) — not 3-part.

Everything else — capacity rigor, the Bad→Good→Great deep dives, RPO/RTO, the trade-off ledger, the 7 interviewer-question domains — follow §1–§11 of `system_design_prompt.md` as written.

---

## Step 3 — Write the conversation JSON

File path:
```
/Users/gbang/Downloads/algora/data/conversations/<slug>.json
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

out = pathlib.Path('/Users/gbang/Downloads/algora/data/conversations') / f'{slug}.json'
out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"Written: {out}")
print(f"Open at: https://localhost:8002/?s={session_id}")
```

---

## Step 4 — Verify

```bash
cd /Users/gbang/Downloads/algora
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

- [ ] All 11 sections present and fully expanded, with the EXACT headings from `system_design_prompt.md` (§1 "Scope, Requirements & Assumptions", §4 "Core Entities", §6 "High-Level Design" — not the old mislabels)
- [ ] §1 opens with the 🔒 Scope lock (2-4 forking questions as vetoable assumptions) FIRST, then functional requirements derived from them, then provisional NFR targets
- [ ] §2 is the residual "forks behind my assumptions" (what changes if I'm wrong) — NOT a fresh question round, and re-asks NOTHING already locked in §1; clarifying questions capped at the 2-4 that fork the design
- [ ] §3: full derivation chains, all terms glossed, capacity computed with run_python
- [ ] §4: 1-2 minute entity scaffold (analogy + interviewer probe per entity) — NOT a field-level data model
- [ ] §5: request/response fields with WHY per endpoint + idempotency + object-level authz + versioning & cursor pagination noted once
- [ ] §6: every above-the-line requirement gets its own `flowchart TD` diagram + 5-column decision table + numbered step narration
- [ ] §7: 5-part storage decision cards + PART D data lifecycle for the largest table
- [ ] §8: Bad→Good→Great tiers with mechanism diagrams + decision math + failure matrix (fold single-tier stubs away)
- [ ] §9: RPO/RTO defined in plain English before use; back-pressure, observability (golden signals + trace propagation), rate-limiting covered
- [ ] §10: trade-off cards with "when this reverses" + a one-line CAP/PACELC framing
- [ ] §11: all 7 question domains + 60-second summary template
- [ ] Mermaid safety: every diagram is `flowchart TD` for multi-path; NO breaking chars — parens, colons, semicolons, slashes, quotes, angle/curly braces — inside any node or edge label
- [ ] Conversation JSON exists at `data/conversations/<slug>.json`; top-level `messages` is `[]`; the single assistant block is `{"k":"text","md":...}` (no tool blocks)
- [ ] `session_id` inside JSON uses `:hld` (colon); slug filename uses `_hld` (underscore)
- [ ] Markdown in the text block is > 20,000 characters (must be thorough)
