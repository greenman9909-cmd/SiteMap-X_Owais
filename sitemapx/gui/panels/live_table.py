from __future__ import annotations

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView


class LiveTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(0, 5, parent)
        self.setHorizontalHeaderLabels(["URL", "Status", "Type", "Depth", "Time"])
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, 5):
            self.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(False)

    def add_event(self, event: dict) -> None:
        row = self.rowCount()
        self.insertRow(row)
        values = [event.get("url", ""), event.get("status", ""), event.get("type", ""), event.get("depth", ""), f"{float(event.get('time') or 0):.3f}s"]
        for col, value in enumerate(values):
            self.setItem(row, col, QTableWidgetItem(str(value)))
        self.scrollToBottom()
