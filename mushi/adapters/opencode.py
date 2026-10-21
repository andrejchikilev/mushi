"""OpenCode CLI adapter implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mushi.adapters._attribution import Candidate
from mushi.adapters._cli_base import CliAdapterBase, invoke_with_attribution, with_context
from mushi.adapters._opencode_db import (
    get_opencode_db_path,
    list_workspace_sessions,
)
from mushi.adapters.protocol import AdapterResult, BackendAdapter, BackendCapability


def _attribution_hooks(db_path: Path | None, workspace_path: str) -> "_OpenCodeHooks":
    return _OpenCodeHooks(db_path, workspace_path)


class _OpenCodeHooks:
    """Spawn-window attribution over the shared OpenCode session table."""

    resume_keys = ("opencode_session_id", "opencode_session_title")

    def __init__(self, db_path: Path | None, workspace_path: str) -> None:
        self.db_path = db_path
        self.workspace_path = workspace_path

    def supports_attribution(self) -> bool:
        return self.db_path is not None

    def snapshot_ids(self) -> set[str]:
        return self._ids()

    def candidates(self) -> list[Candidate]:
        if self.db_path is None:
            return []
        return [
            Candidate(
                key=row["id"],
                created=row["time_created"],
                invocation_fields={
                    "opencode_session_id": row["id"],
                    "opencode_session_title": row["title"],
                },
            )
            for row in list_workspace_sessions(self.db_path, self.workspace_path)
        ]

    def _ids(self) -> set[str]:
        return {c.key for c in self.candidates()}


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
        hooks = _attribution_hooks(db_path, workspace_path)
        return invoke_with_attribution(
            CliAdapterBase.invoke,
            self,
            goal=goal,
            workspace_path=workspace_path,
            settings=settings,
            hooks=hooks,
        )

    def persistent_store_path(self) -> str | None:
        db_path = get_opencode_db_path()
        return str(db_path) if db_path else None
