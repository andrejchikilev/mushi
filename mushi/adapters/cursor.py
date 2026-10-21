"""Cursor CLI adapter implementation."""

from __future__ import annotations

from typing import Any

from mushi.adapters._attribution import Candidate
from mushi.adapters._cli_base import CliAdapterBase, invoke_with_attribution, with_context
from mushi.adapters import _cursor_db
from mushi.adapters._cursor_db import (
    agent_dir_size,
    list_agent_ids,
    list_agent_rows,
    remove_agent_dir,
    workspace_slug_for_path,
)
from mushi.adapters.protocol import AdapterResult, BackendAdapter, BackendCapability
from mushi.core.schemas import SessionRecord


class _CursorHooks:
    """Spawn-window attribution over cursor agent stores."""

    resume_keys = ("cursor_agent_id", "cursor_agent_name")

    def __init__(self, workspace_path: str) -> None:
        self.workspace_path = workspace_path

    def supports_attribution(self) -> bool:
        return _cursor_db.CHATS_DIR.is_dir()

    def snapshot_ids(self) -> set[str]:
        return list_agent_ids()

    def candidates(self) -> list[Candidate]:
        slug = workspace_slug_for_path(self.workspace_path)
        return [
            Candidate(
                key=row["agentId"],
                created=row["createdAt"],
                invocation_fields={
                    "cursor_agent_id": row["agentId"],
                    "cursor_agent_name": row["name"],
                },
            )
            for row in list_agent_rows(workspace_slug=slug)
        ]


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
        return frozenset({BackendCapability.RESUME, BackendCapability.DISK_USAGE, BackendCapability.PURGE})

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
        return invoke_with_attribution(
            CliAdapterBase.invoke,
            self,
            goal=goal,
            workspace_path=workspace_path,
            settings=settings,
            hooks=_CursorHooks(workspace_path),
        )

    def session_disk_usage(self, session: SessionRecord) -> int | None:
        cursor_agent_id = session.invocation.get("cursor_agent_id")
        if not cursor_agent_id:
            return None
        return agent_dir_size(cursor_agent_id)

    def purge_session(self, session: SessionRecord) -> None:
        cursor_agent_id = session.invocation.get("cursor_agent_id")
        if not cursor_agent_id:
            return
        remove_agent_dir(cursor_agent_id)

