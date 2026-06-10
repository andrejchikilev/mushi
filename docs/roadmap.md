# Implementation Roadmap

This roadmap turns the architecture and MVP scope into implementation phases. The ordering intentionally establishes durable data contracts before backend execution, handoff generation, or search indexing.

## Phase 0: Project Foundation

Goal: Establish the repository baseline needed to implement and verify Mushi consistently.

Deliverables:
- Chosen language/toolchain and package manifest.
- Basic CLI or library entrypoint decision.
- Test runner, formatter, lint/typecheck commands, and documented verification flow.
- Minimal project layout for core domain, storage, adapters, and CLI boundaries.

Risks:
- Picking tooling before core requirements are clear can create churn.
- Missing verification commands will make future adapter and storage changes risky.
- Overbuilding framework structure can slow the MVP.

Dependencies:
- Existing `README.md`, `docs/architecture.md`, and `docs/mvp-scope.md`.

## Phase 1: Domain Model and Schemas

Goal: Define stable task, session, profile, event, handoff, and search-record contracts before writing storage or adapter logic.

Deliverables:
- Versioned schemas for task records, session records, profile definitions, history events, and handoff metadata.
- Status enums or equivalent constrained values for tasks and sessions.
- Identifier strategy for tasks and sessions that does not depend on backend ids.
- Redaction rules for sensitive metadata.
- Schema validation tests using representative valid and invalid records.

Risks:
- Persisted schemas are expensive to change after users create data.
- Too much backend-specific metadata in core schemas would weaken agent agnosticism.
- Too little metadata would make resume, search, and handoff workflows unreliable.

Dependencies:
- Phase 0 toolchain and verification flow.

## Phase 2: Filesystem Storage

Goal: Implement source-of-truth persistence for tasks, sessions, profiles, handoffs, and append-friendly history.

### Phase 2.1: Storage Layout Contract

Goal: Define the on-disk structure without implementing read/write behavior.

Deliverables:
- Documented storage root layout for tasks, sessions, events, profiles, handoffs, and derived data.
- Pure path-building helpers for each primary record type.
- Explicit rule that derived directories are rebuildable and not source of truth.
- Tests for path generation using temporary roots and stable ids.
- Manual test guide in `.mushi-dev/manual-test-phase-2-1.md`.

Risks:
- A vague layout will leak into later APIs and be hard to migrate.
- Putting derived data beside primary records can make source-of-truth boundaries unclear.

Dependencies:
- Phase 1 record ids and schema categories.

### Phase 2.2: JSON Serialization Boundary

Goal: Convert Phase 1 records to and from filesystem-safe JSON consistently.

Deliverables:
- Shared serialization/deserialization helpers for Pydantic records.
- Schema validation on load.
- Consistent datetime JSON behavior.
- Tests for valid round trips and invalid JSON/schema failures.
- Manual test guide in `.mushi-dev/manual-test-phase-2-2.md`.

Risks:
- Inconsistent serialization will make future migrations difficult.
- Silent acceptance of unknown fields can hide corrupted or stale records.

Dependencies:
- Phase 2.1 path helpers.
- Phase 1 schemas with `extra="forbid"` validation.

### Phase 2.3: Atomic File Writes

Goal: Add safe write primitives before storing real records.

Deliverables:
- Atomic write helper using a temporary file followed by replace.
- Parent directory creation for writes.
- Read helper with clear missing-file and invalid-file errors.
- Tests for successful writes, overwrites, missing files, and cleanup of failed temp writes where practical.
- Manual test guide in `.mushi-dev/manual-test-phase-2-3.md`.

Risks:
- Partial writes can corrupt long-lived task context.
- Low-level errors can become hard to diagnose if exceptions are too generic.

Dependencies:
- Phase 2.2 serialization helpers.

### Phase 2.4: Task Storage

Goal: Persist and retrieve `TaskRecord` as the first source-of-truth record.

Deliverables:
- Save/load task operations.
- Task existence check.
- List task ids or records from the storage root.
- Tests for create, overwrite/update, load missing task, list empty storage, and list multiple tasks.
- Manual test guide in `.mushi-dev/manual-test-phase-2-4.md`.

Risks:
- Listing behavior can accidentally depend on directory ordering.
- Updating full records without care can hide future concurrency issues.

Dependencies:
- Phase 2.3 atomic file writes.

### Phase 2.5: Session and Profile Storage

Goal: Persist session metadata and profile definitions without invoking backends.

Deliverables:
- Save/load session operations scoped by task id and session id.
- Save/load/list profile operations.
- Tests for session round trips, missing task/session paths, profile round trips, and invalid loaded records.
- Manual test guide in `.mushi-dev/manual-test-phase-2-5.md`.

