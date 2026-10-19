import tempfile
import unittest
from pathlib import Path

import source_status


def engine(name, code=()):
    return {
        "name": name, "aliases": [], "chessprogramming_wiki": {},
        "provenance": [{"source": "ccrl", "label": name, "url": "https://example.org/list"}],
        "source_code": [dict(c) for c in code],
    }


RECORD = {
    "tier": "A", "licensing": "open_source", "availability": "available", "confidence": "high",
    "source_urls": [{"url": "https://github.com/a/alpha", "kind": "original repository", "license": "MIT"}],
    "evidence": [{"url": "https://github.com/a/alpha", "quote": "MIT License"}],
    "rationale": "Author repository with MIT license.",
}


class SourceStatusTests(unittest.TestCase):
    def test_validate_requires_known_values_and_source_for_available(self):
        self.assertEqual(source_status.validate("Alpha", RECORD), [])
        broken = {**RECORD, "availability": "maybe", "source_urls": []}
        self.assertTrue(any("availability" in p for p in source_status.validate("Alpha", broken)))
        missing = {**RECORD, "source_urls": []}
        self.assertTrue(any("without source_urls" in p for p in source_status.validate("Alpha", missing)))
        search_only = {**RECORD, "availability": "not_located", "source_urls": [],
                       "evidence": [{"search": "alpha chess", "quote": "nothing"}]}
        self.assertEqual(source_status.validate("Alpha", search_only), [])

    def test_attach_adds_researched_links_once_and_labels_availability(self):
        catalog = {"engines": [
            engine("Alpha", [{"url": "https://github.com/a/alpha/", "evidence_url": "x", "source": "ccrl"}]),
            engine("Beta"), engine("Gamma", [{"url": "https://g.example/src", "evidence_url": "y", "source": "ccrl"}]),
        ]}
        status = {"families": {
            "Alpha": RECORD,
            "Beta": {**RECORD, "source_urls": [{"url": "https://codeberg.org/b/beta"}]},
        }}
        source_status.attach(catalog, status)
        alpha, beta, gamma = catalog["engines"]
        self.assertEqual(len(alpha["source_code"]), 1)
        self.assertEqual(beta["source_code"][0]["source"], "source-status-research")
        self.assertEqual(beta["source_code"][0]["evidence_url"], "https://github.com/a/alpha")
        self.assertEqual(source_status.availability_label(beta), "available")
        self.assertEqual(source_status.availability_label(gamma), "linked")
        self.assertEqual(source_status.availability_label(engine("Delta")), "not_checked")

    def test_not_located_records_add_no_links(self):
        catalog = {"engines": [engine("Beta")]}
        record = {**RECORD, "availability": "released_not_located"}
        source_status.attach(catalog, {"families": {"Beta": record}})
        self.assertEqual(catalog["engines"][0]["source_code"], [])

    def test_family_pages_have_unique_slugs_and_remove_stale_pages(self):
        engines = [engine("Chess.cpp"), engine("chess-cpp"), engine("Ålpha")]
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / "stale.md").write_text("old", encoding="utf-8")
            source_status.render_family_pages(engines, {"families": {"Ålpha": RECORD}}, target)
            names = sorted(p.name for p in target.glob("*.md"))
            self.assertEqual(names, ["README.md", "alpha.md", "chess-cpp-2.md", "chess-cpp.md"])
            page = (target / "alpha.md").read_text(encoding="utf-8")
            self.assertIn("MIT", page)
            self.assertIn("open_source", page)


if __name__ == "__main__":
    unittest.main()
