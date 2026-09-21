from __future__ import annotations

from pathlib import Path
import html

from ..core.urlutil import local_path_for
from .rewrite_css import rewrite_css
from .rewrite_html import rewrite_html
from .rewrite_js import rewrite_js


class MirrorWriter:
    def __init__(self, root: Path, rewrite_js_enabled: bool = False):
        self.root = Path(root) / "mirror"
        self.root.mkdir(parents=True, exist_ok=True)
        self.rewrite_js_enabled = rewrite_js_enabled
        self.known: dict[str, Path] = {}
        self.pending: list[tuple[str, str, bytes, str]] = []

    def register(self, url: str, content_type: str) -> Path:
        rel = local_path_for(url, content_type)
        self.known[url] = rel
        return rel

    def stage(self, url: str, content_type: str, body: bytes, text: str = "") -> Path:
        rel = self.known.get(url) or self.register(url, content_type)
        self.pending.append((url, content_type, body, text))
        return self.root / rel

    def finalize(self) -> None:
        pages = []
        for url, ctype, body, text in self.pending:
            rel = self.known[url]
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            lower = ctype.lower()
            if "html" in lower:
                content = rewrite_html(text or body.decode("utf-8", "replace"), url, rel, self.known)
                path.write_text(content, "utf-8")
                pages.append((url, rel))
            elif "css" in lower:
                content = rewrite_css(text or body.decode("utf-8", "replace"), url, rel, self.known)
                path.write_text(content, "utf-8")
            elif self.rewrite_js_enabled and ("javascript" in lower or rel.suffix in {".js", ".mjs"}):
                content = rewrite_js(text or body.decode("utf-8", "replace"), url, rel, self.known)
                path.write_text(content, "utf-8")
            else:
                path.write_bytes(body)
        links = "\n".join(f'<li><a href="{html.escape(rel.as_posix())}">{html.escape(url)}</a></li>' for url, rel in pages)
        (self.root / "index.html").write_text(f"<!doctype html><meta charset=utf-8><title>SiteMap-X Mirror</title><h1>Cloned pages</h1><ul>{links}</ul>", "utf-8")
