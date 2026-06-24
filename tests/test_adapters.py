"""Tests for adapter protocol, capability model, and stub adapter."""

import pytest

from mushi.adapters.protocol import AdapterResult, BackendCapability
from mushi.adapters.stub import StubAdapter
from mushi.adapters._cli_base import _get_timeout


def test_stub_adapter_satisfies_protocol() -> None:
    adapter = StubAdapter()

    assert isinstance(adapter, StubAdapter)


def test_stub_adapter_reports_default_name_and_capabilities() -> None:
    adapter = StubAdapter()

    assert adapter.name == "stub"
    assert adapter.capabilities == frozenset()


def test_stub_adapter_check_available_defaults_to_true() -> None:
    assert StubAdapter().check_available() is True


def test_stub_adapter_check_available_can_be_false() -> None:
    assert StubAdapter(available=False).check_available() is False


def test_stub_adapter_invoke_returns_default_success_result() -> None:
    result = StubAdapter().invoke(goal="test", workspace_path="/tmp", settings={})

    assert result.status == "succeeded"
    assert result.result_summary == "Stub invocation succeeded"
    assert result.backend_version == "0.0.0"
    assert result.transcript_refs == []
    assert result.error_details is None


def test_stub_adapter_invoke_passes_goal_and_settings_into_invocation() -> None:
    result = StubAdapter().invoke(
        goal="fix bug",
        workspace_path="/repo",
        settings={"model": "test"},
    )

    assert result.invocation == {
        "goal": "fix bug",
        "workspace_path": "/repo",
        "settings": {"model": "test"},
    }


def test_stub_adapter_invoke_can_return_failure() -> None:
    adapter = StubAdapter(
        available=True,
        result_status="failed",
        result_summary="Something went wrong",
        backend_version=None,
    )

    result = adapter.invoke(goal="test", workspace_path="/tmp", settings={})

    assert result.status == "failed"
    assert result.result_summary == "Something went wrong"
    assert result.backend_version is None


def test_stub_adapter_with_capabilities() -> None:
    caps = frozenset({BackendCapability.RESUME, BackendCapability.TRANSCRIPT_EXPORT})
    adapter = StubAdapter(capabilities=caps)

    assert adapter.capabilities == caps


def test_stub_adapter_invoke_returns_transcript_refs() -> None:
    adapter = StubAdapter(transcript_refs=["/tmp/transcript-1.log"])

    result = adapter.invoke(goal="test", workspace_path="/tmp", settings={})

    assert result.transcript_refs == ["/tmp/transcript-1.log"]


def test_adapter_result_accepts_error_details() -> None:
    result = StubAdapter(result_status="failed", error_details="stack trace").invoke(
        goal="test", workspace_path="/tmp", settings={}
    )

    assert result.status == "failed"
    assert result.error_details == "stack trace"


def test_get_timeout_zero_returns_none() -> None:
    assert _get_timeout({"timeout": 0}) is None


def test_get_timeout_absent_returns_none() -> None:
    assert _get_timeout({}) is None


def test_get_timeout_positive_returns_float() -> None:
    assert _get_timeout({"timeout": 3600}) == 3600.0
