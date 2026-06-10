"""Command line interface for Mushi."""

import json
import os

from pathlib import Path
from typing import Annotated, Any

import typer

from mushi import __version__
from mushi.adapters import registry as adapter_registry
from mushi.core.errors import RecordConflictError, WorkflowError
from mushi.storage.errors import RecordNotFoundError
from mushi.storage.filesystem import FilesystemStorage
from mushi.core.handoffs import HandoffWorkflow
from mushi.core.profiles import ProfileWorkflow
from mushi.core.schemas import SessionStatus, TaskStatus
from mushi.core.search import SearchBuilder, SearchQuery, Searcher
from mushi.core.sessions import SessionWorkflow
from mushi.core.tasks import TaskWorkflow

app = typer.Typer(
    help="Persistent task and session manager for coding agents.",
    no_args_is_help=True,
)
task_app = typer.Typer(help="Task metadata workflows.")
profile_app = typer.Typer(help="Profile workflows.")
session_app = typer.Typer(help="Session metadata workflows.")
handoff_app = typer.Typer(help="Handoff generation workflows.")
search_app = typer.Typer(help="Search task context.")
app.add_typer(task_app, name="task")
app.add_typer(profile_app, name="profile")
app.add_typer(session_app, name="session")
app.add_typer(handoff_app, name="handoff")
app.add_typer(search_app, name="search")

def _load_dotenv() -> None:
    env_path = Path.cwd() / ".env"
    if env_path.is_file():
        for line in env_path.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


def _default_storage_root() -> Path:
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data) / "mushi"
    return Path.home() / ".local" / "share" / "mushi"


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
            help="Storage root. Defaults to MUSHI_STORAGE_ROOT or XDG_DATA_HOME/mushi.",
        ),
    ] = None,
) -> None:
    """Mushi command entrypoint."""
    root = storage_root or Path(os.environ.get("MUSHI_STORAGE_ROOT", _default_storage_root()))
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
    task = _run(lambda: TaskWorkflow(_storage(ctx)).create_task(task_id=task_id, title=title))
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


@task_app.command("resume")
def task_resume(
    ctx: typer.Context,
    task_id: Annotated[str, typer.Argument(help="Task id.")],
) -> None:
    """Re-open the last session of a task."""
    storage = _storage(ctx)
    task = TaskWorkflow(storage).show_task(task_id)
    if not task.session_ids:
        typer.echo(f"No sessions for task: {task_id}", err=True)
        raise typer.Exit(code=1)

    last_id = task.session_ids[-1]
    reopened = SessionWorkflow(storage, get_adapter=adapter_registry.get).reopen_session(
        task_id=task_id,
        session_id=last_id,
    )
    typer.echo(f"reopened {last_id} status {reopened.status.value}")


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


@profile_app.command("list")
def profile_list(ctx: typer.Context) -> None:
    """List profiles."""
    for profile in ProfileWorkflow(_storage(ctx)).list_profiles():
        typer.echo(f"{profile.name}\t{profile.backend}")


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
    session_id: Annotated[str, typer.Argument(help="Session id to resume.")],
) -> None:
    """Re-open a finished session and continue the same backend chat."""
    storage = _storage(ctx)
    prev = storage.find_session_by_id(session_id)
    if prev is None:
        typer.echo(f"Session not found: {session_id}", err=True)
        raise typer.Exit(code=1)

    reopened = SessionWorkflow(storage, get_adapter=adapter_registry.get).reopen_session(
        task_id=prev.task_id,
        session_id=session_id,
    )
    typer.echo(f"reopened session {reopened.id} status {reopened.status.value}")


@session_app.command("list")
def session_list(
    ctx: typer.Context,
    task_id: Annotated[str, typer.Argument(help="Task id.")],
) -> None:
    """List sessions for a task."""
    storage = _storage(ctx)
    for session in storage.list_sessions(task_id):
        typer.echo(f"{session.id}\t{session.status.value}\t{session.goal}")


@session_app.command("show")
def session_show(
    ctx: typer.Context,
    session_id: Annotated[str, typer.Argument(help="Session id.")],
) -> None:
    """Show a session by id."""
    storage = _storage(ctx)
    session = storage.find_session_by_id(session_id)
    if session is None:
        typer.echo(f"Session not found: {session_id}", err=True)
        raise typer.Exit(code=1)
    typer.echo(json.dumps(session.model_dump(mode="json"), indent=2))


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


@search_app.command("query")
def search_query(
    ctx: typer.Context,
    text: Annotated[str | None, typer.Option("--text", "-t", help="Text to search for.")] = None,
    type: Annotated[str | None, typer.Option("--type", help="Record type: task, session, event, handoff.")] = None,
    backend: Annotated[str | None, typer.Option("--backend", help="Backend name.")] = None,
    status: Annotated[str | None, typer.Option("--status", help="Task or session status.")] = None,
) -> None:
    """Search across tasks, sessions, events, and handoffs."""
    storage = _storage(ctx)
    builder = SearchBuilder(storage)
    if not storage.layout.search_index_dir.exists():
        builder.build_index()

    searcher = Searcher(storage)
    query = SearchQuery(
        text=text or "",
        record_type=type,
        backend=backend,
        task_status=status,
    )
    results = searcher.search(query)

    if not results:
        typer.echo("No results.")
        return

    for r in results:
        snippet = r.text[:80].replace("\n", " ")
        typer.echo(f"{r.id:<30s} {r.record_type:<8s} {snippet}")


@search_app.command("rebuild")
def search_rebuild(ctx: typer.Context) -> None:
    """Rebuild the search index from scratch."""
    storage = _storage(ctx)
    SearchBuilder(storage).rebuild()
    typer.echo("Search index rebuilt.")


def _run(wf_callable: Any) -> Any:
    """Execute a workflow callable and translate known errors to CLI messages."""
    try:
        return wf_callable()
    except RecordNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from e
    except RecordConflictError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from e
    except WorkflowError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from e


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
