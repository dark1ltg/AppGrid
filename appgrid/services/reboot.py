from __future__ import annotations

from pathlib import Path

_REBOOT_FLAGS = (
    Path("/run/reboot-required"),
    Path("/var/run/reboot-required"),
)


def reboot_required() -> bool:
    """True when the distro marked a restart after library/kernel updates."""
    return any(path.exists() for path in _REBOOT_FLAGS)
