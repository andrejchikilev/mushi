from pathlib import Path

import pytest

from mushi.core.schemas import TaskRecord, TaskStatus
from mushi.storage.errors import RecordNotFoundError
from mushi.storage.filesystem import FilesystemStorage


def test_save_and_load_task_round_trip(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    task = TaskRecord(id="task-1", title="Design storage")

    storage.save_task(task)

    assert storage.load_task("task-1") == task


def test_save_task_overwrites_existing_record(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    storage.save_task(TaskRecord(id="task-1", title="Design storage"))
    updated = TaskRecord(id="task-1", title="Design storage", status=TaskStatus.IN_PROGRESS)

    storage.save_task(updated)

    assert storage.load_task("task-1") == updated


def test_task_exists_reports_presence(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)

    assert not storage.task_exists("task-1")

    storage.save_task(TaskRecord(id="task-1", title="Design storage"))

    assert storage.task_exists("task-1")


def test_load_missing_task_raises(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)

    with pytest.raises(RecordNotFoundError):
        storage.load_task("missing")


def test_list_tasks_returns_empty_for_empty_storage(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)

    assert storage.list_tasks() == []


def test_list_tasks_returns_records_in_stable_order(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    storage.save_task(TaskRecord(id="task-b", title="B"))
    storage.save_task(TaskRecord(id="task-a", title="A"))

    assert [task.id for task in storage.list_tasks()] == ["task-a", "task-b"]


def test_delete_task_removes_task_directory(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    storage.save_task(TaskRecord(id="task-1", title="Design storage"))
    storage.layout.sessions_dir("task-1").mkdir(parents=True)

    storage.delete_task("task-1")

    assert not storage.layout.task_dir("task-1").exists()


def test_delete_missing_task_raises(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)

    with pytest.raises(RecordNotFoundError):
        storage.delete_task("missing")
