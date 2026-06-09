"""Filesystem layout helpers for Mushi storage."""

from dataclasses import dataclass
from pathlib import Path
import re


IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


@dataclass(frozen=True)
class StorageLayout:
    """Pure path builder for a Mushi storage root.

    Primary records are source of truth. Derived directories are reserved for
    rebuildable data such as future search indexes and caches.
    """

    root: Path

    def __init__(self, root: str | Path) -> None:
        object.__setattr__(self, "root", Path(root))

    @property
    def tasks_dir(self) -> Path:
        return self.root / "tasks"

    @property
    def profiles_dir(self) -> Path:
        return self.root / "profiles"

    @property
    def handoffs_dir(self) -> Path:
        return self.root / "handoffs"

    @property
    def derived_dir(self) -> Path:
        return self.root / "derived"

    @property
    def search_index_dir(self) -> Path:
        return self.derived_dir / "search"

    @property
    def cache_dir(self) -> Path:
        return self.derived_dir / "cache"

    def task_dir(self, task_id: str) -> Path:
        return self.tasks_dir / _safe_segment(task_id)

    def task_path(self, task_id: str) -> Path:
        return self.task_dir(task_id) / "task.json"

    def sessions_dir(self, task_id: str) -> Path:
        return self.task_dir(task_id) / "sessions"

    def session_path(self, task_id: str, session_id: str) -> Path:
        return self.sessions_dir(task_id) / f"{_safe_segment(session_id)}.json"

    def events_dir(self, task_id: str) -> Path:
        return self.task_dir(task_id) / "events"

    def event_path(self, task_id: str, event_id: str) -> Path:
        return self.events_dir(task_id) / f"{_safe_segment(event_id)}.json"

    def profile_path(self, profile_name: str) -> Path:
        return self.profiles_dir / f"{_safe_segment(profile_name)}.json"

    def handoff_metadata_path(self, handoff_id: str) -> Path:
        return self.handoffs_dir / f"{_safe_segment(handoff_id)}.json"


def _safe_segment(value: str) -> str:
    if not IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"Unsafe storage path segment: {value!r}")
    return value
