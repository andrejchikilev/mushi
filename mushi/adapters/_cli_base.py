"""Shared base logic for CLI-based backend adapters."""

from __future__ import annotations

import fcntl
import os
import shutil
import subprocess
from pathlib import Path
from dataclasses import replace
from typing import Any, Callable, Protocol

from mushi.adapters._attribution import (
    Attribution,
    Candidate,
    PollResult,
    select_candidate,
    start_spawn_poll,
    now,
)
from mushi.adapters.protocol import AdapterResult
from mushi.core.schemas import SessionRecord


def storage_root() -> Path:
    """Mirror the CLI storage-root resolution for spawn lock placement."""
    env_root = os.environ.get("MUSHI_STORAGE_ROOT")
    if env_root:
        return Path(env_root)
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data) / "mushi"
    return Path.home() / ".local" / "share" / "mushi"


def spawn_lock_path() -> Path:
    """Global advisory lock serializing agent spawn windows."""
    return storage_root() / "agent-spawn.lock"


class SpawnLock:
    """Advisory ``flock`` lock for agent spawn windows; failures are non-fatal.

    The lock is held only across snapshot + spawn-poll resolution, never for
    the whole interactive session. Subprocesses do not inherit the descriptor
    (close-on-exec), so the lock is always owned by the mushi process.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else spawn_lock_path()
        self._fd: int | None = None

    def acquire(self) -> bool:
        """Acquire an exclusive flock. Returns False on failure (non-fatal)."""
        if self._fd is not None:
            return True
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(str(self.path), os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX)
        except OSError:
            return False
        self._fd = fd
        return True

    def release(self) -> None:
        """Unlock and close if acquired; safe to call from any thread."""
        fd = self._fd
        if fd is None:
            return
        self._fd = None
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            try:
                os.close(fd)
            except OSError:
                pass


class AttributionHooks(Protocol):
    """Backend-specific store access for spawn-window attribution."""

    resume_keys: "tuple[str, ...]"

    def supports_attribution(self) -> bool:
        """True when the backend store could be supervised at all."""
        ...

    def snapshot_ids(self) -> set[str]:
        """IDs of all existing backend sessions before spawning."""
        ...

    def candidates(self) -> list[Candidate]:
        """All backend session rows observable right now."""
        ...


def invoke_with_attribution(
    base_invoke: Callable[..., AdapterResult],
    adapter_self: Any,
    goal: str,
    workspace_path: str,
    settings: dict[str, Any],
    *,
    hooks: AttributionHooks,
) -> AdapterResult:
    """Attribution-aware invoke shared by CLI adapters.

    Runs the blocking base ``invoke`` while a poll thread watches the
    backend store from inside the spawn-lock window; merges the validated
    backend session id - or the resume keys the caller already knew -
    into ``result.invocation``. Detection never overrides a known resume
    id, and the persisted invocation is not wiped when detection is empty.
    """
    resume = {key: settings[key] for key in hooks.resume_keys if settings.get(key)}

    if not hooks.supports_attribution() or resume:
        result = base_invoke(adapter_self, goal=goal, workspace_path=workspace_path, settings=settings)
        invocation = {**result.invocation, **resume}
        return replace(result, invocation=invocation)

    lock = SpawnLock()
    acquired = lock.acquire()
    poller: PollResult | None = None
    try:
        before_ids = hooks.snapshot_ids()
        spawn_ts = now()
        if acquired:
            poller = start_spawn_poll(hooks.candidates, before_ids, spawn_ts, release=lock.release)
        result = base_invoke(adapter_self, goal=goal, workspace_path=workspace_path, settings=settings)
        attribution = (
            poller.result()
            if poller is not None
            else select_candidate([c for c in hooks.candidates() if c.key not in before_ids], spawn_ts)
        )
    except BaseException:
        if poller is None:
            lock.release()
        else:
            poller.abandon()
        raise

    if attribution.candidate is None and not attribution.note:
        # Poll never saw anything (e.g. backend creates its row lazily):
        # fall back to a post-exit set diff with the same fail-safe policy.
        candidates = [c for c in hooks.candidates() if c.key not in before_ids]
        attribution = select_candidate(candidates, spawn_ts)
    return _finalize_attribution(result, resume, attribution)


def _finalize_attribution(
    result: AdapterResult,
    resume: dict[str, Any],
    attribution: Attribution,
) -> AdapterResult:
    invocation = {**result.invocation, **resume}
    candidate = attribution.candidate
    if candidate is not None:
        attribution_fields = {
            key: value for key, value in candidate.invocation_fields.items() if value is not None
        }
        for key in resume:
            attribution_fields.pop(key, None)
        invocation.update(attribution_fields)
    summary = result.result_summary
    if attribution.candidate is None and attribution.note:
        summary = f"{summary} ({attribution.note})" if summary else attribution.note
    return replace(result, invocation=invocation, result_summary=summary)


class CliAdapterBase:
    """Common logic for adapters that invoke a CLI binary.

    Subclasses must set ``binary_name`` and may override ``_build_invoke_args``
    and ``_build_version_args``.

    If *interactive* is True, ``invoke`` passes the terminal through to the
    child process instead of capturing stdout/stderr.
    """

    binary_name: str = ""

    def __init__(self, *, interactive: bool = False) -> None:
        self._version: str | None = None
        self._interactive = interactive

    def check_available(self) -> bool:
        if not self._binary_on_path():
            return False
        try:
            result = self._run_cli(self._build_version_args())
            if result.returncode == 0:
                self._version = result.stdout.strip() or result.stderr.strip() or None
                return True
            return False
        except (FileNotFoundError, OSError):
            self._version = None
            return False

    def invoke(
        self,
        goal: str,
        workspace_path: str,
        settings: dict[str, Any],
    ) -> AdapterResult:
        if self._version is None:
            self._version = self._detect_version()

        args = self._build_invoke_args(goal, settings)
        timeout = _get_timeout(settings)

        if self._interactive:
            return self._invoke_interactive(args, workspace_path, timeout)

        try:
            proc = self._run_cli(args, cwd=workspace_path, timeout=timeout)
        except FileNotFoundError:
            return AdapterResult(
                status="failed",
                result_summary=f"{self.binary_name} not found on PATH",
                error_details="binary not found",
            )
        except subprocess.TimeoutExpired:
            timeout_str = f" (after {timeout}s)" if timeout else ""
            return AdapterResult(
                status="failed",
                result_summary=f"{self.binary_name} timed out{timeout_str}",
                error_details="timeout",
            )
        except OSError as exc:
            return AdapterResult(
                status="failed",
                result_summary=f"{self.binary_name} invocation failed",
                error_details=str(exc),
            )

        status = _status_from_returncode(proc.returncode)
        summary = (proc.stdout.strip() or proc.stderr.strip() or f"Exit code {proc.returncode}")[:200]

        return AdapterResult(
            status=status,
            backend_version=self._version,
            result_summary=summary,
            invocation={
                "args": args,
                "returncode": proc.returncode,
                "cwd": workspace_path,
            },
        )

    def _invoke_interactive(
        self,
        args: list[str],
        workspace_path: str,
        timeout: float | None,
    ) -> AdapterResult:
        try:
            proc = subprocess.run(
                [self.binary_name, *args],
                cwd=workspace_path,
                timeout=timeout,
            )
        except FileNotFoundError:
            return AdapterResult(
                status="failed",
                result_summary=f"{self.binary_name} not found on PATH",
                error_details="binary not found",
            )
        except subprocess.TimeoutExpired:
            timeout_str = f" (after {timeout}s)" if timeout else ""
            return AdapterResult(
                status="failed",
                result_summary=f"{self.binary_name} timed out{timeout_str}",
                error_details="timeout",
            )
        except OSError as exc:
            return AdapterResult(
                status="failed",
                result_summary=f"{self.binary_name} invocation failed",
                error_details=str(exc),
            )

        summary = f"Exit code {proc.returncode}"
        if self._version is None:
            self._version = self._detect_version()

        return AdapterResult(
            status=_status_from_returncode(proc.returncode),
            backend_version=self._version,
            result_summary=summary,
            invocation={
                "args": args,
                "returncode": proc.returncode,
                "cwd": workspace_path,
            },
        )

    def _binary_on_path(self) -> bool:
        return shutil.which(self.binary_name) is not None

    def _run_cli(
        self,
        args: list[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.binary_name, *args],
            capture_output=True,
            text=True,
            cwd=cwd,
            env=env,
            timeout=timeout,
        )

    def _build_version_args(self) -> list[str]:
        return ["--version"]

    def _build_invoke_args(self, goal: str, settings: dict[str, Any]) -> list[str]:
        return [goal]

    def _detect_version(self) -> str | None:
        try:
            result = self._run_cli(self._build_version_args())
            if result.returncode == 0:
                return result.stdout.strip() or result.stderr.strip() or None
        except (FileNotFoundError, OSError):
            pass
        return None

    def session_disk_usage(self, session: SessionRecord) -> int | None:
        return None

    def purge_session(self, session: SessionRecord) -> None:
        return None

    def persistent_store_path(self) -> str | None:
        return None


def with_context(goal: str, settings: dict[str, Any]) -> str:
    """Append context from *settings* to the goal if present."""
    context = settings.get("context")
    if not context:
        return goal
    return f"{goal}\n\nPrevious context:\n{context}"


def _status_from_returncode(returncode: int) -> str:
    if returncode < 0:
        return "cancelled"
    if returncode == 0:
        return "succeeded"
    return "failed"


def _get_timeout(settings: dict[str, Any]) -> float | None:
    raw = settings.get("timeout", 0)
    if raw is None or raw == 0:
        return None
    return float(raw)
