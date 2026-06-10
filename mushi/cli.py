"""Command line interface for Mushi."""

import json
import os
from pathlib import Path
from typing import Annotated, Any

import typer

from mushi import __version__
from mushi.adapters import registry as adapter_registry
from mushi.core.handoffs import HandoffWorkflow
from mushi.core.profiles import ProfileWorkflow
from mushi.core.schemas import SessionStatus, TaskStatus
from mushi.core.sessions import SessionWorkflow
from mushi.core.tasks import TaskWorkflow
from mushi.storage.filesystem import FilesystemStorage

app = typer.Typer(
    help="Persistent task and session manager for coding agents.",
    no_args_is_help=True,
)
task_app = typer.Typer(help="Task metadata workflows.")
profile_app = typer.Typer(help="Profile workflows.")
session_app = typer.Typer(help="Session metadata workflows.")
handoff_app = typer.Typer(help="Handoff generation workflows.")
app.add_typer(task_app, name="task")
app.add_typer(profile_app, name="profile")
app.add_typer(session_app, name="session")
app.add_typer(handoff_app, name="handoff")

DEFAULT_STORAGE_ROOT = ".mushi"


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"mushi {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            help="Show the Mushi version and exit.",
        ),
    ] = False,
    storage_root: Annotated[
        Path | None,
        typer.Option(
            "--storage-root",
            help="Storage root. Defaults to MUSHI_STORAGE_ROOT or .mushi.",
        ),
    ] = None,
) -> None:
    """Mushi command entrypoint."""
    root = storage_root or Path(os.environ.get("MUSHI_STORAGE_ROOT", DEFAULT_STORAGE_ROOT))
    ctx.obj = {"storage": FilesystemStorage(root)}


@app.command()
def schemas() -> None:
    """Show the current persisted schema version."""
    typer.echo("schema version 1")


@task_app.command("create")
def task_create(
    ctx: typer.Context,
    task_id: Annotated[str, typer.Argument(help="Task id.")],
    title: Annotated[str, typer.Argument(help="Task title.")],
) -> None:
    """Create a task."""
    task = TaskWorkflow(_storage(ctx)).create_task(task_id=task_id, title=title)
    typer.echo(f"created task {task.id}")


@task_app.command("list")
def task_list(ctx: typer.Context) -> None:
    """List tasks."""
    for task in TaskWorkflow(_storage(ctx)).list_tasks():
        typer.echo(f"{task.id}\t{task.status.value}\t{task.title}")


@task_app.command("show")
def task_show(
    ctx: typer.Context,
    task_id: Annotated[str, typer.Argument(help="Task id.")],
) -> None:
    """Show a task."""
    task = TaskWorkflow(_storage(ctx)).show_task(task_id)
    typer.echo(json.dumps(task.model_dump(mode="json"), indent=2))


@task_app.command("status")
def task_status(
    ctx: typer.Context,
    task_id: Annotated[str, typer.Argument(help="Task id.")],
    status: Annotated[TaskStatus, typer.Argument(help="New task status.")],
) -> None:
    """Update task status."""
    task = TaskWorkflow(_storage(ctx)).update_task_status(task_id, status)
    typer.echo(f"updated task {task.id} status {task.status.value}")


@profile_app.command("set")
def profile_set(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name.")],
    backend: Annotated[str, typer.Argument(help="Backend name.")],
    settings: Annotated[
        str,
        typer.Option("--settings", help="JSON object with backend-specific settings."),
    ] = "{}",
) -> None:
    """Create or replace a profile."""
    profile = ProfileWorkflow(_storage(ctx)).save_profile(
        name=name,
        backend=backend,
        settings=_parse_settings(settings),
    )
    typer.echo(f"saved profile {profile.name}")


@profile_app.command("show")
def profile_show(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name.")],
) -> None:
    """Show a profile."""
    profile = ProfileWorkflow(_storage(ctx)).show_profile(name)
    typer.echo(json.dumps(profile.model_dump(mode="json"), indent=2))


