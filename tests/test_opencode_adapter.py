"""Tests for OpenCode CLI adapter using a shim binary."""

import os
import sqlite3
import time
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


@pytest.fixture
def shim_with_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Install a shim that handles ``db path`` and ``--prompt``.

    The shim returns a real SQLite DB and inserts a new session row
    each time it is invoked with ``--prompt`` (simulating OpenCode
    creating a session during interactive use).

    Returns ``(shim_dir, db_path)``.
    """
    db_path = tmp_path / "opencode.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE session ("
        "  id TEXT, directory TEXT, title TEXT, time_created REAL, time_updated REAL"
        ")"
    )
    conn.commit()
    conn.close()

    shim = tmp_path / "opencode"
    # Use python3 so we can write to the DB without external sqlite3 CLI
    shim.write_text(
        rf"""#!/usr/bin/env python3
import os, sqlite3, sys, time
db_path = {str(db_path)!r}
if sys.argv[1] == "--version":
    print("opencode 2.0.0", flush=True)
    sys.exit(0)
if sys.argv[1] == "db" and sys.argv[2] == "path":
    print(db_path, flush=True)
    sys.exit(0)
# Simulate OpenCode creating a new session
cwd = os.getcwd()
now = time.time()
conn = sqlite3.connect(db_path)
conn.execute("INSERT INTO session VALUES (?, ?, ?, ?, ?)",
             ("ses_new", cwd, "Session from invoke", now, now))
conn.commit()
conn.close()
print("Simulated opencode output for: " + " ".join(sys.argv[1:]), flush=True)
sys.exit(0)
""",
    )
    shim.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path), prepend=os.pathsep)
    return tmp_path, db_path


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
    assert "Exit code" in result.result_summary


def test_opencode_invoke_propagates_extra_args(shim_env: Path) -> None:
    adapter = OpenCodeAdapter()
    result = adapter.invoke(
        goal="fix bug",
        workspace_path=str(shim_env),
        settings={"extra_args": ["--model", "gpt4"]},
    )

    assert result.invocation["args"] == ["--prompt", "fix bug", "--model", "gpt4"]


def test_opencode_invoke_passes_model_flag(shim_env: Path) -> None:
    adapter = OpenCodeAdapter()
    result = adapter.invoke(
        goal="fix bug",
        workspace_path=str(shim_env),
        settings={"model": "claude-sonnet-4-20250514"},
    )

    assert result.invocation["args"] == ["--prompt", "fix bug", "--model", "claude-sonnet-4-20250514"]


def test_opencode_invoke_model_with_session_flag(shim_env: Path) -> None:
    adapter = OpenCodeAdapter()
    result = adapter.invoke(
        goal="fix bug",
        workspace_path=str(shim_env),
        settings={"opencode_session_id": "ses_abc", "model": "claude-sonnet-4-20250514"},
    )

    assert result.invocation["args"] == ["--session", "ses_abc", "--model", "claude-sonnet-4-20250514"]


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


def test_opencode_invoke_no_db_skips_detection(shim_env: Path) -> None:
    """When no OpenCode DB is found, invoke still succeeds without detection keys."""
    adapter = OpenCodeAdapter()
    result = adapter.invoke(goal="fix bug", workspace_path=str(shim_env), settings={})

    assert result.status == "succeeded"
    assert "opencode_session_id" not in result.invocation


def test_opencode_invoke_detects_new_session(shim_with_db: tuple[Path, Path]) -> None:
    """When the shim creates a session during invoke, the adapter detects it."""
    shim_dir, db_path = shim_with_db
    adapter = OpenCodeAdapter()

    result = adapter.invoke(goal="fix bug", workspace_path=str(shim_dir), settings={})

    assert result.status == "succeeded"
    assert result.invocation["opencode_session_id"] == "ses_new"
    assert result.invocation["opencode_session_title"] == "Session from invoke"


def test_opencode_invoke_detection_only_finds_new_sessions(
    shim_with_db: tuple[Path, Path],
) -> None:
    """Pre-existing sessions are not reported as detected."""
    shim_dir, db_path = shim_with_db

    # Pre-populate a session with an old timestamp
    conn = sqlite3.connect(str(db_path))
    now = time.time()
    conn.execute(
        "INSERT INTO session VALUES (?, ?, ?, ?, ?)",
        ("ses_old", str(shim_dir), "Old session", now - 100, now - 100),
    )
    conn.commit()
    conn.close()

    adapter = OpenCodeAdapter()
    result = adapter.invoke(goal="fix bug", workspace_path=str(shim_dir), settings={})

    assert result.status == "succeeded"
    assert result.invocation["opencode_session_id"] == "ses_new"


def test_opencode_invoke_passes_session_flag_when_set(shim_env: Path) -> None:
    """When settings contains opencode_session_id, only ``--session <id>`` is used (no --prompt)."""
    adapter = OpenCodeAdapter()
    result = adapter.invoke(
        goal="fix bug",
        workspace_path=str(shim_env),
        settings={"opencode_session_id": "ses_abc123"},
    )

    assert result.status == "succeeded"
    assert result.invocation["args"] == ["--session", "ses_abc123"]


def test_opencode_invoke_reports_signal_exit_as_cancelled(shim_env: Path) -> None:
    shim = shim_env / "opencode"
    shim.write_text(
        """#!/usr/bin/env python3
import os, signal, sys
if sys.argv[1] == "--version":
    print("opencode 2.0.0", flush=True)
    sys.exit(0)
if sys.argv[1:3] == ["db", "path"]:
    sys.exit(1)
os.kill(os.getpid(), signal.SIGINT)
""",
    )
    shim.chmod(0o755)

    result = OpenCodeAdapter().invoke(goal="fix bug", workspace_path=str(shim_env), settings={})

    assert result.status == "cancelled"
    assert result.invocation["returncode"] < 0
