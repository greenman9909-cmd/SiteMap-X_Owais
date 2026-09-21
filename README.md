<div align="center">

# SiteMap-X

**Advanced website crawler · offline frontend mirror · backend endpoint mapper · technology fingerprinting toolkit**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-41CD52?logo=qt&logoColor=white)](https://doc.qt.io/qtforpython-6/)
[![CI](https://github.com/greenman9909-cmd/SiteMap-X_Owais/actions/workflows/ci.yml/badge.svg)](https://github.com/greenman9909-cmd/SiteMap-X_Owais/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Support on Ko-fi](https://img.shields.io/badge/Ko--fi-Support%20Owais-FF5E5B?logo=kofi&logoColor=white)](https://ko-fi.com/yorusayano)

**CLI:** `sitemapx` · **Desktop GUI:** `sitemapx-gui`

</div>

SiteMap-X takes one seed URL and builds a structured picture of a website: the pages and assets that make up the frontend, routes and backend endpoints referenced by the client, technology fingerprints, forms, external hosts, optional GraphQL/OpenAPI metadata, and a locally browsable mirror. Crawl state is stored in SQLite so larger jobs can be resumed.

## Why SiteMap-X exists & Key Benefits

Modern websites are often spread across HTML, CSS, JavaScript bundles, lazy-loaded chunks, service workers, runtime XHR/fetch calls, route manifests, sitemaps, API descriptions, and browser-only network activity. Looking at a single page source misses much of that surface.

SiteMap-X bridges this gap by turning raw client artifacts into a complete architectural map.

| Benefit | How It Helps |
|---|---|
| **Reverse Engineering & Code Audits** | Rapidly map the architecture, route structure, and third-party integrations of any unknown web application without needing backend source code. |
| **Complete API Surface Mapping** | Identify internal backend endpoints consumed by the client (tRPC procedures, REST paths, GraphQL endpoints) for security audits, migrations, or contract testing. |
| **Release & Deployment Diffing** | Run `--diff-against` between builds to see what new routes, assets, or API endpoints changed between releases. |
| **Offline Archiving & UI Prototyping** | Save complete snapshots of landing pages or documentation sites for offline reference with rewritten relative links. |
| **Zero-Friction Discovery** | Requires only a single seed URL (`sitemapx https://target.com --out ./out`) to perform discovery, fingerprinting, mirroring, and report generation in one pass. |

---

## What SiteMap-X Allows You To Do

1. **Deep Endpoint & API Discovery (tRPC / REST / GraphQL)**
   - Automatically parses JavaScript bundles, route manifests, and source maps to extract client-side API routes, tRPC procedures, and backend endpoints (e.g. `api/trpc/...`, `api/...`).
   - Categorizes each route by type: *Navigable Page*, *API Endpoint*, *Static Asset*, or *Form Target*, complete with discovery evidence (bundle ref, route literal, or runtime capture).

2. **Offline Frontend Mirroring**
   - Downloads HTML, CSS, JavaScript, images, and fonts while rewriting internal references to relative local paths so you can browse the entire site offline directly from disk.

3. **Multi-Vector Technology Fingerprinting**
   - Detects web servers, frameworks, CDNs, analytics providers, payment processors, and error tracking platforms with confidence scores based on headers, script hashes, DOM signatures, and bundle patterns.

4. **Headless Browser Rendering (Playwright Chromium)**
   - Optionally spins up headless Chromium to execute client-side JavaScript, capture dynamic runtime network requests and WebSockets, record console errors, and generate full-page screenshots.

5. **Resumable SQLite Crawl Engine**
   - Every URL, page, endpoint, and asset is tracked in a WAL-mode SQLite database (`crawl.sqlite3`), allowing large multi-thousand page crawls to pause and resume seamlessly.

6. **Rich Interactive & Machine-Readable Reports**
   - Generates an interactive single-page HTML dashboard (`report.html`) with filterable and searchable tables, as well as JSON, Markdown, and plaintext endpoint listings.

---

## 🧪 Real-World Case Study: resend.com

Here is an example crawl performed on **[https://resend.com](https://resend.com)** with depth 2 and page limit 25:

- **Full Test Repository:** [greenman9909-cmd/resend-test-sitemap-x](https://github.com/greenman9909-cmd/resend-test-sitemap-x)
- **Discovered Technology:** Next.js (0.98), Vercel (0.99), Stripe (0.97), CloudFront (0.95), GA4 (0.94), Rollbar (0.92)
- **Endpoints Discovered (266 mapped):**
  - `https://resend.com/api/trpc/support.contactUs`
  - `https://resend.com/api/trpc/support.enterpriseForm`
  - `https://resend.com/api/trpc/marketing.submitStartupApplication`
  - `https://resend.com/api/trpc/careers.applyToJobPosting`
  - `https://resend.com/api/migrate/convert`
  - `https://resend.com/auth/reset-password`

---

## Core capabilities

| Area | What SiteMap-X does |
|---|---|
| Crawling | Async bounded concurrency, global/per-host rate limiting, retries, redirect tracking, depth/page caps, resumable SQLite state |
| Discovery | HTML, CSS, JS request patterns, route literals, source maps, manifests, service workers, robots.txt, sitemap.xml, framework data, well-known files |
| Rendering | Optional Playwright Chromium, rendered DOM capture, runtime request discovery, WebSocket metadata, console errors, screenshots |
| Mirroring | Saves pages/assets locally and rewrites HTML/CSS references to relative local files |
| Endpoint mapping | Classifies APIs, GraphQL, WebSockets, navigable pages, assets, forms, and external URLs with discovery evidence |
| API metadata | Optional OpenAPI probing and GraphQL introspection/operation extraction |
| Fingerprinting | Detects common frameworks, CMSs, backend hints, CDNs, analytics, auth, payments, and error tracking signals |
| Authentication | Cookies, headers, Basic auth, login request, Netscape cookie files, HAR import, Playwright storage state |
| Reports | Interactive HTML dashboard plus JSON, Markdown, endpoint lists, external host list, cookie export, schema files |
| Interfaces | Click-based CLI and a dark PySide6 desktop GUI |

## What it produces

For a seed URL, SiteMap-X can produce:

- `mirror/` — locally browsable copies of fetched HTML, CSS, JavaScript, images, fonts, documents, and other assets.
- `crawl.sqlite3` — resumable crawl state and structured crawl intelligence.
- `report.html` — interactive single-file dashboard with searchable/sortable tables.
- `report.json` — machine-readable crawl report.
- `report.md` — Markdown summary.
- `endpoints.txt` — flat endpoint list.
- `endpoints.json` — structured endpoint inventory with methods, discovery source, confidence, and source line when available.
- `external_hosts.txt` — registrable external hosts observed during discovery.
- `cookies.txt` — Netscape-format session cookie export.
- `openapi.json` — saved OpenAPI document when one is discovered.
- `graphql_schema.json` / `graphql_schema.graphql` — GraphQL introspection results when enabled and available.
- `screenshots/` — optional full-page screenshots from Playwright rendering.

## Installation

Create and activate a virtual environment, then install the project:

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

python -m pip install --upgrade pip
pip install -e .
```

For JavaScript rendering and screenshots, install Playwright Chromium once:

```bash
python -m playwright install chromium
```

## Quick start

Basic crawl:

```bash
sitemapx https://example.com --out ./out
```

Launch the GUI:

```bash
sitemapx-gui
```

Resume an interrupted crawl from its SQLite state:

```bash
sitemapx https://example.com --out ./out --resume
```

## CLI reference

```text
sitemapx URL [OPTIONS]

  --out DIR
  --depth N
  --concurrency N
  --rate N
  --per-host-rate N
  --max-pages N
  --scope same-host|same-domain|all
  --render
  --screenshots
  --cookie "k=v; ..."
  --header "Name: value"          repeatable
  --basic USER:PASS
  --login-url URL
  --login-method GET|POST|PUT|PATCH
  --login-fields "u=x&p=y"
  --har PATH / --har-file PATH
  --cookie-file PATH
  --storage-state PATH
  --proxy URL
  --user-agent STRING
  --robots / --no-robots
  --rewrite-js
  --include-regex REGEX           repeatable
  --exclude-regex REGEX           repeatable
  --resume
  --diff-against DIR
  --graphql-introspect
  --openapi-probe
  --output-format html,json,md,txt
  --quiet
  --verbose
  --config PATH
```

## Examples by feature

### Deep crawl with rate limits

```bash
sitemapx https://example.com \
  --out ./crawl-example \
  --depth 8 \
  --concurrency 16 \
  --rate 25 \
  --per-host-rate 5 \
  --max-pages 20000
```

### Same-domain crawl across subdomains

```bash
sitemapx https://www.example.com --scope same-domain --out ./domain-crawl
```

### JavaScript-rendered discovery

```bash
sitemapx https://app.example.com --render --out ./rendered
```

### Rendered crawl with screenshots

```bash
sitemapx https://app.example.com --screenshots --out ./screens
```

`--screenshots` implies `--render`.

### Cookie-authenticated crawl

```bash
sitemapx https://app.example.com \
  --cookie "session=abc123; locale=en" \
  --out ./authenticated
```

### Authorization header

```bash
sitemapx https://api.example.com \
  --header "Authorization: Bearer TOKEN" \
  --header "X-Tenant: demo" \
  --out ./api-crawl
```

### HTTP Basic authentication

```bash
sitemapx https://example.com/private --basic user:password --out ./private
```

### Login request followed by crawl

```bash
sitemapx https://app.example.com \
  --login-url https://app.example.com/login \
  --login-method POST \
  --login-fields "username=alice&password=secret" \
  --out ./logged-in
```

The login request is performed with `httpx`; returned cookies are transferred into the crawler session.

### Import Netscape cookies

```bash
sitemapx https://example.com --cookie-file ./cookies.txt --out ./cookie-crawl
```

### Import a HAR capture

```bash
sitemapx https://example.com --har ./session.har --out ./har-crawl
```

SiteMap-X imports reusable request headers and cookies from the HAR.

### Use Playwright storage state

```bash
sitemapx https://app.example.com --storage-state ./state.json --render --out ./state-crawl
```

### Proxy

```bash
sitemapx https://example.com --proxy http://127.0.0.1:8080 --out ./proxied
```

### Custom User-Agent

```bash
sitemapx https://example.com --user-agent "SiteMap-X-Lab/1.0" --out ./ua-crawl
```

### URL include/exclude filters

```bash
sitemapx https://example.com \
  --include-regex '^https://example\.com/' \
  --exclude-regex '/logout(?:\?|$)' \
  --exclude-regex '/calendar/' \
  --out ./filtered
```

### Disable robots processing

```bash
sitemapx https://example.com --no-robots --out ./unfiltered-robots
```

### OpenAPI probing

```bash
sitemapx https://api.example.com --openapi-probe --out ./openapi-crawl
```

This queues common OpenAPI/Swagger locations such as `/openapi.json`, `/swagger.json`, `/api-docs`, and `/v3/api-docs` and ingests documented path/method pairs when a schema is found.

### GraphQL discovery and introspection

```bash
sitemapx https://app.example.com --graphql-introspect --out ./graphql-crawl
```

SiteMap-X collects GraphQL endpoint references from crawled sources and, when enabled, sends a standard introspection query to discovered HTTP GraphQL endpoints. If introspection is unavailable, named GraphQL operations found in JavaScript are still recorded.

### Rewrite known JavaScript asset URLs in the mirror

```bash
sitemapx https://example.com --rewrite-js --out ./rewritten-js
```

JavaScript is otherwise left unchanged so client-side routing and bundle loading are less likely to be disrupted.

### Diff endpoint inventories

```bash
sitemapx https://example.com \
  --out ./crawl-new \
  --diff-against ./crawl-old
```

The result is written to `crawl-new/diff.md`.

### Select report formats

```bash
sitemapx https://example.com --output-format html,json,md,txt --out ./reports
```

`txt` corresponds to the flat auxiliary exports such as `endpoints.txt` and `external_hosts.txt`.

## Configuration files

SiteMap-X automatically looks for `sitemapx.toml`, `sitemapx.yaml`, or `sitemapx.yml` in the current working directory. Use `--config PATH` to select another file. CLI arguments override configuration-file values.

Example `sitemapx.toml`:

```toml
[sitemapx]
out = "./crawl-output"
depth = 7
concurrency = 12
rate = 20
per_host_rate = 5
max_pages = 25000
scope = "same-host"
robots = true
render = false
openapi_probe = true
graphql_introspect = false
output_format = ["html", "json", "md", "txt"]
include_regex = ["^https://example\\.com/"]
exclude_regex = ["/logout"]
```

Example `sitemapx.yaml`:

```yaml
sitemapx:
  out: ./crawl-output
  depth: 7
  concurrency: 12
  rate: 20
  per_host_rate: 5
  max_pages: 25000
  scope: same-host
  robots: true
  render: false
  openapi_probe: true
  output_format: [html, json, md, txt]
```

## Documentation

- [Usage guide](docs/USAGE.md) — practical workflows, authentication, rendering, filters, resume, and diffing.
- [Architecture](docs/ARCHITECTURE.md) — crawler pipeline and module responsibilities.
- [Output reference](docs/OUTPUTS.md) — every generated artifact and endpoint field.
- [`examples/sitemapx.toml`](examples/sitemapx.toml) — ready-to-edit configuration file.
- [Contributing](CONTRIBUTING.md) — development setup and contribution workflow.

## Architecture

```text
sitemapx/
├── pyproject.toml
├── README.md
└── sitemapx/
    ├── __init__.py
    ├── __main__.py
    ├── cli.py
    ├── config.py
    ├── core/
    │   ├── session.py
    │   ├── crawler.py
    │   ├── urlutil.py
    │   ├── fetcher.py
    │   └── scheduler.py
    ├── parse/
    │   ├── html_extract.py
    │   ├── css_extract.py
    │   ├── js_extract.py
    │   ├── sitemap.py
    │   ├── robots.py
    │   ├── manifest.py
    │   ├── sourcemap.py
    │   └── frameworks.py
    ├── render/
    │   └── playwright_engine.py
    ├── mirror/
    │   ├── writer.py
    │   ├── rewrite_html.py
    │   ├── rewrite_css.py
    │   └── rewrite_js.py
    ├── intel/
    │   ├── fingerprints.py
    │   ├── openapi_probe.py
    │   ├── graphql_probe.py
    │   └── wellknown.py
    ├── store/
    │   └── sqlite_store.py
    ├── report/
    │   ├── html_report.py
    │   ├── json_report.py
    │   ├── markdown_report.py
    │   └── diff.py
    └── gui/
        ├── app.py
        ├── main_window.py
        ├── worker.py
        ├── panels/
        │   ├── settings_panel.py
        │   ├── log_panel.py
        │   ├── results_panel.py
        │   └── live_table.py
        └── styles/dark.qss
```

## Discovery model

SiteMap-X feeds its crawl queue from HTML attributes, inline and external CSS, JavaScript request patterns, route literals, source maps, service-worker/bundler references, web manifests, robots and sitemaps, OpenAPI documents, well-known files, and optional Playwright runtime traffic. The endpoint table records the URL, method when known, discovery source, source document, source line when available, query parameter names, response status when fetched, authentication-session hint, and classification.

## SQLite state

The output database uses WAL mode and stores URL state, pages, binary assets, endpoints, fingerprints, forms, cookies, WebSocket metadata, and redirect chains. Running the same output directory with `--resume` loads pending URLs whose fetch status is still unset.

## GUI

The PySide6 interface includes:

- URL entry, Start, Stop, and Resume controls.
- Live crawl progress.
- Crawl settings for depth, concurrency, rate limits, scope, rendering, screenshots, robots, OpenAPI, GraphQL, mirror rewriting, and authentication inputs.
- Include/exclude regex filters.
- Advanced custom headers, proxy, and User-Agent configuration.
- Live URL table and timestamped log output.
- Post-crawl results tree.
- JSON, Markdown, and CSV export actions.
- JWT structure inspector under **Tools > Crack Cookies**.
- Endpoint diffing against a previous crawl.

## Support

If SiteMap-X is useful to you and you want to support more builds from Owais, you can support the project on Ko-fi. Support is optional and does not unlock features.

[![Support me on Ko-fi](https://storage.ko-fi.com/cdn/kofi3.png?v=3)](https://ko-fi.com/yorusayano)

## License

SiteMap-X is released under the [MIT License](LICENSE).
