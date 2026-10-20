import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from collectors.wiki_sources import SOURCE_ID, PageLinks, attach, check, links_digest, orphan_reviews


class WikiSourceTests(unittest.TestCase):
    def engine(self, name="Engine", codes=None, url="https://chessprogramming.org/Engine"):
        return {
            "name": name, "aliases": [], "provenance": [], "source_code": codes or [],
            "chessprogramming_wiki": {"status": "found", "url": url},
        }

    def fetch(self, html):
        def fetch(url):
            return "<article>" + html + "</article>"
        fetch.checked_at = {"https://chessprogramming.org/Engine": "2026-10-19T00:00:00+00:00"}
        return fetch

    def review(self, codes):
        return {"Engine": {
            "wiki_url": "https://chessprogramming.org/Engine",
            "note": "Reviewed engine project; not a dependency.",
            "code_urls": codes,
        }}

    def test_parser_preserves_nested_labels_and_decodes_escaped_urls(self):
        parser = PageLinks("https://chessprogramming.org/Engine")
        parser.feed(
            '<a href="/Other">Other</a>'
            '<a href="https://github.com/a/engine?x=1&amp;y=2"><b>Engine</b> source</a>'
        )
        self.assertEqual(parser.links, [{
            "url": "https://github.com/a/engine?x=1&y=2", "label": "Engine source",
        }])

    def test_only_reviewed_engine_links_are_accepted_not_dependencies_or_profiles(self):
        html = (
            '<a href="https://github.com/author">Author</a>'
            '<a href="https://github.com/author/dependency">Dependency</a>'
            '<a href="https://github.com/author/engine">Engine source</a>'
        )
        results = check([self.engine()], self.fetch(html), self.review([{
            "url": "https://github.com/author/engine", "source_release": "historical 1.0",
        }]))
        result = results["engines"]["Engine"]
        self.assertEqual(result["status"], "found")
        self.assertEqual(len(result["external_links"]), 3)
        self.assertEqual(len(result["code_urls"]), 1)
        self.assertEqual(result["code_urls"][0]["source"], SOURCE_ID)
        self.assertEqual(result["code_urls"][0]["source_release"], "historical 1.0")
        self.assertEqual(result["code_urls"][0]["evidence_url"], result["wiki_url"])

    def test_unreviewed_and_reviewed_negative_results_are_distinct(self):
        engines = [self.engine()]
        fetch = self.fetch('<a href="https://example.com/engine.zip">Download</a>')
        self.assertEqual(check(engines, fetch, {})["engines"]["Engine"]["status"], "needs_review")
        result = check(engines, fetch, self.review([]))["engines"]["Engine"]
        self.assertEqual(result["status"], "no_source_link_found")
        self.assertEqual(result["code_urls"], [])

    def test_nonwiki_source_coverage_skips_requests_but_prior_wiki_links_are_rechecked(self):
        covered = self.engine(codes=[{"url": "https://example.com/source", "source": "ccrl"}])
        def no_fetch(url):
            self.fail("Already covered families must not cause requests")
        self.assertEqual(check([covered], no_fetch, {}), {"engines": {}})
        unchecked = self.engine()
        unchecked["chessprogramming_wiki"]["status"] = "not_found"
        self.assertEqual(check([unchecked], no_fetch, {}), {"engines": {}})
        wiki_only = self.engine(codes=[{"url": "https://example.com/source", "source": SOURCE_ID}])
        self.assertIn("Engine", check([wiki_only], self.fetch(""), {})["engines"])

    def test_research_links_do_not_skip_and_reviewed_pages_are_always_rechecked(self):
        researched = self.engine(codes=[{"url": "https://example.com/s", "source": "source-status-research"}])
        self.assertIn("Engine", check([researched], self.fetch(""), {})["engines"])
        covered = self.engine(codes=[{"url": "https://example.com/s", "source": "computer-chess-org"}])
        self.assertEqual(check([covered], self.fetch(""), self.review([]))["engines"]["Engine"]["status"],
                         "no_source_link_found")
        self.assertEqual(orphan_reviews([self.engine()], {**self.review([]), "Renamed": {}}), ["Renamed"])

    def test_missing_reviewed_link_or_changed_identity_fails(self):
        review = self.review([{"url": "https://github.com/a/engine"}])
        with self.assertRaises(ValueError):
            check([self.engine()], self.fetch("No source"), review)
        review["Engine"]["wiki_url"] = "https://chessprogramming.org/Unrelated"
        with self.assertRaises(ValueError):
            check([self.engine()], self.fetch(""), review)

    def test_changed_external_links_require_review_instead_of_reusing_negative_decision(self):
        review = self.review([])
        review["Engine"]["links_sha256"] = links_digest(["https://example.com/"])
        result = check(
            [self.engine()],
            self.fetch('<a href="https://github.com/a/engine">New source</a>'), review,
        )["engines"]["Engine"]
        self.assertEqual(result["status"], "needs_review")
        self.assertIn("changed since review", result["note"])

    def test_error_page_fails_instead_of_recording_no_source(self):
        fetch = self.fetch("")
        def error_page(url):
            return "<html>Access denied</html>"
        error_page.checked_at = fetch.checked_at
        with self.assertRaises(ValueError):
            check([self.engine()], error_page, self.review([]))

    def test_normalized_project_link_retains_exact_wiki_link_evidence(self):
        code = {
            "url": "https://github.com/a/engine", "link_url": "https://github.com/a/engine/releases",
        }
        result = check(
            [self.engine()], self.fetch('<a href="https://github.com/a/engine/releases">Releases</a>'),
            self.review([code]),
        )["engines"]["Engine"]
        self.assertEqual(result["code_urls"][0]["url"], code["url"])
        self.assertEqual(result["code_urls"][0]["link_url"], code["link_url"])

    def test_attachment_is_idempotent_and_drops_links_for_changed_wiki_identity(self):
        results = check(
            [self.engine()], self.fetch('<a href="https://github.com/a/engine">Engine</a>'),
            self.review([{"url": "https://github.com/a/engine"}]),
        )
        catalog = {"engines": [self.engine()]}
        attach(catalog, results)
        attach(catalog, results)
        self.assertEqual(len(catalog["engines"][0]["source_code"]), 1)
        self.assertEqual(catalog["chessprogramming_source_code"]["found"], 1)
        catalog["engines"][0]["chessprogramming_wiki"]["url"] += "_Other"
        attach(catalog, results)
        self.assertEqual(catalog["engines"][0]["source_code"], [])

    def test_publish_preserves_saved_wiki_sources_in_both_exports(self):
        from collect import publish
        results = check(
            [self.engine()], self.fetch('<a href="https://github.com/a/engine">Engine</a>'),
            self.review([{"url": "https://github.com/a/engine"}]),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            (root / "data" / "chessprogramming-source-code.json").write_text(
                json.dumps(results), encoding="utf-8",
            )
            with patch("collect.ROOT", root):
                publish({"engines": [self.engine()]}, [])
            catalog = json.loads((root / "data" / "engines.json").read_text(encoding="utf-8"))
            self.assertEqual(catalog["engines"][0]["source_code"][0]["source"], SOURCE_ID)
            self.assertIn("https://github.com/a/engine",
                          (root / "data" / "engines.csv").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
