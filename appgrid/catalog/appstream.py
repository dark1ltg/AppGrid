from __future__ import annotations

import multiprocessing
from dataclasses import asdict, fields

from appgrid.backends.base import AppEntry
from appgrid.catalog.text import plain_text
from appgrid.services.jobs import CancelledError, check as jobs_check, register_mp, unregister_mp

_pool = None
_loaded = False
_catalog_payload: dict[str, list[dict]] | None = None
_APPSTREAM_MISSING = (
    "AppGrid cannot read the application catalog. "
    "Install AppStream (package gir1.2-appstream-1.0) and reopen AppGrid."
)
_APPSTREAM_CRASH = (
    "The application catalog stopped unexpectedly. "
    "AppGrid is still running; try again, or install AppStream "
    "(package gir1.2-appstream-1.0)."
)


def reset_pool() -> None:
    global _pool, _loaded, _catalog_payload
    _pool = None
    _loaded = False
    _catalog_payload = None


def _bundle_backends(component) -> set[str]:
    """A component can be both a Debian package and a Flatpak; keep both."""
    import gi

    gi.require_version("AppStream", "1.0")
    from gi.repository import AppStream

    found: set[str] = set()
    bundles = component.get_bundles() or []
    kinds = [b.get_kind() for b in bundles]
    has_pkg = bool(component.get_pkgname() or c_pkgnames(component))
    if has_pkg or AppStream.BundleKind.PACKAGE in kinds:
        found.add("apt")
    if AppStream.BundleKind.FLATPAK in kinds:
        found.add("flatpak")
    origin = (component.get_origin() or "").lower()
    if "flathub" in origin or "flatpak" in origin:
        found.add("flatpak")
    return found


def c_pkgnames(component) -> list[str]:
    names = component.get_pkgnames() or []
    return [n for n in names if n]


def _iter_box(box):
    if box is None:
        return
    getter = getattr(box, "get_size", None)
    indexer = getattr(box, "index_safe", None)
    if getter is None or indexer is None:
        return
    size = getter()
    for index in range(size):
        item = indexer(index)
        if item is not None:
            yield item


def _icon_url(component) -> str:
    icon = component.get_icon_by_size(64, 64) or component.get_icon_by_size(128, 128)
    if icon is None:
        icons = component.get_icons() or []
        icon = icons[0] if icons else None
    if icon is None:
        return ""
    filename = icon.get_filename()
    if filename:
        return filename if filename.startswith("file:") else f"file://{filename}"
    url = icon.get_url() if hasattr(icon, "get_url") else ""
    return url or ""


def _screenshot_url(component) -> str:
    shots = component.get_screenshots_all() or []
    if not shots:
        return ""
    images = shots[0].get_images() or []
    if not images:
        return ""
    best = max(images, key=lambda image: (image.get_width() or 0))
    return best.get_url() or ""


def _developer_name(component) -> str:
    raw = ""
    getter = getattr(component, "get_developer_name", None)
    if callable(getter):
        raw = getter() or ""
    if not raw:
        developer = getattr(component, "get_developer", None)
        obj = developer() if callable(developer) else None
        if obj is not None:
            name_fn = getattr(obj, "get_name", None)
            raw = name_fn() if callable(name_fn) else ""
    name = plain_text(raw or "").strip()
    if not name:
        return ""
    skip = {"debian", "ubuntu", "linux", "unknown", "n/a", "none", "unix"}
    if name.lower() in skip:
        return ""
    return name


def _accent_from_id(app_id: str) -> str:
    palette = [
        "#3D8B8B",
        "#C4783A",
        "#4A7FB5",
        "#8B5E83",
        "#6A8F4E",
        "#B55A5A",
        "#3E6B8A",
        "#8A6B3E",
    ]
    return palette[sum(ord(ch) for ch in app_id) % len(palette)]


def _release_info(component) -> tuple[str, int]:
    box = None
    if hasattr(component, "get_releases_plain"):
        try:
            box = component.get_releases_plain()
        except Exception:
            box = None
    releases = []
    if box is None:
        pass
    elif hasattr(box, "get_size") and hasattr(box, "index_safe"):
        for index in range(box.get_size()):
            item = box.index_safe(index)
            if item is not None:
                releases.append(item)
    else:
        try:
            releases = list(box)
        except TypeError:
            releases = []
    if not releases:
        return "", 0
    best = None
    best_ts = -1
    for item in releases:
        ts = int(item.get_timestamp() or 0) if hasattr(item, "get_timestamp") else 0
        if ts >= best_ts:
            best_ts = ts
            best = item
    if best is None:
        return "", 0
    version = best.get_version() if hasattr(best, "get_version") else ""
    return version or "", int(best_ts if best_ts > 0 else 0)


def _desktop_ids(component) -> list[str]:
    found: list[str] = []
    app_id = component.get_id() or ""
    if app_id:
        found.append(app_id)
    try:
        launchables = component.get_launchables() or []
    except Exception:
        launchables = []
    try:
        iterator = list(launchables)
    except TypeError:
        iterator = []
        if hasattr(launchables, "get_size"):
            for index in range(launchables.get_size()):
                iterator.append(launchables.index_safe(index))
    for item in iterator:
        value = ""
        if hasattr(item, "get_value"):
            value = item.get_value() or ""
        elif isinstance(item, str):
            value = item
        if value:
            found.append(value)
    return found


