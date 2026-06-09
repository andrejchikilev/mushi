import json
from datetime import UTC, datetime

import pytest

from mushi.core.schemas import SessionRecord, TaskRecord
from mushi.storage.errors import InvalidRecordError
from mushi.storage.serialization import record_from_json, record_to_json


def test_record_json_round_trip_preserves_datetime() -> None:
    task = TaskRecord(
        id="task-1",
        title="Design storage",
        created_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, 13, 0, tzinfo=UTC),
    )

    loaded = record_from_json(TaskRecord, record_to_json(task))

    assert loaded == task


def test_record_to_json_outputs_trailing_newline() -> None:
    raw_json = record_to_json(TaskRecord(id="task-1", title="Design storage"))

    assert raw_json.endswith("\n")


def test_record_from_json_rejects_invalid_json() -> None:
    with pytest.raises(InvalidRecordError, match="Invalid JSON"):
        record_from_json(TaskRecord, "{")


def test_record_from_json_rejects_invalid_schema() -> None:
    with pytest.raises(InvalidRecordError, match="Invalid TaskRecord"):
        record_from_json(TaskRecord, '{"schema_version": 1, "id": "task-1", "title": ""}')


def test_record_from_json_rejects_unknown_fields() -> None:
    data = json.loads(record_to_json(
        SessionRecord(
            id="session-1",
            task_id="task-1",
            backend="opencode",
            profile="default",
            workspace_path="/repo",
            goal="Continue task",
        )
    ))
    data["extra"] = "bad"

    with pytest.raises(InvalidRecordError, match="Invalid SessionRecord"):
        record_from_json(SessionRecord, json.dumps(data))
