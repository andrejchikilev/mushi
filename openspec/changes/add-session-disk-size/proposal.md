## Why

`mushi session list` currently shows session identity and status, but not how much persisted data each session uses on disk. Users need this visibility to understand which sessions are growing large and decide what to inspect or remove.

The largest session footprint is often backend-managed state rather than the Mushi session JSON. Cursor stores per-agent chat data under `~/.cursor/chats/`, while OpenCode stores session data in a shared SQLite database. Mushi should surface the disk usage it can attribute safely and clean up backend-owned session data when users remove Mushi sessions or tasks.

## What Changes

- Add a human-readable disk-size column to `mushi session list` output.
- Compute the displayed size from backend session storage when the active backend can report per-session usage.
- Fall back to each persisted Mushi session JSON file size when backend usage is unavailable.
- Show OpenCode's shared database size after the session list as a backend-level summary, because it is not safely attributable per session.
- Purge Cursor per-session backend data when users run `mushi session remove` or `mushi task remove`.
- Format sizes with appropriate units (`B`, `KB`, `MB`, `GB`, `TB`) instead of raw bytes.
- Preserve existing session list filtering behavior: all sessions when no task id is provided, task-specific sessions when a task id is provided.

## Capabilities

### New Capabilities
- `session-listing`: Session list output includes a human-readable size for each listed session and may include backend-level storage summaries.
- `backend-storage-accounting`: Backend adapters can report per-session disk usage when available and purge backend-owned session data when supported.

### Modified Capabilities

## Impact

- Affects `mushi session list` CLI output.
- Affects `mushi session remove` and `mushi task remove` cleanup behavior for Cursor-backed sessions.
- Extends the backend adapter protocol with optional disk usage and purge capabilities.
- Updates adapter, workflow, and CLI tests that assert session list output and removal cleanup.
- No storage schema, dependency, or migration changes.
