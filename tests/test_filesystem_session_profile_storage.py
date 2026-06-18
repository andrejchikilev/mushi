from pathlib import Path

import pytest

from mushi.core.schemas import EventKind, HistoryEvent, ProfileDefinition, SessionRecord, TaskRecord
from mushi.storage.errors import InvalidRecordError, RecordNotFoundError
from mushi.storage.filesystem import FilesystemStorage


def test_save_and_load_session_round_trip(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    session = SessionRecord(
        id="session-1",
        task_id="task-1",
        backend="opencode",
        profile="default",
        workspace_path="/repo",
        goal="Continue task",
    )

    storage.save_session(session)

    assert storage.load_session("task-1", "session-1") == session


def test_load_missing_session_raises(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)

    with pytest.raises(RecordNotFoundError):
        storage.load_session("task-1", "missing")


def test_loading_invalid_session_record_raises(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    path = storage.layout.session_path("task-1", "session-1")
    path.parent.mkdir(parents=True)
    path.write_text('{"schema_version": 1, "id": "session-1"}\n', encoding="utf-8")

    with pytest.raises(InvalidRecordError):
        storage.load_session("task-1", "session-1")


def test_save_and_load_profile_preserves_backend_settings(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    profile = ProfileDefinition(
        name="default",
        backend="opencode",
        settings={"model": "provider/model", "backend_specific": {"flag": True}},
    )

    storage.save_profile(profile)

    assert storage.load_profile("default") == profile


def test_load_missing_profile_raises(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)

    with pytest.raises(RecordNotFoundError):
        storage.load_profile("missing")


def test_list_profiles_returns_empty_for_empty_storage(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)

    assert storage.list_profiles() == []


def test_list_profiles_returns_records_in_stable_order(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    storage.save_profile(ProfileDefinition(name="zeta", backend="opencode"))
    storage.save_profile(ProfileDefinition(name="alpha", backend="cursor"))

    assert [profile.name for profile in storage.list_profiles()] == ["alpha", "zeta"]


def test_session_storage_does_not_require_task_record(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    session = SessionRecord(
        id="session-1",
        task_id="task-1",
        backend="opencode",
        profile="default",
        workspace_path="/repo",
        goal="Continue task",
    )

    storage.save_session(session)

    assert not storage.task_exists("task-1")
    assert storage.load_session("task-1", "session-1") == session


def test_task_and_session_records_are_separate_files(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    storage.save_task(TaskRecord(id="task-1", title="Design storage"))
    session = SessionRecord(
        id="session-1",
        task_id="task-1",
        backend="opencode",
        profile="default",
        workspace_path="/repo",
        goal="Continue task",
    )

    storage.save_session(session)

    assert storage.layout.task_path("task-1").is_file()
    assert storage.layout.session_path("task-1", "session-1").is_file()


def test_delete_profile_removes_profile_file(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    storage.save_profile(ProfileDefinition(name="default", backend="opencode"))

    storage.delete_profile("default")

    with pytest.raises(RecordNotFoundError):
        storage.load_profile("default")


def test_delete_session_removes_session_file(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    storage.save_session(
        SessionRecord(
            id="session-1",
            task_id="task-1",
            backend="opencode",
            profile="default",
            workspace_path="/repo",
            goal="Continue task",
        )
    )

    storage.delete_session("task-1", "session-1")

    with pytest.raises(RecordNotFoundError):
        storage.load_session("task-1", "session-1")


def test_delete_session_events_removes_matching_events_only(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    storage.append_event(
        HistoryEvent(
            id="session-1-started",
            task_id="task-1",
            kind=EventKind.SESSION_STARTED,
            summary="started",
            session_id="session-1",
        )
    )
    storage.append_event(
        HistoryEvent(
            id="session-2-started",
            task_id="task-1",
            kind=EventKind.SESSION_STARTED,
            summary="started",
            session_id="session-2",
        )
    )

    storage.delete_session_events("task-1", "session-1")

    assert [event.id for event in storage.list_events("task-1")] == ["session-2-started"]
