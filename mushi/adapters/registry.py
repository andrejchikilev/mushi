"""Adapter lookup registry.

Maps backend names (as stored in profiles) to adapter instances.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mushi.adapters.protocol import BackendAdapter


_ADAPTERS: dict[str, "BackendAdapter"] = {}


def register(backend: str, adapter: "BackendAdapter") -> None:
    """Register an adapter for the given backend name."""
    _ADAPTERS[backend] = adapter


def get(backend: str) -> "BackendAdapter | None":
    """Return the registered adapter for *backend*, or None."""
    return _ADAPTERS.get(backend)
