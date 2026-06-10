"""Tests for OpenCode CLI adapter using a shim binary."""

import os
from pathlib import Path

import pytest

from mushi.adapters.opencode import OpenCodeAdapter


@pytest.fixture
def shim_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Install a fake `opencode` shim on PATH and return the shim directory."""
    shim = tmp_path / "opencode"
    shim.write_text(
        """#!/usr/bin/env bash
set -eu
if [ "$1" = "--version" ]; then
    echo "opencode 2.0.0"
    exit 0
fi
echo "Simulated opencode output for: $*"
exit 0
""",
    )
    shim.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path), prepend=os.pathsep)
    return tmp_path


def test_opencode_check_available_true_when_binary_found(shim_env: Path) -> None:
    adapter = OpenCodeAdapter()
    assert adapter.check_available() is True


def test_opencode_check_available_false_when_binary_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PATH", "/nonexistent")
    adapter = OpenCodeAdapter()
    assert adapter.check_available() is False


def test_opencode_invoke_uses_prompt_flag(shim_env: Path) -> None:
    adapter = OpenCodeAdapter()
    result = adapter.invoke(goal="fix bug", workspace_path=str(shim_env), settings={})

    assert result.status == "succeeded"
    assert result.backend_version == "opencode 2.0.0"
    assert result.invocation["args"] == ["--prompt", "fix bug"]
    assert "Simulated opencode output" in result.result_summary


def test_opencode_invoke_propagates_extra_args(shim_env: Path) -> None:
    adapter = OpenCodeAdapter()
    result = adapter.invoke(
        goal="fix bug",
        workspace_path=str(shim_env),
        settings={"extra_args": ["--model", "gpt4"]},
    )

    assert result.invocation["args"] == ["--prompt", "fix bug", "--model", "gpt4"]


def test_opencode_invoke_appends_context_to_prompt(shim_env: Path) -> None:
    adapter = OpenCodeAdapter()
    result = adapter.invoke(
        goal="fix bug",
        workspace_path=str(shim_env),
        settings={"context": "Previous session: storage was implemented"},
    )

    assert "Previous session: storage was implemented" in result.invocation["args"][1]
    assert result.invocation["args"][1].startswith("fix bug")


def test_opencode_invoke_without_context_does_not_add_context_block(shim_env: Path) -> None:
    adapter = OpenCodeAdapter()
    result = adapter.invoke(
        goal="fix bug",
        workspace_path=str(shim_env),
        settings={},
    )

    assert "Previous context:" not in result.invocation["args"][1]
