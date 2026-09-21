from __future__ import annotations

import asyncio
from PySide6.QtCore import QThread, Signal

from ..config import Config
from ..core.crawler import Crawler


class CrawlWorker(QThread):
    event = Signal(dict)
    failed = Signal(str)

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.crawler: Crawler | None = None

    def run(self) -> None:
        async def main():
            self.crawler = Crawler(self.config, self.event.emit)
            await self.crawler.run()
        try:
            asyncio.run(main())
        except Exception as exc:
            self.failed.emit(repr(exc))

    def request_stop(self) -> None:
        if self.crawler:
            self.crawler.stop()
