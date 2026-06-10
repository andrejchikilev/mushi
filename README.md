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

Data is stored in `$XDG_DATA_HOME/mushi` (defaults to `~/.local/share/mushi`). Override with `MUSHI_STORAGE_ROOT` env var or `--storage-root`.

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

`workspace_path` is the second positional argument — defaults to current directory.
`session_id`, `--profile`, `--goal` are optional flags. If omitted:

- `session_id` auto-generated as `s-{N}-{task_id}`
- `profile` resolved to `default` profile (auto-created with `opencode` if it exists)
- `goal` omitted — adapter is not invoked

```bash
mushi session start task-1                              # minimal, all auto
mushi session start task-1 /path/to/repo                # custom workspace
mushi session start task-1 --session-id s1              # explicit session id
mushi session start task-1 --profile default            # explicit profile
mushi session start task-1 --goal "Continue work"       # with adapter invocation
mushi session finish s1                                  # only session_id needed
mushi session list                                       # all sessions
mushi session list task-1                                # sessions for a task
```

### Resume from previous session

```bash
mushi session resume session-1
mushi task resume task-1                                 # last session of a task
```

### Handoffs

```bash
mushi handoff create task-1 --notes "Context for next agent"
mushi handoff show handoff-task-1
```

### Search

```bash
mushi search query "storage"                              # full-text search
mushi search query --type session --backend cursor        # filtered search
mushi search rebuild                                      # rebuild search index
```
