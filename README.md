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

## Current CLI

Phase 3 records task, profile, and session metadata only. It does not invoke Cursor CLI, OpenCode, or any other backend yet.

Use `uv` for all project commands:

```bash
uv sync
uv run pytest
uv run mushi --help
```

Manual metadata smoke flow:

```bash
export MUSHI_STORAGE_ROOT=.mushi-dev
uv run mushi task create task-1 "Design storage"
uv run mushi profile set default opencode --settings '{"model":"test"}'
uv run mushi session start session-1 task-1 default "$PWD" "Continue work"
uv run mushi session finish task-1 session-1 succeeded "Recorded metadata"
uv run mushi task show task-1
```
