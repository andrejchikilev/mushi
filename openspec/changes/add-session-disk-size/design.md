## Context

Mushi stores each session as a JSON file under `tasks/{task_id}/sessions/{session_id}.json`. The `session list` command currently emits tab-separated columns for session id, status, task id, and goal. Users can remove sessions and tasks, but they do not have quick visibility into which sessions are taking more space on disk.

The Mushi JSON record is usually small. Backend-managed state can be much larger: Cursor stores per-agent chat data below `~/.cursor/chats/{hash}/{cursor_agent_id}/`, while OpenCode stores session state in a shared `opencode.db`. Cursor data can be attributed to a Mushi session through `session.backend_metadata.cursor_agent_id`; OpenCode's shared database cannot be safely attributed per session.

No storage schema changes are needed because size and purge behavior are derived from existing session metadata and backend storage locations.

## Goals / Non-Goals

**Goals:**
- Display a human-readable size for each session listed by `mushi session list`.
- Keep the existing filtering behavior: list all sessions without a task id, or only task-specific sessions when a task id is provided.
- Prefer backend-reported per-session disk usage when the backend can safely attribute storage to a session.
- Fall back to the persisted Mushi session JSON size when backend usage is unavailable.
- Show OpenCode's shared database size as a backend-level summary after the list rather than per session.
- Purge Cursor per-session backend data when removing a session or a task.

**Non-Goals:**
- Do not include task-level files, handoff documents, or search indexes in the displayed size.
- Do not delete OpenCode's shared database when removing one session or task.
- Do not persist size in session records.
- Do not add new dependencies for formatting sizes.

## Decisions

- Add backend adapter capabilities for disk usage and purge, with protocol methods `session_disk_usage(session) -> int | None` and `purge_session(session) -> None`.
  - Rationale: backend-specific storage layout should stay inside adapters, and workflows/CLI can remain backend-agnostic.
  - Alternative considered: teach CLI/workflows Cursor and OpenCode paths directly. Rejected because it leaks backend internals outside adapter boundaries.
- For Cursor, compute per-session size from `~/.cursor/chats/{hash}/{cursor_agent_id}/` when `cursor_agent_id` is present, and purge that directory on session/task removal.
  - Rationale: Cursor stores agent-scoped data in a directory that can be attributed to one Mushi session.
  - Alternative considered: skip purge if the path cannot be resolved. Accepted for missing metadata or missing directories so removals stay idempotent.
- For OpenCode, do not report per-session size. Instead expose the shared `opencode.db` path so `session list` can print a separate backend summary line with `*`.
  - Rationale: the database is shared, so showing the full DB size on every session row would be misleading.
- Fall back to `storage.layout.session_path(session.task_id, session.id).stat().st_size` when no per-session backend size is available.
  - Rationale: every session has a Mushi record, and this keeps the size column populated even for unsupported or non-attributable backends.
- Format sizes in the CLI with a small helper that scales units from `B` to `KB`, `MB`, `GB`, and `TB`.
  - Rationale: users asked for easy-to-read output rather than raw bytes.
  - Alternative considered: raw byte count. Rejected for usability.
- Add the size column between `task_id` and `goal`.
  - Rationale: identity/status/task remain grouped first, size is metadata about the row, and goal remains the free-text tail column.
- Return `?` if the session file cannot be statted.
- Rationale: missing or inaccessible storage is unexpected but should not crash listing of other sessions.

## Risks / Trade-offs

- Existing scripts that parse `mushi session list` by tab position will see an additional column. Mitigation: keep output tab-separated and append the new size before the free-text goal column.
- Human-readable formatting is approximate for non-byte units. Mitigation: use one decimal place for scaled units and no decimals for bytes.
- Backend storage paths may be missing even when metadata exists. Mitigation: treat missing backend storage as zero or unavailable and keep remove operations idempotent.
- Cursor purge deletes backend-owned data outside Mushi's storage root. Mitigation: only delete paths derived from Cursor's known chat root and a recorded `cursor_agent_id`.
