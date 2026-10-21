import json
from unittest.mock import patch

from typer.testing import CliRunner

from mushi.adapters import registry as adapter_registry
from mushi.adapters.stub import StubAdapter
from mushi.cli import _format_size, app
from mushi.storage.filesystem import FilesystemStorage


def test_cli_shows_help_without_args() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Persistent task and session manager" in result.output


def test_cli_shows_version() -> None:
    result = CliRunner().invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "mushi 0.1.0" in result.output


def test_cli_shows_schema_version() -> None:
    result = CliRunner().invoke(app, ["schemas"])

    assert result.exit_code == 0
    assert "schema version 1" in result.output


def test_format_size_uses_bytes_without_decimals() -> None:
    assert _format_size(512) == "512 B"


def test_format_size_uses_scaled_units_with_one_decimal() -> None:
    assert _format_size(1536) == "1.5 KB"
    assert _format_size(1024 * 1024) == "1.0 MB"
    assert _format_size(1024 * 1024 * 1024) == "1.0 GB"


def test_cli_task_profile_session_workflow(tmp_path) -> None:
    env = {"MUSHI_STORAGE_ROOT": str(tmp_path)}
    runner = CliRunner()

    create_task = runner.invoke(app, ["task", "create", "task-1", "Design storage"], env=env)
    assert create_task.exit_code == 0
    assert "created task task-1" in create_task.output

    set_profile = runner.invoke(
        app,
        ["profile", "set", "default", "test-backend", "--settings", '{"model":"test"}'],
        env=env,
    )
    assert set_profile.exit_code == 0
    assert "saved profile default" in set_profile.output

    start_session = runner.invoke(
        app,
        ["session", "start", "task-1", "/repo",
         "--session-id", "session-1", "--profile", "default", "--goal", "Continue work"],
        env=env,
    )
    assert start_session.exit_code == 0
    assert "session session-1 status running" in start_session.output

    finish_session = runner.invoke(
        app,
        ["session", "finish", "session-1"],
        env=env,
    )
    assert finish_session.exit_code == 0
    assert "finished session session-1 status succeeded" in finish_session.output

    show_task = runner.invoke(app, ["task", "show", "task-1"], env=env)
    assert show_task.exit_code == 0
    data = json.loads(show_task.output)
    assert data["session_ids"] == ["session-1"]


def test_cli_task_status_and_list(tmp_path) -> None:
    env = {"MUSHI_STORAGE_ROOT": str(tmp_path)}
    runner = CliRunner()

    assert runner.invoke(app, ["task", "create", "task-1", "Design storage"], env=env).exit_code == 0
    status = runner.invoke(app, ["task", "status", "task-1", "in_progress"], env=env)
    listing = runner.invoke(app, ["task", "list"], env=env)

    assert status.exit_code == 0
    assert "updated task task-1 status in_progress" in status.output
    assert listing.exit_code == 0
    assert "task-1\tin_progress\tDesign storage" in listing.output


def test_cli_handoff_create_and_show(tmp_path) -> None:
    env = {"MUSHI_STORAGE_ROOT": str(tmp_path)}
    runner = CliRunner()

    create_task = runner.invoke(app, ["task", "create", "task-1", "Design storage"], env=env)
    assert create_task.exit_code == 0

    set_profile = runner.invoke(
        app,
        ["profile", "set", "default", "opencode", "--settings", "{}"],
        env=env,
    )
    assert set_profile.exit_code == 0

    start = runner.invoke(
        app,
        ["session", "start", "task-1", "/repo",
         "--session-id", "session-1", "--profile", "default", "--goal", "Work"],
        env=env,
    )
    assert start.exit_code == 0

    result = runner.invoke(app, ["handoff", "create", "task-1", "--notes", "Manual test"], env=env)
    assert result.exit_code == 0
    assert "handoff" in result.output
    assert "task-1" in result.output

    show = runner.invoke(app, ["handoff", "show", "handoff-task-1"], env=env)
    assert show.exit_code == 0
    assert "# Handoff: Design storage" in show.output