Risks:
- Session storage may accidentally assume backend-specific transcript formats.
- Profile storage may fail to preserve unknown backend-specific settings.

Dependencies:
- Phase 2.4 task storage.

### Phase 2.6: Append-Only History Events

Goal: Store meaningful task history without rewriting prior events.

Deliverables:
- Append event operation for `HistoryEvent`.
- List events for a task in deterministic order.
- Duplicate event id behavior defined and tested.
- Tests for append, list empty history, ordering, and invalid event records.
- Manual test guide in `.mushi-dev/manual-test-phase-2-6.md`.

Risks:
- Mutable history weakens auditability.
- Ordering by filename rather than event timestamp can produce confusing histories unless defined explicitly.

Dependencies:
- Phase 2.4 task storage.
- Phase 2.3 atomic file writes.

### Phase 2.7: Handoff Metadata and Derived Data Boundaries

Goal: Persist handoff metadata and prove derived data is optional.

Deliverables:
- Save/load handoff metadata operations.
- Reserved derived-data paths for future search indexes and caches.
- Tests that primary record operations work when derived directories are missing or deleted.
- Tests for handoff metadata round trips and missing handoff errors.
- Manual test guide in `.mushi-dev/manual-test-phase-2-7.md`.

Risks:
- Generated handoff documents can be confused with handoff metadata source of truth.
- Derived data may accidentally become required by primary storage tests.

Dependencies:
- Phase 2.3 atomic file writes.
- Phase 2.5 session storage.

Deliverables for the full phase:
- Filesystem layout for primary records and derived data.
- Read/write/update operations for task records.
- Read/write operations for session metadata and profile definitions.
- Append-only history/event writing for meaningful task changes.
- Atomic write or safe-write behavior for primary records.
- Storage tests for round trips, missing files, invalid records, and rebuild-safe derived directories.

Risks:
- Unsafe writes can corrupt long-lived task context.
- Ambiguous layout can make migration and manual inspection difficult.
- Derived search or cache data may accidentally become required source of truth.

Dependencies:
- Phase 1 schemas and validation rules.

## Phase 3: Task and Session Workflows

Goal: Provide the core workflows for creating tasks, recording sessions, and inspecting persisted state without invoking real agent backends yet.

### Phase 3.1: Task Workflow Service

Goal: Add storage-backed task operations without CLI concerns.

Deliverables:
- Create task operation with explicit task id and title.
- Update task status operation.
- List and show task operations backed by `FilesystemStorage`.
- History events for task creation and status changes.
- Tests for create, duplicate task rejection, status update, list, show, and missing task behavior.
- Manual test guide in `.mushi-dev/manual-test-phase-3-1.md`.

Risks:
- Workflow code may duplicate storage behavior instead of enforcing task lifecycle rules.
- Event history can drift from task updates if not written in the same workflow operation.

Dependencies:
- Phase 2 task storage and append-only events.

### Phase 3.2: Profile Resolution Service

Goal: Resolve profile settings for sessions without invoking backends.

Deliverables:
- Create or save profile workflow.
- Resolve profile by name into backend plus settings snapshot.
- Clear error when a requested profile is missing.
- Tests for profile creation, resolution, missing profiles, and preserving backend-specific settings.
- Manual test guide in `.mushi-dev/manual-test-phase-3-2.md`.

Risks:
- Resolved settings may be hard to audit if sessions only reference a profile name.
- Profile logic can accidentally validate backend-specific settings that should remain adapter-owned.

Dependencies:
- Phase 2 profile storage.

### Phase 3.3: Session Recording Workflow

Goal: Record planned/started and finished session metadata with a no-backend path.

Deliverables:
- Start session operation that records backend, profile, workspace, goal, timestamps, and resolved profile settings.
- Finish session operation that records final status and result summary.
- Task `session_ids` update when a session starts.
- History events for session start and finish.
- Tests for start, finish, task linkage, missing task, missing profile, and invalid finish status.
- Manual test guide in `.mushi-dev/manual-test-phase-3-3.md`.

Risks:
- Session workflow may assume synchronous backend execution before adapters exist.
- Updating task and session records separately can leave inconsistent state if one write succeeds and another fails.

Dependencies:
- Phase 3.1 task workflow service.
- Phase 3.2 profile resolution service.

### Phase 3.4: Minimal CLI Wiring

Goal: Expose task/profile/session workflows through simple Typer commands.

