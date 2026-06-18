"""Filesystem-backed storage for Mushi records."""

from pathlib import Path
import shutil

from mushi.core.schemas import HandoffMetadata, HistoryEvent, ProfileDefinition, SessionRecord, TaskRecord
from mushi.storage.errors import RecordNotFoundError
from mushi.storage.files import atomic_create_text, atomic_write_text, delete_text_file, read_text_file
from mushi.storage.layout import StorageLayout
from mushi.storage.serialization import record_from_json, record_to_json


class FilesystemStorage:
    """Storage facade for source-of-truth filesystem records."""

    def __init__(self, root: str | Path) -> None:
        self.layout = StorageLayout(root)

    def save_task(self, task: TaskRecord) -> None:
        atomic_write_text(self.layout.task_path(task.id), record_to_json(task))

    def load_task(self, task_id: str) -> TaskRecord:
        return record_from_json(TaskRecord, read_text_file(self.layout.task_path(task_id)))

    def delete_task(self, task_id: str) -> None:
        path = self.layout.task_dir(task_id)
        if not path.is_dir():
            raise RecordNotFoundError(f"Task not found: {task_id}")
        shutil.rmtree(path)

    def task_exists(self, task_id: str) -> bool:
        return self.layout.task_path(task_id).is_file()

    def list_tasks(self) -> list[TaskRecord]:
        if not self.layout.tasks_dir.exists():
            return []

        task_paths = sorted(self.layout.tasks_dir.glob("*/task.json"))
        return [record_from_json(TaskRecord, read_text_file(path)) for path in task_paths]

    def save_session(self, session: SessionRecord) -> None:
        path = self.layout.session_path(session.task_id, session.id)
        atomic_write_text(path, record_to_json(session))

    def load_session(self, task_id: str, session_id: str) -> SessionRecord:
        path = self.layout.session_path(task_id, session_id)
        return record_from_json(SessionRecord, read_text_file(path))

    def delete_session(self, task_id: str, session_id: str) -> None:
        delete_text_file(self.layout.session_path(task_id, session_id))

    def save_profile(self, profile: ProfileDefinition) -> None:
        atomic_write_text(self.layout.profile_path(profile.name), record_to_json(profile))

    def load_profile(self, profile_name: str) -> ProfileDefinition:
        return record_from_json(
            ProfileDefinition,
            read_text_file(self.layout.profile_path(profile_name)),
        )

    def delete_profile(self, profile_name: str) -> None:
        delete_text_file(self.layout.profile_path(profile_name))

    def list_profiles(self) -> list[ProfileDefinition]:
        if not self.layout.profiles_dir.exists():
            return []

        profile_paths = sorted(self.layout.profiles_dir.glob("*.json"))
        return [record_from_json(ProfileDefinition, read_text_file(path)) for path in profile_paths]

    def append_event(self, event: HistoryEvent) -> None:
        path = self.layout.event_path(event.task_id, event.id)
        atomic_create_text(path, record_to_json(event))

    def list_events(self, task_id: str) -> list[HistoryEvent]:
        events_dir = self.layout.events_dir(task_id)
        if not events_dir.exists():
            return []

        event_paths = sorted(events_dir.glob("*.json"))
        events = [record_from_json(HistoryEvent, read_text_file(path)) for path in event_paths]
        return sorted(events, key=lambda event: (event.created_at, event.id))

    def delete_session_events(self, task_id: str, session_id: str) -> None:
        for event in self.list_events(task_id):
            if event.session_id == session_id:
                delete_text_file(self.layout.event_path(task_id, event.id))

    def find_session_by_id(self, session_id: str) -> SessionRecord | None:
        """Find a session by its ID across all tasks, or return None."""
        if not self.layout.tasks_dir.exists():
            return None
        for path in self.layout.tasks_dir.glob(f"*/sessions/{session_id}.json"):
            return record_from_json(SessionRecord, read_text_file(path))
        return None

    def list_sessions(self, task_id: str) -> list[SessionRecord]:
        """List all sessions for a task, ordered by creation time."""
        sessions_dir = self.layout.sessions_dir(task_id)
        if not sessions_dir.exists():
            return []
        return [
            record_from_json(SessionRecord, read_text_file(p))
            for p in sorted(sessions_dir.glob("*.json"))
        ]

    def save_handoff_metadata(self, handoff: HandoffMetadata) -> None:
        path = self.layout.handoff_metadata_path(handoff.id)
        atomic_write_text(path, record_to_json(handoff))

    def load_handoff_metadata(self, handoff_id: str) -> HandoffMetadata:
        path = self.layout.handoff_metadata_path(handoff_id)
        return record_from_json(HandoffMetadata, read_text_file(path))

    def find_handoffs_for_task(self, task_id: str) -> list[HandoffMetadata]:
        if not self.layout.handoffs_dir.exists():
            return []
        handoff_paths = sorted(self.layout.handoffs_dir.glob("*.json"))
        handoffs = [record_from_json(HandoffMetadata, read_text_file(path)) for path in handoff_paths]
        return [handoff for handoff in handoffs if handoff.task_id == task_id]

    def delete_handoff(self, handoff: HandoffMetadata) -> None:
        delete_text_file(self.layout.handoff_metadata_path(handoff.id))
        path = Path(handoff.path)
        if path.is_file():
            delete_text_file(path)