def test_cli_session_resume(tmp_path) -> None:
    env = {"MUSHI_STORAGE_ROOT": str(tmp_path)}
    runner = CliRunner()

    create_task = runner.invoke(app, ["task", "create", "task-1", "Design storage"], env=env)
    assert create_task.exit_code == 0

    set_profile = runner.invoke(
        app, ["profile", "set", "default", "test-backend", "--settings", "{}"], env=env
    )
    assert set_profile.exit_code == 0

    start1 = runner.invoke(
        app, ["session", "start", "task-1", "/repo",
              "--session-id", "session-1", "--profile", "default", "--goal", "First"], env=env
    )
    assert start1.exit_code == 0

    finish1 = runner.invoke(
        app, ["session", "finish", "session-1"], env=env
    )
    assert finish1.exit_code == 0

    resume = runner.invoke(app, ["session", "resume", "session-1"], env=env)
    assert resume.exit_code == 0
    assert "reopened session session-1 status running" in resume.output


def test_cli_task_resume(tmp_path) -> None:
    env = {"MUSHI_STORAGE_ROOT": str(tmp_path)}
    runner = CliRunner()

    create_task = runner.invoke(app, ["task", "create", "task-1", "Design storage"], env=env)
    assert create_task.exit_code == 0

    set_profile = runner.invoke(
        app, ["profile", "set", "default", "test-backend", "--settings", "{}"], env=env
    )
    assert set_profile.exit_code == 0

    start1 = runner.invoke(
        app, ["session", "start", "task-1", "/repo",
              "--session-id", "session-1", "--profile", "default", "--goal", "First"], env=env
    )
    assert start1.exit_code == 0

    finish1 = runner.invoke(
        app, ["session", "finish", "session-1"], env=env
    )
    assert finish1.exit_code == 0

    resume = runner.invoke(app, ["task", "resume", "task-1"], env=env)
    assert resume.exit_code == 0
    assert "reopened session-1 status running" in resume.output


def test_cli_session_resume_warns_when_backend_session_id_is_missing(tmp_path) -> None:
    env = {"MUSHI_STORAGE_ROOT": str(tmp_path)}
    runner = CliRunner()
    runner.invoke(app, ["task", "create", "task-1", "Design storage"], env=env)
    runner.invoke(app, ["profile", "set", "default", "opencode", "--settings", "{}"], env=env)
    runner.invoke(app, ["session", "start", "task-1", "--session-id", "session-1", "--no-invoke"], env=env)
    runner.invoke(app, ["session", "finish", "session-1"], env=env)

    resume = runner.invoke(app, ["session", "resume", "session-1", "--no-invoke"], env=env)

    assert resume.exit_code == 0
    assert "has no backend session ID" in resume.output
    assert "reopened session session-1 status running" in resume.output


def test_cli_session_resume_shows_failure_summary(tmp_path) -> None:
    env = {"MUSHI_STORAGE_ROOT": str(tmp_path)}
    runner = CliRunner()
    adapter_registry.register(
        "failing-stub",
        StubAdapter(result_status="failed", result_summary="Backend exited unexpectedly"),
    )
    runner.invoke(app, ["task", "create", "task-1", "Design storage"], env=env)
    runner.invoke(app, ["profile", "set", "default", "failing-stub", "--settings", "{}"], env=env)
    runner.invoke(
        app,
        ["session", "start", "task-1", "--session-id", "session-1", "--goal", "First"],
        env=env,
    )

    resume = runner.invoke(app, ["session", "resume", "session-1"], env=env)

    assert resume.exit_code == 0
    assert "reopened session session-1 status failed (Backend exited unexpectedly)" in resume.output


def test_cli_session_start_no_invoke_skips_adapter(tmp_path) -> None:
    env = {"MUSHI_STORAGE_ROOT": str(tmp_path)}
    runner = CliRunner()
    adapter_registry.register(
        "no-invoke-stub",
        StubAdapter(result_status="failed", result_summary="Should not run"),
    )
    runner.invoke(app, ["task", "create", "task-1", "Design storage"], env=env)
    runner.invoke(app, ["profile", "set", "default", "no-invoke-stub", "--settings", "{}"], env=env)

    result = runner.invoke(
        app,
        ["session", "start", "task-1", "--session-id", "session-1", "--goal", "First", "--no-invoke"],
        env=env,
    )

    assert result.exit_code == 0
    assert "session session-1 status running" in result.output


