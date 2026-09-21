from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urljoin


@dataclass(slots=True)
class RobotsInfo:
    sitemaps: list[str] = field(default_factory=list)
    crawl_delay: float = 0.0
    allows: list[str] = field(default_factory=list)
    disallows: list[str] = field(default_factory=list)


def parse_robots(text: str, base_url: str, user_agent: str = '*') -> RobotsInfo:
    info = RobotsInfo()
    active = False
    matched_agent = False
    for raw in text.splitlines():
        line = raw.split('#', 1)[0].strip()
        if not line or ':' not in line:
            continue
        key, value = [x.strip() for x in line.split(':', 1)]
        k = key.lower()
        if k == 'sitemap':
            info.sitemaps.append(urljoin(base_url, value))
            continue
        if k == 'user-agent':
            ua = value.lower()
            active = ua == '*' or ua in user_agent.lower()
            matched_agent = matched_agent or active
            continue
        if not active:
            continue
        if k == 'crawl-delay':
            try:
                info.crawl_delay = max(info.crawl_delay, float(value))
            except ValueError:
                pass
        elif k == 'allow':
            info.allows.append(value)
        elif k == 'disallow' and value:
            info.disallows.append(value)
    return info


def robots_allows(path: str, info: RobotsInfo) -> bool:
    matches = []
    for rule in info.disallows:
        if path.startswith(rule):
            matches.append((len(rule), False))
    for rule in info.allows:
        if path.startswith(rule):
            matches.append((len(rule), True))
    if not matches:
        return True
    return max(matches, key=lambda x: x[0])[1]
