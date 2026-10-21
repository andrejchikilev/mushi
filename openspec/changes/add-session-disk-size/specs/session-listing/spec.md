## ADDED Requirements

### Requirement: Session list shows disk size
The system SHALL include a human-readable disk-size column for every session shown by `mushi session list`.

#### Scenario: List sessions for a task
- **WHEN** a user runs `mushi session list <task_id>` for a task with sessions
- **THEN** each output row includes the session id, status, task id, human-readable size, and goal

#### Scenario: List all sessions
- **WHEN** a user runs `mushi session list` without a task id
- **THEN** each output row includes the session id, status, task id, human-readable size, and goal for sessions across all tasks

#### Scenario: Backend reports per-session usage
- **WHEN** a listed session belongs to a backend that can report disk usage for that session
- **THEN** the row's size reflects the backend-reported session usage

#### Scenario: Backend cannot report per-session usage
- **WHEN** a listed session belongs to a backend that cannot report disk usage for that session
- **THEN** the row's size falls back to the persisted Mushi session record size

### Requirement: Session size is human-readable
The system SHALL format session sizes using byte-based units (`B`, `KB`, `MB`, `GB`, `TB`) instead of raw byte counts alone.

#### Scenario: Small session file
- **WHEN** a session JSON file is smaller than 1024 bytes
- **THEN** the displayed size uses the `B` unit with no decimal places

#### Scenario: Larger session file
- **WHEN** a session JSON file is 1024 bytes or larger
- **THEN** the displayed size uses the largest appropriate unit and one decimal place

### Requirement: Session listing handles missing size metadata gracefully
The system SHALL continue listing sessions if the size of an individual session file cannot be read.

#### Scenario: Session file cannot be statted
- **WHEN** `mushi session list` cannot read the file size for a listed session
- **THEN** that session row displays `?` for the size and listing continues

### Requirement: Session list shows shared backend storage separately
The system SHALL display shared backend storage as a separate summary when a backend has storage that cannot be safely attributed to individual sessions.

#### Scenario: OpenCode shared database is present
- **WHEN** `mushi session list` lists sessions for the OpenCode backend and the shared OpenCode database exists
- **THEN** the output includes a summary line marked with `*` that shows the human-readable size of `opencode.db`

#### Scenario: OpenCode shared database is absent
- **WHEN** `mushi session list` lists sessions for the OpenCode backend and the shared OpenCode database does not exist
- **THEN** the output does not fail because of the missing database

### Requirement: Removing sessions purges attributable backend storage
The system SHALL purge backend-owned session data when removing sessions if the backend can safely identify that data.

#### Scenario: Remove Cursor-backed session with backend metadata
- **WHEN** a user removes a session whose backend metadata includes a Cursor agent id
- **THEN** the system removes the matching Cursor chat data for that session before completing removal

#### Scenario: Remove Cursor-backed session without backend metadata
- **WHEN** a user removes a session whose backend metadata does not include a Cursor agent id
- **THEN** the system completes removal without failing because there is no attributable Cursor backend data

#### Scenario: Remove task with Cursor-backed sessions
- **WHEN** a user removes a task that has Cursor-backed sessions with Cursor agent ids
- **THEN** the system removes matching Cursor chat data for those sessions before completing task removal

#### Scenario: Remove OpenCode-backed session or task
- **WHEN** a user removes an OpenCode-backed session or task
- **THEN** the system does not delete the shared OpenCode database
