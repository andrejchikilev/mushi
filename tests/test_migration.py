"""Tests for migration module."""

from pathlib import Path

import pytest

from mushi.core.migration import CURRENT_SCHEMA_VERSION, check_schema_version, migrate
from mushi.core.schemas import TaskRecord
from mushi.storage.filesystem import FilesystemStorage


def test_check_schema_version_returns_empty_for_empty_storage(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    versions = check_schema_version(storage)

    assert versions == {}


def test_check_schema_version_detects_task_version(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    storage.save_task(TaskRecord(id="task-1", title="Test"))

    versions = check_schema_version(storage)

    assert versions.get("task") == CURRENT_SCHEMA_VERSION


def test_migrate_same_version_is_noop(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    migrate(storage, CURRENT_SCHEMA_VERSION, CURRENT_SCHEMA_VERSION)


def test_migrate_different_version_raises(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)

    with pytest.raises(NotImplementedError):
        migrate(storage, 0, 1)
