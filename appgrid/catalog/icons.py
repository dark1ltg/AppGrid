from __future__ import annotations

from pathlib import Path

from appgrid.backends.base import AppEntry

_ICON_ROOTS = (Path("/usr/share/icons"), Path("/usr/share/pixmaps"))
_SIZES = (
    "512x512",
    "256x256",
    "192x192",
    "128x128",
    "96x96",
    "64x64",
    "scalable",
    "48x48",
    "apps",
)
_SKIP = ("symbolic", "/mimetypes/", "/actions/", "/categories/", "/emblems/", "/places/", "/char-white/")
_FLATHUB_ICON = "https://dl.flathub.org/repo/appstream/x86_64/icons/128x128/{app_id}.png"
_FLATHUB_IDS = {
    "org.gnome.Rhythmbox": "org.gnome.Rhythmbox3",
    "org.gnome.gedit": "org.gnome.gedit",
}


def icon_uri(entry: AppEntry, *, fetch_remote: bool = False) -> str:
    """Best local theme icon for a catalog card, as a file: URL."""
    colorful = _find_icon(entry, colorful_only=True)
    if colorful is not None:
        return colorful.as_uri()
    if fetch_remote:
        remote = _flathub_icon(entry.app_id)
        if remote is not None:
            return remote.as_uri()
    any_icon = _find_icon(entry, colorful_only=False)
    if any_icon is not None:
        return any_icon.as_uri()
    return ""


def _candidates(entry: AppEntry) -> list[str]:
    names: list[str] = []
    for raw in (entry.app_id, entry.package, entry.name, entry.launch_id):
        text = (raw or "").strip()
        if not text:
            continue
        names.append(text)
        names.append(text.removesuffix(".desktop"))
        if "." in text:
            names.append(text.split(".")[-1])
        names.append(text.lower())
        names.append(text.replace(" ", "-").lower())
        names.append(text.replace(" ", "").lower())
    extra = {
        "firefox": ["firefox", "org.mozilla.Firefox"],
        "vlc": ["vlc", "org.videolan.VLC"],
        "gimp": ["gimp", "org.gimp.GIMP"],
        "libreoffice": ["libreoffice-startcenter", "libreoffice-writer", "org.libreoffice.LibreOffice"],
        "inkscape": ["inkscape", "org.inkscape.Inkscape"],
        "blender": ["blender", "org.blender.Blender"],
        "krita": ["krita", "org.kde.krita"],
        "calculator": ["org.gnome.Calculator", "gnome-calculator", "accessories-calculator"],
        "obs": ["com.obsproject.Studio", "obs"],
        "spotify": ["spotify", "spotify-client", "com.spotify.Client"],
        "code": ["com.visualstudio.code", "visual-studio-code", "vscode", "code"],
        "thunderbird": ["thunderbird", "org.mozilla.Thunderbird"],
        "text editor": ["org.gnome.gedit", "org.gnome.Gedit", "gedit"],
        "telegram": ["org.telegram.desktop", "telegram", "telegram-desktop"],
        "rhythmbox": ["org.gnome.Rhythmbox3", "org.gnome.Rhythmbox", "rhythmbox"],
        "builder": ["org.gnome.Builder", "gnome-builder"],
        "steam": ["steam", "com.valvesoftware.Steam"],
        "clocks": ["org.gnome.clocks", "gnome-clocks"],
    }
    key = (entry.name or "").lower()
    names.extend(extra.get(key, []))
    seen: set[str] = set()
    ordered: list[str] = []
    for name in names:
        if not name or name in seen:
            continue
        seen.add(name)
        ordered.append(name)
    return ordered


def _find_icon(entry: AppEntry, *, colorful_only: bool = False) -> Path | None:
    names = _candidates(entry)
    best: Path | None = None
    best_score = -1
    for root in _ICON_ROOTS:
        if not root.is_dir():
            continue
        for name in names:
            for path in _iter_named(root, name):
                score = _score(path)
                if colorful_only and (path.suffix.lower() != ".png" or score < 128):
                    continue
                if score > best_score:
                    best = path
                    best_score = score
    return best


def _cache_dir() -> Path:
    path = Path.home() / ".cache" / "appgrid" / "icons"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _flathub_icon(app_id: str) -> Path | None:
    flathub_id = _FLATHUB_IDS.get(app_id, app_id)
    dest = _cache_dir() / f"{flathub_id}.png"
    if dest.is_file() and dest.stat().st_size > 0:
        return dest
    import urllib.request

    url = _FLATHUB_ICON.format(app_id=flathub_id)
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            dest.write_bytes(response.read())
    except Exception:
        return None
    return dest if dest.is_file() and dest.stat().st_size > 0 else None


def _iter_named(root: Path, name: str) -> list[Path]:
    found: list[Path] = []
    if root.name == "pixmaps":
        for suffix in (".png", ".svg", ".xpm"):
            candidate = root / f"{name}{suffix}"
            if candidate.is_file():
                found.append(candidate)
        return found
    for theme in root.iterdir():
        if not theme.is_dir():
            continue
        for size in _SIZES:
            for folder in (theme / size / "apps", theme / "apps" / size, theme / size):
                for suffix in (".png", ".svg"):
                    candidate = folder / f"{name}{suffix}"
                    if candidate.is_file():
                        found.append(candidate)
    return found


def _score(path: Path) -> int:
    text = str(path).lower()
    if any(token in text for token in _SKIP):
        return -1
    score = 0
    if path.suffix == ".png":
        score += 20
    if "/apps/" in text:
        score += 10
    for size in (512, 256, 192, 128, 96, 64, 48):
        if f"{size}x{size}" in text or f"/{size}/" in text:
            score += size
            break
    else:
        if "scalable" in text:
            score += 200
        elif "/16/" in text or "16x16" in text:
            score += 16
    return score
