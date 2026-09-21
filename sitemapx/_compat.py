from __future__ import annotations

"""Small runtime fallbacks used only when optional install-time dependencies are absent.

The project still declares and prefers its normal dependencies. These shims make core CLI
verification possible in constrained/offline environments.
"""

import sqlite3
from urllib.parse import urlsplit


class AsyncCursor:
    def __init__(self, cursor: sqlite3.Cursor):
        self._cursor = cursor

    async def fetchone(self):
        return self._cursor.fetchone()

    async def fetchall(self):
        return self._cursor.fetchall()


class AsyncSQLiteConnection:
    def __init__(self, path):
        self._conn = sqlite3.connect(path)

    @property
    def row_factory(self):
        return self._conn.row_factory

    @row_factory.setter
    def row_factory(self, value):
        self._conn.row_factory = value

    async def execute(self, sql, parameters=()):
        return AsyncCursor(self._conn.execute(sql, parameters))

    async def executescript(self, sql):
        self._conn.executescript(sql)

    async def commit(self):
        self._conn.commit()

    async def close(self):
        self._conn.close()


class AioSQLiteShim:
    Row = sqlite3.Row
    Connection = AsyncSQLiteConnection

    @staticmethod
    async def connect(path):
        return AsyncSQLiteConnection(path)


# A pragmatic public-suffix fallback for same-domain scoping when tldextract is not installed.
# It intentionally covers common multi-label public suffixes without trying to replace the PSL.
_COMMON_TWO_LEVEL_SUFFIXES = {
    "co.uk", "org.uk", "ac.uk", "gov.uk",
    "com.au", "net.au", "org.au", "edu.au",
    "co.nz", "org.nz", "com.br", "com.mx",
    "co.jp", "ne.jp", "co.kr", "co.in", "firm.in", "net.in", "org.in",
    "com.cn", "com.hk", "com.sg", "com.tr", "com.pk", "com.sa",
    "com.es", "com.pt",
}


def fallback_registrable_domain(url: str) -> str:
    host = (urlsplit(url).hostname or "").strip(".").lower()
    if not host:
        return ""
    # IPs and localhost-like names should remain literal.
    try:
        import ipaddress
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    suffix2 = ".".join(parts[-2:])
    if suffix2 in _COMMON_TWO_LEVEL_SUFFIXES and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])
