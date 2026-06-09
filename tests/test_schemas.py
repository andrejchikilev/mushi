from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from mushi.core.schemas import (
    EventKind,
    HandoffMetadata,
    HistoryEvent,
    ProfileDefinition,
    SearchRecord,
    SessionRecord,
    SessionStatus,
    TaskRecord,
    TaskStatus,
    redact_metadata,
)


def test_task_record_defaults_and_serialization() -> None:
    task = TaskRecord(id="task-1", title="Design storage")

    data = task.model_dump(mode="json")

    assert data["schema_version"] == 1
    assert data["status"] == TaskStatus.OPEN
    assert data["session_ids"] == []


def test_task_record_rejects_empty_title() -> None:
    with pytest.raises(ValidationError):
        TaskRecord(id="task-1", title="")


@pytest.mark.parametrize("bad_id", ["../outside", "task/child", ".hidden", ""])
def test_task_record_rejects_path_unsafe_ids(bad_id: str) -> None:
    with pytest.raises(ValidationError):
        TaskRecord(id=bad_id, title="Design storage")


def test_session_record_rejects_ended_before_started() -> None:
    started_at = datetime(2026, 1, 1, tzinfo=UTC)

    with pytest.raises(ValidationError):
        SessionRecord(
            id="session-1",
            task_id="task-1",
            backend="opencode",
            profile="default",
            workspace_path="/repo",
            goal="Continue task",
            status=SessionStatus.FAILED,
            started_at=started_at,
            ended_at=started_at - timedelta(seconds=1),
        )


def test_phase_one_records_accept_minimal_valid_data() -> None:
    profile = ProfileDefinition(name="default", backend="opencode")
    event = HistoryEvent(
        id="event-1",
        task_id="task-1",
        kind=EventKind.CREATED,
        summary="Task created",
    )
    handoff = HandoffMetadata(
        id="handoff-1",
        task_id="task-1",
        title="Resume task",
        path="handoffs/handoff-1.md",
    )
    search = SearchRecord(
        id="search-1",
        record_type="task",
        source_id="task-1",
        text="Design storage",
    )

    assert profile.schema_version == 1
    assert event.kind == EventKind.CREATED
    assert handoff.source_session_ids == []
    assert search.record_type == "task"


def test_profile_rejects_path_unsafe_names() -> None:
    with pytest.raises(ValidationError):
        ProfileDefinition(name="../default", backend="opencode")


def test_redact_metadata_recursively_redacts_sensitive_keys() -> None:
    redacted = redact_metadata(
        {
            "token": "secret",
            "nested": {"api-key": "secret", "safe": "visible"},
            "items": [{"password": "secret"}],
        }
    )

    assert redacted == {
        "token": "[REDACTED]",
        "nested": {"api-key": "[REDACTED]", "safe": "visible"},
        "items": [{"password": "[REDACTED]"}],
    }
