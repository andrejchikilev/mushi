"""Command line interface for Mushi."""

import json
import os
import re
import shutil

from pathlib import Path
from typing import Annotated, Any

import typer

from mushi import __version__
from mushi.adapters import registry as adapter_registry
from mushi.core.errors import RecordConflictError, WorkflowError
from mushi.core.profiles import ProfileWorkflow
from mushi.core.schemas import ProfileDefinition, SessionRecord, SessionStatus, TaskStatus
from mushi.storage.errors import RecordNotFoundError
from mushi.storage.filesystem import FilesystemStorage
from mushi.core.handoffs import HandoffWorkflow
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


@task_app.command("remove")
def task_remove(
    ctx: typer.Context,
    task_id: Annotated[str, typer.Argument(help="Task id.")],
) -> None:
    """Remove a task and its sessions, events, and handoffs."""
    _run(lambda: TaskWorkflow(_storage(ctx)).remove_task(task_id))
    typer.echo(f"removed task {task_id}")


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
    backend: Annotated[
        str | None,
        typer.Argument(help="Backend name. Required for new profiles."),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option("--model", "-m", help="AI model for the backend."),
    ] = None,
    timeout: Annotated[
        float | None,
        typer.Option("--timeout", "-t", help="Timeout in seconds. 0 or omit = no timeout."),
    ] = None,
    settings: Annotated[
        str | None,
        typer.Option("--settings", help="JSON object merged with existing settings."),
    ] = None,
) -> None:
    """Create or update a profile."""
    storage = _storage(ctx)
    workflow = ProfileWorkflow(storage)
    try:
        existing = workflow.show_profile(name)
        new_backend = backend or existing.backend
        new_settings = dict(existing.settings)
        if model is not None:
            new_settings["model"] = model
        if timeout is not None:
            new_settings["timeout"] = timeout
        if settings is not None:
            new_settings.update(_parse_settings(settings))
    except RecordNotFoundError:
        if backend is None:
            raise typer.BadParameter("backend is required when creating a new profile")
        new_backend = backend
        new_settings = {}
        if model is not None:
            new_settings["model"] = model
        if timeout is not None:
            new_settings["timeout"] = timeout
        if settings is not None:
            new_settings.update(_parse_settings(settings))

    profile = workflow.save_profile(name=name, backend=new_backend, settings=new_settings)
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


@profile_app.command("migrate-timeout")
def profile_migrate_timeout(ctx: typer.Context) -> None:
    """Add default timeout (0 = no timeout) to all profiles without one."""
    storage = _storage(ctx)
    updated = 0
    for profile in storage.list_profiles():
        if "timeout" not in profile.settings:
            settings = dict(profile.settings)
            settings["timeout"] = 0
            storage.save_profile(profile.model_copy(update={"settings": settings}))
            updated += 1
    typer.echo(f"Updated {updated} profile(s) with default timeout.")


@profile_app.command("remove")
def profile_remove(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Profile name.")],
) -> None:
    """Remove a profile."""
    _run(lambda: ProfileWorkflow(_storage(ctx)).remove_profile(name))
    typer.echo(f"removed profile {name}")


@session_app.command("start")
def session_start(
    ctx: typer.Context,
    task_id: Annotated[str, typer.Argument(help="Task id.")],
    workspace_path: Annotated[
        Path | None,
        typer.Argument(help="Workspace path. Defaults to current directory."),
    ] = None,
    session_id: Annotated[
        str | None,
        typer.Option("--session-id", "-s", help="Session id. Auto-generated if not given."),
    ] = None,
    profile_name: Annotated[
        str | None,
        typer.Option("--profile", "-p", help="Profile name. Defaults to 'default' profile."),
    ] = None,
    goal: Annotated[
        str | None,
        typer.Option("--goal", "-g", help="Session goal. If not given, adapter opens without a prompt."),
    ] = None,
    no_invoke: Annotated[
        bool,
        typer.Option("--no-invoke", help="Record the session without invoking the backend adapter."),
    ] = False,
) -> None:
    """Record a started session and invoke the backend adapter if available."""
    storage = _storage(ctx)
    sid = session_id or _next_session_id(storage, task_id)
    if session_id is not None:
        if storage.find_session_by_id(session_id) is not None:
            typer.echo(f"Session already exists: {session_id}", err=True)
            raise typer.Exit(code=1)
    profile = _resolve_profile(storage, profile_name)
    get_adapter = None if no_invoke else adapter_registry.get
    session = SessionWorkflow(storage, get_adapter=get_adapter).start_session(
        session_id=sid,
        task_id=task_id,
        profile_name=profile,
        workspace_path=workspace_path or Path.cwd(),
        goal=goal or "",
    )
    typer.echo(f"session {session.id} status {session.status.value}")


