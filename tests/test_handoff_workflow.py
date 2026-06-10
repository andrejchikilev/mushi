"""Tests for HandoffWorkflow (builder + renderer + storage)."""

from pathlib import Path

from mushi.core.handoffs import HandoffBuilder, HandoffWorkflow
from mushi.core.profiles import ProfileWorkflow
from mushi.core.schemas import SessionStatus
from mushi.core.sessions import SessionWorkflow
from mushi.core.tasks import TaskWorkflow
from mushi.storage.filesystem import FilesystemStorage


def _setup(tmp_path: Path) -> tuple[FilesystemStorage, str]:
    storage = FilesystemStorage(tmp_path)
    TaskWorkflow(storage).create_task(task_id="task-1", title="Design storage")
    ProfileWorkflow(storage).save_profile(name="default", backend="opencode", settings={})
    SessionWorkflow(storage).start_session(
        session_id="session-1",
        task_id="task-1",
        profile_name="default",
        workspace_path="/repo",
        goal="Implement storage",
    )
    SessionWorkflow(storage).finish_session(
        task_id="task-1",
        session_id="session-1",
        status=SessionStatus.SUCCEEDED,
        result_summary="Done",
    )
    return storage, "task-1"


def test_handoff_workflow_saves_markdown_file(tmp_path: Path) -> None:
    storage, task_id = _setup(tmp_path)
    hf_dir = tmp_path / "handoffs"
    workflow = HandoffWorkflow(storage, handoff_dir=hf_dir)

    meta = workflow.generate(task_id, handoff_id="hf-1")

    assert hf_dir.joinpath("hf-1.md").is_file()
    assert meta.id == "hf-1"
    assert meta.task_id == "task-1"
    assert meta.path == str(hf_dir / "hf-1.md")


def test_handoff_workflow_contents_include_task_title(tmp_path: Path) -> None:
    storage, task_id = _setup(tmp_path)
    hf_dir = tmp_path / "handoffs"
    workflow = HandoffWorkflow(storage, handoff_dir=hf_dir)

    workflow.generate(task_id, handoff_id="hf-1")

    content = hf_dir.joinpath("hf-1.md").read_text(encoding="utf-8")
    assert "# Handoff: Design storage" in content
    assert "## Summary" in content
    assert "## Sessions" in content
    assert "## History" in content


def test_handoff_workflow_generates_default_id(tmp_path: Path) -> None:
    storage, task_id = _setup(tmp_path)
    workflow = HandoffWorkflow(storage, handoff_dir=tmp_path / "h")

    meta = workflow.generate(task_id)

    assert meta.id == "handoff-task-1"


def test_handoff_workflow_saves_metadata_to_storage(tmp_path: Path) -> None:
    storage, task_id = _setup(tmp_path)
    workflow = HandoffWorkflow(storage, handoff_dir=tmp_path / "h")

    meta = workflow.generate(task_id, handoff_id="hf-1")

    loaded = storage.load_handoff_metadata("hf-1")
    assert loaded == meta


def test_handoff_workflow_creates_history_event(tmp_path: Path) -> None:
    storage, task_id = _setup(tmp_path)
    workflow = HandoffWorkflow(storage, handoff_dir=tmp_path / "h")

    workflow.generate(task_id, handoff_id="hf-1")

    events = storage.list_events(task_id)
    kinds = [e.kind.value for e in events]
    assert "handoff_generated" in kinds


def test_handoff_workflow_includes_user_notes_in_markdown(tmp_path: Path) -> None:
    storage, task_id = _setup(tmp_path)
    hf_dir = tmp_path / "handoffs"
    workflow = HandoffWorkflow(storage, handoff_dir=hf_dir)

    workflow.generate(task_id, handoff_id="hf-1", user_notes="Critical fix needed")

    content = hf_dir.joinpath("hf-1.md").read_text(encoding="utf-8")
    assert "Critical fix needed" in content
    assert "## User Notes" in content


def test_handoff_workflow_source_includes_session_ids(tmp_path: Path) -> None:
    storage, task_id = _setup(tmp_path)
    workflow = HandoffWorkflow(storage, handoff_dir=tmp_path / "h")

    meta = workflow.generate(task_id, handoff_id="hf-1")

    assert meta.source_session_ids == ["session-1"]


def test_handoff_workflow_without_sessions(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    TaskWorkflow(storage).create_task(task_id="task-1", title="Empty task")
    workflow = HandoffWorkflow(storage, handoff_dir=tmp_path / "h")

    meta = workflow.generate("task-1", handoff_id="hf-1")

    content = (tmp_path / "h" / "hf-1.md").read_text(encoding="utf-8")
    assert "# Handoff: Empty task" in content
    assert "No sessions recorded" in content
    assert meta.source_session_ids == []


def test_handoff_builder_redacts_sensitive_metadata(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    TaskWorkflow(storage).create_task(
        task_id="task-1",
        title="Secure task",
        metadata={"api_key": "secret-123"},
    )
    data = HandoffBuilder(storage).build("task-1")

    assert data.task_metadata["api_key"] == "[REDACTED]"


def test_handoff_workflow_handles_long_notes(tmp_path: Path) -> None:
    storage, task_id = _setup(tmp_path)
    workflow = HandoffWorkflow(storage, handoff_dir=tmp_path / "h")
    long_notes = "word " * 500

    workflow.generate(task_id, handoff_id="hf-1", user_notes=long_notes)

    content = (tmp_path / "h" / "hf-1.md").read_text(encoding="utf-8")
    assert len(content) > 1000
    assert "## User Notes" in content
