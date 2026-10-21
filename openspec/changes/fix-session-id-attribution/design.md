## Context

Both active adapters infer the backend session ID by diffing backend-local stores around an invoke:

- OpenCode: `mushi/adapters/opencode.py` snapshots `MAX(time_created)` for the workspace from the shared `opencode.db` (`_opencode_db.py`), then after the interactive process exits takes the newest row created after that timestamp.
- Cursor: `mushi/adapters/cursor.py` snapshots `{store.db path: mtime}`, then takes the agent with the newest `createdAt` among stores whose mtime changed. The computed `workspaceSlug` is never used for filtering.

Three failure modes verified in code:

1. **Foreign pickup**: another agent's session row created inside our detection window wins because we sort newest-first and take index 0. Concurrency in the same workspace (typical mushi multi-agent usage) guarantees records share/steal IDs.
2. **No workspace scoping (cursor)**: agents from other projects are candidates.
3. **Erasure of known IDs**: on resume the known `opencode_session_id`/`cursor_agent_id` is passed via settings, but the base `AdapterResult.invocation` contains only `args/returncode/cwd`; `_invoke_adapter` (`mushi/core/sessions.py:145`) overwrites `invocation` wholesale. If post-exit detection returns nothing (typical for `opencode --session X`, whose row's `time_created` does not advance) the persisted ID is dropped, and the next resume opens a new backend session.

OpenCode has no deterministic ID output for interactive TUI runs; Cursor interactive `agent` runs print no chat id either. A `serve`+`attach` pipeline for OpenCode was evaluated and rejected: no better precision for mushi-driven flows, plus server/port lifecycle complexity.

Working tree note: uncommitted `add-session-disk-size` change already touches the same adapter files; this change builds on top of that state.

## Goals / Non-Goals

**Goals:**

- Every session started through mushi records its own backend session ID (exact for all mushi-vs-mushi concurrency, robust against non-mushi backend activity).
- Resume always continues the previously recorded backend session and never loses that ID.
- Ambiguity fails safe: record nothing and warn, never attribute a foreign session.
- Minimal behavioral change: keep storage schemas, CLI UX, and adapter protocol unchanged.

**Non-Goals:**

- Replacing backend stores, adding backend APIs/keys, or changing resume UX beyond warnings.
- Attributing sessions started outside mushi.
- Handling backends other than opencode and cursor.

## Decisions

1. **ID-set snapshot and exclusion.** Snapshot every existing backend ID before spawn (OpenCode: session ids for workspace; Cursor: all `agentId`s). Post-exit candidates = new IDs only. Rationale: excludes stale rows entirely and is unaffected by clock granularity; cheaper than window arithmetic alone.
   Alternative considered: max-timestamp only (current) - rejected as the direct cause of foreign pickup.

2. **Spawn serialization with immediate in-window validation (primary mechanism).**
   A global lock file (default `~/.local/share/mushi/agent-spawn.lock`, overridable via env for tests; per-user, not per-workspace) serializes the critical section: acquire lock → take ID snapshot → spawn backend process → poll the store for any new *workspace-matching* ID (short timeout, ~15s; rows are created at process start for both backends - to verify in implementation) → validate creation time proximity to spawn instant → release lock.
   Because candidate rows for concurrent mushi agents exist before the next critical section starts (they are created during the previous section's poll), each run's attribution is its own row. Tests can inject lockdir/fake stores.
   Non-mushi interference inside the critical section is mitigated by proximity validation: keep the candidate whose creation timestamp is closest to our spawn instant (Cursor `createdAt` ms precision; OpenCode `time_created`). Two distinct candidates in the window with no time match ⇒ ambiguous ⇒ no attribution.
   Alternatives considered:
   - Best-effort guess among multiple candidates - rejected by user decision; error side (foreign resume) is worse than degraded side (new chat on resume).
   - `opencode serve` + `attach` - rejected (see Context).

3. **Post-exit fallback.** If polling timed out (row created lazily), fall back after process exit to ID-set diff; apply the same unique-candidate / proximity / ambiguity policy. Detection results other than "exactly one validated" never overwrite.

4. **Resume never regresses IDs.** Adapters seed `result.invocation` with the resume keys (`opencode_session_id`, `opencode_session_title`, `cursor_agent_id`, `cursor_agent_name`) taken from settings, then overlay detection findings; `_invoke_adapter` merges the incoming `invocation` over the persisted one instead of replacing it, so nothing known is lost. Resume itself keeps using `--session <id>` / `agent --resume <id>`.

5. **Workspace scoping for Cursor.** `detect_new_agents` accepts a workspace slug; candidates are restricted to agents whose transcript workspace slug matches the invoked workspace slug (derive from cwd slug format - verify at implementation; fall back to unfiltered behavior if mapping is unavailable).

6. **Warning surfacing.** When a finished session ends up without a backend ID that it could have had (ambiguity, poll timeout rebuilt to nothing), the adapter result carries an `attribution_note` in `result_summary`; `sessions resume` already warns when no backend ID is present (`cli.py:337`) and will keep that message.

## Risks / Trade-offs

- [OpenCode row creation may be lazy for prompt-less TUI runs] → Poll timeout + post-exit fallback; worst case is a warning, not a wrong ID. Verify behavior at implementation.
- [Slug mapping for Cursor workspaces may be unstable] → Capability check: if slug cannot be derived, skip the filter (behavior equals today's) rather than mis-exclude our own agent.
- [Non-mushi backend sessions created inside our poll window] → Proximity validation reduces; true near-simultaneous foreign spawns may still mislead; ambiguity guard prevents overwriting once attributed.
- [Lock contention adds latency] → Critical section is snapshot+spawn+poll seconds; interactive startups naturally serialize in human terms.
- [Stale lock after crash] → Lock acquisition uses a short-lived lease (threshold timeout, e.g. 30s auto-break) so a killed mushi process cannot wedge subsequent runs.

## Migration Plan

In-place code change; existing session records with correct IDs keep working (resume reads the same keys). Records already polluted with foreign IDs stay as-is - users can `sessions remove` and re-start. Storage schema unchanged; no migration.

## Open Questions

- Exact row-creation timing of OpenCode TUI with and without `--prompt` (affects poll timeout tuning) - verify during implementation with live binary.
- Cursor cwd→slug derivation format - verify during implementation against `~/.cursor/projects/`.
