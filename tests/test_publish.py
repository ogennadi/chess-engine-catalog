import json
import re
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import publish


def engine(name, aliases=(), code=(), provenance=None, wiki=None):
    return {
        "name": name, "aliases": list(aliases),
        "chessprogramming_wiki": wiki or {"status": "not_found", "titles_checked": [name]},
        "provenance": provenance or [{"source": "ccrl", "label": name, "url": "https://example.org/list"}],
        "source_code": [dict(c) for c in code],
    }


CATALOG = {
    "generated_at": "2026-10-20T00:00:00+00:00",
    "sources": [{"id": "ccrl", "name": "CCRL", "url": "https://example.org/list", "status": "collected"}],
    "engines": [
        engine("Alpha", aliases=["Alfa"], code=[{
            "url": "https://github.com/a/alpha", "evidence_url": "https://example.org/list", "source": "ccrl",
        }], provenance=[{
            "source": "rwbc", "label": "Alpha", "url": "https://example.org/rwbc",
            "alternate_names": "AlphaChess\n(Pesto PST)", "row": ["raw"], "headers": ["raw"],
        }]),
        engine("Beta"),
        engine("Gamma", wiki={"status": "found", "url": "https://chessprogramming.org/Gamma", "title": "Gamma"}),
        {**engine("Delta"), "rejected_source_code": [{
            "url": "https://github.com/d/delta-releases", "evidence_url": "https://example.org/list",
            "source": "ccrl", "reason": "Binaries only.", "review_evidence_url": "https://example.org/delta-bin",
        }]},
        engine("Evil", code=[{"url": "javascript:alert(1)", "evidence_url": "javascript:alert(2)", "source": "ccrl"}]),
    ],
}
STATUS = {"families": {
    "Beta": {
        "tier": "D", "licensing": "unknown", "availability": "archived_only", "confidence": "medium",
        "source_urls": [{"url": "https://web.archive.org/beta.zip", "kind": "archive", "license": "none stated"}],
        "evidence": [{"url": "https://example.org/beta", "quote": "Beta <b>source</b> zip"}],
        "rationale": "Archived source only.", "release_scope": "Beta 1.0 only",
    },
    "Gamma": {
        "tier": "E", "licensing": "proprietary", "availability": "not_located", "confidence": "low",
        "source_urls": [], "evidence": [{"search": "gamma chess source", "quote": "nothing found"}],
        "rationale": "No copy found.", "identity_issue": "Two programs share this name.",
    },
    "Delta": {
        "tier": "review", "licensing": "open_source", "availability": "not_located", "confidence": "high",
        "source_urls": [], "evidence": [{"source": "dossier: RWBC", "quote": "GPL"}],
        "rationale": "Licence stated, code missing.", "identity_issue": "Successor's code is not Delta's.",
        "needs_review": False, "notes": "Reviewed with the user.",
    },
}}
REGISTRY = [
    {"id": "ccrl", "name": "CCRL", "url": "https://example.org/list", "collector": "ccrl"},
    {"id": "rwbc", "name": "RWBC", "url": "https://example.org/rwbc", "collector": "rwbc"},
]
OVERRIDES = {"aliases": {"Alpha-Chess": "Alpha"}, "source_aliases": [{
    "sources": ["ccrl"], "family": "Gamma", "target": "Gamma (Smith)",
    "evidence_url": "https://example.org/gamma-author", "note": "Different author.",
}], "related_families": [{
    "family": "Delta", "relation": "derived_from", "related": "Alpha",
    "note": "Port of Alpha.", "evidence_url": "https://example.org/delta-port",
}]}
DOCS = {
    "ccrl": "# CCRL\n\n- **URL:** <https://example.org/list>\n\n## How it was found\n\n"
            "Listed in the [README](../../README.md) and [RWBC](rwbc.md).\n",
    "README": "# Sources\n\n## OpenBench candidates not registered\n\n| Instance | Reason |\n|---|---|\n| x.example | HTTP 404 |\n",
}


