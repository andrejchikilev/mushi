"""Abstract adapter protocol and capability model for Mushi backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from mushi.core.schemas import SessionRecord


class BackendCapability(StrEnum):
    """Capabilities a backend adapter may advertise."""

    RESUME = "resume"
    TRANSCRIPT_EXPORT = "transcript_export"
    DISK_USAGE = "disk_usage"
    PURGE = "purge"


@dataclass(frozen=True)
class AdapterResult:
    """Normalised result from a backend adapter invocation."""

    status: str  # "succeeded", "failed", "cancelled"
    backend_version: str | None = None
    transcript_refs: list[str] = field(default_factory=list)
    invocation: dict[str, Any] = field(default_factory=dict)
    result_summary: str = ""
    error_details: str | None = None


@runtime_checkable
class BackendAdapter(Protocol):
    """Protocol that every backend adapter must satisfy."""

    @property
    def name(self) -> str:
        ...

    @property
    def capabilities(self) -> frozenset[BackendCapability]:
        ...

    def check_available(self) -> bool:
        """Return True if the backend CLI or service is available on this system."""
        ...

    def invoke(
        self,
        goal: str,
        workspace_path: str,
        settings: dict[str, Any],
    ) -> AdapterResult:
        """Invoke the backend with the given goal and profile settings.

        This call blocks until the backend finishes or raises on fatal errors.
        Communicate status, transcript references, and errors via AdapterResult.
        """
        ...

    def session_disk_usage(self, session: SessionRecord) -> int | None:
        """Return the disk usage in bytes attributable to *session*, or None if unavailable."""
        ...

    def purge_session(self, session: SessionRecord) -> None:
        """Remove backend-owned data attributable to *session*.

        Implementations SHOULD be idempotent — missing metadata or missing
        backend storage paths MUST NOT raise.
        """
        ...

    def persistent_store_path(self) -> str | None:
        """Return the path to a shared persistent data store, or None.

        Used by the CLI to display a backend-level storage summary when per-session
        attribution is not available (e.g. OpenCode's shared SQLite database).
        """
        ...
