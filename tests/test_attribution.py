"""Tests for spawn-window attribution helpers and the shared invoke driver."""

from __future__ import annotations

import threading
import time
from typing import Any

import pytest

from mushi.adapters import _attribution as attribution
from mushi.adapters._attribution import (
    Candidate,
    PollResult,
    select_candidate,
    start_spawn_poll,
)
from mushi.adapters._cli_base import SpawnLock, invoke_with_attribution
from mushi.adapters.protocol import AdapterResult


def _adapter_result(invocation: dict[str, Any] | None = None) -> AdapterResult:
    return AdapterResult(
        status="succeeded",
        backend_version="x 1.0",
        invocation=invocation or {"args": ["run"]},
        result_summary="done",
    )


class TestSelectCandidate:
    def test_single_candidate_attributed(self) -> None:
        cand = Candidate("own", 100.0, invocation_fields={"id": "own"})
        attribution = select_candidate([cand], 99.98)
        assert attribution.candidate is cand
        assert attribution.note == ""

    def test_no_candidates_no_note(self) -> None:
        result = select_candidate([], 0.0)
        assert result.candidate is None
        assert result.note == ""

    def test_two_close_candidates_ambiguous(self) -> None:
        near = Candidate("own", 100.01, invocation_fields={"id": "own"})
        foreign = Candidate("foreign", 100.02, invocation_fields={"id": "foreign"})
        attribution = select_candidate([near, foreign], 100.0)
        assert attribution.candidate is None
        assert "ambiguous" in attribution.note

    def test_two_far_candidates_pick_closest(self) -> None:
        own = Candidate("own", 100.01, invocation_fields={"id": "own"})
        foreign = Candidate("foreign", 130.0, invocation_fields={"id": "foreign"})
        attribution = select_candidate([foreign, own], 100.0)
        assert attribution.candidate is own
        assert attribution.note == ""

    def test_unknown_created_time_is_ambiguous_for_multiple(self) -> None:
        a = Candidate("a", None)
        b = Candidate("b", None)
        attribution_result = select_candidate([a, b], 1.0)
        assert attribution_result.candidate is None
        assert "ambiguous" in attribution_result.note


class TestStartSpawnPoll:
    def test_finds_and_attributes_own_row(self) -> None:
        seen_release = []
        own = Candidate("own", None, invocation_fields={"id": "own"})

        def poll_fn() -> list[Candidate]:
            return [own]

        result = start_spawn_poll(
            poll_fn, before_ids=set(), spawn_ts=attribution.now(),
            release=lambda: seen_release.append(1),
            poll_interval=0.01, poll_timeout=5.0, grace=0.05,
        )
        attribution_result = result.result()
        assert attribution_result.candidate is own
        assert seen_release == [1]

    def test_excludes_before_ids(self) -> None:
        old = Candidate("old", None)

        def poll_fn() -> list[Candidate]:
            return [old]

        result = start_spawn_poll(
            poll_fn, before_ids={"old", "old"}, spawn_ts=attribution.now(),
            poll_interval=0.01, poll_timeout=0.2, grace=0.01,
        )
        assert result.result().candidate is None

    def test_release_happens_exactly_once(self) -> None:
        released = []

        def poll_fn() -> list[Candidate]:
            return []

        result = start_spawn_poll(
            poll_fn, before_ids=set(), spawn_ts=attribution.now(),
            release=lambda: released.append(1),
            poll_interval=0.01, poll_timeout=0.1, grace=0.01,
        )
        result.result()
        assert released == [1]


class TestSpawnLock:
    def test_acquire_release_roundtrip(self, tmp_path: Any) -> None:
        lock = SpawnLock(tmp_path / "root" / "agent-spawn.lock")
        assert lock.acquire() is True
        assert lock.acquire() is True  # idempotent while held
        lock.release()
        assert lock._fd is None

    def test_second_thread_blocks_until_released(self, tmp_path: Any) -> None:
        lock = SpawnLock(tmp_path / "agent-spawn.lock")
        assert lock.acquire() is True

        second = SpawnLock(tmp_path / "agent-spawn.lock")
        acquired_from_thread = threading.Event()
        released_from_thread = threading.Event()

        def other() -> None:
            second.acquire()
            acquired_from_thread.set()
            second.release()
            released_from_thread.set()

        thread = threading.Thread(target=other, daemon=True)
        thread.start()
        # Give the waiting thread time to reach the blocked flock call.
        deadline = time.time() + 1.0
        while time.time() < deadline and not acquired_from_thread.is_set():
            time.sleep(0.01)
        assert not acquired_from_thread.is_set(), "second acquire should be blocked by the lock"
        lock.release()
        assert released_from_thread.wait(2.0)
        acquired_from_thread.wait(2.0)

    def test_acquire_fails_gracefully_when_unwritable(self, tmp_path: Any) -> None:
        blocker = tmp_path / "not-a-dir"
        blocker.write_text("")
        lock = SpawnLock(blocker / "agent-spawn.lock")
        assert lock.acquire() is False
        lock.release()  # no-op, must not raise


