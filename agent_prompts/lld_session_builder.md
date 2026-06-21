# LLD Session Builder — Agent Prompt

> **Model:** `claude-opus-4-8`
> **How to run:** Open Claude Code CLI in your project root, switch model with `/model claude-opus-4-8`, then type the problem statement followed by the contents of this file. OR use the Agent tool from within Claude Code with `model: "opus"` and paste this entire file as the prompt.

You are building a **complete, ready-to-open LLD (Low Level Design) interview session** for the Algora frontend. When you are done, the user must be able to open it at `https://localhost:8002/?s=<SESSION_ID>:lld` and see the full design with working code.

---

## What you must produce

Given a problem statement (e.g. "Design a Parking Lot", "Design Splitwise"), you will:

1. **Write all Python files** into the workspace directory.
2. **Run `main.py`** and capture the actual output.
3. **Write the conversation JSON** so the frontend can open the session.

---

## The LLD System Prompt

Before generating anything, read the full LLD system prompt from:
```
/Users/anshullkgarg/Desktop/projects/claude-gpt/lld_prompt.md
```
This is the exact prompt the AI uses in production. Your output must match every section it describes (§1 through §9), including the ⏱️ 60-Minute Interview Plan at the top.

---

## Step 1 — Pick a session ID

Use a fresh UUID4 for the session. The session ID format is:
```
<uuid>:lld
```
Example: `a1b2c3d4-e5f6-7890-abcd-ef1234567890:lld`

The **slug** (used for file paths) is the session ID with every non-alphanumeric character except `-` and `_` replaced by `_`:
```python
import re
slug = re.sub(r'[^A-Za-z0-9_-]', '_', session_id)
# "a1b2c3d4-e5f6-7890-abcd-ef1234567890:lld" → "a1b2c3d4-e5f6-7890-abcd-ef1234567890_lld"
```

---

## Step 2 — Workspace structure

All Python files go in:
```
/Users/anshullkgarg/Desktop/projects/claude-gpt/workspace/<slug>/
```

**CANONICAL FILE LAYOUT — use these EXACT names. Never invent `helpers.py` / `utils.py` / `service.py`.** The service file is named after the DOMAIN (e.g. `locker_service.py`, `parking_service.py`, `booking_service.py`).

```
models.py             # domain entities, enums, value objects, custom exceptions (the "nouns")
strategies.py         # Strategy interfaces + concretes  (ONLY if §5 has a Strategy pattern)
gateways.py           # external-system interfaces: PaymentGateway, NotificationSink, Clock  (ONLY if §5 names one)
<domain>_service.py   # the orchestrator: clean single-threaded core + ThreadSafe subclass
main.py               # small __main__ demo driver: 3-5 cases with print(), NO test framework
tests/test_<domain>.py  # pytest suite: every public method, every error path, the concurrency case
tests/conftest.py     # adds the parent dir to sys.path so `from models import …` works in tests
```

Use ~3-6 files total. Python **3.11+** idioms: `list[Foo]`, `X | None` (not `Optional[X]`), no `from __future__ import annotations`.

### models.py must contain:
- All enums (`class X(IntEnum)` when ordering matters, else `class X(Enum)`)
- A single base exception (`<Domain>Error`) and one specific subclass per failure mode — **never mix in a bare `RuntimeError`/`Exception`/`ValueError`**
- All frozen dataclasses (`@dataclass(frozen=True)`) for value objects
- All mutable dataclasses for entities (the state-machine entity owns its own transition methods)

### <domain>_service.py must contain:
- The clean single-threaded service with a `@contextmanager _lock()` no-op hook
- The `ThreadSafe<Domain>Service(<Domain>Service)` subclass that overrides `_lock()` with the per-key `RLock` double-lock idiom
- Every public method from §6, fully implemented (NO `pass`/`...` bodies)
- **Imports at the TOP only** — never a mid-file `import threading`
- **No dead code** — every method is called from `main.py` or a test

### main.py must contain:
- `# Python 3.11+` as the first line
- A narrated demo: 3-5 cases with `print("Case N … -> OK")`, plain `assert X, message` (no `try/except False` antipattern)

