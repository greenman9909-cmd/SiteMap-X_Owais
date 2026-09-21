# SiteMap-X Usage Guide

SiteMap-X is designed for situations where you need a repeatable, structured picture of a web application from one starting URL. It combines crawling, offline mirroring, endpoint discovery, stack fingerprinting, and reporting in one run.

## Typical uses

### 1. Build an offline frontend mirror

Use the mirror when you need to inspect page structure and downloaded assets without repeatedly requesting the original site.

```bash
sitemapx https://example.com --out ./example-crawl
```

Open `example-crawl/mirror/index.html` after the run. The mirror rewrites known HTML and CSS URLs to local files. JavaScript is left untouched by default; `--rewrite-js` enables conservative rewriting for known mirrored assets.

### 2. Inventory backend endpoints referenced by a frontend

SiteMap-X extracts endpoints from forms, JavaScript request calls, route literals, runtime Playwright traffic, OpenAPI documents, manifests, source maps, and other discovery sources.

```bash
sitemapx https://app.example.com \
  --openapi-probe \
  --graphql-introspect \
  --out ./endpoint-map
```

Review `endpoints.json`, `endpoints.txt`, or the **Endpoints** tab in `report.html`.

### 3. Inspect JavaScript-rendered applications

For SPAs where important routes and XHR/fetch requests appear only after client-side execution:

```bash
sitemapx https://app.example.com --render --out ./rendered-crawl
```

To capture full-page screenshots too:

```bash
sitemapx https://app.example.com --screenshots --out ./rendered-crawl
```

The first Playwright use requires:

```bash
python -m playwright install chromium
```

### 4. Compare web application revisions

Keep crawl outputs from different builds or dates and compare endpoint inventories:

```bash
sitemapx https://example.com \
  --out ./crawl-new \
  --diff-against ./crawl-old
```

The comparison is saved as `diff.md` in the new output directory.

### 5. Resume a large crawl

SiteMap-X persists crawl state in SQLite. If a crawl is interrupted, run the same seed URL and output directory with `--resume`:

```bash
sitemapx https://example.com --out ./large-crawl --resume
```

## Scope modes

`--scope same-host` stays on the exact seed host. `--scope same-domain` also permits sibling subdomains under the same registrable domain. `--scope all` permits external HTTP/HTTPS URLs discovered during crawling.

```bash
sitemapx https://www.example.com --scope same-domain --out ./domain-map
```

## Rate controls

The crawler applies both a global rate and a per-host rate:

```bash
sitemapx https://example.com \
  --concurrency 16 \
  --rate 20 \
  --per-host-rate 4 \
  --out ./controlled
```

`429` and `503` responses trigger retry/backoff behavior. `Crawl-Delay` from `robots.txt` is applied when robots processing is enabled.

## Authentication inputs

### Cookie string

```bash
sitemapx https://app.example.com \
  --cookie "session=abc123; locale=en" \
  --out ./session-crawl
```

### Custom headers

```bash
sitemapx https://api.example.com \
  --header "Authorization: Bearer TOKEN" \
  --header "X-Tenant: example" \
  --out ./header-crawl
```

### HTTP Basic

```bash
sitemapx https://example.com/private --basic user:password --out ./private-crawl
```

### Login request

```bash
sitemapx https://app.example.com \
  --login-url https://app.example.com/login \
  --login-method POST \
  --login-fields "username=alice&password=secret" \
  --out ./logged-in
```

### HAR, Netscape cookie file, or Playwright storage state

```bash
sitemapx https://app.example.com --har ./session.har --out ./har-crawl
sitemapx https://app.example.com --cookie-file ./cookies.txt --out ./cookie-crawl
sitemapx https://app.example.com --storage-state ./state.json --render --out ./state-crawl
```

## URL filters

Include/exclude expressions are regular expressions and may be repeated:

```bash
sitemapx https://example.com \
  --include-regex '^https://example\.com/' \
  --exclude-regex '/logout(?:\?|$)' \
  --exclude-regex '/calendar/' \
  --out ./filtered
```

## Configuration files

SiteMap-X automatically reads `sitemapx.toml`, `sitemapx.yaml`, or `sitemapx.yml` from the current directory. A custom file can be selected with `--config`.

```bash
sitemapx https://example.com --config ./examples/sitemapx.toml
```

Command-line options override configuration-file values.
