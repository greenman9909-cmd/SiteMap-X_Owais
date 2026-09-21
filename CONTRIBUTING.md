# Contributing to SiteMap-X

Contributions are welcome for crawler correctness, parsers, framework discovery, reporting, GUI improvements, test coverage, documentation, and performance.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e '.[dev]'
```

For rendered-crawl development:

```bash
python -m playwright install chromium
```

## Before opening a pull request

Run:

```bash
python -m compileall -q sitemapx
python -m sitemapx.cli --help
ruff check sitemapx
```

Keep modules focused, preserve async behavior in crawl paths, parameterize SQL queries, and include a concise explanation of behavior changes in the pull request.

## Project style

- Python 3.11+.
- Prefer typed, small functions with explicit inputs/outputs.
- Keep network operations asynchronous.
- Avoid blocking work on the Qt UI thread.
- Add parser logic to the relevant `sitemapx/parse` module instead of growing a single catch-all parser.
- Keep report data machine-readable even when adding richer presentation to `report.html`.
