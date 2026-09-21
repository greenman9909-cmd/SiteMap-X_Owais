from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import sqlite3

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS urls(
 id INTEGER PRIMARY KEY, url TEXT NOT NULL, normalized_url TEXT UNIQUE NOT NULL, host TEXT,
 depth INTEGER, status INTEGER, content_type TEXT, size INTEGER, fetched_at TEXT, error TEXT
);
CREATE TABLE IF NOT EXISTS pages(id INTEGER PRIMARY KEY, url_id INTEGER, html TEXT, title TEXT, lang TEXT);
CREATE TABLE IF NOT EXISTS assets(id INTEGER PRIMARY KEY, url_id INTEGER, body_blob BLOB, mime TEXT, size INTEGER);
CREATE TABLE IF NOT EXISTS endpoints(
 id INTEGER PRIMARY KEY, url TEXT, method TEXT, source TEXT, discovered_from TEXT,
 confidence REAL, category TEXT, line INTEGER, query_params TEXT, response_status INTEGER,
 auth_hint INTEGER DEFAULT 0, is_form INTEGER DEFAULT 0,
 UNIQUE(url, method, source, discovered_from)
);
CREATE TABLE IF NOT EXISTS fingerprints(id INTEGER PRIMARY KEY, category TEXT, name TEXT, confidence REAL, evidence TEXT,
 UNIQUE(category,name,evidence));
CREATE TABLE IF NOT EXISTS forms(id INTEGER PRIMARY KEY, page_url TEXT, action TEXT, method TEXT, fields_json TEXT);
CREATE TABLE IF NOT EXISTS cookies(id INTEGER PRIMARY KEY, name TEXT, value TEXT, domain TEXT, path TEXT, secure INTEGER, httponly INTEGER);
CREATE TABLE IF NOT EXISTS ws_messages(id INTEGER PRIMARY KEY, ws_url TEXT, direction TEXT, type TEXT, size INTEGER);
CREATE TABLE IF NOT EXISTS redirects(id INTEGER PRIMARY KEY, source_url TEXT, target_url TEXT, hop INTEGER, status INTEGER);
CREATE INDEX IF NOT EXISTS idx_urls_status ON urls(status);
CREATE INDEX IF NOT EXISTS idx_endpoints_url ON endpoints(url);
"""


class SQLiteStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.db: sqlite3.Connection | None = None

    async def open(self) -> "SQLiteStore":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.db.commit()
        return self

    async def close(self) -> None:
        if self.db:
            self.db.commit()
            self.db.close()
            self.db = None

    async def seen_urls(self) -> set[str]:
        cur = self.db.execute("SELECT normalized_url FROM urls")
        return {r[0] for r in cur.fetchall()}

    async def pending_urls(self) -> list[dict[str, Any]]:
        cur = self.db.execute("SELECT url, normalized_url, depth FROM urls WHERE status IS NULL AND error IS NULL ORDER BY id")
        return [dict(r) for r in cur.fetchall()]

    async def upsert_url(self, url: str, normalized: str, host: str, depth: int) -> int:
        self.db.execute(
            "INSERT INTO urls(url,normalized_url,host,depth) VALUES(?,?,?,?) ON CONFLICT(normalized_url) DO UPDATE SET depth=MIN(depth,excluded.depth)",
            (url, normalized, host, depth),
        )
        self.db.commit()
        row = self.db.execute("SELECT id FROM urls WHERE normalized_url=?", (normalized,)).fetchone()
        return int(row[0])

    async def mark_fetch(self, url_id: int, status: int | None, content_type: str | None, size: int, fetched_at: str, error: str | None = None) -> None:
        self.db.execute("UPDATE urls SET status=?,content_type=?,size=?,fetched_at=?,error=? WHERE id=?", (status, content_type, size, fetched_at, error, url_id))
        self.db.commit()

    async def save_page(self, url_id: int, html: str, title: str = "", lang: str = "") -> None:
        self.db.execute("DELETE FROM pages WHERE url_id=?", (url_id,))
        self.db.execute("INSERT INTO pages(url_id,html,title,lang) VALUES(?,?,?,?)", (url_id, html, title, lang))
        self.db.commit()

    async def save_asset(self, url_id: int, body: bytes, mime: str) -> None:
        self.db.execute("DELETE FROM assets WHERE url_id=?", (url_id,))
        self.db.execute("INSERT INTO assets(url_id,body_blob,mime,size) VALUES(?,?,?,?)", (url_id, body, mime, len(body)))
        self.db.commit()

    async def add_endpoint(self, url: str, method: str = "GET", source: str = "", discovered_from: str = "", confidence: float = .8,
                           category: str = "API ENDPOINT", line: int | None = None, query_params: list[str] | None = None,
                           response_status: int | None = None, auth_hint: bool = False, is_form: bool = False) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO endpoints(url,method,source,discovered_from,confidence,category,line,query_params,response_status,auth_hint,is_form) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (url, method.upper(), source, discovered_from, confidence, category, line, json.dumps(query_params or []), response_status, int(auth_hint), int(is_form)),
        )
        self.db.commit()

    async def update_endpoint_status(self, url: str, status: int | None) -> None:
        self.db.execute("UPDATE endpoints SET response_status=? WHERE url=?", (status, url))
        self.db.commit()

    async def add_form(self, page_url: str, action: str, method: str, fields: list[dict[str, Any]]) -> None:
        self.db.execute("INSERT INTO forms(page_url,action,method,fields_json) VALUES(?,?,?,?)", (page_url, action, method.upper(), json.dumps(fields)))
        self.db.commit()

    async def add_fingerprint(self, category: str, name: str, confidence: float, evidence: str) -> None:
        self.db.execute("INSERT OR IGNORE INTO fingerprints(category,name,confidence,evidence) VALUES(?,?,?,?)", (category, name, confidence, evidence[:2000]))
        self.db.commit()

    async def add_ws_message(self, ws_url: str, direction: str, message_type: str, size: int) -> None:
        self.db.execute("INSERT INTO ws_messages(ws_url,direction,type,size) VALUES(?,?,?,?)", (ws_url, direction, message_type, int(size)))
        self.db.commit()

    async def add_redirect(self, source_url: str, target_url: str, hop: int, status: int) -> None:
        self.db.execute("INSERT INTO redirects(source_url,target_url,hop,status) VALUES(?,?,?,?)", (source_url, target_url, hop, status))
        self.db.commit()

    async def replace_cookies(self, cookies: list[dict[str, Any]]) -> None:
        self.db.execute("DELETE FROM cookies")
        for c in cookies:
            self.db.execute("INSERT INTO cookies(name,value,domain,path,secure,httponly) VALUES(?,?,?,?,?,?)", (
                c.get("name", ""), c.get("value", ""), c.get("domain", ""), c.get("path", "/"), int(bool(c.get("secure"))), int(bool(c.get("httponly") or c.get("httpOnly")))
            ))
        self.db.commit()

    async def rows(self, table: str) -> list[dict[str, Any]]:
        if table not in {"urls", "pages", "assets", "endpoints", "fingerprints", "forms", "cookies", "ws_messages", "redirects"}:
            raise ValueError(table)
        cur = self.db.execute(f"SELECT * FROM {table}")
        return [dict(r) for r in cur.fetchall()]

    async def summary(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for table in ("urls", "pages", "assets", "endpoints", "fingerprints", "forms"):
            result[table] = int(self.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        return result
