"""Tests for adapter integration into SessionWorkflow."""

from pathlib import Path

from mushi.adapters.protocol import AdapterResult, BackendAdapter, BackendCapability
from mushi.adapters.stub import StubAdapter
from mushi.core.profiles import ProfileWorkflow
from mushi.core.schemas import SessionStatus
from mushi.core.sessions import SessionWorkflow
from mushi.core.tasks import TaskWorkflow
from mushi.storage.filesystem import FilesystemStorage


def _setup(tmp_path: Path) -> tuple[FilesystemStorage, str]:
    storage = FilesystemStorage(tmp_path)
    TaskWorkflow(storage).create_task(task_id="task-1", title="Design storage")
    ProfileWorkflow(storage).save_profile(
        name="default",
        backend="stub",
        settings={"model": "test"},
    )
    return storage, "task-1"


def test_start_session_resolves_and_invokes_adapter(tmp_path: Path) -> None:
    storage, task_id = _setup(tmp_path)
    stub = StubAdapter()
    workflow = SessionWorkflow(storage, get_adapter=lambda name: stub if name == "stub" else None)

    session = workflow.start_session(
        session_id="session-1",
        task_id=task_id,
        profile_name="default",
        workspace_path="/repo",
        goal="Continue work",
    )

    assert session.status == SessionStatus.SUCCEEDED
    assert session.backend_version == "0.0.0"
    assert session.result_summary == "Stub invocation succeeded"


def test_start_session_records_invocation_metadata(tmp_path: Path) -> None:
    storage, task_id = _setup(tmp_path)
    stub = StubAdapter()
    workflow = SessionWorkflow(storage, get_adapter=lambda name: stub if name == "stub" else None)

    session = workflow.start_session(
        session_id="session-1",
        task_id=task_id,
        profile_name="default",
        workspace_path="/repo",
        goal="Continue work",
    )

    assert session.invocation["goal"] == "Continue work"
    assert session.invocation["workspace_path"] == "/repo"


def test_start_session_marks_failed_when_adapter_unavailable(tmp_path: Path) -> None:
    storage, task_id = _setup(tmp_path)
    stub = StubAdapter(available=False)
    workflow = SessionWorkflow(storage, get_adapter=lambda name: stub if name == "stub" else None)

    session = workflow.start_session(
        session_id="session-1",
        task_id=task_id,
        profile_name="default",
        workspace_path="/repo",
        goal="Continue work",
    )

    assert session.status == SessionStatus.FAILED
    assert "is not available" in (session.result_summary or "")


def test_start_session_preserves_adapter_error_details(tmp_path: Path) -> None:
    storage, task_id = _setup(tmp_path)
    stub = StubAdapter(
        result_status="failed",
        result_summary="Backend failed",
        error_details="exit code 2",
    )
    workflow = SessionWorkflow(storage, get_adapter=lambda name: stub if name == "stub" else None)

    session = workflow.start_session(
        session_id="session-1",
        task_id=task_id,
        profile_name="default",
        workspace_path="/repo",
        goal="Continue work",
    )

    assert session.status == SessionStatus.FAILED
    assert session.result_summary == "Backend failed (details: exit code 2)"


def test_start_session_uses_fallback_when_no_adapter_registered(tmp_path: Path) -> None:
    storage, task_id = _setup(tmp_path)
    workflow = SessionWorkflow(storage, get_adapter=lambda name: None)

    session = workflow.start_session(
        session_id="session-1",
        task_id=task_id,
        profile_name="default",
        workspace_path="/repo",
        goal="Continue work",
    )

    assert session.status == SessionStatus.RUNNING


def test_start_session_resume_passes_context_from_previous_session(tmp_path: Path) -> None:
    storage, task_id = _setup(tmp_path)
    stub = StubAdapter()
    workflow = SessionWorkflow(storage, get_adapter=lambda name: stub if name == "stub" else None)

    workflow.start_session(
        session_id="session-1",
        task_id=task_id,
        profile_name="default",
        workspace_path="/repo",
        goal="First session",
    )
    workflow.finish_session(
        task_id=task_id,
        session_id="session-1",
        status=SessionStatus.SUCCEEDED,
        result_summary="Storage implemented",
    )

    session2 = workflow.start_session(
        session_id="session-2",
        task_id=task_id,
        profile_name="default",
        workspace_path="/repo",
        goal="Second session",
        resume_from="session-1",
    )

    assert session2.status == SessionStatus.SUCCEEDED
    assert session2.invocation["settings"]["context"] == "Storage implemented"


def test_start_session_resume_works_without_adapter(tmp_path: Path) -> None:
    storage, task_id = _setup(tmp_path)
    workflow = SessionWorkflow(storage)

    workflow.start_session(
        session_id="session-1",
        task_id=task_id,
        profile_name="default",
        workspace_path="/repo",
        goal="First session",
    )
    workflow.finish_session(
        task_id=task_id,
        session_id="session-1",
        status=SessionStatus.SUCCEEDED,
        result_summary="Storage done",
    )

    session2 = workflow.start_session(
        session_id="session-2",
        task_id=task_id,
        profile_name="default",
        workspace_path="/repo",
        goal="Second session",
        resume_from="session-1",
    )

    assert session2.status == SessionStatus.RUNNING


def test_start_session_pass_through_without_get_adapter(tmp_path: Path) -> None:
    """Backward compat: SessionWorkflow without get_adapter keeps Phase 3 behaviour."""
    storage, task_id = _setup(tmp_path)
    workflow = SessionWorkflow(storage)

    session = workflow.start_session(
        session_id="session-1",
        task_id=task_id,
        profile_name="default",
        workspace_path="/repo",
        goal="Continue work",
    )

    assert session.status == SessionStatus.RUNNING


