"""Backend adapter protocol and built-in adapter registration."""

from mushi.adapters.cursor import CursorCliAdapter
from mushi.adapters.opencode import OpenCodeAdapter
from mushi.adapters.protocol import AdapterResult, BackendAdapter, BackendCapability
from mushi.adapters.registry import register
from mushi.adapters.stub import StubAdapter

register("cursor", CursorCliAdapter())
register("opencode", OpenCodeAdapter())

__all__ = [
    "AdapterResult",
    "BackendAdapter",
    "BackendCapability",
    "CursorCliAdapter",
    "OpenCodeAdapter",
    "StubAdapter",
]
