# SiteMap-X Output Reference

A crawl output directory is intentionally self-contained so it can be inspected later without rerunning the crawl.

## Primary reports

### `report.html`

Interactive single-file dashboard with dark styling, tabs, sortable tables, and a global search box. It summarizes pages, assets, forms, endpoint discoveries, fingerprints, GraphQL records, and external hosts.

### `report.json`

Machine-readable snapshot of crawl configuration, summary counters, URLs, pages, assets, endpoints, fingerprints, forms, cookies, and redirect records. Authentication values in the saved configuration are redacted.

### `report.md`

Portable Markdown summary suitable for notes, issue discussions, or source-control review.

## Endpoint exports

### `endpoints.txt`

One discovered HTTP/HTTPS/WebSocket URL per line.

### `endpoints.json`

Structured endpoint records. Important fields include:

- `url` — discovered URL or logical GraphQL record.
- `method` — HTTP method when known.
- `source` — discovery mechanism such as `fetch`, `axios`, `form`, `openapi`, or runtime traffic.
- `discovered_from` — page or resource that contained the reference.
- `confidence` — confidence score assigned by the relevant extractor.
- `category` — API endpoint, GraphQL endpoint, WebSocket URL, external resource, etc.
- `line` — source line when static extraction can identify it.
- `query_params` — observed query parameter names.
- `response_status` — status code if the endpoint was fetched.
- `auth_hint` — whether the crawl session had authentication material attached.
- `is_form` — whether the endpoint was observed as a form action.

### `external_hosts.txt`

Distinct external hostnames discovered during the crawl.

## Crawl database

### `crawl.sqlite3`

The resumable crawl database. Tables include `urls`, `pages`, `assets`, `endpoints`, `fingerprints`, `forms`, `cookies`, `ws_messages`, and `redirects`. SQLite WAL mode is enabled for concurrent-friendly reads during active crawling.

## Offline mirror

### `mirror/`

Local copies of fetched pages and assets. Paths are derived deterministically from URLs. HTML and CSS references are rewritten to relative local paths when the target resource is known. Query-string variants use hashed filenames to avoid collisions.

## Optional artifacts

### `screenshots/`

Full-page PNG captures when `--screenshots` is enabled.

### `openapi.json`

The discovered OpenAPI/Swagger document when SiteMap-X successfully identifies one.

### `graphql_schema.json`

Raw GraphQL introspection response when introspection succeeds.

### `graphql_schema.graphql`

Human-readable SDL generated from the introspection response.

### `sourcemap_sources.txt`

Source paths collected from JavaScript source maps when present.

### `diff.md`

Endpoint additions/removals when `--diff-against` is used.

### `cookies.txt`

Netscape-format cookie export from the final crawl session.
