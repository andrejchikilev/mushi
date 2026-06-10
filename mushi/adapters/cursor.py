"""Cursor CLI adapter implementation."""

from __future__ import annotations

from typing import Any

from mushi.adapters._cli_base import CliAdapterBase
from mushi.adapters.protocol import BackendAdapter, BackendCapability


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
        from mushi.adapters._cli_base import with_context

        extra_args: list[str] = settings.get("extra_args", [])
        return ["agent", with_context(goal, settings), *extra_args]
