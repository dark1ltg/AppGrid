from __future__ import annotations

import re
import time
from collections.abc import Callable

_reporter: Callable[[str], None] | None = None
_percent_reporter: Callable[[int], None] | None = None
_last_percent: int | None = None
_last_percent_at: float = 0.0
# Keep the last real % briefly so chatty non-percent lines do not flicker (#8).
_PERCENT_GRACE_S = 1.5

# Prefer pkcon / flatpak / apt progress phrasing over arbitrary "N%" tokens (#15).
# Avoid matching the fractional digit in values like "3.0%".
_PERCENT_PATTERNS = (
    re.compile(
        r"(?:progress|percentage|downloaded|downloading|installing|updating|removing|"
        r"transferring|receiving|deploying|extracting|configuring)"
        r"[^\d%]{0,80}(?<![.\d])(\d{1,3})\s*%",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?<![.\d])(\d{1,3})\s*%\s*(?:complete|done|downloaded|finished)",
        re.IGNORECASE,
    ),
    re.compile(r"\[\s*(?<![.\d])(\d{1,3})\s*%\s*]"),
)


def set_reporter(
    callback: Callable[[str], None] | None,
    percent_callback: Callable[[int], None] | None = None,
) -> None:
    """Wire status text and optional percent (-1 = unknown / indeterminate)."""
    global _reporter, _percent_reporter, _last_percent, _last_percent_at
    _reporter = callback
    _percent_reporter = percent_callback
    _last_percent = None
    _last_percent_at = 0.0


def extract_percent(message: str) -> int | None:
    """Return 0–100 if the line reports a real percentage, else None."""
    if not message:
        return None
    for pattern in _PERCENT_PATTERNS:
        matches = pattern.findall(message)
        if not matches:
            continue
        value = int(matches[-1])
        if 0 <= value <= 100:
            return value
    return None


def report_percent(value: int | None) -> None:
    """Publish percent. None or out-of-range clears to indeterminate (-1)."""
    global _last_percent, _last_percent_at
    if _percent_reporter is None:
        return
    if value is None:
        _last_percent = None
        _last_percent_at = 0.0
        _percent_reporter(-1)
        return
    if 0 <= int(value) <= 100:
        _percent_reporter(int(value))


def report(message: str) -> None:
    global _last_percent, _last_percent_at
    if _reporter is None or not message:
        return
    line = " ".join(message.split())
    if len(line) > 140:
        line = line[:137] + "…"
    _reporter(line)
    pct = extract_percent(line)
    now = time.monotonic()
    if pct is not None:
        _last_percent = pct
        _last_percent_at = now
        report_percent(pct)
        return
    # Non-percent line: keep last % for a short grace window (#8), then clear (#5).
    if _last_percent is not None and (now - _last_percent_at) < _PERCENT_GRACE_S:
        report_percent(_last_percent)
        return
    _last_percent = None
    _last_percent_at = 0.0
    report_percent(None)
