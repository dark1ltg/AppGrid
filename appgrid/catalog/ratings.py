from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

from appgrid.backends.base import AppEntry
from appgrid.services.jobs import check as jobs_check

_URL = "https://odrs.gnome.org/1.0/reviews/api/ratings"
_CACHE = Path.home() / ".cache" / "appgrid" / "odrs-averages.json"
_TTL = 60 * 60 * 24
_table: dict[str, float] | None = None


def apply_ratings(apps: list[AppEntry]) -> None:
    """Attach ODRS star averages. Missing or failed ratings stay hidden."""
    table = _ratings_table()
    if not table:
        return
    for entry in apps:
        entry.rating = _lookup(table, entry)


def average_from_stars(blob: dict) -> float:
    counts = [int(blob.get(f"star{index}") or 0) for index in range(6)]
    total = int(blob.get("total") or 0) or sum(counts)
    if total <= 0:
        return 0.0
    points = sum(index * counts[index] for index in range(1, 6))
    return round(points / total, 1)


def _ratings_table() -> dict[str, float]:
    global _table
    if _table is not None:
        return _table
    jobs_check()
    cached = _read_cache()
    if cached is not None:
        _table = cached
        return _table
    raw = _fetch()
    _table = _averages(raw) if raw else {}
    if _table:
        _write_cache(_table)
    return _table


def _lookup(table: dict[str, float], entry: AppEntry) -> float:
    best = 0.0
    for raw in (entry.app_id, entry.launch_id, *entry.desktop_ids):
        key = (raw or "").lower().removesuffix(".desktop").strip()
        if not key:
            continue
        value = table.get(key) or table.get(f"{key}.desktop")
        if value and value > best:
            best = value
    return best


def _averages(raw: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    for key, blob in raw.items():
        if not isinstance(blob, dict):
            continue
        avg = average_from_stars(blob)
        if avg <= 0:
            continue
        folded = str(key).lower().removesuffix(".desktop")
        current = out.get(folded, 0.0)
        if avg > current:
            out[folded] = avg
    return out


def _read_cache() -> dict[str, float] | None:
    try:
        if not _CACHE.is_file():
            return None
        if time.time() - _CACHE.stat().st_mtime > _TTL:
            return None
        payload = json.loads(_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return {str(key): float(value) for key, value in payload.items() if value}


def _write_cache(table: dict[str, float]) -> None:
    try:
        _CACHE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE.write_text(json.dumps(table), encoding="utf-8")
    except Exception:
        pass


def _fetch() -> dict | None:
    jobs_check()
    try:
        request = urllib.request.Request(_URL, headers={"User-Agent": "AppGrid/1.0"})
        with urllib.request.urlopen(request, timeout=2.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    jobs_check()
    return payload if isinstance(payload, dict) else None
