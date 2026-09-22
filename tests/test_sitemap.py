from __future__ import annotations

import gzip

from sitemapx.parse.sitemap import looks_like_sitemap, parse_sitemap, sitemap_kind


INDEX = b'''<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap><loc>https://example.test/sitemap-a.xml</loc></sitemap>
<sitemap><loc>https://example.test/sitemap-b.xml</loc></sitemap>
</sitemapindex>'''
CHILD_A = b'''<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>/a/one</loc></url><url><loc>/a/two</loc></url><url><loc>/a/three</loc></url></urlset>'''
CHILD_B = b'''<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>/b/one</loc></url><url><loc>/b/two</loc></url><url><loc>/b/three</loc></url></urlset>'''


def test_two_level_sitemap_index_yields_six_pages():
    _, children = parse_sitemap(INDEX, "https://example.test/")
    pages = []
    for child in children:
        body = CHILD_A if child.endswith("a.xml") else CHILD_B
        urls, nested = parse_sitemap(body, child)
        pages.extend(urls)
        assert nested == []
    assert len(pages) == 6
    assert sitemap_kind(INDEX) == "index"
    assert sitemap_kind(CHILD_A) == "urlset"


def test_uncompressed_and_gzipped_variants_parse_identically():
    for body in (INDEX, gzip.compress(INDEX)):
        assert looks_like_sitemap("https://example.test/sitemap.xml", "application/xml", body)
        _, children = parse_sitemap(body, "https://example.test/")
        assert len(children) == 2
    for body in (CHILD_A, gzip.compress(CHILD_A)):
        assert looks_like_sitemap("https://example.test/sitemap-a.xml.gz", "application/gzip", body)
        urls, _ = parse_sitemap(body, "https://example.test/sitemap-a.xml.gz")
        assert len(urls) == 3
