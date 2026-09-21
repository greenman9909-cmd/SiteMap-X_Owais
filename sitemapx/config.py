from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any
import tomllib

import yaml


@dataclass(slots=True)
class Config:
    url: str = ""
    out: Path = Path("output")
    depth: int = 10
    concurrency: int = 10
    rate: float = 5.0
    per_host_rate: float = 2.0
    max_pages: int = 50_000
    scope: str = "same-host"
    http2: bool = False
    render: bool = False
    screenshots: bool = False
    cookie: str | None = None
    headers: list[str] = field(default_factory=list)
    basic: str | None = None
    login_url: str | None = None
    login_method: str = "POST"
    login_fields: str | None = None
    har: Path | None = None
    cookie_file: Path | None = None
    storage_state: Path | None = None
    proxy: str | None = None
    user_agent: str = "SiteMap-X/0.1 (+https://github.com/greenman9909-cmd/SiteMap-X_Owais)"
    robots: bool = True
    rewrite_js: bool = False
    include_regex: list[str] = field(default_factory=list)
    exclude_regex: list[str] = field(default_factory=list)
    resume: bool = False
    diff_against: Path | None = None
    graphql_introspect: bool = False
    openapi_probe: bool = False
    output_format: list[str] = field(default_factory=lambda: ["html", "json", "md", "txt"])
    quiet: bool = False
    verbose: bool = False
    render_wait_ms: int = 500
    timeout: float = 30.0
    redirect_limit: int = 10

    def ensure_out(self) -> Path:
        self.out = Path(self.out).expanduser().resolve()
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / "mirror").mkdir(exist_ok=True)
        if self.screenshots:
            (self.out / "screenshots").mkdir(exist_ok=True)
        return self.out

    def as_jsonable(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("out", "har", "cookie_file", "storage_state", "diff_against"):
            value = data.get(key)
            if value is not None:
                data[key] = str(value)
        if data.get("cookie"):
            data["cookie"] = "<configured>"
        if data.get("basic"):
            data["basic"] = "<configured>"
        if data.get("login_fields"):
            data["login_fields"] = "<configured>"
        if data.get("headers"):
            redacted = []
            for raw in data["headers"]:
                name = str(raw).split(":", 1)[0].strip()
                redacted.append(f"{name}: <configured>")
            data["headers"] = redacted
        return data


CrawlConfig = Config


def _load_mapping(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix == ".toml":
        return tomllib.loads(raw.decode("utf-8"))
    if suffix in {".yaml", ".yml"}:
        return yaml.safe_load(raw) or {}
    raise ValueError(f"Unsupported config type: {path.suffix}")


def discover_config(explicit: str | Path | None = None) -> Path | None:
    if explicit:
        p = Path(explicit)
        return p if p.exists() else None
    for candidate in (Path("sitemapx.toml"), Path("sitemapx.yaml"), Path("sitemapx.yml")):
        if candidate.exists():
            return candidate
    return None


def _coerce_paths(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    for key in {"out", "har", "cookie_file", "storage_state", "diff_against"}:
        value = out.get(key)
        if value not in (None, ""):
            out[key] = Path(value)
    if isinstance(out.get("output_format"), str):
        out["output_format"] = [x.strip() for x in out["output_format"].split(",") if x.strip()]
    return out


def load_config(path: str | Path | None = None) -> Config:
    resolved = discover_config(path)
    if not resolved:
        return Config()
    data = _load_mapping(resolved)
    if isinstance(data.get("sitemapx"), dict):
        data = data["sitemapx"]
    valid = {f.name for f in fields(Config)}
    clean = _coerce_paths({k: v for k, v in data.items() if k in valid})
    return Config(**clean)


def merge_config(base: Config, overrides: dict[str, Any]) -> Config:
    valid = {f.name for f in fields(Config)}
    data = asdict(base)
    for key, value in overrides.items():
        if key in valid and value is not None:
            data[key] = value
    data = _coerce_paths(data)
    return Config(**data)
