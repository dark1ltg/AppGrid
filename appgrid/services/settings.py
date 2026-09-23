from __future__ import annotations

from appgrid.qt import QSettings


class AppSettings:
    def __init__(self) -> None:
        self._store = QSettings("AppGrid", "AppGrid")

    @property
    def flatpak_enabled(self) -> bool:
        return bool(self._store.value("enableFlatpak", False, type=bool))

    @flatpak_enabled.setter
    def flatpak_enabled(self, value: bool) -> None:
        self._store.setValue("enableFlatpak", bool(value))
        self._store.sync()
