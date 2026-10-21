## 1. CLI Formatting Helpers

- [x] 1.1 Add `_format_size(size: int) -> str` to format `B`, `KB`, `MB`, `GB`, and `TB` values without new dependencies
- [x] 1.2 Add `_session_size(storage: FilesystemStorage, session: SessionRecord) -> str` to stat the persisted session JSON file and return `?` on `OSError`

## 2. Session List Output

- [x] 2.1 Update `mushi session list` output to include size between `task_id` and `goal`
- [x] 2.2 Preserve current all-sessions and task-filtered listing behavior

## 3. Tests

- [x] 3.1 Update `test_cli_session_list_and_show` to assert the size column is present
- [x] 3.2 Add focused tests for `_format_size` covering bytes and scaled units
- [x] 3.3 Run `uv run pytest` and fix any failures

## 4. Backend Storage Accounting

- [x] 4.1 Add backend adapter capabilities for per-session disk usage and backend session purge
- [x] 4.2 Add default protocol methods for `session_disk_usage(session) -> int | None` and `purge_session(session) -> None`
- [x] 4.3 Implement Cursor per-session disk usage from recorded `cursor_agent_id`
- [x] 4.4 Implement Cursor purge for the matching per-session chat directory
- [x] 4.5 Expose OpenCode shared database size for CLI summary without treating it as per-session usage

## 5. Removal Workflows

- [x] 5.1 Purge supported backend data before `mushi session remove` deletes the Mushi session record
- [x] 5.2 Purge supported backend data for each session before `mushi task remove` deletes the task tree
- [x] 5.3 Keep removals idempotent when backend metadata or backend storage paths are missing

## 6. Backend Size CLI Output

- [x] 6.1 Prefer backend-reported per-session disk usage in `mushi session list`
- [x] 6.2 Fall back to Mushi session JSON size when backend per-session usage is unavailable
- [x] 6.3 Print OpenCode shared database size after listed sessions using a `*` marker

## 7. Expanded Tests

- [x] 7.1 Test Cursor-backed `session list` displays backend directory size
- [x] 7.2 Test OpenCode-backed `session list` displays shared database summary instead of per-session database size
- [x] 7.3 Test `session remove` purges Cursor chat data and tolerates missing metadata
- [x] 7.4 Test `task remove` purges Cursor chat data for all task sessions and tolerates missing metadata
- [x] 7.5 Run `uv run pytest` and fix any failures
