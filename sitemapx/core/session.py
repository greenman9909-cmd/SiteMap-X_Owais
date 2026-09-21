from __future__ import annotations

from dataclasses import dataclass
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit
import json

import aiohttp
import httpx
from yarl import URL

from ..config import Config


@dataclass(slots=True)
class SessionBundle:
    session: aiohttp.ClientSession
    http2_client: httpx.AsyncClient | None
    auth_attached: bool


def parse_headers(values: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in values:
        if ":" in item:
            key, value = item.split(":", 1)
            key = key.strip()
            if key:
                out[key] = value.strip()
    return out


def parse_cookie_header(value: str | None) -> dict[str, str]:
    if not value:
        return {}
    cookie = SimpleCookie()
    cookie.load(value)
    return {key: morsel.value for key, morsel in cookie.items()}


def load_netscape_cookie_file(path: Path) -> list[dict]:
    cookies: list[dict] = []
    for raw in path.read_text("utf-8", errors="ignore").splitlines():
        if not raw or raw.startswith("#"):
            continue
        parts = raw.split("\t")
        if len(parts) < 7:
            continue
        domain, _, cookie_path, secure, expires, name, value = parts[:7]
        cookies.append({
            "domain": domain,
            "path": cookie_path or "/",
            "secure": secure.upper() == "TRUE",
            "expires": expires,
            "name": name,
            "value": value,
        })
    return cookies


def _har_material(path: Path) -> tuple[dict[str, str], list[dict]]:
    headers: dict[str, str] = {}
    cookies: list[dict] = []
    try:
        har = json.loads(path.read_text("utf-8"))
    except Exception:
        return headers, cookies
    entries = har.get("log", {}).get("entries", [])
    for entry in entries:
        req = entry.get("request", {})
        for item in req.get("headers", []):
            name = str(item.get("name", ""))
            if name.lower() in {"authorization", "x-api-key", "x-auth-token"}:
                headers[name] = str(item.get("value", ""))
        for cookie in req.get("cookies", []):
            name = str(cookie.get("name", ""))
            if name:
                cookies.append({
                    "name": name,
                    "value": str(cookie.get("value", "")),
                    "domain": str(cookie.get("domain", "")),
                    "path": str(cookie.get("path", "/") or "/"),
                    "secure": bool(cookie.get("secure", False)),
                })
    return headers, cookies


def _aio_cookie_url(cfg: Config, domain: str = "") -> URL:
    if domain:
        clean = domain.lstrip(".")
        scheme = "https"
        return URL(f"{scheme}://{clean}/")
    seed = urlsplit(cfg.url or cfg.login_url or "https://localhost/")
    scheme = seed.scheme if seed.scheme in {"http", "https"} else "https"
    host = seed.netloc or "localhost"
    return URL(f"{scheme}://{host}/")


def _set_cookie_both(
    cfg: Config,
    jar: aiohttp.CookieJar,
    http_client: httpx.AsyncClient | None,
    cookie: dict,
) -> None:
    name = str(cookie.get("name") or "")
    if not name:
        return
    value = str(cookie.get("value") or "")
    domain = str(cookie.get("domain") or "")
    path = str(cookie.get("path") or "/")
    jar.update_cookies({name: value}, response_url=_aio_cookie_url(cfg, domain))
    if http_client is not None:
        kwargs = {"path": path}
        if domain:
            kwargs["domain"] = domain
        http_client.cookies.set(name, value, **kwargs)


async def build_session(cfg: Config) -> SessionBundle:
    headers = {"User-Agent": cfg.user_agent, **parse_headers(cfg.headers)}
    auth_attached = bool(cfg.cookie or cfg.headers or cfg.basic or cfg.cookie_file or cfg.har or cfg.login_url or cfg.storage_state)

    basic_auth = None
    httpx_auth = None
    if cfg.basic and ":" in cfg.basic:
        username, password = cfg.basic.split(":", 1)
        basic_auth = aiohttp.BasicAuth(username, password)
        httpx_auth = (username, password)

    jar = aiohttp.CookieJar(unsafe=True)
    timeout = aiohttp.ClientTimeout(total=cfg.timeout)
    connector = aiohttp.TCPConnector(limit=max(1, cfg.concurrency * 2))
    session = aiohttp.ClientSession(
        headers=headers,
        auth=basic_auth,
        cookie_jar=jar,
        timeout=timeout,
        connector=connector,
    )

    need_http_client = bool(cfg.http2)
    http_client = None
    if need_http_client:
        http_client = httpx.AsyncClient(
            headers=headers,
            auth=httpx_auth,
            http2=True,
            follow_redirects=True,
            timeout=cfg.timeout,
            proxy=cfg.proxy,
            max_redirects=cfg.redirect_limit,
        )

    for name, value in parse_cookie_header(cfg.cookie).items():
        _set_cookie_both(cfg, jar, http_client, {"name": name, "value": value})

    if cfg.cookie_file and Path(cfg.cookie_file).exists():
        for cookie in load_netscape_cookie_file(Path(cfg.cookie_file)):
            _set_cookie_both(cfg, jar, http_client, cookie)

    if cfg.har and Path(cfg.har).exists():
        har_headers, har_cookies = _har_material(Path(cfg.har))
        session.headers.update(har_headers)
        if http_client is not None:
            http_client.headers.update(har_headers)
        for cookie in har_cookies:
            _set_cookie_both(cfg, jar, http_client, cookie)

    if cfg.login_url:
        payload = dict(parse_qsl(cfg.login_fields or "", keep_blank_values=True))
        login_client = http_client
        temporary = False
        if login_client is None:
            login_client = httpx.AsyncClient(
                headers=headers,
                auth=httpx_auth,
                follow_redirects=True,
                timeout=cfg.timeout,
                proxy=cfg.proxy,
                max_redirects=cfg.redirect_limit,
            )
            temporary = True
        try:
            response = await login_client.request(cfg.login_method.upper(), cfg.login_url, data=payload)
            response.raise_for_status()
            for cookie in login_client.cookies.jar:
                _set_cookie_both(cfg, jar, http_client, {
                    "name": cookie.name,
                    "value": cookie.value,
                    "domain": cookie.domain,
                    "path": cookie.path,
                    "secure": cookie.secure,
                })
        finally:
            if temporary:
                await login_client.aclose()

    return SessionBundle(session=session, http2_client=http_client, auth_attached=auth_attached)


def cookies_for_report(session: aiohttp.ClientSession, http2_client: httpx.AsyncClient | None = None) -> list[dict]:
    merged: dict[tuple[str, str, str], dict] = {}
    for morsel in session.cookie_jar:
        name = morsel.key
        domain = morsel["domain"] or ""
        path = morsel["path"] or "/"
        merged[(name, domain, path)] = {
            "name": name,
            "value": morsel.value,
            "domain": domain,
            "path": path,
            "secure": bool(morsel["secure"]),
            "httponly": bool(morsel["httponly"]),
        }
    if http2_client is not None:
        for cookie in http2_client.cookies.jar:
            merged[(cookie.name, cookie.domain or "", cookie.path or "/")] = {
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain or "",
                "path": cookie.path or "/",
                "secure": bool(cookie.secure),
                "httponly": "httponly" in {str(k).lower() for k in cookie._rest},
            }
    return list(merged.values())
