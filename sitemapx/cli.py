from __future__ import annotations

from pathlib import Path
import asyncio
import sys

import click

from .config import load_config, merge_config
from .core.crawler import Crawler


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("url")
@click.option("--out", type=click.Path(path_type=Path), default=None, help="Output directory")
@click.option("--depth", type=int, default=None, help="Max crawl depth")
@click.option("--concurrency", type=int, default=None, help="Parallel requests")
@click.option("--rate", type=float, default=None, help="Global requests per second")
@click.option("--per-host-rate", type=float, default=None, help="Per-host requests per second")
@click.option("--max-pages", type=int, default=None, help="Maximum fetched pages/assets")
@click.option("--scope", type=click.Choice(["same-host", "same-domain", "all"]), default=None)
@click.option("--http2", is_flag=True, default=None, help="Use HTTP/2-capable httpx transport")
@click.option("--render", is_flag=True, default=None, help="Render pages with Playwright Chromium")
@click.option("--screenshots", is_flag=True, default=None, help="Save full-page screenshots (implies --render)")
@click.option("--cookie", default=None, help="Cookie header-style string: k=v; k2=v2")
@click.option("--header", "headers", multiple=True, help="Custom header, repeatable")
@click.option("--basic", default=None, metavar="USER:PASS", help="HTTP Basic credentials")
@click.option("--login-url", default=None)
@click.option("--login-method", type=click.Choice(["GET", "POST", "PUT", "PATCH"], case_sensitive=False), default=None)
@click.option("--login-fields", default=None, help="Form fields: u=x&p=y")
@click.option("--har", "--har-file", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--cookie-file", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--storage-state", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--proxy", default=None)
@click.option("--user-agent", default=None)
@click.option("--robots/--no-robots", default=None, help="Honor robots.txt (default on)")
@click.option("--rewrite-js", is_flag=True, default=None)
@click.option("--include-regex", multiple=True)
@click.option("--exclude-regex", multiple=True)
@click.option("--resume", is_flag=True, default=None)
@click.option("--diff-against", type=click.Path(exists=True, file_okay=False, path_type=Path), default=None)
@click.option("--graphql-introspect", is_flag=True, default=None)
@click.option("--openapi-probe", is_flag=True, default=None)
@click.option("--output-format", default=None, help="Comma-separated: html,json,md,txt")
@click.option("--quiet", is_flag=True, default=None)
@click.option("--verbose", is_flag=True, default=None)
@click.option("--config", "config_path", type=click.Path(exists=True, dir_okay=False, path_type=Path), default=None)
def main(url: str, **kwargs) -> None:
    """Crawl URL, build an offline mirror, map endpoints, and generate reports."""
    config_path = kwargs.pop("config_path", None)
    file_cfg = load_config(config_path)
    overrides = {"url": url}
    for key, value in kwargs.items():
        if key == "headers" and value:
            overrides["headers"] = list(value)
        elif key in {"include_regex", "exclude_regex"} and value:
            overrides[key] = list(value)
        elif key == "output_format" and value:
            overrides[key] = [x.strip() for x in value.split(",") if x.strip()]
        elif value is not None:
            overrides[key] = value
    if overrides.get("screenshots"):
        overrides["render"] = True
    if config_path:
        overrides["config_path"] = config_path
    config = merge_config(file_cfg, overrides)

    def on_event(event: dict) -> None:
        if config.quiet:
            return
        kind = event.get("kind")
        if kind == "url":
            click.echo(f"[{event.get('status')}] d={event.get('depth')} {event.get('type')} {event.get('url')}")
        elif kind == "log" and (config.verbose or event.get("level") in {"WARN", "ERROR"}):
            click.echo(f"{event.get('level')}: {event.get('message')}", err=event.get("level") == "ERROR")
        elif kind == "done":
            click.echo(f"Output: {event.get('out')}")
            click.echo("Summary: " + ", ".join(f"{k}={v}" for k, v in event.get("summary", {}).items()))

    crawler = Crawler(config, on_event)
    try:
        asyncio.run(crawler.run())
    except KeyboardInterrupt:
        crawler.stop()
        click.echo("Stopped.", err=True)
        raise SystemExit(130)
    except Exception as exc:
        click.echo(f"SiteMap-X failed: {exc}", err=True)
        if config.verbose:
            raise
        raise SystemExit(1)


if __name__ == "__main__":
    main()