def no_network(*args, **kwargs):
    raise AssertionError("publish.py must not access the network")


class PublishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.temp.name) / "dist"
        with mock.patch.object(socket.socket, "connect", no_network), \
                mock.patch.object(socket, "create_connection", no_network):
            cls.result = publish.build(CATALOG, STATUS, REGISTRY, OVERRIDES, {}, DOCS, cls.out)
        cls.index = (cls.out / "index.html").read_text(encoding="utf-8")
        cls.sources = (cls.out / "sources.html").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def family(self, slug):
        return (self.out / "families" / f"{slug}.html").read_text(encoding="utf-8")

    def rows(self):
        return re.findall(r'<tr data-names="([^"]*)" data-availability="([^"]*)">(.*?)</tr>', self.index, re.S)

    def test_writes_complete_site_with_downloads(self):
        for path in ("index.html", "sources.html", "assets/site.css", "assets/site.js", "assets/theme.js",
                     "downloads/engines.csv", "downloads/engines.json", "downloads/source-status.json",
                     "downloads/source-available-engines.pdf"):
            self.assertTrue((self.out / path).is_file(), path)
        self.assertEqual(len(list((self.out / "families").glob("*.html"))), 5)
        self.assertTrue((self.out / "downloads/source-available-engines.pdf").read_bytes().startswith(b"%PDF"))
        self.assertIn("Beta", json.loads((self.out / "downloads/engines.json").read_text(encoding="utf-8"))
                      ["engines"][1]["name"])
        self.assertTrue((self.out / "downloads/engines.csv").read_text(encoding="utf-8").startswith("name,aliases"))
        self.assertEqual(self.result[0], 5)

    def test_does_not_modify_input_catalog(self):
        self.assertNotIn("source_status", CATALOG["engines"][1])

    def test_index_table_shows_canonical_names_and_searches_aliases(self):
        rows = self.rows()
        self.assertEqual(len(rows), 5)
        names = [re.search(r'<th scope="row"><a href="families/[^"]+">([^<]+)</a>', r[2]).group(1) for r in rows]
        self.assertEqual(names, ["Alpha", "Beta", "Delta", "Evil", "Gamma"])
        self.assertIn('<td class="index-number">1</td>', rows[0][2])
        alpha = json.loads(rows[0][0].replace("&quot;", '"'))
        self.assertEqual(alpha, ["Alpha", "Alfa", "Alpha-Chess", "AlphaChess"])
        self.assertNotIn("Pesto", self.index)
        self.assertNotIn("Alfa</", self.index)
        self.assertEqual(self.index.count("<th scope=\"col\">"), 3)

    def test_index_availability_labels_and_links(self):
        rows = {re.search(r">([^<]+)</a></th>", r[2]).group(1): r for r in self.rows()}
        self.assertEqual(rows["Alpha"][1], "linked")
        self.assertIn('href="https://github.com/a/alpha"', rows["Alpha"][2])
        self.assertEqual(rows["Beta"][1], "archived_only")
        self.assertIn("Archived only", rows["Beta"][2])
        self.assertIn('href="https://web.archive.org/beta.zip"', rows["Beta"][2])
        self.assertEqual(rows["Gamma"][1], "not_located")
        self.assertIn("Source not located", rows["Gamma"][2])
        self.assertNotIn("closed", rows["Gamma"][2].casefold())

    def test_header_links_and_no_per_family_pdfs(self):
        self.assertEqual(self.index.count('href="downloads/source-available-engines.pdf"'), 1)
        self.assertIn('href="sources.html"', self.index)
        self.assertIn(f'href="{publish.REPOSITORY}"', self.index)
        for slug in ("alpha", "beta", "gamma", "delta"):
            self.assertNotIn(".pdf", self.family(slug))

    def test_filters_hidden_without_javascript_and_dark_default(self):
        self.assertIn('<form id="filters" role="search" hidden>', self.index)
        self.assertIn('<button type="button" id="clear-search" aria-label="Clear search" hidden>', self.index)
        self.assertIn('<option value="available">Source available (including archived only)</option>', self.index)
        self.assertIn('<html lang="en" data-theme="dark">', self.index)
        self.assertNotIn(" hidden>", "".join(r[2] for r in self.rows()))

    def test_links_are_relative_or_external(self):
        pages = [self.index, self.sources, *(self.family(s) for s in ("alpha", "beta", "gamma", "delta", "evil"))]
        for html in pages:
            for href in re.findall(r'(?:href|src)="([^"]+)"', html):
                self.assertFalse(href.startswith(("/", "file:", "javascript:")), href)
                if not href.startswith(("http://", "https://", "#")):
                    self.assertNotIn("://", href)

    def test_untrusted_urls_and_text_are_escaped(self):
        evil = self.family("evil")
        self.assertNotIn('href="javascript:', evil + self.index)
        self.assertIn("javascript:alert(1)", evil)
        self.assertIn("Beta &lt;b&gt;source&lt;/b&gt; zip", self.family("beta"))

    def test_related_families_reviewed_both_ways_and_similar_names_flagged(self):
        related = lambda html: html.split('id="related"')[1].split("</section>")[0]
        delta = related(self.family("delta"))
        self.assertIn('<strong>Derived from:</strong> <a href="alpha.html">Alpha</a>. Port of Alpha.', delta)
        self.assertIn('href="https://example.org/delta-port"', delta)
        self.assertIn('<strong>Has derivative:</strong> <a href="delta.html">Delta</a>', related(self.family("alpha")))
        self.assertIn("<strong>Same name, different program:</strong> Gamma (Smith).", related(self.family("gamma")))
        self.assertNotIn('id="related"', self.family("beta"))
        engines = [{"name": n, "provenance": []} for n in ("Atlas", "Atlas (1967)", "Atlas (Bell)", "Atlantis")]
        similar = publish.similar_names(engines)
        rules = {"related_families": [{"family": "Atlas (Bell)", "relation": "same_name", "related": "Atlas"}]}
        self.assertEqual(publish.related_families(engines[0], rules, similar),
                         ([("Same name, different program", "Atlas (Bell)", "", None)], ["Atlas (1967)"]))
        self.assertEqual(publish.related_families(engines[3], rules, similar), ([], []))

    def test_family_page_shows_deduplicated_authors_first(self):
        engine = {"name": "Abbess", "provenance": [
            {"source": "rwbc", "authors": "Pope Robert\n*Diaz Daniel*\n-"},
            {"source": "computer-chess-org", "author": "Robert Pope, Daniel Díaz"},
            {"source": "wiki-engines", "listed_name": "Abbess", "label": "Abbess by Robert Pope"},
        ]}
        self.assertEqual(publish.authors(engine), [
            ("Robert Pope, Daniel Díaz", ["wiki-engines", "computer-chess-org", "rwbc"]),
        ])
        self.assertEqual(publish.authors({"provenance": [
            {"source": "rwbc", "authors": "Atkin Larry\nFrey Peter"},
        ]}), [("Atkin Larry", ["rwbc"]), ("Frey Peter", ["rwbc"])])
        porter = {"provenance": [{"source": "rwbc", "authors": "Tridgel Andrew\n(Ablett Jim)"}]}
        self.assertEqual(publish.authors(porter), [("Tridgel Andrew", ["rwbc"])])
        self.assertEqual(publish.also_credited(porter), ["Ablett Jim"])
        lucas = {"provenance": [{"source": "lucas-chess", "author": "Lucas Monge"},
                                {"source": "computer-chess-org", "author": "Lucas Monge"}]}
        self.assertEqual(publish.authors(lucas), [("Lucas Monge", ["computer-chess-org", "lucas-chess"])])
        alpha = self.family("alpha")
        self.assertLess(alpha.index("<dt>Author</dt>"), alpha.index("<dt>Source availability</dt>"))
        self.assertIn("Not recorded by the collected lists", alpha)

    def test_family_page_research_details(self):
        beta = self.family("beta")
        for expected in ("Archived source only", "Unknown", "Medium", "Beta 1.0 only", "none stated",
                         "<blockquote>", 'href="https://example.org/beta"', "Archived source only.",
                         'href="../sources.html#ccrl"', 'href="https://example.org/list"'):
            self.assertIn(expected, beta)
        alpha = self.family("alpha")
        self.assertIn("Not separately researched", alpha)
        self.assertIn("<li>Alpha-Chess</li>", alpha)
        self.assertNotIn("raw", alpha)
        gamma = self.family("gamma")
        self.assertIn('href="https://chessprogramming.org/Gamma"', gamma)
        self.assertIn("Search: <q>gamma chess source</q>", gamma)

    def test_open_questions_are_separate_from_reviewed_decisions(self):
        def sections(html):
            open_part = html.split('id="open-questions"')[1].split("</section>")[0]
            reviewed = html.split('id="decisions"')[1].split("</section>")[0]
            return open_part, reviewed
        gamma_open, gamma_reviewed = sections(self.family("gamma"))
        self.assertIn("Two programs share this name.", gamma_open)
        self.assertIn("Different author.", gamma_reviewed)
        self.assertIn('href="https://example.org/gamma-author"', gamma_reviewed)
        delta_open, delta_reviewed = sections(self.family("delta"))
        self.assertNotIn("Successor", delta_open)
        self.assertIn("Successor&#x27;s code is not Delta&#x27;s.", delta_reviewed)
        self.assertIn("Reviewed with the user.", delta_reviewed)
        self.assertIn('Not counted as source code: <a href="https://github.com/d/delta-releases"', delta_reviewed)
        self.assertIn("Binaries only.", delta_reviewed)
        self.assertNotIn("delta-releases", self.family("delta").split('id="decisions"')[0])
        beta_open, _ = sections(self.family("beta"))
        self.assertIn("Licence for https://web.archive.org/beta.zip is not clearly established", beta_open)

    def test_sources_page_is_consolidated(self):
        for source in REGISTRY:
            self.assertIn(f'<section id="{source["id"]}">', self.sources)
            self.assertIn(f'href="{source["url"]}"', self.sources)
        self.assertIn('id="methodology"', self.sources)
        self.assertIn("How it was found", self.sources)
        self.assertIn(f'href="{publish.REPOSITORY_FILES}README.md"', self.sources)
        self.assertIn('href="#rwbc"', self.sources)
        self.assertIn("<td>x.example</td>", self.sources)
        self.assertFalse((self.out / "sources").exists())

    def test_rebuild_removes_stale_generated_family_pages(self):
        stale = self.out / "families" / "removed.html"
        stale.write_text("<!doctype html>\n" + publish.GENERATED, encoding="utf-8")
        keep = self.out / "families" / "handwritten.html"
        keep.write_text("not generated", encoding="utf-8")
        publish.build(CATALOG, STATUS, REGISTRY, OVERRIDES, {}, DOCS, self.out)
        self.assertFalse(stale.exists())
        self.assertTrue(keep.exists())
        keep.unlink()

    def test_refuses_repository_root_and_unregistered_sources(self):
        with self.assertRaises(ValueError):
            publish.build(CATALOG, STATUS, REGISTRY, OVERRIDES, {}, DOCS, publish.ROOT)
        with tempfile.TemporaryDirectory() as temp, self.assertRaises(ValueError):
            publish.build(CATALOG, STATUS, REGISTRY[:1], OVERRIDES, {}, DOCS, Path(temp))


if __name__ == "__main__":
    unittest.main()
