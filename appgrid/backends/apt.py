from __future__ import annotations

import os

from appgrid.backends.base import AppEntry, PackageBackend
from appgrid.catalog.appstream import load_appstream
from appgrid.services.names import debian_package_name
from appgrid.services.jobs import run_capture
from appgrid.services.packagekit import (
    install_packages,
    refresh_and_upgrade_system,
    remove_packages,
    upgrade_packages,
)


def apt_bin() -> str | None:
    """Return a real apt-get binary, ignoring shell aliases on Arch/CachyOS."""
    for candidate in ("/usr/bin/apt-get", "/usr/bin/apt"):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def dpkg_query() -> str | None:
    path = "/usr/bin/dpkg-query"
    return path if os.path.isfile(path) else None


class AptBackend(PackageBackend):
    name = "apt"
    label = "APT"

    def available(self) -> bool:
        return apt_bin() is not None or self._python_apt() is not None

    def _python_apt(self):
        try:
            import apt

            return apt
        except Exception:
            return None

    def _installed_packages(self) -> dict[str, str]:
        query = dpkg_query()
        if not query:
            return {}
        result = run_capture([query, "-W", "-f=${Package}\\t${Version}\\n"])
        installed: dict[str, str] = {}
        for line in result.stdout.splitlines():
            if "\t" not in line:
                continue
            name, version = line.split("\t", 1)
            installed[name] = version
        return installed

    def _simulated_upgrades(self) -> set[str]:
        """Packages that would change in a full upgrade, using the current APT cache."""
        sim = "/usr/bin/apt-get"
        if not os.path.isfile(sim) or not os.access(sim, os.X_OK):
            sim = apt_bin() or ""
        if not sim:
            return set()
        result = run_capture(
            [sim, "-s", "-o", "Debug::NoLocking=true", "upgrade", "--with-new-pkgs"]
        )
        names: set[str] = set()
        for line in result.stdout.splitlines():
            if not line.startswith("Inst "):
                continue
            parts = line.split()
            if len(parts) >= 2:
                names.add(parts[1].split(":")[0])
        return names

    def _apt_state(self) -> tuple[dict[str, str], dict[str, str], set[str]]:
        # CLI only: python-apt is not safe on a background thread.
        return self._installed_packages(), {}, self._simulated_upgrades() | self._listed_upgrades()

    def _listed_upgrades(self) -> set[str]:
        binary = "/usr/bin/apt"
        if not os.path.isfile(binary) or not os.access(binary, os.X_OK):
            return set()
        result = run_capture([binary, "list", "--upgradable", "-qq"])
        names: set[str] = set()
        for line in result.stdout.splitlines():
            if "/" not in line:
                continue
            name = line.split("/", 1)[0].split(":", 1)[0].strip()
            if name:
                names.add(name)
        return names

    def refresh(self) -> list[AppEntry]:
        if not self.available():
            return []
        installed, candidates, upgradable = self._apt_state()
        entries = load_appstream(backend="apt")
        for entry in entries:
            pkg = entry.package
            entry.installed = pkg in installed
            entry.version = candidates.get(pkg) or installed.get(pkg, entry.version)
            entry.has_update = pkg in upgradable
            entry.origin = entry.origin or "Ubuntu/Debian"
        return entries

    def install(self, entry: AppEntry) -> None:
        if not apt_bin() and self._python_apt() is None:
            raise RuntimeError("APT is not available on this system")
        install_packages([debian_package_name(entry)])

    def remove(self, entry: AppEntry) -> None:
        if not apt_bin() and self._python_apt() is None:
            raise RuntimeError("APT is not available on this system")
        remove_packages([debian_package_name(entry)])

    def update_one(self, entry: AppEntry) -> None:
        if not apt_bin() and self._python_apt() is None:
            raise RuntimeError("APT is not available on this system")
        upgrade_packages([debian_package_name(entry)])

    def update_all(self) -> None:
        """Refresh indexes, then upgrade packages on this release (not 24.04→26.04)."""
        if not apt_bin() and self._python_apt() is None:
            raise RuntimeError("APT is not available on this system")
        refresh_and_upgrade_system()
