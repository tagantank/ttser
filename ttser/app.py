from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from engine.runtime import resource_root
from ttser.i18n import apply_language
from ttser.main_window import MainWindow
from ttser.settings import load_settings

_PACKAGE_ICON = Path(__file__).resolve().parent / "resources" / "icon.png"
_BUNDLE_ICON = resource_root() / "ttser" / "resources" / "icon.png"
ICON_PATH = _PACKAGE_ICON if _PACKAGE_ICON.is_file() else _BUNDLE_ICON


def main() -> int:
    app = QApplication(sys.argv)
    settings = load_settings()
    apply_language(app, settings.ui_language)
    if ICON_PATH.is_file():
        icon = QIcon(str(ICON_PATH))
        app.setWindowIcon(icon)
    win = MainWindow()
    if ICON_PATH.is_file():
        win.setWindowIcon(QIcon(str(ICON_PATH)))
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
