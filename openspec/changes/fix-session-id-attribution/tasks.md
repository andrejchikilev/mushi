## 1. OpenCode attribution

- [x] 1.1 Extend `_opencode_db.py` with set-based snapshot (`list_workspace_session_ids`) and row lookup helpers that return full candidate rows for a workspace
- [x] 1.2 Add spawn-window attribution to `OpenCodeAdapter.invoke`: pre-spawn ID snapshot, optional lock file, poll during invoke start via a post-spawn identification pass, post-exit fallback on ID-set diff
- [x] 1.3 Keep known resume IDs: seed `result.invocation` from resume settings keys (`opencode_session_id`, `opencode_session_title`); detection only fills when absent
- [x] 1.4 Validate candidates by `time_created` proximity to spawn instant; ambiguous cases attribute nothing and append an attribution note to `result_summary`

## 2. Cursor attribution

- [x] 2.1 Extend `_cursor_db.py` with workspace slug filtering (`detect_new_agents(before, workspace_slug=...)`) and slug derivation for a cwd
- [x] 2.2 Rewrite `CursorCliAdapter.invoke` attribution: pre-spawn agent ID snapshot, spawn-window polling (agents' store.db created at process start), post-exit fallback, ambiguity fails safe
- [x] 2.3 Keep known resume IDs: seed `result.invocation` from resume settings keys (`cursor_agent_id`, `cursor_agent_name`); detection only fills when absent

## 3. Invocation merge in workflow

- [x] 3.1 Change `_invoke_adapter` in `mushi/core/sessions.py` to merge incoming adapter `invocation` over the persisted session `invocation` (removal only when adapter explicitly empties it)

## 4. Tests

- [x] 4.1 Unit tests for new `_opencode_db` helpers (set snapshot, candidates)
- [x] 4.2 Unit tests for cursor workspace filtering and `detect_new_agents` slug behavior
- [x] 4.3 Adapter-level concurrency tests: two interleaved attribution windows attribute their own IDs; foreign session in window is excluded or fails safe
- [x] 4.4 Resume retention tests for both adapters: known ID survives empty detection; detection does not overwrite known ID
- [x] 4.5 Update `tests/test_cli.py` expectations if any session output changes, run `uv run pytest`

## 5. Documentation

- [x] 5.1 Review diff (correctness, regressions, schema compat, coverage gaps) and fix findings, max 2 review cycles
- [x] 5.2 Create `.mushi/manual-test-session-id-attribution.md` with self-contained verification commands
