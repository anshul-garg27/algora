"""Central configuration for the agentic coding assistant.

All tunables live here so the rest of the codebase reads from a single source.
Values can be overridden via environment variables.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
from pathlib import Path

# --- Paths --------------------------------------------------------------------

# Project root = the folder that contains this `backend/` package.
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _build_marker() -> str:
    """A short hash of the backend source, computed at import. Surfaced in /api/health
    so you can VERIFY which code a running server actually loaded (vs a stale process)."""
    h = hashlib.sha256()
    here = Path(__file__).resolve().parent
    for name in ("agent.py", "prompts.py", "config.py", "server.py", "tools.py"):
        try:
            h.update((here / name).read_bytes())
        except OSError:
            pass
    return h.hexdigest()[:8]


BUILD = _build_marker()

# Where Claude is allowed to create and run files. Everything the agent does on
# disk is confined to this directory.
WORKSPACE_DIR = Path(os.environ.get("WORKSPACE_DIR", PROJECT_ROOT / "workspace")).resolve()

FRONTEND_DIR = PROJECT_ROOT / "frontend"

# Saved conversations (chat history) live here, one JSON per session.
CONV_DIR = Path(os.environ.get("CONV_DIR", PROJECT_ROOT / "data" / "conversations")).resolve()


def session_slug(session_id: str) -> str:
    """Filesystem-safe slug for a session id (shared by workspace + history)."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", session_id or "").strip("._")[:80] or "session"


def workspace_for(session_id: str | None, mode: str | None = None) -> Path:
    """Per-conversation workspace subdir, so concurrent chats never share files.

    Each browser tab/session gets its own dir (keyed by the session id, which is
    unique per tab and carries the mode). Two chats writing `capacity.py` at the
    same time land in different folders instead of clobbering each other.
    Falls back to a per-mode dir when no session id is given (e.g. unit tests).
    """
    if session_id:
        return WORKSPACE_DIR / session_slug(session_id)
    return WORKSPACE_DIR / (mode or "default")


# --- Models -------------------------------------------------------------------

# Current Claude model IDs (verified at runtime by /api/health). Opus 4.8 is the
# default for the deepest agentic reasoning; the UI exposes Sonnet and Haiku as
# faster/cheaper alternatives.
MODELS = {
    "sonnet": os.environ.get("MODEL_SONNET", "claude-sonnet-4-6"),
    "opus": os.environ.get("MODEL_OPUS", "claude-opus-4-8"),
    "haiku": os.environ.get("MODEL_HAIKU", "claude-haiku-4-5-20251001"),
}

# Opus 4.8 (1M) is the default — best agentic reasoning for DSA + design.
DEFAULT_MODEL_KEY = os.environ.get("DEFAULT_MODEL", "opus")

# 1M-context beta header (applied to Opus requests so long multi-turn design
# sessions with 128k outputs fit). Set ENABLE_1M_CONTEXT=0 to disable.
ENABLE_1M_CONTEXT = os.environ.get("ENABLE_1M_CONTEXT", "1") == "1"
CONTEXT_1M_BETA = os.environ.get("CONTEXT_1M_BETA", "context-1m-2025-08-07")

# Server-side web search (handled by Anthropic). Set ENABLE_WEB_SEARCH=0 to disable.
ENABLE_WEB_SEARCH = os.environ.get("ENABLE_WEB_SEARCH", "1") == "1"
WEB_SEARCH_MAX_USES = int(os.environ.get("WEB_SEARCH_MAX_USES", "5"))

# --- Access control ----------------------------------------------------------
# The agent can run shell/Python on the host, and the server is reachable on the
# LAN (for the phone). Set ALGORA_TOKEN to a secret to require it on every
# request — the UI asks for it once. If unset, the API is OPEN to your network
# (fine on a private hotspot, risky on a shared network) and a warning is logged.
ALGORA_TOKEN = os.environ.get("ALGORA_TOKEN", "").strip()

# Cross-origin allowlist (the SPA is same-origin, so empty is the safe default).
ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get("ALGORA_ALLOWED_ORIGINS", "").split(",") if o.strip()
]


