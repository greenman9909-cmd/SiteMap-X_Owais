from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QTabWidget, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QLineEdit, QPlainTextEdit, QPushButton, QFileDialog,
    QHBoxLayout
)

from ...config import Config


class SettingsPanel(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.addTab(self._crawl_tab(), "Crawl Settings")
        self.addTab(self._filters_tab(), "Filters")
        self.addTab(self._advanced_tab(), "Advanced")

    def _path_row(self, target: QLineEdit, title: str, file_filter: str = "All files (*)") -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(target)
        button = QPushButton("Browse")
        button.clicked.connect(lambda: self._browse_file(target, title, file_filter))
        layout.addWidget(button)
        return row

    def _crawl_tab(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        self.out = QLineEdit(str(Path.cwd() / "sitemapx-output"))
        browse = QPushButton("Browse")
        browse.clicked.connect(self._browse_out)
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(self.out)
        h.addWidget(browse)
        f.addRow("Output", row)

        self.depth = QSpinBox(); self.depth.setRange(0, 100); self.depth.setValue(10); f.addRow("Depth", self.depth)
        self.concurrency = QSpinBox(); self.concurrency.setRange(1, 128); self.concurrency.setValue(12); f.addRow("Concurrency", self.concurrency)
        self.rate = QDoubleSpinBox(); self.rate.setRange(0, 1000); self.rate.setValue(20); f.addRow("Global req/s", self.rate)
        self.host_rate = QDoubleSpinBox(); self.host_rate.setRange(0, 1000); self.host_rate.setValue(5); f.addRow("Per-host req/s", self.host_rate)
        self.max_pages = QSpinBox(); self.max_pages.setRange(1, 2_000_000); self.max_pages.setValue(50_000); f.addRow("Page cap", self.max_pages)
        self.scope = QComboBox(); self.scope.addItems(["same-host", "same-domain", "all"]); f.addRow("Scope", self.scope)
        self.http2 = QCheckBox("Use HTTP/2-capable transport"); f.addRow("HTTP/2", self.http2)
        self.render = QCheckBox("Use Playwright Chromium"); f.addRow("Rendering", self.render)
        self.screenshots = QCheckBox("Full-page PNGs"); f.addRow("Screenshots", self.screenshots)
        self.robots = QCheckBox("Respect robots.txt"); self.robots.setChecked(True); f.addRow("Robots", self.robots)
        self.openapi = QCheckBox("Probe common OpenAPI paths"); f.addRow("OpenAPI", self.openapi)
        self.graphql = QCheckBox("Try GraphQL introspection"); f.addRow("GraphQL", self.graphql)
        self.rewrite_js = QCheckBox("Rewrite known URLs in JS"); f.addRow("Mirror", self.rewrite_js)

        self.cookie = QLineEdit(); self.cookie.setEchoMode(QLineEdit.Password); f.addRow("Cookie", self.cookie)
        self.basic = QLineEdit(); self.basic.setEchoMode(QLineEdit.Password); f.addRow("Basic user:pass", self.basic)
        self.login_url = QLineEdit(); f.addRow("Login URL", self.login_url)
        self.login_method = QComboBox(); self.login_method.addItems(["POST", "GET", "PUT", "PATCH"]); f.addRow("Login method", self.login_method)
        self.login_fields = QLineEdit(); self.login_fields.setPlaceholderText("user=admin&pass=secret"); f.addRow("Login fields", self.login_fields)

        self.har = QLineEdit(); f.addRow("HAR file", self._path_row(self.har, "Choose HAR file", "HAR files (*.har);;All files (*)"))
        self.cookie_file = QLineEdit(); f.addRow("Cookie file", self._path_row(self.cookie_file, "Choose Netscape cookie file"))
        self.storage_state = QLineEdit(); f.addRow("Storage state", self._path_row(self.storage_state, "Choose Playwright storage state", "JSON files (*.json);;All files (*)"))
        return w

    def _filters_tab(self) -> QWidget:
        w = QWidget(); f = QFormLayout(w)
        self.include = QPlainTextEdit(); self.include.setPlaceholderText("One regex per line")
        self.exclude = QPlainTextEdit(); self.exclude.setPlaceholderText("One regex per line")
        f.addRow("Include regex", self.include); f.addRow("Exclude regex", self.exclude)
        return w

    def _advanced_tab(self) -> QWidget:
        w = QWidget(); f = QFormLayout(w)
        self.headers = QPlainTextEdit(); self.headers.setPlaceholderText("Authorization: Bearer ...\nX-Custom: value")
        self.proxy = QLineEdit(); self.proxy.setPlaceholderText("http://127.0.0.1:8080")
        self.ua = QLineEdit("SiteMap-X/1.0 (+https://localhost/)")
        f.addRow("Headers", self.headers); f.addRow("Proxy", self.proxy); f.addRow("User-Agent", self.ua)
        return w

    def _browse_out(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose output directory", self.out.text())
        if path:
            self.out.setText(path)

    def _browse_file(self, target: QLineEdit, title: str, file_filter: str) -> None:
        path, _ = QFileDialog.getOpenFileName(self, title, target.text() or str(Path.home()), file_filter)
        if path:
            target.setText(path)

    @staticmethod
    def _maybe_path(value: str) -> Path | None:
        value = value.strip()
        return Path(value).expanduser() if value else None

    def build_config(self, url: str, resume: bool = False) -> Config:
        return Config(
            url=url,
            out=Path(self.out.text()).expanduser(),
            depth=self.depth.value(),
            concurrency=self.concurrency.value(),
            rate=self.rate.value(),
            per_host_rate=self.host_rate.value(),
            max_pages=self.max_pages.value(),
            scope=self.scope.currentText(),
            http2=self.http2.isChecked(),
            render=self.render.isChecked() or self.screenshots.isChecked(),
            screenshots=self.screenshots.isChecked(),
            robots=self.robots.isChecked(),
            openapi_probe=self.openapi.isChecked(),
            graphql_introspect=self.graphql.isChecked(),
            rewrite_js=self.rewrite_js.isChecked(),
            cookie=self.cookie.text() or None,
            basic=self.basic.text() or None,
            login_url=self.login_url.text() or None,
            login_method=self.login_method.currentText(),
            login_fields=self.login_fields.text() or None,
            har=self._maybe_path(self.har.text()),
            cookie_file=self._maybe_path(self.cookie_file.text()),
            storage_state=self._maybe_path(self.storage_state.text()),
            headers=[x.strip() for x in self.headers.toPlainText().splitlines() if x.strip()],
            proxy=self.proxy.text() or None,
            user_agent=self.ua.text() or "SiteMap-X/1.0",
            include_regex=[x.strip() for x in self.include.toPlainText().splitlines() if x.strip()],
            exclude_regex=[x.strip() for x in self.exclude.toPlainText().splitlines() if x.strip()],
            resume=resume,
        )
