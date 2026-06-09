from pathlib import Path

import pytest

from mushi.storage.errors import RecordAlreadyExistsError, RecordNotFoundError
from mushi.storage.files import atomic_create_text, atomic_write_text, read_text_file


def test_atomic_write_creates_parent_directories(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "record.json"

    atomic_write_text(path, "{}\n")

    assert path.read_text(encoding="utf-8") == "{}\n"


def test_atomic_write_overwrites_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "record.json"

    atomic_write_text(path, "old\n")
    atomic_write_text(path, "new\n")

    assert path.read_text(encoding="utf-8") == "new\n"


def test_read_text_file_reads_utf8_content(tmp_path: Path) -> None:
    path = tmp_path / "record.json"
    atomic_write_text(path, "content\n")

    assert read_text_file(path) == "content\n"


def test_read_text_file_raises_for_missing_file(tmp_path: Path) -> None:
    with pytest.raises(RecordNotFoundError, match="Record not found"):
        read_text_file(tmp_path / "missing.json")


def test_atomic_write_does_not_leave_temp_files_on_success(tmp_path: Path) -> None:
    path = tmp_path / "record.json"

    atomic_write_text(path, "content\n")

    assert list(tmp_path.glob(".*.tmp")) == []


def test_atomic_create_creates_parent_directories(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "record.json"

    atomic_create_text(path, "{}\n")

    assert path.read_text(encoding="utf-8") == "{}\n"


def test_atomic_create_rejects_existing_file_without_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "record.json"
    atomic_create_text(path, "original\n")

    with pytest.raises(RecordAlreadyExistsError):
        atomic_create_text(path, "replacement\n")

    assert path.read_text(encoding="utf-8") == "original\n"


def test_atomic_create_does_not_leave_temp_files_on_duplicate(tmp_path: Path) -> None:
    path = tmp_path / "record.json"
    atomic_create_text(path, "original\n")

    with pytest.raises(RecordAlreadyExistsError):
        atomic_create_text(path, "replacement\n")

    assert list(tmp_path.glob(".*.tmp")) == []
