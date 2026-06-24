"""Shared base logic for CLI-based backend adapters."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

from mushi.adapters.protocol import AdapterResult


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

        if self._interactive:
            return self._invoke_interactive(args, workspace_path)

        try:
            proc = self._run_cli(args, cwd=workspace_path)
        except FileNotFoundError:
            return AdapterResult(
                status="failed",
                result_summary=f"{self.binary_name} not found on PATH",
                error_details="binary not found",
            )
        except subprocess.TimeoutExpired:
            return AdapterResult(
                status="failed",
                result_summary=f"{self.binary_name} timed out",
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
    ) -> AdapterResult:
        try:
            proc = subprocess.run(
                [self.binary_name, *args],
                cwd=workspace_path,
                timeout=3600,
            )
        except FileNotFoundError:
            return AdapterResult(
                status="failed",
                result_summary=f"{self.binary_name} not found on PATH",
                error_details="binary not found",
            )
        except subprocess.TimeoutExpired:
            return AdapterResult(
                status="failed",
                result_summary=f"{self.binary_name} timed out (after 3600s)",
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
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.binary_name, *args],
            capture_output=True,
            text=True,
            cwd=cwd,
            env=env,
            timeout=3600,
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