def test_cli_session_resume_no_invoke_skips_adapter(tmp_path) -> None:
    env = {"MUSHI_STORAGE_ROOT": str(tmp_path)}
    runner = CliRunner()
    adapter_registry.register(
        "resume-no-invoke-stub",
        StubAdapter(result_status="failed", result_summary="Should not run"),
    )
    runner.invoke(app, ["task", "create", "task-1", "Design storage"], env=env)
    runner.invoke(app, ["profile", "set", "default", "resume-no-invoke-stub", "--settings", "{}"], env=env)
    runner.invoke(
        app,
        ["session", "start", "task-1", "--session-id", "session-1", "--goal", "First", "--no-invoke"],
        env=env,
    )
    runner.invoke(app, ["session", "finish", "session-1"], env=env)

    result = runner.invoke(app, ["session", "resume", "session-1", "--no-invoke"], env=env)

    assert result.exit_code == 0
    assert "reopened session session-1 status running" in result.output


def test_cli_search(tmp_path) -> None:
    env = {"MUSHI_STORAGE_ROOT": str(tmp_path)}
    runner = CliRunner()

    create = runner.invoke(app, ["task", "create", "task-1", "Design storage"], env=env)
    assert create.exit_code == 0

    result = runner.invoke(app, ["search", "query", "--text", "storage"], env=env)
    assert result.exit_code == 0
    assert "task-task-1" in result.output

    rebuild = runner.invoke(app, ["search", "rebuild"], env=env)
    assert rebuild.exit_code == 0
    assert "Search index rebuilt" in rebuild.output


def test_cli_rejects_non_object_profile_settings(tmp_path) -> None:
    result = CliRunner().invoke(
        app,
        ["profile", "set", "default", "opencode", "--settings", "[]"],
        env={"MUSHI_STORAGE_ROOT": str(tmp_path)},
    )

    assert result.exit_code != 0
    assert "settings must be a JSON object" in result.output


def test_cli_profile_list(tmp_path) -> None:
    env = {"MUSHI_STORAGE_ROOT": str(tmp_path)}
    runner = CliRunner()

    runner.invoke(app, ["profile", "set", "dev", "opencode", "--settings", "{}"], env=env)
    runner.invoke(app, ["profile", "set", "prod", "cursor", "--settings", "{}"], env=env)

    result = runner.invoke(app, ["profile", "list"], env=env)
    assert result.exit_code == 0
    assert "dev\topencode" in result.output
    assert "prod\tcursor" in result.output


def test_cli_profile_set_with_model(tmp_path) -> None:
    env = {"MUSHI_STORAGE_ROOT": str(tmp_path)}
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["profile", "set", "default", "opencode", "--model", "claude-sonnet-4-20250514"],
        env=env,
    )
    assert result.exit_code == 0

    show = runner.invoke(app, ["profile", "show", "default"], env=env)
    assert show.exit_code == 0
    data = json.loads(show.output)
    assert data["settings"]["model"] == "claude-sonnet-4-20250514"


def test_cli_profile_update_model_without_backend(tmp_path) -> None:
    env = {"MUSHI_STORAGE_ROOT": str(tmp_path)}
    runner = CliRunner()

    runner.invoke(
        app,
        ["profile", "set", "default", "opencode", "--model", "old-model"],
        env=env,
    )
    result = runner.invoke(
        app,
        ["profile", "set", "default", "--model", "new-model"],
        env=env,
    )
    assert result.exit_code == 0

    show = runner.invoke(app, ["profile", "show", "default"], env=env)
    assert show.exit_code == 0
    data = json.loads(show.output)
    assert data["settings"]["model"] == "new-model"
    assert data["backend"] == "opencode"


