from pathlib import Path

import pytest

from mushi.core.profiles import ProfileWorkflow
from mushi.storage.errors import RecordNotFoundError
from mushi.storage.filesystem import FilesystemStorage


def test_save_profile_persists_profile(tmp_path: Path) -> None:
    storage = FilesystemStorage(tmp_path)
    workflow = ProfileWorkflow(storage)

    profile = workflow.save_profile(
        name="default",
        backend="opencode",
        settings={"model": "provider/model"},
        description="Default profile",
    )

    assert storage.load_profile("default") == profile


def test_resolve_profile_returns_backend_and_settings_snapshot(tmp_path: Path) -> None:
    workflow = ProfileWorkflow(FilesystemStorage(tmp_path))
    workflow.save_profile(
        name="default",
        backend="opencode",
        settings={"model": "provider/model", "backend_specific": {"flag": True}},
    )

    resolved = workflow.resolve_profile("default")

    assert resolved.name == "default"
    assert resolved.backend == "opencode"
    assert resolved.settings == {"model": "provider/model", "backend_specific": {"flag": True}}


def test_resolved_profile_settings_are_not_mutable(tmp_path: Path) -> None:
    workflow = ProfileWorkflow(FilesystemStorage(tmp_path))
    workflow.save_profile(name="default", backend="opencode", settings={"model": "provider/model"})
    resolved = workflow.resolve_profile("default")

    with pytest.raises(TypeError):
        resolved.settings["model"] = "changed"  # type: ignore[index]


def test_resolve_missing_profile_raises(tmp_path: Path) -> None:
    workflow = ProfileWorkflow(FilesystemStorage(tmp_path))

    with pytest.raises(RecordNotFoundError):
        workflow.resolve_profile("missing")


def test_list_profiles_returns_storage_order(tmp_path: Path) -> None:
    workflow = ProfileWorkflow(FilesystemStorage(tmp_path))
    workflow.save_profile(name="zeta", backend="opencode")
    workflow.save_profile(name="alpha", backend="cursor")

    assert [profile.name for profile in workflow.list_profiles()] == ["alpha", "zeta"]
