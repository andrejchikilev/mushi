"""Versioned domain schemas for persisted Mushi records."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION: Literal[1] = 1
SENSITIVE_KEY_PARTS = ("api_key", "authorization", "credential", "password", "secret", "token")


def _utc_now() -> datetime:
    return datetime.now(UTC)


class TaskStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    ARCHIVED = "archived"


class SessionStatus(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EventKind(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    STATUS_CHANGED = "status_changed"
    SESSION_STARTED = "session_started"
    SESSION_FINISHED = "session_finished"
    HANDOFF_GENERATED = "handoff_generated"


class BaseRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: Literal[1] = SCHEMA_VERSION


class TaskRecord(BaseRecord):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    status: TaskStatus = TaskStatus.OPEN
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    session_ids: list[str] = Field(default_factory=list)

    @field_validator("updated_at")
    @classmethod
    def updated_after_created(cls, updated_at: datetime, info: Any) -> datetime:
        created_at = info.data.get("created_at")
        if created_at is not None and updated_at < created_at:
            raise ValueError("updated_at must not be earlier than created_at")
        return updated_at


class SessionRecord(BaseRecord):
    id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    backend: str = Field(min_length=1)
    profile: str = Field(min_length=1)
    workspace_path: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    status: SessionStatus = SessionStatus.PLANNED
    started_at: datetime | None = None
    ended_at: datetime | None = None
    backend_version: str | None = None
    resolved_profile: dict[str, Any] = Field(default_factory=dict)
    invocation: dict[str, Any] = Field(default_factory=dict)
    result_summary: str | None = None
    transcript_refs: list[str] = Field(default_factory=list)
    handoff_ids: list[str] = Field(default_factory=list)

    @field_validator("ended_at")
    @classmethod
    def ended_after_started(cls, ended_at: datetime | None, info: Any) -> datetime | None:
        started_at = info.data.get("started_at")
        if started_at is not None and ended_at is not None and ended_at < started_at:
            raise ValueError("ended_at must not be earlier than started_at")
        return ended_at


class ProfileDefinition(BaseRecord):
    name: str = Field(min_length=1)
    backend: str = Field(min_length=1)
    settings: dict[str, Any] = Field(default_factory=dict)
    description: str | None = None


class HistoryEvent(BaseRecord):
    id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    kind: EventKind
    created_at: datetime = Field(default_factory=_utc_now)
    summary: str = Field(min_length=1)
    session_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HandoffMetadata(BaseRecord):
    id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=_utc_now)
    source_session_ids: list[str] = Field(default_factory=list)
    title: str = Field(min_length=1)
    path: str = Field(min_length=1)


class SearchRecord(BaseRecord):
    id: str = Field(min_length=1)
    record_type: Literal["task", "session", "handoff", "event"]
    source_id: str = Field(min_length=1)
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


def redact_metadata(value: Any) -> Any:
    """Return metadata with sensitive keys redacted before persistence or handoff use."""
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if _is_sensitive_key(key) else redact_metadata(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_metadata(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)
