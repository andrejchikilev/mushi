"""Task workflow operations."""

from mushi.core.errors import RecordConflictError
from mushi.core.schemas import EventKind, HistoryEvent, TaskRecord, TaskStatus, utc_now
from mushi.storage.filesystem import FilesystemStorage


class TaskWorkflow:
    """Storage-backed task lifecycle operations."""

    def __init__(self, storage: FilesystemStorage) -> None:
        self.storage = storage

    def create_task(
        self,
        *,
        task_id: str,
        title: str,
        tags: list[str] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> TaskRecord:
        if self.storage.task_exists(task_id):
            raise RecordConflictError(f"Task already exists: {task_id}")

        now = utc_now()
        task = TaskRecord(
            id=task_id,
            title=title,
            tags=tags or [],
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )
        self.storage.save_task(task)
        self.storage.append_event(
            HistoryEvent(
                id=f"{task.id}-created",
                task_id=task.id,
                kind=EventKind.CREATED,
                created_at=now,
                summary=f"Task created: {task.title}",
            )
        )
        return task

    def update_task_status(self, task_id: str, status: TaskStatus) -> TaskRecord:
        task = self.storage.load_task(task_id)
        previous_status = task.status
        updated = task.model_copy(update={"status": status, "updated_at": utc_now()})
        self.storage.save_task(updated)

        if previous_status != status:
            now = utc_now()
            self.storage.append_event(
                HistoryEvent(
                    id=f"{task.id}-{previous_status.value}-to-{status.value}-{now.strftime('%Y%m%dT%H%M%S')}",
                    task_id=task.id,
                    kind=EventKind.STATUS_CHANGED,
                    created_at=now,
                    summary=f"Task status changed from {previous_status.value} to {status.value}",
                )
            )
        return updated

    def show_task(self, task_id: str) -> TaskRecord:
        return self.storage.load_task(task_id)

    def list_tasks(self) -> list[TaskRecord]:
        return self.storage.list_tasks()

    def remove_task(self, task_id: str) -> None:
        self.storage.load_task(task_id)
        for handoff in self.storage.find_handoffs_for_task(task_id):
            self.storage.delete_handoff(handoff)
        self.storage.delete_task(task_id)
