from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit
import json

from ..config import Config
from ..store.sqlite_store import SQLiteStore


def esc(value) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


async def generate_markdown_report(store: SQLiteStore, out: Path, config: Config) -> Path:
    summary = await store.summary()
    endpoints = await store.rows("endpoints")
    fps = await store.rows("fingerprints")
    forms = await store.rows("forms")
    urls = await store.rows("urls")
    lines = [
        "# SiteMap-X Report", "", f"Seed: `{config.url}`", "", "## Overview", "",
        "| Metric | Count |", "|---|---:|",
    ]
    for key, value in summary.items():
        lines.append(f"| {esc(key)} | {value} |")
    lines += ["", "## Endpoints", "", "| Method | Category | URL | Source |", "|---|---|---|---|"]
    for e in endpoints[:5000]:
        lines.append(f"| {esc(e.get('method'))} | {esc(e.get('category'))} | `{esc(e.get('url'))}` | {esc(e.get('source'))} |")
    lines += ["", "## Fingerprints", "", "| Category | Technology | Confidence | Evidence |", "|---|---|---:|---|"]
    for f in fps:
        lines.append(f"| {esc(f.get('category'))} | {esc(f.get('name'))} | {float(f.get('confidence') or 0):.2f} | {esc(f.get('evidence'))} |")
    lines += ["", "## Forms", "", "| Page | Method | Action | Fields |", "|---|---|---|---|"]
    for f in forms:
        try:
            count = len(json.loads(f.get("fields_json") or "[]"))
        except Exception:
            count = 0
        lines.append(f"| `{esc(f.get('page_url'))}` | {esc(f.get('method'))} | `{esc(f.get('action'))}` | {count} |")
    external_hosts = sorted({urlsplit(e.get("url", "")).netloc for e in endpoints if e.get("category") == "EXTERNAL"})
    lines += ["", "## External Hosts", ""] + [f"- `{esc(h)}`" for h in external_hosts]
    path = Path(out) / "report.md"
    path.write_text("\n".join(lines) + "\n", "utf-8")
    return path
