from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin
import re

from ..core.urlutil import normalize_url, relative_link

URL_RE = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.I)
IMPORT_RE = re.compile(r"(@import\s+(?:url\()?\s*['\"]?)([^'\"\)\s;]+)", re.I)


def _lookup(known: dict[str, Path], absolute: str) -> Path | None:
    target = known.get(absolute)
    if target:
        return target
    try:
        return known.get(normalize_url(absolute))
    except Exception:
        return None


def rewrite_css(text: str, source_url: str, source_file: Path, known: dict[str, Path]) -> str:
    def repl(m):
        raw = m.group(2)
        if raw.startswith("data:"):
            return m.group(0)
        target = _lookup(known, urljoin(source_url, raw))
        if not target:
            return m.group(0)
        return f"url('{relative_link(source_file, target)}')"
    text = URL_RE.sub(repl, text)

    def repl_import(m):
        target = _lookup(known, urljoin(source_url, m.group(2)))
        return m.group(1) + (relative_link(source_file, target) if target else m.group(2))
    return IMPORT_RE.sub(repl_import, text)