Deliverables:
- `task create`, `task list`, `task show`, and `task status` commands.
- `profile set` and `profile show` commands.
- `session start` and `session finish` commands that only record metadata.
- Storage root option or environment variable for tests and manual use.
- CLI tests using isolated temporary storage roots.
- Manual test guide in `.mushi-dev/manual-test-phase-3-4.md`.

Risks:
- CLI argument choices can become hard to change once documented.
- Exposing too much storage detail through CLI can constrain future workflow design.

Dependencies:
- Phases 3.1 through 3.3.

### Phase 3.5: Workflow Documentation and Verification

Goal: Document the manual Phase 3 smoke path and verify end-to-end metadata recording.

Deliverables:
- README or docs update with exact `uv run mushi ...` examples for Phase 3 commands.
- Tests covering a create-task, create-profile, start-session, finish-session flow.
- Manual test guide in `.mushi-dev/manual-test-phase-3-5.md`.
- Updated `AGENTS.md` only if verification commands change.

Risks:
- Docs can imply backend execution exists when Phase 3 only records metadata.
- End-to-end tests can become brittle if they assert presentation details instead of persisted behavior.

Dependencies:
- Phase 3.4 CLI wiring.

Deliverables:
- Create, update, list, and show task operations.
- Start/finish session metadata operations using a stub or no-op backend path.
- Profile resolution and recording of resolved session-affecting settings.
- Result summary storage for completed sessions.
- Focused tests for task lifecycle, session lifecycle, and profile resolution.

Risks:
- CLI or API design may leak storage details too early.
- Session workflows may assume synchronous backend behavior that future adapters cannot satisfy.
- Profile resolution may become hard to audit if resolved values are not persisted.

Dependencies:
- Phase 2 filesystem storage.

## Phase 4: Backend Adapter Boundary

Goal: Create the backend adapter interface and implement Cursor CLI and OpenCode adapters behind the same core contract.

### Phase 4.1: Adapter Protocol and Capability Model

Goal: Define the abstract adapter contract and backend capability model without implementing any real CLI invocation.

Deliverables:
- Abstract adapter protocol or ABC with methods for availability check, capability reporting, invocation, transcript reference capture, and normalized result status.
- Backend capability enum or frozen set model for differences such as resume support or transcript export.
- Canonical adapter result type with status, transcript ref, backend version, and optional error details.
- Stub adapter that implements the protocol for testing.
- Tests that exercise the full protocol through the stub adapter.
- Manual test guide in `.mushi-dev/manual-test-phase-4-1.md`.

Risks:
- Overly abstract interface may not fit all future backend (Claude Code, Codex, Aider) special cases.
- Capability model that is too specific to Cursor/OpenCode may misrepresent Claude Code or Codex.
- Using ABC may make adapter registration harder than a simpler Protocol-based design.

Dependencies:
- Phase 3 session workflow and profile resolution.

### Phase 4.2: Cursor CLI Adapter

Goal: Implement the Cursor CLI adapter behind the Phase 4.1 protocol contract.

Deliverables:
- `CursorCliAdapter` implementing the adapter protocol.
- Availability check by probing `cursor --version` or equivalent.
- Command invocation building: construct `cursor` CLI arguments from profile settings.
- Capture of stdout/stderr and transcript file reference when available.
- Normalization of exit code into an adapter result status.
- Shim-based tests that replace the real `cursor` binary with a controlled script returning known output and exit codes.
- Manual test guide in `.mushi-dev/manual-test-phase-4-2.md`.

Risks:
- `cursor` CLI flags and output format may change between versions without notice.
- The real CLI may require authentication or a running daemon, making shim-only tests insufficient for full coverage.
- Transcript file location or format may be undocumented or version-dependent.

Dependencies:
- Phase 4.1 adapter protocol and capability model.

### Phase 4.3: OpenCode Adapter

Goal: Implement the OpenCode CLI adapter behind the same Phase 4.1 protocol contract.

Deliverables:
- `OpenCodeAdapter` implementing the adapter protocol.
- Availability check by probing `opencode --version` or equivalent.
- Command invocation building from profile settings.
- Capture of stdout/stderr and transcript reference.
- Normalization of exit code into adapter result status.
- Shim-based tests with a controlled script replacing the real `opencode` binary.
- Manual test guide in `.mushi-dev/manual-test-phase-4-3.md`.

Risks:
- `opencode` CLI flags and output format may change between versions.
- The real CLI may behave differently depending on environment variables and installed plugins.
- OpenCode's session/transcript model may differ substantially from Cursor's.

Dependencies:
- Phase 4.1 adapter protocol and capability model.

### Phase 4.4: CLI Integration

Goal: Wire the backend adapters into the existing `session start` workflow so that a real or shim backend is invoked and its result is recorded.