# --- Engine auth (the Claude Agent SDK drives the `claude` CLI) ---------------
#
# The underlying CLI authenticates one of two ways:
#   * API key      — ANTHROPIC_API_KEY present in the subprocess env (per-token
#                    billing against your API account). This is the default.
#   * Subscription — ANTHROPIC_API_KEY ABSENT and you have logged in once with
#                    `claude login` (or `claude setup-token`); the CLI then uses
#                    your Pro/Max plan and no API key is needed.
#
# Set ALGORA_USE_SUBSCRIPTION=1 to strip the key from the spawned CLI so it falls
# back to your subscription. Flipping this single flag is the ONLY change needed
# to move this app from an API key to a Claude subscription on another machine.
USE_SUBSCRIPTION = os.environ.get("ALGORA_USE_SUBSCRIPTION", "0") == "1"


def subprocess_env() -> dict[str, str] | None:
    """Environment overrides for the spawned `claude` CLI.

    Returns ``None`` in API mode so we don't pass ``env`` at all — the subprocess
    inherits this process's environment (ANTHROPIC_API_KEY included → API billing).

    In subscription mode it returns ONLY the overrides. The SDK merges these on
    top of the inherited environment, so to actually drop the API key we must
    override it to empty (the CLI treats an empty key as "no key" and falls back
    to your `claude login` subscription) rather than just omitting it.
    """
    if not USE_SUBSCRIPTION:
        return None
    return {"ANTHROPIC_API_KEY": "", "ANTHROPIC_AUTH_TOKEN": ""}


# Explicit path to the `claude` binary; auto-discovered on PATH if unset. Passed
# to the SDK so a non-login shell (e.g. launched by run.sh) still finds it.
CLAUDE_CLI = os.environ.get("ALGORA_CLAUDE_CLI") or shutil.which("claude") or ""

# Claude Code's built-in tools the agent is allowed to use — it writes and runs
# its own code with these (no custom write_file/run_python tools anymore).
ALLOWED_TOOLS = [
    t.strip()
    for t in os.environ.get(
        "ALGORA_ALLOWED_TOOLS", "Read,Write,Edit,Bash,Glob,Grep,WebSearch"
    ).split(",")
    if t.strip()
]

# Local personal tool: let the agent write files and run code WITHOUT interactive
# permission prompts (headless can't answer them). This is a looser sandbox than
# the old per-path allowlist — fine on a private machine; see the README security
# note. Override with ALGORA_PERMISSION_MODE if you want a stricter mode.
PERMISSION_MODE = os.environ.get("ALGORA_PERMISSION_MODE", "bypassPermissions")

# Filesystem settings sources the agent loads (user/project/local). Empty by
# default so the agent's behaviour comes ONLY from the mode system prompt and is
# not coloured by your global ~/.claude/CLAUDE.md or a project's settings.
SETTING_SOURCES = [
    s.strip() for s in os.environ.get("ALGORA_SETTING_SOURCES", "").split(",") if s.strip()
]


# --- Modes --------------------------------------------------------------------

