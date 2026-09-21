from __future__ import annotations

from pathlib import Path
import base64
import csv
import json
import shutil
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QProgressBar,
    QSplitter, QMessageBox, QFileDialog, QInputDialog, QDialog, QPlainTextEdit, QDialogButtonBox,
    QLabel
)

from .panels.settings_panel import SettingsPanel
from .panels.live_table import LiveTable
from .panels.log_panel import LogPanel
from .panels.results_panel import ResultsPanel
from .worker import CrawlWorker
from ..report.diff import diff_directories


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SiteMap-X")
        self.resize(1500, 900)
        self.worker: CrawlWorker | None = None
        self.last_out: Path | None = None
        self._build_ui()
        self._build_menu()

    def _build_ui(self):
        root = QWidget(); outer = QVBoxLayout(root)
        top = QHBoxLayout()
        self.url = QLineEdit(); self.url.setPlaceholderText("https://example.com")
        self.start_btn = QPushButton("Start Crawl"); self.stop_btn = QPushButton("Stop"); self.resume_btn = QPushButton("Resume")
        self.stop_btn.setEnabled(False)
        self.progress = QProgressBar(); self.progress.setRange(0, 100); self.progress.setValue(0)
        top.addWidget(QLabel("URL")); top.addWidget(self.url, 1); top.addWidget(self.start_btn); top.addWidget(self.stop_btn); top.addWidget(self.resume_btn); top.addWidget(self.progress)
        outer.addLayout(top)

        self.settings = SettingsPanel()
        self.table = LiveTable()
        self.logs = LogPanel()
        self.results = ResultsPanel()
        center = QSplitter(Qt.Vertical)
        center.addWidget(self.table); center.addWidget(self.logs); center.setSizes([570, 220])
        main = QSplitter(Qt.Horizontal)
        main.addWidget(self.settings); main.addWidget(center); main.addWidget(self.results)
        main.setSizes([320, 860, 320])
        outer.addWidget(main, 1)
        self.setCentralWidget(root)
        self.start_btn.clicked.connect(lambda: self.start_crawl(False))
        self.resume_btn.clicked.connect(lambda: self.start_crawl(True))
        self.stop_btn.clicked.connect(self.stop_crawl)

    def _build_menu(self):
        file_menu = self.menuBar().addMenu("File")
        for label, fmt in (("Export JSON", "json"), ("Export Markdown", "md"), ("Export CSV", "csv")):
            action = QAction(label, self); action.triggered.connect(lambda checked=False, f=fmt: self.export_format(f)); file_menu.addAction(action)
        tools = self.menuBar().addMenu("Tools")
        crack = QAction("Crack Cookies", self); crack.triggered.connect(self.jwt_inspector); tools.addAction(crack)
        diff = QAction("Diff Crawl", self); diff.triggered.connect(self.diff_crawl); tools.addAction(diff)
        helpm = self.menuBar().addMenu("Help")
        about = QAction("About", self); about.triggered.connect(lambda: QMessageBox.about(self, "About SiteMap-X", "SiteMap-X 1.0\nWebsite mirror, endpoint mapper, and crawl reporter.")); helpm.addAction(about)

    def start_crawl(self, resume: bool):
        target = self.url.text().strip()
        if not target:
            QMessageBox.warning(self, "SiteMap-X", "Enter a URL first.")
            return
        if self.worker and self.worker.isRunning():
            return
        self.table.setRowCount(0)
        config = self.settings.build_config(target, resume=resume)
        self.last_out = config.out.expanduser().resolve()
        self.worker = CrawlWorker(config, self)
        self.worker.event.connect(self.on_event)
        self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(self.on_finished)
        self.start_btn.setEnabled(False); self.resume_btn.setEnabled(False); self.stop_btn.setEnabled(True)
        self.logs.log("INFO", f"Starting {'resume' if resume else 'crawl'}: {target}")
        self.worker.start()

    def stop_crawl(self):
        if self.worker:
            self.worker.request_stop()
            self.logs.log("INFO", "Stop requested")

    def on_event(self, event: dict):
        kind = event.get("kind")
        if kind == "url":
            self.table.add_event(event)
        elif kind == "log":
            self.logs.log(event.get("level", "INFO"), event.get("message", ""))
        elif kind == "progress":
            crawled = int(event.get("crawled") or 0); queued = int(event.get("queued") or 0); failed = int(event.get("failed") or 0)
            total = crawled + queued + failed
            self.progress.setValue(int((crawled / total) * 100) if total else 0)
            self.progress.setFormat(f"{crawled} crawled / {queued} queued / {failed} failed")
        elif kind == "done":
            self.logs.log("INFO", f"Done: {event.get('summary')}")
            self.progress.setValue(100)
            if self.last_out: self.results.load_report(self.last_out)

    def on_failed(self, message: str):
        self.logs.log("ERROR", message)
        QMessageBox.critical(self, "SiteMap-X", message)

    def on_finished(self):
        self.start_btn.setEnabled(True); self.resume_btn.setEnabled(True); self.stop_btn.setEnabled(False)

    def export_format(self, fmt: str):
        if not self.last_out or not self.last_out.exists():
            QMessageBox.information(self, "Export", "Run or open a crawl first.")
            return
        suffix = {"json": ".json", "md": ".md", "csv": ".csv"}[fmt]
        dest, _ = QFileDialog.getSaveFileName(self, f"Export {fmt.upper()}", str(Path.home() / f"sitemapx-export{suffix}"), f"*{suffix}")
        if not dest: return
        if fmt in {"json", "md"}:
            source = self.last_out / ("report.json" if fmt == "json" else "report.md")
            if not source.exists():
                QMessageBox.warning(self, "Export", f"{source.name} is not present in the output directory.")
                return
            shutil.copy2(source, dest)
        else:
            db = self.last_out / "crawl.sqlite3"
            con = sqlite3.connect(db)
            try:
                rows = con.execute("SELECT method,category,url,source,discovered_from,line,response_status FROM endpoints ORDER BY url").fetchall()
                with open(dest, "w", newline="", encoding="utf-8") as fh:
                    w = csv.writer(fh); w.writerow(["method","category","url","source","discovered_from","line","response_status"]); w.writerows(rows)
            finally:
                con.close()
        self.logs.log("INFO", f"Exported {dest}")

    def jwt_inspector(self):
        token, ok = QInputDialog.getMultiLineText(self, "Crack Cookies / JWT Inspector", "Paste a JWT value to decode its header and payload locally:")
        if not ok or not token.strip(): return
        parts = token.strip().split(".")
        if len(parts) < 2:
            QMessageBox.warning(self, "JWT Inspector", "This value does not have JWT header.payload structure.")
            return
        def dec(part):
            pad = "=" * (-len(part) % 4)
            return json.loads(base64.urlsafe_b64decode(part + pad).decode("utf-8"))
        try:
            data = {"header": dec(parts[0]), "payload": dec(parts[1]), "signature_present": len(parts) > 2 and bool(parts[2])}
        except Exception as exc:
            QMessageBox.warning(self, "JWT Inspector", f"Could not decode JWT: {exc}")
            return
        dlg = QDialog(self); dlg.setWindowTitle("JWT structure"); lay = QVBoxLayout(dlg); view = QPlainTextEdit(json.dumps(data, indent=2)); view.setReadOnly(True); lay.addWidget(view)
        buttons = QDialogButtonBox(QDialogButtonBox.Close); buttons.rejected.connect(dlg.reject); buttons.clicked.connect(dlg.accept); lay.addWidget(buttons); dlg.resize(700,500); dlg.exec()

    def diff_crawl(self):
        if not self.last_out:
            QMessageBox.information(self, "Diff Crawl", "Run a crawl first.")
            return
        old = QFileDialog.getExistingDirectory(self, "Choose previous crawl directory")
        if not old: return
        result = diff_directories(Path(old), self.last_out, self.last_out / "diff.md")
        QMessageBox.information(self, "Diff Crawl", f"Added: {len(result['added'])}\nRemoved: {len(result['removed'])}\nUnchanged: {len(result['unchanged'])}\n\nSaved diff.md")
