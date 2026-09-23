from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from appgrid.services.jobs import check as jobs_check

_FLATHUB_APPSTREAM = "https://flathub.org/api/v2/appstream/{app_id}"
_IDS = {
    "org.gnome.Rhythmbox": "org.gnome.Rhythmbox3",
    "org.gnome.gedit": "org.gnome.gedit",
}


def cache_dir() -> Path:
    path = Path.home() / ".cache" / "appgrid" / "shots"
    path.mkdir(parents=True, exist_ok=True)
    return path


def demo_screenshot(app_id: str) -> str:
    """Local copy of a real Flathub screenshot for filler catalog tiles."""
    flathub_id = _IDS.get(app_id, app_id)
    dest = cache_dir() / f"{_safe(flathub_id)}.png"
    if dest.is_file() and dest.stat().st_size > 800:
        return dest.as_uri()
    jobs_check()
    url = _first_screenshot_url(flathub_id)
    if not url:
        return ""
    jobs_check()
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "AppGrid/1.0"})
        with urllib.request.urlopen(request, timeout=20) as response:
            dest.write_bytes(response.read())
    except Exception:
        return ""
    if dest.is_file() and dest.stat().st_size > 800:
        return dest.as_uri()
    return ""


def _first_screenshot_url(app_id: str) -> str:
    request = urllib.request.Request(
        _FLATHUB_APPSTREAM.format(app_id=app_id),
        headers={"User-Agent": "AppGrid/1.0", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        return ""
    for shot in data.get("screenshots") or []:
        picked = _best_size(shot.get("sizes") or [])
        if picked:
            return picked
        for key in ("src", "url", "imgDesktopUrl"):
            value = shot.get(key) or ""
            if isinstance(value, str) and value.startswith("http"):
                return value
    return ""


def _best_size(sizes: list) -> str:
    best = ""
    best_delta = 10_000
    for item in sizes:
        if not isinstance(item, dict):
            continue
        src = item.get("src") or item.get("url") or ""
        if not src:
            continue
        width = int(item.get("width") or 0)
        delta = abs(width - 752) if width else 400
        if delta < best_delta:
            best = src
            best_delta = delta
    return best


def _safe(app_id: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in app_id)
