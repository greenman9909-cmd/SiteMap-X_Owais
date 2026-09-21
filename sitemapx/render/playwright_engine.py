from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from ..config import Config


@dataclass(slots=True)
class RenderResult:
    html: str
    requests: list[tuple[str, str, str]] = field(default_factory=list)
    websockets: list[str] = field(default_factory=list)
    ws_messages: list[tuple[str, str, str, int]] = field(default_factory=list)
    console_errors: list[str] = field(default_factory=list)
    frames: list[tuple[str, str, str, int]] = field(default_factory=list)
    screenshot: Path | None = None


class PlaywrightEngine:
    def __init__(self, config: Config):
        self.config = config
        self._pw = None
        self._browser = None
        self._context = None

    async def start(self) -> None:
        from playwright.async_api import async_playwright
        self._pw = await async_playwright().start()
        launch_args = {"headless": True}
        if self.config.proxy:
            launch_args["proxy"] = {"server": self.config.proxy}
        self._browser = await self._pw.chromium.launch(**launch_args)
        context_args = {"user_agent": self.config.user_agent}
        if self.config.storage_state and self.config.storage_state.exists():
            context_args["storage_state"] = str(self.config.storage_state)
        if self.config.basic:
            username, _, password = self.config.basic.partition(":")
            context_args["http_credentials"] = {"username": username, "password": password}
        self._context = await self._browser.new_context(**context_args)
        if self.config.headers:
            headers = {}
            for item in self.config.headers:
                if ":" in item:
                    k, v = item.split(":", 1)
                    headers[k.strip()] = v.strip()
            await self._context.set_extra_http_headers(headers)

    async def set_cookies(self, cookies: list[dict]) -> None:
        if not self._context:
            await self.start()
        seed = urlsplit(self.config.url)
        origin = f"{seed.scheme}://{seed.netloc}/"
        prepared = []
        for c in cookies:
            name = str(c.get("name") or "")
            if not name:
                continue
            row = {
                "name": name,
                "value": str(c.get("value") or ""),
                "path": str(c.get("path") or "/"),
                "secure": bool(c.get("secure")),
                "httpOnly": bool(c.get("httponly") or c.get("httpOnly")),
            }
            domain = str(c.get("domain") or "").strip()
            if domain:
                row["domain"] = domain
            else:
                row.pop("path", None)
                row["url"] = origin
            prepared.append(row)
        if prepared:
            await self._context.add_cookies(prepared)

    async def close(self) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    async def render(self, url: str, screenshot_path: Path | None = None) -> RenderResult:
        if not self._context:
            await self.start()
        page = await self._context.new_page()
        requests: list[tuple[str, str, str]] = []
        websockets: list[str] = []
        ws_messages: list[tuple[str, str, str, int]] = []
        errors: list[str] = []
        page.on("request", lambda r: requests.append((r.url, r.method, r.resource_type)))

        def on_websocket(ws) -> None:
            websockets.append(ws.url)

            def record(direction: str, payload) -> None:
                kind = "binary" if isinstance(payload, (bytes, bytearray, memoryview)) else "text"
                try:
                    size = len(payload)
                except Exception:
                    size = len(str(payload))
                ws_messages.append((ws.url, direction, kind, size))

            ws.on("framesent", lambda payload: record("sent", payload))
            ws.on("framereceived", lambda payload: record("received", payload))

        page.on("websocket", on_websocket)
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        try:
            await page.goto(url, wait_until="networkidle", timeout=int(self.config.timeout * 1000))
            if self.config.render_wait_ms:
                await page.wait_for_timeout(self.config.render_wait_ms)
            html = await page.content()
            shot = None
            if screenshot_path:
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(screenshot_path), full_page=True)
                shot = screenshot_path
            return RenderResult(
                html=html,
                requests=requests,
                websockets=websockets,
                ws_messages=ws_messages,
                console_errors=errors,
                screenshot=shot,
            )
        finally:
            await page.close()
