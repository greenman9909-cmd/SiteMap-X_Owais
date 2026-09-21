from __future__ import annotations

import hashlib
import ipaddress
import posixpath
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

try:
    import tldextract
except Exception:
    tldextract = None

from .._compat import fallback_registrable_domain


STATIC_EXTENSIONS = {
    ".css", ".js", ".mjs", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
    ".woff", ".woff2", ".ttf", ".otf", ".eot", ".mp4", ".webm", ".mp3", ".wav", ".pdf",
    ".zip", ".map", ".wasm", ".webmanifest",
}
API_PATH_RE = re.compile(r"/(?:api(?:/|$)|v\d+(?:/|$)|graphql(?:/|$)|rest(?:/|$)|rpc(?:/|$)|ajax(?:/|$)|json(?:/|$)|xml(?:/|$)|oauth(?:/|$)|auth(?:/|$))", re.I)


def absolutize(base: str, raw: str | None) -> str | None:
    if not raw:
        return None
    value = raw.strip()
    if not value or value.startswith(("data:", "javascript:", "mailto:", "tel:", "blob:", "about:")):
        return None
    if value.startswith(("ws://", "wss://")):
        return value
    return urljoin(base, value)


def normalize_url(url: str, base: str | None = None) -> str | None:
    if base:
        url = urljoin(base, url)
    p = urlsplit(url.strip())
    if p.scheme.lower() not in {"http", "https"}:
        return None
    host = (p.hostname or "").lower()
    if not host:
        return None
    port = p.port
    netloc = host
    if port and not ((p.scheme.lower() == "http" and port == 80) or (p.scheme.lower() == "https" and port == 443)):
        netloc = f"{host}:{port}"
    path = re.sub(r"/{2,}", "/", p.path or "/")
    query = urlencode(sorted(parse_qsl(p.query, keep_blank_values=True)))
    fragment = p.fragment if p.fragment.startswith(("/", "!")) else ""
    return urlunsplit((p.scheme.lower(), netloc, path, query, fragment))


def registrable_domain(value: str) -> str:
    host = (urlsplit(value).hostname if "://" in value else value) or ""
    host = host.strip(".").lower()
    if not host:
        return ""
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    if tldextract:
        ext = tldextract.extract(host)
        if ext.domain and ext.suffix:
            return f"{ext.domain}.{ext.suffix}".lower()
    return fallback_registrable_domain(f"https://{host}")


def in_scope(seed: str, candidate: str, mode: str) -> bool:
    if mode == "all":
        return True
    a, b = urlsplit(seed), urlsplit(candidate)
    if mode == "same-domain":
        return registrable_domain(a.hostname or "") == registrable_domain(b.hostname or "")
    return (a.hostname or "").lower() == (b.hostname or "").lower()


def classify_url(url: str, source: str = "") -> str:
    lower = url.lower()
    if lower.startswith(("ws://", "wss://")):
        return "WEBSOCKET URL"
    p = urlsplit(url)
    path = p.path.lower()
    if "graphql" in path or source in {"graphql", "graphql-probe"}:
        return "GRAPHQL ENDPOINT"
    source_lower = source.lower()
    if source_lower in {"fetch", "axios", "xhr", "eventsource", "beacon", "form", "openapi"} or source_lower.startswith("runtime:") or API_PATH_RE.search(path):
        return "API ENDPOINT"
    if Path(path).suffix.lower() in STATIC_EXTENSIONS:
        return "STATIC ASSET"
    if source_lower.startswith("html:a") or path.endswith((".html", ".htm", ".xml")) or not Path(path).suffix:
        return "NAVIGABLE PAGE"
    return "STATIC ASSET" if source_lower.startswith(("html:img", "html:script", "html:link", "css:", "bundle", "source-map")) else "NAVIGABLE PAGE"


def safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return value[:140] or "index"


def local_path_for(url: str, content_type: str | None = None) -> Path:
    p = urlsplit(url)
    path = p.path or "/"
    if path.endswith("/"):
        path += "index.html"
    leaf = posixpath.basename(path)
    if "." not in leaf:
        if (content_type or "").startswith("text/html"):
            path = path.rstrip("/") + "/index.html"
        else:
            path = path.rstrip("/") + "/index"
    parts = [safe_name(x) for x in path.lstrip("/").split("/") if x]
    if not parts:
        parts = ["index.html"]
    if p.query:
        stem = Path(parts[-1]).stem
        suffix = Path(parts[-1]).suffix
        parts[-1] = f"{stem}_{hashlib.sha1(p.query.encode()).hexdigest()[:10]}{suffix}"
    return Path(safe_name(p.hostname or "site"), *parts)


def relative_link(from_path: Path, target_path: Path) -> str:
    return posixpath.relpath(target_path.as_posix(), start=Path(from_path).parent.as_posix())


relative_local_link = relative_link
