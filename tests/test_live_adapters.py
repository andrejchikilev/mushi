"""Optional live integration tests for adapter -- skip by default.

Run with: uv run pytest -m live
"""

import pytest

from mushi.adapters.cursor import CursorCliAdapter
from mushi.adapters.opencode import OpenCodeAdapter


@pytest.mark.live
def test_cursor_adapter_live_availability() -> None:
    adapter = CursorCliAdapter()
    available = adapter.check_available()
    assert isinstance(available, bool)


@pytest.mark.live
def test_cursor_adapter_live_version() -> None:
    adapter = CursorCliAdapter()
    if not adapter.check_available():
        pytest.skip("cursor not found on PATH")
    assert adapter._version is not None


@pytest.mark.live
def test_opencode_adapter_live_availability() -> None:
    adapter = OpenCodeAdapter()
    available = adapter.check_available()
    assert isinstance(available, bool)


@pytest.mark.live
def test_opencode_adapter_live_version() -> None:
    adapter = OpenCodeAdapter()
    if not adapter.check_available():
        pytest.skip("opencode not found on PATH")
    assert adapter._version is not None
