# Portable Claude Code session

This folder carries **one** Claude Code session ("abcd") and this project's
memory so the conversation can be resumed on another laptop via git.

| | |
|---|---|
| Session name | `abcd` |
| Session ID | `24061c8a-2a69-4177-88e2-49dfff5310e9` |
| Transcript | `sessions/24061c8a-2a69-4177-88e2-49dfff5310e9.jsonl` (~38 MB) |
| Memory | `memory/MEMORY.md`, `memory/uber-interview-prep.md` |

## Restore on the other laptop

1. Clone/pull this repo.
2. From the repo root, run:
   ```bash
   bash .claude-session/restore.sh
   ```
3. Launch Claude Code in this project and resume:
   ```bash
   claude --resume 24061c8a-2a69-4177-88e2-49dfff5310e9
   ```
   (or `claude --resume` and pick the session named **abcd**)

## Why the restore script (don't just copy the file)

Claude Code finds sessions at
`~/.claude/projects/<encoded-project-path>/<id>.jsonl`, where
`<encoded-project-path>` is the project's absolute path with every `/` turned
into `-`. That string depends on the machine's username and clone location, so
`restore.sh` recomputes it on the target machine instead of hard-coding this
laptop's path.

## Not included (on purpose)

`~/.claude/settings.json`, global `CLAUDE.md`, and `RTK.md` are user-private and
may contain secrets — they are intentionally left out.
