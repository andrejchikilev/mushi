"""Shared spawn-window attribution primitives for backend adapters.

Both CLI adapters infer the backend session id by diffing backend-local
stores around an invoke; the naive "take the newest new entry" approach
attributes another agent's session when several mushi agents run
concurrently. This module provides deterministic, race-safe attribution:

1. Under a global spawn lock: snapshot the set of existing backend
   session IDs, record the spawn instant, spawn the backend process.
2. A poll thread watches the backend store during the (possibly long)
   interactive invoke. The first new IDs to appear are compared by
   creation-time proximity to the spawn instant. Once resolution is due
   (candidates seen + a short grace, or timeout) it releases the lock,
   so the next mushi agent's snapshot window starts after this run's
   row already exists.
3. Post-exit fallback: if polling was inconclusive, diff the store once
   on exit against the snapshot and apply the same selection policy.

Selection policy fails safe: a single candidate is attributed; among
several, the candidate with the creation time closest to the spawn
instant wins; if two candidates are indistinguishable by proximity, no
candidate is attributed and a note is returned instead.
"""

from __future__ import annotations

import threading
import time as _time
from dataclasses import dataclass, field
from typing import Any, Callable

AMBIGUITY_MARGIN_SECONDS = 0.5
SPAWN_POLL_INTERVAL = 0.1
SPAWN_POLL_TIMEOUT = 10.0
SPAWN_GRACE_INTERVAL = 0.5


def now() -> float:
    """Wall clock wrapper (patchable in tests)."""
    return _time.time()


def sleep(seconds: float) -> None:
    """Sleep wrapper (patchable in tests)."""
    _time.sleep(seconds)


@dataclass(frozen=True)
class Candidate:
    """One backend-side session row seen by the store poller."""

    key: str
    created: float | None
    invocation_fields: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Attribution:
    candidate: Candidate | None
    note: str = ""


def select_candidate(
    candidates: list[Candidate],
    spawn_ts: float | None,
    *,
    margin: float = AMBIGUITY_MARGIN_SECONDS,
) -> Attribution:
    """Return the invocation-attributable candidate, or an ambiguous note."""
    if not candidates:
        return Attribution(None)

    if len(candidates) == 1:
        return Attribution(candidates[0])

    if spawn_ts is None or any(c.created is None for c in candidates):
        return Attribution(None, "ambiguous backend session attribution - no id recorded")

    ranked = sorted(candidates, key=lambda c: abs(c.created - spawn_ts))  # type: ignore[arg-type]
    closest = ranked[0]
    second_closest = ranked[1]
    if abs(second_closest.created - spawn_ts) - abs(closest.created - spawn_ts) < margin:
        return Attribution(None, "ambiguous backend session attribution - no id recorded")
    return Attribution(closest)


class PollResult:
    """Joinable handle for the spawn-window poll thread."""

    def __init__(
        self,
        thread: threading.Thread,
        release: Callable[[], None] | None,
        timeout: float,
        holder: dict[str, Attribution],
    ) -> None:
        self._thread = thread
        self._release = release
        self._timeout = timeout
        self._holder = holder

    def abandon(self) -> None:
        """Release the spawn lock and stop waiting for the poll thread."""
        self._release_once()

    def result(self, join_timeout: float = 2.0) -> Attribution:
        """Join the poll thread (bounded) and return its attribution result.

        The join is bounded so that an interactive session that exits
        early is not delayed until the full poll timeout. If the thread
        has not resolved yet, an empty attribution is returned and the
        caller may run its post-exit fallback.
        """
        if self._thread is not None:
            self._thread.join(timeout=join_timeout)
        self._release_once()
        return self._holder.get("result", Attribution(None))

    def _release_once(self) -> None:
        if self._release is not None:
            release, self._release = self._release, None
            try:
                release()
            except OSError:
                pass


def start_spawn_poll(
    poll_fn: Callable[[], list[Candidate]],
    before_ids: set[str],
    spawn_ts: float,
    *,
    release: Callable[[], None] | None = None,
    poll_interval: float | None = None,
    poll_timeout: float | None = None,
    grace: float | None = None,
) -> PollResult:
    """Poll the backend store for new candidate rows on a daemon thread.

    Collects rows whose key is not in *before_ids*. Once at least one
    was seen and *grace* elapsed since the first sighting, or the
    timeout expired, selection runs and *release* is invoked exactly
    once (typically releasing the spawn lock).
    """
    interval = SPAWN_POLL_INTERVAL if poll_interval is None else poll_interval
    timeout = SPAWN_POLL_TIMEOUT if poll_timeout is None else poll_timeout
    grace_period = SPAWN_GRACE_INTERVAL if grace is None else grace
    holder: dict[str, Attribution] = {}
    seen: dict[str, Candidate] = {}

    def loop() -> None:
        deadline = spawn_ts + timeout
        first_seen: float | None = None
        while now() < deadline:
            try:
                rows = poll_fn()
            except Exception:  # noqa: BLE001 - polling must never kill the thread
                rows = []
            for cand in rows:
                if cand.key not in before_ids:
                    seen.setdefault(cand.key, cand)
            if seen and first_seen is None:
                first_seen = now()
            if seen and first_seen is not None and now() - first_seen >= grace_period:
                break
            sleep(interval)
        holder["result"] = select_candidate(list(seen.values()), spawn_ts)

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    return PollResult(thread, release, timeout, holder)
