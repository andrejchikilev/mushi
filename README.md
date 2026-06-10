# Mushi

Mushi is a persistent task and session manager for coding agents.

Goals:

- Store long-lived task context
- Resume work across agent sessions
- Support multiple backends:
  - Cursor CLI
  - OpenCode
- Generate handoffs between agents
- Search historical task context

Mushi is agent-agnostic.
Agent backends are interchangeable.

## Installation

**Dev mode** (from local repo):

```bash
uv sync
uv run mushi --help
```

**System-wide** (for use from any directory):

```bash
uv tool install .
mushi --help
```

To update after local changes:

```bash
uv tool install --reinstall .
```

## Usage

All commands accept `--storage-root` (defaults to `MUSHI_STORAGE_ROOT` env var or `.mushi`).

### Tasks

```bash
mushi task create task-1 "Design storage"
mushi task list
mushi task show task-1
mushi task status task-1 in_progress
```

### Profiles

```bash
mushi profile set default opencode --settings '{"model":"test"}'
mushi profile show default
```

### Sessions

`workspace_path` is optional — defaults to current directory.

```bash
mushi session start session-1 task-1 default "Continue work"
mushi session finish task-1 session-1 succeeded "Recorded metadata"
```

### Resume from previous session

```bash
mushi session resume session-2 task-1 default "Next phase" --resume-from session-1
```

### Handoffs

```bash
mushi handoff create task-1 --notes "Context for next agent"
mushi handoff show handoff-task-1
```
