from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin
import re

from ..core.urlutil import normalize_url, relative_link

QUOTED = re.compile(r"(['\"])([^'\"\n]{1,300})\1")


def _lookup(known: dict[str, Path], absolute: str) -> Path | None:
    target = known.get(absolute)
    if target:
        return target
    try:
        return known.get(normalize_url(absolute))
    except Exception:
        return None


def rewrite_js(text: str, source_url: str, source_file: Path, known: dict[str, Path]) -> str:
    def repl(m):
        raw = m.group(2)
        if not raw.startswith(("/", "./", "../", "http://", "https://")):
            return m.group(0)
        target = _lookup(known, urljoin(source_url, raw))
        if not target:
            return m.group(0)
        return f"{m.group(1)}{relative_link(source_file, target)}{m.group(1)}"
    return QUOTED.sub(repl, text)
