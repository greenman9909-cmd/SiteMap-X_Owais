# Architecture

SiteMap-X is split into small subsystems so crawling, extraction, mirroring, reporting, and the GUI can evolve independently.

## Data flow

```text
seed URL
   |
   v
Config -> Session/Auth -> Scheduler -> Fetcher
                                 |
                                 v
                              Crawler
                       /       |       \
                      /        |        \
                 Parsers    Renderer   Fingerprints
                    |          |            |
                    +----------+------------+
                               |
                         SQLiteStore
                         /    |     \
                        /     |      \
                   Mirror  Reports  Diff/export
```

## Core

`core/crawler.py` owns the queue, scope checks, deduplication, depth/page caps, discovery fan-out, resume behavior, and post-crawl probes.

`core/scheduler.py` enforces global and per-host pacing. It also tracks transient host backoff after `429`/`503` responses.

`core/fetcher.py` performs a single HTTP fetch with redirects, retries, timing, content metadata, and optional HTTP/2 transport.

`core/session.py` builds the shared authenticated session. It can ingest explicit cookies, Netscape cookie files, HAR authentication material, Playwright storage-state cookies, Basic auth, custom headers, and login-form cookies.

`core/urlutil.py` centralizes URL normalization, same-host/domain scoping, endpoint classification, and deterministic mirror-path mapping.

## Discovery parsers

The `parse/` package extracts new crawl candidates and structured endpoint evidence from HTML, CSS, JavaScript, source maps, manifests, service-worker references, robots files, sitemaps, and framework route markers.

JavaScript extraction records the source line for direct `fetch`, Axios, XHR, WebSocket, EventSource, beacon, import, API-path, and route-literal hits where possible.

## Runtime rendering

`render/playwright_engine.py` is optional. It renders a page in Chromium, waits for network idle, captures the final DOM, records requests, WebSocket URLs, frame direction/type/size metadata, console errors, and optional screenshots.

## Mirror

`mirror/writer.py` stages fetched resources and writes them after discovery so URL rewriting has the broadest possible known-resource map. HTML and CSS are rewritten to relative local paths. JavaScript is preserved unless `--rewrite-js` is enabled.

## Intelligence

`intel/fingerprints.py` records technology fingerprints with a confidence value and triggering evidence. `openapi_probe.py` detects OpenAPI/Swagger documents and expands documented path/method pairs. `graphql_probe.py` extracts named operations and converts successful introspection output into readable SDL.

## Storage

`store/sqlite_store.py` uses SQLite with WAL mode. Tables cover URL state, HTML pages, binary assets, endpoints, forms, fingerprints, cookies, WebSocket metadata, and redirect chains. The URL table is also the source of truth for resumable crawls.

## Reports

The `report/` package generates a machine-readable JSON snapshot, Markdown summary, and a single-file interactive HTML dashboard. The diff module compares endpoint inventories from two output directories.

## GUI

The PySide6 GUI uses a `QThread` whose `run()` method owns a dedicated asyncio event loop. Crawl progress is emitted back to the UI through Qt signals so network work never blocks the main GUI thread.
