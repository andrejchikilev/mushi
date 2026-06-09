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

Deliverables:
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

Deliverables:
- Adapter interface for availability checks, capability reporting, invocation, transcript/reference capture, and normalized result status.
- Cursor CLI adapter implementation.
- OpenCode adapter implementation.
- Backend capability model for differences such as resume support or transcript export.
- Adapter tests using fakes or command shims so verification does not require live agent credentials.

Risks:
- Real backend CLIs may change flags, output formats, or transcript behavior.
- Treating Cursor CLI or OpenCode as the default model could block future Claude Code, Codex, or Aider support.
- Live integration tests may be flaky, expensive, or environment-dependent.

Dependencies:
- Phase 3 session workflow and profile resolution.
- Local availability of Cursor CLI and OpenCode only for manual or optional integration checks.

## Phase 5: Handoff Generation

Goal: Generate useful, backend-neutral handoffs from persisted task context, session summaries, history, and selected transcript references.

Deliverables:
- Handoff template or rendering pipeline.
- Handoff generation command or API for a task.
- Handoff records stored separately from source-of-truth task and session records.
- Redaction pass for sensitive metadata before handoff output.
- Tests for handoff content, provenance links, missing summaries, and backend-neutral output.

Risks:
- Handoffs may become too verbose to be useful for agents.
- Backend transcript parsing can pull the core toward backend-specific formats.
- Missing redaction could persist secrets in generated documents.

Dependencies:
- Phase 2 storage for handoff records.
- Phase 3 task/session summaries.
- Phase 4 adapter-provided transcript references or excerpts where available.

## Phase 6: Search

Goal: Make stored task context discoverable through simple, rebuildable search over primary records and generated handoffs.

Deliverables:
- Search API or CLI over task titles, statuses, tags, backend, profile, repository path, summaries, notes, and handoffs.
- Simple filesystem scan or rebuildable index.
- Filters for time range, backend, profile, and task status.
- Rebuild command for derived search data if an index is introduced.
- Tests proving search works after derived data is deleted and rebuilt.

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
