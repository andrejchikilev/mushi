"""Tests for HandoffData builder."""

from pathlib import Path

from mushi.core.handoffs import HandoffBuilder
from mushi.core.profiles import ProfileWorkflow
from mushi.core.schemas import EventKind, HistoryEvent, SessionStatus, TaskStatus
from mushi.core.sessions import SessionWorkflow
from mushi.core.tasks import TaskWorkflow
from mushi.storage.filesystem import FilesystemStorage


def _setup_storage(
    tmp_path: Path,
) -> tuple[FilesystemStorage, str]:
    storage = FilesystemStorage(tmp_path)
    tw = TaskWorkflow(storage)
    pw = ProfileWorkflow(storage)
    tw.create_task(task_id="task-1", title="Design storage", tags=["storage", "phase2"])
    pw.save_profile(name="default", backend="opencode", settings={"model": "test"})

    sw = SessionWorkflow(storage)
    sw.start_session(
        session_id="session-1",
        task_id="task-1",
        profile_name="default",
        workspace_path="/repo",
        goal="Implement storage",
    )
    sw.finish_session(
        task_id="task-1",
        session_id="session-1",
        status=SessionStatus.SUCCEEDED,
        result_summary="Storage implemented",
    )

    tw.update_task_status("task-1", TaskStatus.DONE)
    return storage, "task-1"


def test_handoff_builder_returns_task_fields(tmp_path: Path) -> None:
    storage, task_id = _setup_storage(tmp_path)
    builder = HandoffBuilder(storage)

    data = builder.build(task_id)

    assert data.task_id == "task-1"
    assert data.task_title == "Design storage"
    assert data.task_status == "done"


def test_handoff_builder_returns_sorted_tags(tmp_path: Path) -> None:
    storage, task_id = _setup_storage(tmp_path)
    builder = HandoffBuilder(storage)

    data = builder.build(task_id)

    assert data.tags == ("phase2", "storage")


def test_handoff_builder_includes_sessions(tmp_path: Path) -> None:
    storage, task_id = _setup_storage(tmp_path)
    builder = HandoffBuilder(storage)

    data = builder.build(task_id)

    assert len(data.sessions) == 1
    session = data.sessions[0]
    assert session.id == "session-1"
    assert session.backend == "opencode"
    assert session.goal == "Implement storage"
    assert session.status == "succeeded"
    assert session.result_summary == "Storage implemented"


def test_handoff_builder_includes_events(tmp_path: Path) -> None:
    storage, task_id = _setup_storage(tmp_path)
    builder = HandoffBuilder(storage)

    data = builder.build(task_id)

    kinds = [e.kind for e in data.events]
    assert EventKind.CREATED.value in kinds
    assert EventKind.SESSION_STARTED.value in kinds
    assert EventKind.SESSION_FINISHED.value in kinds
    assert EventKind.STATUS_CHANGED.value in kinds


def test_handoff_builder_passes_user_notes(tmp_path: Path) -> None:
    storage, task_id = _setup_storage(tmp_path)
    builder = HandoffBuilder(storage)

    data = builder.build(task_id, user_notes="Fixed a critical bug")

    assert data.user_notes == "Fixed a critical bug"


def test_handoff_builder_redacts_task_metadata(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    TaskWorkflow(storage).create_task(
        task_id="task-1",
        title="Secure task",
        metadata={"token": "should-not-appear", "safe": "visible"},
    )
    builder = HandoffBuilder(storage)

    data = builder.build("task-1")

    assert data.task_metadata["token"] == "[REDACTED]"
    assert data.task_metadata["safe"] == "visible"