@session_app.command("start")
def session_start(
    ctx: typer.Context,
    session_id: Annotated[str, typer.Argument(help="Session id.")],
    task_id: Annotated[str, typer.Argument(help="Task id.")],
    profile_name: Annotated[str, typer.Argument(help="Profile name.")],
    goal: Annotated[str, typer.Argument(help="Session goal.")],
    workspace_path: Annotated[
        Path,
        typer.Argument(help="Workspace path. Defaults to current directory."),
    ] = Path.cwd(),
) -> None:
    """Record a started session and invoke the backend adapter if available."""
    session = SessionWorkflow(_storage(ctx), get_adapter=adapter_registry.get).start_session(
        session_id=session_id,
        task_id=task_id,
        profile_name=profile_name,
        workspace_path=workspace_path,
        goal=goal,
    )
    typer.echo(f"session {session.id} status {session.status.value}")


@session_app.command("finish")
def session_finish(
    ctx: typer.Context,
    task_id: Annotated[str, typer.Argument(help="Task id.")],
    session_id: Annotated[str, typer.Argument(help="Session id.")],
    status: Annotated[SessionStatus, typer.Argument(help="Final session status.")],
    result_summary: Annotated[str, typer.Argument(help="Result summary.")],
) -> None:
    """Record a finished session without invoking a backend."""
    session = SessionWorkflow(_storage(ctx)).finish_session(
        task_id=task_id,
        session_id=session_id,
        status=status,
        result_summary=result_summary,
    )
    typer.echo(f"finished session {session.id} status {session.status.value}")


@session_app.command("resume")
def session_resume(
    ctx: typer.Context,
    session_id: Annotated[str, typer.Argument(help="New session id.")],
    task_id: Annotated[str, typer.Argument(help="Task id.")],
    profile_name: Annotated[str, typer.Argument(help="Profile name.")],
    goal: Annotated[str, typer.Argument(help="Session goal.")],
    resume_from: Annotated[str, typer.Option("--resume-from", help="Previous session id to resume context from.")],
    workspace_path: Annotated[
        Path,
        typer.Argument(help="Workspace path. Defaults to current directory."),
    ] = Path.cwd(),
) -> None:
    """Start a session that resumes context from a previous session."""
    session = SessionWorkflow(_storage(ctx), get_adapter=adapter_registry.get).start_session(
        session_id=session_id,
        task_id=task_id,
        profile_name=profile_name,
        workspace_path=workspace_path,
        goal=goal,
        resume_from=resume_from,
    )
    typer.echo(f"session {session.id} status {session.status.value} (resumed from {resume_from})")


@handoff_app.command("create")
def handoff_create(
    ctx: typer.Context,
    task_id: Annotated[str, typer.Argument(help="Task id.")],
    notes: Annotated[
        str | None,
        typer.Option("--notes", "-n", help="Optional user notes for the handoff."),
    ] = None,
) -> None:
    """Generate a handoff document for a task."""
    storage = _storage(ctx)
    handoff_dir = storage.layout.root / "handoffs"
    workflow = HandoffWorkflow(storage, handoff_dir=str(handoff_dir))
    meta = workflow.generate(task_id, user_notes=notes or "")
    typer.echo(f"handoff {meta.id} created at {meta.path}")


@handoff_app.command("show")
def handoff_show(
    ctx: typer.Context,
    handoff_id: Annotated[str, typer.Argument(help="Handoff id.")],
) -> None:
    """Show the content of a generated handoff."""
    meta = _storage(ctx).load_handoff_metadata(handoff_id)
    path = Path(meta.path)
    if not path.is_file():
        typer.echo(f"Handoff file not found: {path}", err=True)
        raise typer.Exit(code=1)
    content = path.read_text(encoding="utf-8")
    typer.echo(content)


def _storage(ctx: typer.Context) -> FilesystemStorage:
    return ctx.ensure_object(dict)["storage"]


def _parse_settings(raw_settings: str) -> dict[str, Any]:
    try:
        settings = json.loads(raw_settings)
    except json.JSONDecodeError as error:
        raise typer.BadParameter("settings must be a JSON object") from error
    if not isinstance(settings, dict):
        raise typer.BadParameter("settings must be a JSON object")
    return settings
