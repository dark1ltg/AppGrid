from __future__ import annotations

import re
from collections import defaultdict

from appgrid.backends.base import AppEntry

_WEAK_TAILS = {
    "app",
    "org",
    "com",
    "net",
    "io",
    "desktop",
    "linux",
    "gnome",
    "kde",
    "gtk",
    "qt",
    "gui",
    "cli",
    "code",
    "player",
    "editor",
}


def _fold_name(entry: AppEntry) -> str:
    return re.sub(r"[^a-z0-9]+", "", entry.name.lower())


def _clean_id(value: str) -> str:
    return value.lower().removesuffix(".desktop").strip()


def _ids(entry: AppEntry) -> set[str]:
    found: set[str] = set()
    for raw in (entry.app_id, entry.launch_id, *entry.desktop_ids):
        cleaned = _clean_id(raw)
        if cleaned:
            found.add(cleaned)
    return found


def _pkgs(entry: AppEntry) -> set[str]:
    if not entry.package:
        return set()
    pkg = entry.package.lower().split(":")[0]
    if not pkg or pkg.startswith("lib") or len(pkg) < 3:
        return set()
    return {pkg}


def _id_tail(value: str) -> str | None:
    tail = value.split(".")[-1]
    if "." not in value:
        return None
    if len(tail) < 3 or tail in _WEAK_TAILS:
        return None
    return tail


def _cmp_versions(left: str, right: str) -> int:
    """Compare Debian-style versions (epoch, upstream, revision).

    A real version beats an empty one (#4).
    """
    if not left and not right:
        return 0
    if not left:
        return -1
    if not right:
        return 1
    return _cmp_debian(left, right)


def _split_epoch(text: str) -> tuple[int, str]:
    if ":" in text:
        head, tail = text.split(":", 1)
        if head.isdigit():
            return int(head), tail
    return 0, text


def _split_revision(text: str) -> tuple[str, str]:
    if "-" in text:
        upstream, revision = text.rsplit("-", 1)
        return upstream, revision
    return text, ""


def _cmp_debian(left: str, right: str) -> int:
    le, lu = _split_epoch(left.strip())
    re, ru = _split_epoch(right.strip())
    if le != re:
        return 1 if le > re else -1
    l_up, l_rev = _split_revision(lu)
    r_up, r_rev = _split_revision(ru)
    by_up = _cmp_debian_part(l_up, r_up)
    if by_up:
        return by_up
    return _cmp_debian_part(l_rev, r_rev)


def _cmp_debian_part(left: str, right: str) -> int:
    """Debian upstream/revision compare: '~' first, then letters, then other, digits as ints."""
    i = j = 0
    while i < len(left) or j < len(right):
        if i < len(left) and j < len(right) and left[i].isdigit() and right[j].isdigit():
            a, i = _read_digits(left, i)
            b, j = _read_digits(right, j)
            if a != b:
                return 1 if a > b else -1
            continue
        a_ch = left[i] if i < len(left) else ""
        b_ch = right[j] if j < len(right) else ""
        a_w = _debian_weight(a_ch)
        b_w = _debian_weight(b_ch)
        if a_w != b_w:
            return 1 if a_w > b_w else -1
        i += 1 if a_ch else 0
        j += 1 if b_ch else 0
    return 0


def _read_digits(text: str, index: int) -> tuple[int, int]:
    start = index
    while index < len(text) and text[index].isdigit():
        index += 1
    return int(text[start:index] or "0"), index


def _debian_weight(char: str) -> tuple[int, int]:
    if not char:
        return (1, 0)
    if char == "~":
        return (0, 0)
    if char.isalpha():
        return (2, ord(char))
    return (3, ord(char))


def _looks_runtime_train(version: str) -> bool:
    """Flatpak runtime-style trains (e.g. 24.08.1) mis-rank as Debian vs 1.2.0 (#8)."""
    text = (version or "").strip()
    if not text:
        return False
    return bool(re.match(r"^\d{2}\.\d{2}(\.|$)", text))


def _cross_backend_by_version(left: AppEntry, right: AppEntry) -> AppEntry | None:
    """Compare versions across backends without Debian-ranking runtime trains (#8)."""
    if not left.version and not right.version:
        return None
    if not left.version:
        return right
    if not right.version:
        return left
    left_rt = _looks_runtime_train(left.version)
    right_rt = _looks_runtime_train(right.version)
    # Don't Debian-compare a runtime train against a normal app version.
    if left_rt != right_rt:
        return None
    by_version = _cmp_versions(left.version, right.version)
    if by_version > 0:
        return left
    if by_version < 0:
        return right
    return None