def prefetch_appstream(backends: tuple[str, ...]) -> None:
    """Load requested backends once per process unless reset_pool() was called."""
    global _catalog_payload
    jobs_check()
    wanted = tuple(name for name in backends if name in {"apt", "flatpak"})
    if not wanted:
        return
    if _catalog_payload is not None and all(name in _catalog_payload for name in wanted):
        return
    fetched = _fetch_catalog_payload(wanted)
    if _catalog_payload is None:
        _catalog_payload = fetched
    else:
        _catalog_payload.update(fetched)


def load_appstream(backend: str) -> list[AppEntry]:
    jobs_check()
    prefetch_appstream((backend,))
    raw = (_catalog_payload or {}).get(backend) or []
    return [entry_from_dict(item) for item in raw]


def entry_from_dict(data: dict) -> AppEntry:
    payload = dict(data)
    extras = payload.pop("extras", []) or []
    allowed = {item.name for item in fields(AppEntry)}
    cleaned = {key: value for key, value in payload.items() if key in allowed and key != "extras"}
    entry = AppEntry(**cleaned)
    entry.extras = [entry_from_dict(item) for item in extras]
    return entry


def _fetch_catalog_payload(backends: tuple[str, ...]) -> dict[str, list[dict]]:
    jobs_check()
    ctx = multiprocessing.get_context("spawn")
    receiver, sender = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_appstream_child, args=(sender, tuple(backends)))
    register_mp(proc)
    proc.start()
    sender.close()
    try:
        while True:
            jobs_check()
            if receiver.poll(0.2):
                return _unpack_catalog(receiver)
            if not proc.is_alive():
                if receiver.poll(0.4):
                    return _unpack_catalog(receiver)
                raise RuntimeError(_APPSTREAM_CRASH)
    except CancelledError:
        proc.terminate()
        proc.join(timeout=1)
        if proc.is_alive():
            proc.kill()
        raise
    finally:
        unregister_mp(proc)
        try:
            receiver.close()
        except Exception:
            pass
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=1)
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=1)


def _unpack_catalog(receiver) -> dict[str, list[dict]]:
    try:
        status, payload = receiver.recv()
    except (EOFError, OSError) as exc:
        raise RuntimeError(_APPSTREAM_CRASH) from exc
    if status != "ok":
        raise RuntimeError(str(payload) or _APPSTREAM_MISSING)
    return payload


def _appstream_child(conn, backends: tuple[str, ...] = ("apt", "flatpak")) -> None:
    try:
        payload = {
            name: [asdict(entry) for entry in _load_appstream_gi(name)]
            for name in backends
        }
        conn.send(("ok", payload))
    except Exception as exc:  # noqa: BLE001
        try:
            conn.send(("err", str(exc) or _APPSTREAM_MISSING))
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _load_appstream_gi(backend: str) -> list[AppEntry]:
    global _pool, _loaded
    try:
        import gi

        gi.require_version("AppStream", "1.0")
        from gi.repository import AppStream
    except Exception as exc:
        raise RuntimeError(_APPSTREAM_MISSING) from exc

    if _pool is None:
        _pool = AppStream.Pool()
        try:
            _pool.load()
            _loaded = True
        except Exception as exc:
            _pool = None
            _loaded = False
            raise RuntimeError("Could not load the application catalog") from exc
    if not _loaded:
        _pool = None
        raise RuntimeError("Could not load the application catalog")

    entries: list[AppEntry] = []
    try:
        box = _pool.get_components_by_kind(AppStream.ComponentKind.DESKTOP_APP)
    except Exception as exc:
        raise RuntimeError("Could not load the application catalog") from exc
    for component in _iter_box(box):
        assigned = _bundle_backends(component)
        if backend not in assigned:
            continue
        app_id = component.get_id() or ""
        if not app_id:
            continue
        pkgnames = c_pkgnames(component)
        package = component.get_pkgname() or (pkgnames[0] if pkgnames else "")
        if backend == "flatpak":
            package = package or app_id
        elif not package:
            continue
        categories = list(component.get_categories() or [])
        version, release_ts = _release_info(component)
        entries.append(
            AppEntry(
                uid=f"{backend}:{app_id}",
                backend=backend,
                app_id=app_id.removesuffix(".desktop"),
                name=plain_text(component.get_name() or app_id) or app_id,
                summary=plain_text(component.get_summary() or ""),
                description=plain_text(component.get_description() or ""),
                package=package,
                version=version,
                icon=_icon_url(component),
                screenshot=_screenshot_url(component),
                categories=categories,
                developer=_developer_name(component),
                origin=(
                    "Flathub"
                    if backend == "flatpak" and not (component.get_origin() or "").strip()
                    else (component.get_origin() or "Ubuntu/Debian")
                ),
                accent=_accent_from_id(app_id),
                launch_id=app_id,
                release_ts=release_ts,
                desktop_ids=_desktop_ids(component),
            )
        )
    return entries
