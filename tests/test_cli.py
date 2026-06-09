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
        ["profile", "set", "default", "opencode", "--settings", '{"model":"test"}'],
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
    assert "started session session-1" in start_session.output

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


def test_cli_rejects_non_object_profile_settings(tmp_path) -> None:
    result = CliRunner().invoke(
        app,
        ["profile", "set", "default", "opencode", "--settings", "[]"],
        env={"MUSHI_STORAGE_ROOT": str(tmp_path)},
    )

    assert result.exit_code != 0
    assert "settings must be a JSON object" in result.output
