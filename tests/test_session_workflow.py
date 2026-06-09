from pathlib import Path

import pytest

from mushi.core.errors import InvalidWorkflowStateError, RecordConflictError
from mushi.core.profiles import ProfileWorkflow
from mushi.core.schemas import EventKind, SessionStatus
from mushi.core.sessions import SessionWorkflow
from mushi.core.tasks import TaskWorkflow
from mushi.storage.errors import RecordNotFoundError
from mushi.storage.filesystem import FilesystemStorage


def _storage_with_task_and_profile(tmp_path: Path) -> FilesystemStorage:
    storage = FilesystemStorage(tmp_path)
    TaskWorkflow(storage).create_task(task_id="task-1", title="Design storage")
    ProfileWorkflow(storage).save_profile(
        name="default",
        backend="opencode",
        settings={"model": "provider/model"},
    )
    return storage


def test_start_session_records_metadata_and_links_task(tmp_path: Path) -> None:
    storage = _storage_with_task_and_profile(tmp_path)
    workflow = SessionWorkflow(storage)

    session = workflow.start_session(
        session_id="session-1",
        task_id="task-1",
        profile_name="default",
        workspace_path="/repo",
        goal="Continue work",
    )

    assert session.status == SessionStatus.RUNNING
    assert session.backend == "opencode"
    assert session.resolved_profile == {"model": "provider/model"}
    assert storage.load_task("task-1").session_ids == ["session-1"]
    assert storage.load_session("task-1", "session-1") == session


def test_start_session_records_history_event(tmp_path: Path) -> None:
    storage = _storage_with_task_and_profile(tmp_path)

    SessionWorkflow(storage).start_session(
        session_id="session-1",
        task_id="task-1",
        profile_name="default",
        workspace_path="/repo",
        goal="Continue work",
    )

    assert [event.kind for event in storage.list_events("task-1")] == [
        EventKind.CREATED,
        EventKind.SESSION_STARTED,
    ]


def test_start_session_rejects_duplicate_task_link(tmp_path: Path) -> None:
    storage = _storage_with_task_and_profile(tmp_path)
    workflow = SessionWorkflow(storage)
    workflow.start_session(
        session_id="session-1",
        task_id="task-1",
        profile_name="default",
        workspace_path="/repo",
        goal="Continue work",
    )

    with pytest.raises(RecordConflictError):
        workflow.start_session(
            session_id="session-1",
            task_id="task-1",
            profile_name="default",
            workspace_path="/repo",
            goal="Continue work",
        )


def test_start_session_requires_existing_task(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    ProfileWorkflow(storage).save_profile(name="default", backend="opencode")

    with pytest.raises(RecordNotFoundError):
        SessionWorkflow(storage).start_session(
            session_id="session-1",
            task_id="missing",
            profile_name="default",
            workspace_path="/repo",
            goal="Continue work",
        )


def test_start_session_requires_existing_profile(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    TaskWorkflow(storage).create_task(task_id="task-1", title="Design storage")

    with pytest.raises(RecordNotFoundError):
        SessionWorkflow(storage).start_session(
            session_id="session-1",
            task_id="task-1",
            profile_name="missing",
            workspace_path="/repo",
            goal="Continue work",
        )


def test_finish_session_records_status_summary_and_history(tmp_path: Path) -> None:
    storage = _storage_with_task_and_profile(tmp_path)
    workflow = SessionWorkflow(storage)
    workflow.start_session(
        session_id="session-1",
        task_id="task-1",
        profile_name="default",
        workspace_path="/repo",
        goal="Continue work",
    )

    finished = workflow.finish_session(
        task_id="task-1",
        session_id="session-1",
        status=SessionStatus.SUCCEEDED,
        result_summary="Recorded metadata",
    )

    assert finished.status == SessionStatus.SUCCEEDED
    assert finished.result_summary == "Recorded metadata"
    assert finished.ended_at is not None
    assert [event.kind for event in storage.list_events("task-1")] == [
        EventKind.CREATED,
        EventKind.SESSION_STARTED,
        EventKind.SESSION_FINISHED,
    ]


def test_finish_session_rejects_non_final_status(tmp_path: Path) -> None:
    storage = _storage_with_task_and_profile(tmp_path)
    workflow = SessionWorkflow(storage)
    workflow.start_session(
        session_id="session-1",
        task_id="task-1",
        profile_name="default",
        workspace_path="/repo",
        goal="Continue work",
    )

    with pytest.raises(InvalidWorkflowStateError):
        workflow.finish_session(
            task_id="task-1",
            session_id="session-1",
            status=SessionStatus.RUNNING,
            result_summary="Still running",
        )
