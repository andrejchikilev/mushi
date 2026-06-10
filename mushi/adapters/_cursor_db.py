"""Detect Cursor agent sessions by scanning its local storage."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


CHATS_DIR = Path.home() / ".cursor" / "chats"
PROJECTS_DIR = Path.home() / ".cursor" / "projects"


def read_agent_meta(db_path: Path) -> dict[str, Any] | None:
    """Read agent session metadata from a Cursor ``store.db``.

    The ``meta`` table stores a hex-encoded JSON blob under key ``'0'``.
    """
    try:
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT value FROM meta WHERE key = '0'").fetchone()
        conn.close()
        if row is None:
            return None
        raw = bytes.fromhex(row[0]).decode("utf-8")
        return dict(json.loads(raw))
    except (sqlite3.Error, OSError, ValueError, json.JSONDecodeError):
        return None


def list_all_agent_store_paths() -> set[Path]:
    """Return a set of ``store.db`` paths for every existing agent session."""
    result: set[Path] = set()
    chats = CHATS_DIR
    if not chats.is_dir():
        return result
    for chat_hash_dir in chats.iterdir():
        if not chat_hash_dir.is_dir():
            continue
        for agent_dir in chat_hash_dir.iterdir():
            db = agent_dir / "store.db"
            if db.is_file():
                result.add(db)
    return result


def list_all_agent_store_paths_with_mtime() -> dict[Path, float]:
    """Return ``{store.db path: st_mtime}`` for every existing agent session.

    Used as the *before* snapshot so that modified sessions are also detected.
    """
    return {p: p.stat().st_mtime for p in list_all_agent_store_paths()}


def workspace_slug_for_chat_hash(chat_hash: str) -> str | None:
    """Map a chat directory hash to a project slug by checking ``agent-transcripts/``."""
    projects = PROJECTS_DIR
    if not projects.is_dir():
        return None
    chat_path = CHATS_DIR / chat_hash
    if not chat_path.is_dir():
        return None

    agent_ids = {d.name for d in chat_path.iterdir() if d.is_dir()}

    for slug_dir in projects.iterdir():
        if not slug_dir.is_dir():
            continue
        transcripts_dir = slug_dir / "agent-transcripts"
        if not transcripts_dir.is_dir():
            continue
        transcript_agents = set(transcripts_dir.iterdir())
        if agent_ids & transcript_agents:
            return slug_dir.name
    return None


def detect_new_agents(
    before: dict[Path, float] | None = None,
) -> list[dict[str, Any]]:
    """Find agent sessions created or modified since the *before* snapshot.

    *before* is ``{store.db path: st_mtime}`` from
    ``list_all_agent_store_paths_with_mtime()``. When ``None`` (first run),
    all existing sessions are returned.

    Returns a list of dicts sorted by ``createdAt`` descending (newest first).
    """
    after = list_all_agent_store_paths()
    if before is None:
        before = {}

    sessions = []
    for db_path in after:
        old_mtime = before.get(db_path)
        new_mtime = db_path.stat().st_mtime
        if old_mtime is not None and new_mtime <= old_mtime:
            continue

        meta = read_agent_meta(db_path)
        if meta is None:
            continue
        agent_id = meta.get("agentId", "")
        if not agent_id:
            continue
        chat_hash = db_path.parent.parent.name
        slug = workspace_slug_for_chat_hash(chat_hash) or chat_hash
        sessions.append({
            "agentId": agent_id,
            "name": meta.get("name", ""),
            "createdAt": meta.get("createdAt", 0),
            "workspaceSlug": slug,
        })

    sessions.sort(key=lambda s: s.get("createdAt", 0), reverse=True)
    return sessions
