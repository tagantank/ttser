from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from ttser.main_window import MainWindow

ICON_PATH = Path(__file__).resolve().parent / "resources" / "icon.png"


def main() -> int:
    app = QApplication(sys.argv)
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
