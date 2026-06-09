"""Session recording workflow operations."""

from pathlib import Path

from mushi.core.errors import InvalidWorkflowStateError, RecordConflictError
from mushi.core.profiles import ProfileWorkflow
from mushi.core.schemas import EventKind, HistoryEvent, SessionRecord, SessionStatus, utc_now
from mushi.storage.filesystem import FilesystemStorage


FINISH_STATUSES = {SessionStatus.SUCCEEDED, SessionStatus.FAILED, SessionStatus.CANCELLED}


class SessionWorkflow:
    """Storage-backed session metadata operations without backend execution."""

    def __init__(
        self,
        storage: FilesystemStorage,
        profiles: ProfileWorkflow | None = None,
    ) -> None:
        self.storage = storage
        self.profiles = profiles or ProfileWorkflow(storage)

    def start_session(
        self,
        *,
        session_id: str,
        task_id: str,
        profile_name: str,
        workspace_path: str | Path,
        goal: str,
    ) -> SessionRecord:
        task = self.storage.load_task(task_id)
        if session_id in task.session_ids:
            raise RecordConflictError(f"Session already linked to task: {session_id}")

        resolved_profile = self.profiles.resolve_profile(profile_name)
        started_at = utc_now()
        session = SessionRecord(
            id=session_id,
            task_id=task_id,
            backend=resolved_profile.backend,
            profile=resolved_profile.name,
            workspace_path=str(workspace_path),
            goal=goal,
            status=SessionStatus.RUNNING,
            started_at=started_at,
            resolved_profile=dict(resolved_profile.settings),
        )
        self.storage.save_session(session)
        updated_task = task.model_copy(
            update={
                "session_ids": [*task.session_ids, session.id],
                "updated_at": started_at,
            }
        )
        self.storage.save_task(updated_task)
        self.storage.append_event(
            HistoryEvent(
                id=f"{session.id}-started",
                task_id=task_id,
                kind=EventKind.SESSION_STARTED,
                created_at=started_at,
                summary=f"Session started with {session.backend} using profile {session.profile}",
                session_id=session.id,
            )
        )
        return session

    def finish_session(
        self,
        *,
        task_id: str,
        session_id: str,
        status: SessionStatus,
        result_summary: str,
    ) -> SessionRecord:
        if status not in FINISH_STATUSES:
            raise InvalidWorkflowStateError(f"Invalid final session status: {status.value}")

        session = self.storage.load_session(task_id, session_id)
        ended_at = utc_now()
        updated = session.model_copy(
            update={
                "status": status,
                "ended_at": ended_at,
                "result_summary": result_summary,
            }
        )
        self.storage.save_session(updated)
        self.storage.append_event(
            HistoryEvent(
                id=f"{session.id}-finished",
                task_id=task_id,
                kind=EventKind.SESSION_FINISHED,
                created_at=ended_at,
                summary=f"Session finished with status {status.value}: {result_summary}",
                session_id=session.id,
            )
        )
        return updated
