"""OpenCode CLI adapter implementation."""

from __future__ import annotations

from typing import Any

from mushi.adapters._cli_base import CliAdapterBase, with_context
from mushi.adapters.protocol import BackendAdapter, BackendCapability


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
        prompt = with_context(goal, settings)
        return ["--prompt", prompt, *extra_args]
