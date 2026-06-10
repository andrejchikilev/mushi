"""Schema version checking and migration placeholder."""

from pathlib import Path

from mushi.core.schemas import SCHEMA_VERSION
from mushi.storage.serialization import record_from_json
from mushi.storage.files import read_text_file
from mushi.storage.filesystem import FilesystemStorage


CURRENT_SCHEMA_VERSION = SCHEMA_VERSION


def check_schema_version(storage: FilesystemStorage) -> dict[str, int]:
    """Scan stored records and return a mapping of record kind to schema version.

    Returns dict like {"task": 1, "session": 1, ...}. If a record kind has no
    stored data, it is omitted.
    """
    versions: dict[str, int] = {}

    for task in storage.list_tasks():
        versions["task"] = task.schema_version
        break

    profiles = storage.list_profiles()
    if profiles:
        versions["profile"] = profiles[0].schema_version

    for task in storage.list_tasks():
        events = storage.list_events(task.id)
        if events:
            versions["event"] = events[0].schema_version
        for sid in task.session_ids:
            session = storage.load_session(task.id, sid)
            versions["session"] = session.schema_version
            break
        break

    return versions


def migrate(storage: FilesystemStorage, from_version: int, to_version: int) -> None:
    """Migrate storage from *from_version* to *to_version*.

    Raises NotImplementedError until a real schema change occurs.
    """
    if from_version == to_version:
        return
    raise NotImplementedError(
        f"Migration from schema v{from_version} to v{to_version} is not yet implemented. "
        f"Please recreate your storage (current schema is v{CURRENT_SCHEMA_VERSION})."
    )
