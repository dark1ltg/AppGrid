from __future__ import annotations

from appgrid.qt import QThread, Signal

from appgrid.backends.base import AppEntry
from appgrid.backends.registry import BackendRegistry
from appgrid.catalog.snapshot import load_snapshot
from appgrid.services import progress
from appgrid.services.jobs import CancelledError
from appgrid.services.packagekit import refresh_package_indexes
from appgrid.services.reboot import reboot_required


def _copies(entry: AppEntry) -> list[AppEntry]:
    items = [entry, *entry.extras]
    seen: set[str] = set()
    copies: list[AppEntry] = []
    for item in items:
        if item.uid in seen:
            continue
        seen.add(item.uid)
        copies.append(item)
    return copies


class CatalogWorker(QThread):
    loaded = Signal(object)
    failed = Signal(str)
    progress = Signal(str)
    progressPercent = Signal(int)  # -1 = indeterminate
    indexesRefreshed = Signal(bool)

    def __init__(
        self,
        registry: BackendRegistry,
        flatpak_enabled: bool = False,
        merge_duplicates: bool = True,
        refresh_indexes: bool = False,
        skip_snapshot: bool = False,
    ) -> None:
        super().__init__()
        self._registry = registry
        self._flatpak_enabled = flatpak_enabled
        self._merge_duplicates = merge_duplicates
        self._refresh_indexes = refresh_indexes
        # Post-action reloads must not emit a stale snapshot first: that apply
        # used to clear the Install/fail footer before the real catalog arrived.
        self._skip_snapshot = skip_snapshot

    def run(self) -> None:
        progress.set_reporter(self.progress.emit, self.progressPercent.emit)
        progress.report_percent(None)
        try:
            if self._refresh_indexes:
                try:
                    refresh_package_indexes()
                    self.indexesRefreshed.emit(True)
                except CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    progress.report(str(exc) or "Could not check for updates")
                    self.indexesRefreshed.emit(False)
            if (
                not self._registry.demo
                and not self._refresh_indexes
                and not self._skip_snapshot
            ):
                cached = load_snapshot(self._flatpak_enabled)
                if cached:
                    self.loaded.emit(
                        self._registry.overlay_install_state(
                            cached, flatpak_enabled=self._flatpak_enabled
                        )
                    )
            self.loaded.emit(
                self._registry.catalog(
                    flatpak_enabled=self._flatpak_enabled,
                    merge_duplicates=self._merge_duplicates,
                    refresh_metadata=self._refresh_indexes,
                )
            )
        except CancelledError:
            self.failed.emit("Cancelled.")
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
        finally:
            progress.set_reporter(None)


class ActionWorker(QThread):
    finished_ok = Signal(str)
    failed = Signal(str)
    progress = Signal(str)
    progressPercent = Signal(int)  # -1 = indeterminate

    def __init__(
        self,
        registry: BackendRegistry,
        action: str,
        entry: AppEntry | None,
        flatpak_enabled: bool = False,
    ) -> None:
        super().__init__()
        self._registry = registry
        self._action = action
        self._entry = entry
        self._flatpak_enabled = flatpak_enabled

    def _plugin(self, backend: str):
        if backend == "flatpak" and not self._flatpak_enabled and not self._registry.demo:
            raise RuntimeError("Flatpak is turned off in Settings")
        return self._registry.get(backend)

    def _act_on_copies(self, entry: AppEntry, action: str) -> str:
        copies = _copies(entry)
        if action == "install":
            targets = [entry]
            verb = "Installed"
        elif action == "remove":
            targets = [copy for copy in copies if copy.self_installed]
            verb = "Removed"
            if not targets:
                raise RuntimeError(f"{entry.name} is not installed")
        elif action == "update":
            targets = [copy for copy in copies if copy.self_installed and copy.self_has_update]
            if not targets:
                targets = [copy for copy in copies if copy.self_installed]
            verb = "Updated"
            if not targets:
                raise RuntimeError(f"{entry.name} is not installed")
        else:
            raise RuntimeError(f"Unknown action {action}")

        errors: list[str] = []
        done = 0
        for target in targets:
            try:
                plugin = self._plugin(target.backend)
                if action == "install":
                    plugin.install(target)
                elif action == "remove":
                    plugin.remove(target)
                else:
                    plugin.update_one(target)
                done += 1
            except CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))
        if done == 0:
            raise RuntimeError(errors[-1] if errors else f"Could not {action} {entry.name}")
        # Partial multi-copy success is not full success (#10).
        if errors:
            raise RuntimeError(
                f"Could not fully {action} {entry.name} "
                f"({done}/{len(targets)} copies ok). {errors[-1]}"
            )
        return f"{verb} {entry.name}"

    def run(self) -> None:
        progress.set_reporter(self.progress.emit, self.progressPercent.emit)
        progress.report_percent(None)
        try:
            if self._action == "update-all":
                completed = 0
                failed: list[tuple[str, str]] = []
                cancelled_note = ""
                for name, plugin in self._registry.plugins.items():
                    if name == "flatpak" and not self._flatpak_enabled:
                        continue
                    try:
                        plugin.update_all()
                        completed += 1
                    except CancelledError:
                        # APT (or earlier backend) finished; do not hard-fail the job (#5).
                        if completed:
                            cancelled_note = " Some updates were cancelled."
                            break
                        raise
                    except Exception as exc:  # noqa: BLE001
                        failed.append((name, str(exc)))
                if completed == 0:
                    raise RuntimeError(failed[-1][1] if failed else "Could not update packages")
                if reboot_required():
                    message = (
                        "Package updates finished. Restart the computer to finish applying library and kernel updates."
                    )
                else:
                    message = "Package updates finished."
                if cancelled_note:
                    message += cancelled_note
                    self.finished_ok.emit(message)
                    return
                if failed:
                    kinds = {item[0] for item in failed}
                    cancelish = [
                        msg for _, msg in failed if "cancel" in (msg or "").lower()
                    ]
                    # Prefer concrete partial-cancel text from Flatpak (#4).
                    if cancelish:
                        message += " " + cancelish[-1]
                    elif kinds == {"flatpak"}:
                        message += " Flatpak updates could not be completed."
                    elif "flatpak" not in kinds:
                        message += " System package updates could not be completed."
                    else:
                        message += " Some updates could not be completed."
                    # Non-cancel partial backend failure → fail sticky (hunt-5 sev 3).
                    raise RuntimeError(message)
                self.finished_ok.emit(message)
                return
            if self._entry is None:
                raise RuntimeError("No application selected")
            self.finished_ok.emit(self._act_on_copies(self._entry, self._action))
        except CancelledError:
            self.failed.emit("Cancelled.")
        except Exception as exc:  # noqa: BLE001 — surface package manager errors in the status bar
            self.failed.emit(str(exc))
        finally:
            progress.set_reporter(None)
