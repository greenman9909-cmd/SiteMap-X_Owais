from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Awaitable
from urllib.parse import urljoin, urlsplit, parse_qsl
import asyncio
import json
import re

from ..config import Config
from ..intel.fingerprints import fingerprint, dns_fingerprints
from ..intel.graphql_probe import INTROSPECTION_QUERY, extract_operation_names, schema_to_sdl
from ..intel.openapi_probe import COMMON_PATHS, UI_PATHS, extract_openapi
from ..intel.wellknown import WELL_KNOWN_PATHS
from ..mirror.writer import MirrorWriter
from ..parse.css_extract import extract_css
from ..parse.frameworks import extract_framework_routes
from ..parse.html_extract import extract_html
from ..parse.js_extract import extract_js
from ..parse.manifest import extract_manifest
from ..parse.robots import RobotsInfo, parse_robots, robots_allows
from ..parse.sitemap import parse_sitemap
from ..parse.sourcemap import extract_sourcemap
from ..render.playwright_engine import PlaywrightEngine
from ..store.sqlite_store import SQLiteStore
from .fetcher import fetch_url
from .scheduler import RateScheduler
from .session import build_session, cookies_for_report
from .urlutil import classify_url, in_scope, normalize_url, registrable_domain

EventCallback = Callable[[dict[str, Any]], Any]


@dataclass(slots=True)
class QueueItem:
    url: str
    depth: int
    source: str = "seed"


