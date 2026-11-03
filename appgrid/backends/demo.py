from __future__ import annotations

from appgrid.backends.base import AppEntry, PackageBackend
from appgrid.catalog.demo_shots import demo_screenshot
from appgrid.catalog.icons import icon_uri

DEMO_APPS = [
    {
        "app_id": "org.mozilla.firefox",
        "name": "Firefox",
        "summary": "Fast, private web browser",
        "description": (
            "Firefox is a fast, private web browser from Mozilla. It blocks many trackers "
            "by default, supports tab containers, and lets you choose your own search engine. "
            "Sign in to sync bookmarks, passwords, and open tabs across your computers and phone.\n\n"
            "The library of extensions covers ad blocking, translation, password managers, and "
            "developer tools. Picture-in-picture, reader view, and HTTPS-first browsing are built in. "
            "Firefox is free software: Mozilla does not sell a profile of your browsing history, "
            "and you can change privacy controls without creating an account.\n\n"
            "Use it as your everyday browser on Ubuntu. Install from this page; remove it the "
            "same way when you no longer need it. Updates arrive through the normal system update path."
        ),
        "package": "firefox",
        "backend": "apt",
        "origin": "Ubuntu",
        "categories": ["Network", "WebBrowser"],
        "installed": True,
        "has_update": True,
        "version": "131.0",
        "developer": "Mozilla",
        "accent": "#E66000",
        "license": "MPL-2.0",
        "homepage": "https://www.mozilla.org/firefox/",
        "size_bytes": 91645542,
    },
    {
        "app_id": "org.videolan.VLC",
        "name": "VLC",
        "summary": "Play every media format",
        "description": "VLC plays video and audio with a small footprint and no codec hunt.",
        "package": "vlc",
        "backend": "apt",
        "origin": "Ubuntu",
        "categories": ["AudioVideo"],
        "installed": True,
        "accent": "#FF6A00",
        "version": "3.0.18",
        "license": "GPL-2.0-or-later",
        "homepage": "https://www.videolan.org/vlc/",
    },
    {
        "app_id": "org.gimp.GIMP",
        "name": "GIMP",
        "summary": "Image editor for photos and graphics",
        "description": "Layer-based image editor for retouching, composition, and original art.",
        "package": "gimp",
        "backend": "apt",
        "origin": "Ubuntu",
        "categories": ["Graphics"],
        "accent": "#5C5C5C",
    },
    {
        "app_id": "org.libreoffice.LibreOffice",
        "name": "LibreOffice",
        "summary": "Office suite for documents and spreadsheets",
        "description": "Writer, Calc, Impress, and Draw without a subscription.",
        "package": "libreoffice",
        "backend": "apt",
        "origin": "Ubuntu",
        "categories": ["Office"],
        "installed": True,
        "accent": "#18A303",
    },
    {
        "app_id": "org.inkscape.Inkscape",
        "name": "Inkscape",
        "summary": "Vector graphics editor",
        "description": "Create icons, diagrams, and illustrations with SVG.",
        "package": "inkscape",
        "backend": "apt",
        "origin": "Ubuntu",
        "categories": ["Graphics"],
        "accent": "#E0E0E0",
    },
    {
        "app_id": "org.blender.Blender",
        "name": "Blender",
        "summary": "3D modeling, animation, and rendering",
        "description": "A complete 3D pipeline from sculpting to video editing.",
        "package": "blender",
        "backend": "apt",
        "origin": "Ubuntu",
        "categories": ["Graphics"],
        "accent": "#E87D0D",
    },
    {
        "app_id": "org.kde.krita",
        "name": "Krita",
        "summary": "Digital painting for illustration",
        "description": "Brush engines, animation timeline, and HDR painting tools.",
        "package": "krita",
        "backend": "apt",
        "origin": "Ubuntu",
        "categories": ["Graphics"],
        "accent": "#3E76A4",
    },
    {
        "app_id": "org.gnome.Calculator",
        "name": "Calculator",
        "summary": "Desktop calculator with advanced modes",
        "description": "Basic, advanced, financial, and programming modes.",
        "package": "gnome-calculator",
        "backend": "apt",
        "origin": "Ubuntu",
        "categories": ["Utility"],
        "installed": True,
        "accent": "#3584E4",
    },
    {
        "app_id": "com.obsproject.Studio",
        "name": "OBS Studio",
        "summary": "Live streaming and screen recording",
        "description": "Capture scenes, mix audio, and stream to common platforms.",
        "package": "com.obsproject.Studio",
        "backend": "flatpak",
        "origin": "Flathub",
        "categories": ["AudioVideo"],
        "installed": True,
        "has_update": True,
        "version": "31.0",
        "accent": "#302E31",
    },
    {
        "app_id": "com.spotify.Client",
        "name": "Spotify",
        "summary": "Music and podcast streaming",
        "description": "Listen to playlists and podcasts from a Flatpak build.",
        "package": "com.spotify.Client",
        "backend": "flatpak",
        "origin": "Flathub",
        "categories": ["AudioVideo"],
        "accent": "#1DB954",
    },
    {
        "app_id": "com.visualstudio.code",
        "name": "VS Code",
        "summary": "Code editor with extensions",
        "description": "Edit, debug, and git without leaving the editor.",
        "package": "com.visualstudio.code",
        "backend": "flatpak",
        "origin": "Flathub",
        "categories": ["Development"],
        "accent": "#0078D7",
    },
    {
        "app_id": "org.mozilla.Thunderbird",
        "name": "Thunderbird",
        "summary": "Mail, calendar, and chat",
        "description": "Open-source email client with junk controls and calendaring.",
        "package": "thunderbird",
        "backend": "apt",
        "origin": "Ubuntu",
        "categories": ["Network"],
        "accent": "#0A84FF",
    },
    {
        "app_id": "org.gnome.gedit",
        "name": "Text Editor",
        "summary": "Simple notes and code snippets",
        "description": "Lightweight editor with syntax highlighting.",
        "package": "gedit",
        "backend": "apt",
        "origin": "Ubuntu",
        "categories": ["Utility"],
        "installed": True,
        "accent": "#F8E45C",
    },
    {
        "app_id": "org.telegram.desktop",
        "name": "Telegram",
        "summary": "Messaging with large chats and files",
        "description": "Cloud chats, channels, and bots in a desktop client.",
        "package": "org.telegram.desktop",
        "backend": "flatpak",
        "origin": "Flathub",
        "categories": ["Network"],
        "accent": "#2AABEE",
    },
    {
        "app_id": "org.gnome.Rhythmbox",
        "name": "Rhythmbox",
        "summary": "Music library and player",
        "description": "Play local files, podcasts, and internet radio.",
        "package": "rhythmbox",
        "backend": "apt",
        "origin": "Ubuntu",
        "categories": ["AudioVideo"],
        "accent": "#E01B24",
        "desktop_ids": ["org.gnome.Rhythmbox3"],
    },
    {
        "app_id": "org.gnome.Builder",
        "name": "Builder",
        "summary": "IDE for GNOME apps",
        "description": "Write GTK applications with integrated building and debugging.",
        "package": "gnome-builder",
        "backend": "apt",
        "origin": "Ubuntu",
        "categories": ["Development"],
        "accent": "#62A0EA",
    },
    {
        "app_id": "com.valvesoftware.Steam",
        "name": "Steam",
        "summary": "Games, workshop, and friends",
        "description": "Install and run games from Valve's store as a Flatpak.",
        "package": "com.valvesoftware.Steam",
        "backend": "flatpak",
        "origin": "Flathub",
        "categories": ["Game"],
        "accent": "#1B2838",
    },
    {
        "app_id": "org.gnome.clocks",
        "name": "Clocks",
        "summary": "World clocks, timer, and stopwatch",
        "description": "Keep time zones and timers on the desktop.",
        "package": "gnome-clocks",
        "backend": "apt",
        "origin": "Ubuntu",
        "categories": ["Utility"],
        "accent": "#1C71D8",
    },
    {
        "app_id": "org.mozilla.firefox",
        "name": "Firefox",
        "summary": "Fast, private web browser",
        "description": (
            "Firefox is a fast, private web browser from Mozilla. It blocks many trackers "
            "by default, supports tab containers, and lets you choose your own search engine. "
            "Sign in to sync bookmarks, passwords, and open tabs across your computers and phone.\n\n"
            "The library of extensions covers ad blocking, translation, password managers, and "
            "developer tools. Picture-in-picture, reader view, and HTTPS-first browsing are built in. "
            "Firefox is free software: Mozilla does not sell a profile of your browsing history, "
            "and you can change privacy controls without creating an account.\n\n"
            "Use it as your everyday browser on Ubuntu. Install from this page; remove it the "
            "same way when you no longer need it. Updates arrive through the normal system update path."
        ),
        "package": "org.mozilla.firefox",
        "backend": "flatpak",
        "origin": "Flathub",
        "categories": ["Network", "WebBrowser"],
        "version": "133.0.3",
        "developer": "Mozilla",
        "accent": "#E66000",
    },
    {
        "app_id": "org.videolan.VLC",
        "name": "VLC",
        "summary": "Play every media format",
        "description": "The Flathub build of VLC.",
        "package": "org.videolan.VLC",
        "backend": "flatpak",
        "origin": "Flathub",
        "categories": ["AudioVideo"],
        "version": "3.0.21",
        "accent": "#FF6A00",
    },
    {
        "app_id": "org.gimp.GIMP",
        "name": "GIMP",
        "summary": "Image editor for photos and graphics",
        "description": "The Flathub build of GIMP.",
        "package": "org.gimp.GIMP",
        "backend": "flatpak",
        "origin": "Flathub",
        "categories": ["Graphics"],
        "version": "3.0.2",
        "accent": "#5C5C5C",
    },
    {
        "app_id": "org.libreoffice.LibreOffice",
        "name": "LibreOffice",
        "summary": "Office suite for documents and spreadsheets",
        "description": "The Flathub build of LibreOffice.",
        "package": "org.libreoffice.LibreOffice",
        "backend": "flatpak",
        "origin": "Flathub",
        "categories": ["Office"],
        "version": "24.8.2",
        "accent": "#18A303",
    },
]


