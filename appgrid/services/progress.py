from __future__ import annotations

import re
from collections.abc import Callable

_reporter: Callable[[str], None] | None = None
_percent_reporter: Callable[[int], None] | None = None

# Last 0–100% in a line (pkcon / flatpak / apt-style progress).
# Avoid matching the fractional digit in values like "3.0%".
_PERCENT = re.compile(r"(?<![.\d])(\d{1,3})\s*%")


def set_reporter(
    callback: Callable[[str], None] | None,
    percent_callback: Callable[[int], None] | None = None,
) -> None:
    """Wire status text and optional percent (-1 = unknown / indeterminate)."""
    global _reporter, _percent_reporter
    _reporter = callback
    _percent_reporter = percent_callback


def extract_percent(message: str) -> int | None:
    """Return 0–100 if the line reports a real percentage, else None."""
    if not message:
        return None
    matches = _PERCENT.findall(message)
    if not matches:
        return None
    value = int(matches[-1])
    if 0 <= value <= 100:
        return value
    return None


def report_percent(value: int | None) -> None:
    """Publish percent. None or out-of-range clears to indeterminate (-1)."""
    if _percent_reporter is None:
        return
    if value is None:
        _percent_reporter(-1)
        return
    if 0 <= int(value) <= 100:
        _percent_reporter(int(value))


def report(message: str) -> None:
    if _reporter is None or not message:
        return
    line = " ".join(message.split())
    if len(line) > 140:
        line = line[:137] + "…"
    _reporter(line)
    pct = extract_percent(line)
    if pct is not None:
        report_percent(pct)
