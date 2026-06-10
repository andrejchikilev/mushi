"""Handoff data building and rendering."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from mushi.core.schemas import EventKind, HandoffMetadata, HistoryEvent, utc_now
from mushi.storage.filesystem import FilesystemStorage


@dataclass(frozen=True)
class HandoffData:
    """Structured handoff data collected from task, sessions, and events."""

    task_id: str
    task_title: str
    task_status: str
    created_at: datetime
    updated_at: datetime
    tags: tuple[str, ...]
    task_metadata: dict[str, Any]
    sessions: tuple["HandoffSession", ...]
    events: tuple["HandoffEvent", ...]
    user_notes: str = ""


@dataclass(frozen=True)
class HandoffSession:
    """Session summary for handoff output."""

    id: str
    backend: str
    profile: str
    goal: str
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    result_summary: str | None
    backend_version: str | None
    transcript_refs: tuple[str, ...]


@dataclass(frozen=True)
class HandoffEvent:
    """History event for handoff timeline."""

    kind: str
    summary: str
    created_at: datetime
    session_id: str | None


class HandoffBuilder:
    """Collect task, session, and event data into a structured HandoffData."""

    def __init__(self, storage: FilesystemStorage) -> None:
        self.storage = storage

    def build(self, task_id: str, *, user_notes: str = "") -> HandoffData:
        task = self.storage.load_task(task_id)
        sessions = [self.storage.load_session(task_id, sid) for sid in task.session_ids]
        events = self.storage.list_events(task_id)

        return HandoffData(
            task_id=task.id,
            task_title=task.title,
            task_status=task.status.value,
            created_at=task.created_at,
            updated_at=task.updated_at,
            tags=tuple(sorted(task.tags)),
            task_metadata=_redacted_dict(task.metadata),
            sessions=tuple(
                HandoffSession(
                    id=s.id,
                    backend=s.backend,
                    profile=s.profile,
                    goal=s.goal,
                    status=s.status.value,
                    started_at=s.started_at,
                    ended_at=s.ended_at,
                    result_summary=s.result_summary,
                    backend_version=s.backend_version,
                    transcript_refs=tuple(s.transcript_refs),
                )
                for s in sessions
            ),
            events=tuple(
                HandoffEvent(
                    kind=e.kind.value,
                    summary=e.summary,
                    created_at=e.created_at,
                    session_id=e.session_id,
                )
                for e in events
            ),
            user_notes=user_notes,
        )


def _redacted_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Return metadata with sensitive keys redacted."""
    from mushi.core.schemas import redact_metadata

    return redact_metadata(data)  # type: ignore[return-value]


class HandoffRenderer:
    """Render HandoffData into a markdown handoff document."""

    def render(self, data: HandoffData) -> str:
        sections = [
            self._render_header(data),
            self._render_summary(data),
            self._render_sessions(data),
            self._render_history(data),
            self._render_notes(data),
            self._render_provenance(data),
        ]
        return "\n\n".join(sections) + "\n"

    def _render_header(self, data: HandoffData) -> str:
        tags = ", ".join(data.tags) if data.tags else "—"
        return (
            f"# Handoff: {data.task_title}\n\n"
            f"**Task:** `{data.task_id}`  ·  **Status:** {data.task_status}  ·  "
            f"**Tags:** {tags}\n\n"
            f"*Created {data.created_at.isoformat()}  ·  "
            f"Updated {data.updated_at.isoformat()}*"
        )

    def _render_summary(self, data: HandoffData) -> str:
        completed = sum(1 for s in data.sessions if s.status in ("succeeded", "failed"))
        return (
            f"## Summary\n\n"
            f"Task **{data.task_title}** is currently **{data.task_status}**.\n\n"
            f"- {len(data.sessions)} session(s), {completed} completed\n"
            f"- {len(data.events)} history event(s)"
        )

    def _render_sessions(self, data: HandoffData) -> str:
        if not data.sessions:
            return "## Sessions\n\nNo sessions recorded."

        rows = [
            "| Session | Backend | Profile | Status | Goal | Result |",
            "|---------|---------|---------|--------|------|--------|",
        ]
        for s in data.sessions:
            goal = s.goal[:60] + "…" if len(s.goal) > 60 else s.goal
            summary = (s.result_summary or "—")[:60]
            rows.append(f"| `{s.id}` | {s.backend} | {s.profile} | {s.status} | {goal} | {summary} |")

        return "## Sessions\n\n" + "\n".join(rows)

    def _render_history(self, data: HandoffData) -> str:
        if not data.events:
            return "## History\n\nNo events recorded."

        lines = ["## History\n"]
        for event in data.events:
            ts = event.created_at.isoformat()
            session_ref = f" [session: `{event.session_id}`]" if event.session_id else ""
            lines.append(f"- **{ts}** — {event.summary}{session_ref}")

        return "\n".join(lines)

    def _render_notes(self, data: HandoffData) -> str:
        notes = data.user_notes or "—"
        return f"## User Notes\n\n{notes}"

    def _render_provenance(self, data: HandoffData) -> str:
        return (
            f"## Provenance\n\n"
            f"Generated from task `{data.task_id}` with "
            f"{len(data.sessions)} session(s) and {len(data.events)} event(s)."
        )


class HandoffWorkflow:
    """Orchestrate handoff generation: build → render → save."""

    def __init__(self, storage: FilesystemStorage, handoff_dir: str | Path = ".mushi/handoffs") -> None:
        self.storage = storage
        self.handoff_dir = Path(handoff_dir)
        self.builder = HandoffBuilder(storage)
        self.renderer = HandoffRenderer()

    def generate(
        self,
        task_id: str,
        *,
        handoff_id: str | None = None,
        user_notes: str = "",
    ) -> HandoffMetadata:
        hid = handoff_id or f"handoff-{task_id}"

        data = self.builder.build(task_id, user_notes=user_notes)
        markdown = self.renderer.render(data)

        doc_path = self.handoff_dir / f"{hid}.md"
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_text(markdown, encoding="utf-8")

        metadata = HandoffMetadata(
            id=hid,
            task_id=task_id,
            title=data.task_title,
            source_session_ids=list(s.id for s in data.sessions),
            path=str(doc_path),
        )
        self.storage.save_handoff_metadata(metadata)

        self.storage.append_event(
            HistoryEvent(
                id=f"{hid}-generated",
                task_id=task_id,
                kind=EventKind.HANDOFF_GENERATED,
                summary=f"Handoff generated for task {task_id}: {data.task_title}",
            )
        )

        return metadata
