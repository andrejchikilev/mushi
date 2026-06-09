"""Low-level filesystem read/write helpers."""

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from mushi.storage.errors import RecordAlreadyExistsError, RecordNotFoundError, StorageError


def read_text_file(path: Path) -> str:
    """Read a UTF-8 text file or raise a storage-specific missing-record error."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise RecordNotFoundError(f"Record not found: {path}") from error
    except OSError as error:
        raise StorageError(f"Could not read record: {path}") from error


def atomic_write_text(path: Path, content: str) -> None:
    """Write UTF-8 text by replacing the target with a completed temp file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None

    try:
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(content)
            temp_file.flush()
        temp_path.replace(path)
    except OSError as error:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise StorageError(f"Could not write record: {path}") from error


def atomic_create_text(path: Path, content: str) -> None:
    """Create a UTF-8 text file atomically, failing if the target already exists."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None

    try:
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(content)
            temp_file.flush()
        os.link(temp_path, path)
    except FileExistsError as error:
        raise RecordAlreadyExistsError(f"Record already exists: {path}") from error
    except OSError as error:
        raise StorageError(f"Could not create record: {path}") from error
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