def test_cli_profile_set_with_timeout(tmp_path) -> None:
    env = {"MUSHI_STORAGE_ROOT": str(tmp_path)}
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["profile", "set", "default", "opencode", "--timeout", "7200"],
        env=env,
    )
    assert result.exit_code == 0

    show = runner.invoke(app, ["profile", "show", "default"], env=env)
    assert show.exit_code == 0
    data = json.loads(show.output)
    assert data["settings"]["timeout"] == 7200


def test_cli_profile_update_timeout_without_backend(tmp_path) -> None:
    env = {"MUSHI_STORAGE_ROOT": str(tmp_path)}
    runner = CliRunner()

    runner.invoke(
        app,
        ["profile", "set", "default", "opencode", "--timeout", "3600"],
        env=env,
    )
    result = runner.invoke(
        app,
        ["profile", "set", "default", "--timeout", "0"],
        env=env,
    )
    assert result.exit_code == 0

    show = runner.invoke(app, ["profile", "show", "default"], env=env)
    assert show.exit_code == 0
    data = json.loads(show.output)
    assert data["settings"]["timeout"] == 0


def test_cli_profile_migrate_timeout(tmp_path) -> None:
    env = {"MUSHI_STORAGE_ROOT": str(tmp_path)}
    runner = CliRunner()

    runner.invoke(app, ["profile", "set", "dev", "opencode", "--settings", "{}"], env=env)
    runner.invoke(app, ["profile", "set", "prod", "cursor", "--settings", '{"model":"gpt4"}'], env=env)

    result = runner.invoke(app, ["profile", "migrate-timeout"], env=env)
    assert result.exit_code == 0
    assert "Updated 2 profile(s) with default timeout" in result.output

    show_dev = runner.invoke(app, ["profile", "show", "dev"], env=env)
    assert json.loads(show_dev.output)["settings"]["timeout"] == 0

    show_prod = runner.invoke(app, ["profile", "show", "prod"], env=env)
    assert json.loads(show_prod.output)["settings"]["timeout"] == 0
    env = {"MUSHI_STORAGE_ROOT": str(tmp_path)}
    runner = CliRunner()

    runner.invoke(app, ["task", "create", "task-1", "Design storage"], env=env)
    runner.invoke(app, ["profile", "set", "default", "test-backend", "--settings", "{}"], env=env)
    runner.invoke(
        app, ["session", "start", "task-1", "/repo",
              "--session-id", "session-1", "--profile", "default", "--goal", "First"], env=env
    )
    runner.invoke(
        app, ["session", "finish", "session-1"], env=env
    )
    runner.invoke(
        app, ["session", "start", "task-1", "/repo",
              "--session-id", "session-2", "--profile", "default", "--goal", "Second"], env=env
    )

    list_result = runner.invoke(app, ["session", "list", "task-1"], env=env)
    assert list_result.exit_code == 0
    rows = [line.split("\t") for line in list_result.output.splitlines()]
    assert rows[0][:3] == ["session-1", "succeeded", "task-1"]
    assert rows[0][3].endswith(" B")
    assert rows[0][4] == "First"
    assert rows[1][:3] == ["session-2", "running", "task-1"]
    assert rows[1][3].endswith(" B")
    assert rows[1][4] == "Second"

    show_result = runner.invoke(app, ["session", "show", "session-1"], env=env)
    assert show_result.exit_code == 0
    assert '"id": "session-1"' in show_result.output
    assert '"task_id": "task-1"' in show_result.output


def test_cli_profile_remove(tmp_path) -> None:
    env = {"MUSHI_STORAGE_ROOT": str(tmp_path)}
    runner = CliRunner()
    runner.invoke(app, ["profile", "set", "default", "opencode", "--settings", "{}"], env=env)

    result = runner.invoke(app, ["profile", "remove", "default"], env=env)

    assert result.exit_code == 0
    assert "removed profile default" in result.output
    show = runner.invoke(app, ["profile", "show", "default"], env=env)
    assert show.exit_code != 0


