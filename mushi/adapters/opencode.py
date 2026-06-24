"""OpenCode CLI adapter implementation."""

from __future__ import annotations

from typing import Any

from mushi.adapters._cli_base import CliAdapterBase, with_context
from mushi.adapters._opencode_db import detect_new_sessions, get_max_created_at, get_opencode_db_path
from mushi.adapters.protocol import AdapterResult, BackendAdapter, BackendCapability


class OpenCodeAdapter(CliAdapterBase, BackendAdapter):
    """Adapter for the OpenCode CLI (`opencode` binary)."""

    binary_name = "opencode"

    def __init__(self) -> None:
        super().__init__(interactive=True)

    @property
    def name(self) -> str:
        return "opencode"

    @property
    def capabilities(self) -> frozenset[BackendCapability]:
        return frozenset({BackendCapability.TRANSCRIPT_EXPORT})

    def _build_invoke_args(self, goal: str, settings: dict[str, Any]) -> list[str]:
        extra_args: list[str] = settings.get("extra_args", [])
        model: str | None = settings.get("model")
        opencode_session_id: str | None = settings.get("opencode_session_id")
        if opencode_session_id:
            args = ["--session", opencode_session_id]
        else:
            prompt = with_context(goal, settings)
            args = ["--prompt", prompt]
        if model:
            args += ["--model", model]
        return args + extra_args

    def invoke(
        self,
        goal: str,
        workspace_path: str,
        settings: dict[str, Any],
    ) -> AdapterResult:
        db_path = get_opencode_db_path()
        before = get_max_created_at(db_path, workspace_path) if db_path else None

        result = super().invoke(goal=goal, workspace_path=workspace_path, settings=settings)

        if db_path is not None:
            sessions = detect_new_sessions(db_path, workspace_path, before)
            if sessions:
                latest = sessions[0]
                result = AdapterResult(
                    status=result.status,
                    backend_version=result.backend_version,
                    transcript_refs=list(result.transcript_refs),
                    invocation={
                        **result.invocation,
                        "opencode_session_id": latest["id"],
                        "opencode_session_title": latest["title"],
                    },
                    result_summary=result.result_summary,
                    error_details=result.error_details,
                )

        return result
