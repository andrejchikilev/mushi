from datetime import UTC, datetime
from pathlib import Path

import pytest

from mushi.core.schemas import EventKind, HistoryEvent
from mushi.storage.errors import InvalidRecordError, RecordAlreadyExistsError
from mushi.storage.filesystem import FilesystemStorage


def test_append_and_list_events(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    event = HistoryEvent(
        id="event-1",
        task_id="task-1",
        kind=EventKind.CREATED,
        summary="Task created",
    )

    storage.append_event(event)

    assert storage.list_events("task-1") == [event]


def test_list_events_returns_empty_for_task_without_events(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)

    assert storage.list_events("task-1") == []


def test_list_events_returns_deterministic_chronological_order(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    later = HistoryEvent(
        id="event-b",
        task_id="task-1",
        kind=EventKind.UPDATED,
        summary="Updated",
        created_at=datetime(2026, 1, 1, 12, 1, tzinfo=UTC),
    )
    earlier = HistoryEvent(
        id="event-a",
        task_id="task-1",
        kind=EventKind.CREATED,
        summary="Created",
        created_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )

    storage.append_event(later)
    storage.append_event(earlier)

    assert [event.id for event in storage.list_events("task-1")] == ["event-a", "event-b"]


def test_append_event_rejects_duplicate_id(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    event = HistoryEvent(
        id="event-1",
        task_id="task-1",
        kind=EventKind.CREATED,
        summary="Task created",
    )

    storage.append_event(event)

    with pytest.raises(RecordAlreadyExistsError):
        storage.append_event(event)


def test_list_events_raises_for_invalid_event_record(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    path = storage.layout.event_path("task-1", "event-1")
    path.parent.mkdir(parents=True)
    path.write_text('{"schema_version": 1, "id": "event-1"}\n', encoding="utf-8")

    with pytest.raises(InvalidRecordError):
        storage.list_events("task-1")
