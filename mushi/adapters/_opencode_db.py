"""Detect OpenCode sessions by querying its SQLite database."""

from __future__ import annotations

import sqlite3
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def get_opencode_db_path() -> Path | None:
    """Return the path to the OpenCode SQLite database.

    Discovers the path by running ``opencode db path``.
    Returns ``None`` if the binary is unavailable or the DB does not exist.
    """
    try:
        result = subprocess.run(
            ["opencode", "db", "path"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None
        path = result.stdout.strip()
        if not path:
            return None
        p = Path(path)
        return p if p.exists() else None
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None


def get_max_created_at(db_path: Path, workspace_path: str) -> datetime | None:
    """Return the latest ``time_created`` for *workspace_path*, or ``None``."""
    try:
        with sqlite3.connect(str(db_path)) as conn:
            row = conn.execute(
                "SELECT MAX(time_created) FROM session WHERE directory = ?",
                (workspace_path,),
            ).fetchone()
        if row and row[0] is not None:
            return datetime.fromtimestamp(float(row[0]), tz=UTC)
        return None
    except (sqlite3.Error, OSError, ValueError):
        return None


def detect_new_sessions(
    db_path: Path,
    workspace_path: str,
    before: datetime | None,
) -> list[dict[str, Any]]:
    """Return sessions for *workspace_path* created *after* ``before``.

    If *before* is ``None`` all sessions for the workspace are returned.
    Results are ordered by ``time_created`` descending (newest first).
    """
    try:
        with sqlite3.connect(str(db_path)) as conn:
            if before is not None:
                rows = conn.execute(
                    """SELECT id, directory, title, time_created, time_updated
                       FROM session
                       WHERE directory = ? AND time_created > ?
                       ORDER BY time_created DESC""",
                    (workspace_path, before.timestamp()),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT id, directory, title, time_created, time_updated
                       FROM session
                       WHERE directory = ?
                       ORDER BY time_created DESC""",
                    (workspace_path,),
                ).fetchall()
        return [
            {
                "id": r[0],
                "directory": r[1],
                "title": r[2],
                "time_created": r[3],
                "time_updated": r[4],
            }
            for r in rows
        ]
    except (sqlite3.Error, OSError):
        return []
