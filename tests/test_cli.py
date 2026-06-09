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
