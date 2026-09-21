from __future__ import annotations

from urllib.parse import urljoin
import json
import re

URL_RE = re.compile(r"https?://[^\s'\"<>]+|/(?:api|v\d+|graphql|rest|oauth|auth)/[^\s'\"<>]*", re.I)


def extract_sourcemap(text: str, base_url: str) -> tuple[list[str], list[str]]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return [], []
    sources = [urljoin(base_url, s) for s in data.get('sources', []) if isinstance(s, str)]
    urls: list[str] = []
    haystacks = [json.dumps(data.get('names', []))]
    haystacks.extend(x for x in data.get('sourcesContent', []) if isinstance(x, str))
    for blob in haystacks:
        for m in URL_RE.finditer(blob):
            urls.append(urljoin(base_url, m.group(0)))
    return sources, urls