class TestInvokeWithAttribution:
    """Driver-level behavior with fake hooks and a fake base invoke."""

    @pytest.fixture(autouse=True)
    def _lock_root(self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MUSHI_STORAGE_ROOT", str(tmp_path / "storage"))

    def _fake_hooks(self, rows: "list[Candidate]", resume_keys: "tuple[str, ...]" = ()) -> Any:
        class FakeHooks:
            def __init__(self, resume_keys: "tuple[str, ...]" = ()) -> None:
                self.store: list[Candidate] = list(rows)
                self.resume_keys = tuple(resume_keys)

            def supports_attribution(self) -> bool:
                return True

            def snapshot_ids(self) -> set[str]:
                return set()

            def candidates(self) -> list[Candidate]:
                return list(self.store)

        return FakeHooks(resume_keys=resume_keys)

    def _invoke(self, hooks: Any, settings: dict[str, Any], base: Any) -> AdapterResult:
        return invoke_with_attribution(
            base,
            object(),
            goal="g",
            workspace_path="/ws",
            settings=settings,
            hooks=hooks,
        )

    def test_own_row_attributed_into_invocation(self) -> None:
        hooks = self._fake_hooks([])

        def base(self: Any, *, goal: str, workspace_path: str, settings: dict[str, Any]) -> AdapterResult:
            hooks.store.append(Candidate("own", attribution.now(), {"opencode_session_id": "own"}))
            time.sleep(0.05)
            return _adapter_result()

        result = self._invoke(hooks, {}, base)
        assert result.invocation["opencode_session_id"] == "own"

    def test_foreign_row_far_from_spawn_is_excluded(self) -> None:
        hooks = self._fake_hooks([])

        def base(self: Any, *, goal: str, workspace_path: str, settings: dict[str, Any]) -> AdapterResult:
            now_ts = attribution.now()
            hooks.store.append(Candidate("own", now_ts, {"opencode_session_id": "own"}))
            hooks.store.append(Candidate("foreign", now_ts + 30.0, {"opencode_session_id": "foreign"}))
            time.sleep(0.05)
            return _adapter_result()

        result = self._invoke(hooks, {}, base)
        assert result.invocation["opencode_session_id"] == "own"

    def test_two_indistinguishable_rows_fall_safe_with_note(self) -> None:
        hooks = self._fake_hooks([])

        def base(self: Any, *, goal: str, workspace_path: str, settings: dict[str, Any]) -> AdapterResult:
            now_ts = attribution.now()
            hooks.store.append(Candidate("a", now_ts, {"opencode_session_id": "a"}))
            hooks.store.append(Candidate("b", now_ts + 0.1, {"opencode_session_id": "b"}))
            time.sleep(0.05)
            return _adapter_result()

        result = self._invoke(hooks, {}, base)
        assert "opencode_session_id" not in result.invocation
        assert "ambiguous" in result.result_summary

    def test_resume_keys_survive_detection_and_are_never_overridden(self) -> None:
        hooks = self._fake_hooks([], resume_keys=("opencode_session_id",))

        def base(self: Any, *, goal: str, workspace_path: str, settings: dict[str, Any]) -> AdapterResult:
            now_ts = attribution.now()
            hooks.store.append(Candidate("foreign", now_ts, {"opencode_session_id": "foreign"}))
            return _adapter_result({"args": ["--session", "ses_known"]})

        result = self._invoke(hooks, {"opencode_session_id": "ses_known"}, base)
        assert result.invocation["opencode_session_id"] == "ses_known"

    def test_no_resume_and_unsupported_store_skips_detection(self) -> None:
        class NoneHooks:
            resume_keys = ()

            def supports_attribution(self) -> bool:
                return False

            def snapshot_ids(self) -> set[str]:
                return set()

            def candidates(self) -> list[Candidate]:
                return []

        calls = []

        def base(self: Any, *, goal: str, workspace_path: str, settings: dict[str, Any]) -> AdapterResult:
            calls.append(True)
            return _adapter_result()

        result = invoke_with_attribution(
            base, object(), goal="g", workspace_path="/ws", settings={}, hooks=NoneHooks(),
        )
        assert calls == [True]
        assert "opencode_session_id" not in result.invocation

    def test_resume_is_skipped_from_poll_window(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
        """Resume-known keys never start poll machinery at all."""
        hooks = self._fake_hooks([], resume_keys=("cursor_agent_id",))

        poll_calls: list[int] = []
        monkeypatch.setattr(
            "mushi.adapters._cli_base.start_spawn_poll",
            lambda *a, **kw: poll_calls.append(1) or (_ for _ in ()).throw(AssertionError("should not poll")),
        )

        def base(self: Any, *, goal: str, workspace_path: str, settings: dict[str, Any]) -> AdapterResult:
            return _adapter_result({"args": ["agent", "--resume", "agent-1"]})

        result = self._invoke(hooks, {"cursor_agent_id": "agent-1"}, base)
        assert poll_calls == []
        assert result.invocation["cursor_agent_id"] == "agent-1"

    def test_poll_death_falls_back_to_post_exit_diff(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any,
    ) -> None:
        """When polling is inconclusive, the post-exit store diff attributes the row."""
        monkeypatch.setattr(attribution, "SPAWN_POLL_TIMEOUT", 0.05)
        hooks = self._fake_hooks([])

        def base(self: Any, *, goal: str, workspace_path: str, settings: dict[str, Any]) -> AdapterResult:
            # The backend only commits its row near process exit, long
            # after the (patched-short) poll window has already expired.
            time.sleep(0.3)
            hooks.store.append(Candidate("own", attribution.now(), {"opencode_session_id": "own"}))
            return _adapter_result()

        result = self._invoke(hooks, {}, base)
        assert result.invocation["opencode_session_id"] == "own"


def test_poll_result_bounded_join_keeps_running_thread_alive(tmp_path_factory: Any) -> None:
    """`result()` returns promptly even when the poll thread keeps polling."""
    started = threading.Event()

    def poll_fn() -> list[Candidate]:
        started.set()
        return []

    spawn_ts = attribution.now()
    result = start_spawn_poll(
        poll_fn, before_ids=set(), spawn_ts=spawn_ts,
        poll_interval=0.01, poll_timeout=5.0, grace=0.01,
    )
    assert started.wait(1.0)
    attribution_result = result.result(join_timeout=0.05)
    assert attribution_result.candidate is None
