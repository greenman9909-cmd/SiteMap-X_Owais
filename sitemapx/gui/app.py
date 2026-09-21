from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtWidgets import QApplication

from .main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    qss = Path(__file__).with_name("styles") / "dark.qss"
    if qss.exists():
        app.setStyleSheet(qss.read_text("utf-8"))
    win = MainWindow()
    win.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
