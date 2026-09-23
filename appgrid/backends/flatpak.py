from __future__ import annotations

import shutil

from appgrid.backends.base import AppEntry, PackageBackend
from appgrid.backends.flathub import display_origin, install_remote_and_scope, scope_has_remote
from appgrid.catalog.appstream import load_appstream
from appgrid.services.jobs import CancelledError, run_capture, run_streaming


class FlatpakBackend(PackageBackend):
    name = "flatpak"
    label = "Flatpak"

    def available(self) -> bool:
        return shutil.which("flatpak") is not None

    def _installed(self) -> dict[str, dict]:
        return self._installed_from_cli()

    def _installed_from_cli(self) -> dict[str, dict]:
        binary = shutil.which("flatpak")
        if not binary:
            return {}
        merged: dict[str, dict] = {}
        for scope in ("system", "user"):
            result = run_capture(
                [binary, "list", "--app", f"--{scope}", "--columns=application,version"],
            )
            for line in result.stdout.splitlines():
                parts = line.split("\t")
                if not parts or parts[0] in {"Application", ""}:
                    continue
                app_id = parts[0].strip()
                version = parts[1].strip() if len(parts) > 1 else ""
                record = merged.setdefault(app_id, {"version": "", "scopes": []})
                if version:
                    record["version"] = version
                if scope not in record["scopes"]:
                    record["scopes"].append(scope)
        return merged

    def _update_ids(self) -> set[str]:
        binary = shutil.which("flatpak")
        if not binary:
            return set()
        result = run_capture(
            [binary, "list", "--app", "--updates", "--columns=application"],
        )
        return {
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip() and line.strip() not in {"Application", "APPLICATION"}
        }

    def refresh(self) -> list[AppEntry]:
        if not self.available():
            return []
        installed = self._installed()
        updates = self._update_ids()
        entries = load_appstream(backend="flatpak")
        seen = {entry.app_id for entry in entries}
        for entry in entries:
            record = installed.get(entry.app_id) or installed.get(f"{entry.app_id}.desktop")
            if record:
                entry.installed = True
                entry.scopes = list(record["scopes"])
                if record["version"] and not entry.version:
                    entry.version = record["version"]
            entry.has_update = entry.app_id in updates
            entry.origin = display_origin(entry.origin)
        for app_id, record in installed.items():
            if app_id in seen or app_id.removesuffix(".desktop") in seen:
                continue
            entries.append(
                AppEntry(
                    uid=f"flatpak:{app_id}",
                    backend="flatpak",
                    app_id=app_id,
                    name=app_id.split(".")[-1],
                    summary="Installed Flatpak application",
                    package=app_id,
                    version=record["version"],
                    installed=True,
                    origin="Flathub",
                    accent="#4A90D9",
                    scopes=list(record["scopes"]),
                )
            )
        return entries

    def _run(self, args: list[str]) -> None:
        binary = shutil.which("flatpak")
        if not binary:
            raise RuntimeError("flatpak is not installed")
        code, output = run_streaming([binary, *args])
        if code != 0:
            raise RuntimeError(output or f"flatpak {' '.join(args)} failed")

    def install(self, entry: AppEntry) -> None:
        remote, flag = install_remote_and_scope(entry.origin)
        if entry.scopes:
            preferred = entry.scopes[0]
            if scope_has_remote(preferred, remote):
                flag = f"--{preferred}"
        self._run(["install", "-y", flag, remote, entry.app_id])

    def remove(self, entry: AppEntry) -> None:
        scopes = entry.scopes or ["user", "system"]
        errors: list[str] = []
        for scope in scopes:
            try:
                self._run(["uninstall", "-y", f"--{scope}", entry.app_id])
            except CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))
        if errors and len(errors) == len(scopes):
            raise RuntimeError(errors[-1])

    def update_one(self, entry: AppEntry) -> None:
        scopes = entry.scopes or ["user", "system"]
        errors: list[str] = []
        for scope in scopes:
            try:
                self._run(["update", "-y", f"--{scope}", entry.app_id])
            except CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))
        if errors and len(errors) == len(scopes):
            raise RuntimeError(errors[-1])

    def update_all(self) -> None:
        self._run(["update", "-y", "--user"])