@session_app.command("finish")
def session_finish(
    ctx: typer.Context,
    session_id: Annotated[str, typer.Argument(help="Session id.")],
) -> None:
    """Record a finished session without invoking a backend."""
    storage = _storage(ctx)
    session = storage.find_session_by_id(session_id)
    if session is None:
        typer.echo(f"Session not found: {session_id}", err=True)
        raise typer.Exit(code=1)
    # TODO: result_summary will include paths to generated artifacts in the future
    session = SessionWorkflow(storage).finish_session(
        task_id=session.task_id,
        session_id=session_id,
        status=SessionStatus.SUCCEEDED,
        result_summary="",
    )
    typer.echo(f"finished session {session.id} status {session.status.value}")


@session_app.command("resume")
def session_resume(
    ctx: typer.Context,
    session_id: Annotated[str, typer.Argument(help="Session id to resume.")],
    no_invoke: Annotated[
        bool,
        typer.Option("--no-invoke", help="Re-open metadata without invoking the backend adapter."),
    ] = False,
) -> None:
    """Re-open a finished session and continue the same backend chat."""
    storage = _storage(ctx)
    prev = storage.find_session_by_id(session_id)
    if prev is None:
        typer.echo(f"Session not found: {session_id}", err=True)
        raise typer.Exit(code=1)
    if not _backend_session_id(prev):
        typer.echo(
            f"Warning: session {session_id} has no backend session ID. "
            "Resume may start a new backend session.",
            err=True,
        )

    get_adapter = None if no_invoke else adapter_registry.get
    reopened = SessionWorkflow(storage, get_adapter=get_adapter).reopen_session(
        task_id=prev.task_id,
        session_id=session_id,
    )
    message = f"reopened session {reopened.id} status {reopened.status.value}"
    if reopened.status == SessionStatus.FAILED and reopened.result_summary:
        message += f" ({reopened.result_summary})"
    typer.echo(message)


@session_app.command("remove")
def session_remove(
    ctx: typer.Context,
    session_id: Annotated[str, typer.Argument(help="Session id.")],
) -> None:
    """Remove a session and its session events."""
    storage = _storage(ctx)
    session = storage.find_session_by_id(session_id)
    if session is None:
        typer.echo(f"Session not found: {session_id}", err=True)
        raise typer.Exit(code=1)
    _run(lambda: SessionWorkflow(storage).remove_session(task_id=session.task_id, session_id=session_id))
    typer.echo(f"removed session {session_id}")


@session_app.command("list")
def session_list(
    ctx: typer.Context,
    task_id: Annotated[str | None, typer.Argument(help="Task id. If not given, list all sessions.")] = None,
) -> None:
    """List sessions. If task_id is given, list only for that task."""
    storage = _storage(ctx)
    sessions: list[SessionRecord] = []
    if task_id is not None:
        sessions = storage.list_sessions(task_id)
    else:
        for task in storage.list_tasks():
            sessions.extend(storage.list_sessions(task.id))
    for session in sessions:
        typer.echo(f"{session.id}\t{session.status.value}\t{session.task_id}\t{session.goal}")


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


def _next_session_id(storage: FilesystemStorage, task_id: str) -> str:
    pattern = re.compile(rf"^s-(\d+)-{re.escape(task_id)}$")
    max_n = 0
    for session in storage.list_sessions(task_id):
        m = pattern.match(session.id)
        if m:
            n = int(m.group(1))
            if n > max_n:
                max_n = n
    return f"s-{max_n + 1}-{task_id}"


def _resolve_profile(storage: FilesystemStorage, name: str | None) -> str:
    if name is not None:
        return name
    try:
        storage.load_profile("default")
        return "default"
    except RecordNotFoundError:
        pass
    if shutil.which("opencode"):
        storage.save_profile(ProfileDefinition(name="default", backend="opencode"))
        return "default"
    raise WorkflowError("No profile specified and default profile could not be created. "
                        "Create a profile first with `profile set` or install opencode.")


def _backend_session_id(session: SessionRecord) -> str | None:
    if session.backend == "opencode":
        value = session.invocation.get("opencode_session_id")
        return value if isinstance(value, str) else None
    if session.backend == "cursor":
        value = session.invocation.get("cursor_agent_id")
        return value if isinstance(value, str) else None
    return None


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
