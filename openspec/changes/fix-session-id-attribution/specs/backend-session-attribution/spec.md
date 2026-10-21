## ADDED Requirements

### Requirement: New backend sessions are attributed on spawn
The system SHALL attribute a backend session ID to a mushi session by identifying exactly the backend session created for that invocation, using a pre-spawn snapshot of existing backend session IDs and a serialized spawn window that excludes overlapping attributions of other mushi agents.

#### Scenario: Single new backend session
- **WHEN** mushi starts a session and exactly one new backend session matching the workspace is created for that invocation
- **THEN** that backend session ID is recorded in the session record under `invocation`

#### Scenario: Concurrent mushi agents
- **WHEN** two or more mushi agents run concurrently through the same adapter and both finish
- **THEN** each session record contains the backend session ID created for its own invocation

#### Scenario: Foreign session created during the window
- **WHEN** a backend session not started by mushi is created while a mushi agent is starting
- **THEN** the mushi agent's attribution keeps its own backend session ID and excludes the foreign one when its creation time is distinguishable from the spawn instant

### Requirement: Ambiguous attribution fails safe
The system SHALL NOT record any backend session ID when attribution is ambiguous, and SHALL surface a warning instead of choosing a most-recent candidate.

#### Scenario: Multiple indistinguishable candidates
- **WHEN** more than one new backend session exists in the window and creation times or workspace matching cannot identify the invocation's own session
- **THEN** the session record is stored without a backend session ID and the result notes the ambiguity

#### Scenario: Resume of an unattributed session
- **WHEN** a user resumes a session without a recorded backend session ID
- **THEN** the CLI warns that a new backend session may be started

### Requirement: Known backend session IDs survive resume
The system SHALL retain an already-recorded backend session ID when resuming a session, regardless of post-exit detection results.

#### Scenario: Resume with no new backend session detected
- **WHEN** a session resumed with a known backend session ID finishes and no new backend sessions are detected afterwards
- **THEN** the session record still contains the same backend session ID

#### Scenario: Detection returns multiple candidates during resume
- **WHEN** a resumed session's post-exit detection finds other new backend sessions
- **THEN** detection results do not overwrite the recorded backend session ID

### Requirement: Cursor attribution is workspace-scoped
The system SHALL restrict cursor agent attribution candidates to agents belonging to the invoked workspace when the workspace can be identified.

#### Scenario: Concurrent cursor agents in different workspaces
- **WHEN** two cursors agents run at the same time in different projects and one finishes
- **THEN** only agents matching the finishing workspace are considered candidates

#### Scenario: Workspace cannot be identified
- **WHEN** the workspace for a cursor agent cannot be mapped
- **THEN** attribution proceeds without workspace filtering rather than excluding the invocation's own agent
