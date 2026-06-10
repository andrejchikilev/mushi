"""Tests for the OpenCode SQLite session detection helpers."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from mushi.adapters._opencode_db import detect_new_sessions, get_max_created_at


def _seed_db(
    db_path: Path,
    *,
    workspace: str = "/workspace",
    sessions: list[tuple[str, str, float]] | None = None,
) -> None:
    """Create the ``session`` table and insert optional rows.

    Each session tuple is ``(id, title, time_created_epoch)``.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS session ("
        "  id TEXT, directory TEXT, title TEXT, time_created REAL, time_updated REAL"
        ")"
    )
    if sessions:
        for sid, title, epoch in sessions:
            conn.execute(
                "INSERT INTO session VALUES (?, ?, ?, ?, ?)",
                (sid, workspace, title, epoch, epoch),
            )
    conn.commit()
    conn.close()


class TestGetMaxCreatedAt:
    def test_returns_none_when_table_empty(self, tmp_path: Path) -> None:
        db = tmp_path / "opencode.db"
        _seed_db(db, sessions=[])
        assert get_max_created_at(db, "/workspace") is None

    def test_returns_none_when_no_matching_workspace(self, tmp_path: Path) -> None:
        db = tmp_path / "opencode.db"
        _seed_db(db, workspace="/other", sessions=[("s1", "Other", 1000.0)])
        assert get_max_created_at(db, "/workspace") is None

    def test_returns_latest_timestamp(self, tmp_path: Path) -> None:
        db = tmp_path / "opencode.db"
        _seed_db(
            db,
            sessions=[
                ("s1", "Old", 1000.0),
                ("s2", "New", 2000.0),
                ("s3", "Mid", 1500.0),
            ],
        )
        result = get_max_created_at(db, "/workspace")
        assert result is not None
        assert result == datetime.fromtimestamp(2000.0, tz=UTC)

    def test_returns_none_when_db_missing(self, tmp_path: Path) -> None:
        db = tmp_path / "nonexistent.db"
        assert get_max_created_at(db, "/workspace") is None


class TestDetectNewSessions:
    def test_returns_empty_when_no_sessions(self, tmp_path: Path) -> None:
        db = tmp_path / "opencode.db"
        _seed_db(db, sessions=[])
        assert detect_new_sessions(db, "/workspace", before=None) == []

    def test_returns_all_when_before_is_none(self, tmp_path: Path) -> None:
        db = tmp_path / "opencode.db"
        _seed_db(
            db,
            sessions=[
                ("s1", "First", 1000.0),
                ("s2", "Second", 2000.0),
            ],
        )
        result = detect_new_sessions(db, "/workspace", before=None)
        assert len(result) == 2
        assert result[0]["id"] == "s2"  # newest first

    def test_filters_by_before_timestamp(self, tmp_path: Path) -> None:
        db = tmp_path / "opencode.db"
        _seed_db(
            db,
            sessions=[
                ("s1", "Old", 1000.0),
                ("s2", "New", 2000.0),
            ],
        )
        before = datetime.fromtimestamp(1500.0, tz=UTC)
        result = detect_new_sessions(db, "/workspace", before=before)
        assert len(result) == 1
        assert result[0]["id"] == "s2"

    def test_returns_empty_when_nothing_after_before(self, tmp_path: Path) -> None:
        db = tmp_path / "opencode.db"
        _seed_db(
            db,
            sessions=[("s1", "Only", 1000.0)],
        )
        before = datetime.fromtimestamp(2000.0, tz=UTC)
        result = detect_new_sessions(db, "/workspace", before=before)
        assert result == []

    def test_filters_by_workspace(self, tmp_path: Path) -> None:
        db = tmp_path / "opencode.db"
        conn = sqlite3.connect(str(db))
        conn.execute(
            "CREATE TABLE session ("
            "  id TEXT, directory TEXT, title TEXT, time_created REAL, time_updated REAL"
            ")"
        )
        conn.execute(
            "INSERT INTO session VALUES (?, ?, ?, ?, ?)",
            ("s1", "/workspace-a", "A", 1000.0, 1000.0),
        )
        conn.execute(
            "INSERT INTO session VALUES (?, ?, ?, ?, ?)",
            ("s2", "/workspace-b", "B", 2000.0, 2000.0),
        )
        conn.commit()
        conn.close()

        result = detect_new_sessions(db, "/workspace-a", before=None)
        assert len(result) == 1
        assert result[0]["id"] == "s1"

    def test_returns_empty_when_db_missing(self, tmp_path: Path) -> None:
        db = tmp_path / "nonexistent.db"
        assert detect_new_sessions(db, "/workspace", before=None) == []

    def test_result_includes_all_fields(self, tmp_path: Path) -> None:
        db = tmp_path / "opencode.db"
        _seed_db(
            db,
            sessions=[("s1", "My Session", 1234.0)],
        )
        result = detect_new_sessions(db, "/workspace", before=None)
        assert len(result) == 1
        entry = result[0]
        assert entry["id"] == "s1"
        assert entry["directory"] == "/workspace"
        assert entry["title"] == "My Session"
        assert entry["time_created"] == 1234.0
        assert entry["time_updated"] == 1234.0