def test_start_session_resume_passes_opencode_session_id(tmp_path: Path) -> None:
    """Resuming an opencode session passes opencode_session_id to adapter settings."""
    storage, task_id = _setup(tmp_path)
    stub = StubAdapter()

    workflow = SessionWorkflow(storage, get_adapter=lambda name: stub if name == "stub" else None)
    workflow.start_session(
        session_id="session-1",
        task_id=task_id,
        profile_name="default",
        workspace_path="/repo",
        goal="First session",
    )
    session1 = storage.load_session(task_id, "session-1")
    storage.save_session(
        session1.model_copy(
            update={
                "backend": "opencode",
                "invocation": {"opencode_session_id": "ses_open123"},
            }
        )
    )
    workflow.finish_session(
        task_id=task_id,
        session_id="session-1",
        status=SessionStatus.SUCCEEDED,
        result_summary="First run done",
    )

    session2 = workflow.start_session(
        session_id="session-2",
        task_id=task_id,
        profile_name="default",
        workspace_path="/repo",
        goal="Continue",
        resume_from="session-1",
    )

    assert session2.status == SessionStatus.SUCCEEDED
    assert session2.invocation["settings"]["opencode_session_id"] == "ses_open123"
    assert session2.invocation["settings"]["context"] == "First run done"


def test_start_session_resume_passes_cursor_agent_id(tmp_path: Path) -> None:
    """Resuming a cursor session passes cursor_agent_id to adapter settings."""
    storage, task_id = _setup(tmp_path)
    stub = StubAdapter()

    workflow = SessionWorkflow(storage, get_adapter=lambda name: stub if name == "stub" else None)
    workflow.start_session(
        session_id="session-1",
        task_id=task_id,
        profile_name="default",
        workspace_path="/repo",
        goal="First session",
    )
    session1 = storage.load_session(task_id, "session-1")
    storage.save_session(
        session1.model_copy(
            update={
                "backend": "cursor",
                "invocation": {"cursor_agent_id": "cursor-agent-xyz"},
            }
        )
    )
    workflow.finish_session(
        task_id=task_id,
        session_id="session-1",
        status=SessionStatus.SUCCEEDED,
        result_summary="First run done",
    )

    session2 = workflow.start_session(
        session_id="session-2",
        task_id=task_id,
        profile_name="default",
        workspace_path="/repo",
        goal="Continue",
        resume_from="session-1",
    )

    assert session2.status == SessionStatus.SUCCEEDED
    assert session2.invocation["settings"]["cursor_agent_id"] == "cursor-agent-xyz"
    assert session2.invocation["settings"]["context"] == "First run done"


def test_reopen_session_passes_result_summary_as_context(tmp_path: Path) -> None:
    storage, task_id = _setup(tmp_path)
    stub = StubAdapter()
    workflow = SessionWorkflow(storage, get_adapter=lambda name: stub if name == "stub" else None)
    workflow.start_session(
        session_id="session-1",
        task_id=task_id,
        profile_name="default",
        workspace_path="/repo",
        goal="First session",
    )
    workflow.finish_session(
        task_id=task_id,
        session_id="session-1",
        status=SessionStatus.SUCCEEDED,
        result_summary="First run done",
    )

    reopened = workflow.reopen_session(task_id=task_id, session_id="session-1")

    assert reopened.status == SessionStatus.SUCCEEDED
    assert reopened.invocation["settings"]["context"] == "First run done"


def test_reopen_session_without_backend_session_id_or_goal_skips_adapter(tmp_path: Path) -> None:
    storage, task_id = _setup(tmp_path)
    stub = StubAdapter(result_status="failed", result_summary="Should not run")
    workflow = SessionWorkflow(storage, get_adapter=lambda name: stub if name == "stub" else None)
    workflow.start_session(
        session_id="session-1",
        task_id=task_id,
        profile_name="default",
        workspace_path="/repo",
        goal="",
    )
    workflow.finish_session(
        task_id=task_id,
        session_id="session-1",
        status=SessionStatus.SUCCEEDED,
        result_summary="First run done",
    )

    reopened = workflow.reopen_session(task_id=task_id, session_id="session-1")

    assert reopened.status == SessionStatus.RUNNING
    assert reopened.invocation == {}


def test_reopen_session_includes_profile_settings(tmp_path: Path) -> None:
    """reopen_session loads profile settings (e.g. timeout, model) into adapter_settings."""
    storage, task_id = _setup(tmp_path)
    stub = StubAdapter()
    workflow = SessionWorkflow(storage, get_adapter=lambda name: stub if name == "stub" else None)
    workflow.start_session(
        session_id="session-1",
        task_id=task_id,
        profile_name="default",
        workspace_path="/repo",
        goal="First session",
    )
    workflow.finish_session(
        task_id=task_id,
        session_id="session-1",
        status=SessionStatus.SUCCEEDED,
        result_summary="First run done",
    )
    # Add timeout to the stored profile
    storage.save_profile(
        ProfileWorkflow(storage).show_profile("default").model_copy(
            update={"settings": {"model": "test", "timeout": 7200}}
        )
    )

    reopened = workflow.reopen_session(task_id=task_id, session_id="session-1")

    assert reopened.status == SessionStatus.SUCCEEDED
    assert reopened.invocation["settings"]["timeout"] == 7200
    assert reopened.invocation["settings"]["model"] == "test"
    assert reopened.invocation["settings"]["context"] == "First run done"
