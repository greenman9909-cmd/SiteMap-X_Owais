from __future__ import annotations

from pathlib import Path
import json


def _load_endpoints(directory: Path) -> set[str]:
    p = Path(directory) / "endpoints.json"
    if p.exists():
        try:
            data = json.loads(p.read_text("utf-8"))
            return {x.get("url", "") for x in data if isinstance(x, dict) and x.get("url")}
        except Exception:
            pass
    p = Path(directory) / "endpoints.txt"
    if p.exists():
        return {x.strip() for x in p.read_text("utf-8", errors="ignore").splitlines() if x.strip()}
    return set()


def diff_directories(old_dir: Path, new_dir: Path, output: Path | None = None) -> dict[str, list[str]]:
    old, new = _load_endpoints(Path(old_dir)), _load_endpoints(Path(new_dir))
    result = {"added": sorted(new-old), "removed": sorted(old-new), "unchanged": sorted(old & new)}
    if output:
        lines = ["# Crawl Diff", "", "## Added"] + [f"- `{x}`" for x in result["added"]] + ["", "## Removed"] + [f"- `{x}`" for x in result["removed"]]
        Path(output).write_text("\n".join(lines)+"\n", "utf-8")
    return result
