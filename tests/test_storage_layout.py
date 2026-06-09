from pathlib import Path

import pytest

from mushi.storage.layout import StorageLayout


def test_layout_builds_primary_record_paths(tmp_path: Path) -> None:
    layout = StorageLayout(tmp_path)

    assert layout.task_path("task-1") == tmp_path / "tasks" / "task-1" / "task.json"
    assert layout.session_path("task-1", "session-1") == (
        tmp_path / "tasks" / "task-1" / "sessions" / "session-1.json"
    )
    assert layout.event_path("task-1", "event-1") == (
        tmp_path / "tasks" / "task-1" / "events" / "event-1.json"
    )
    assert layout.profile_path("default") == tmp_path / "profiles" / "default.json"
    assert layout.handoff_metadata_path("handoff-1") == tmp_path / "handoffs" / "handoff-1.json"


def test_layout_builds_derived_paths(tmp_path: Path) -> None:
    layout = StorageLayout(tmp_path)

    assert layout.derived_dir == tmp_path / "derived"
    assert layout.search_index_dir == tmp_path / "derived" / "search"
    assert layout.cache_dir == tmp_path / "derived" / "cache"


def test_layout_accepts_string_root(tmp_path: Path) -> None:
    layout = StorageLayout(str(tmp_path))

    assert layout.root == tmp_path


@pytest.mark.parametrize("bad_segment", ["../outside", "task/child", ".hidden", ""])
def test_layout_rejects_unsafe_path_segments(tmp_path: Path, bad_segment: str) -> None:
    layout = StorageLayout(tmp_path)

    with pytest.raises(ValueError, match="Unsafe storage path segment"):
        layout.task_path(bad_segment)
