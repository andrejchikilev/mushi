## Why

When several agents are opened through mushi (even in different workspaces), backend session IDs get mixed up after the agents close: both adapters attribute backend sessions by taking the *newest* entry that appeared in the backend's local store between a pre-invoke and post-exit snapshot. With overlapping windows from concurrent runs (or foreign backend activity), a mushi session record gets another agent's `opencode_session_id` / `cursor_agent_id`, so `sessions resume` opens the wrong chat. Resume also loses an already-known backend ID entirely whenever post-exit detection finds nothing, because `_invoke_adapter` replaces the stored `invocation` wholesale.

## What Changes

- Replace "take the newest new entry" attribution with deterministic, race-safe attribution for mushi-driven agents:
  - Snapshot the full set of existing backend session IDs (not just max timestamp) before spawning.
  - Hold a global spawn lock across snapshot → process spawn → immediate store polling, so concurrent mushi agents get disjoint validation windows.
  - Validate the polled candidate by creation-time proximity to the spawn instant (Cursor `createdAt` ms; OpenCode `time_created`).
- Filter cursor detection candidates by workspace instead of considering all agents on the machine.
- Never overwrite a known backend session ID on resume; merge persisted invocation keys into the adapter result so resume detection cannot erase them.
- When attribution is ambiguous (foreign sessions in the window, no title/time match), record no backend ID and surface a warning instead of guessing - resume then opens a new chat rather than someone else's.

## Capabilities

### New Capabilities
- `backend-session-attribution`: Deterministic, concurrency-safe recording of backend session IDs for sessions started and resumed through mushi adapters.

### Modified Capabilities

## Impact

- `mushi/adapters/opencode.py`, `mushi/adapters/cursor.py` - attribution logic.
- `mushi/adapters/_opencode_db.py`, `mushi/adapters/_cursor_db.py` - set-based snapshots, workspace filtering, creation-time validation helpers.
- `mushi/core/sessions.py` - invocation merge instead of wholesale overwrite in `_invoke_adapter`.
- `mushi/cli.py` - warning output when a finished session has no attributable backend ID.
- Tests: `tests/test_adapters.py`, `tests/test_cursor_db.py`, `tests/test_opencode_db.py`, `tests/test_session_adapter_integration.py`, `tests/test_cli.py`.
- Build on top of the in-flight `add-session-disk-size` working-tree changes; no storage schema changes.
