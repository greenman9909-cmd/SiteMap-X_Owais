from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import asyncio
import time

import aiohttp
import httpx

from ..config import Config
from .scheduler import RateScheduler


@dataclass(slots=True)
class FetchResult:
    url: str
    final_url: str
    status: int
    headers: dict[str, str]
    body: bytes
    content_type: str
    redirects: list[tuple[str, str, int]] = field(default_factory=list)
    error: str | None = None
    fetched_at: str = ""
    elapsed: float = 0.0

    @property
    def text(self) -> str:
        charset = "utf-8"
        ctype = self.headers.get("Content-Type", self.headers.get("content-type", ""))
        if "charset=" in ctype:
            charset = ctype.split("charset=", 1)[1].split(";", 1)[0].strip().strip('"')
        try:
            return self.body.decode(charset, errors="replace")
        except LookupError:
            return self.body.decode("utf-8", errors="replace")


def _retry_delay(headers: dict[str, str], attempt: int) -> float:
    raw = headers.get("Retry-After") or headers.get("retry-after")
    if raw:
        raw = raw.strip()
        try:
            return min(float(raw), 60.0)
        except ValueError:
            try:
                dt = parsedate_to_datetime(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return max(0.0, min((dt - datetime.now(timezone.utc)).total_seconds(), 60.0))
            except Exception:
                pass
    return min(2 ** attempt, 10.0)


def _content_type(headers: dict[str, str]) -> str:
    return (headers.get("Content-Type") or headers.get("content-type") or "").split(";", 1)[0].strip().lower()


def _redirects_from_aiohttp(resp: aiohttp.ClientResponse) -> list[tuple[str, str, int]]:
    hops = []
    history = list(resp.history)
    for idx, previous in enumerate(history):
        target = history[idx + 1].url if idx + 1 < len(history) else resp.url
        hops.append((str(previous.url), str(target), int(previous.status)))
    return hops


def _redirects_from_httpx(resp: httpx.Response) -> list[tuple[str, str, int]]:
    hops = []
    history = list(resp.history)
    for idx, previous in enumerate(history):
        target = history[idx + 1].url if idx + 1 < len(history) else resp.url
        hops.append((str(previous.url), str(target), int(previous.status_code)))
    return hops


async def fetch_url(session: aiohttp.ClientSession, url: str, config: Config, scheduler: RateScheduler, extra_delay: float = 0.0, http2_client: httpx.AsyncClient | None = None) -> FetchResult:
    started = time.perf_counter()
    fetched_at = datetime.now(timezone.utc).isoformat()
    last_error = "fetch failed"
    for attempt in range(4):
        await scheduler.wait(url, extra_delay if attempt == 0 else 0.0)
        try:
            if http2_client is not None:
                response = await http2_client.get(url)
                headers = dict(response.headers)
                status = int(response.status_code)
                body = response.content
                if status in {429, 503} or 500 <= status < 600:
                    if attempt < 3:
                        delay = _retry_delay(headers, attempt)
                        scheduler.backoff(url, delay)
                        await asyncio.sleep(delay)
                        continue
                return FetchResult(url=url, final_url=str(response.url), status=status, headers=headers, body=body, content_type=_content_type(headers), redirects=_redirects_from_httpx(response), fetched_at=fetched_at, elapsed=time.perf_counter() - started)
            async with session.get(url, allow_redirects=True, max_redirects=config.redirect_limit, proxy=config.proxy) as response:
                body = await response.read()
                headers = dict(response.headers)
                status = int(response.status)
                if status in {429, 503} or 500 <= status < 600:
                    if attempt < 3:
                        delay = _retry_delay(headers, attempt)
                        scheduler.backoff(url, delay)
                        await asyncio.sleep(delay)
                        continue
                return FetchResult(url=url, final_url=str(response.url), status=status, headers=headers, body=body, content_type=_content_type(headers), redirects=_redirects_from_aiohttp(response), fetched_at=fetched_at, elapsed=time.perf_counter() - started)
        except (aiohttp.ClientError, httpx.HTTPError, asyncio.TimeoutError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < 3:
                delay = min(2 ** attempt, 10.0)
                scheduler.backoff(url, delay)
                await asyncio.sleep(delay)
                continue
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            break
    return FetchResult(url=url, final_url=url, status=0, headers={}, body=b"", content_type="", error=last_error, fetched_at=fetched_at, elapsed=time.perf_counter() - started)


async def fetch(session: aiohttp.ClientSession, url: str, limiter: RateScheduler, *, proxy: str | None = None, retries: int = 3) -> FetchResult:
    config = Config(url=url, proxy=proxy)
    return await fetch_url(session, url, config, limiter)