class DemoBackend(PackageBackend):
    """Curated filler catalog used when APT metadata is missing, and for screenshots."""

    name = "demo"
    label = "Demo"

    def __init__(self, only_backend: str | None = None) -> None:
        self.only_backend = only_backend
        self._state = {(item["backend"], item["app_id"]): dict(item) for item in DEMO_APPS}

    def available(self) -> bool:
        return True

    def refresh(self) -> list[AppEntry]:
        entries: list[AppEntry] = []
        for item in self._state.values():
            backend = item["backend"]
            if self.only_backend and backend != self.only_backend:
                continue
            entry = AppEntry(
                uid=f"{backend}:{item['app_id']}",
                backend=backend,
                app_id=item["app_id"],
                name=item["name"],
                summary=item["summary"],
                description=item["description"],
                package=item["package"],
                version=item.get("version", ""),
                installed=bool(item.get("installed")),
                has_update=bool(item.get("has_update")),
                categories=list(item.get("categories") or []),
                developer=item.get("developer", ""),
                origin=item["origin"],
                accent=item["accent"],
                desktop_ids=list(item.get("desktop_ids") or []),
                license=item.get("license", ""),
                homepage=item.get("homepage", ""),
                size_bytes=int(item.get("size_bytes") or 0),
            )
            entry.self_installed = bool(entry.installed)
            entry.self_has_update = bool(entry.has_update)
            entry.icon = icon_uri(entry, fetch_remote=True)
            entry.screenshot = demo_screenshot(item["app_id"])
            entries.append(entry)
        return entries

    def install(self, entry: AppEntry) -> None:
        self._state[(entry.backend, entry.app_id)]["installed"] = True
        self._state[(entry.backend, entry.app_id)]["has_update"] = False

    def remove(self, entry: AppEntry) -> None:
        self._state[(entry.backend, entry.app_id)]["installed"] = False
        self._state[(entry.backend, entry.app_id)]["has_update"] = False

    def update_one(self, entry: AppEntry) -> None:
        self._state[(entry.backend, entry.app_id)]["has_update"] = False

    def update_all(self) -> None:
        for item in self._state.values():
            item["has_update"] = False
