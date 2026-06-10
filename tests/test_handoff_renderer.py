"""Tests for HandoffData markdown renderer."""

import dataclasses
from datetime import UTC, datetime

from mushi.core.handoffs import HandoffData, HandoffEvent, HandoffRenderer, HandoffSession


def _sample_data(*, notes: str = "") -> HandoffData:
    return HandoffData(
        task_id="task-1",
        task_title="Design storage",
        task_status="done",
        created_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 6, 1, 14, 0, tzinfo=UTC),
        tags=("phase2", "storage"),
        task_metadata={"key": "value"},
        sessions=(
            HandoffSession(
                id="session-1",
                backend="opencode",
                profile="default",
                goal="Implement storage layer",
                status="succeeded",
                started_at=datetime(2026, 6, 1, 12, 30, tzinfo=UTC),
                ended_at=datetime(2026, 6, 1, 13, 0, tzinfo=UTC),
                result_summary="All tests pass",
                backend_version="1.0.0",
                transcript_refs=("/tmp/transcript.log",),
            ),
        ),
        events=(
            HandoffEvent(
                kind="created",
                summary="Task created",
                created_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
                session_id=None,
            ),
            HandoffEvent(
                kind="session_started",
                summary="Session started with opencode using profile default",
                created_at=datetime(2026, 6, 1, 12, 30, tzinfo=UTC),
                session_id="session-1",
            ),
        ),
        user_notes=notes,
    )


def test_renderer_includes_header() -> None:
    md = HandoffRenderer().render(_sample_data())

    assert "# Handoff: Design storage" in md
    assert "`task-1`" in md
    assert "done" in md
    assert "phase2" in md
    assert "storage" in md


def test_renderer_includes_summary() -> None:
    md = HandoffRenderer().render(_sample_data())

    assert "## Summary" in md
    assert "1 session(s), 1 completed" in md
    assert "2 history event(s)" in md


def test_renderer_includes_session_table() -> None:
    md = HandoffRenderer().render(_sample_data())

    assert "## Sessions" in md
    assert "| Session | Backend | Profile | Status | Goal | Result |" in md
    assert "opencode" in md
    assert "succeeded" in md
    assert "All tests pass" in md


def test_renderer_includes_history_timeline() -> None:
    md = HandoffRenderer().render(_sample_data())

    assert "## History" in md
    assert "Task created" in md
    assert "Session started with opencode" in md
    assert "session: `session-1`" in md


def test_renderer_includes_user_notes() -> None:
    md = HandoffRenderer().render(_sample_data(notes="Fixed edge case"))

    assert "## User Notes" in md
    assert "Fixed edge case" in md


def test_renderer_shows_placeholder_for_empty_notes() -> None:
    md = HandoffRenderer().render(_sample_data())

    assert "—" in md
    assert "## User Notes" in md


def test_renderer_includes_provenance() -> None:
    md = HandoffRenderer().render(_sample_data())

    assert "## Provenance" in md
    assert "task `task-1`" in md
    assert "1 session(s)" in md


def test_renderer_handles_no_sessions() -> None:
    data = dataclasses.replace(_sample_data(), sessions=())
    md = HandoffRenderer().render(data)

    assert "No sessions recorded" in md


def test_renderer_handles_no_events() -> None:
    data = dataclasses.replace(_sample_data(), events=())
    md = HandoffRenderer().render(data)

    assert "No events recorded" in md
