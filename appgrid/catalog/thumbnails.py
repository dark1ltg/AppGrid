from __future__ import annotations

from pathlib import Path

from appgrid.qt import QColor, QFont, QImage, QLinearGradient, QPainter, QPen, QRectF, Qt

from appgrid.backends.base import AppEntry

WIDTH = 640
HEIGHT = 360


def cache_dir() -> Path:
    path = Path.home() / ".cache" / "appgrid" / "thumbs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def preview_kind(entry: AppEntry) -> str:
    blob = " ".join([entry.name, entry.app_id, *entry.categories]).lower()
    if any(token in blob for token in ("firefox", "browser", "network", "web")):
        return "browser"
    if any(token in blob for token in ("vlc", "obs", "rhythmbox", "spotify", "audiovideo", "video", "music")):
        return "media"
    if any(token in blob for token in ("gimp", "inkscape", "krita", "blender", "graphics")):
        return "graphics"
    if any(token in blob for token in ("libreoffice", "office", "writer")):
        return "office"
    if any(token in blob for token in ("telegram", "chat", "mail", "thunderbird")):
        return "chat"
    if any(token in blob for token in ("code", "builder", "development", "ide")):
        return "code"
    if any(token in blob for token in ("steam", "game", "retro")):
        return "game"
    if any(token in blob for token in ("clock", "calc", "utility")):
        return "utility"
    return "generic"


def ensure_thumbnail(entry: AppEntry) -> str:
    """Return a file: or remote URL suitable for the grid preview."""
    if entry.screenshot and entry.screenshot.startswith(("http://", "https://", "file:")):
        return entry.screenshot
    if entry.screenshot and Path(entry.screenshot).exists():
        return Path(entry.screenshot).as_uri()
    path = cache_dir() / f"{_safe(entry.uid)}.png"
    if not path.exists():
        render_preview(entry, path)
    return path.as_uri()


def _safe(uid: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in uid)


