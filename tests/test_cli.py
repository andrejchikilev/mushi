import json

from typer.testing import CliRunner

from mushi.cli import app


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
        ["session", "start", "session-1", "task-1", "default", "/repo", "Continue work"],
        env=env,
    )
    assert start_session.exit_code == 0
    assert "session session-1 status running" in start_session.output

    finish_session = runner.invoke(
        app,
        ["session", "finish", "task-1", "session-1", "succeeded", "Recorded metadata"],
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
        ["session", "start", "session-1", "task-1", "default", "/repo", "Work"],
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
        app, ["session", "start", "session-1", "task-1", "default", "/repo", "First"], env=env
    )
    assert start1.exit_code == 0

    finish1 = runner.invoke(
        app, ["session", "finish", "task-1", "session-1", "succeeded", "Phase one done"], env=env
    )
    assert finish1.exit_code == 0

    resume = runner.invoke(app, ["session", "resume", "session-1"], env=env)
    assert resume.exit_code == 0
    assert "resumed session-1 as rsession-1" in resume.output


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
        app, ["session", "start", "session-1", "task-1", "default", "/repo", "First"], env=env
    )
    assert start1.exit_code == 0

    finish1 = runner.invoke(
        app, ["session", "finish", "task-1", "session-1", "succeeded", "Phase one done"], env=env
    )
    assert finish1.exit_code == 0

    resume = runner.invoke(app, ["task", "resume", "task-1"], env=env)
    assert resume.exit_code == 0
    assert "resumed session-1" in resume.output


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


def test_cli_session_list_and_show(tmp_path) -> None:
    env = {"MUSHI_STORAGE_ROOT": str(tmp_path)}
    runner = CliRunner()

    runner.invoke(app, ["task", "create", "task-1", "Design storage"], env=env)
    runner.invoke(app, ["profile", "set", "default", "test-backend", "--settings", "{}"], env=env)
    runner.invoke(
        app, ["session", "start", "session-1", "task-1", "default", "/repo", "First"], env=env
    )
    runner.invoke(
        app, ["session", "finish", "task-1", "session-1", "succeeded", "Phase one done"], env=env
    )
    runner.invoke(
        app, ["session", "start", "session-2", "task-1", "default", "/repo", "Second"], env=env
    )

    list_result = runner.invoke(app, ["session", "list", "task-1"], env=env)
    assert list_result.exit_code == 0
    assert "session-1\tsucceeded\t" in list_result.output
    assert "session-2\trunning\t" in list_result.output

    show_result = runner.invoke(app, ["session", "show", "session-1"], env=env)
    assert show_result.exit_code == 0
    assert '"id": "session-1"' in show_result.output
    assert '"task_id": "task-1"' in show_result.output
