"""Session recording workflow operations."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from mushi.core.errors import InvalidWorkflowStateError, RecordConflictError
from mushi.core.profiles import ProfileWorkflow
from mushi.core.schemas import EventKind, HistoryEvent, SessionRecord, SessionStatus, utc_now
from mushi.storage.filesystem import FilesystemStorage

if TYPE_CHECKING:
    from mushi.adapters.protocol import BackendAdapter

FINISH_STATUSES = {SessionStatus.SUCCEEDED, SessionStatus.FAILED, SessionStatus.CANCELLED}


class SessionWorkflow:
    """Storage-backed session metadata operations without backend execution."""

    def __init__(
        self,
        storage: FilesystemStorage,
        profiles: ProfileWorkflow | None = None,
        get_adapter: Callable[[str], "BackendAdapter | None"] | None = None,
    ) -> None:
        self.storage = storage
        self.profiles = profiles or ProfileWorkflow(storage)
        self.get_adapter = get_adapter

    def start_session(
        self,
        *,
        session_id: str,
        task_id: str,
        profile_name: str,
        workspace_path: str | Path,
        goal: str,
        resume_from: str | None = None,
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

        resume_summary = ""
        resume_opencode_id: str | None = None
        resume_cursor_id: str | None = None
        if resume_from is not None:
            previous = self.storage.load_session(task_id, resume_from)
            resume_summary = previous.result_summary or ""
            if previous.backend == "opencode":
                resume_opencode_id = previous.invocation.get("opencode_session_id")
            elif previous.backend == "cursor":
                resume_cursor_id = previous.invocation.get("cursor_agent_id")

        self.storage.append_event(
            HistoryEvent(
                id=f"{session.id}-started",
                task_id=task_id,
                kind=EventKind.SESSION_STARTED,
                created_at=started_at,
                summary=(
                    f"Session started with {session.backend} using profile {session.profile}"
                    + (f" (resumed from {resume_from})" if resume_from else "")
                ),
                session_id=session.id,
            )
        )

        if goal and self.get_adapter is not None:
            adapter = self.get_adapter(resolved_profile.backend)
            if adapter is not None:
                adapter_settings = dict(resolved_profile.settings)
                if resume_summary:
                    adapter_settings["context"] = resume_summary
                if resume_opencode_id:
                    adapter_settings["opencode_session_id"] = resume_opencode_id
                if resume_cursor_id:
                    adapter_settings["cursor_agent_id"] = resume_cursor_id
                session = self._invoke_adapter(session, adapter, goal, workspace_path, adapter_settings)

        return session

    def _invoke_adapter(
        self,
        session: SessionRecord,
        adapter: "BackendAdapter",
        goal: str,
        workspace_path: str | Path,
        settings: dict[str, Any],
    ) -> SessionRecord:
        if not adapter.check_available():
            updated = session.model_copy(
                update={
                    "status": SessionStatus.FAILED,
                    "result_summary": f"{adapter.name} is not available",
                }
            )
            self.storage.save_session(updated)
            return updated

        result = adapter.invoke(goal=goal, workspace_path=str(workspace_path), settings=settings)

        status_map = {
            "succeeded": SessionStatus.SUCCEEDED,
            "failed": SessionStatus.FAILED,
            "cancelled": SessionStatus.CANCELLED,
        }
        new_status = status_map.get(result.status, SessionStatus.FAILED)

        updated = session.model_copy(
            update={
                "status": new_status,
                "backend_version": result.backend_version,
                "invocation": result.invocation,
                "transcript_refs": result.transcript_refs,
                "result_summary": result.result_summary,
            }
        )
        if new_status in FINISH_STATUSES:
            updated = updated.model_copy(update={"ended_at": utc_now()})

        self.storage.save_session(updated)
        return updated

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

    def reopen_session(
        self,
        *,
        task_id: str,
        session_id: str,
    ) -> SessionRecord:
        """Re-open a finished session and invoke the backend adapter with its stored session ID."""
        session = self.storage.load_session(task_id, session_id)
        now = utc_now()
        session = session.model_copy(
            update={
                "status": SessionStatus.RUNNING,
                "started_at": now,
                "ended_at": None,
            }
        )
        self.storage.save_session(session)

        self.storage.append_event(
            HistoryEvent(
                id=f"{session.id}-reopened-{now.strftime('%H%M%S')}",
                task_id=task_id,
                kind=EventKind.SESSION_STARTED,
                created_at=now,
                summary=f"Session reopened for {session.backend} with {session.profile}",
                session_id=session.id,
            )
        )

        if self.get_adapter is not None:
            adapter = self.get_adapter(session.backend)
            if adapter is not None:
                adapter_settings: dict[str, Any] = {}
                if session.backend == "opencode":
                    sid = session.invocation.get("opencode_session_id")
                    if sid:
                        adapter_settings["opencode_session_id"] = sid
                elif session.backend == "cursor":
                    cid = session.invocation.get("cursor_agent_id")
                    if cid:
                        adapter_settings["cursor_agent_id"] = cid
                session = self._invoke_adapter(
                    session, adapter, session.goal, session.workspace_path, adapter_settings,
                )

        return session
