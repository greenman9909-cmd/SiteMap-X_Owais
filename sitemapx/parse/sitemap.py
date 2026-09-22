from __future__ import annotations

import gzip
from urllib.parse import urljoin
from xml.etree import ElementTree as ET


_SITEMAP_CONTENT_TYPES = {"application/xml", "text/xml", "application/gzip"}


def _payload_bytes(payload: str | bytes) -> bytes:
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    if raw[:2] == b"\x1f\x8b":
        return gzip.decompress(raw)
    return raw


def looks_like_sitemap(url: str, content_type: str, payload: str | bytes) -> bool:
    path = url.lower().split("?", 1)[0]
    ctype = (content_type or "").split(";", 1)[0].strip().lower()
    if path.endswith((".xml", ".xml.gz")) or "/sitemap" in path:
        return True
    if ctype in _SITEMAP_CONTENT_TYPES:
        return True
    try:
        head = _payload_bytes(payload).lstrip()[:120].lower()
    except (OSError, EOFError, gzip.BadGzipFile):
        return False
    return head.startswith((b"<?xml", b"<urlset", b"<sitemapindex"))


def parse_sitemap(payload: str | bytes, base_url: str) -> tuple[list[str], list[str]]:
    """Return (page URLs, child sitemap URLs) from one sitemap document."""
    urls: list[str] = []
    sitemaps: list[str] = []
    try:
        root = ET.fromstring(_payload_bytes(payload))
    except (ET.ParseError, OSError, EOFError, gzip.BadGzipFile, UnicodeError):
        return urls, sitemaps

    root_tag = root.tag.rsplit("}", 1)[-1].lower()
    if root_tag not in {"urlset", "sitemapindex"}:
        return urls, sitemaps
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1].lower() != "loc" or not element.text:
            continue
        target = urljoin(base_url, element.text.strip())
        if root_tag == "sitemapindex":
            sitemaps.append(target)
        else:
            urls.append(target)
    return urls, sitemaps


def sitemap_kind(payload: str | bytes) -> str | None:
    try:
        root = ET.fromstring(_payload_bytes(payload))
    except (ET.ParseError, OSError, EOFError, gzip.BadGzipFile, UnicodeError):
        return None
    tag = root.tag.rsplit("}", 1)[-1].lower()
    return {"urlset": "urlset", "sitemapindex": "index"}.get(tag)
