from __future__ import annotations

from pathlib import Path
import json

from ..config import Config
from ..store.sqlite_store import SQLiteStore


async def collect_report(store: SQLiteStore, config: Config) -> dict:
    urls = await store.rows("urls")
    pages = await store.rows("pages")
    assets = await store.rows("assets")
    for a in assets:
        a.pop("body_blob", None)
    return {
        "tool": "SiteMap-X",
        "version": "0.1.0",
        "config": config.as_jsonable(),
        "summary": await store.summary(),
        "urls": urls,
        "pages": pages,
        "assets": assets,
        "endpoints": await store.rows("endpoints"),
        "fingerprints": await store.rows("fingerprints"),
        "forms": await store.rows("forms"),
        "cookies": [{**c, "value": c.get("value", "")} for c in await store.rows("cookies")],
        "redirects": await store.rows("redirects"),
    }


async def generate_json_report(store: SQLiteStore, out: Path, config: Config) -> Path:
    data = await collect_report(store, config)
    path = Path(out) / "report.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
    return path
