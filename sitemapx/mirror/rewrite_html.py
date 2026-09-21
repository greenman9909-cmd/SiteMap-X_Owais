from __future__ import annotations

from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from ..core.urlutil import normalize_url, relative_link
from .rewrite_css import rewrite_css


def _lookup(known: dict[str, Path], absolute: str) -> Path | None:
    target = known.get(absolute)
    if target:
        return target
    try:
        return known.get(normalize_url(absolute))
    except Exception:
        return None


def rewrite_html(text: str, page_url: str, page_file: Path, known: dict[str, Path]) -> str:
    soup = BeautifulSoup(text, "lxml")
    base_tag = soup.find("base", href=True)
    base_url = urljoin(page_url, base_tag.get("href")) if base_tag else page_url
    if base_tag:
        base_tag.decompose()
    attrs = ("href", "src", "action", "poster", "data-src", "data-href")
    for node in soup.find_all(True):
        for attr in attrs:
            raw = node.get(attr)
            if not raw:
                continue
            absolute = urljoin(base_url, raw)
            target = _lookup(known, absolute)
            if target:
                node[attr] = relative_link(page_file, target)
        if node.get("srcset"):
            rewritten = []
            for part in node["srcset"].split(","):
                bits = part.strip().split()
                if not bits:
                    continue
                absolute = urljoin(base_url, bits[0])
                target = _lookup(known, absolute)
                if target:
                    bits[0] = relative_link(page_file, target)
                rewritten.append(" ".join(bits))
            node["srcset"] = ", ".join(rewritten)
        if node.get("style"):
            node["style"] = rewrite_css(node["style"], base_url, page_file, known)
    for style in soup.find_all("style"):
        style.string = rewrite_css(style.get_text(), base_url, page_file, known)
    return str(soup)