# Four surfaces share the same engine but differ in system prompt + generation
# budget. Design modes (lld/hld) and interview think hard and write long, complete
# answers (the 1M-context Opus 4.8 has ample room).
MODES = {
    "assessment": {
        "max_tokens": int(os.environ.get("ASSESS_MAX_TOKENS", "16000")),
        "thinking_budget": int(os.environ.get("ASSESS_THINKING_BUDGET", "5000")),  # Reduced (adaptive thinking)
        "effort": os.environ.get("ASSESS_EFFORT", "xhigh"),
    },
    # Live coding interview: MEDIUM. Measured time-to-first-text by effort on hard
    # problems: low ~5s, medium ~36-60s, high 4-79s (unpredictable), xhigh 67-124s.
    # Correctness was IDENTICAL across all levels (the run-and-verify loop guarantees it,
    # not thinking depth) — so higher effort buys a cleaner FIRST approach + richer
    # write-up, NOT correctness. Medium fits the real workflow: the model thinks while
    # the candidate is still reading/understanding the problem (~1 min reading + several
    # min to grasp it), so ~36-60s is hidden behind that window. xhigh's 1-2 min buys
    # nothing extra. Override per taste with INTERVIEW_EFFORT (low|medium|high|xhigh).
    # All models (Opus/Sonnet/Haiku) now use adaptive thinking, so they think ON-DEMAND.
    "interview": {
        "max_tokens": int(os.environ.get("INTERVIEW_MAX_TOKENS", "32000")),
        "thinking_budget": int(os.environ.get("INTERVIEW_THINKING_BUDGET", "6000")),  # Lower now that adaptive
        "effort": os.environ.get("INTERVIEW_EFFORT", "medium"),
    },
    # Design modes use LOW thinking effort: the prompt's structure (rigor checklist,
    # per-requirement scaffold, Bad->Good->Great template) carries correctness, so a
    # long upfront reasoning phase only delays the speakable opener the candidate
    # needs within seconds in a live interview. Bump via *_EFFORT if practising offline.
    "lld": {
        "max_tokens": int(os.environ.get("LLD_MAX_TOKENS", "128000")),
        "thinking_budget": int(os.environ.get("LLD_THINKING_BUDGET", "6000")),
        "effort": os.environ.get("LLD_EFFORT", "low"),
    },
    "hld": {
        "max_tokens": int(os.environ.get("HLD_MAX_TOKENS", "128000")),
        "thinking_budget": int(os.environ.get("HLD_THINKING_BUDGET", "6000")),
        "effort": os.environ.get("HLD_EFFORT", "low"),
    },
    # Behavioral / hiring-manager / resume round: a STAR answer in the candidate's
    # real voice. Medium effort keeps it natural (not over-polished) and fast for
    # live practice; the voice rubric — not deep reasoning — carries quality.
    "behavioral": {
        "max_tokens": int(os.environ.get("BEHAVIORAL_MAX_TOKENS", "20000")),
        "thinking_budget": int(os.environ.get("BEHAVIORAL_THINKING_BUDGET", "6000")),
        "effort": os.environ.get("BEHAVIORAL_EFFORT", "medium"),
    },
}
DEFAULT_MODE = "assessment"


def resolve_mode(mode: str | None) -> str:
    return mode if mode in MODES else DEFAULT_MODE


def resolve_model(key_or_id: str | None) -> str:
    """Map a short key (sonnet/opus/haiku) to a model id, or pass through an id."""
    if not key_or_id:
        key_or_id = DEFAULT_MODEL_KEY
    return MODELS.get(key_or_id, key_or_id)


# --- Generation budgets -------------------------------------------------------
#
# Per-mode max_tokens / thinking_budget / effort live in MODES above. Extended
# thinking comes in two API shapes depending on the model generation:
#   * "budget" style (Sonnet 4.6, Haiku 4.5): thinking={"type":"enabled","budget_tokens":N}
#   * "adaptive" style (Opus 4.8):            thinking={"type":"adaptive"} + output_config.effort
# The "effort" values are: low | medium | high | xhigh | max. xhigh ("always
# thinks deeply with extended exploration") is Opus 4.8/4.7 only.

# Model-id substrings that require the adaptive-thinking API instead of budgets.
# All three latest models (Opus 4.8, Sonnet 4.6, Haiku 4.5) support adaptive thinking.
# This makes them all think ON-DEMAND (when needed) instead of always upfront.
ADAPTIVE_THINKING_MODELS = [
    s.strip().lower()
    for s in os.environ.get("ADAPTIVE_THINKING_MODELS", "opus-4-8,opus-4-9,sonnet-4-6,haiku-4-5").split(",")
    if s.strip()
]


def uses_adaptive_thinking(model_id: str) -> bool:
    """True if this model needs thinking.type=adaptive + output_config.effort."""
    m = (model_id or "").lower()
    return any(sub in m for sub in ADAPTIVE_THINKING_MODELS)


# Hard ceiling on agentic tool-use iterations to prevent runaway loops.
MAX_AGENT_STEPS = int(os.environ.get("MAX_AGENT_STEPS", "20"))


# --- Tool execution safety ----------------------------------------------------

# Default and maximum wall-clock seconds for a single code/command execution.
DEFAULT_EXEC_TIMEOUT = int(os.environ.get("DEFAULT_EXEC_TIMEOUT", "15"))
MAX_EXEC_TIMEOUT = int(os.environ.get("MAX_EXEC_TIMEOUT", "60"))

# Cap captured stdout/stderr returned to the model (characters) to protect the
# context window from runaway output.
MAX_OUTPUT_CHARS = int(os.environ.get("MAX_OUTPUT_CHARS", "20000"))

# Cap how large a single file the agent may write (bytes).
MAX_FILE_BYTES = int(os.environ.get("MAX_FILE_BYTES", "1000000"))


# --- Server -------------------------------------------------------------------

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
