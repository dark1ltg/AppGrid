from __future__ import annotations

from appgrid.backends.base import AppEntry

# Same buckets as the 2013 App Grid, plus Internet so browsers are not only in All.
GROUPS: tuple[tuple[str, str, frozenset[str]], ...] = (
    ("arts", "Arts", frozenset({"graphics", "art", "photography", "audiovideo", "audio", "video", "tv", "tuner"})),
    ("games", "Games", frozenset({"game", "games", "actiongame", "adventuregame", "arcadegame", "blocksgame", "boardgame", "cardgame", "kidsgame", "logicgame", "roleplaying", "shooter", "simulation", "sportsgame", "strategygame"})),
    ("productivity", "Productivity", frozenset({"office", "productivity", "wordprocessor", "spreadsheet", "presentation", "chart", "database", "finance", "projectmanagement", "email", "calendar", "contactmanagement"})),
    ("programming", "Programming", frozenset({"development", "ide", "debugger", "building", "revisioncontrol", "guidesigner", "webdevelopment"})),
    ("sciences", "Sciences", frozenset({"science", "education", "math", "numericalanalysis", "astronomy", "biology", "chemistry", "geology", "medicalsoftware", "physics"})),
    ("internet", "Internet", frozenset({"network", "webbrowser", "chat", "instantmessaging", "ircclient", "filetransfer", "p2p", "news", "hamradio"})),
    ("system", "System", frozenset({"system", "settings", "utility", "security", "packagemanager", "monitor", "filemanager", "terminalemulator", "accessibility"})),
)


def group_id(entry: AppEntry) -> str:
    tags = {item.lower() for item in (entry.categories or []) if item}
    for ident, _label, needles in GROUPS:
        if tags & needles:
            return ident
    return ""


# More specific than the ticker bucket, used on the detail page only.
_DETAIL_TAGS: tuple[tuple[str, str], ...] = (
    ("webbrowser", "Web Browser"),
    ("email", "Email"),
    ("ide", "IDE"),
    ("filemanager", "Files"),
    ("terminalemulator", "Terminal"),
    ("chat", "Chat"),
    ("instantmessaging", "Chat"),
    ("ircclient", "Chat"),
    ("wordprocessor", "Productivity"),
    ("spreadsheet", "Productivity"),
    ("presentation", "Productivity"),
    ("audiovideo", "Arts"),
    ("audio", "Arts"),
    ("video", "Arts"),
    ("graphics", "Arts"),
    ("photography", "Arts"),
    ("game", "Games"),
    ("games", "Games"),
)


def detail_category(entry: AppEntry) -> str:
    """One friendly type label, or empty if nothing maps. Never invent Other."""
    tags = {item.lower() for item in (entry.categories or []) if item}
    for tag, label in _DETAIL_TAGS:
        if tag in tags:
            return label
    ident = group_id(entry)
    for group, label, _needles in GROUPS:
        if group == ident:
            return label
    return ""


def matches(entry: AppEntry, category: str) -> bool:
    if not category:
        return True
    return group_id(entry) == category


def present(entries: list[AppEntry]) -> list[dict[str, str]]:
    seen = {group_id(entry) for entry in entries}
    return [{"id": ident, "label": label} for ident, label, _needles in GROUPS if ident in seen]
