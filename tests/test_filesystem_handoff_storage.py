import shutil
from pathlib import Path

import pytest

from mushi.core.schemas import HandoffMetadata, ProfileDefinition, TaskRecord
from mushi.storage.errors import InvalidRecordError, RecordNotFoundError
from mushi.storage.filesystem import FilesystemStorage


def test_save_and_load_handoff_metadata_round_trip(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    handoff = HandoffMetadata(
        id="handoff-1",
        task_id="task-1",
        title="Resume task",
        path="handoffs/handoff-1.md",
        source_session_ids=["session-1"],
    )

    storage.save_handoff_metadata(handoff)

    assert storage.load_handoff_metadata("handoff-1") == handoff


def test_load_missing_handoff_metadata_raises(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)

    with pytest.raises(RecordNotFoundError):
        storage.load_handoff_metadata("missing")


def test_loading_invalid_handoff_metadata_raises(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    path = storage.layout.handoff_metadata_path("handoff-1")
    path.parent.mkdir(parents=True)
    path.write_text('{"schema_version": 1, "id": "handoff-1"}\n', encoding="utf-8")

    with pytest.raises(InvalidRecordError):
        storage.load_handoff_metadata("handoff-1")


def test_primary_records_do_not_require_derived_directories(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    task = TaskRecord(id="task-1", title="Design storage")
    profile = ProfileDefinition(name="default", backend="opencode")

    storage.save_task(task)
    storage.save_profile(profile)
    storage.layout.search_index_dir.mkdir(parents=True)
    storage.layout.cache_dir.mkdir(parents=True)
    shutil.rmtree(storage.layout.derived_dir)

    assert storage.load_task("task-1") == task
    assert storage.load_profile("default") == profile


def test_handoff_metadata_is_separate_from_generated_handoff_document(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    handoff = HandoffMetadata(
        id="handoff-1",
        task_id="task-1",
        title="Resume task",
        path="generated/handoff-1.md",
    )

    storage.save_handoff_metadata(handoff)

    assert storage.layout.handoff_metadata_path("handoff-1").is_file()
    assert not (tmp_path / "generated" / "handoff-1.md").exists()