def newer_source(left: AppEntry, right: AppEntry) -> AppEntry:
    """Pick the newest build.

    Same-backend: Debian version compare, then release_ts.
    Cross-backend: both release_ts → newer ts; one-sided ts yields to a clearly
    newer version string on the other side (#4); never Debian-compare a runtime
    train against a normal version (#8). Empty version loses. Remaining tie → APT.
    """
    same_backend = left.backend == right.backend
    if same_backend:
        if left.version or right.version:
            by_version = _cmp_versions(left.version, right.version)
            if by_version > 0:
                return left
            if by_version < 0:
                return right
        # Equal / empty versions: honor one-sided release_ts (# hunt-4 sev 3).
        if left.release_ts or right.release_ts:
            if left.release_ts and right.release_ts:
                if left.release_ts > right.release_ts:
                    return left
                if right.release_ts > left.release_ts:
                    return right
            elif left.release_ts:
                return left
            else:
                return right
    else:
        if left.release_ts and right.release_ts:
            if left.release_ts > right.release_ts:
                return left
            if right.release_ts > left.release_ts:
                return right
        elif left.release_ts or right.release_ts:
            # One-sided ts: runtime-train-safe version compare; newer other wins (#4/#6).
            ts_side = left if left.release_ts else right
            other = right if ts_side is left else left
            by_version = _cross_backend_by_version(other, ts_side)
            if by_version is other:
                return other
            if by_version is ts_side:
                return ts_side
            # Incomparable schemes (e.g. 24.08 vs 1.2): prefer non-runtime-train side.
            if _looks_runtime_train(ts_side.version) and not _looks_runtime_train(other.version):
                if other.version:
                    return other
            return ts_side
        by_version = _cross_backend_by_version(left, right)
        if by_version is not None:
            return by_version
    if left.backend == "apt":
        return left
    if right.backend == "apt":
        return right
    return left


def _fold(winner: AppEntry, other: AppEntry) -> None:
    if other.uid == winner.uid:
        return
    winner.extras.append(other)
    if not winner.screenshot:
        winner.screenshot = other.screenshot
    if other.screenshot and (not winner.thumb or winner.thumb == winner.icon):
        winner.thumb = other.screenshot
    if not winner.thumb:
        winner.thumb = other.thumb or other.icon
    if not winner.icon:
        winner.icon = other.icon
    if not winner.summary:
        winner.summary = other.summary
    if not winner.description:
        winner.description = other.description
    if not winner.version:
        winner.version = other.version
    if not winner.developer:
        winner.developer = other.developer
    if not winner.license:
        winner.license = other.license
    if not winner.homepage:
        winner.homepage = other.homepage
    if not winner.size_bytes and other.size_bytes:
        winner.size_bytes = other.size_bytes
    if other.rating > winner.rating:
        winner.rating = other.rating
    winner.alt_backend = other.backend
    winner.alt_package = other.package
    winner.alt_app_id = other.app_id
    winner.alt_scopes = list(other.scopes)


def pick_winner(cluster: list[AppEntry]) -> AppEntry:
    winner = cluster[0]
    for item in cluster[1:]:
        winner = newer_source(winner, item)
    for item in cluster:
        if item is not winner:
            _fold(winner, item)
    copies = [winner, *winner.extras]
    winner.installed = any(copy.self_installed for copy in copies)
    winner.has_update = any(copy.self_installed and copy.self_has_update for copy in copies)
    # Keep the winner's own version on the card face (#9). Do not overwrite with
    # an older installed APT copy when Flatpak won on newer.
    return winner


def merge_by_newer(entries: list[AppEntry]) -> list[AppEntry]:
    """One card per app: newest build from APT or Flatpak, never both.

    Merge on the same app id / package name, or when a simple APT package name
    matches the last part of a Flatpak id (firefox ↔ org.mozilla.firefox).
    Do not merge merely similar display names.
    """
    if not entries:
        return []
    parent = list(range(len(entries)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    def union_all(indexes: list[int]) -> None:
        if len(indexes) < 2:
            return
        first = indexes[0]
        for index in indexes[1:]:
            union(first, index)

    by_id: dict[str, list[int]] = defaultdict(list)
    by_pkg: dict[str, list[int]] = defaultdict(list)
    by_id_tail: dict[str, list[int]] = defaultdict(list)
    by_simple_pkg: dict[str, list[int]] = defaultdict(list)

    for index, entry in enumerate(entries):
        for ident in _ids(entry):
            by_id[ident].append(index)
            tail = _id_tail(ident)
            if tail:
                by_id_tail[tail].append(index)
        for pkg in _pkgs(entry):
            by_pkg[pkg].append(index)
            if "." not in pkg:
                by_simple_pkg[pkg].append(index)

    for indexes in by_id.values():
        union_all(indexes)
    for indexes in by_pkg.values():
        union_all(indexes)
    for tail, pkg_indexes in by_simple_pkg.items():
        id_indexes = [index for index in by_id_tail.get(tail, []) if index not in pkg_indexes]
        if not id_indexes:
            continue
        for pkg_i in pkg_indexes:
            apt_entry = entries[pkg_i]
            named = [
                index
                for index in id_indexes
                if _fold_name(entries[index]) == _fold_name(apt_entry)
            ]
            if len(named) == 1:
                pick = named[0]
            elif len(id_indexes) == 1:
                pick = id_indexes[0]
            elif named:
                pick = named[0]
            else:
                continue
            union(pkg_i, pick)

    groups: dict[int, list[AppEntry]] = defaultdict(list)
    for index, entry in enumerate(entries):
        groups[find(index)].append(entry)

    merged = [pick_winner(cluster) for cluster in groups.values()]
    merged.sort(key=lambda item: item.name.lower())
    return merged


def merge_by_id(entries: list[AppEntry]) -> list[AppEntry]:
    """Fallback merge: same app id only, so a failed full merge does not show duplicates."""
    groups: dict[str, list[AppEntry]] = defaultdict(list)
    leftover: list[AppEntry] = []
    for entry in entries:
        key = _clean_id(entry.app_id)
        if not key:
            leftover.append(entry)
            continue
        groups[key].append(entry)
    merged = [pick_winner(cluster) if len(cluster) > 1 else cluster[0] for cluster in groups.values()]
    merged.extend(leftover)
    merged.sort(key=lambda item: item.name.lower())
    return merged
