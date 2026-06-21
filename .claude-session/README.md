# Claude Code Session Backup

This directory contains the Claude Code session transcript and memory files from the original machine.

## Contents

- `session.jsonl` — Full conversation transcript (session UUID: `24061c8a-2a69-4177-88e2-49dfff5310e9`)
- `memory/` — Project memory files (auto-memory system)

## Restoring on Another Machine

**IMPORTANT:** The session file name in `~/.claude/projects/` depends on the project path. The directory name is path-encoded (slashes → dashes).

### Steps to restore:

1. **Clone the repo** on the new machine
2. **Find the encoded path:**
   ```bash
   # If project is at /Users/anshul/projects/algora
   echo "-Users-anshul-projects-algora"
   ```
3. **Copy files to Claude's project directory:**
   ```bash
   # Create the directory structure
   mkdir -p ~/.claude/projects/<encoded-path>/memory
   
   # Copy session transcript (keep the original UUID)
   cp .claude-session/session.jsonl \
      ~/.claude/projects/<encoded-path>/24061c8a-2a69-4177-88e2-49dfff5310e9.jsonl
   
   # Copy memory files
   cp .claude-session/memory/* \
      ~/.claude/projects/<encoded-path>/memory/
   ```
4. **Launch Claude Code** in the project directory
5. The conversation should appear in your session history

### Example (if new path is `/Users/anshul/projects/algora`):

```bash
cd ~/projects/algora
ENCODED_PATH="-Users-anshul-projects-algora"
mkdir -p ~/.claude/projects/$ENCODED_PATH/memory
cp .claude-session/session.jsonl ~/.claude/projects/$ENCODED_PATH/24061c8a-2a69-4177-88e2-49dfff5310e9.jsonl
cp .claude-session/memory/* ~/.claude/projects/$ENCODED_PATH/memory/
```

## What's NOT included (intentional)

- `~/.claude/settings.json` — Contains API keys and personal settings
- Other sessions from this project
- Global Claude Code configuration

Only this specific session and its project memory are included.
