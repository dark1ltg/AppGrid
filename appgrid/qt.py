"""Qt 6 Python bindings.

Ubuntu 24.10+ and Debian 13 ship split PySide6 packages; 24.04 / Debian 12
only have PyQt6. Try PySide6 first so newer releases use the split packages,
then fall back to PyQt6. Short Qt enum names are restored for PyQt6.
"""
from __future__ import annotations

BINDING = ""


def _flatten_enums(*types: type) -> None:
    for cls in types:
        for attr in dir(cls):
            obj = getattr(cls, attr, None)
            members = getattr(obj, "__members__", None)
            if not members:
                continue
            for name, value in members.items():
                if hasattr(cls, name):
                    continue
                try:
                    setattr(cls, name, value)
                except (TypeError, AttributeError):
                    pass


try:
    from PySide6.QtCore import (  # noqa: F401
        Property,
        QAbstractListModel,
        QMetaObject,
        QModelIndex,
        QObject,
        QRectF,
        QSettings,
        QSortFilterProxyModel,
        Qt,
        QThread,
        QTimer,
        QUrl,
        Signal,
        Slot,
    )
    from PySide6.QtGui import (  # noqa: F401
        QColor,
        QFont,
        QGuiApplication,
        QIcon,
        QImage,
        QLinearGradient,
        QPainter,
        QPen,
    )
    from PySide6.QtQml import QQmlApplicationEngine  # noqa: F401
    from PySide6.QtQuick import QQuickWindow  # noqa: F401

    BINDING = "PySide6"
except ImportError:
    from PyQt6.QtCore import (  # noqa: F401
        QAbstractListModel,
        QMetaObject,
        QModelIndex,
        QObject,
        QRectF,
        QSettings,
        QSortFilterProxyModel,
        Qt,
        QThread,
        QTimer,
        QUrl,
        pyqtProperty as Property,
        pyqtSignal as Signal,
        pyqtSlot as Slot,
    )
    from PyQt6.QtGui import (  # noqa: F401
        QColor,
        QFont,
        QGuiApplication,
        QIcon,
        QImage,
        QLinearGradient,
        QPainter,
        QPen,
    )
    from PyQt6.QtQml import QQmlApplicationEngine  # noqa: F401
    from PyQt6.QtQuick import QQuickWindow  # noqa: F401

    BINDING = "PyQt6"

_flatten_enums(Qt, QImage, QPainter, QFont)
