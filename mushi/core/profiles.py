"""Profile workflow operations."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from mushi.core.schemas import ProfileDefinition
from mushi.storage.filesystem import FilesystemStorage


@dataclass(frozen=True)
class ResolvedProfile:
    """Profile settings snapshot used when recording a session."""

    name: str
    backend: str
    settings: Mapping[str, Any]


class ProfileWorkflow:
    """Storage-backed profile operations."""

    def __init__(self, storage: FilesystemStorage) -> None:
        self.storage = storage

    def save_profile(
        self,
        *,
        name: str,
        backend: str,
        settings: dict[str, Any] | None = None,
        description: str | None = None,
    ) -> ProfileDefinition:
        profile = ProfileDefinition(
            name=name,
            backend=backend,
            settings=settings or {},
            description=description,
        )
        self.storage.save_profile(profile)
        return profile

    def show_profile(self, name: str) -> ProfileDefinition:
        return self.storage.load_profile(name)

    def list_profiles(self) -> list[ProfileDefinition]:
        return self.storage.list_profiles()

    def resolve_profile(self, name: str) -> ResolvedProfile:
        profile = self.storage.load_profile(name)
        return ResolvedProfile(
            name=profile.name,
            backend=profile.backend,
            settings=MappingProxyType(dict(profile.settings)),
        )