class Crawler:
    def __init__(self, config: Config, event_cb: EventCallback | None = None):
        self.config = config
        self.event_cb = event_cb
        self.out = config.ensure_out()
        self.store = SQLiteStore(self.out / "crawl.sqlite3")
        self.scheduler = RateScheduler(config.rate, config.per_host_rate)
        self.queue: asyncio.Queue[QueueItem] = asyncio.Queue()
        self.seen: set[str] = set()
        self.accepted = 0
        self.completed = 0
        self.failed = 0
        self.stop_event = asyncio.Event()
        self.seed = normalize_url(config.url)
        if not self.seed:
            raise ValueError(f"Invalid HTTP/HTTPS seed URL: {config.url!r}")
        self.seed_host = urlsplit(self.seed).hostname or ""
        self.robots: dict[str, RobotsInfo] = {}
        self._robots_locks: dict[str, asyncio.Lock] = {}
        self.mirror = MirrorWriter(self.out, config.rewrite_js)
        self.renderer: PlaywrightEngine | None = PlaywrightEngine(config) if config.render or config.screenshots else None
        self.http2_client = None
        self.openapi: dict | None = None
        self.graphql_json: dict | None = None
        self.graphql_sdl: str | None = None
        self._include = [re.compile(x) for x in config.include_regex]
        self._exclude = [re.compile(x) for x in config.exclude_regex]
        self.dns_checked: set[str] = set()
        self.sourcemap_sources: set[str] = set()

    def emit(self, kind: str, **data: Any) -> None:
        payload = {"kind": kind, **data}
        if self.event_cb:
            try:
                self.event_cb(payload)
            except Exception:
                pass

    def stop(self) -> None:
        self.stop_event.set()

    def allowed_by_filters(self, url: str) -> bool:
        if self._include and not any(r.search(url) for r in self._include):
            return False
        if any(r.search(url) for r in self._exclude):
            return False
        return True

    async def enqueue(self, url: str, depth: int, source: str = "discovery") -> bool:
        if self.stop_event.is_set() or depth > self.config.depth:
            return False
        try:
            norm = normalize_url(url)
        except Exception:
            return False
        if not norm or not norm.startswith(("http://", "https://")) or not self.allowed_by_filters(norm):
            return False
        if norm in self.seen or self.accepted >= self.config.max_pages:
            return False
        if not in_scope(self.seed, norm, self.config.scope):
            await self.store.add_endpoint(norm, "GET", source, self.seed, .7, "EXTERNAL", query_params=[k for k, _ in parse_qsl(urlsplit(norm).query)])
            return False
        host = urlsplit(norm).hostname or ""
        rinfo = self.robots.get(host)
        if self.config.robots and rinfo and not robots_allows(urlsplit(norm).path or "/", rinfo):
            self.emit("log", level="INFO", message=f"robots.txt skipped {norm}")
            return False
        self.seen.add(norm)
        self.accepted += 1
        await self.store.upsert_url(url, norm, host, depth)
        await self.queue.put(QueueItem(norm, depth, source))
        self.emit("progress", crawled=self.completed, queued=self.queue.qsize(), failed=self.failed)
        return True

    async def _ensure_robots(self, session, target_url: str) -> RobotsInfo:
        host = urlsplit(target_url).hostname or ""
        if not self.config.robots or not host:
            return RobotsInfo()
        if host in self.robots:
            return self.robots[host]
        lock = self._robots_locks.setdefault(host, asyncio.Lock())
        async with lock:
            if host in self.robots:
                return self.robots[host]
            p = urlsplit(target_url)
            base = f"{p.scheme}://{p.netloc}"
            robots_url = base + "/robots.txt"
            result = await fetch_url(session, robots_url, self.config, self.scheduler, http2_client=self.http2_client)
            if result.status and result.status < 400:
                info = parse_robots(result.text, base, self.config.user_agent)
                self.robots[host] = info
                self.mirror.register(robots_url, result.content_type or "text/plain")
                self.mirror.stage(robots_url, result.content_type or "text/plain", result.body, result.text)
                for sm in info.sitemaps:
                    await self.enqueue(sm, 0, "robots:sitemap")
            else:
                info = RobotsInfo()
                self.robots[host] = info
            return info

    async def _bootstrap_robots(self, session) -> None:
        await self._ensure_robots(session, self.seed)

    async def _bootstrap_specials(self) -> None:
        p = urlsplit(self.seed)
        origin = f"{p.scheme}://{p.netloc}"
        for path in ("/sitemap.xml", "/manifest.json", "/manifest.webmanifest") + tuple(WELL_KNOWN_PATHS):
            await self.enqueue(urljoin(origin, path), 0, "bootstrap")
        if self.config.openapi_probe:
            for path in COMMON_PATHS + UI_PATHS:
                await self.enqueue(urljoin(origin, path), 0, "openapi-probe")
        if self.config.graphql_introspect:
            for path in ("/graphql", "/api/graphql", "/v1/graphql"):
                await self.enqueue(urljoin(origin, path), 0, "graphql-probe")

    async def run(self) -> dict[str, Any]:
        await self.store.open()
        bundle = await build_session(self.config)
        session = bundle.session
        self.http2_client = bundle.http2_client
        try:
            if self.renderer:
                await self.renderer.start()
                await self.renderer.set_cookies(cookies_for_report(session, self.http2_client))
            existing = await self.store.seen_urls()
            if self.config.resume:
                self.seen = set(existing)
                pending = await self.store.pending_urls()
                for row in pending:
                    await self.queue.put(QueueItem(row["normalized_url"], int(row.get("depth") or 0), "resume"))
                self.accepted = len(existing)
            await self._bootstrap_robots(session)
            if not self.config.resume or self.queue.empty():
                await self.enqueue(self.seed, 0, "seed")
                await self._bootstrap_specials()
            workers = [asyncio.create_task(self._worker(session, bundle.auth_attached, i)) for i in range(max(1, self.config.concurrency))]
            await self.queue.join()
            self.stop_event.set()
            for w in workers:
                w.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
            await self._post_probes(session, bundle.auth_attached)
            await self.store.replace_cookies(cookies_for_report(session, self.http2_client))
            self.mirror.finalize()
            from ..report.html_report import generate_html_report
            from ..report.json_report import generate_json_report
            from ..report.markdown_report import generate_markdown_report
            from ..report.diff import diff_directories
            formats = {x.lower() for x in self.config.output_format}
            if "json" in formats:
                await generate_json_report(self.store, self.out, self.config)
            if "html" in formats:
                await generate_html_report(self.store, self.out, self.config)
            if "md" in formats:
                await generate_markdown_report(self.store, self.out, self.config)
            await self._write_auxiliary()
            if self.config.diff_against:
                diff_directories(self.config.diff_against, self.out, self.out / "diff.md")
            summary = await self.store.summary()
            self.emit("done", summary=summary, out=str(self.out))
            return summary
        finally:
            if self.renderer:
                await self.renderer.close()
            if self.http2_client is not None:
                await self.http2_client.aclose()
            await session.close()
            await self.store.close()

    async def _worker(self, session, auth_attached: bool, worker_id: int) -> None:
        while True:
            item = await self.queue.get()
            try:
                if self.stop_event.is_set():
                    continue
                await self._process(session, auth_attached, item)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.failed += 1
                self.emit("log", level="ERROR", message=f"{item.url}: {e!r}")
            finally:
                self.queue.task_done()
                self.emit("progress", crawled=self.completed, queued=self.queue.qsize(), failed=self.failed)

    async def _process(self, session, auth_attached: bool, item: QueueItem) -> None:
        host = urlsplit(item.url).hostname or ""
        url_id = await self.store.upsert_url(item.url, normalize_url(item.url), host, item.depth)
        info = await self._ensure_robots(session, item.url)
        if self.config.robots and not robots_allows(urlsplit(item.url).path or "/", info):
            await self.store.mark_fetch(url_id, 0, "", 0, "", "Blocked by robots.txt")
            self.emit("log", level="INFO", message=f"robots.txt skipped {item.url}")
            return
        result = await fetch_url(session, item.url, self.config, self.scheduler, info.crawl_delay if self.config.robots else 0.0, self.http2_client)
        await self.store.mark_fetch(url_id, result.status, result.content_type, len(result.body), result.fetched_at, result.error)
        await self.store.update_endpoint_status(item.url, result.status)
        if result.final_url != item.url:
            await self.store.update_endpoint_status(result.final_url, result.status)
        for hop, (source, target, status) in enumerate(result.redirects):
            await self.store.add_redirect(source, target, hop, status)
        if result.error:
            self.failed += 1
            self.emit("url", url=item.url, status="ERR", type="error", depth=item.depth, time=result.elapsed)
            return
        if host and host not in self.dns_checked:
            self.dns_checked.add(host)
            try:
                for fp in await asyncio.to_thread(dns_fingerprints, host):
                    await self.store.add_fingerprint(fp.category, fp.name, fp.confidence, fp.evidence)
            except Exception as exc:
                self.emit("log", level="WARN", message=f"DNS fingerprint failed for {host}: {exc!r}")
        self.completed += 1
        category = classify_url(result.final_url, item.source)
        if category in {"API ENDPOINT", "GRAPHQL ENDPOINT"}:
            await self.store.add_endpoint(
                result.final_url, "GET", item.source, item.source, .80, category,
                query_params=[k for k, _ in parse_qsl(urlsplit(result.final_url).query)],
                response_status=result.status, auth_hint=auth_attached,
            )
        self.emit("url", url=result.final_url, status=result.status, type=category, depth=item.depth, time=result.elapsed)
        if result.status and result.status >= 400:
            return
        ctype = result.content_type
        textish = any(x in ctype for x in ("html", "css", "javascript", "json", "xml", "text")) or Path(urlsplit(result.final_url).path).suffix.lower() in {".js", ".css", ".map", ".json", ".xml", ".txt"}
        text = result.text if textish else ""
        self.mirror.register(result.final_url, ctype)
        self.mirror.stage(result.final_url, ctype, result.body, text)
        if "html" in ctype:
            parsed = extract_html(text, result.final_url)
            if not parsed.noindex:
                await self.store.save_page(url_id, text, parsed.title, parsed.lang)
            for form in parsed.forms:
                await self.store.add_form(result.final_url, form["action"], form["method"], form["fields"])
                await self.store.add_endpoint(form["action"], form["method"], "form", result.final_url, .98, classify_url(form["action"], "form"), query_params=[k for k,_ in parse_qsl(urlsplit(form["action"]).query)], auth_hint=auth_attached, is_form=True)
            for fp in fingerprint(result.headers, text, ([c.name for c in self.http2_client.cookies.jar] if self.http2_client is not None else [c.key for c in session.cookie_jar]), result.final_url):
                await self.store.add_fingerprint(fp.category, fp.name, fp.confidence, fp.evidence)
            if not parsed.nofollow:
                for url, source in parsed.urls:
                    await self._discover(url, item.depth + 1, source, result.final_url, auth_attached)
                for css in parsed.inline_css:
                    for url, source in extract_css(css, result.final_url):
                        await self._discover(url, item.depth + 1, source, result.final_url, auth_attached)
                for js in parsed.inline_js:
                    await self._handle_js(js, result.final_url, item.depth, auth_attached)
                for url, source in extract_framework_routes(text, result.final_url):
                    await self._discover(url, item.depth + 1, source, result.final_url, auth_attached)
            if self.renderer:
                shot = None
                if self.config.screenshots:
                    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", urlsplit(result.final_url).path.strip("/") or "index")[:160]
                    shot = self.out / "screenshots" / f"{safe}.png"
                rendered = await self.renderer.render(result.final_url, shot)
                if rendered.html and rendered.html != text:
                    rp = extract_html(rendered.html, result.final_url)
                    for url, source in rp.urls:
                        await self._discover(url, item.depth + 1, "render:" + source, result.final_url, auth_attached)
                for url, method, resource_type in rendered.requests:
                    await self.store.add_endpoint(url, method, f"runtime:{resource_type}", result.final_url, .99, classify_url(url, "fetch"), query_params=[k for k,_ in parse_qsl(urlsplit(url).query)], auth_hint=auth_attached)
                    await self.enqueue(url, item.depth + 1, f"runtime:{resource_type}")
                for ws in rendered.websockets:
                    await self.store.add_endpoint(ws, "GET", "runtime:websocket", result.final_url, 1.0, "WEBSOCKET URL", auth_hint=auth_attached)
                for ws_url, direction, message_type, size in rendered.ws_messages:
                    await self.store.add_ws_message(ws_url, direction, message_type, size)
                for err in rendered.console_errors:
                    self.emit("log", level="WARN", message=f"console {result.final_url}: {err}")
        elif "css" in ctype or result.final_url.lower().endswith(".css"):
            await self.store.save_asset(url_id, result.body, ctype)
            for url, source in extract_css(text, result.final_url):
                await self._discover(url, item.depth + 1, source, result.final_url, auth_attached)
        elif "javascript" in ctype or result.final_url.lower().endswith((".js", ".mjs")):
            await self.store.save_asset(url_id, result.body, ctype)
            await self._handle_js(text, result.final_url, item.depth, auth_attached)
            map_url = result.final_url + ".map"
            await self.enqueue(map_url, item.depth + 1, "source-map-guess")
        elif result.final_url.lower().endswith(".map"):
            await self.store.save_asset(url_id, result.body, ctype)
            sources, urls = extract_sourcemap(text, result.final_url)
            for u in sources:
                self.sourcemap_sources.add(u)
                await self.store.add_endpoint(u, "GET", "sourcemap:source", result.final_url, .45, classify_url(u))
            for u in urls:
                await self._discover(u, item.depth + 1, "sourcemap:url", result.final_url, auth_attached)
        elif "xml" in ctype or result.final_url.lower().endswith(".xml"):
            await self.store.save_asset(url_id, result.body, ctype)
            urls, maps = parse_sitemap(text, result.final_url)
            for u in urls + maps:
                await self.enqueue(u, item.depth + 1, "sitemap")
        elif "json" in ctype or result.final_url.lower().endswith((".json", ".webmanifest")):
            await self.store.save_asset(url_id, result.body, ctype)
            for u, source in extract_manifest(text, result.final_url):
                await self._discover(u, item.depth + 1, source, result.final_url, auth_attached)
            openapi, endpoints = extract_openapi(text, result.final_url)
            if openapi:
                self.openapi = openapi
                for u, method in endpoints:
                    await self.store.add_endpoint(u, method, "openapi", result.final_url, 1.0, "API ENDPOINT", auth_hint=auth_attached)
        else:
            await self.store.save_asset(url_id, result.body, ctype)
            if text:
                for m in re.finditer(r"https?://[^\s'\"<>]+", text):
                    await self._discover(m.group(0), item.depth + 1, "text:url", result.final_url, auth_attached)

    async def _discover(self, url: str, depth: int, source: str, discovered_from: str, auth_attached: bool) -> None:
        cat = classify_url(url, source.split(":",1)[0])
        if url.startswith(("http://", "https://")) and registrable_domain(url) != registrable_domain(self.seed):
            cat = "EXTERNAL"
        if source != "form" and cat in {"API ENDPOINT", "GRAPHQL ENDPOINT", "WEBSOCKET URL"}:
            await self.store.add_endpoint(url, "GET", source, discovered_from, .85, cat, query_params=[k for k,_ in parse_qsl(urlsplit(url).query)], auth_hint=auth_attached)
        if url.startswith(("http://", "https://")):
            await self.enqueue(url, depth, source)
        elif url.startswith(("ws://", "wss://")):
            await self.store.add_endpoint(url, "GET", source, discovered_from, .98, "WEBSOCKET URL", auth_hint=auth_attached)

    async def _handle_js(self, text: str, source_url: str, depth: int, auth_attached: bool) -> None:
        for hit in extract_js(text, source_url):
            category = "WEBSOCKET URL" if hit.kind == "websocket" else classify_url(hit.url, hit.kind)
            await self.store.add_endpoint(hit.url, hit.method, hit.kind, source_url, hit.confidence, category, line=hit.line,
                                          query_params=[k for k,_ in parse_qsl(urlsplit(hit.url).query)], auth_hint=auth_attached)
            if hit.url.startswith(("http://", "https://")):
                await self.enqueue(hit.url, depth + 1, hit.kind)
        for op_type, name in extract_operation_names(text):
            await self.store.add_endpoint(f"graphql-operation:{op_type}:{name}", op_type.upper(), "js-operation", source_url, .7, "GRAPHQL OPERATION")
        for url, source in extract_framework_routes(text, source_url):
            await self._discover(url, depth + 1, source, source_url, auth_attached)

    async def _post_probes(self, session, auth_attached: bool) -> None:
        if not self.config.graphql_introspect:
            return
        endpoints = await self.store.rows("endpoints")
        gqls = [e["url"] for e in endpoints if e.get("category") == "GRAPHQL ENDPOINT" and str(e.get("url","")).startswith(("http://", "https://"))]
        for url in dict.fromkeys(gqls):
            try:
                await self.scheduler.wait(url)
                if self.http2_client is not None:
                    resp2 = await self.http2_client.post(url, json={"query": INTROSPECTION_QUERY})
                    if resp2.status_code >= 400:
                        continue
                    data = resp2.json()
                else:
                    async with session.post(url, json={"query": INTROSPECTION_QUERY}, proxy=self.config.proxy) as resp:
                        if resp.status >= 400:
                            continue
                        data = await resp.json(content_type=None)
                if isinstance(data, dict) and data.get("data", {}).get("__schema"):
                    self.graphql_json = data
                    self.graphql_sdl = schema_to_sdl(data)
                    (self.out / "graphql_schema.json").write_text(json.dumps(data, indent=2), "utf-8")
                    (self.out / "graphql_schema.graphql").write_text(self.graphql_sdl, "utf-8")
                    await self._record_graphql_schema(data, url, auth_attached)
                    break
            except Exception as e:
                self.emit("log", level="WARN", message=f"GraphQL introspection failed at {url}: {e!r}")

    async def _record_graphql_schema(self, data: dict[str, Any], endpoint: str, auth_attached: bool) -> None:
        schema = data.get("data", {}).get("__schema", {})
        type_map = {t.get("name"): t for t in schema.get("types", []) or [] if isinstance(t, dict) and t.get("name")}
        for kind_key, op_kind in (("queryType", "query"), ("mutationType", "mutation"), ("subscriptionType", "subscription")):
            root_name = (schema.get(kind_key) or {}).get("name")
            root = type_map.get(root_name) or {}
            for field in root.get("fields") or []:
                name = field.get("name")
                if name:
                    await self.store.add_endpoint(f"graphql-operation:{op_kind}:{name}", op_kind.upper(), "graphql-introspection", endpoint, 1.0, "GRAPHQL OPERATION", auth_hint=auth_attached)
        for t in schema.get("types", []) or []:
            name = t.get("name")
            kind = t.get("kind")
            if not name or name.startswith("__"):
                continue
            category = "GRAPHQL INPUT" if kind == "INPUT_OBJECT" else "GRAPHQL TYPE"
            await self.store.add_endpoint(f"graphql-{kind.lower()}:{name}", "SCHEMA", "graphql-introspection", endpoint, 1.0, category, auth_hint=auth_attached)

    async def _write_auxiliary(self) -> None:
        endpoints = await self.store.rows("endpoints")
        urls = sorted({e["url"] for e in endpoints if str(e.get("url","")).startswith(("http://", "https://", "ws://", "wss://"))})
        (self.out / "endpoints.txt").write_text("\n".join(urls) + ("\n" if urls else ""), "utf-8")
        (self.out / "endpoints.json").write_text(json.dumps(endpoints, indent=2), "utf-8")
        external = sorted({e["url"] for e in endpoints if e.get("category") == "EXTERNAL"})
        (self.out / "external_hosts.txt").write_text("\n".join(sorted({urlsplit(x).netloc for x in external})) + ("\n" if external else ""), "utf-8")
        if self.sourcemap_sources:
            (self.out / "sourcemap_sources.txt").write_text("\n".join(sorted(self.sourcemap_sources)) + "\n", "utf-8")
        if self.openapi:
            (self.out / "openapi.json").write_text(json.dumps(self.openapi, indent=2), "utf-8")
        cookies = await self.store.rows("cookies")
        lines = ["# Netscape HTTP Cookie File"]
        for c in cookies:
            lines.append("\t".join([c.get("domain") or "", "TRUE" if str(c.get("domain","")).startswith(".") else "FALSE", c.get("path") or "/", "TRUE" if c.get("secure") else "FALSE", "0", c.get("name") or "", c.get("value") or ""]))
        (self.out / "cookies.txt").write_text("\n".join(lines) + "\n", "utf-8")
