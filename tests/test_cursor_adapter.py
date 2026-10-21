"""Tests for Cursor CLI adapter using a shim binary."""

import os
import threading
from pathlib import Path
from typing import Any

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


def test_cursor_invoke_adds_resume_flag_when_agent_id_in_settings(shim_env: Path) -> None:
    """When settings contains cursor_agent_id, only ``--resume <id>`` is used (no goal)."""
    adapter = CursorCliAdapter()
    result = adapter.invoke(
        goal="fix bug",
        workspace_path=str(shim_env),
        settings={"cursor_agent_id": "abc-123-def"},
    )

    assert result.status == "succeeded"
    assert result.invocation["args"] == ["agent", "--resume", "abc-123-def"]


def test_cursor_invoke_passes_model_flag(shim_env: Path) -> None:
    adapter = CursorCliAdapter()
    result = adapter.invoke(
        goal="fix bug",
        workspace_path=str(shim_env),
        settings={"model": "gpt-4"},
    )

    assert result.invocation["args"] == ["agent", "fix bug", "--model", "gpt-4"]


def test_cursor_invoke_model_with_resume_flag(shim_env: Path) -> None:
    adapter = CursorCliAdapter()
    result = adapter.invoke(
        goal="fix bug",
        workspace_path=str(shim_env),
        settings={"cursor_agent_id": "abc-123", "model": "gpt-4"},
    )

    assert result.invocation["args"] == ["agent", "--resume", "abc-123", "--model", "gpt-4"]


def test_cursor_invoke_reports_signal_exit_as_cancelled(shim_env: Path) -> None:
    shim = shim_env / "cursor"
    shim.write_text(
        """#!/usr/bin/env python3
import os, signal, sys
if sys.argv[1] == "--version":
    print("cursor 1.2.3", flush=True)
    sys.exit(0)
os.kill(os.getpid(), signal.SIGINT)
""",
    )
    shim.chmod(0o755)

    result = CursorCliAdapter().invoke(goal="fix bug", workspace_path=str(shim_env), settings={})

    assert result.status == "cancelled"
    assert result.invocation["returncode"] < 0


@pytest.fixture
def chats_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Fake cursor chats/projects dirs and a shim that opens a new agent each run."""
    import json

    chats = tmp_path / "chats"
    chats.mkdir()
    (tmp_path / "projects").mkdir()
    ws = tmp_path / "ws"
    ws.mkdir()

    shim = tmp_path / "cursor"
    shim.write_text(
        "\n".join([
            "#!/usr/bin/env python3",
            "import json, sqlite3, sys, time, uuid, pathlib",
            'if sys.argv[1] == "--version":',
            '    print("cursor 1.2.3")',
            "    sys.exit(0)",
            'prompt = sys.argv[2] if len(sys.argv) > 2 else ""',
            "agent_id = str(uuid.uuid4())",
            'agent_dir = pathlib.Path(%r) / "unknown-hash" / agent_id' % str(chats),
            "agent_dir.mkdir(parents=True)",
            'conn = sqlite3.connect(str(agent_dir / "store.db"))',
            'conn.execute("CREATE TABLE meta (key TEXT, value TEXT)")',
            'meta = json.dumps({"agentId": agent_id, "name": "Session: " + prompt,',
            '                  "createdAt": int(time.time() * 1000)})',
            'conn.execute("INSERT INTO meta VALUES (\'0\', ?)", (meta.encode("utf-8").hex(),))',
            "conn.commit()",
            "conn.close()",
            "sys.exit(0)",
        ]),
    )
    shim.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path), prepend=os.pathsep)
    monkeypatch.setattr("mushi.adapters._cursor_db.CHATS_DIR", chats)
    monkeypatch.setattr("mushi.adapters._cursor_db.PROJECTS_DIR", tmp_path / "projects")
    return ws


def test_cursor_invoke_attributes_new_agent_to_own_run(chats_env: Path) -> None:
    adapter = CursorCliAdapter()
    result = adapter.invoke(goal="fix the bug", workspace_path=str(chats_env), settings={})

    assert result.invocation["cursor_agent_id"]
    assert result.invocation["cursor_agent_name"] == "Session: fix the bug"


def test_cursor_invoke_resume_keeps_existing_agent_id(chats_env: Path) -> None:
    adapter = CursorCliAdapter()
    before = adapter.invoke(goal="first", workspace_path=str(chats_env), settings={})
    agent_id = before.invocation["cursor_agent_id"]

    resumed = adapter.invoke(
        goal="continue", workspace_path=str(chats_env),
        settings={"cursor_agent_id": agent_id, "cursor_agent_name": before.invocation["cursor_agent_name"]},
    )

    assert resumed.invocation["cursor_agent_id"] == agent_id
    assert resumed.invocation["args"] == ["agent", "--resume", agent_id]


def test_cursor_concurrent_agents_attribute_own_ids(chats_env: Path) -> None:
    """Two concurrent agents in the same workspace each record their own agent id."""
    results: dict[str, Any] = {}

    def run(goal: str) -> None:
        results[goal] = CursorCliAdapter().invoke(goal=goal, workspace_path=str(chats_env), settings={})

    t1 = threading.Thread(target=lambda: run("goal-one"))
    t2 = threading.Thread(target=lambda: run("goal-two"))
    t1.start(); t2.start(); t1.join(); t2.join()

    ids = {
        goal: results[goal].invocation.get("cursor_agent_id")
        for goal in ("goal-one", "goal-two")
    }
    assert ids["goal-one"], ids["goal-two"]
    assert ids["goal-one"] != ids["goal-two"]
    assert results["goal-one"].invocation["cursor_agent_name"] == "Session: goal-one"
    assert results["goal-two"].invocation["cursor_agent_name"] == "Session: goal-two"