def test_cli_session_remove(tmp_path) -> None:
    env = {"MUSHI_STORAGE_ROOT": str(tmp_path)}
    runner = CliRunner()
    runner.invoke(app, ["task", "create", "task-1", "Design storage"], env=env)
    runner.invoke(app, ["profile", "set", "default", "test-backend", "--settings", "{}"], env=env)
    runner.invoke(
        app,
        ["session", "start", "task-1", "/repo",
         "--session-id", "session-1", "--profile", "default", "--goal", "First"],
        env=env,
    )

    result = runner.invoke(app, ["session", "remove", "session-1"], env=env)

    assert result.exit_code == 0
    assert "removed session session-1" in result.output
    show = runner.invoke(app, ["session", "show", "session-1"], env=env)
    assert show.exit_code != 0
    task = runner.invoke(app, ["task", "show", "task-1"], env=env)
    data = json.loads(task.output)
    assert data["session_ids"] == []


def test_cli_task_remove(tmp_path) -> None:
    env = {"MUSHI_STORAGE_ROOT": str(tmp_path)}
    runner = CliRunner()
    runner.invoke(app, ["task", "create", "task-1", "Design storage"], env=env)

    result = runner.invoke(app, ["task", "remove", "task-1"], env=env)

    assert result.exit_code == 0
    assert "removed task task-1" in result.output
    show = runner.invoke(app, ["task", "show", "task-1"], env=env)
    assert show.exit_code != 0


def test_cli_session_list_shows_cursor_backend_size(tmp_path) -> None:
    env = {"MUSHI_STORAGE_ROOT": str(tmp_path)}
    runner = CliRunner()
    runner.invoke(app, ["task", "create", "task-1", "Test"], env=env)
    runner.invoke(app, ["profile", "set", "default", "cursor", "--settings", "{}"], env=env)
    runner.invoke(
        app, ["session", "start", "task-1", "/repo",
              "--session-id", "session-1", "--profile", "default", "--goal", "Test", "--no-invoke"],
        env=env,
    )

    storage = FilesystemStorage(tmp_path)
    session = storage.load_session("task-1", "session-1")
    session = session.model_copy(update={
        "invocation": {"cursor_agent_id": "test-agent-789"},
    })
    storage.save_session(session)

    chats_dir = tmp_path / ".cursor" / "chats"
    agent_dir = chats_dir / "somehash" / "test-agent-789"
    agent_dir.mkdir(parents=True)
    (agent_dir / "data.txt").write_text("x" * 2048)

    with patch("mushi.adapters._cursor_db.CHATS_DIR", chats_dir):
        result = runner.invoke(app, ["session", "list"], env=env)

    assert result.exit_code == 0
    rows = [line.split("\t") for line in result.output.splitlines()]
    assert rows[0][:3] == ["session-1", "running", "task-1"]
    assert "2.0 KB" in rows[0][3]


def test_cli_session_list_shows_opencode_db_summary(tmp_path) -> None:
    env = {"MUSHI_STORAGE_ROOT": str(tmp_path)}
    runner = CliRunner()
    runner.invoke(app, ["task", "create", "task-1", "Test"], env=env)
    runner.invoke(app, ["profile", "set", "default", "opencode", "--settings", "{}"], env=env)
    runner.invoke(
        app, ["session", "start", "task-1", "/repo",
              "--session-id", "session-1", "--profile", "default", "--goal", "Test", "--no-invoke"],
        env=env,
    )

    db_path = tmp_path / "opencode.db"
    db_path.write_text("x" * 512)

    with patch("mushi.adapters.opencode.get_opencode_db_path", return_value=db_path):
        result = runner.invoke(app, ["session", "list"], env=env)

    assert result.exit_code == 0
    assert "*\topencode DB: 512 B" in result.output


