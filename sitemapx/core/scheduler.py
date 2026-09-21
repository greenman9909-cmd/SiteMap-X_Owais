from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from urllib.parse import urlsplit


class RateScheduler:
    """Global + per-host pacing with lightweight retry backoff support."""

    def __init__(self, global_rate: float, per_host_rate: float):
        self.global_interval = 1.0 / global_rate if global_rate > 0 else 0.0
        self.host_interval = 1.0 / per_host_rate if per_host_rate > 0 else 0.0
        self._global_lock = asyncio.Lock()
        self._host_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._last_global = 0.0
        self._last_host: dict[str, float] = {}
        self._backoff_until: dict[str, float] = {}

    async def wait(self, url_or_host: str, extra_delay: float = 0.0) -> None:
        host = urlsplit(url_or_host).hostname or url_or_host
        backoff = self._backoff_until.get(host, 0.0) - time.monotonic()
        if backoff > 0:
            await asyncio.sleep(backoff)
        if extra_delay > 0:
            await asyncio.sleep(extra_delay)

        async with self._global_lock:
            now = time.monotonic()
            delay = self.global_interval - (now - self._last_global)
            if delay > 0:
                await asyncio.sleep(delay)
            self._last_global = time.monotonic()

        async with self._host_locks[host]:
            now = time.monotonic()
            delay = self.host_interval - (now - self._last_host.get(host, 0.0))
            if delay > 0:
                await asyncio.sleep(delay)
            self._last_host[host] = time.monotonic()

    def backoff(self, url_or_host: str, seconds: float) -> None:
        host = urlsplit(url_or_host).hostname or url_or_host
        self._backoff_until[host] = max(self._backoff_until.get(host, 0.0), time.monotonic() + max(0.0, seconds))


# Compatibility alias.
RateLimiter = RateScheduler
