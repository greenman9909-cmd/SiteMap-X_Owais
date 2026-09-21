from __future__ import annotations

from pathlib import Path
import json

from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem


class ResultsPanel(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["Results", "Value"])

    def load_report(self, out: Path) -> None:
        self.clear()
        p = Path(out) / "report.json"
        if not p.exists():
            return
        data = json.loads(p.read_text("utf-8"))
        groups = {
            "Endpoints": data.get("endpoints", []),
            "Pages": data.get("pages", []),
            "Assets": data.get("assets", []),
            "Fingerprints": data.get("fingerprints", []),
            "GraphQL": [x for x in data.get("endpoints", []) if "GRAPHQL" in str(x.get("category", ""))],
            "External": [x for x in data.get("endpoints", []) if x.get("category") == "EXTERNAL"],
        }
        for name, rows in groups.items():
            parent = QTreeWidgetItem([name, str(len(rows))])
            self.addTopLevelItem(parent)
            for row in rows[:1000]:
                label = row.get("url") or row.get("name") or row.get("title") or str(row.get("id", ""))
                value = row.get("method") or row.get("category") or row.get("mime") or ""
                parent.addChild(QTreeWidgetItem([str(label), str(value)]))
