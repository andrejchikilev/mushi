"""Tests for Cursor agent session detection helpers."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from mushi.adapters._cursor_db import (
    detect_new_agents,
    list_all_agent_store_paths,
    list_all_agent_store_paths_with_mtime,
    read_agent_meta,
)


class TestReadAgentMeta:
    def test_returns_none_when_db_missing(self, tmp_path: Path) -> None:
        assert read_agent_meta(tmp_path / "nonexistent.db") is None

    def test_returns_parsed_meta_from_store_db(self, tmp_path: Path) -> None:
        db = tmp_path / "store.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE meta (key TEXT, value TEXT)")
        meta = {"agentId": "abc-123", "name": "Test Session", "mode": "default"}
        hex_val = json.dumps(meta).encode("utf-8").hex()
        conn.execute("INSERT INTO meta VALUES ('0', ?)", (hex_val,))
        conn.commit()
        conn.close()

        result = read_agent_meta(db)
        assert result is not None
        assert result["agentId"] == "abc-123"
        assert result["name"] == "Test Session"

    def test_returns_none_when_key_missing(self, tmp_path: Path) -> None:
        db = tmp_path / "store.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE meta (key TEXT, value TEXT)")
        conn.commit()
        conn.close()

        assert read_agent_meta(db) is None


class TestListAllAgentStorePaths:
    def test_returns_empty_when_chats_dir_missing(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr("mushi.adapters._cursor_db.CHATS_DIR", tmp_path / "nonexistent")
        assert list_all_agent_store_paths() == set()

    def test_finds_store_db_files(self, tmp_path: Path, monkeypatch) -> None:
        chats = tmp_path / "chats"
        agent_dir = chats / "hash123" / "agent-uuid"
        agent_dir.mkdir(parents=True)
        db = agent_dir / "store.db"
        db.write_text("")
        monkeypatch.setattr("mushi.adapters._cursor_db.CHATS_DIR", chats)

        result = list_all_agent_store_paths()
        assert result == {db}

    def test_skips_dirs_without_store_db(self, tmp_path: Path, monkeypatch) -> None:
        chats = tmp_path / "chats"
        (chats / "hash1" / "agent1").mkdir(parents=True)
        monkeypatch.setattr("mushi.adapters._cursor_db.CHATS_DIR", chats)

        result = list_all_agent_store_paths()
        assert result == set()

    def test_with_mtime_returns_path_and_mtime(self, tmp_path: Path, monkeypatch) -> None:
        chats = tmp_path / "chats"
        agent_dir = chats / "hash1" / "agent1"
        agent_dir.mkdir(parents=True)
        db = agent_dir / "store.db"
        db.write_text("")
        monkeypatch.setattr("mushi.adapters._cursor_db.CHATS_DIR", chats)

        result = list_all_agent_store_paths_with_mtime()
        assert db in result
        assert isinstance(result[db], float)


class TestDetectNewAgents:
    def test_no_before_returns_all(self, tmp_path: Path, monkeypatch) -> None:
        chats = tmp_path / "chats"
        agent_dir = chats / "hash1" / "agent1"
        agent_dir.mkdir(parents=True)
        db = agent_dir / "store.db"
        _make_store_db(db, "agent-1", "Session 1")
        monkeypatch.setattr("mushi.adapters._cursor_db.CHATS_DIR", chats)

        result = detect_new_agents(before=None)
        assert len(result) == 1
        assert result[0]["agentId"] == "agent-1"

    def test_unchanged_path_not_detected(self, tmp_path: Path, monkeypatch) -> None:
        chats = tmp_path / "chats"
        agent_dir = chats / "hash1" / "agent1"
        agent_dir.mkdir(parents=True)
        db = agent_dir / "store.db"
        _make_store_db(db, "agent-1", "Session 1")
        monkeypatch.setattr("mushi.adapters._cursor_db.CHATS_DIR", chats)

        before = list_all_agent_store_paths_with_mtime()
        result = detect_new_agents(before=before)
        assert result == []

    def test_new_path_detected(self, tmp_path: Path, monkeypatch) -> None:
        chats = tmp_path / "chats"
        (chats / "hash1" / "agent1").mkdir(parents=True)
        monkeypatch.setattr("mushi.adapters._cursor_db.CHATS_DIR", chats)

        before = list_all_agent_store_paths_with_mtime()

        db = chats / "hash1" / "agent2" / "store.db"
        _make_store_db(db, "agent-2", "New Session")
        result = detect_new_agents(before=before)
        assert len(result) == 1
        assert result[0]["agentId"] == "agent-2"

    def test_modified_mtime_detected(self, tmp_path: Path, monkeypatch) -> None:
        chats = tmp_path / "chats"
        agent_dir = chats / "hash1" / "agent1"
        agent_dir.mkdir(parents=True)
        db = agent_dir / "store.db"
        _make_store_db(db, "agent-1", "Old name")
        monkeypatch.setattr("mushi.adapters._cursor_db.CHATS_DIR", chats)

        before = list_all_agent_store_paths_with_mtime()

        time.sleep(0.01)
        _make_store_db(db, "agent-1", "New name")
        result = detect_new_agents(before=before)
        assert len(result) == 1
        assert result[0]["agentId"] == "agent-1"


def _make_store_db(db_path: Path, agent_id: str, name: str) -> None:
    import sqlite3
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT, value TEXT)")
    meta = json.dumps({"agentId": agent_id, "name": name, "createdAt": time.time() * 1000})
    conn.execute("INSERT OR REPLACE INTO meta VALUES ('0', ?)", (meta.encode("utf-8").hex(),))
    conn.commit()
    conn.close()
