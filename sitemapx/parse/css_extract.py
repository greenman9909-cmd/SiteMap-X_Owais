from __future__ import annotations

from urllib.parse import urljoin
import re

URL_RE = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.I)
IMPORT_RE = re.compile(r"@import\s+(?:url\()?\s*['\"]?([^'\"\)\s;]+)", re.I)


def extract_css(text: str, base_url: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for _, raw in URL_RE.findall(text):
        if raw and not raw.startswith("data:"):
            found.append((urljoin(base_url, raw), "css:url"))
    for raw in IMPORT_RE.findall(text):
        found.append((urljoin(base_url, raw), "css:import"))
    return found
