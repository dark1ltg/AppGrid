from __future__ import annotations

import copy

from appgrid.backends.apt import AptBackend
from appgrid.backends.base import AppEntry, PackageBackend
from appgrid.backends.demo import DemoBackend
from appgrid.backends.flatpak import FlatpakBackend
from appgrid.backends.flathub import display_origin, ensure_flathub_remote, refresh_appstream
from appgrid.catalog.appstream import prefetch_appstream, reset_pool
from appgrid.catalog.prefer import merge_by_id, merge_by_newer
from appgrid.catalog.ratings import apply_ratings
from appgrid.catalog.snapshot import save_snapshot
from appgrid.services.distro import is_debian_family
from appgrid.services.jobs import check as jobs_check


class BackendRegistry:
    def __init__(self, demo: bool = False) -> None:
        self.demo = demo
        self.plugins: dict[str, PackageBackend] = {}
        apt = AptBackend()
        flatpak = FlatpakBackend()
        if demo:
            self.plugins["apt"] = DemoBackend(only_backend="apt")
            self.plugins["flatpak"] = DemoBackend(only_backend="flatpak")
            return
        if not is_debian_family():
            return
        if apt.available():
            self.plugins["apt"] = apt
        if flatpak.available():
            self.plugins["flatpak"] = flatpak

    def backend_names(self, flatpak_enabled: bool) -> list[str]:
        names = ["apt"]
        if flatpak_enabled and "flatpak" in self.plugins:
            names.append("flatpak")
        return names

    def overlay_install_state(
        self, apps: list[AppEntry], flatpak_enabled: bool = False
    ) -> list[AppEntry]:
        """Refresh installed/update flags without re-reading AppStream."""
        jobs_check()
        apps = copy.deepcopy(apps)
        apt_installed, candidates, upgradable = self._apt_state()
        fp_installed, fp_updates = ({}, set())
        if flatpak_enabled:
            fp_installed, fp_updates = self._flatpak_state()
        for entry in apps:
            self._stamp_entry(entry, apt_installed, candidates, upgradable, fp_installed, fp_updates)
            for extra in entry.extras:
                self._stamp_entry(
                    extra, apt_installed, candidates, upgradable, fp_installed, fp_updates
                )
            copies = [entry, *entry.extras]
            entry.installed = any(copy.self_installed for copy in copies)
            entry.has_update = any(copy.self_installed and copy.self_has_update for copy in copies)
        return apps

    def catalog(
        self,
        flatpak_enabled: bool = False,
        merge_duplicates: bool = True,
        refresh_metadata: bool = False,
    ) -> list[AppEntry]:
        jobs_check()
        names = self.backend_names(flatpak_enabled)
        if refresh_metadata:
            reset_pool()
        if flatpak_enabled and "flatpak" in self.plugins and not self.demo:
            ensure_flathub_remote()
            refresh_appstream(force=refresh_metadata)
        if not self.demo:
            prefetch_appstream(tuple(names))
        apps: list[AppEntry] = []
        seen: set[str] = set()
        for name in names:
            jobs_check()
            plugin = self.plugins.get(name)
            if plugin is None:
                continue
            for entry in plugin.refresh():
                if entry.uid in seen:
                    continue
                seen.add(entry.uid)
                entry.self_installed = bool(entry.installed)
                entry.self_has_update = bool(entry.has_update)
                entry.thumb = entry.screenshot or entry.icon
                apps.append(entry)
        if flatpak_enabled and merge_duplicates:
            try:
                apps = merge_by_newer(apps)
            except Exception:
                apps = merge_by_id(apps)
        apps.sort(key=lambda item: item.name.lower())
        apply_ratings(apps)
        if not self.demo:
            save_snapshot(apps, flatpak_enabled)
        return apps

    def get(self, name: str) -> PackageBackend:
        if name not in self.plugins:
            raise KeyError(f"Unknown backend {name}")
        return self.plugins[name]

    def _apt_state(self) -> tuple[dict[str, str], dict[str, str], set[str]]:
        plugin = self.plugins.get("apt")
        if not isinstance(plugin, AptBackend):
            return {}, {}, set()
        return plugin._apt_state()

    def _flatpak_state(self) -> tuple[dict[str, dict], set[str]]:
        plugin = self.plugins.get("flatpak")
        if not isinstance(plugin, FlatpakBackend):
            return {}, set()
        return plugin._installed(), plugin._update_ids()

    def _stamp_entry(
        self,
        entry: AppEntry,
        apt_installed: dict[str, str],
        candidates: dict[str, str],
        upgradable: set[str],
        fp_installed: dict[str, dict],
        fp_updates: set[str],
    ) -> None:
        if entry.backend == "apt":
            pkg = entry.package
            entry.installed = pkg in apt_installed
            entry.version = candidates.get(pkg) or apt_installed.get(pkg, entry.version)
            entry.has_update = pkg in upgradable
        elif entry.backend == "flatpak":
            record = fp_installed.get(entry.app_id) or fp_installed.get(f"{entry.app_id}.desktop")
            entry.installed = bool(record)
            if record:
                entry.scopes = list(record.get("scopes") or [])
                if record.get("version") and not entry.version:
                    entry.version = record["version"]
            entry.has_update = (
                entry.app_id in fp_updates
                or f"{entry.app_id}.desktop" in fp_updates
                or entry.app_id.removesuffix(".desktop") in fp_updates
            )
            entry.origin = display_origin(entry.origin)
        entry.self_installed = bool(entry.installed)
        entry.self_has_update = bool(entry.has_update)
        entry.thumb = entry.screenshot or entry.icon or entry.thumb