def render_preview(entry: AppEntry, path: Path) -> None:
    image = QImage(WIDTH, HEIGHT, QImage.Format_ARGB32_Premultiplied)
    image.fill(QColor("#12141A"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.TextAntialiasing)
    accent = QColor(entry.accent or "#3D8B8B")
    _window_chrome(painter, entry, accent)
    kind = preview_kind(entry)
    body = QRectF(18, 42, WIDTH - 36, HEIGHT - 60)
    {
        "browser": _paint_browser,
        "media": _paint_media,
        "graphics": _paint_graphics,
        "office": _paint_office,
        "chat": _paint_chat,
        "code": _paint_code,
        "game": _paint_game,
        "utility": _paint_utility,
        "generic": _paint_generic,
    }[kind](painter, body, entry, accent)
    _draw_icon_if_any(painter, entry)
    painter.end()
    image.save(str(path), "PNG")


def _window_chrome(painter: QPainter, entry: AppEntry, accent: QColor) -> None:
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#1E2430"))
    painter.drawRoundedRect(QRectF(8, 8, WIDTH - 16, HEIGHT - 16), 14, 14)
    painter.setBrush(QColor("#2A3142"))
    painter.drawRoundedRect(QRectF(8, 8, WIDTH - 16, 32), 14, 14)
    painter.drawRect(QRectF(8, 24, WIDTH - 16, 16))
    for index, color in enumerate(("#FF5F56", "#FFBD2E", "#27C93F")):
        painter.setBrush(QColor(color))
        painter.drawEllipse(22 + index * 16, 18, 10, 10)
    painter.setPen(QColor("#D5DEEA"))
    painter.setFont(QFont("Sans", 10))
    painter.drawText(QRectF(80, 10, WIDTH - 160, 24), Qt.AlignVCenter, entry.name)
    painter.setPen(Qt.NoPen)
    painter.setBrush(accent)
    painter.drawRect(QRectF(8, 40, WIDTH - 16, 3))


def _paint_browser(painter: QPainter, body: QRectF, entry: AppEntry, accent: QColor) -> None:
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#151922"))
    painter.drawRoundedRect(body.adjusted(0, 0, 0, -8), 8, 8)
    tab_y = body.top() + 6
    for index, label in enumerate(("Home", "Docs", entry.name[:10])):
        painter.setBrush(accent if index == 2 else QColor("#243044"))
        painter.drawRoundedRect(QRectF(body.left() + 10 + index * 92, tab_y, 86, 22), 6, 6)
        painter.setPen(QColor("#F2F6FB") if index == 2 else QColor("#8A97A8"))
        painter.setFont(QFont("Sans", 8))
        painter.drawText(QRectF(body.left() + 10 + index * 92, tab_y, 86, 22), Qt.AlignCenter, label)
        painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#0F131A"))
    painter.drawRoundedRect(QRectF(body.left() + 10, body.top() + 34, body.width() - 20, 22), 8, 8)
    painter.setPen(QColor("#7E8B9A"))
    painter.setFont(QFont("Sans", 8))
    painter.drawText(
        QRectF(body.left() + 20, body.top() + 34, body.width() - 40, 22),
        Qt.AlignVCenter,
        f"https://{entry.app_id.split('.')[-1].lower()}.example",
    )
    content = QRectF(body.left() + 10, body.top() + 64, body.width() - 20, body.height() - 78)
    gradient = QLinearGradient(content.topLeft(), content.bottomRight())
    gradient.setColorAt(0.0, accent.lighter(135))
    gradient.setColorAt(1.0, QColor("#10141C"))
    painter.setPen(Qt.NoPen)
    painter.setBrush(gradient)
    painter.drawRoundedRect(content, 8, 8)
    painter.setPen(QColor("#F2F6FB"))
    painter.setFont(QFont("Sans", 16, QFont.Bold))
    painter.drawText(content.adjusted(16, 12, -16, 0), Qt.AlignLeft | Qt.AlignTop, entry.name)
    painter.setFont(QFont("Sans", 9))
    painter.setPen(QColor("#D5DEEA"))
    painter.drawText(content.adjusted(16, 44, -16, -12), Qt.TextWordWrap, entry.summary)


def _paint_media(painter: QPainter, body: QRectF, entry: AppEntry, accent: QColor) -> None:
    stage = body.adjusted(0, 0, 0, -42)
    gradient = QLinearGradient(stage.topLeft(), stage.bottomRight())
    gradient.setColorAt(0.0, QColor("#0B0C10"))
    gradient.setColorAt(1.0, accent.darker(180))
    painter.setPen(Qt.NoPen)
    painter.setBrush(gradient)
    painter.drawRoundedRect(stage, 8, 8)
    painter.setBrush(accent)
    painter.drawEllipse(QRectF(body.center().x() - 22, body.center().y() - 40, 44, 44))
    painter.setPen(QColor("#10141C"))
    painter.setFont(QFont("Sans", 16, QFont.Bold))
    painter.drawText(QRectF(body.center().x() - 22, body.center().y() - 40, 44, 44), Qt.AlignCenter, "▶")
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#243044"))
    painter.drawRoundedRect(QRectF(body.left(), body.bottom() - 36, body.width(), 28), 6, 6)
    painter.setBrush(accent)
    painter.drawRoundedRect(QRectF(body.left() + 12, body.bottom() - 24, body.width() * 0.55, 6), 3, 6)


def _paint_graphics(painter: QPainter, body: QRectF, entry: AppEntry, accent: QColor) -> None:
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#2A3142"))
    painter.drawRoundedRect(QRectF(body.left(), body.top(), 44, body.height() - 8), 8, 8)
    for index, color in enumerate((accent, QColor("#E8E8E8"), QColor("#4A90D9"), QColor("#E05A5A"), QColor("#F2C14E"))):
        painter.setBrush(color)
        painter.drawRoundedRect(QRectF(body.left() + 8, body.top() + 12 + index * 28, 28, 22), 4, 4)
    canvas = body.adjusted(52, 0, 0, -8)
    painter.setBrush(QColor("#F4F1EA"))
    painter.drawRoundedRect(canvas, 8, 8)
    painter.setBrush(accent)
    painter.drawEllipse(QRectF(canvas.left() + 36, canvas.top() + 28, 120, 120))
    painter.setBrush(accent.lighter(140))
    painter.drawRoundedRect(QRectF(canvas.right() - 160, canvas.top() + 48, 110, 72), 10, 10)
    painter.setPen(QColor("#3A3A3A"))
    painter.setFont(QFont("Sans", 11, QFont.Bold))
    painter.drawText(canvas.adjusted(16, canvas.height() - 36, -16, -8), Qt.AlignLeft, entry.name)


def _paint_office(painter: QPainter, body: QRectF, entry: AppEntry, accent: QColor) -> None:
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#F7F4EE"))
    painter.drawRoundedRect(body.adjusted(0, 0, 0, -8), 8, 8)
    painter.setBrush(accent)
    painter.drawRect(QRectF(body.left(), body.top(), body.width(), 8))
    painter.setPen(QColor("#2A3142"))
    painter.setFont(QFont("Sans", 14, QFont.Bold))
    painter.drawText(body.adjusted(20, 20, -20, 0), Qt.AlignLeft | Qt.AlignTop, "Quarterly notes")
    painter.setPen(QPen(QColor("#C9C2B4"), 2))
    for index in range(7):
        y = body.top() + 58 + index * 22
        painter.drawLine(int(body.left() + 20), int(y), int(body.right() - 28), int(y))
    painter.setPen(Qt.NoPen)
    painter.setBrush(accent)
    painter.setOpacity(0.35)
    painter.drawRoundedRect(QRectF(body.left() + 20, body.top() + 96, 180, 18), 3, 3)
    painter.setOpacity(1.0)


def _paint_chat(painter: QPainter, body: QRectF, entry: AppEntry, accent: QColor) -> None:
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#141A24"))
    painter.drawRoundedRect(body.adjusted(0, 0, 0, -8), 8, 8)
    bubbles = [
        (False, "Are you shipping tonight?"),
        (True, "Yes — grid thumbs are in."),
        (False, "Looks like a real store."),
        (True, entry.summary[:42] or "On it."),
    ]
    y = body.top() + 16
    for mine, text in bubbles:
        width = min(280, 18 * max(8, len(text) // 2))
        x = body.right() - width - 18 if mine else body.left() + 18
        painter.setBrush(accent if mine else QColor("#2A3344"))
        painter.drawRoundedRect(QRectF(x, y, width, 34), 12, 12)
        painter.setPen(QColor("#F2F6FB"))
        painter.setFont(QFont("Sans", 8))
        painter.drawText(QRectF(x + 8, y, width - 16, 34), Qt.AlignVCenter, text)
        painter.setPen(Qt.NoPen)
        y += 42


def _paint_code(painter: QPainter, body: QRectF, entry: AppEntry, accent: QColor) -> None:
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#0E1218"))
    painter.drawRoundedRect(body.adjusted(0, 0, 0, -8), 8, 8)
    painter.setBrush(QColor("#1A1F29"))
    painter.drawRoundedRect(QRectF(body.left(), body.top(), 92, body.height() - 8), 8, 8)
    painter.setPen(QColor("#8A97A8"))
    painter.setFont(QFont("Monospace", 8))
    painter.drawText(QRectF(body.left() + 10, body.top() + 12, 80, 20), "src/")
    painter.setPen(accent)
    painter.drawText(QRectF(body.left() + 10, body.top() + 32, 80, 20), "main.py")
    lines = [
        ("def", "launch():"),
        ("    ", "grid.show()"),
        ("    ", "return store"),
        ("# ", entry.name),
        ("apps", " = catalog()"),
    ]
    y = body.top() + 16
    for prefix, rest in lines:
        painter.setPen(accent if prefix.strip() in {"def", "#"} else QColor("#D5DEEA"))
        painter.drawText(QRectF(body.left() + 108, y, body.width() - 130, 20), prefix + rest)
        y += 22


def _paint_game(painter: QPainter, body: QRectF, entry: AppEntry, accent: QColor) -> None:
    gradient = QLinearGradient(body.topLeft(), body.bottomRight())
    gradient.setColorAt(0.0, QColor("#0B1A24"))
    gradient.setColorAt(1.0, accent)
    painter.setPen(Qt.NoPen)
    painter.setBrush(gradient)
    painter.drawRoundedRect(body.adjusted(0, 0, 0, -8), 8, 8)
    painter.setBrush(QColor(0, 0, 0, 90))
    painter.drawRoundedRect(QRectF(body.left() + 24, body.bottom() - 88, 220, 54), 8, 8)
    painter.setPen(QColor("#F2F6FB"))
    painter.setFont(QFont("Sans", 16, QFont.Bold))
    painter.drawText(QRectF(body.left() + 36, body.bottom() - 86, 200, 28), entry.name)
    painter.setFont(QFont("Sans", 8))
    painter.setPen(QColor("#D5DEEA"))
    painter.drawText(QRectF(body.left() + 36, body.bottom() - 58, 200, 20), "Play  ·  Library  ·  Store")


def _paint_utility(painter: QPainter, body: QRectF, entry: AppEntry, accent: QColor) -> None:
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#1A2230"))
    painter.drawRoundedRect(body.adjusted(0, 0, 0, -8), 8, 8)
    painter.setBrush(accent)
    painter.drawEllipse(QRectF(body.center().x() - 70, body.center().y() - 78, 140, 140))
    painter.setBrush(QColor("#1A2230"))
    painter.drawEllipse(QRectF(body.center().x() - 52, body.center().y() - 60, 104, 104))
    painter.setPen(QPen(accent, 8))
    painter.drawLine(
        int(body.center().x()),
        int(body.center().y()),
        int(body.center().x() + 28),
        int(body.center().y() - 36),
    )
    painter.setPen(QColor("#F2F6FB"))
    painter.setFont(QFont("Sans", 12, QFont.Bold))
    painter.drawText(QRectF(body.left(), body.bottom() - 40, body.width(), 24), Qt.AlignHCenter, entry.name)


def _paint_generic(painter: QPainter, body: QRectF, entry: AppEntry, accent: QColor) -> None:
    gradient = QLinearGradient(body.topLeft(), body.bottomRight())
    gradient.setColorAt(0.0, accent.lighter(130))
    gradient.setColorAt(1.0, accent.darker(130))
    painter.setPen(Qt.NoPen)
    painter.setBrush(gradient)
    painter.drawRoundedRect(body.adjusted(0, 0, 0, -8), 8, 8)
    painter.setPen(QColor("#F2F6FB"))
    painter.setFont(QFont("Sans", 22, QFont.Bold))
    painter.drawText(body.adjusted(20, 24, -20, 0), Qt.AlignLeft | Qt.AlignTop, entry.name)
    painter.setFont(QFont("Sans", 10))
    painter.drawText(body.adjusted(20, 64, -20, -20), Qt.TextWordWrap, entry.summary)


def _draw_icon_if_any(painter: QPainter, entry: AppEntry) -> None:
    source = entry.icon.removeprefix("file://") if entry.icon else ""
    if not source or not Path(source).exists():
        return
    icon = QImage(source)
    if icon.isNull():
        return
    scaled = icon.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    painter.drawImage(WIDTH - 70, HEIGHT - 70, scaled)
