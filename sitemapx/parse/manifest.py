from __future__ import annotations

from urllib.parse import urljoin
import json


def extract_manifest(text: str, base_url: str) -> list[tuple[str, str]]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    found: list[tuple[str, str]] = []
    for key in ('start_url', 'scope'):
        if isinstance(data.get(key), str):
            found.append((urljoin(base_url, data[key]), f'manifest:{key}'))
    for icon in data.get('icons', []) or []:
        if isinstance(icon, dict) and icon.get('src'):
            found.append((urljoin(base_url, icon['src']), 'manifest:icon'))
    for item in data.get('shortcuts', []) or []:
        if isinstance(item, dict):
            if item.get('url'):
                found.append((urljoin(base_url, item['url']), 'manifest:shortcut'))
            for icon in item.get('icons', []) or []:
                if icon.get('src'):
                    found.append((urljoin(base_url, icon['src']), 'manifest:shortcut-icon'))
    return found
