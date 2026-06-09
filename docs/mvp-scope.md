# MVP Scope

The MVP should prove that Mushi can persist task context, resume work across agent sessions, and move context between Cursor CLI and OpenCode without binding the core model to either backend.

## In Scope
- Filesystem-based storage for tasks, sessions, profiles, handoffs, and rebuildable search data.
- A stable task model with id, title, status, timestamps, metadata, and session references.
- Session metadata for backend, profile, workspace path, prompt or goal, timestamps, status, and result summary.
- Profile support for reusable backend execution settings.
- Backend adapter interfaces for Cursor CLI and OpenCode.
- Basic handoff generation from task metadata, session summaries, and user-provided notes.
- Basic search over task records, session metadata, summaries, and handoffs.
- Clear schema/version markers for persisted records.

## Out of Scope for MVP
- Implementing Claude Code, Codex, or Aider backends.
- Remote synchronization or multi-user collaboration.
- A hosted service, daemon, or database requirement.
- Rich terminal UI or web UI.
- Automatic semantic understanding of every backend transcript format.
- Complex ranking, embeddings, or vector search.
- Plugin marketplace or third-party adapter loading.
- Secret management beyond avoiding accidental persistence of sensitive values.

## MVP Workflows
- Create a task with a durable id and initial goal.
- Start a session for a task using a selected profile and backend.
- Record session metadata and a short result summary.
- Append meaningful task history as the task changes.
- Generate a handoff for another agent or later session.
- Search prior task context by keyword and metadata filters.
- Rebuild derived search data from filesystem records.

## Backend Expectations
Cursor CLI and OpenCode support should be implemented through adapters with the same core interface. The MVP should validate backend availability, invoke the selected backend, and normalize basic session results.

The MVP does not need perfect feature parity between backends. Differences should be represented as adapter capabilities rather than special cases in task storage.

## Storage Expectations
The filesystem layout should keep source-of-truth records separate from generated or derived data. Records should be readable and migration-friendly.

Required persisted records:
- Task metadata.
- Session metadata.
- Profile definitions.
- Handoff documents.

Derived data:
- Search indexes.
- Cached transcript excerpts.
- Generated summaries that can be recreated from primary records when possible.

## Success Criteria
- A task can be created, updated, and inspected after the original agent session ends.
- A session can be recorded with enough metadata to understand backend, profile, workspace, status, and outcome.
- Cursor CLI and OpenCode are both represented through adapters rather than hard-coded throughout the core.
- A handoff can be generated that is useful to another backend.
- Search can find previous tasks and handoffs from stored filesystem data.
- Adding a future backend should not require changing the task or session storage schema for ordinary use.

## Deferral Triggers
- If a feature requires backend-specific transcript parsing, defer it unless it can be expressed through adapter capabilities.
- If a feature requires a service database, defer it unless filesystem storage has clearly become insufficient.
- If a feature requires storing secrets, defer it until an explicit secret handling design exists.
- If search quality requires complex ranking, start with simple scan/index behavior and keep the index replaceable.
