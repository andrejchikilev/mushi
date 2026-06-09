"""Command line interface for Mushi."""

from typing import Annotated

import typer

from mushi import __version__

app = typer.Typer(
    help="Persistent task and session manager for coding agents.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"mushi {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            help="Show the Mushi version and exit.",
        ),
    ] = False,
) -> None:
    """Mushi command entrypoint."""


@app.command()
def schemas() -> None:
    """Show the current persisted schema version."""
    typer.echo("schema version 1")
