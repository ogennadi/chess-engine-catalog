import json
import unittest
from pathlib import Path

from collectors.openbench import collect, parse


STOCK = """
<ul><li class="header">Support</li>
<li><a href="https://github.com/AndyGrant/OpenBench">OpenBench</a></li></ul>
<ul><li class="header">Engines</li>
<li><a href="https://github.com/jhonnold/berserk">Berserk</a></li>
<li><a href="https://github.com/AndyGrant/Stockfish">Stockfish</a></li>
<li><a href="https://github.com/crippa1337/svart/">Svart</a></li>
</ul>
<a href="https://github.com/jhonnold/berserk/compare/a..b">diff</a>
"""
RESTYLED = """
<details class="engine-directory"><summary>Engines <span>3</span></summary><div>
<a href="https://github.com/kz04px/4ku">4ku <span aria-hidden="true">&#8599;</span></a>
<a href="https://github.com/ChessCom/TorchDev">Torch <span>\u2197</span></a>
<a href="https://example.org/engine">Homepage</a>
</div></details>
<div class="support-links"><a href="https://github.com/Silverrzz/MattBench">OpenBench</a></div>
"""


class OpenBenchTests(unittest.TestCase):
    def test_stock_sidebar_uses_originals_for_forks_and_moved_repositories(self):
        rows = parse(STOCK, "https://ob.example/")
        self.assertEqual([row["family"] for row in rows], ["Berserk", "Stockfish", "Svart"])
        self.assertEqual(rows[0]["code_urls"], [{
            "url": "https://github.com/jhonnold/berserk", "evidence_url": "https://ob.example/",
        }])
        self.assertEqual(rows[1]["code_urls"], [{
            "url": "https://github.com/official-stockfish/Stockfish",
            "evidence_url": "https://github.com/AndyGrant/Stockfish",
        }])
        self.assertEqual(rows[2]["code_urls"][0]["url"], "https://github.com/feliskio/svart")
        self.assertEqual(rows[2]["project_url"], "https://github.com/crippa1337/svart")

    def test_restyled_directory_drops_private_and_non_forge_links(self):
        rows = collect(lambda url: RESTYLED, "https://mb.example/index/")
        self.assertEqual([row["family"] for row in rows], ["4ku", "Torch", "Homepage"])
        self.assertEqual(len(rows[0]["code_urls"]), 1)
        self.assertEqual(rows[1]["code_urls"], [])
        self.assertIn("closed source", rows[1]["project_url_note"])
        self.assertEqual(rows[2]["code_urls"], [])

    def test_missing_engine_directory_is_an_error(self):
        with self.assertRaises(ValueError):
            parse("<ul><li class='header'>Tests</li></ul>", "https://ob.example/")

    def test_variant_only_engines_are_skipped(self):
        page = (
            '<ul><li class="header">Engines</li>'
            '<li><a href="https://github.com/sscg13/Frolic">Frolic</a></li>'
            '<li><a href="https://github.com/sscg13/Prolix">Prolix</a></li></ul>'
        )
        self.assertEqual([row["family"] for row in parse(page, "https://ob.example/")], ["Frolic"])


class SourceProvenanceTests(unittest.TestCase):
    def test_every_registered_source_has_a_provenance_page(self):
        root = Path(__file__).resolve().parent.parent
        sources = json.loads((root / "sources.json").read_text(encoding="utf-8"))
        index = (root / "docs" / "sources" / "README.md").read_text(encoding="utf-8")
        for source in sources:
            page = root / "docs" / "sources" / (source["id"] + ".md")
            self.assertTrue(page.exists(), page)
            self.assertIn(source["url"], page.read_text(encoding="utf-8"))
            self.assertIn(f"({source['id']}.md)", index)


if __name__ == "__main__":
    unittest.main()
