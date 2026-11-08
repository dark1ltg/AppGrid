from __future__ import annotations

import time

from appgrid.qt import Property, QObject, QTimer, Signal, Slot

from appgrid.backends.base import AppEntry
from appgrid.backends.registry import BackendRegistry
from appgrid.catalog.groups import present as present_categories, detail_category
from appgrid.catalog.snapshot import load_snapshot
from appgrid.models.app_list import AppFilterModel, AppListModel
from appgrid.services import jobs
from appgrid.services.distro import UNSUPPORTED_MESSAGE, is_debian_family, native_store_label
from appgrid.services.settings import AppSettings
from appgrid.services.worker import ActionWorker, CatalogWorker

# Re-check package indexes when opening Updates after this many seconds (#9).
_INDEX_REFRESH_COOLDOWN_S = 60.0
# How long Install/fail footer stays before returning to catalog counts (#10).
_PENDING_STATUS_HOLD_MS = 5000


class AppController(QObject):
    catalogChanged = Signal()
    statusChanged = Signal()
    selectionChanged = Signal()
    busyChanged = Signal()
    progressChanged = Signal()
    filterChanged = Signal()
    settingsChanged = Signal()

    def __init__(
        self,
        demo: bool = False,
        *,
        flatpak_enabled: bool | None = None,
        merge_duplicates: bool = True,
        show_source_badges: bool = False,
    ) -> None:
        super().__init__()
        self._registry = BackendRegistry(demo=demo)
        self._settings = AppSettings()
        self._flatpak_override = flatpak_enabled
        self._merge_duplicates = merge_duplicates
        self._show_source_badges = show_source_badges
        self._demo = demo
        self._supported = demo or is_debian_family()
        self._source = AppListModel()
        self._model = AppFilterModel(self._source)
        self._status = "Loading apps…"
        self._busy = True
        self._progress_percent = -1  # -1 = indeterminate (no fake 0–100)
        self._filter = "all"
        self._category = ""
        self._query = ""
        self._selected: AppEntry | None = None
        self._pending_status: str | None = None
        # Generation so a stale clear timer cannot wipe a newer sticky (#4).
        self._pending_status_gen: int = 0
        self._active_action: str = ""
        self._worker: ActionWorker | None = None
        self._catalog_worker: CatalogWorker | None = None
        self._reload_again = False
        self._reload_refresh = False
        self._post_action_reload = False
        self._index_refresh_at = 0.0
        self._index_refresh_pending = False
        if not self._supported:
            self._busy = False
            self._status = UNSUPPORTED_MESSAGE
            return
        if not demo:
            cached = load_snapshot(self.flatpakEnabled)
            if cached:
                self._busy = False
                self._apply_catalog(cached)
        self.reload()

    def model(self) -> AppListModel:
        return self._model

    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    def _set_status(self, text: str) -> None:
        self._status = text
        self.statusChanged.emit()

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    def _set_busy(self, value: bool) -> None:
        self._busy = value
        self.busyChanged.emit()
        if not value:
            self._set_progress_percent(-1)

    @Property(int, notify=progressChanged)
    def progressPercent(self) -> int:
        """0–100 when a backend reported percent; -1 when indeterminate."""
        return self._progress_percent

    @Property(bool, notify=progressChanged)
    def progressKnown(self) -> bool:
        return self._progress_percent >= 0

    def _set_progress_percent(self, value: int) -> None:
        percent = int(value)
        if percent < 0 or percent > 100:
            percent = -1
        if percent == self._progress_percent:
            return
        self._progress_percent = percent
        self.progressChanged.emit()

    @Slot(int)
    def previewProgress(self, percent: int) -> None:
        """Screenshot / demo helper: show busy footer with a known percent."""
        self._set_busy(True)
        self._set_progress_percent(percent)
        if percent >= 0:
            self._set_status(f"Installing… {percent}%")
        else:
            self._set_status("Working…")

    @Property(str, notify=filterChanged)
    def filterMode(self) -> str:
        return self._filter

    @Property(str, notify=filterChanged)
    def categoryFilter(self) -> str:
        return self._category

    @Property(str, notify=filterChanged)
    def searchQuery(self) -> str:
        return self._query

    @Property("QVariantList", notify=catalogChanged)
    def categories(self) -> list:
        return present_categories(self._source.entries())

    @Property(int, notify=catalogChanged)
    def countAll(self) -> int:
        return self._model.counts()["all"]

    @Property(int, notify=catalogChanged)
    def countInstalled(self) -> int:
        return self._model.counts()["installed"]

    @Property(int, notify=catalogChanged)
    def countUpdates(self) -> int:
        return self._model.counts()["updates"]

    @Property(int, notify=catalogChanged)
    def countVisible(self) -> int:
        return self._model.counts()["visible"]

    def _selected_value(self, key: str, default=""):
        if self._selected is None:
            return default
        return getattr(self._selected, key)

    @Property(str, notify=selectionChanged)
    def selectedUid(self) -> str:
        return self._selected.uid if self._selected else ""

    @Property(str, notify=selectionChanged)
    def selectedName(self) -> str:
        return self._selected.name if self._selected else ""

    @Property(str, notify=selectionChanged)
    def selectedSummary(self) -> str:
        return self._selected.summary if self._selected else ""

    @Property(str, notify=selectionChanged)
    def selectedDescription(self) -> str:
        if not self._selected:
            return ""
        return self._selected.description or self._selected.summary

    @Property(str, notify=selectionChanged)
    def selectedBackend(self) -> str:
        return self._selected.backend if self._selected else ""

    @Property(str, notify=selectionChanged)
    def selectedOrigin(self) -> str:
        return self._selected.origin if self._selected else ""

    @Property(str, notify=selectionChanged)
    def selectedVersion(self) -> str:
        return self._selected.version if self._selected else ""

    @Property(str, notify=selectionChanged)
    def selectedFactVersion(self) -> str:
        """Version for the optional facts bar (same as selectedVersion)."""
        return self.selectedVersion

    @Property(str, notify=selectionChanged)
    def selectedLicense(self) -> str:
        return (self._selected.license or "").strip() if self._selected else ""

    @Property(str, notify=selectionChanged)
    def selectedHomepage(self) -> str:
        return (self._selected.homepage or "").strip() if self._selected else ""

    @Property(str, notify=selectionChanged)
    def selectedHomepageHost(self) -> str:
        url = self.selectedHomepage
        if not url:
            return ""
        text = url
        for prefix in ("https://", "http://"):
            if text.startswith(prefix):
                text = text[len(prefix) :]
                break
        return text.removesuffix("/")

    @Property(str, notify=selectionChanged)
    def selectedSizeLabel(self) -> str:
        if not self._selected:
            return ""
        return self._format_size(int(self._selected.size_bytes or 0))

    @Property(bool, notify=selectionChanged)
    def selectedHasFacts(self) -> bool:
        return bool(
            self.selectedFactVersion
            or self.selectedLicense
            or self.selectedSizeLabel
            or self.selectedHomepage
        )

    @staticmethod
    def _format_size(nbytes: int) -> str:
        if nbytes <= 0:
            return ""
        units = (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10))
        for label, scale in units:
            if nbytes >= scale:
                value = nbytes / scale
                if label == "KB" and value >= 10:
                    return f"{value:.0f} {label}"
                return f"{value:.1f} {label}"
        return f"{nbytes} B"

    @Property(float, notify=selectionChanged)
    def selectedRating(self) -> float:
        return float(self._selected.rating) if self._selected else 0.0

    @Property(str, notify=selectionChanged)
    def selectedAccent(self) -> str:
        return self._selected.accent if self._selected else "#3D8B8B"

    @Property(str, notify=selectionChanged)
    def selectedIcon(self) -> str:
        return self._selected.icon if self._selected else ""

    @Property(str, notify=selectionChanged)
    def selectedScreenshot(self) -> str:
        return self._selected.screenshot if self._selected else ""

    @Property(str, notify=selectionChanged)
    def selectedInitial(self) -> str:
        if not self._selected:
            return ""
        return self._selected.name[:1].upper()

    @Property(str, notify=selectionChanged)
    def selectedCategory(self) -> str:
        return detail_category(self._selected) if self._selected else ""

    @Property(str, notify=selectionChanged)
    def selectedDeveloper(self) -> str:
        if not self._selected:
            return ""
        name = (self._selected.developer or "").strip()
        if not name:
            return ""
        if name.lower() == (self._selected.name or "").lower():
            return ""
        return name

    @Property(str, notify=selectionChanged)
    def selectedPrimaryAction(self) -> str:
        if not self._selected:
            return ""
        installed = self._installed_native_copies()
        # Newer uninstalled winner → Install even if an older copy has an update (#5).
        if (
            installed
            and not self._selected.self_installed
            and self._selected.backend in {"apt", "flatpak"}
        ):
            return "install"
        if installed and self._selected.has_update:
            return "update"
        if not installed:
            return "install"
        return ""

    def _installed_native_copies(self) -> list[AppEntry]:
        if not self._selected:
            return []
        copies = [self._selected, *self._selected.extras]
        return [
            copy
            for copy in copies
            if copy.self_installed and copy.backend in {"apt", "flatpak"}
        ]

    @Property(bool, notify=selectionChanged)
    def selectedInstalled(self) -> bool:
        return bool(self._installed_native_copies())

    @Property(str, notify=selectionChanged)
    def selectedStatusLabel(self) -> str:
        """Detail-page install status: live job verb, or Installed / Not Installed."""
        action = self._active_action
        if action == "cancelling":
            return "Cancelling…"
        if action == "install":
            return "Installing…"
        if action == "update":
            return "Updating…"
        if action == "remove":
            return "Removing…"
        if action == "update-all":
            return "Updating…"
        if self._installed_native_copies():
            return "Installed"
        return "Not Installed"

    @Property(str, notify=busyChanged)
    def activeAction(self) -> str:
        return self._active_action

    def _set_active_action(self, action: str) -> None:
        action = action or ""
        if action == self._active_action:
            return
        self._active_action = action
        self.busyChanged.emit()
        self.selectionChanged.emit()

    @Property(bool, notify=selectionChanged)
    def selectedHasUpdate(self) -> bool:
        return bool(self._selected and self._selected.has_update)

    @Property(bool, notify=selectionChanged)
    def selectedCanInstall(self) -> bool:
        return bool(self._selected and self.selectedPrimaryAction == "install")

    @Property(bool, notify=selectionChanged)
    def selectedInstallOverCopy(self) -> bool:
        """True when Install would add a newer source beside an older installed copy (#6)."""
        return bool(
            self._selected
            and self.selectedPrimaryAction == "install"
            and self._installed_native_copies()
        )

    @Property(bool, notify=selectionChanged)
    def selectedCanUpdateInstalled(self) -> bool:
        """Update for older installed copy while Install-newer is primary (hunt-4 sev 3)."""
        if not self.selectedInstallOverCopy:
            return False
        return any(copy.self_has_update for copy in self._installed_native_copies())

    @Property(bool, notify=selectionChanged)
    def selectedCanRemove(self) -> bool:
        return bool(self._installed_native_copies())

    @Property(int, notify=selectionChanged)
    def selectedCopyCount(self) -> int:
        if not self._selected:
            return 0
        return sum(1 for copy in [self._selected, *self._selected.extras] if copy.self_installed)

    @Property(bool, notify=settingsChanged)
    def flatpakEnabled(self) -> bool:
        if self._flatpak_override is not None:
            return self._flatpak_override
        return self._settings.flatpak_enabled

    @Property(bool, constant=True)
    def showSourceBadges(self) -> bool:
        return self._show_source_badges

    @Property(bool, constant=True)
    def supportedDistro(self) -> bool:
        return self._supported

    @Property(str, constant=True)
    def unsupportedMessage(self) -> str:
        return UNSUPPORTED_MESSAGE

    @Property(str, constant=True)
    def nativeStoreLabel(self) -> str:
        if self._demo:
            return "Ubuntu"
        return native_store_label()

    @Slot(bool)
    def setFlatpakEnabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == bool(self.flatpakEnabled):
            return
        self._settings.flatpak_enabled = enabled
        self.settingsChanged.emit()
        if self._action_running():
            self._reload_again = True
            return
        self.reload()

    @staticmethod
    def _thread_running(worker) -> bool:
        if worker is None:
            return False
        try:
            return bool(worker.isRunning())
        except RuntimeError:
            # QObject already destroyed via deleteLater.
            return False

    def _action_running(self) -> bool:
        running = self._thread_running(self._worker)
        if not running:
            self._worker = None
        return running

    def _catalog_running(self) -> bool:
        running = self._thread_running(self._catalog_worker)
        if not running:
            self._catalog_worker = None
        return running

    @Slot()
    def reload(self) -> None:
        self._pending_status = None
        self._pending_status_gen += 1
        self._reload(False)

    def _reload(self, refresh_indexes: bool) -> None:
        if not self._supported:
            self._set_busy(False)
            self._set_status(UNSUPPORTED_MESSAGE)
            return
        if refresh_indexes:
            self._reload_refresh = True
        if self._action_running():
            self._reload_again = True
            return
        if self._catalog_running():
            self._reload_again = True
            return
        use_refresh = self._reload_refresh
        self._reload_refresh = False
        keep_busy = self._post_action_reload
        self._post_action_reload = False
        has_grid = bool(self._source.entries())
        # Keep busy through post-action refresh so Cancel stays until catalog finishes (#3).
        self._set_busy(True if keep_busy or not has_grid else False)
        self._set_progress_percent(-1)
        if use_refresh:
            self._set_status("Checking for updates…")
        elif self._pending_status:
            # Keep success/fail footer during refresh (#9).
            pass
        elif has_grid:
            self._set_status("Refreshing apps…")
        else:
            self._set_status("Loading apps…")
        if self._filter in {"apt", "flatpak"}:
            self._filter = "all"
        jobs.reset()
        worker = CatalogWorker(
            self._registry,
            flatpak_enabled=self.flatpakEnabled,
            merge_duplicates=self._merge_duplicates,
            refresh_indexes=use_refresh,
            skip_snapshot=keep_busy,
        )
        worker.loaded.connect(self._on_catalog)
        worker.failed.connect(self._on_catalog_fail)
        # Don't let catalog chatter wipe a sticky Install/fail message.
        if not self._pending_status:
            worker.progress.connect(self._set_status)
        worker.progressPercent.connect(self._set_progress_percent)
        worker.indexesRefreshed.connect(self._on_indexes_refreshed)
        worker.finished.connect(worker.deleteLater)
        self._catalog_worker = worker
        worker.start()

    def _on_catalog(self, apps: object) -> None:
        self._apply_catalog(list(apps) if apps else [])
        if self._reload_again and not self._action_running():
            worker = self._catalog_worker
            if worker is None or not self._thread_running(worker):
                self._reload_again = False
                self._reload(False)

    def _apply_catalog(self, apps: list[AppEntry]) -> None:
        selected_uid = self._selected.uid if self._selected else ""
        app_id = self._selected.app_id if self._selected else ""
        name = self._selected.name if self._selected else ""
        self._model.set_catalog(apps)
        available = {item["id"] for item in present_categories(self._source.entries())}
        if self._category and self._category not in available:
            self._category = ""
        self._model.apply_filters(self._query, self._filter, self._category)
        if selected_uid or app_id or name:
            self._selected = self._model.resolve(selected_uid, app_id, name)
        counts = self._model.counts()
        # Keep Install/fail/success text sticky across snapshot+full catalog emits.
        # Clearing here made Kubuntu installs look like a silent no-op: fail → brief
        # footer → second catalog apply replaced it with "N apps · …".
        status = self._pending_status or (
            f"{counts['all']} apps · {counts['installed']} installed · {counts['updates']} updates"
        )
        self._set_status(status)
        if self._pending_status and not self._action_running() and not self._catalog_running():
            # After the user has had time to read it, return to catalog counts (#10).
            self._schedule_pending_clear()
        if not self._action_running():
            self._set_busy(False)
        self.catalogChanged.emit()
        self.selectionChanged.emit()

    def _schedule_pending_clear(self) -> None:
        token = self._pending_status_gen
        QTimer.singleShot(
            _PENDING_STATUS_HOLD_MS, lambda: self._clear_pending_status(token)
        )

    def _clear_pending_status(self, token: int | None = None) -> None:
        # Ignore stale timers from an earlier sticky message (#4).
        if token is not None and token != self._pending_status_gen:
            return
        if not self._pending_status:
            return
        if self._action_running() or self._catalog_running():
            return
        self._pending_status = None
        counts = self._model.counts()
        self._set_status(
            f"{counts['all']} apps · {counts['installed']} installed · {counts['updates']} updates"
        )

    def _on_indexes_refreshed(self, ok: bool) -> None:
        self._index_refresh_pending = False
        if ok:
            self._index_refresh_at = time.monotonic()

    def _on_catalog_fail(self, message: str) -> None:
        self._index_refresh_pending = False
        # Catalog cancel never hits _on_ok/_on_fail; clear Cancelling… here (#1).
        self._set_active_action("")
        # Prefer a pending action error over a generic catalog-cancel wipe.
        text = self._pending_status or message or "Could not load the app list"
        self._set_status(text)
        if self._pending_status and not self._action_running():
            self._schedule_pending_clear()
        if not self._action_running():
            self._set_busy(False)
        self.catalogChanged.emit()
        if self._reload_again and not self._action_running():
            self._reload_again = False
            self._reload(False)

    @Slot(str)
    def setSearch(self, query: str) -> None:
        self._query = query
        self._model.apply_filters(self._query, self._filter, self._category)
        self.filterChanged.emit()
        self.catalogChanged.emit()

    @Slot(str)
    def setFilter(self, mode: str) -> None:
        self._filter = mode
        self._model.apply_filters(self._query, self._filter, self._category)
        self.filterChanged.emit()
        self.catalogChanged.emit()
        # Refresh indexes when opening Updates, with a short cooldown (#9).
        stale = (time.monotonic() - self._index_refresh_at) >= _INDEX_REFRESH_COOLDOWN_S
        if (
            mode == "updates"
            and self._supported
            and not self._demo
            and stale
            and not self._index_refresh_pending
        ):
            self._index_refresh_pending = True
            if self._action_running() or self._catalog_running():
                self._reload_refresh = True
                self._reload_again = True
                self._index_refresh_pending = False
                return
            self._reload(True)

    @Slot(str)
    def setCategory(self, category: str) -> None:
        self._category = "" if category == "all" else category
        self._model.apply_filters(self._query, self._filter, self._category)
        self.filterChanged.emit()
        self.catalogChanged.emit()

    @Slot(str)
    def select(self, uid: str) -> None:
        app_id = uid.split(":", 1)[-1] if ":" in uid else uid
        self._selected = self._model.resolve(uid, app_id=app_id, name=uid)
        self.selectionChanged.emit()

    @Slot()
    def clearSelection(self) -> None:
        self._selected = None
        self.selectionChanged.emit()

    @Slot()
    def installSelected(self) -> None:
        self._run("install")

    @Slot()
    def removeSelected(self) -> None:
        self._run("remove")

    @Slot()
    def updateSelected(self) -> None:
        self._run("update")

    @Slot()
    def updateAll(self) -> None:
        self._run("update-all")

    def _run(self, action: str) -> None:
        if not self._supported:
            self._set_status(UNSUPPORTED_MESSAGE)
            return
        if self._busy:
            return
        if self._catalog_running():
            self._set_status("Still loading the app list…")
            return
        entry = self._selected
        if action != "update-all" and entry is None:
            return
        if action == "update-all":
            label = "Updating installed packages and libraries…"
        else:
            label = {
                "install": f"Installing {entry.name}…",
                "remove": f"Removing {entry.name}…",
                "update": f"Updating {entry.name}…",
            }[action]
        self._pending_status = None
        self._pending_status_gen += 1
        self._set_active_action(action)
        self._set_busy(True)
        self._set_progress_percent(-1)
        self._set_status(label)
        try:
            jobs.reset()
            self._worker = ActionWorker(
                self._registry, action, entry, flatpak_enabled=self.flatpakEnabled
            )
            self._worker.finished_ok.connect(self._on_ok)
            self._worker.failed.connect(self._on_fail)
            self._worker.progress.connect(self._set_status)
            self._worker.progressPercent.connect(self._set_progress_percent)
            self._worker.finished.connect(self._worker.deleteLater)
            self._worker.start()
        except Exception as exc:  # noqa: BLE001
            self._set_active_action("")
            self._set_busy(False)
            self._set_status(str(exc) or "Could not start that action")

    def _on_ok(self, message: str) -> None:
        # Mirror fail-path: deferred reload until the action thread has stopped (#1).
        self._set_active_action("")
        self._pending_status = message
        self._pending_status_gen += 1
        self._set_status(message or "Done")
        self._reload_again = True
        worker = self._worker
        if worker is not None and self._action_running():
            worker.finished.connect(self._reload_after_action)
        QTimer.singleShot(0, self._reload_after_action)

    def _on_fail(self, message: str) -> None:
        # Refresh install flags after fail/cancel so DetailPage/grid match reality:
        # failed install with nothing installed → Not Installed; failed update/remove
        # that left the app installed → stay Installed (failure stays in the footer).
        self._set_active_action("")
        text = message or "Action failed"
        self._pending_status = text
        self._pending_status_gen += 1
        self._set_status(text)
        self._index_refresh_pending = False
        # Keep a queued Updates index refresh across fail (#8); do not clear
        # _reload_refresh here — success path already preserves it.
        # Keep busy until reload starts so a new action cannot interleave (#6).
        self._reload_again = True
        worker = self._worker
        if worker is not None and self._action_running():
            worker.finished.connect(self._reload_after_action)
        QTimer.singleShot(0, self._reload_after_action)

    def _reload_after_action(self) -> None:
        if self._action_running():
            return
        worker = self._worker
        if worker is not None:
            try:
                worker.finished.disconnect(self._reload_after_action)
            except (TypeError, RuntimeError):
                pass
        if not self._reload_again:
            # Aborted deferred reload (e.g. stale callback): never leave Cancelling… (#1).
            self._set_active_action("")
            if not self._catalog_running():
                self._set_busy(False)
            return
        self._reload_again = False
        self._post_action_reload = True
        # Keep sticky Install/fail text: do not call reload() which clears it.
        self._reload(False)

    @Slot()
    def cancelJob(self) -> None:
        if not self._busy:
            return
        jobs.request()
        # Only show Cancelling… while an action worker is alive (#1).
        # Do not clear _reload_again: post-action refresh must still run after
        # cancel in the deferred-reload gap (busy true, action already finished).
        if self._action_running():
            self._set_active_action("cancelling")
            self._set_status("Cancelling…")
            return
        self._set_active_action("")
        self._set_status("Cancelling…")
