"""Stub adapter for testing the adapter protocol without a real backend."""

from __future__ import annotations

from typing import Any

from mushi.adapters.protocol import AdapterResult, BackendAdapter, BackendCapability


class StubAdapter(BackendAdapter):
    """Adapter that returns canned results without invoking anything."""

    def __init__(
        self,
        *,
        available: bool = True,
        result_status: str = "succeeded",
        result_summary: str = "Stub invocation succeeded",
        backend_version: str | None = "0.0.0",
        transcript_refs: list[str] | None = None,
        error_details: str | None = None,
        capabilities: frozenset[BackendCapability] | None = None,
    ) -> None:
        self._available = available
        self._result_status = result_status
        self._result_summary = result_summary
        self._backend_version = backend_version
        self._transcript_refs = transcript_refs or []
        self._error_details = error_details
        self._capabilities = capabilities or frozenset()

    @property
    def name(self) -> str:
        return "stub"

    @property
    def capabilities(self) -> frozenset[BackendCapability]:
        return self._capabilities

    def check_available(self) -> bool:
        return self._available

    def invoke(
        self,
        goal: str,
        workspace_path: str,
        settings: dict[str, Any],
    ) -> AdapterResult:
        return AdapterResult(
            status=self._result_status,
            backend_version=self._backend_version,
            transcript_refs=list(self._transcript_refs),
            invocation={"goal": goal, "workspace_path": workspace_path, "settings": settings},
            result_summary=self._result_summary,
            error_details=self._error_details,
        )
