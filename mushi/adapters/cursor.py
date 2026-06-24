"""Cursor CLI adapter implementation."""

from __future__ import annotations

from typing import Any

from mushi.adapters._cli_base import CliAdapterBase, with_context
from mushi.adapters._cursor_db import detect_new_agents, list_all_agent_store_paths_with_mtime
from mushi.adapters.protocol import AdapterResult, BackendAdapter, BackendCapability


class CursorCliAdapter(CliAdapterBase, BackendAdapter):
    """Adapter for the Cursor CLI (`cursor` binary)."""

    binary_name = "cursor"

    def __init__(self) -> None:
        super().__init__(interactive=True)

    @property
    def name(self) -> str:
        return "cursor"

    @property
    def capabilities(self) -> frozenset[BackendCapability]:
        return frozenset({BackendCapability.RESUME})

    def _build_invoke_args(self, goal: str, settings: dict[str, Any]) -> list[str]:
        extra_args: list[str] = settings.get("extra_args", [])
        model: str | None = settings.get("model")
        cursor_agent_id: str | None = settings.get("cursor_agent_id")
        if cursor_agent_id:
            args = ["agent", "--resume", cursor_agent_id]
        else:
            prompt = with_context(goal, settings)
            args = ["agent", prompt]
        if model:
            args += ["--model", model]
        return args + extra_args

    def invoke(
        self,
        goal: str,
        workspace_path: str,
        settings: dict[str, Any],
    ) -> AdapterResult:
        before = list_all_agent_store_paths_with_mtime()

        result = super().invoke(goal=goal, workspace_path=workspace_path, settings=settings)

        sessions = detect_new_agents(before)
        if sessions:
            latest = sessions[0]
            result = AdapterResult(
                status=result.status,
                backend_version=result.backend_version,
                transcript_refs=list(result.transcript_refs),
                invocation={
                    **result.invocation,
                    "cursor_agent_id": latest["agentId"],
                    "cursor_agent_name": latest["name"],
                },
                result_summary=result.result_summary,
                error_details=result.error_details,
            )

        return result
