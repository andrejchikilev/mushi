# Architecture

Mushi is a persistent task and session manager for coding agents. It should remain agent-agnostic: Cursor CLI and OpenCode are initial backends, but core task state must not depend on either backend's internal format.

## Design Goals
- Keep durable state in simple filesystem data that can be inspected, backed up, diffed, and migrated.
- Separate Mushi's domain model from backend-specific command execution and transcript formats.
- Preserve enough session metadata to resume work, generate handoffs, and search historical context.
- Favor explicit data schemas and small adapter boundaries over implicit coupling to one agent.

## Core Concepts
- Task: a long-lived unit of work with stable identity, title, status, history, and links to sessions.
- Session: one interaction or execution span for a task, including backend, profile, timestamps, workspace path, and outcome metadata.
- Profile: named configuration for how a backend should run, such as model, permissions, environment assumptions, or prompt defaults.
- Backend adapter: the only layer that knows how to invoke or interpret a specific coding agent backend.
- Handoff: a generated summary that lets another session or backend resume with relevant context and next steps.

## Filesystem Storage
Mushi should store primary state on disk rather than requiring a service database for the MVP. The storage layout should optimize for clarity and migration safety.

Recommended durable data categories:
- Task records containing task identity, status, metadata, and references to related sessions.
- Session records containing backend, profile, timestamps, workspace path, command metadata, and result summaries.
- Append-only event or history records for meaningful task changes.
- Handoff documents generated from task and session history.
- Search indexes or caches that can be rebuilt from primary records.

Primary records should be treated as source of truth. Derived files, indexes, and caches should be safe to delete and rebuild.

## Session Metadata
Every session should record enough metadata to understand what happened without knowing backend internals.

Minimum useful metadata:
- Session id and task id.
- Backend name and backend version when available.
- Profile name and resolved profile settings that affect behavior.
- Workspace path and relevant repository identity.
- Start time, end time, and final status.
- User-provided goal or prompt.
- Backend command or invocation metadata when safe to persist.
- Links to transcripts, handoffs, generated artifacts, or follow-up tasks.

Sensitive values should not be persisted unless explicitly intended. Environment variables, tokens, and private credentials should be redacted from metadata and generated handoffs.

## Profile Support
Profiles should define reusable execution preferences without changing task data. A profile should be referenced by name from session metadata, and sessions should capture the resolved settings needed for later auditability.

Profiles may include:
- Backend selection.
- Model or effort settings when supported by the backend.
- Permission and sandbox expectations.
- Default handoff or summary style.
- Workspace-specific defaults.

The core profile model should allow unknown backend-specific settings to be passed through to adapters without making the core depend on those settings.

## Backend Adapters
Backend adapters isolate all backend-specific behavior from storage, task management, search, and handoff generation.

Adapter responsibilities:
- Validate that the backend is available.
- Translate a Mushi session request into the backend's invocation format.
- Capture backend outputs or transcript references.
- Normalize completion status and basic result metadata.
- Expose backend capabilities such as resume support, transcript export, or profile options.

Initial supported adapters:
- Cursor CLI.
- OpenCode.

Future adapters should fit the same boundary:
- Claude Code.
- Codex.
- Aider.

The core should never branch deeply on backend-specific details. Prefer capability checks and adapter-owned translation.

## Handoff Generation
Handoffs are generated artifacts built from task records, session metadata, selected transcript context, and explicit user notes. They should be useful when switching agents, resuming later, or delegating work.

A handoff should include:
- Task goal and current status.
- Relevant decisions and constraints.
- Completed work and changed files when known.
- Open questions, blockers, and next steps.
- Backend/session provenance.
- Searchable references to source sessions or events.

Handoff generation should not require a specific backend transcript format. Backend adapters can provide transcript extraction, but the handoff builder should consume normalized session data and selected text.

## Search
Search should work across persisted task context, session metadata, handoffs, and selected transcript content. Filesystem records are the source of truth; indexes are derived acceleration structures.

Search should support:
- Finding tasks by title, status, tags, backend, profile, or repository path.
- Full-text search across summaries, handoffs, and stored notes.
- Filtering by time range, backend, profile, and task status.
- Rebuilding indexes from primary records.

The MVP can use simple filesystem scanning before introducing a dedicated indexing library. If an index is added later, it should remain replaceable.

## Maintainability Principles
- Keep schemas explicit and versioned so stored data can migrate safely.
- Treat backend adapters as plugins around a stable core model.
- Make primary data human-readable unless there is a strong reason not to.
- Avoid coupling task identity or session identity to backend transcript ids.
- Prefer append-friendly history for auditability and recovery.
- Keep generated artifacts separate from source-of-truth records.
