from __future__ import annotations

from urllib.parse import urljoin
import json

COMMON_PATHS = [
    "/swagger.json", "/openapi.json", "/api-docs", "/v3/api-docs", "/swagger/v1/swagger.json"
]
UI_PATHS = ["/docs", "/swagger", "/redoc"]


def extract_openapi(text: str, base_url: str) -> tuple[dict | None, list[tuple[str, str]]]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None, []
    if not isinstance(data, dict) or not (data.get("openapi") or data.get("swagger")) or not isinstance(data.get("paths"), dict):
        return None, []
    found: list[tuple[str, str]] = []
    server = base_url
    if data.get("servers") and isinstance(data["servers"], list) and data["servers"] and data["servers"][0].get("url"):
        server = urljoin(base_url, data["servers"][0]["url"])
    for path, item in data["paths"].items():
        if not isinstance(item, dict):
            continue
        for method in item:
            if method.lower() in {"get", "post", "put", "patch", "delete", "head", "options", "trace"}:
                found.append((urljoin(server.rstrip("/") + "/", path.lstrip("/")), method.upper()))
    return data, found
