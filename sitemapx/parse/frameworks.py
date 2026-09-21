from __future__ import annotations

from urllib.parse import urljoin
import re


def extract_framework_routes(text: str, base_url: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for marker, kind in (("__NEXT_DATA__", "next"), ("__NUXT__", "nuxt"), ("__remixManifest", "remix"), ("__SVELTEKIT", "sveltekit")):
        if marker not in text:
            continue
        for m in re.finditer(r"['\"](/[^'\"\s]{1,180})['\"]", text):
            raw = m.group(1)
            if raw.startswith('//'):
                continue
            out.append((urljoin(base_url, raw), f'framework:{kind}'))
    for m in re.finditer(r"(?:serviceWorker\.register|navigator\.serviceWorker\.register)\(\s*['\"`]([^'\"`]+)", text):
        out.append((urljoin(base_url, m.group(1)), 'service-worker'))
    for m in re.finditer(r"(?:chunk|assets?)[-_][A-Za-z0-9._-]+\.(?:js|css)", text, re.I):
        out.append((urljoin(base_url, m.group(0)), 'bundle-manifest'))
    return list(dict.fromkeys(out))
