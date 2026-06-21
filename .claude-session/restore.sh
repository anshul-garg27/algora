#!/usr/bin/env bash
# Restore this Claude Code session + project memory on a new machine.
#
# Claude Code stores sessions under:
#   ~/.claude/projects/<encoded-abs-project-path>/<session-id>.jsonl
# where <encoded-abs-project-path> is the project's ABSOLUTE path with every
# "/" replaced by "-". That encoding depends on THIS machine's username and
# clone location, so we compute it here instead of hard-coding it.
#
# Run this from the repo root on the target laptop:
#   bash .claude-session/restore.sh
#
# Then launch Claude Code in this project and resume:
#   claude --resume 24061c8a-2a69-4177-88e2-49dfff5310e9
# (or `claude --resume` and pick the session named "abcd")

set -euo pipefail

SESSION_ID="24061c8a-2a69-4177-88e2-49dfff5310e9"

# Repo root = parent of this script's directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Encode the absolute project path: "/" -> "-".
ENCODED="${REPO_ROOT//\//-}"
TARGET="$HOME/.claude/projects/$ENCODED"

echo "Project path : $REPO_ROOT"
echo "Target dir   : $TARGET"

mkdir -p "$TARGET/memory"
cp "$SCRIPT_DIR/sessions/$SESSION_ID.jsonl" "$TARGET/"
cp "$SCRIPT_DIR/memory/"* "$TARGET/memory/"

echo "Done. Session and memory restored."
echo "Now run:  claude --resume $SESSION_ID"
