from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class AppEntry:
    uid: str
    backend: str
    app_id: str
    name: str
    summary: str = ""
    description: str = ""
    package: str = ""
    version: str = ""
    icon: str = ""
    screenshot: str = ""
    thumb: str = ""
    installed: bool = False
    has_update: bool = False
    self_installed: bool = False
    self_has_update: bool = False
    categories: list[str] = field(default_factory=list)
    origin: str = ""
    accent: str = "#3D8B8B"
    launch_id: str = ""
    scopes: list[str] = field(default_factory=list)
    release_ts: int = 0
    alt_backend: str = ""
    alt_package: str = ""
    alt_app_id: str = ""
    alt_scopes: list[str] = field(default_factory=list)
    desktop_ids: list[str] = field(default_factory=list)
    extras: list["AppEntry"] = field(default_factory=list)
    rating: float = 0.0
    developer: str = ""


class PackageBackend(ABC):
    """Install-source plugin. APT and Flatpak each implement this."""

    name: str
    label: str

    @abstractmethod
    def available(self) -> bool:
        """Return True when this backend can run on the current system."""

    @abstractmethod
    def refresh(self) -> list[AppEntry]:
        """Return catalog entries (desktop apps only)."""

    @abstractmethod
    def install(self, entry: AppEntry) -> None:
        """Install the application. May prompt via PolicyKit."""

    @abstractmethod
    def remove(self, entry: AppEntry) -> None:
        """Remove the application."""

    @abstractmethod
    def update_one(self, entry: AppEntry) -> None:
        """Apply available updates for one application."""

    @abstractmethod
    def update_all(self) -> None:
        """Apply all pending updates for this backend."""
