from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..core.urlutil import absolutize


@dataclass(slots=True)
class HTMLExtraction:
    urls: list[tuple[str, str]] = field(default_factory=list)
    forms: list[dict] = field(default_factory=list)
    inline_css: list[str] = field(default_factory=list)
    inline_js: list[str] = field(default_factory=list)
    title: str = ""
    lang: str = ""
    nofollow: bool = False
    noindex: bool = False
    base_url: str = ""


def _srcset_values(value: str) -> list[str]:
    return [part.strip().split()[0] for part in (value or "").split(",") if part.strip()]


def extract_html(text: str, page_url: str) -> HTMLExtraction:
    soup = BeautifulSoup(text, "lxml")
    base = page_url
    base_tag = soup.find("base", href=True)
    if base_tag:
        base = urljoin(page_url, base_tag.get("href", ""))
    out = HTMLExtraction(base_url=base)
    if soup.title:
        out.title = soup.title.get_text(" ", strip=True)
    if soup.html:
        out.lang = soup.html.get("lang", "")
    robots = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "robots"})
    if robots:
        directives = robots.get("content", "").lower()
        out.nofollow = "nofollow" in directives or "none" in directives
        out.noindex = "noindex" in directives or "none" in directives

    attrs = {
        "a": ["href"], "link": ["href"], "script": ["src"], "img": ["src", "data-src"],
        "source": ["src"], "video": ["src", "poster"], "audio": ["src"], "iframe": ["src"],
        "embed": ["src"], "object": ["data"],
    }
    for tag, names in attrs.items():
        for node in soup.find_all(tag):
            for attr in names:
                if node.get(attr):
                    u = absolutize(base, node.get(attr))
                    if u:
                        out.urls.append((u, f"html:{tag}.{attr}"))
            for attr in ("srcset",):
                if node.get(attr):
                    for raw in _srcset_values(node.get(attr)):
                        u = absolutize(base, raw)
                        if u:
                            out.urls.append((u, f"html:{tag}.{attr}"))
    for node in soup.find_all(True):
        style = node.get("style")
        if style:
            out.inline_css.append(style)
        for attr in ("data-href",):
            if node.get(attr):
                u = absolutize(base, node.get(attr))
                if u:
                    out.urls.append((u, f"html:{node.name}.{attr}"))
    for style in soup.find_all("style"):
        out.inline_css.append(style.get_text("\n"))
    for script in soup.find_all("script"):
        if not script.get("src"):
            out.inline_js.append(script.get_text("\n"))
    for form in soup.find_all("form"):
        action = absolutize(base, form.get("action") or page_url) or page_url
        method = (form.get("method") or "GET").upper()
        fields = []
        for inp in form.find_all(["input", "select", "textarea", "button"]):
            fields.append({"name": inp.get("name", ""), "type": inp.get("type", inp.name), "value": inp.get("value", "")})
        out.forms.append({"action": action, "method": method, "fields": fields})
        out.urls.append((action, "form"))
    for meta in soup.find_all("meta"):
        if (meta.get("http-equiv") or "").lower() == "refresh" and meta.get("content"):
            content = meta.get("content")
            if "url=" in content.lower():
                raw = content.split("=", 1)[1].strip(" '\"")
                u = absolutize(base, raw)
                if u:
                    out.urls.append((u, "meta-refresh"))
        if (meta.get("property") or "").lower() == "og:image" and meta.get("content"):
            u = absolutize(base, meta.get("content"))
            if u:
                out.urls.append((u, "og:image"))
    return out
