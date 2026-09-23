from __future__ import annotations

import re

from appgrid.backends.base import AppEntry

_TOKEN = re.compile(r"^[A-Za-z0-9_+-]+$")


def looks_like_appstream_id(name: str) -> bool:
    """True for reverse-DNS ids such as org.mozilla.firefox, not Debian package names."""
    parts = [part for part in (name or "").split(".") if part]
    if len(parts) < 3:
        return False
    if not parts[0].isalpha():
        return False
    return all(_TOKEN.match(part) for part in parts)


def debian_package_name(entry: AppEntry) -> str:
    pkg = (entry.package or "").strip().split(":")[0]
    if not pkg or looks_like_appstream_id(pkg):
        raise RuntimeError(
            f"AppGrid does not know the Ubuntu package name for {entry.name}."
        )
    return pkg
