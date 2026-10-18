from __future__ import annotations

import os
import argparse
import sys
from pathlib import Path

from appgrid.qt import (
    QGuiApplication,
    QIcon,
    QMetaObject,
    QObject,
    QQmlApplicationEngine,
    QQuickWindow,
    Qt,
    QTimer,
    QUrl,
)

from appgrid.controller import AppController

QML_DIR = Path(__file__).resolve().parent / "qml"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AppGrid software store")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Use filler APT/Flatpak catalog (also implied by --screenshot)",
    )
    parser.add_argument(
        "--screenshot",
        metavar="PATH",
        help="Write a window screenshot and exit",
    )
    parser.add_argument(
        "--screenshot-duplicates",
        metavar="PATH",
        help="Screenshot the old duplicate native/Flatpak cards using filler apps",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    demo = args.demo or bool(args.screenshot) or bool(args.screenshot_duplicates)
    duplicate_shot = bool(args.screenshot_duplicates)

    app = QGuiApplication(sys.argv)
    app.setApplicationName("AppGrid")
    app.setOrganizationName("AppGrid")
    icon_path = Path(__file__).resolve().parent / "data" / "appgrid.svg"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    controller = AppController(
        demo=demo,
        flatpak_enabled=True if (duplicate_shot or args.screenshot) else None,
        merge_duplicates=not duplicate_shot,
        show_source_badges=duplicate_shot,
    )
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(QML_DIR))
    engine.rootContext().setContextProperty("controller", controller)
    engine.rootContext().setContextProperty("appModel", controller.model())
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        return 1

    window = engine.rootObjects()[0]
    shot_path = args.screenshot_duplicates or args.screenshot

    if shot_path:
        output = Path(shot_path)
        if os.environ.get("APPGRID_SHOT_DETAIL"):
            window.setProperty("width", 1280)
            window.setProperty("height", 860)
        else:
            window.setProperty("width", 1600)
            window.setProperty("height", 1240)

        def grab() -> None:
            try:
                quick = window if isinstance(window, QQuickWindow) else None
                if quick is None:
                    found = window.findChildren(QQuickWindow)
                    quick = found[0] if found else None
                if quick is None:
                    screen = QGuiApplication.primaryScreen()
                    image = screen.grabWindow(int(window.winId()))
                else:
                    image = quick.grabWindow()
                output.parent.mkdir(parents=True, exist_ok=True)
                if image.isNull() or not image.save(str(output)):
                    print(f"failed to write {output}", file=sys.stderr)
                    QGuiApplication.exit(1)
                    return
            except Exception as exc:  # noqa: BLE001
                print(f"screenshot failed: {exc}", file=sys.stderr)
                QGuiApplication.exit(1)
                return
            QGuiApplication.exit(0)

        def grab_when_ready() -> None:
            if controller.busy:
                QTimer.singleShot(150, grab_when_ready)
                return
            if os.environ.get("APPGRID_SHOT_TICKER"):
                window.setProperty("categoryBannerOpen", True)
            if os.environ.get("APPGRID_SHOT_SETTINGS"):
                dialog = window.findChild(QObject, "settingsDialog")
                if dialog is not None:
                    queued = getattr(Qt, "QueuedConnection", None)
                    if queued is None:
                        queued = Qt.ConnectionType.QueuedConnection
                    QMetaObject.invokeMethod(dialog, "open", queued)
                QTimer.singleShot(400, grab)
                return
            detail = os.environ.get("APPGRID_SHOT_DETAIL")
            if detail:
                controller.select(detail)
                window.setProperty("shotDetailUid", detail)

                def grab_detail() -> None:
                    shot_progress = os.environ.get("APPGRID_SHOT_PROGRESS")
                    if shot_progress is not None:
                        try:
                            percent = int(shot_progress)
                        except ValueError:
                            percent = 42
                        controller.previewProgress(percent)
                        QTimer.singleShot(400, grab)
                        return
                    grab()

                QTimer.singleShot(1800, grab_detail)
                return
            shot_progress = os.environ.get("APPGRID_SHOT_PROGRESS")
            if shot_progress is not None:
                try:
                    percent = int(shot_progress)
                except ValueError:
                    percent = 42
                controller.previewProgress(percent)
                # Keep busy for the grab; don't wait for catalog idle after this.
                QTimer.singleShot(400, grab)
                return
            QTimer.singleShot(1200, grab)

        QTimer.singleShot(150, grab_when_ready)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
