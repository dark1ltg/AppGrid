from __future__ import annotations

from appgrid.qt import QAbstractListModel, QModelIndex, QSortFilterProxyModel, Qt

from appgrid.backends.base import AppEntry
from appgrid.catalog.groups import matches as category_matches

ROLES = {
    Qt.UserRole + 1: "uid",
    Qt.UserRole + 2: "backend",
    Qt.UserRole + 3: "appId",
    Qt.UserRole + 4: "name",
    Qt.UserRole + 5: "summary",
    Qt.UserRole + 6: "description",
    Qt.UserRole + 7: "packageName",
    Qt.UserRole + 8: "version",
    Qt.UserRole + 9: "icon",
    Qt.UserRole + 10: "screenshot",
    Qt.UserRole + 16: "thumb",
    Qt.UserRole + 11: "installed",
    Qt.UserRole + 12: "hasUpdate",
    Qt.UserRole + 13: "origin",
    Qt.UserRole + 14: "accent",
    Qt.UserRole + 15: "initial",
    Qt.UserRole + 17: "rating",
}


class AppListModel(QAbstractListModel):
    def __init__(self) -> None:
        super().__init__()
        self._all: list[AppEntry] = []

    def set_catalog(self, entries: list[AppEntry]) -> None:
        self.beginResetModel()
        self._all = list(entries)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._all)

    def item_at(self, row: int) -> AppEntry | None:
        if 0 <= row < len(self._all):
            return self._all[row]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._all)):
            return None
        item = self._all[index.row()]
        mapping = {
            Qt.UserRole + 1: item.uid,
            Qt.UserRole + 2: item.backend,
            Qt.UserRole + 3: item.app_id,
            Qt.UserRole + 4: item.name,
            Qt.UserRole + 5: item.summary,
            Qt.UserRole + 6: item.description,
            Qt.UserRole + 7: item.package,
            Qt.UserRole + 8: item.version,
            Qt.UserRole + 9: item.icon,
            Qt.UserRole + 10: item.screenshot,
            Qt.UserRole + 16: item.thumb or item.icon,
            Qt.UserRole + 11: item.installed,
            Qt.UserRole + 12: item.has_update,
            Qt.UserRole + 13: item.origin,
            Qt.UserRole + 14: item.accent,
            Qt.UserRole + 15: (item.name[:1] or "?").upper(),
            Qt.UserRole + 17: item.rating,
        }
        return mapping.get(role)

    def roleNames(self):  # noqa: N802
        return {key: value.encode() for key, value in ROLES.items()}

    def entry(self, uid: str) -> AppEntry | None:
        for item in self._all:
            if item.uid == uid:
                return item
        return None

    def resolve(self, uid: str, app_id: str = "", name: str = "") -> AppEntry | None:
        found = self.entry(uid)
        if found:
            return found
        if app_id:
            for item in self._all:
                ids = {item.app_id, *(extra.app_id for extra in item.extras)}
                if app_id in ids:
                    return item
        folded = (name or "").strip().lower()
        if folded:
            matches = [item for item in self._all if item.name.lower() == folded]
            if len(matches) == 1:
                return matches[0]
        return None

    def entries(self) -> list[AppEntry]:
        return list(self._all)

    def counts(self) -> dict[str, int]:
        return {
            "all": len(self._all),
            "installed": sum(1 for item in self._all if item.installed),
            "updates": sum(1 for item in self._all if item.has_update),
        }


class AppFilterModel(QSortFilterProxyModel):
    def __init__(self, source: AppListModel) -> None:
        super().__init__()
        self._source = source
        self._query = ""
        self._mode = "all"
        self._category = ""
        self.setSourceModel(source)
        self.setDynamicSortFilter(True)

    def apply_filters(self, query: str, mode: str, category: str = "") -> None:
        self._query = query
        self._mode = mode
        self._category = category
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:  # noqa: N802
        item = self._source.item_at(source_row)
        if item is None:
            return False
        mode = self._mode
        if mode == "installed" and not item.installed:
            return False
        if mode == "updates" and not item.has_update:
            return False
        if mode in {"apt", "flatpak"} and item.backend != mode:
            return False
        if self._category and not category_matches(item, self._category):
            return False
        needle = self._query.strip().lower()
        if needle:
            hay = f"{item.name} {item.summary} {item.app_id} {item.package}".lower()
            if needle not in hay:
                return False
        return True

    def entry(self, uid: str) -> AppEntry | None:
        return self._source.entry(uid)

    def resolve(self, uid: str, app_id: str = "", name: str = "") -> AppEntry | None:
        return self._source.resolve(uid, app_id, name)

    def set_catalog(self, entries: list[AppEntry]) -> None:
        self._source.set_catalog(entries)

    def counts(self) -> dict[str, int]:
        counts = self._source.counts()
        counts["visible"] = self.rowCount()
        return counts