### tests/test_<domain>.py must contain (pytest-shaped):
- One happy-path test per public operation; one test per typed exception path; a boundary test; an idempotency test if any method is safe-to-call-twice
- The **concurrency test** with STRICT assertions: `len(wins) == K`, `len(set(wins)) == K` (unique reservation ids), `len({w.compartment_id …}) == K` (unique resources — catches the silent collision bug), every loss is the typed error, and the count of in-RESERVED/OCCUPIED resources == K. Use `threading.Barrier` so all N threads hit the critical section at one instant. `pytest.raises(<TypedError>)` — never bare `Exception`.

---

## Step 3 — Generate the full §1–§9 LLD response

Using the system prompt from `lld_prompt.md`, generate the complete LLD response as markdown. This is what the user will READ in the frontend — it must be complete, not abbreviated. Match the CURRENT structure exactly:

- **⏱️ 60-Minute Interview Plan** — table (phase | what you do | mode) + the Mode A (whiteboard, no run) vs Mode B (coding env, run) note.
- **§1 Understanding the Problem & Clarifying Questions** — 1.1 plain-words restatement (coffee-chat tone), 1.2 **candidate-LED dialogue** (`**You:**` proposes an assumption/scope-cut + asks to confirm, `**Interviewer:**` ~70% agrees, italic reaction line), 1.3 Final Requirements (numbered functional + "Out of scope" list) + 💬 opener.
- **§2 Actors & Core Flows** — bulleted actors + 3-5 one-line happy-path flows. No diagram here.
- **§3 Core Entities (accept/reject)** — 3.1 noun walkthrough accepting/**rejecting** each candidate noun with a reason, 3.2 entity table (Entity | Responsibility | Key fields typed | Invariant) + enums block, 3.3 🎙️ spoken-intro paragraph that names the rejected nouns.
- **§3.5 API / System Interface** — the orchestrator's **public surface only**, as ONE typed contract table (`Method | Signature | Returns | Raises | Purpose`) with 3-7 rows + ONE 🎙️ spoken line on what the surface reveals. Signatures use Python 3.11+ hints and MUST match §4.1 / §4.2 diagram / §6 code one-for-one; `Raises` lists specific typed exceptions (never bare `Exception`). Every method traces to a §1.3 requirement and vice-versa. Comes BEFORE §4 (hellointerview ordering: Requirements → Entities → API → design).
- **§4 Class Design** — 4.1 per-class derivation: for EVERY accepted entity (orchestrator first, then each part — entities, value objects, AND strategy interfaces) the FOUR-block format (a) one-line role → (b) state-derivation table **+ a fenced state block** → (c) operations-derivation table **+ a COMPLETE fenced class block (state + constructor + every method from the table)** → (d) design-choice Q&A. ⚠️ Every class subsection MUST end with its own complete fenced class block — never a bare (c) table. Do not let the 2nd/3rd/4th class degrade to table-only after the orchestrator got the full treatment. Then 4.2 consolidated `classDiagram` (draw-vs-say split) + relationships + Pattern Map + 🎙️ box-by-box + **⚠️ PROACTIVE CONCURRENCY FLAG**.
- **§5 Design Patterns & Principles** — 5.1 Information Expert first, 5.2 applied patterns (1-3, each earned, with 💬 layman gloss), 5.3 SOLID tied to named classes, 5.4 EARN YOUR PATTERNS rule.
- **§5.5 Core Algorithms** — A key insight (insight + why-it-works + what-breaks-without-it), B per-operation pseudocode + STORY-driven 🎙️ scripts + a **DRY RUN** of the pipeline method with a state-change table, C data-structure choices (4 cols incl. rejected alternative), D tricky logic (🧠 Claim / 🔬 Proof / 🛠️ Fix), E ONE "❌ what I'd write WRONG first" anti-example, F narration-order table.
- **§6 Implementation** — **§6.0 Live Writing Order** (9 phases + 7 golden rules + TL;DR time table + mid-flight situations), then orchestrator SKELETON first, then each method in the 6-block format (role / core-logic bullets / edge-case bullets / code / reasoning PROSE / 🎙️+⚠️), ONE **Approach Comparison** for the trickiest helper, helpers written (not skipped), and a **Verification** subsection with full-lifecycle state-table dry runs.
- **§7 Putting It Together** — 7.1 `main.py` narrated demo output, 7.2 `tests/` pytest suite + the actual `pytest -q` output. Both green.
- **§8 Key Flow** — a `sequenceDiagram` of the most interesting flow + 🎙️ arrow-by-arrow narration + why-it-shows-the-design-is-good.
- **§9 Concurrency, Thread-Safety, Edge Cases & Extensibility** — 4-step verbal race walkthrough, **CONCURRENCY VOCABULARY table**, **CONCURRENCY FOLLOW-UP Q&A** (why RLock, why not global, deadlock, pessimistic vs optimistic, …), the clean→thread-safe diff (Part A hook+subclass, Part B exact modified method, Part C barrier test proof), edge-cases-handled list, **Extensibility** (level-calibration note + summary table + 2-3 TWIST walkthroughs with minimal code diffs), and the hardest follow-up Q&A (concurrency/distributed/scale — distinct from the twists).

**CRITICAL RULES FOR CODE IN §6:**
- NO `...` ANYWHERE. No abbreviations. No `# ... rest of implementation`.
- Every method body must be complete — every line, every real argument, every real error message, every real return value.
- Code blocks tagged ` ```python copy ` so the frontend renders a copy button.
- The §6 narration shows code method-by-method (teaching); the FULL files also ship as Write tool blocks (the frontend's LLD "Complete Code Implementation" tabbed viewer renders them from those `write_file` captures).

---

## Step 4 — Run main.py AND pytest, capture output

```bash
cd /Users/anshullkgarg/Desktop/projects/claude-gpt/workspace/<slug>
python3 main.py
python3 -m pytest -q
```

Capture the exact stdout from BOTH. The `main.py` output goes into the `tool_run` Bash block; the `pytest -q` output goes into the `tool_pytest` Bash block. Both must be green — if either errors, fix the CODE (not the test) and re-run before continuing.

---

## Step 5 — Write the conversation JSON

File path:
```
/Users/anshullkgarg/Desktop/projects/claude-gpt/data/conversations/<slug>.json
```

### Tool-block format (CRITICAL — the frontend keys off these exact names):
- File blocks: `"name": "write_file"`, `"input": {"path": "<bare path>", "content": "..."}`. The `path` is RELATIVE to the workspace (`models.py`, `tests/test_booking.py`) — **NOT** `workspace/<slug>/models.py`, and **NOT** `"Write"`/`"file_path"`. The frontend's LLD "Complete Code Implementation" tabbed viewer is built from these `write_file` blocks, so every file the candidate should see must be a `write_file` block.
- Run blocks: `"name": "run_command"`, `"input": {"command": "python3 main.py"}` — bare command, no `cd`.
- Also populate `messages` (Anthropic format) so follow-ups have context: a user message with the problem text and an assistant message whose single text block is the full §1–§9 markdown.

### JSON structure:
```json
{
  "session_id": "<uuid>:lld",
  "mode": "lld",
  "title": "Design a <Problem Name>",
  "created_at": <unix timestamp>,
  "updated_at": <unix timestamp + 180>,
  "messages": [
    {"role": "user", "content": [{"type": "text", "text": "<problem statement>"}]},
    {"role": "assistant", "content": [{"type": "text", "text": "<THE FULL §1-§9 MARKDOWN>"}]}
  ],
  "transcript": [
    {
      "role": "user",
      "text": "Design a <Problem Name>",
      "images": 0
    },
    {
      "role": "assistant",
      "thinking": "",
      "blocks": [
        {
          "k": "text",
          "md": "<THE FULL §1-§9 MARKDOWN RESPONSE>"
        },
        {
          "k": "tool",
          "id": "tool_write_0",
          "name": "write_file",
          "input": {
            "path": "models.py",
            "content": "<full file content>"
          },
          "output": "File created successfully.",
          "is_error": false
        },
        {
          "k": "tool",
          "id": "tool_write_1",
          "name": "write_file",
          "input": {
            "path": "<domain>_service.py",
            "content": "<full file content>"
          },
          "output": "File created successfully.",
          "is_error": false
        },
        {
          "k": "tool",
          "id": "tool_write_2",
          "name": "write_file",
          "input": {
            "path": "main.py",
            "content": "<full file content>"
          },
          "output": "File created successfully.",
          "is_error": false
        },
        {
          "k": "tool",
          "id": "tool_write_3",
          "name": "write_file",
          "input": {
            "path": "tests/test_<domain>.py",
            "content": "<full pytest file content>"
          },
          "output": "File created successfully.",
          "is_error": false
        },
        {
          "k": "tool",
          "id": "tool_write_4",
          "name": "write_file",
          "input": {
            "path": "tests/conftest.py",
            "content": "<conftest that adds parent dir to sys.path>"
          },
          "output": "File created successfully.",
          "is_error": false
        },
        {
          "k": "tool",
          "id": "tool_run_main",
          "name": "run_command",
          "input": {
            "command": "python3 main.py"
          },
          "output": "<actual stdout from running main.py>",
          "is_error": false
        },
        {
          "k": "tool",
          "id": "tool_run_pytest",
          "name": "run_command",
          "input": {
            "command": "python3 -m pytest -q"
          },
          "output": "<actual pytest stdout — all green>",
          "is_error": false
        }
      ],
      "usage": {
        "input_tokens": 9000,
        "output_tokens": 16000,
        "cache_read_input_tokens": 40000,
        "cache_creation_input_tokens": 0
      }
    }
  ]
}
```

### Important slug rule:
The JSON filename and the session_id field inside it must be consistent:
```python
import re, json, pathlib

session_id = "<uuid>:lld"
slug = re.sub(r'[^A-Za-z0-9_-]', '_', session_id)
# slug == "<uuid>_lld"   ← this is the filename
# session_id == "<uuid>:lld"  ← this goes INSIDE the JSON as the "session_id" field
```

Write the JSON using Python to avoid encoding issues:
```python
import json, pathlib
out = pathlib.Path('data/conversations') / f'{slug}.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
```

---

## Step 6 — Verify

After writing the JSON, verify it loads correctly:
```python
import json, sys
sys.path.insert(0, '.')
from backend.config import session_slug, CONV_DIR

sid = '<uuid>:lld'
slug = session_slug(sid)
p = CONV_DIR / f'{slug}.json'
assert p.exists(), f"File not found: {p}"
d = json.loads(p.read_text())
assert d['session_id'] == sid
assert d['mode'] == 'lld'
print('OK — open at: https://localhost:8002/?s=' + sid)
```

---

## Quality checklist before finishing

- [ ] Canonical file layout: `models.py`, `<domain>_service.py`, `main.py`, `tests/test_<domain>.py`, `tests/conftest.py` (+ `strategies.py`/`gateways.py` only if §5 needs them) — NO `service.py`/`utils.py`/`helpers.py`
- [ ] Python 3.11+ idioms (`list[Foo]`, `X | None`); no `from __future__ import annotations`; imports at top only (no mid-file `import threading`)
- [ ] `python3 main.py` exits 0 with all cases printing "OK"
- [ ] `python3 -m pytest -q` is fully green
- [ ] Concurrency test asserts UNIQUE resources (`len({…compartment_id…}) == K`), not just the win count
- [ ] Single domain exception base; no bare `RuntimeError`/`Exception` raised from own code; no dead code
- [ ] No `...` in any code in §6 — every method is complete
- [ ] §3.5 API / System Interface present: ONE typed contract table (`Method | Signature | Returns | Raises | Purpose`, 3-7 rows) + ONE 🎙️ line; every method also appears in §4.1/§4.2/§6
- [ ] §4.1: EVERY class subsection (not just the orchestrator) ends with a COMPLETE fenced class block (state + constructor + methods) after its (c) operations table — no class degrades to table-only
- [ ] §6 includes §6.0 Live Writing Order, orchestrator skeleton-first, the 6-block per-method format, ONE Approach Comparison, and a Verification dry-run subsection
- [ ] §9 includes the Concurrency Vocabulary table, the Concurrency Follow-up Q&A, and 2-3 Extensibility TWIST walkthroughs
- [ ] Conversation JSON exists at `data/conversations/<slug>.json`
- [ ] `session_id` inside JSON matches the `:lld` format (with colon, not underscore)
- [ ] Slug in filename uses `_lld` (colon → underscore)
- [ ] All tool blocks use `write_file` (×5-6, bare relative `path`) + `run_command` (×2) — never `Write`/`Bash`/`file_path`/`workspace/<slug>/…`
- [ ] The full §1–§9 markdown is in the first text block
- [ ] `python3 -c "from backend.config import session_slug, CONV_DIR; ..."` confirms file is loadable