Deliverables:
- Backend lookup by name from session profile (e.g., `opencode` → `OpenCodeAdapter`).
- Session workflow integration: on `session start`, resolve adapter, check availability, invoke backend, record result.
- Fallback or stub adapter for backends not yet implemented.
- CLI tests using shim backend that verify the full invocation flow through the existing `session start`/`session finish` commands.
- Error handling: missing backend, unavailable backend, non-zero exit, timeout.
- Manual test guide in `.mushi-dev/manual-test-phase-4-4.md`.

Risks:
- Real backend execution during tests would make tests slow, flaky, and environment-dependent.
- Session workflow changes may break the Phase 3 contract of metadata-only recording before backends exist.
- The integration layer may need to handle long-running backends asynchronously in the future.

Dependencies:
- Phase 4.2 Cursor CLI adapter.
- Phase 4.3 OpenCode adapter.
- Phase 3.3 session recording workflow.
- Phase 3.4 CLI wiring.

### Phase 4.5: Test Hardening and Manual Smoke Guide

Goal: Validate the adapter boundary end-to-end with optional live integration checks and document manual verification steps.

Deliverables:
- Optional pytest markers (`pytest.mark.live`) for tests that require real `cursor` or `opencode` binaries.
- Shim adapter tests running in CI without live backends.
- Manual test guide in `.mushi-dev/manual-test-phase-4-5.md` covering: shim invocation, live availability check, transcript capture inspection, and cleanup.
- Updated `AGENTS.md` if adapter CLI commands or verification flows changed.

Risks:
- Live integration tests may be skipped locally, masking regressions in real CLI interaction.
- Manual test guide may drift from actual CLI behavior if backend versions change.

Dependencies:
- Phase 4.4 CLI integration.

## Phase 5: Handoff Generation

Goal: Generate useful, backend-neutral handoffs from persisted task context, session summaries, history, and selected transcript references.

### Phase 5.1: Handoff Data Builder

Goal: Collect task metadata, session summaries, events, and user notes into a structured handoff data object.

Deliverables:
- `HandoffData` frozen dataclass with fields for task info, session summaries, events, notes.
- `HandoffBuilder` service that collects data from storage by task id.
- Builder interface for optionally including session transcripts and user notes.
- Tests for structured data output with known task, sessions, and events.
- Manual test guide in `.mushi-dev/manual-test-phase-5-1.md`.

Risks:
- Building handoffs may pull too much data into memory for large histories.
- Backend-specific transcript formats may leak into the handoff data model.

Dependencies:
- Phase 2 task storage, session storage, event storage.
- Phase 3 task/session workflows.

### Phase 5.2: Handoff Markdown Renderer

Goal: Render a `HandoffData` object into a human-readable markdown handoff document.

Deliverables:
- `HandoffRenderer` that converts `HandoffData` to a markdown string.
- Sections: task summary, status, history timeline, session table, user notes.
- The output is backend-neutral and contains provenance links.
- Tests for expected markdown structure, missing data handling, and large history rendering.
- Manual test guide in `.mushi-dev/manual-test-phase-5-2.md`.

Risks:
- Markdown format may need to change as handoff requirements evolve.
- Rendering without a template engine may be inflexible for future formats.

Dependencies:
- Phase 5.1 handoff data builder.

### Phase 5.3: Handoff Workflow Service

Goal: Combine builder, renderer, and storage into a single handoff generation workflow.

Deliverables:
- `HandoffWorkflow` that orchestrates building, rendering, redacting, and persisting.
- Generated handoff markdown file written to a configurable directory.
- `HandoffMetadata` record saved alongside the generated document.
- Redaction pass applied to `metadata` fields and user notes before rendering.
- Tests for full generation flow: build → redact → render → save.
- Manual test guide in `.mushi-dev/manual-test-phase-5-3.md`.

Risks:
- Redaction before rendering may miss sensitive content in session summaries.
- Separating metadata storage from document storage can lead to drift.

Dependencies:
- Phase 5.1 handoff data builder.
- Phase 5.2 handoff renderer.
- Phase 2.7 handoff metadata storage.

### Phase 5.4: CLI Wiring

Goal: Expose handoff generation through CLI commands.

Deliverables:
- `handoff create <task-id>` command that generates a handoff and shows its path.
- `handoff show <handoff-id>` command that prints the markdown content.
- Handoff output directory option or default (e.g., `.mushi/handoffs/`).
- CLI tests using isolated storage and known task data.
- Manual test guide in `.mushi-dev/manual-test-phase-5-4.md`.

Risks:
- Handoff output path should not conflict with handoff metadata storage path.
- CLI output may become verbose for large handoffs.

