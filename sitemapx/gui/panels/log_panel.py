from __future__ import annotations

from datetime import datetime
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPlainTextEdit


class LogPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.filter = QComboBox()
        self.filter.addItems(["ALL", "INFO", "WARN", "ERROR"])
        bar.addWidget(self.filter)
        bar.addStretch()
        layout.addLayout(bar)
        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(5000)
        self.view.setStyleSheet("font-family: Consolas, 'Courier New', monospace;")
        layout.addWidget(self.view)
        self._rows: list[tuple[str, str]] = []
        self.filter.currentTextChanged.connect(self._render)

    def log(self, level: str, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self._rows.append((level.upper(), f"[{stamp}] {level.upper():5s} {message}"))
        if len(self._rows) > 5000:
            self._rows = self._rows[-5000:]
        self._render()

    def _render(self) -> None:
        selected = self.filter.currentText()
        lines = [line for level, line in self._rows if selected == "ALL" or level == selected]
        self.view.setPlainText("\n".join(lines))
        self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum())
