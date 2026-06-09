from pathlib import Path

import pytest

from mushi.core.errors import RecordConflictError
from mushi.core.schemas import EventKind, TaskStatus
from mushi.core.tasks import TaskWorkflow
from mushi.storage.errors import RecordNotFoundError
from mushi.storage.filesystem import FilesystemStorage


def test_create_task_persists_task_and_history_event(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    workflow = TaskWorkflow(storage)

    task = workflow.create_task(task_id="task-1", title="Design storage", tags=["storage"])

    assert storage.load_task("task-1") == task
    events = storage.list_events("task-1")
    assert len(events) == 1
    assert events[0].kind == EventKind.CREATED


def test_create_task_rejects_duplicate_id(tmp_path: Path) -> None:
    workflow = TaskWorkflow(FilesystemStorage(tmp_path))
    workflow.create_task(task_id="task-1", title="Design storage")

    with pytest.raises(RecordConflictError):
        workflow.create_task(task_id="task-1", title="Different title")


def test_update_task_status_persists_task_and_history_event(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    workflow = TaskWorkflow(storage)
    workflow.create_task(task_id="task-1", title="Design storage")

    updated = workflow.update_task_status("task-1", TaskStatus.IN_PROGRESS)

    assert updated.status == TaskStatus.IN_PROGRESS
    assert storage.load_task("task-1").status == TaskStatus.IN_PROGRESS
    assert [event.kind for event in storage.list_events("task-1")] == [
        EventKind.CREATED,
        EventKind.STATUS_CHANGED,
    ]


def test_update_task_status_does_not_duplicate_event_for_same_status(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    workflow = TaskWorkflow(storage)
    workflow.create_task(task_id="task-1", title="Design storage")

    workflow.update_task_status("task-1", TaskStatus.OPEN)

    assert [event.kind for event in storage.list_events("task-1")] == [EventKind.CREATED]


def test_show_task_returns_existing_task(tmp_path: Path) -> None:
    workflow = TaskWorkflow(FilesystemStorage(tmp_path))
    task = workflow.create_task(task_id="task-1", title="Design storage")

    assert workflow.show_task("task-1") == task


def test_show_missing_task_raises(tmp_path: Path) -> None:
    workflow = TaskWorkflow(FilesystemStorage(tmp_path))

    with pytest.raises(RecordNotFoundError):
        workflow.show_task("missing")


def test_list_tasks_returns_storage_order(tmp_path: Path) -> None:
    workflow = TaskWorkflow(FilesystemStorage(tmp_path))
    workflow.create_task(task_id="task-b", title="B")
    workflow.create_task(task_id="task-a", title="A")

    assert [task.id for task in workflow.list_tasks()] == ["task-a", "task-b"]
