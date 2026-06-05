# How It Works — the Expert DSA Agent, implemented

This document maps the design brief ("force the model into a rigorous, agentic
DSA-solving workflow with tool calling") onto the actual code in this repo, so
you can see exactly how each idea is realized — and tweak it.

It is the "how to implement this in your web app" explanation, grounded in the
working implementation rather than pseudocode.

---

## 1. Model versions — and why this app does NOT use "Claude 3.5 Sonnet"

The original brief suggested targeting **Claude 3.5 Sonnet** as "the most capable
agentic coding model." That guidance is **out of date**. The current Anthropic
lineup is the **Claude 4.x** family, and for this app we target:

| Role in UI | Model ID used | Why |
|------------|---------------|-----|
| Default / balanced | `claude-sonnet-4-6` | strong agentic coding, fast |
| Deepest reasoning | `claude-opus-4-8` | best for hard DSA / interview depth |
| Fast / cheap | `claude-haiku-4-5-20251001` | quick iterations |

These IDs are **verified live against your API key** (`/api/health` lists them;
a startup probe confirmed all three return `ok`). Using a retired `claude-3-5-*`
string would be slower, weaker at agentic tool use, and may not be the best
option available on your account. The model is configurable — see
`backend/config.py` (`MODELS`, `DEFAULT_MODEL`) — so you can change it if needed.

> A real subtlety we had to solve: the newer **Opus 4.8** dropped the classic
> `thinking={"type":"enabled","budget_tokens":N}` API and requires **adaptive**
> thinking (`thinking={"type":"adaptive","display":"summarized"}` +
> `output_config={"effort":"xhigh"}`), while **Sonnet 4.6 / Haiku 4.5** still use
> the budget style. The app picks the right one per model automatically and falls
> back gracefully if a model rejects the thinking config. See
> `backend/agent.py::_create_kwargs` and `config.uses_adaptive_thinking`.

---

## 2. The system prompts — forcing the agentic workflow

The "Expert DSA Agent" protocol (analyze → strategize → code → **rigorously
test** → final answer) lives in **`backend/prompts.py`**. There are **four**
mode-specific prompts:

- **`ASSESSMENT_SYSTEM_PROMPT`** — the 5-step protocol for timed online
  assessments: optimal code, run-and-verify, then `Core Logic / Complexity /
  Code / Edge Cases Conquered`.
- **`INTERVIEW_SYSTEM_PROMPT`** — live coding interview: problem understanding,
  brute force, the optimal approach explained **intuition-first with a tiny
  traced example**, runnable code, walkthrough, complexity, edge cases, and 💬
  "what to say out loud".
- **`LLD_SYSTEM_PROMPT`** — low-level/OO design: requirements, a **class
  diagram**, design patterns & SOLID, code **narrated class by class** and run,
  a **sequence diagram**, concurrency & edge cases.
- **`HLD_SYSTEM_PROMPT`** — system design: requirements, capacity **computed**
  with `run_python`, API & data model, an **architecture diagram**, deep dives
  (with a flow/sequence diagram), scaling, trade-offs, failure modes.

Shared blocks: `_TOOLING` / `_TOOLING_DESIGN` **mandate execution** ("never show
unrun code; compute estimates, don't hand-wave"), `_DIAGRAMS` / `_DIAGRAMS_DESIGN`
require Mermaid diagrams, `_LAYMAN` adds 💬 plain-English narration, `_WEBSEARCH`
allows the web-search tool, and `_FOLLOWUP` enables multi-turn refinement.

The UI picks the prompt via the **mode tab**; `Agent.mode` selects the prompt and
the generation budget (`config.MODES`) — design modes use up to **128k** output
tokens on Opus 4.8.

## 2b. Web search, voice, and access control

- **Web search** — `agent._tools()` appends Anthropic's server-side
  `web_search_20250305` tool; the loop handles `stop_reason == "pause_turn"` so a
  mid-generation search never truncates the answer.
- **Voice** — `audio.js` does dictation (STT, secure-context only → HTTPS for
  iPhone) and natural read-aloud (TTS) with the best local voice.
- **Access control** — set `ALGORA_TOKEN` to require a token on `/api/chat` and
  `/api/reset` (the agent can run shell/Python and is reachable on the LAN); the
  UI prompts for it once. Unset = open on your network (a startup warning is
  logged); fine on a private hotspot, not on a shared network.

---

## 3. The "True Claude Code Method" — real tool calling

This is strategy #2 from the brief: instead of asking the model to *mentally*
dry-run, we give it **tools that physically create and run files**, and require
it to use them before answering.

### The tools (`backend/tools.py`)

| Tool | What it does |
|------|--------------|
| `write_file(path, content)` | creates a file in the workspace |
| `read_file(path)` | reads it back |
| `list_files()` | lists the workspace |
| `run_python(path, stdin?, timeout?)` | **runs a `.py` file**, pipes stdin, captures stdout/stderr + exit code |
| `run_command(command, stdin?, timeout?)` | runs an arbitrary shell command |

Safety: file paths are sandboxed inside the workspace (path-traversal blocked),
runs have a timeout, and captured output is size-capped.

### Files are created and run *in this folder*

Exactly as requested — when the model calls a tool, it writes and runs files
**right here**, under `workspace/`. To stop the two tabs colliding on a file
named `solution.py`, each mode gets its own subdir:

```
workspace/
├── assessment/      ← files the Assessment tab writes & runs
└── interview/       ← files the Interview tab writes & runs
```

See `Agent._workspace()` (`backend/agent.py`) and the `base`-dir threading in
`tools.execute_tool`.

### The agentic loop (`backend/agent.py::stream_turn`)

```
user message
   │
   ▼
┌─────────────────────────────────────────────┐
│ call Claude (system prompt + tools, stream)  │◀────────┐
└─────────────────────────────────────────────┘         │
   │ stream: thinking_delta / text_delta                 │
   ▼                                                      │
 stop_reason == "tool_use"? ──no──▶ turn_done (answer)    │
   │ yes                                                  │
   ▼                                                      │
 execute each tool (write_file / run_python / …)          │
   │  → tool_result (stdout, stderr, exit code)           │
   ▼                                                      │
 append results, loop ─────────────────────────────────-─┘
```

So the model writes code → runs it → reads the real output → fixes it → re-runs,
until it passes its own tests. (In testing it caught a malformed test case,
fixed it, and re-ran until "All 16 tests pass.") This is the behavior the brief
wanted: *"you MUST use the execute tool to run your code... if it fails, rewrite
and test again."*

Each step is streamed to the browser as **Server-Sent Events**: `step_start`,
`thinking_delta`, `text_delta`, `tool_call`, `tool_result`, `turn_done`,
`notice`, `error`, `done` — which is why you watch it think, write, and run live.

---

## 4. The web app — laptop + iPhone over hotspot

One FastAPI process (`backend/server.py`) serves both the JSON/SSE API and the
static frontend, and binds to `0.0.0.0`, so the same URL works on the laptop and
on a phone on the same network.

```bash
./run.sh
#  On this laptop:   http://localhost:8000
#  On your iPhone:   http://<laptop-LAN-ip>:8000   (printed by run.sh)
```

To use it from the iPhone over a hotspot: enable Personal Hotspot on the phone,
connect the **laptop** to it, run `./run.sh`, then open the printed
`http://<ip>:8000` in Safari (Add to Home Screen for full-screen). See the README
for details.

The frontend (`frontend/`) is a zero-build SPA: a tab-aware SSE client
(`app.js`), a self-contained Markdown renderer with Python highlighting, GFM
tables, and **Mermaid diagrams** (`markdown.js`), and free browser **voice
dictation** (`audio.js`).

---

## 5. How the brief's 5-step protocol maps to the code

| Brief step | Where it happens |
|------------|------------------|
| 1. Problem analysis (text **or image**) | system prompt + multimodal input (`/api/chat` accepts base64 images) |
| 2. Approach & strategy (brute force → optimal, Big-O) | system prompt; extended **thinking** streamed to the Reasoning panel |
| 3. Code generation (clean, commented Python) | model writes via `write_file` |
| 4. **Rigorous testing** (samples + ≥3 edge cases, revise on failure) | model runs via `run_python`/`run_command`, loops until green |
| 5. Final output format | enforced by the system prompt; rendered as Markdown |

---

## 6. Verified

Not asserted — exercised: 34 unit/API tests (mocked SDK), live runs across all
three models with thinking on/off, real-browser E2E for both tabs, diagram and
table rendering, and an adversarial multi-agent review whose findings (incl. a
DOM-XSS and a diagram-render race) were fixed and re-verified. See `tests/`.
