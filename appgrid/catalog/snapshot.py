from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path

from appgrid.backends.base import AppEntry
from appgrid.catalog.appstream import entry_from_dict

VERSION = 1
_PATH = Path.home() / ".cache" / "appgrid" / "catalog.json"


def load_snapshot(flatpak_enabled: bool) -> list[AppEntry] | None:
    try:
        if not _PATH.is_file():
            return None
        payload = json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict) or payload.get("version") != VERSION:
        return None
    if bool(payload.get("flatpak")) != bool(flatpak_enabled):
        return None
    raw = payload.get("apps")
    if not isinstance(raw, list) or not raw:
        return None
    try:
        return [entry_from_dict(item) for item in raw if isinstance(item, dict)]
    except Exception:
        return None


def save_snapshot(apps: list[AppEntry], flatpak_enabled: bool) -> None:
    try:
        _PATH.parent.mkdir(parents=True, exist_ok=True)
        blob = {
            "version": VERSION,
            "flatpak": bool(flatpak_enabled),
            "saved": time.time(),
            "apps": [asdict(entry) for entry in apps],
        }
        _PATH.write_text(json.dumps(blob), encoding="utf-8")
    except Exception:
        pass
