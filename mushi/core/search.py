"""Search index builder and query API."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mushi.core.schemas import SearchRecord
from mushi.storage.files import atomic_write_text, read_text_file
from mushi.storage.filesystem import FilesystemStorage
from mushi.storage.serialization import record_from_json, record_to_json


@dataclass
class SearchQuery:
    text: str = ""
    record_type: str | None = None
    backend: str | None = None
    profile: str | None = None
    task_status: str | None = None
    tags: list[str] | None = None


@dataclass
class SearchResult:
    id: str
    record_type: str
    source_id: str
    text: str
    metadata: dict[str, Any]


class SearchBuilder:
    """Walk storage and build a rebuildable SearchRecord index."""

    def __init__(self, storage: FilesystemStorage) -> None:
        self.storage = storage

    def build_index(self) -> None:
        index_dir = self.storage.layout.search_index_dir
        if index_dir.exists():
            _clear_dir(index_dir)
        index_dir.mkdir(parents=True, exist_ok=True)

        records: list[SearchRecord] = []

        for task in self.storage.list_tasks():
            records.append(
                SearchRecord(
                    id=f"task-{task.id}",
                    record_type="task",
                    source_id=task.id,
                    text=f"{task.title} {' '.join(task.tags)} {task.status.value}",
                    metadata={"status": task.status.value, "tags": list(task.tags)},
                )
            )

            for sid in task.session_ids:
                session = self.storage.load_session(task.id, sid)
                records.append(
                    SearchRecord(
                        id=f"session-{sid}",
                        record_type="session",
                        source_id=sid,
                        text=f"{session.goal} {session.result_summary or ''} {session.backend} {session.profile}",
                        metadata={
                            "backend": session.backend,
                            "profile": session.profile,
                            "status": session.status.value,
                            "task_id": task.id,
                        },
                    )
                )

            for event in self.storage.list_events(task.id):
                records.append(
                    SearchRecord(
                        id=f"event-{event.id}",
                        record_type="event",
                        source_id=event.id,
                        text=f"{event.kind.value} {event.summary}",
                        metadata={"task_id": task.id, "session_id": event.session_id or ""},
                    )
                )

        for record in records:
            path = index_dir / f"{record.id}.json"
            atomic_write_text(path, record_to_json(record))

    def delete_index(self) -> None:
        index_dir = self.storage.layout.search_index_dir
        if index_dir.exists():
            _clear_dir(index_dir)
            index_dir.rmdir()

    def rebuild(self) -> None:
        self.delete_index()
        self.build_index()


class Searcher:
    """Query a built search index."""

    def __init__(self, storage: FilesystemStorage) -> None:
        self.storage = storage

    def search(self, query: SearchQuery) -> list[SearchResult]:
        index_dir = self.storage.layout.search_index_dir
        if not index_dir.exists():
            return []

        raw = self._text_to_match(query.text)

        results: list[SearchResult] = []
        for path in sorted(index_dir.glob("*.json")):
            record = record_from_json(SearchRecord, read_text_file(path))

            if query.record_type is not None and record.record_type != query.record_type:
                continue

            if query.backend is not None:
                meta_backend = record.metadata.get("backend", "")
                if meta_backend != query.backend:
                    continue

            if query.profile is not None:
                meta_profile = record.metadata.get("profile", "")
                if meta_profile != query.profile:
                    continue

            if query.task_status is not None:
                meta_status = record.metadata.get("status", "")
                if meta_status != query.task_status:
                    continue

            if query.tags:
                meta_tags: list[str] = record.metadata.get("tags", [])
                if not any(t in meta_tags for t in query.tags):
                    continue

            if raw and raw not in self._text_to_match(record.text):
                continue

            results.append(
                SearchResult(
                    id=record.id,
                    record_type=record.record_type,
                    source_id=record.source_id,
                    text=record.text,
                    metadata=dict(record.metadata),
                )
            )

        return results

    @staticmethod
    def _text_to_match(text: str) -> str:
        return text.lower()


def _clear_dir(directory: Path) -> None:
    for child in directory.iterdir():
        if child.is_file():
            child.unlink()
        elif child.is_dir():
            _clear_dir(child)
            child.rmdir()
