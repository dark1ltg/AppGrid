from __future__ import annotations

from pathlib import Path

_OS_RELEASE = Path("/etc/os-release")
_DEBIAN_LIKE = {"debian", "ubuntu"}
_KNOWN_IDS = _DEBIAN_LIKE | {
    "linuxmint",
    "lmde",
    "pop",
    "elementary",
    "zorin",
    "neon",
    "kubuntu",
    "xubuntu",
    "lubuntu",
    "ubuntu-mate",
    "ubuntustudio",
    "edubuntu",
    "linuxlite",
    "mx",
    "raspbian",
    "raspios",
    "kali",
    "pureos",
    "tails",
    "devuan",
    "bunsenlabs",
    "peppermint",
    "bodhi",
    "galliumos",
    "trisquel",
}


def os_release() -> dict[str, str]:
    info: dict[str, str] = {}
    if not _OS_RELEASE.is_file():
        return info
    for line in _OS_RELEASE.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        info[key] = value.strip().strip('"')
    return info


def distro_id() -> str:
    return os_release().get("ID", "").lower()


_STORE_LABELS = {
    "linuxmint": "Linux Mint",
    "lmde": "Linux Mint",
    "ubuntu": "Ubuntu",
    "debian": "Debian",
    "pop": "Pop!_OS",
    "elementary": "elementary OS",
    "zorin": "Zorin OS",
    "neon": "KDE neon",
    "kubuntu": "Kubuntu",
    "xubuntu": "Xubuntu",
    "lubuntu": "Lubuntu",
    "ubuntu-mate": "Ubuntu MATE",
    "ubuntustudio": "Ubuntu Studio",
    "edubuntu": "Edubuntu",
    "linuxlite": "Linux Lite",
    "mx": "MX Linux",
    "raspbian": "Raspberry Pi OS",
    "raspios": "Raspberry Pi OS",
    "kali": "Kali Linux",
    "pureos": "PureOS",
    "tails": "Tails",
    "devuan": "Devuan",
    "bunsenlabs": "BunsenLabs",
    "peppermint": "Peppermint OS",
    "bodhi": "Bodhi Linux",
    "galliumos": "GalliumOS",
    "trisquel": "Trisquel",
}


def native_store_label() -> str:
    """Short distro name for Settings copy, e.g. Linux Mint, Debian, Ubuntu."""
    ident = distro_id()
    if ident in _STORE_LABELS:
        return _STORE_LABELS[ident]
    name = os_release().get("NAME", "").strip()
    if name:
        return name.replace(" GNU/Linux", "").strip()
    return "this system"


def distro_name() -> str:
    info = os_release()
    return info.get("PRETTY_NAME") or info.get("NAME") or distro_id() or "this system"


def is_debian_family() -> bool:
    """True for Ubuntu, Debian, Mint, Pop!_OS, elementary, and other APT-based relatives."""
    info = os_release()
    ident = info.get("ID", "").lower()
    like = info.get("ID_LIKE", "").lower().split()
    if ident in _KNOWN_IDS:
        return True
    return any(token in _DEBIAN_LIKE for token in like)


UNSUPPORTED_MESSAGE = (
    "AppGrid is made for Ubuntu, Debian, Linux Mint, and similar systems. "
    f"{distro_name()} is not supported."
)
