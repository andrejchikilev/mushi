"""Tests for Cursor CLI adapter using a shim binary."""

import os
from pathlib import Path

import pytest

from mushi.adapters.cursor import CursorCliAdapter


@pytest.fixture
def shim_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Install a fake `cursor` shim on PATH and return the shim directory."""
    shim = tmp_path / "cursor"
    shim.write_text(
        """#!/usr/bin/env bash
set -eu
if [ "$1" = "--version" ]; then
    echo "cursor 1.2.3"
    exit 0
fi
echo "Simulated output for: $*"
exit 0
""",
    )
    shim.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path), prepend=os.pathsep)
    return tmp_path


def test_cursor_check_available_true_when_binary_found(shim_env: Path) -> None:
    adapter = CursorCliAdapter()
    assert adapter.check_available() is True


def test_cursor_check_available_false_when_binary_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PATH", "/nonexistent")
    adapter = CursorCliAdapter()
    assert adapter.check_available() is False


def test_cursor_invoke_returns_success_result(shim_env: Path) -> None:
    adapter = CursorCliAdapter()
    result = adapter.invoke(goal="fix bug", workspace_path=str(shim_env), settings={})

    assert result.status == "succeeded"
    assert result.backend_version == "cursor 1.2.3"
    assert "Exit code" in result.result_summary


def test_cursor_invoke_records_invocation_metadata(shim_env: Path) -> None:
    adapter = CursorCliAdapter()
    result = adapter.invoke(
        goal="fix bug",
        workspace_path=str(shim_env),
        settings={"extra_args": ["--model", "gpt4"]},
    )

    assert result.invocation["args"] == ["agent", "fix bug", "--model", "gpt4"]
    assert result.invocation["cwd"] == str(shim_env)
    assert result.invocation["returncode"] == 0


def test_cursor_invoke_appends_context_to_goal(shim_env: Path) -> None:
    adapter = CursorCliAdapter()
    result = adapter.invoke(
        goal="fix bug",
        workspace_path=str(shim_env),
        settings={"context": "Previous work: design done"},
    )

    arg = result.invocation["args"][1]
    assert "Previous work: design done" in arg
    assert arg.startswith("fix bug")


def test_cursor_invoke_without_context_passes_goal_unchanged(shim_env: Path) -> None:
    adapter = CursorCliAdapter()
    result = adapter.invoke(
        goal="fix bug",
        workspace_path=str(shim_env),
        settings={},
    )

    assert result.invocation["args"] == ["agent", "fix bug"]


def test_cursor_invoke_propagates_extra_args_from_settings(shim_env: Path) -> None:
    adapter = CursorCliAdapter()
    result = adapter.invoke(
        goal="fix bug",
        workspace_path=str(shim_env),
        settings={"extra_args": ["--model", "gpt4"]},
    )

    assert result.invocation["args"] == ["agent", "fix bug", "--model", "gpt4"]
