from __future__ import annotations

from collections.abc import Callable

_reporter: Callable[[str], None] | None = None


def set_reporter(callback: Callable[[str], None] | None) -> None:
    global _reporter
    _reporter = callback


def report(message: str) -> None:
    if _reporter is None or not message:
        return
    line = " ".join(message.split())
    if len(line) > 140:
        line = line[:137] + "…"
    _reporter(line)