def test_cli_session_remove_purges_cursor_backend(tmp_path) -> None:
    env = {"MUSHI_STORAGE_ROOT": str(tmp_path)}
    runner = CliRunner()
    runner.invoke(app, ["task", "create", "task-1", "Test"], env=env)
    runner.invoke(app, ["profile", "set", "default", "cursor", "--settings", "{}"], env=env)
    runner.invoke(
        app, ["session", "start", "task-1", "/repo",
              "--session-id", "session-1", "--profile", "default", "--goal", "Test", "--no-invoke"],
        env=env,
    )

    storage = FilesystemStorage(tmp_path)
    session = storage.load_session("task-1", "session-1")
    session = session.model_copy(update={
        "invocation": {"cursor_agent_id": "test-agent-101"},
    })
    storage.save_session(session)

    chats_dir = tmp_path / ".cursor" / "chats"
    agent_dir = chats_dir / "somehash" / "test-agent-101"
    agent_dir.mkdir(parents=True)
    (agent_dir / "data.txt").write_text("some data")
    assert agent_dir.exists()

    with patch("mushi.adapters._cursor_db.CHATS_DIR", chats_dir):
        result = runner.invoke(app, ["session", "remove", "session-1"], env=env)

    assert result.exit_code == 0
    assert "removed session session-1" in result.output
    assert not agent_dir.exists()


def test_cli_session_remove_tolerates_missing_cursor_metadata(tmp_path) -> None:
    env = {"MUSHI_STORAGE_ROOT": str(tmp_path)}
    runner = CliRunner()
    runner.invoke(app, ["task", "create", "task-1", "Test"], env=env)
    runner.invoke(app, ["profile", "set", "default", "cursor", "--settings", "{}"], env=env)
    runner.invoke(
        app, ["session", "start", "task-1", "/repo",
              "--session-id", "session-1", "--profile", "default", "--goal", "Test", "--no-invoke"],
        env=env,
    )

    result = runner.invoke(app, ["session", "remove", "session-1"], env=env)

    assert result.exit_code == 0
    assert "removed session session-1" in result.output


def test_cli_task_remove_purges_cursor_backend_for_all_sessions(tmp_path) -> None:
    env = {"MUSHI_STORAGE_ROOT": str(tmp_path)}
    runner = CliRunner()
    runner.invoke(app, ["task", "create", "task-1", "Test"], env=env)
    runner.invoke(app, ["profile", "set", "default", "cursor", "--settings", "{}"], env=env)
    runner.invoke(
        app, ["session", "start", "task-1", "/repo",
              "--session-id", "session-1", "--profile", "default", "--goal", "First", "--no-invoke"],
        env=env,
    )
    runner.invoke(
        app, ["session", "start", "task-1", "/repo",
              "--session-id", "session-2", "--profile", "default", "--goal", "Second", "--no-invoke"],
        env=env,
    )

    storage = FilesystemStorage(tmp_path)
    for sid, agent_id in [("session-1", "agent-a"), ("session-2", "agent-b")]:
        session = storage.load_session("task-1", sid)
        session = session.model_copy(update={"invocation": {"cursor_agent_id": agent_id}})
        storage.save_session(session)

    chats_dir = tmp_path / ".cursor" / "chats"
    for agent_id in ("agent-a", "agent-b"):
        agent_dir = chats_dir / "hash" / agent_id
        agent_dir.mkdir(parents=True)
        (agent_dir / "data.txt").write_text("some data")
        assert agent_dir.exists()

    with patch("mushi.adapters._cursor_db.CHATS_DIR", chats_dir):
        result = runner.invoke(app, ["task", "remove", "task-1"], env=env)

    assert result.exit_code == 0
    assert "removed task task-1" in result.output
    for agent_id in ("agent-a", "agent-b"):
        assert not (chats_dir / "hash" / agent_id).exists()


def test_cli_task_remove_tolerates_missing_cursor_metadata(tmp_path) -> None:
    env = {"MUSHI_STORAGE_ROOT": str(tmp_path)}
    runner = CliRunner()
    runner.invoke(app, ["task", "create", "task-1", "Test"], env=env)
    runner.invoke(app, ["profile", "set", "default", "cursor", "--settings", "{}"], env=env)
    runner.invoke(
        app, ["session", "start", "task-1", "/repo",
              "--session-id", "session-1", "--profile", "default", "--goal", "Test", "--no-invoke"],
        env=env,
    )

    result = runner.invoke(app, ["task", "remove", "task-1"], env=env)

    assert result.exit_code == 0
    assert "removed task task-1" in result.output