Dependencies:
- Phase 5.3 handoff workflow service.
- Phase 3.4 CLI wiring infrastructure.

### Phase 5.5: Test Hardening and Documentation

Goal: Cover edge cases, verify redaction, and document manual smoke tests.

Deliverables:
- Edge case tests: empty task history, missing sessions, very long summaries.
- Redaction tests confirming sensitive keys are not present in rendered output.
- Manual smoke guide in `.mushi-dev/manual-test-phase-5-5.md`.
- Updated `AGENTS.md` if CLI commands changed.

Risks:
- Redaction tests may produce false positives if backends use different naming conventions.
- Long handoffs may be impractical to assert verbatim in tests.

Dependencies:
- Phase 5.4 CLI wiring.

### Phase 5.6: Session Resume Workflow

Goal: Allow a new session to resume context from a previous session or generated handoff.

Deliverables:
- `session resume` CLI command that creates a new session pre-populated with context from a prior session.
- `OpenCodeAdapter._build_invoke_args` extended to accept optional `context: str` appended to `--prompt`.
- `SessionWorkflow.start_session` accepts optional `previous_session_id` and `context` for adapter invocation.
- Context gathering: load previous session `result_summary` or generate a handoff inline and pass it to the adapter.
- If no adapter is available (test-backend), context is stored in the session record but not passed anywhere.
- CLI tests using a shim adapter that captures the received prompt and confirms context is included.
- Manual test guide in `.mushi-dev/manual-test-phase-5-6.md`.

Risks:
- Long handoff text may exceed CLI argument length limits; might need file-based context passing.
- Different backends may have different prompt/context passing mechanisms (Cursor vs OpenCode).
- Resuming without a handoff provides less useful context than resuming with one.

Dependencies:
- Phase 5.5 CLI wiring for handoff creation.
- Phase 5.1 handoff data builder (for inline context generation).
- Phase 4 adapter invoke interface (context passing).

## Phase 6: Search

Goal: Make stored task context discoverable through simple, rebuildable search over primary records and generated handoffs.

Deliverables:
- Search API or CLI over task titles, statuses, tags, backend, profile, repository path, summaries, notes, and handoffs.
- Simple filesystem scan or rebuildable index.
- Filters for time range, backend, profile, and task status.
- Rebuild command for derived search data if an index is introduced.
- Tests proving search works after derived data is deleted and rebuilt.
- Manual test guide in `.mushi-dev/manual-test-phase-6.md`.

Risks:
- Premature indexing complexity can make storage harder to evolve.
- Search results may become inconsistent if derived data is not clearly rebuildable.
- Transcript content can be large or sensitive if indexed without limits and redaction.

Dependencies:
- Phase 2 primary storage.
- Phase 5 handoff records.
- Redaction rules from Phase 1.

## Phase 7: MVP Hardening

Goal: Validate the end-to-end MVP against real workflows and document operational expectations.

Deliverables:
- End-to-end flow: create task, run session with Cursor CLI or OpenCode, record result, generate handoff, search prior context.
- Error handling for missing backends, invalid profiles, corrupted records, and unavailable workspaces.
- Migration placeholder or first migration mechanism for schema versions.
- User-facing setup and usage documentation.
- `workspace_path` in `session start` and `session resume` made optional, defaulting to `Path.cwd()`.
- Install workflow: `uv tool install .` for system-wide use, `uv sync` for dev mode.
- README section with install instructions and CLI examples without explicit `$PWD`.
- Manual test guide in `.mushi-dev/manual-test-phase-7.md`.
- Updated `AGENTS.md` with exact setup and verification commands once the toolchain exists.

Risks:
- Real backend behavior may expose gaps in the adapter contract.
- Migration support may be deferred too long once real data exists.
- Documentation can drift from executable commands if not updated with implementation.

Dependencies:
- Phases 0 through 6.
- Access to at least one supported backend for manual end-to-end validation.

## Post-MVP Candidates

Goal: Expand capability without compromising the core filesystem-first, agent-agnostic model.

Deliverables:
- Claude Code, Codex, and Aider adapters using the same adapter boundary.
- Richer transcript extraction through adapter capabilities.
- More advanced search ranking or optional index backends.
- Optional UI once CLI/library workflows are stable.
- Optional sync or collaboration design after local storage semantics are proven.

Risks:
- New backends may pressure the core schema with backend-specific concepts.
- Advanced search or sync may require stronger consistency guarantees than the MVP storage layout provides.
- UI work can hide unresolved core workflow problems.

Dependencies:
- Stable MVP workflows and schema versioning.
- Clear adapter capability model from Phase 4.
