from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin
import re


@dataclass(slots=True)
class JSHit:
    url: str
    method: str
    kind: str
    line: int
    confidence: float = .9


def _line(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def extract_js(text: str, base_url: str) -> list[JSHit]:
    hits: list[JSHit] = []
    patterns = [
        (re.compile(r"\bfetch\(\s*['\"`]([^'\"`]+)", re.I), "GET", "fetch", .95),
        (re.compile(r"\baxios\.(get|post|put|delete|patch|head|options)\(\s*['\"`]([^'\"`]+)", re.I), None, "axios", .95),
        (re.compile(r"\.open\(\s*['\"](GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)['\"]\s*,\s*['\"`]([^'\"`]+)", re.I), None, "xhr", .95),
        (re.compile(r"new\s+WebSocket\(\s*['\"`]([^'\"`]+)", re.I), "GET", "websocket", .98),
        (re.compile(r"new\s+EventSource\(\s*['\"`]([^'\"`]+)", re.I), "GET", "eventsource", .95),
        (re.compile(r"\b(?:import|require|importScripts)\(\s*['\"`]([^'\"`]+)", re.I), "GET", "import", .75),
        (re.compile(r"navigator\.sendBeacon\(\s*['\"`]([^'\"`]+)", re.I), "POST", "beacon", .95),
    ]
    for regex, method, kind, confidence in patterns:
        for m in regex.finditer(text):
            if kind in {"axios", "xhr"}:
                meth, raw = m.group(1).upper(), m.group(2)
            else:
                meth, raw = method or "GET", m.group(1)
            url = raw if raw.startswith(("ws://", "wss://")) else urljoin(base_url, raw)
            hits.append(JSHit(url, meth, kind, _line(text, m.start()), confidence))

    for m in re.finditer(r"[#@]\s*sourceMappingURL=([^\s*]+)", text):
        hits.append(JSHit(urljoin(base_url, m.group(1).strip()), "GET", "source-map", _line(text, m.start()), .98))
    for block in re.finditer(r"(?:cache\.addAll|addAll)\(\s*\[([^\]]{0,10000})\]", text, re.I | re.S):
        for sm in re.finditer(r"['\"]([^'\"]+)['\"]", block.group(1)):
            raw = sm.group(1)
            if raw and not raw.startswith(("data:", "javascript:")):
                hits.append(JSHit(urljoin(base_url, raw), "GET", "service-worker-cache", _line(text, block.start()+sm.start()), .85))
    for m in re.finditer(r"['\"]([^'\"\n]+\.(?:js|mjs|css|map))(?:\?[^'\"]*)?['\"]", text, re.I):
        raw = m.group(1)
        if len(raw) < 300:
            hits.append(JSHit(urljoin(base_url, raw), "GET", "bundle-ref", _line(text, m.start()), .65))

    literal = re.compile(r"['\"`]((?:/api/|/v\d+/|/graphql(?:\b|/)|/rest/|/rpc\b|/ajax/|/json/|/xml/|/ws\b|/socket\b|/events\b|/stream\b|/oauth/|/auth/)[^'\"`\s]*)", re.I)
    for m in literal.finditer(text):
        hits.append(JSHit(urljoin(base_url, m.group(1)), "GET", "literal-api-path", _line(text, m.start()), .75))
    route = re.compile(r"['\"`](/(?!/)[A-Za-z0-9_~.!$&()*+,;=:@%/?#-]{1,180})['\"`]")
    for m in route.finditer(text):
        raw = m.group(1)
        if any(x in raw for x in (" ", "\\", "${")) or raw.count("/") == 1 and "." in raw:
            continue
        hits.append(JSHit(urljoin(base_url, raw), "GET", "route-literal", _line(text, m.start()), .4))
    unique = {}
    for h in hits:
        unique[(h.url, h.method, h.kind, h.line)] = h
    return list(unique.values())
