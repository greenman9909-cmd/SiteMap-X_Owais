from __future__ import annotations

from urllib.parse import urljoin
from xml.etree import ElementTree as ET


def parse_sitemap(text: str, base_url: str) -> tuple[list[str], list[str]]:
    urls: list[str] = []
    sitemaps: list[str] = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return urls, sitemaps
    tag = root.tag.rsplit('}', 1)[-1].lower()
    for loc in root.iter():
        if loc.tag.rsplit('}', 1)[-1].lower() != 'loc' or not loc.text:
            continue
        target = urljoin(base_url, loc.text.strip())
        if tag == 'sitemapindex':
            sitemaps.append(target)
        else:
            urls.append(target)
    return urls, sitemaps
