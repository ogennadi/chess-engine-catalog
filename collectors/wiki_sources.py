"""Preserve reviewed source-code links found on engine wiki pages."""

import hashlib
import json
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit


SOURCE_ID = "chessprogramming-wiki"
DERIVED_SOURCES = {SOURCE_ID, "source-status-research"}


class PageLinks(HTMLParser):
    def __init__(self, page_url):
        super().__init__()
        self.page_url = page_url
        self.links = []
        self.current = None
        self.has_article = False

    def handle_starttag(self, tag, attrs):
        if tag == "article":
            self.has_article = True
        if tag == "a":
            self.current = {"url": urljoin(self.page_url, dict(attrs).get("href", "")), "label": ""}

    def handle_data(self, data):
        if self.current is not None:
            self.current["label"] += data

    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            parsed = urlsplit(self.current["url"])
            if parsed.scheme in ("http", "https") and parsed.hostname != urlsplit(self.page_url).hostname:
                self.current["label"] = " ".join(self.current["label"].split())
                if self.current not in self.links:
                    self.links.append(self.current)
            self.current = None


def links_digest(urls):
    return hashlib.sha256(json.dumps(sorted(set(urls)), ensure_ascii=True).encode()).hexdigest()


def check(engines, fetch, reviews):
    results = {}
    for engine in engines:
        wiki = engine.get("chessprogramming_wiki", {})
        # Research links are attached after this check and often came from the wiki page itself,
        # so only links from the provenance lists count as independent coverage.
        covered = any(code.get("source") not in DERIVED_SOURCES for code in engine["source_code"])
        if wiki.get("status") != "found" or (covered and engine["name"] not in reviews):
            continue
        url = wiki["url"]
        parser = PageLinks(url)
        parser.feed(fetch(url))
        if not parser.has_article:
            raise ValueError(f"Wiki response has no article content for {engine['name']}")
        links = {link["url"] for link in parser.links}
        review = reviews.get(engine["name"])
        result = {
            "wiki_url": url, "checked_at": fetch.checked_at[url],
            "status": "needs_review", "code_urls": [],
            "external_links": parser.links,
        }
        if review is not None:
            if review["wiki_url"] != url:
                raise ValueError(f"Reviewed wiki identity changed for {engine['name']}")
            if review.get("links_sha256", links_digest(links)) != links_digest(links):
                result["note"] = "External links changed since review; source decisions need review."
                results[engine["name"]] = result
                continue
            result["note"] = review["note"]
            for code in review["code_urls"]:
                if code.get("link_url", code["url"]) not in links:
                    raise ValueError(f"Reviewed source link missing from {engine['name']} wiki page")
                result["code_urls"].append({
                    **code, "evidence_url": url, "source": SOURCE_ID,
                    "checked_at": fetch.checked_at[url],
                })
            result["status"] = "found" if result["code_urls"] else "no_source_link_found"
        results[engine["name"]] = result
    return {"engines": results}


def orphan_reviews(engines, reviews):
    """Reviewed wiki pages whose family no longer exists (renamed or merged)."""
    names = {engine["name"] for engine in engines}
    return sorted(name for name in reviews if name not in names)


def attach(catalog, results):
    counts = {"found": 0, "no_source_link_found": 0, "needs_review": 0}
    for engine in catalog["engines"]:
        engine["source_code"] = [
            code for code in engine["source_code"] if code.get("source") != SOURCE_ID
        ]
        result = results["engines"].get(engine["name"])
        if result is None:
            continue
        wiki = engine.get("chessprogramming_wiki", {})
        if wiki.get("status") != "found" or wiki["url"] != result["wiki_url"]:
            continue
        counts[result["status"]] += 1
        for code in result["code_urls"]:
            if code not in engine["source_code"]:
                engine["source_code"].append(code)
        engine["source_code"].sort(key=lambda code: (code["url"], code["evidence_url"]))
    catalog["chessprogramming_source_code"] = counts
