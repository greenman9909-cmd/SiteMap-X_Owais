from __future__ import annotations

from pathlib import Path
import html
import json

from ..config import Config
from ..store.sqlite_store import SQLiteStore
from .json_report import collect_report


def _table(rows: list[dict], cols: list[tuple[str, str]]) -> str:
    head = "".join(f"<th>{html.escape(label)}</th>" for _, label in cols)
    body = []
    for row in rows:
        cells = []
        for key, _ in cols:
            value = row.get(key, "")
            if key == "confidence":
                try: value = f"{float(value):.2f}"
                except Exception: pass
            cells.append(f"<td>{html.escape(str(value if value is not None else ''))}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f'<div class="tablewrap"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


async def generate_html_report(store: SQLiteStore, out: Path, config: Config) -> Path:
    data = await collect_report(store, config)
    tabs = {
        "Overview": "<div class=cards>" + "".join(f"<div class=card><b>{html.escape(k)}</b><span>{v}</span></div>" for k,v in data["summary"].items()) + "</div>",
        "Endpoints": _table(data["endpoints"], [("method","Method"),("category","Category"),("url","URL"),("source","Source"),("discovered_from","Found in"),("line","Line"),("response_status","Status")]),
        "Pages": _table(data["urls"], [("status","Status"),("url","URL"),("depth","Depth"),("content_type","Content-Type"),("size","Bytes")]),
        "Assets": _table(data["assets"], [("url_id","URL ID"),("mime","MIME"),("size","Bytes")]),
        "Forms": _table(data["forms"], [("page_url","Page"),("method","Method"),("action","Action"),("fields_json","Fields")]),
        "Fingerprints": _table(data["fingerprints"], [("category","Category"),("name","Technology"),("confidence","Confidence"),("evidence","Evidence")]),
        "GraphQL": _table([e for e in data["endpoints"] if "GRAPHQL" in str(e.get("category","")) or str(e.get("url","")).startswith("graphql-operation:")], [("method","Type"),("url","Operation / URL"),("source","Source")]),
        "External Hosts": _table([e for e in data["endpoints"] if e.get("category") == "EXTERNAL"], [("url","URL"),("discovered_from","Found in")]),
    }
    buttons = "".join(f'<button class="tabbtn" data-tab="t{i}">{html.escape(name)}</button>' for i,name in enumerate(tabs))
    panels = "".join(f'<section id="t{i}" class="tab">{content}</section>' for i,content in enumerate(tabs.values()))
    doc = f'''<!doctype html><html><head><meta charset="utf-8"><title>SiteMap-X Report</title>
<style>
:root{{color-scheme:dark;font-family:Inter,system-ui,sans-serif}}body{{margin:0;background:#0c1016;color:#e7edf6}}header{{padding:22px 28px;background:#111824;position:sticky;top:0;z-index:2;border-bottom:1px solid #263143}}h1{{margin:0 0 12px}}#search{{width:min(620px,90vw);padding:10px 12px;background:#0b111b;color:#fff;border:1px solid #33445b;border-radius:8px}}nav{{padding:12px 28px;display:flex;gap:8px;flex-wrap:wrap}}button{{background:#172235;color:#dce8f7;border:1px solid #30415a;border-radius:8px;padding:8px 12px;cursor:pointer}}button.active{{background:#2e5b95}}main{{padding:0 28px 40px}}.tab{{display:none}}.tab.active{{display:block}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}}.card{{padding:18px;background:#121a26;border:1px solid #243146;border-radius:12px;display:flex;justify-content:space-between}}.tablewrap{{overflow:auto;max-height:72vh;border:1px solid #243146;border-radius:10px}}table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{padding:8px 10px;border-bottom:1px solid #202c3d;text-align:left;vertical-align:top}}th{{position:sticky;top:0;background:#172131;cursor:pointer}}tr:hover{{background:#141e2b}}td{{max-width:620px;word-break:break-word}}code{{font-family:ui-monospace,monospace}}
</style></head><body><header><h1>SiteMap-X Report</h1><div>{html.escape(config.url)}</div><br><input id="search" placeholder="Search all tables..."></header><nav>{buttons}</nav><main>{panels}</main>
<script>
const btns=[...document.querySelectorAll('.tabbtn')], tabs=[...document.querySelectorAll('.tab')];
function openTab(i){{btns.forEach((b,n)=>b.classList.toggle('active',n===i));tabs.forEach((t,n)=>t.classList.toggle('active',n===i));}} openTab(0);
btns.forEach((b,i)=>b.onclick=()=>openTab(i));
document.querySelector('#search').addEventListener('input',e=>{{let q=e.target.value.toLowerCase();document.querySelectorAll('tbody tr').forEach(r=>r.style.display=r.innerText.toLowerCase().includes(q)?'':'none')}});
document.querySelectorAll('th').forEach((th,idx)=>th.onclick=()=>{{let table=th.closest('table'),body=table.tBodies[0],col=[...th.parentNode.children].indexOf(th),rows=[...body.rows];let asc=th.dataset.asc!=='1';rows.sort((a,b)=>a.cells[col].innerText.localeCompare(b.cells[col].innerText,undefined,{{numeric:true}})*(asc?1:-1));rows.forEach(r=>body.appendChild(r));th.dataset.asc=asc?'1':'0';}});
</script></body></html>'''
    path = Path(out) / "report.html"
    path.write_text(doc, "utf-8")
    return path
